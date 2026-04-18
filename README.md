# AI Study Assistant

FastAPI + vanilla JavaScript app for generating study notes, flashcards,
quizzes, and study plans from a topic plus optional uploaded notes, PDFs, or
slides.

The backend serves both the API and the static frontend. There is no separate
Node or frontend build step.

## Requirements

- Python 3.11 or newer
- Groq API key for AI generation
- Tavily API key for web research

## Start The App

### Windows PowerShell

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

Create a `.env` file in the project root:

```env
GROQ_API_KEY=your-groq-key-here
TAVILY_API_KEY=your-tavily-key-here
```

Start the server:

```powershell
python main.py
```

Open:

```text
http://127.0.0.1:8000
```

### macOS Or Linux

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

Create a `.env` file in the project root:

```env
GROQ_API_KEY=your-groq-key-here
TAVILY_API_KEY=your-tavily-key-here
```

Start the server:

```bash
python main.py
```

Open:

```text
http://127.0.0.1:8000
```

## First Login

When the app opens, create an account with any email and a password of at least
6 characters. Accounts and study sessions are stored locally in `app.db`, so
each teammate has their own local data.

## Health Check

To confirm the backend is running:

```text
http://127.0.0.1:8000/api/health
```

Expected response:

```json
{"status":"ok","database":"ok"}
```

## Environment Variables

Required for the full app:

```env
GROQ_API_KEY=your-groq-key-here
TAVILY_API_KEY=your-tavily-key-here
```

Optional:

```env
GROQ_MODEL=llama-3.3-70b-versatile
JWT_SECRET=use-a-long-random-secret-for-shared-dev
HOST=127.0.0.1
PORT=8000
RELOAD=true
CORS_ORIGINS=http://localhost:3000,http://127.0.0.1:8000
```

If `JWT_SECRET` is not set, the app creates a local `.jwt_secret` file
automatically.

## Run Tests

Install the development dependencies:

```bash
python -m pip install -r requirements-dev.txt
```

Run the test suite:

```bash
python -m pytest
```

The tests use a temporary SQLite database and stubbed AI/search agents, so they
do not use real Groq or Tavily credits.

## Files Created Locally

These are generated while running the app and should not be committed:

- `.env` - local API keys
- `.jwt_secret` - local JWT signing key
- `app.db` - SQLite database
- `app.db-*` - SQLite WAL/journal files
- `uploads/` - uploaded files
- `.venv/` - local Python environment

## Project Layout

```text
main.py              FastAPI app and startup configuration
frontend/            Static HTML, CSS, and JavaScript
routers/             API routes for auth, study, upload, quiz, and plan
services/            Database, auth, sessions, file parsing, and API clients
agents/              AI/search backed study agents
models/              Pydantic request schemas
tests/               Pytest endpoint tests
requirements.txt     Runtime dependencies
requirements-dev.txt Test/development dependencies
```

## Troubleshooting

### PowerShell Will Not Activate The Virtual Environment

Run this once in PowerShell:

```powershell
Set-ExecutionPolicy -Scope CurrentUser RemoteSigned
```

Then try again:

```powershell
.\.venv\Scripts\Activate.ps1
```

### Port 8000 Is Already In Use

Start on a different port:

```powershell
$env:PORT="8001"
python main.py
```

On macOS/Linux:

```bash
PORT=8001 python main.py
```

Then open:

```text
http://127.0.0.1:8001
```

### Missing API Key Errors

Check that `.env` exists in the project root and contains:

```env
GROQ_API_KEY=...
TAVILY_API_KEY=...
```

Restart the server after editing `.env`.

### Frontend Looks Stale

Hard refresh the browser:

- Windows/Linux: `Ctrl + Shift + R`
- macOS: `Cmd + Shift + R`
