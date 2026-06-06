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

# Copy package metadata first so dependency/browser layers survive normal source edits.
COPY pyproject.toml ./
RUN printf "# OGI backend image\n" > README.md

# Install browsers into a shared location (not root's home) so a non-root
# runtime user can find them. Must be set before `playwright install`.
ENV PLAYWRIGHT_BROWSERS_PATH=/opt/playwright

# Install Playwright package first so browser binaries can be cached separately
# from application source changes.
RUN uv pip install "playwright>=1.58.0"

# Install Playwright browser binaries and required system packages
RUN playwright install --with-deps chromium

# Copy package source and then install the full project + extras.
COPY ogi/ ogi/
RUN uv pip install -e ".[web_extract]"

# Copy non-package runtime files
COPY alembic/ alembic/
COPY alembic.ini .
COPY entrypoint.sh /app/entrypoint.sh
RUN chmod +x /app/entrypoint.sh

# Default runtime directories (populated via volume mount at runtime)
RUN mkdir -p plugins media

# Run as an unprivileged user. Chromium's sandbox is disabled under root, and a
# plugin/dependency RCE here would otherwise have host-root blast radius, so the
# worker/agent-worker (which run third-party plugin code and headless Chromium)
# drop to this account too. HOME is set explicitly so uv's boot-time plugin
# install has a writable cache; /opt/venv and /opt/playwright are chowned so the
# venv and browser binaries remain usable after the switch.
ENV HOME=/home/ogi
RUN groupadd -r ogi && useradd -r -g ogi -d /home/ogi -m ogi \
    && chown -R ogi:ogi /app /opt/venv /opt/playwright /home/ogi
USER ogi

EXPOSE 8000

ENTRYPOINT ["/app/entrypoint.sh"]
CMD ["uvicorn", "ogi.main:app", "--host", "0.0.0.0", "--port", "8000"]
