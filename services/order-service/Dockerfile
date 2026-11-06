FROM python:3.12-slim AS builder

WORKDIR /app
COPY packages/common /app/packages/common
COPY services/order-service/requirements.txt /app/
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt && \
    pip install --no-cache-dir -e /app/packages/common

FROM python:3.12-slim
WORKDIR /app
RUN useradd -m -u 1000 appuser

COPY --from=builder /usr/local/lib/python3.12/site-packages /usr/local/lib/python3.12/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin
COPY packages/common /app/packages/common
COPY contracts /app/contracts
COPY services/order-service /app

ENV PYTHONPATH=/app:/app/packages/common
USER appuser

EXPOSE 8005
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8005"]
