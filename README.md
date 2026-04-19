# AI Study Assistant

A gamified study companion that turns any topic (plus optional notes, PDFs, or
slides) into AI-generated study notes, flashcards, quizzes, and a personalized
study plan — with a shop, a growable plant pet, tiered skins, and optional
Spotify playback while you study.

The backend serves both the API and the static frontend. There is no separate
Node or frontend build step.

## What's Included

- Account-based study sessions backed by local SQLite.
- Web research with Tavily plus optional uploaded study material.
- Groq-powered notes, flashcards, quizzes, and study plans.
- Quiz weak-area tracking that feeds the study-plan generator.
- Coin economy, upgrade shop, plant XP/health, claimable plant tiers, and
  profile stats.
- Optional Spotify OAuth, device selection, playlist/track search, playback
  transfer, and current playback display.
- Request validation, upload caps, file-type checks, token encryption, and
  configurable API rate limits.
- Pytest coverage for auth, uploads, sessions, quizzes, shop behavior, and
  Spotify flows.

## Features

**Study pipeline**
- Choose web research, uploaded files, or both as the source for generated
  notes.
- AI research/content agents build notes with a summary, key concepts,
  sectioned content, and visual-learning image descriptions from a topic plus
  uploaded files (`.pdf`, `.pptx`, `.txt`, `.md`).
- Drag-and-drop upload flow with extension allow-listing, PDF/PPTX magic-byte
  checks, configurable upload size limits, and extracted-text truncation.
- Generates 1–30 flashcards and 1–20 multiple-choice quiz questions per
  session, at beginner, intermediate, or advanced difficulty.
- Personalized 1–30 day study plan with priority tagging and extra time for
  weak areas found in the latest quiz attempt.
- Session history sidebar — reload or delete any past session.
- Local settings modal for dark mode, compact mode, toast notifications,
  sound preference, and default flashcard/quiz/plan values.

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
- Profile dashboard with study time, coin totals, quiz count, average quiz
  score, recent quiz history, plant XP/health, tier descriptions, and skin
  claiming/equipping.
- Hidden local demo/admin unlock control in the profile plant section that
  unlocks all plant rewards and grants demo coins. This is convenient for
  judging/demo runs and should be removed or protected before production use.

**Integrations**
- Optional Spotify Connect: OAuth login, status, disconnect, token refresh,
  encrypted access/refresh token storage, device discovery, device transfer,
  track/playlist search, user's playlists, current playback display, and
  play/pause/next/previous controls.
- In-browser playback support through the Spotify Web Playback SDK and Spotify
  Web API. Playback control generally requires Spotify Premium and an active
  device.

**Accounts**
- Email + password auth, JWT sessions, local SQLite storage. Each teammate
  has their own isolated data in `app.db`.
- Auth, AI, upload, and Spotify endpoints use configurable SlowAPI rate limits.

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
- [SlowAPI](https://slowapi.readthedocs.io/) — request rate limiting
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
- Static assets under `Sprites/` for plant stages and tier skins
- LocalStorage-backed UI settings and current session pointer

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
APP_NAME=AI Student Agent
GROQ_MODEL=llama-3.3-70b-versatile
JWT_SECRET=use-a-long-random-secret-for-shared-dev
HOST=127.0.0.1
PORT=8000
RELOAD=true
CORS_ORIGINS=http://localhost:3000,http://127.0.0.1:8000
CORS_METHODS=GET,POST,PUT,DELETE,OPTIONS
CORS_HEADERS=Authorization,Content-Type,Accept,X-Requested-With
CORS_ALLOW_CREDENTIALS=false
LOG_LEVEL=INFO
FRONTEND_DIR=frontend
MAX_SEARCH_RESULTS=6
MAX_NOTES_CHARS=8000
MAX_UPLOAD_BYTES=10485760
MAX_FILE_TEXT_CHARS=12000
RATE_LIMIT_DEFAULT=120/minute
RATE_LIMIT_AUTH=5/minute
RATE_LIMIT_UPLOAD=10/minute
RATE_LIMIT_AI=10/minute
RATE_LIMIT_SPOTIFY=60/minute
```

If `JWT_SECRET` is not set, the app creates a local `.jwt_secret` file
automatically.

### Upload Limits

Uploads accept `.pdf`, `.pptx`, `.txt`, and `.md`. PDF and PPTX uploads are
checked against their expected file signatures before parsing. `MAX_UPLOAD_BYTES`
defaults to 10 MB per file and `MAX_FILE_TEXT_CHARS` defaults to 12,000
extracted characters per file.

### Rate Limits

SlowAPI is configured globally with `RATE_LIMIT_DEFAULT` and per-route groups:

- `RATE_LIMIT_AUTH` for signup/login.
- `RATE_LIMIT_UPLOAD` for file uploads.
- `RATE_LIMIT_AI` for research and learning generation.
- `RATE_LIMIT_SPOTIFY` for Spotify connect/search/playback endpoints.

Limits are keyed by bearer token when present, otherwise by client IP.

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
SPOTIFY_SCOPES=user-read-private user-read-email user-read-playback-state user-read-currently-playing user-modify-playback-state playlist-read-private playlist-read-collaborative streaming
SPOTIFY_COOKIE_SECURE=false
SPOTIFY_TOKEN_KEY_FILE=.spotify_token_key
```

Generate the Fernet key with:

```powershell
py -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

Restart the server after editing `.env`. Users can then click **Connect
Spotify** in the header. Playback control usually requires Spotify Premium and
an active device. Keep `SPOTIFY_TOKEN_ENCRYPTION_KEY` stable across restarts —
changing it means existing connections cannot be decrypted and users must
reconnect. If omitted, the app creates a local `.spotify_token_key` file
(dev only).

## API Surface

Routers are mounted under `/api`:

| Prefix         | Purpose                                                    |
| -------------- | ---------------------------------------------------------- |
| `/api/auth`    | signup, login, `me`                                        |
| `/api/study`   | start research, generate flashcards + quiz, session CRUD   |
| `/api/upload`  | upload PDFs / PPTX / TXT / MD into a study session         |
| `/api/quiz`    | submit quiz, record history, heal/damage plant             |
| `/api/plan`    | generate personalized study plan from notes + weak areas   |
| `/api/shop`    | coins, upgrade state/purchase, study ticks                 |
| `/api/profile` | stats, quiz history, plant tier claims, local admin unlock |
| `/api/plant`   | `POST /heal-flashcard` — heal from flashcard review        |
| `/api/spotify` | OAuth, search, playlists, devices, playback, now playing   |
| `/api/health`  | health check                                               |

Auto-generated OpenAPI docs: `http://127.0.0.1:8000/docs`.

### Key Endpoints

| Method | Path                           | Notes                                      |
| ------ | ------------------------------ | ------------------------------------------ |
| `POST` | `/api/auth/signup`             | Create user and return JWT session         |
| `POST` | `/api/auth/login`              | Return JWT session                         |
| `GET`  | `/api/auth/me`                 | Current user                               |
| `POST` | `/api/upload`                  | Multipart file upload with optional session |
| `POST` | `/api/study/start`             | Generate notes from `web`, `files`, or `both` |
| `POST` | `/api/study/generate-learning` | Generate flashcards and quiz               |
| `GET`  | `/api/study/sessions`          | List current user's sessions               |
| `GET`  | `/api/study/session/{id}`      | Load a full session payload                |
| `DELETE` | `/api/study/session/{id}`    | Delete a session                           |
| `POST` | `/api/quiz/submit`             | Score quiz, record weak topics, update plant |
| `POST` | `/api/plan/generate`           | Build day-by-day study plan                |
| `GET`  | `/api/shop/state`              | Coins, upgrades, study time, plant state   |
| `POST` | `/api/shop/study-tick`         | Award timed study progress                 |
| `POST` | `/api/shop/purchase`           | Buy an upgrade                             |
| `GET`  | `/api/profile/`                | Stats, quiz history, plant tiers           |
| `POST` | `/api/profile/claim`           | Claim/equip a plant tier skin              |
| `POST` | `/api/profile/admin-unlock`    | Local demo unlock endpoint                 |
| `POST` | `/api/plant/heal-flashcard`    | Heal plant after reviewing a flashcard     |
| `GET`  | `/api/spotify/status`          | Spotify config/connection status           |
| `POST` | `/api/spotify/connect`         | Start Spotify OAuth                        |
| `POST` | `/api/spotify/disconnect`      | Remove Spotify connection                  |
| `GET`  | `/api/spotify/token`           | Access token for Web Playback SDK          |
| `GET`  | `/api/spotify/devices`         | Available playback devices                 |
| `GET`  | `/api/spotify/search`          | Track and playlist search                  |
| `GET`  | `/api/spotify/playlists`       | Current user's playlists                   |
| `GET`  | `/api/spotify/current`         | Current playback summary                   |
| `PUT`  | `/api/spotify/transfer`        | Transfer playback to a device              |
| `PUT`  | `/api/spotify/play`            | Play/resume track or context               |
| `PUT`  | `/api/spotify/pause`           | Pause playback                             |
| `POST` | `/api/spotify/next`            | Next track                                 |
| `POST` | `/api/spotify/previous`        | Previous track                             |

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
  rate_limit.py        SlowAPI limiter configuration
  exceptions.py        shared error types
agents/                AI/search-backed study agents
  research_agent.py    Tavily search
  content_agent.py     structured notes
  learning_agent.py    flashcards + quiz questions
  planning_agent.py    personalized study plan
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
