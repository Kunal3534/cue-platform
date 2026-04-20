# Pin to bookworm (Debian 12) — python:3.11-slim otherwise follows Debian's
# rolling tag and broke when upstream moved to trixie (libgdk-pixbuf rename).
FROM python:3.11-slim-bookworm

WORKDIR /app
ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1

# WeasyPrint system deps (Pango, Cairo, GLib, fontconfig)
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc libpq-dev \
    libpango-1.0-0 libpangoft2-1.0-0 libpangocairo-1.0-0 \
    libcairo2 libgdk-pixbuf-2.0-0 libffi-dev \
    shared-mime-info libglib2.0-0 \
    fontconfig fonts-liberation \
 && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8000
# Run migrations before uvicorn starts. `bash -c` lets us chain commands and
# fail fast if alembic errors out.
CMD ["bash", "-c", "alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port 8000"]
