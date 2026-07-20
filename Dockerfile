FROM python:3.14-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .

RUN pip install --upgrade pip \
    && pip install --no-cache-dir -r requirements.txt \
    && pip install --no-cache-dir gunicorn psycopg[binary]

COPY . .


EXPOSE 8000


CMD ["sh", "-c", "python manage.py collectstatic --noinput && python manage.py migrate --noinput && gunicorn --bind 0.0.0.0:8000 --workers 3 core.wsgi:application"]
