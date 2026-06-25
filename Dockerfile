FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app
COPY app.py /app/app.py
COPY templates /app/templates
COPY static /app/static

EXPOSE 8090
CMD ["python", "/app/app.py"]
