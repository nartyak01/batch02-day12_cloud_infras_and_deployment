FROM python:3.11-slim

WORKDIR /app

COPY 05-scaling-reliability/production/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY 05-scaling-reliability/production/app.py .
RUN mkdir -p /app/utils
COPY 05-scaling-reliability/production/utils/mock_llm.py /app/utils/mock_llm.py

ENV PYTHONPATH=/app
EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')" || exit 1

CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8000"]
