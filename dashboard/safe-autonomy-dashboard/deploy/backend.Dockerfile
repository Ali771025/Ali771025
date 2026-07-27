FROM python:3.12-slim AS runtime
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app
COPY pyproject.toml ./
COPY backend ./backend
RUN pip install --no-cache-dir .
RUN addgroup --system dashboard && adduser --system --ingroup dashboard dashboard \
    && mkdir -p /app/runtime && chown -R dashboard:dashboard /app/runtime
USER dashboard
EXPOSE 8080 15010/udp 15011
CMD ["uvicorn", "flight_dashboard.main:app", "--host", "0.0.0.0", "--port", "8080", "--workers", "1", "--loop", "uvloop"]

