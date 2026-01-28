FROM python:3.11-slim

WORKDIR /app

# Install dependencies
COPY pyproject.toml .
RUN pip install --no-cache-dir .

# Copy source
COPY src/ src/

# Set Python path
ENV PYTHONPATH=/app/src

# Run the bot
CMD ["python", "-m", "aswa_slack.app"]
