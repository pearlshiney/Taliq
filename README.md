# طَلِقْ (Taliq) — Arabic Reading Evaluation

A FastAPI-based web application for evaluating Arabic reading skills using AI. The app generates Arabic text with tashkeel (diacritics), records students reading aloud, transcribes their speech, and evaluates pronunciation accuracy with a visual word-level diff.

---

## Features

- **AI-Powered Text Generation** — Generates Arabic paragraphs at three difficulty levels using the Nuha-2.0 LLM
- **Browser Audio Recording** — Students record their reading directly in the browser via the Web Audio API
- **Speech-to-Text** — Transcribes recordings using Elm-ASR and strips tashkeel for fair comparison
- **Word-Level Diff Evaluation** — Colour-coded comparison: green (correct), grey strikethrough (missing), red wavy underline (extra)
- **Text-to-Speech Reference** — Plays correct pronunciation using Elm-TTS
- **Student Management** — Register students with IDs, assign pre-generated reading texts per student
- **Admin Control Panel** — Configure scoring thresholds, manage students and assignments
- **Management Dashboard** — School-wide KPIs, grade distributions, and evaluation history
- **Persistent Storage** — SQLite database with permanent audio file storage

---

## Tech Stack

| Layer | Technology |
|-------|------------|
| Backend | Python 3.10+ + FastAPI |
| AI Client | OpenAI-compatible client (Elmodels API) |
| AI Models | Nuha-2.0 (LLM), Elm-TTS, Elm-ASR |
| Frontend | Vanilla JavaScript (ES6+) SPA |
| Styling | CSS3 with RTL Arabic support |
| Database | SQLite (embedded) |
| Server | Uvicorn |

---

## Prerequisites

- **Python 3.10** or higher
- **pip** package manager
- An **API key** for the [Elmodels API](https://elmodels.ngrok.app) (required for AI features)
- A modern web browser with microphone support (Chrome, Firefox, Edge)

---

## Installation

### 1. Clone the repository

```bash
git clone <repository-url>
cd Hakathon
```

### 2. Create a virtual environment

```bash
# Linux / macOS
python3 -m venv venv
source venv/bin/activate

# Windows
python -m venv venv
venv\Scripts\activate
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

### 4. Set up environment variables

Create a `.env` file in the project root:

```bash
cp .env.example .env   # if an example exists, or create manually
```

Edit `.env` and add your Elmodels API key:

```env
API_KEY=your_elmodels_api_key_here
```

> **Security:** Never commit the `.env` file. It is already listed in `.gitignore`.

### 5. Create required directories

The app will auto-create these on startup, but you can ensure they exist:

```bash
mkdir -p recordings speeches
```

---

## Running Locally

### Development mode (with auto-reload)

```bash
# Make sure your virtual environment is activated
source venv/bin/activate

# Option A: using the built-in entry point
python main.py

# Option B: using uvicorn directly
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

The application will be available at: **`http://localhost:8000`**

### Production mode

```bash
# Using gunicorn with uvicorn workers
gunicorn main:app -w 2 -k uvicorn.workers.UvicornWorker --bind 0.0.0.0:8000
```

### API Documentation

Once the server is running, interactive API docs are available at:

- **Swagger UI:** http://localhost:8000/docs
- **ReDoc:** http://localhost:8000/redoc

---

## Project Structure

```
Hakathon/
├── main.py                  # FastAPI application entry point
├── ai_client.py             # AI model client wrapper (Elmodels API)
├── requirements.txt         # Python dependencies
├── .env                     # Environment variables (API key) — not committed
├── .gitignore              # Git ignore rules
├── AGENTS.md               # Detailed agent/developer documentation
├── README.md               # This file
│
├── templates/              # Jinja2 HTML templates
│   ├── index.html          # Main student app (reading & evaluation)
│   ├── control_panel.html  # Admin control panel
│   └── dashboard.html      # Management dashboard
│
├── static/                 # Static assets
│   ├── css/style.css       # RTL Arabic stylesheet
│   └── js/app.js           # Frontend SPA logic
│
├── recordings/             # Permanent student audio recordings
├── speeches/               # Generated TTS audio files
└── evaluations.db          # SQLite database (auto-created)
```

---

## Application Views

### 1. Student App (`/`)
The main reading evaluation flow:
1. Select your name from the dropdown
2. Read the displayed Arabic text aloud
3. Review the AI evaluation with colour-coded diff and score

### 2. Control Panel (`/control-panel`)
Admin tools for:
- **Student Management** — Add, edit, delete students
- **Assignment Generation** — Create pre-generated reading texts per student
- **Settings** — Customise scoring thresholds (pace ratios, grade boundaries, weights)

### 3. Dashboard (`/dashboard`)
Management overview with:
- KPI cards (total students, evaluations, mean score)
- Difficulty & length breakdowns
- Grade & pace distribution charts
- Clickable evaluation history with detail modal

---

## Key API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/` | GET | Main student app |
| `/control-panel` | GET | Admin control panel |
| `/dashboard` | GET | Management dashboard |
| `/api/students` | GET / POST | List / create students |
| `/api/assignments` | GET / POST | List / create assignments |
| `/api/student-assignments/{id}` | GET | Get current assignment for a student |
| `/api/transcribe` | POST | Upload audio → transcription |
| `/api/evaluate` | POST | Run evaluation on a recording |
| `/api/generate-speech` | POST | Generate TTS audio |
| `/api/generate-text` | POST | Generate Arabic text via LLM |
| `/api/settings` | GET / POST | Read / update admin settings |
| `/api/dashboard-stats` | GET | School-wide aggregated statistics |
| `/api/health` | GET | Health check |

---

## How Evaluation Works

1. **Text Generation** — Nuha-2.0 generates Arabic text **with tashkeel**
2. **Tashkeel Removal** — The LLM strips diacritics once at assignment creation; both versions are stored
3. **Student Recording** — Browser captures audio via `MediaRecorder`
4. **Transcription** — Elm-ASR converts speech to text, then tashkeel is removed
5. **Comparison** — Clean original vs. clean transcribed text are compared word-for-word
6. **Display** — The diff is rendered using the **raw original text** (with tashkeel intact) so students see proper Arabic

---

## Troubleshooting

| Issue | Solution |
|-------|----------|
| **Port 8000 already in use** | Kill the existing process: `lsof -ti:8000 \| xargs kill -9` then restart |
| **Microphone not working** | Ensure the browser has microphone permissions. HTTPS is required in production |
| **AI API errors** | Check your `API_KEY` in `.env`. Verify network connectivity to `elmodels.ngrok.app` |
| **Generated audio not playing** | Ensure `speeches/` directory exists and is writable |
| **Missing dependencies** | Run `pip install -r requirements.txt` again |
| **Database errors** | Delete `evaluations.db` to reset (⚠️ loses all data). It will be recreated on next startup |

---

## Development Notes

- The app is designed as a **Single Page Application (SPA)** with an RTL Arabic interface
- All error messages displayed to users are in **Arabic**
- The SQLite database is embedded and requires no external setup
- Audio recordings are stored permanently in `recordings/` (not cleaned up automatically)
- The app is stateless aside from the database and audio files

---

## License

This project was built for the Hakathon. See repository for license details.
