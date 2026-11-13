from __future__ import annotations

import csv
import io
import json
from datetime import date

from fastapi import APIRouter, Depends, HTTPException, UploadFile
from sqlmodel import Session, select

from .. import services
from ..connectors.registry import statuses
from ..db import get_session
from ..models import (Alert, Device, Flight, HotelBooking, JobRun, Purchase, Subscription, Transaction, Trip, Watch,
                      utcnow)
from ..notify import apns
from ..rules import flights as flight_rules
from ..rules.returns import return_window
from .deps import Auth
from .schemas import (DeviceIn, FlightIn, HotelIn, PurchaseIn, PurchaseOut, TransactionIn, TripIn, WatchIn)

router = APIRouter(dependencies=[Auth])
public = APIRouter()


@public.get("/health")
def health(s: Session = Depends(get_session)):
    runs = {}
    for name in services.JOBS:
        jr = s.exec(select(JobRun).where(JobRun.job == name).order_by(JobRun.started_at.desc())).first()
        runs[name] = None if not jr else {"at": jr.started_at, "ok": jr.ok, "detail": jr.detail}
    return {"ok": True, "version": "0.1.0", "connectors": [c.__dict__ for c in statuses()],
            "apns_configured": apns.configured(), "jobs": runs}


# ---------------------------------------------------------------- alerts
@router.get("/alerts")
def alerts(unread_only: bool = False, limit: int = 100, s: Session = Depends(get_session)):
    q = select(Alert).where(Alert.dismissed_at.is_(None)).order_by(Alert.created_at.desc()).limit(limit)
    if unread_only:
        q = q.where(Alert.read_at.is_(None))
    return [{**a.model_dump(), "payload": json.loads(a.payload_json)} for a in s.exec(q).all()]


@router.post("/alerts/{alert_id}/read")
def alert_read(alert_id: int, s: Session = Depends(get_session)):
    a = s.get(Alert, alert_id) or _404()
    a.read_at = utcnow(); s.add(a); s.commit()
    return {"ok": True}


@router.post("/alerts/{alert_id}/dismiss")
def alert_dismiss(alert_id: int, s: Session = Depends(get_session)):
    a = s.get(Alert, alert_id) or _404()
    a.dismissed_at = utcnow(); s.add(a); s.commit()
    return {"ok": True}


# ---------------------------------------------------------------- purchases / return windows
def _pout(p: Purchase, today: date) -> PurchaseOut:
    rw = return_window(p, today)
    return PurchaseOut(**{k: getattr(p, k) for k in ("id", "retailer", "order_id", "item_name", "sku", "price", "purchased_on",
                                                        "delivered_on", "returned")},
                       deadline=rw.deadline, days_left=rw.days_left, urgency=rw.urgency, rule=rw.rule,
                       is_holiday_extension=rw.is_holiday_extension)


@router.get("/purchases", response_model=list[PurchaseOut])
def purchases(include_closed: bool = False, s: Session = Depends(get_session)):
    today = date.today()
    rows = [_pout(p, today) for p in s.exec(select(Purchase).order_by(Purchase.purchased_on.desc())).all()]
    if not include_closed:
        rows = [r for r in rows if r.urgency not in ("closed",) and not r.returned]
    rows.sort(key=lambda r: (r.days_left is None, r.days_left if r.days_left is not None else 0))
    return rows


@router.post("/purchases", response_model=PurchaseOut)
def purchase_add(body: PurchaseIn, s: Session = Depends(get_session)):
    p = Purchase(**body.model_dump())
    s.add(p); s.commit(); s.refresh(p)
    return _pout(p, date.today())


@router.post("/purchases/{pid}/returned")
def purchase_returned(pid: int, s: Session = Depends(get_session)):
    p = s.get(Purchase, pid) or _404()
    p.returned = True; s.add(p); s.commit()
    return {"ok": True}


@router.delete("/purchases/{pid}")
def purchase_delete(pid: int, s: Session = Depends(get_session)):
    p = s.get(Purchase, pid) or _404()
    s.delete(p); s.commit()
    return {"ok": True}


# ---------------------------------------------------------------- watches
@router.get("/watches")
def watches(s: Session = Depends(get_session)):
    return s.exec(select(Watch).where(Watch.active == True)).all()  # noqa: E712


@router.post("/watches")
def watch_add(body: WatchIn, s: Session = Depends(get_session)):
    w = Watch(**body.model_dump()); s.add(w); s.commit(); s.refresh(w)
    return w


@router.delete("/watches/{wid}")
def watch_del(wid: int, s: Session = Depends(get_session)):
    w = s.get(Watch, wid) or _404()
    w.active = False; s.add(w); s.commit()
    return {"ok": True}


# ---------------------------------------------------------------- flights / hotels / trips
@router.get("/flights")
def flights(s: Session = Depends(get_session)):
    out = []
    for f in s.exec(select(Flight).order_by(Flight.scheduled_departure.desc())).all():
        claims = flight_rules.evaluate(f)
        out.append({**f.model_dump(), "claims": [c.__dict__ for c in claims], "at_stake": flight_rules.total_at_stake(claims)})
    return out


@router.post("/flights")
def flight_add(body: FlightIn, s: Session = Depends(get_session)):
    f = Flight(**body.model_dump()); s.add(f); s.commit()
    services._auto_trips(s)
    s.refresh(f)  # _auto_trips commits, which expires f; refresh before serialising
    return f


@router.get("/hotels")
def hotels(s: Session = Depends(get_session)):
    return s.exec(select(HotelBooking).order_by(HotelBooking.check_in)).all()


@router.post("/hotels")
def hotel_add(body: HotelIn, s: Session = Depends(get_session)):
    h = HotelBooking(**body.model_dump()); s.add(h); s.commit(); s.refresh(h)
    return h


@router.get("/trips")
def trips(s: Session = Depends(get_session)):
    return s.exec(select(Trip).order_by(Trip.travel_date)).all()


@router.post("/trips")
def trip_add(body: TripIn, s: Session = Depends(get_session)):
    t = Trip(**body.model_dump()); s.add(t); s.commit(); s.refresh(t)
    return t


@router.get("/trips/{tid}/brief")
async def trip_brief(tid: int, s: Session = Depends(get_session)):
    t = s.get(Trip, tid) or _404()
    f = s.get(Flight, t.flight_id) if t.flight_id else None
    return await services.build_brief(t, f)


# ---------------------------------------------------------------- subscriptions
@router.get("/subscriptions")
def subscriptions(s: Session = Depends(get_session)):
    rows = s.exec(select(Subscription).order_by(Subscription.amount.desc())).all()
    monthly = sum(r.amount * {"weekly": 52 / 12, "monthly": 1, "yearly": 1 / 12}[r.cadence] for r in rows)
    return {"monthly_total": round(monthly, 2), "items": rows}


@router.post("/subscriptions/{sid}/ack")
def sub_ack(sid: int, s: Session = Depends(get_session)):
    r = s.get(Subscription, sid) or _404()
    r.acknowledged = True; s.add(r); s.commit()
    return {"ok": True}


@router.post("/subscriptions/{sid}/flag-cancel")
def sub_flag(sid: int, s: Session = Depends(get_session)):
    r = s.get(Subscription, sid) or _404()
    r.flagged_cancel = True; s.add(r); s.commit()
    return {"ok": True}


@router.post("/transactions")
def tx_add(body: TransactionIn, s: Session = Depends(get_session)):
    t = Transaction(**body.model_dump(), source="manual"); s.add(t); s.commit(); s.refresh(t)
    return t


@router.post("/transactions/import-csv")
async def tx_import(file: UploadFile, s: Session = Depends(get_session)):
    """Bank/card CSV export. Finds Date / Description / Amount columns by name (case-insensitive)."""
    text = (await file.read()).decode("utf-8-sig", "replace")
    rdr = csv.DictReader(io.StringIO(text))
    cols = {c.lower().strip(): c for c in (rdr.fieldnames or [])}
    dcol = next((cols[c] for c in cols if c in ("date", "transaction date", "posted date", "post date")), None)
    mcol = next((cols[c] for c in cols if c in ("description", "merchant", "name", "payee")), None)
    acol = next((cols[c] for c in cols if c in ("amount", "debit", "transaction amount")), None)
    if not (dcol and mcol and acol):
        raise HTTPException(400, f"could not find date/description/amount columns in {rdr.fieldnames}")
    from dateutil import parser as dtp
    n = 0
    for i, row in enumerate(rdr):
        try:
            amt = abs(float(str(row[acol]).replace("$", "").replace(",", "")))
            d = dtp.parse(row[dcol]).date()
        except (ValueError, TypeError):
            continue
        ref = f"csv:{file.filename}:{i}"
        if s.exec(select(Transaction).where(Transaction.source_ref == ref)).first():
            continue
        s.add(Transaction(merchant=row[mcol], amount=amt, posted_on=d, source="csv", source_ref=ref)); n += 1
    s.commit()
    return {"imported": n}


# ---------------------------------------------------------------- devices / jobs
@router.post("/devices")
def device_register(body: DeviceIn, s: Session = Depends(get_session)):
    d = s.exec(select(Device).where(Device.token == body.token)).first() or Device(**body.model_dump())
    d.platform, d.name, d.last_seen = body.platform, body.name, utcnow()
    s.add(d); s.commit(); s.refresh(d)
    return d


@router.post("/jobs/{name}/run")
async def job_run(name: str):
    if name not in services.JOBS:
        raise HTTPException(404, f"unknown job; valid: {sorted(services.JOBS)}")
    jr = await services.run_job(name, services.JOBS[name])
    return jr


def _404():
    raise HTTPException(404, "not found")
