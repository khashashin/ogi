FROM python:3.14-slim

WORKDIR /app

# Install uv for fast dependency management
RUN pip install --no-cache-dir uv

# Install C-compiler for packages missing 3.14 wheels (like pyroaring)
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    python3-dev \
    && rm -rf /var/lib/apt/lists/*

# Set up a venv since python 3.14 marks itself as externally managed
RUN uv venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Copy project definition first for layer caching
COPY pyproject.toml .

# Install dependencies into the venv
RUN uv pip install -e .

# Copy application code and migrations
COPY ogi/ ogi/
COPY alembic/ alembic/
COPY alembic.ini .

# Default plugins directory (populated via volume mount at runtime)
RUN mkdir -p plugins

EXPOSE 8000

CMD ["uvicorn", "ogi.main:app", "--host", "0.0.0.0", "--port", "8000"]
