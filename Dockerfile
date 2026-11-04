# Airlock API — the control plane. It runs OUR code and drives the host Docker daemon
# through the mounted socket (compose); it never runs PR code in its own container.
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY app ./app
COPY policies ./policies
COPY eval_cases ./eval_cases
# baked-in benchmark results as a fallback; on the VM a named volume is mounted here so
# `make bench` results survive rebuilds
COPY eval_results ./eval_results

EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
