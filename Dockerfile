FROM python:3.11-slim

WORKDIR /app

# System deps for curl_cffi (libcurl)
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc g++ libcurl4-openssl-dev curl ca-certificates \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Persist data dir
VOLUME ["/app/JioData"]

CMD ["python", "-u", "bot.py"]
