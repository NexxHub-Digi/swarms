# Build with the REPOSITORY ROOT as context:
# docker build -f nexx_gateway/Dockerfile -t nexx-swarms-gateway .
FROM python:3.11-slim
WORKDIR /app
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
COPY pyproject.toml README.md ./
COPY swarms/ ./swarms/
RUN pip install --no-cache-dir .
COPY nexx_gateway/ ./nexx_gateway/
RUN pip install --no-cache-dir -r nexx_gateway/requirements.txt
RUN useradd -u 10001 --create-home serviceuser
USER serviceuser
EXPOSE 8000
CMD ["uvicorn", "nexx_gateway.app:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]
