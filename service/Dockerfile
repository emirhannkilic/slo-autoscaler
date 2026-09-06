FROM python:3.12-slim

WORKDIR /app
COPY pyproject.toml ./
COPY src ./src
COPY service ./service
RUN pip install --no-cache-dir '.[service]'

USER 10001
EXPOSE 8080
CMD ["uvicorn", "service.app:app", "--host", "0.0.0.0", "--port", "8080"]
