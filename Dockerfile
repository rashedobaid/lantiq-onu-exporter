FROM python:3.15-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY lantiq_onu_exporter/ lantiq_onu_exporter/

USER nobody
EXPOSE 9877
CMD ["python", "-u", "-m", "lantiq_onu_exporter"]
