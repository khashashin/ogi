import os

# The app lifespan connects to Redis when it can; no test needs one (CI has none).
# Since rq 3, `import rq` also succeeds on Windows, so the lifespan reaches its
# ping there, and Windows takes ~4s to refuse a connection to a closed localhost
# port. Keep the default URL but fail the connect quickly when nothing listens.
os.environ.setdefault("OGI_REDIS_URL", "redis://localhost:6379/0?socket_connect_timeout=0.05")
