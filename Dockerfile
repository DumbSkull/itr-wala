# Engine service: FastAPI behind the AWS Lambda Web Adapter.
# Same container runs locally (docker run -p 8000:8000) and as a Lambda
# function (Function URL). Align the adapter version with Work/Dockerfile.api.
FROM public.ecr.aws/docker/library/python:3.12-slim

COPY --from=public.ecr.aws/awsguru/aws-lambda-adapter:0.9.1 /lambda-adapter /opt/extensions/lambda-adapter

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PORT=8000 \
    AWS_LWA_READINESS_CHECK_PATH=/health

WORKDIR /app

# deps first for layer caching
COPY pyproject.toml ./
RUN pip install --no-cache-dir "fastapi>=0.115,<1" "pydantic>=2.7,<3" "jsonschema>=4.22,<5" "uvicorn>=0.30,<1" "pdfplumber>=0.11,<1" "python-multipart>=0.0.9"

COPY skills/itr-wala/scripts ./skills/itr-wala/scripts
COPY service ./service
RUN rm -rf service/tests

# Non-root; the service is stateless and writes nothing.
RUN useradd --uid 10001 --no-create-home app
USER app

EXPOSE 8000
CMD ["sh", "-c", "uvicorn service.app:app --host 0.0.0.0 --port ${PORT}"]
