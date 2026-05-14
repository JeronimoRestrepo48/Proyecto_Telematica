FROM python:3.12-slim
WORKDIR /app
RUN apt-get update && apt-get install -y --no-install-recommends libpq5 \
    && rm -rf /var/lib/apt/lists/*
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
ENV PYTHONUNBUFFERED=1
ENV MPLBACKEND=Agg
EXPOSE 5050
CMD ["gunicorn", "--bind", "0.0.0.0:5050", "--workers", "1", "app:app"]
