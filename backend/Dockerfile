FROM python:3.14-slim

WORKDIR /app

# Install uv for fast dependency management
RUN pip install --no-cache-dir uv

# Copy project definition first for layer caching
COPY pyproject.toml .

# Install dependencies
RUN uv pip install --system -e .

# Copy application code
COPY ogi/ ogi/

# Default plugins directory (populated via volume mount at runtime)
RUN mkdir -p plugins

EXPOSE 8000

CMD ["uvicorn", "ogi.main:app", "--host", "0.0.0.0", "--port", "8000"]
