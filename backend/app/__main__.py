import uvicorn

from .config import get_settings

if __name__ == "__main__":
    uvicorn.run("app.main:app", host="0.0.0.0", port=8787, log_level=get_settings().log_level.lower())
