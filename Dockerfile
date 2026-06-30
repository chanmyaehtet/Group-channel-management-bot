# Hugging Face Spaces — Docker Blank
FROM python:3.11-slim

# HF Spaces runs as non-root user
RUN useradd -m -u 1000 botuser

WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy source code
COPY --chown=botuser:botuser . .

USER botuser

# No port needed — pure Telegram bot (long-polling)
CMD ["python", "main.py"]
