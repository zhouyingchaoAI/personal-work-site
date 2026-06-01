FROM python:3.10-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    HOST=0.0.0.0 \
    PORT=8765 \
    OPENCLAW_PLATFORM_INTERNAL_URL=http://host.docker.internal:18080/openclaw \
    OPENCLAW_PLATFORM_PUBLIC_URL=https://yfdemo.chencytech.com/openclaw \
    OPENCLAW_OFFICE_SSO_SECRET=openclaw-office-sso-dev

WORKDIR /app

# 中文字体：OFD 渲染（easyofd）需要，否则发票文字渲染为空白。
# 用开源文泉驿字体顶替 easyofd font_map 期望的系统字体文件名。
RUN apt-get update \
    && apt-get install -y --no-install-recommends fonts-wqy-zenhei \
    && rm -rf /var/lib/apt/lists/* \
    && mkdir -p /opt/ofdfonts \
    && for f in simsun.ttc simkai.ttf simhei.ttf COURI.TTF courbd.TTF; do \
         cp /usr/share/fonts/truetype/wqy/wqy-zenhei.ttc /opt/ofdfonts/$f; \
       done

COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt
COPY . /app

RUN mkdir -p /app/user_data /app/backend/generated /app/backend/drafts \
    && chmod +x /app/start.sh

EXPOSE 8765

CMD ["python3", "app.py"]
