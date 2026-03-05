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

# Copy package metadata and source before install so CLI entry points resolve modules.
COPY pyproject.toml ./
RUN printf "# OGI backend image\n" > README.md
COPY ogi/ ogi/

# Install project + dependencies into the venv
RUN uv pip install -e ".[web_extract]"

# Install Playwright browser binaries and required system packages
RUN playwright install --with-deps chromium

# Copy non-package runtime files
COPY alembic/ alembic/
COPY alembic.ini .
COPY entrypoint.sh /app/entrypoint.sh
RUN chmod +x /app/entrypoint.sh

# Default plugins directory (populated via volume mount at runtime)
RUN mkdir -p plugins

EXPOSE 8000

ENTRYPOINT ["/app/entrypoint.sh"]
CMD ["uvicorn", "ogi.main:app", "--host", "0.0.0.0", "--port", "8000"]
