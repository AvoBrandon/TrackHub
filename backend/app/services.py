"""The watchers. Each `job_*` is scheduled in scheduler.py and can also be run on demand via the API.
They are deliberately small: load rows, call a connector, run a rule, emit alerts, log a JobRun."""
from __future__ import annotations

import asyncio
import json
import logging
from datetime import date, datetime, timedelta

from sqlmodel import Session, select

from .config import get_settings
from .connectors import aeroapi, bestbuy, ebay, hotels, keepa, tsa, weather
from .connectors.base import ConnectorError
from .db import session
from .ingest import gmail
from .ingest.parsers.charges import parse_charge
from .ingest.parsers.retail import delivery_date_update, parse_order
from .ingest.parsers.travel import parse_flights, parse_hotels
from .models import (Alert, AlertKind, Device, Flight, HotelBooking, JobRun, PriceObservation, Purchase, Retailer,
                     Subscription, Transaction, Trip, Watch, utcnow)
from .notify import apns
from .notify.outbox import emit
from .rules import flights as flight_rules
from .rules import hotels as hotel_rules
from .rules import subscriptions as sub_rules
from .rules.price_adjust import opportunities
from .rules.returns import ALERT_DAYS, return_window
from .rules.tripbrief import maps_links, packing_list, summarise

log = logging.getLogger(__name__)


# ----------------------------------------------------------------------------- plumbing
async def run_job(name: str, fn, *args) -> JobRun:
    with session() as s:
        jr = JobRun(job=name)
        s.add(jr)
        s.commit()
        s.refresh(jr)
        jid = jr.id
    detail, ok = "", True
    try:
        res = fn(*args)
        if asyncio.iscoroutine(res):
            res = await res
        detail = str(res or "")
    except Exception as e:  # noqa: BLE001 - a watcher must never take the service down
        ok, detail = False, f"{type(e).__name__}: {e}"
        log.exception("job %s failed", name)
    with session() as s:
        jr = s.get(JobRun, jid)
        jr.finished_at, jr.ok, jr.detail = utcnow(), ok, detail[:2000]
        s.add(jr)
        s.commit()
        s.refresh(jr)
        return jr


# ----------------------------------------------------------------------------- 0. ingestion
def job_ingest_gmail() -> str:
    if not gmail.credentials_ready():
        return "skipped: Gmail not connected (see docs/SETUP.md)"
    with session() as s:
        known = set(s.exec(select(Purchase.source_message_id)).all()) | set(s.exec(select(Flight.source_message_id)).all()) \
            | set(s.exec(select(HotelBooking.source_message_id)).all()) | set(s.exec(select(Transaction.source_ref)).all())
    emails = gmail.fetch_recent(known_ids=known)
    n_p = n_f = n_h = n_t = n_d = 0
    with session() as s:
        for e in emails:
            for p in parse_order(e):
                s.add(p); n_p += 1
            upd = delivery_date_update(e)
            if upd:
                oid, when = upd
                for p in s.exec(select(Purchase).where(Purchase.order_id == oid, Purchase.delivered_on.is_(None))).all():
                    p.delivered_on = when; s.add(p); n_d += 1
            for f in parse_flights(e):
                if not s.exec(select(Flight).where(Flight.flight_number == f.flight_number,
                                                   Flight.scheduled_departure == f.scheduled_departure)).first():
                    s.add(f); n_f += 1
            for h in parse_hotels(e):
                if not s.exec(select(HotelBooking).where(HotelBooking.confirmation == h.confirmation)).first():
                    s.add(h); n_h += 1
            t = parse_charge(e)
            if t and not parse_order(e):
                s.add(t); n_t += 1
        s.commit()
        _auto_trips(s)
    return f"emails={len(emails)} purchases={n_p} deliveries={n_d} flights={n_f} hotels={n_h} charges={n_t}"


def _auto_trips(s: Session) -> None:
    """Every upcoming flight gets a Trip (home -> origin airport) so the brief fires the evening before."""
    cfg = get_settings()
    for f in s.exec(select(Flight).where(Flight.scheduled_departure >= datetime.now())).all():
        if s.exec(select(Trip).where(Trip.flight_id == f.id)).first():
            continue
        s.add(Trip(label=f"{f.flight_number} {f.origin}→{f.destination}", travel_date=f.scheduled_departure.date(),
                   origin_address=cfg.home_address or "Current Location", destination_address=f"{f.origin} Airport",
                   destination_city=f.destination, flight_id=f.id))
    s.commit()


# ----------------------------------------------------------------------------- 11. return windows
def job_return_windows(today: date | None = None) -> str:
    today = today or date.today()
    n = 0
    with session() as s:
        for p in s.exec(select(Purchase).where(Purchase.returned == False)).all():  # noqa: E712
            rw = return_window(p, today)
            if rw.deadline is None or rw.days_left is None or rw.days_left < 0:
                continue
            if rw.days_left in ALERT_DAYS:
                when = "today" if rw.days_left == 0 else f"in {rw.days_left} day{'s' if rw.days_left > 1 else ''}"
                if emit(s, AlertKind.return_window, f"return:{p.id}:{rw.days_left}",
                        f"Return window closes {when}: {p.item_name[:60]}",
                        f"${p.price:,.2f} at {p.retailer.value.title()}, order {p.order_id}. Deadline {rw.deadline:%a %b %d}. {rw.rule}",
                        money=p.price, payload={"purchase_id": p.id, "deadline": rw.deadline.isoformat()}):
                    n += 1
    return f"alerts={n}"


# ----------------------------------------------------------------------------- 12/20. price adjust + card protection
async def job_price_adjust(today: date | None = None) -> str:
    today = today or date.today()
    bb, kp = bestbuy.BestBuy(), keepa.Keepa()
    checked = alerts = 0
    with session() as s:
        for p in s.exec(select(Purchase).where(Purchase.returned == False)).all():  # noqa: E712
            if (today - p.purchased_on).days > 95 or not p.sku:
                continue
            price = None
            try:
                if p.retailer == Retailer.bestbuy and bb.configured():
                    off = await bb.product(p.sku); price, src, url = off.price, "bestbuy", off.url
                elif p.retailer == Retailer.amazon and kp.configured():
                    ap = await kp.product(p.sku); price, src, url = ap.best_new, "keepa", ap.url
            except ConnectorError as e:
                log.warning("price check %s: %s", p.sku, e)
            if price is None:
                continue
            checked += 1
            s.add(PriceObservation(purchase_id=p.id, source=src, price=price, url=url))
            for op in opportunities(p, price, today):
                kind = AlertKind.card_protection if op.route == "card_price_protection" else AlertKind.price_adjust
                if emit(s, kind, f"{op.route}:{p.id}:{int(price)}",
                        f"Get ${op.refund:,.2f} back on {p.item_name[:50]}",
                        f"Now ${price:,.2f} (you paid ${p.price:,.2f}). {op.how}" + (f" Deadline {op.deadline:%b %d}." if op.deadline else ""),
                        money=op.refund, action_url=url, payload={"purchase_id": p.id, "route": op.route}):
                    alerts += 1
        s.commit()
    return f"checked={checked} alerts={alerts}"


# ----------------------------------------------------------------------------- 14. open-box + cross-market watcher
async def job_watches() -> str:
    bb, eb, kp = bestbuy.BestBuy(), ebay.Ebay(), keepa.Keepa()
    alerts = 0
    with session() as s:
        for w in s.exec(select(Watch).where(Watch.active == True)).all():  # noqa: E712
            offers: list[tuple[str, float, str, str]] = []  # (source, price, condition, url)
            try:
                if w.bestbuy_sku and bb.configured():
                    if w.want_open_box:
                        offers += [("bestbuy", o.price, o.condition, o.url) for o in await bb.open_box(w.bestbuy_sku)]
                    n = await bb.product(w.bestbuy_sku); offers.append(("bestbuy", n.price, "new", n.url))
                if w.amazon_asin and kp.configured():
                    ap = await kp.product(w.amazon_asin)
                    if ap.best_new: offers.append(("amazon", ap.best_new, "new", ap.url))
                    if ap.warehouse_price and w.want_open_box: offers.append(("amazon", ap.warehouse_price, "warehouse", ap.url))
                if w.ebay_query and eb.configured():
                    for l in (await eb.search(w.ebay_query, max_price=w.target_price))[:5]:
                        offers.append(("ebay", l.landed, l.condition.lower(), l.url))
            except ConnectorError as e:
                log.warning("watch %s: %s", w.label, e)
            for src, price, cond, url in offers:
                s.add(PriceObservation(watch_id=w.id, source=src, price=price, condition=cond, url=url))
                hit_target = w.target_price is not None and price <= w.target_price
                new_open_box = w.want_open_box and cond.startswith(("open-box", "warehouse"))
                if hit_target or new_open_box:
                    kind = AlertKind.open_box if new_open_box else AlertKind.price_watch
                    if emit(s, kind, f"watch:{w.id}:{src}:{cond}:{int(price)}",
                            f"{w.label}: ${price:,.2f} {cond} on {src.title()}",
                            ("Open-box unit available. " if new_open_box else "") + (f"Under your ${w.target_price:,.2f} target. " if hit_target else "") + "Tap to view.",
                            money=(w.target_price or price) - price if w.target_price else 0, action_url=url,
                            payload={"watch_id": w.id, "source": src}):
                        alerts += 1
        s.commit()
    return f"alerts={alerts}"


# ----------------------------------------------------------------------------- 1. flight delay compensation
async def job_flights(now: datetime | None = None) -> str:
    now = now or datetime.now()
    api = aeroapi.AeroAPI()
    updated = alerts = 0
    with session() as s:
        window = s.exec(select(Flight).where(Flight.scheduled_departure >= now - timedelta(days=2),
                                             Flight.scheduled_departure <= now + timedelta(hours=6))).all()
        for f in window:
            if api.configured():
                try:
                    st = await api.flight_status(f.flight_number, f.scheduled_departure)
                    f.cancelled = st.cancelled
                    f.status = "cancelled" if st.cancelled else (st.status or f.status)
                    if st.actual_in: f.actual_arrival = st.actual_in.replace(tzinfo=None) if st.actual_in.tzinfo else st.actual_in
                    if st.actual_out: f.actual_departure = st.actual_out.replace(tzinfo=None) if st.actual_out.tzinfo else st.actual_out
                    if st.scheduled_in and st.actual_in:  # align to the same clock as the API
                        f.scheduled_arrival = st.scheduled_in.replace(tzinfo=None) if st.scheduled_in.tzinfo else st.scheduled_in
                    if st.distance_km: f.distance_km = st.distance_km
                    s.add(f); updated += 1
                except ConnectorError as e:
                    log.warning("flight %s: %s", f.flight_number, e)
            claims = flight_rules.evaluate(f)
            if claims:
                total = flight_rules.total_at_stake(claims)
                body = "\n".join(f"• {c.regime}: {c.amount:,.0f} {c.currency} ({c.confidence}). {c.next_step}" for c in claims)
                if emit(s, AlertKind.flight_comp, f"flightcomp:{f.id}:{'c' if f.cancelled else 'd'}",
                        f"You may be owed money for {f.flight_number} {f.origin}→{f.destination}", body, money=total,
                        payload={"flight_id": f.id, "claims": [c.__dict__ for c in claims]}):
                    alerts += 1
        s.commit()
    return f"tracked={len(window)} updated={updated} alerts={alerts}"


# ----------------------------------------------------------------------------- 2. hotel rebook
async def job_hotels(today: date | None = None) -> str:
    today = today or date.today()
    api = hotels.GenericHotelAPI()
    alerts = 0
    with session() as s:
        for b in s.exec(select(HotelBooking).where(HotelBooking.check_in > today)).all():
            if b.free_cancel_until and datetime.now() > b.free_cancel_until:
                continue
            if api.configured() and b.provider_hotel_id:
                try:
                    offers = [o for o in await api.offers(b.provider_hotel_id, b.check_in, b.check_out) if o.refundable]
                except ConnectorError as e:
                    log.warning("hotel %s: %s", b.confirmation, e); offers = []
                if offers:
                    best = min(offers, key=lambda o: o.total)
                    if b.best_seen_price is None or best.total < b.best_seen_price:
                        b.best_seen_price, b.best_seen_at = best.total, utcnow(); s.add(b)
                    adv = hotel_rules.advise(b, best.total)
                    if adv.should_rebook and emit(s, AlertKind.hotel_rebook, f"hotel:{b.id}:{int(best.total)}",
                                                  f"Rebook {b.hotel_name} and save ${adv.savings:,.2f}", adv.reason,
                                                  money=adv.savings, action_url=best.url, payload={"hotel_id": b.id}):
                        alerts += 1
            else:
                # no API: a weekly 10-second manual check with the exact dates pre-filled
                week = today.isocalendar()[1]
                links = hotels.manual_check_links(b.hotel_name, b.city, b.check_in, b.check_out)
                if emit(s, AlertKind.hotel_rebook, f"hotel-manual:{b.id}:{today.year}-{week}",
                        f"Re-check price: {b.hotel_name} ({b.check_in:%b %d}–{b.check_out:%b %d})",
                        f"You paid ${b.total_price:,.2f}. Open the links, compare the refundable rate; if it's lower, book it then cancel {b.confirmation}.",
                        action_url=links["google_hotels"], payload={"hotel_id": b.id, "links": links}):
                    alerts += 1
        s.commit()
    return f"alerts={alerts}"


# ----------------------------------------------------------------------------- 3. TSA morning
async def job_tsa(today: date | None = None) -> str:
    today = today or date.today()
    t = tsa.TSA()
    alerts = 0
    with session() as s:
        for f in s.exec(select(Flight).where(Flight.scheduled_departure >= datetime.combine(today, datetime.min.time()),
                                             Flight.scheduled_departure < datetime.combine(today + timedelta(days=1), datetime.min.time()))).all():
            try:
                rows = await t.wait_times(f.origin)
                latest = rows[0] if rows else None
                body = (f"Latest reported wait at {f.origin}: ~{latest.minutes} min (checkpoint {latest.checkpoint}). "
                        if latest else f"No recent report for {f.origin}. ") + f"Live page: {tsa.TSA.fallback_url(f.origin)}"
            except ConnectorError:
                body = f"TSA feed unavailable this morning. Check {f.origin}'s live page: {tsa.TSA.fallback_url(f.origin)}"
            if emit(s, AlertKind.tsa_wait, f"tsa:{f.id}:{today}", f"Security at {f.origin} for {f.flight_number} ({f.scheduled_departure:%-I:%M %p})",
                    body, action_url=tsa.TSA.fallback_url(f.origin), payload={"flight_id": f.id}):
                alerts += 1
        s.commit()
    return f"alerts={alerts}"


# ----------------------------------------------------------------------------- 4. trip brief
async def build_brief(trip: Trip, flight: Flight | None) -> dict:
    w = weather.Weather()
    days = []
    try:
        if trip.destination_lat is None:
            lat, lon, _ = await w.geocode(trip.destination_city)
        else:
            lat, lon = trip.destination_lat, trip.destination_lon
        days = await w.forecast(lat, lon, 4)
    except ConnectorError as e:
        log.warning("weather: %s", e)
    links = maps_links(trip.origin_address, trip.destination_address)
    return {
        "trip_id": trip.id, "label": trip.label, "date": trip.travel_date.isoformat(),
        "flight": f"{flight.flight_number} departs {flight.scheduled_departure:%-I:%M %p}" if flight else None,
        "weather": summarise(days), "packing": packing_list(days, flying=flight is not None), "maps": links,
    }


async def job_trip_brief(today: date | None = None) -> str:
    today = today or date.today()
    alerts = 0
    with session() as s:
        for t in s.exec(select(Trip).where(Trip.travel_date == today + timedelta(days=1), Trip.brief_sent_at.is_(None))).all():
            f = s.get(Flight, t.flight_id) if t.flight_id else None
            brief = await build_brief(t, f)
            body = (f"{brief['flight']}\n" if brief["flight"] else "") + f"Weather at {t.destination_city}:\n{brief['weather']}\n\n" \
                   f"Pack: {', '.join(brief['packing'][:8])}…\n\nDirections are ready in the app: tap Apple Maps or Google Maps."
            if emit(s, AlertKind.trip_brief, f"brief:{t.id}", f"Tomorrow: {t.label}", body, action_url=brief["maps"]["apple"], payload=brief):
                alerts += 1
            t.brief_sent_at = utcnow(); s.add(t)
        s.commit()
    return f"alerts={alerts}"


# ----------------------------------------------------------------------------- 29. subscriptions
def job_subscriptions(today: date | None = None) -> str:
    today = today or date.today()
    with session() as s:
        recs = sub_rules.detect(s.exec(select(Transaction)).all(), today)
        for r in recs:
            existing = s.exec(select(Subscription).where(Subscription.merchant == r.merchant)).first()
            if existing:
                existing.amount, existing.cadence, existing.last_charged, existing.next_expected, existing.confidence = \
                    r.amount, r.cadence, r.last_charged, r.next_expected, r.confidence
                s.add(existing)
            else:
                s.add(Subscription(merchant=r.merchant, amount=r.amount, cadence=r.cadence, last_charged=r.last_charged,
                                   next_expected=r.next_expected, confidence=r.confidence))
        s.commit()
        report = sub_rules.monthly_report(recs)
        emit(s, AlertKind.subscriptions, f"subs:{today:%Y-%m}", f"Subscription creep report — {today:%B}", report,
             money=sum(r.yearly_cost for r in recs) / 12, payload={"count": len(recs)})
    return f"recurring={len(recs)}"


# ----------------------------------------------------------------------------- push
async def job_push() -> str:
    if not apns.configured():
        return "skipped: APNs not configured (Windows app polls; iPhone needs APNs keys)"
    sent = 0
    with session() as s:
        pending = s.exec(select(Alert).where(Alert.pushed_at.is_(None))).all()
        devices = s.exec(select(Device).where(Device.platform == "ios")).all()
        for a in pending:
            ok_any = False
            for d in devices:
                if await apns.send(d.token, a.title, a.body[:200], {"alert_id": a.id, "kind": a.kind.value}):
                    ok_any = True
            if ok_any or not devices:
                a.pushed_at = utcnow(); s.add(a); sent += 1
        s.commit()
    return f"pushed={sent}"


JOBS = {
    "ingest_gmail": job_ingest_gmail, "return_windows": job_return_windows, "price_adjust": job_price_adjust,
    "watches": job_watches, "flights": job_flights, "hotels": job_hotels, "tsa": job_tsa,
    "trip_brief": job_trip_brief, "subscriptions": job_subscriptions, "push": job_push,
}
