# backend

```bash
python -m venv .venv && . .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -e ".[dev]"
cp .env.example .env                           # fill in what you have
python -m app                                  # http://localhost:8787/health
pytest                                         # 47 tests, no network needed
```
Manual job trigger: `curl -X POST -H "Authorization: Bearer $API_TOKEN" localhost:8787/api/jobs/return_windows/run`
