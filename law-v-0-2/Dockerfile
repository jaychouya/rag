FROM python:3.12-slim

WORKDIR /build
COPY pyproject.toml /build/
COPY app/ /build/app/
RUN pip install --no-cache-dir -i https://pypi.tuna.tsinghua.edu.cn/simple . && rm -rf /build

WORKDIR /app
COPY app/ /app/

ENV PYTHONPATH=/app
EXPOSE 8000

CMD ["python3", "/app/main.py"]
