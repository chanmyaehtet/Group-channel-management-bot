FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
# Use main.py (FastAPI + uvicorn webhook server) for Render deployment.
# This opens the HTTP port Render requires. Use main_polling.py only for
# local polling mode (e.g. GitHub Actions).
CMD ["python", "main.py"]
