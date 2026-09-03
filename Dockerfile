FROM python:3.11-slim

WORKDIR /app

ENV PYTHONUNBUFFERED=1     PORT=8080     GOOGLE_CLOUD_PROJECT=ag-test-1310     GOOGLE_CLOUD_LOCATION=global

COPY requirements.txt .
COPY agent/requirements.txt agent_reqs.txt
RUN pip install --no-cache-dir -r requirements.txt -r agent_reqs.txt

COPY . .

EXPOSE 8080

CMD ["python", "web_server.py"]
