FROM python:3.12-slim

WORKDIR /app
COPY pyproject.toml .
COPY src ./src
RUN pip install --no-cache-dir .

RUN mkdir -p /var/lib/document-intelligence
VOLUME ["/var/lib/document-intelligence"]
EXPOSE 8000
CMD ["uvicorn", "document_intelligence.main:app", "--host", "0.0.0.0", "--port", "8000"]
