# OGI — OpenGraph Intel

An open source visual link analysis and OSINT framework. An alternative to Maltego.

## Architecture

- **Backend**: Python / FastAPI — graph engine, transform execution, REST API
- **Frontend**: React + TypeScript + Sigma.js — interactive graph visualization
- **Desktop**: Tauri (planned)

## Quick Start

### Backend

```bash
cd backend
python -m venv .venv
source .venv/bin/activate  # or .venv\Scripts\activate on Windows
pip install -e ".[dev]"
uvicorn ogi.main:app --reload
```

### Frontend

```bash
cd frontend
pnpm install
pnpm dev
```

## License

AGPLv3
