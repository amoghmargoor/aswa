FROM python:3.11-slim

WORKDIR /app

COPY pyproject.toml .
RUN pip install --no-cache-dir .

COPY src/ src/

ENV PYTHONPATH=/app/src

EXPOSE 3978

CMD ["python", "-m", "aswa_teams.app"]
