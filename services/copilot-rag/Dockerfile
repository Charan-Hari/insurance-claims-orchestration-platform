FROM python:3.12-slim
WORKDIR /app
COPY pyproject.toml .
COPY src ./src
RUN pip install --no-cache-dir .
RUN mkdir -p /var/lib/copilot-rag
EXPOSE 8000
CMD ["uvicorn", "copilot_rag.main:app", "--host", "0.0.0.0", "--port", "8000"]
