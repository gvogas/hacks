# AI Study Assistant

A gamified study companion that turns any topic (plus optional notes, PDFs, or
slides) into AI-generated study notes, flashcards, quizzes, and a personalized
study plan — with a shop, a growable plant pet, tiered skins, and optional
Spotify playback while you study.

The backend serves both the API and the static frontend. There is no separate
Node or frontend build step.

## Features

**Study pipeline**
- AI research agent builds notes with summary, key concepts, and sectioned
  content from a topic plus uploaded files (`.pdf`, `.pptx`, `.txt`, `.md`).
- Generates 1–30 flashcards and 1–20 multiple-choice quiz questions per
  session, at your chosen difficulty.
- Personalized multi-day study plan with priority tagging on weak areas.
- Session history sidebar — reload, rename, or delete any past session.

**Gamification**
- Earn coins while studying (per-minute ticks) plus quiz, flashcard, and plan
  bonuses.
- Shop with four upgrade tracks: Focus Engine (coin rate), Card Foundry,
  Quiz Magnet, and Plan Compass.
- Plant pet that grows in XP as you study and takes damage from wrong answers.
  If it dies you lose coins and have to revive it by studying.
- **Plant health heals when you review a flashcard or answer a quiz question
  correctly** (+2 per unique card, +5 per correct answer).
- **Seven tier skins with distinct plant sprites**: Bad, Average, Good,
  Excellent, Amazing, Phenomenal, Legendary — each tier unlocks a different
  plant look and grants a one-time coin reward when claimed.

**Integrations**
- Optional Spotify Connect: search tracks/playlists, transfer playback between
  devices, control play/pause/next from the header. In-browser playback via
  the Spotify Web Playback SDK (Premium required).

**Accounts**
- Email + password auth, JWT sessions, local SQLite storage. Each teammate
  has their own isolated data in `app.db`.

## Tech Stack

**Backend**
- Python 3.11+
- [FastAPI](https://fastapi.tiangolo.com/) — API framework
- [Uvicorn](https://www.uvicorn.org/) — ASGI server with auto-reload
- [Pydantic v2](https://docs.pydantic.dev/) — request/response schemas
- SQLite (stdlib `sqlite3`) — local persistence in `app.db`
- [bcrypt](https://pypi.org/project/bcrypt/) — password hashing
- [PyJWT](https://pyjwt.readthedocs.io/) — session tokens
- [cryptography](https://cryptography.io/) (Fernet) — Spotify token encryption
- [python-dotenv](https://pypi.org/project/python-dotenv/) — `.env` loading
- [PyPDF2](https://pypdf2.readthedocs.io/) and
  [python-pptx](https://python-pptx.readthedocs.io/) — file parsing
- [aiofiles](https://pypi.org/project/aiofiles/) — async uploads
- [python-multipart](https://pypi.org/project/python-multipart/) — form uploads
- [email-validator](https://pypi.org/project/email-validator/) — email parsing

**AI / external services**
- [Groq](https://groq.com/) Python SDK — LLM generation (default model
  `llama-3.3-70b-versatile`)
- [Tavily](https://tavily.com/) — web research
- [Spotify Web API](https://developer.spotify.com/documentation/web-api) and
  Web Playback SDK — music playback

**Frontend**
- Vanilla HTML, CSS, and JavaScript — no framework, no build step
- Spotify Web Playback SDK loaded via CDN

**Testing**
- [pytest](https://docs.pytest.org/) + [httpx](https://www.python-httpx.org/)
  `AsyncClient` — async endpoint tests against a temp SQLite DB with stubbed
  AI/search agents.

## Requirements

- Python 3.11 or newer
- [Groq API key](https://console.groq.com/) for AI generation
- [Tavily API key](https://tavily.com/) for web research
- (Optional) Spotify developer app for music integration

## Quick Start

### Windows PowerShell

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

### macOS / Linux

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

## Run The App

```bash
python main.py
```

Then open:

```text
http://127.0.0.1:8000
```

### Auto-Reload In Development

`RELOAD=true` is on by default, so Uvicorn watches Python files and restarts
automatically on save. Static frontend files (`frontend/*.html`, `*.css`,
`*.js`) are served fresh on every request — just hard-refresh the browser:

- Windows/Linux: `Ctrl + Shift + R`
- macOS: `Cmd + Shift + R`

To disable auto-reload (e.g. for profiling or production-style runs):

```bash
RELOAD=false python main.py
```

### First Login

Create an account with any email and a password of at least 6 characters.
Accounts and sessions are stored locally in `app.db`.

### Health Check

```text
http://127.0.0.1:8000/api/health
```

Expected:

```json
{"status":"ok","database":"ok"}
```

## Run Tests

Install the dev dependencies (includes pytest + httpx):

```bash
python -m pip install -r requirements-dev.txt
```

Run the full suite:

```bash
python -m pytest
```

Run a single file or test:

```bash
python -m pytest tests/test_quiz.py
python -m pytest tests/test_quiz.py::test_submit_quiz_heals_plant
```

The tests spin up a temporary SQLite database and stub the AI and search
agents, so they do not consume real Groq or Tavily credits.

## Environment Variables

Required:

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
LOG_LEVEL=INFO
FRONTEND_DIR=frontend
```

If `JWT_SECRET` is not set, the app creates a local `.jwt_secret` file
automatically.

### Spotify (Optional)

Create an app in the Spotify Developer Dashboard and add this redirect URI:

```text
http://127.0.0.1:8000/api/spotify/callback
```

Add these values to `.env`:

```env
SPOTIFY_CLIENT_ID=your-spotify-client-id
SPOTIFY_CLIENT_SECRET=your-spotify-client-secret
SPOTIFY_REDIRECT_URI=http://127.0.0.1:8000/api/spotify/callback
SPOTIFY_TOKEN_ENCRYPTION_KEY=your-fernet-key
```

Generate the Fernet key with:

```powershell
py -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

Restart the server after editing `.env`. Users can then click **Connect
Spotify** in the header. Playback requires Spotify Premium and an active
device. Keep `SPOTIFY_TOKEN_ENCRYPTION_KEY` stable across restarts — changing
it means existing connections cannot be decrypted and users must reconnect.
If omitted, the app creates a local `.spotify_token_key` file (dev only).

## API Surface

Routers are mounted under `/api`:

| Prefix             | Purpose                                            |
| ------------------ | -------------------------------------------------- |
| `/api/auth`        | signup, login, `me`                                |
| `/api/study`       | start research, generate flashcards + quiz, sessions |
| `/api/upload`      | upload PDFs / PPTX / TXT / MD                      |
| `/api/quiz`        | submit quiz (heals plant on correct, damages on wrong) |
| `/api/plan`        | generate personalized study plan                   |
| `/api/shop`        | coins, upgrades, study ticks                       |
| `/api/profile`     | stats, quiz history, plant tier claims             |
| `/api/plant`       | `POST /heal-flashcard` — heal from flashcard view  |
| `/api/spotify`     | connect, search, playback, devices                 |
| `/api/health`      | health check                                       |

Auto-generated OpenAPI docs: `http://127.0.0.1:8000/docs`.

## Project Layout

```text
main.py                FastAPI app, router mounts, static file serving
frontend/              Static HTML, CSS, and JavaScript (no build step)
  index.html
  app.js
  style.css
Sprites/               Plant sprite PNGs (per-tier skins)
routers/               API routes
  auth.py              signup / login / me
  study.py             research + flashcard/quiz generation
  upload.py            file uploads
  quiz.py              quiz submit (with plant heal + wither)
  plan.py              study plan generation
  shop.py              coins, upgrades, study ticks
  profile.py           user stats + plant tier claims
  plant.py             plant heal endpoints (flashcard)
  spotify.py           Spotify OAuth + playback proxy
services/              Business logic
  db.py                SQLite connection + schema
  auth.py              JWT + bcrypt
  session_store.py     study session CRUD
  file_parser.py       PDF / PPTX / text extraction
  groq_client.py       Groq LLM wrapper
  shop.py              coin economy + upgrades
  plant.py             XP, health, tiers, heal logic
  spotify.py           Spotify OAuth + API client
  exceptions.py        shared error types
agents/                AI/search-backed study agents
models/
  schemas.py           Pydantic request/response models
tests/                 Pytest endpoint tests (async, stubbed AI)
requirements.txt       Runtime dependencies
requirements-dev.txt   Test dependencies
```

## Files Created Locally

Generated while running the app — do not commit:

- `.env` — local API keys
- `.jwt_secret` — local JWT signing key
- `.spotify_token_key` — local Spotify Fernet key (when not in `.env`)
- `app.db`, `app.db-shm`, `app.db-wal` — SQLite database + WAL files
- `uploads/` — uploaded files
- `.venv/` — local Python environment
- `__pycache__/` — Python bytecode caches

## Troubleshooting

### PowerShell Will Not Activate The Virtual Environment

Run once:

```powershell
Set-ExecutionPolicy -Scope CurrentUser RemoteSigned
```

Then:

```powershell
.\.venv\Scripts\Activate.ps1
```

### Port 8000 Is Already In Use

```powershell
$env:PORT="8001"
python main.py
```

On macOS/Linux:

```bash
PORT=8001 python main.py
```

Open `http://127.0.0.1:8001`.

### Missing API Key Errors

Make sure `.env` exists in the project root with `GROQ_API_KEY` and
`TAVILY_API_KEY` set, then restart the server.

### Frontend Looks Stale

Hard-refresh the browser:

- Windows/Linux: `Ctrl + Shift + R`
- macOS: `Cmd + Shift + R`

### Spotify "No Devices Found"

Open Spotify on desktop or mobile first, then click **Refresh devices** in the
Spotify tab. Users who connected before playlist scopes were added should
disconnect and reconnect Spotify.
