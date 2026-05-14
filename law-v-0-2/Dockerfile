FROM python:3.12-slim

WORKDIR /app

COPY pyproject.toml /app/
RUN pip install --no-cache-dir -e . 2>/dev/null || pip install --no-cache-dir .

COPY app/ /app/

ENV PYTHONPATH=/app
EXPOSE 8000

CMD ["python3", "/app/main.py"]
