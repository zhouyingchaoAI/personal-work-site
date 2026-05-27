FROM python:3.10-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    HOST=0.0.0.0 \
    PORT=8765 \
    OPENCLAW_PLATFORM_INTERNAL_URL=http://host.docker.internal:18080/openclaw \
    OPENCLAW_PLATFORM_PUBLIC_URL=https://yfdemo.chencytech.com/openclaw \
    OPENCLAW_OFFICE_SSO_SECRET=openclaw-office-sso-dev

WORKDIR /app
COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt
COPY . /app

RUN mkdir -p /app/user_data /app/backend/generated /app/backend/drafts \
    && chmod +x /app/start.sh

EXPOSE 8765

CMD ["python3", "app.py"]
