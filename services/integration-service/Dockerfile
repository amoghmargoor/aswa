FROM python:3.11-slim

WORKDIR /app

# Install dependencies
COPY pyproject.toml .
RUN pip install --no-cache-dir .

# Copy application code
COPY src/ src/

# Set Python path
ENV PYTHONPATH=/app/src

# Expose port
EXPOSE 8004

# Run the application
CMD ["python", "-m", "aswa_integrations.main"]
