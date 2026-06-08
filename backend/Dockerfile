FROM python:3.12-slim

WORKDIR /app/backend

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

COPY requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt \
    && groupadd --system --gid 10001 app \
    && useradd --system --uid 10001 --gid app --home-dir /app/backend --shell /usr/sbin/nologin app \
    && mkdir -p /app/data /app/backend

COPY --chown=app:app app ./app
COPY --chown=app:app config ./config
RUN chown -R app:app /app/backend /app/data \
    && chmod -R a-w /app/backend/app /app/backend/config

USER app
EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
