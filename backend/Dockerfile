FROM python:3.12-slim
WORKDIR /srv
COPY pyproject.toml ./
RUN pip install --no-cache-dir . 2>/dev/null || true
COPY . .
RUN pip install --no-cache-dir -e .
VOLUME ["/srv/data", "/srv/secrets"]
EXPOSE 8787
HEALTHCHECK CMD python -c "import urllib.request;urllib.request.urlopen('http://localhost:8787/health')"
CMD ["python", "-m", "app"]
