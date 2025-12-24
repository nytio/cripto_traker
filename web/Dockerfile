FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

RUN addgroup --system app && adduser --system --ingroup app app

RUN apt-get update \
    && apt-get install -y --no-install-recommends build-essential \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

ENV CMDSTAN=/opt/cmdstan/latest
ENV MPLCONFIGDIR=/tmp/matplotlib
RUN python - <<'PY'
from cmdstanpy import install_cmdstan, cmdstan_path
import os

install_cmdstan(dir="/opt/cmdstan")
path = cmdstan_path()
link = "/opt/cmdstan/latest"
if os.path.islink(link) or os.path.exists(link):
    os.unlink(link)
os.symlink(path, link)
PY
RUN chmod -R a+rX /opt/cmdstan

COPY . .

USER app

EXPOSE 8000

CMD ["gunicorn", "-b", "0.0.0.0:8000", "wsgi:app"]
