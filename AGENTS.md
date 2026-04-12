# Arabic Reading Evaluation App - Agent Documentation

## Project Overview

This is a **FastAPI-based web application** for evaluating Arabic reading skills using AI. The application provides a complete workflow for:

1. **Generating Arabic text** using the Nuha-2.0 LLM model
2. **Recording user reading** via browser microphone
3. **Evaluating pronunciation** using Elm-ASR for transcription and comparison
4. **Playing correct pronunciation** using Elm-TTS text-to-speech

The app is designed as a **Single Page Application (SPA)** with an RTL (Right-to-Left) Arabic interface.

### Key Features
- Three-step wizard: Text Generation → Recording → Evaluation
- Real-time audio recording using Web Audio API
- AI-powered text comparison and scoring
- Text-to-speech for correct pronunciation reference
- Mobile-responsive design

---

## Technology Stack

| Layer | Technology | Purpose |
|-------|------------|---------|
| Backend | Python 3.x + FastAPI | REST API server |
| AI Client | OpenAI-compatible client | Integration with Elmodels API |
| AI Models | Nuha-2.0, Elm-TTS, Elm-ASR | Arabic LLM, TTS, and ASR |
| Frontend | Vanilla JavaScript (ES6+) | SPA logic and UI interactions |
| Styling | CSS3 with CSS Variables | RTL-responsive design |
| Templating | Jinja2 | HTML template rendering |

### External Dependencies
- **Elmodels API** (`https://elmodels.ngrok.app/v1`): Provides access to AI models
- **Browser MediaRecorder API**: For client-side audio recording

---

## Project Structure

```
/
├── main.py              # FastAPI application entry point
├── ai_client.py         # AI model client wrapper
├── requirements.txt     # Python dependencies
├── .env                 # Environment variables (API keys)
├── .gitignore          # Git ignore rules
├── AGENTS.md           # This file
│
├── templates/          # Jinja2 HTML templates
│   └── index.html      # Main SPA template (Arabic RTL)
│
├── static/             # Static assets
│   ├── css/
│   │   └── style.css   # Main stylesheet (RTL design)
│   └── js/
│       └── app.js      # Frontend JavaScript logic
│
└── speeches/           # Generated audio files (TTS output)
    └── .gitkeep        # Keep directory in git
```

---

## Code Organization

### Backend (`main.py`)

The FastAPI application provides these endpoints:

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/` | GET | Serve the main HTML page |
| `/api/generate-text` | POST | Generate Arabic text using Nuha LLM |
| `/api/transcribe` | POST | Transcribe audio using Elm-ASR |
| `/api/generate-speech` | POST | Generate TTS audio using Elm-TTS |
| `/api/health` | GET | Health check endpoint |
| `/static/*` | GET | Static files (CSS, JS) |
| `/speeches/*` | GET | Generated audio files |

**Input Validation:**
- `difficulty`: `"beginner"`, `"intermediate"`, or `"advanced"`
- `length`: `"short"`, `"medium"`, or `"long"`

### AI Client (`ai_client.py`)

Wrapper module for Elmodels API with three main functions:

```python
ask_nuha(difficulty: str, length: str) -> str
    # Generate Arabic text using Nuha-2.0 LLM

generate_speech_file(text: str, output_path: str) -> str
    # Generate TTS audio using Elm-TTS

transcribe_audio(audio_file_path: str) -> str
    # Transcribe audio to text using Elm-ASR
```

### Frontend (`static/js/app.js`)

Single Page Application with three views:

1. **View 1 - Text Generator** (`#view-1`)
   - Form to select difficulty and length
   - Calls `/api/generate-text`
   - Displays generated text

2. **View 2 - Reading Recorder** (`#view-2`)
   - Displays the text to read
   - Records audio using MediaRecorder API
   - Submits audio for transcription

3. **View 3 - Evaluation** (`#view-3`)
   - Shows similarity score (0-100%)
   - Compares original vs transcribed text
   - Lists specific mistakes
   - Plays TTS for correct pronunciation

**Global State (`appState`):**
```javascript
{
    currentView: 1,
    generatedText: '',
    transcribedText: '',
    audioBlob: null,
    audioUrl: null,
    ttsAudioUrl: null
}
```

---

## Environment Setup

### Prerequisites
- Python 3.8+
- pip

### Installation

```bash
# Create virtual environment
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Set up environment variables
cp .env.example .env  # Edit .env with your API key
```

### Environment Variables

Create a `.env` file with:

```bash
API_KEY=your_elmodels_api_key_here
```

> **Security Note:** Never commit the `.env` file. It contains sensitive API credentials.

---

## Running the Application

### Development Mode

```bash
# Using the built-in main.py entry point
python main.py

# Or using uvicorn directly
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

The application will be available at `http://localhost:8000`

### Production Deployment

```bash
# Using gunicorn with uvicorn workers
gunicorn main:app -w 2 -k uvicorn.workers.UvicornWorker --bind 0.0.0.0:8000
```

---

## API Documentation

When the server is running, visit:
- Swagger UI: `http://localhost:8000/docs`
- ReDoc: `http://localhost:8000/redoc`

---

## Code Style Guidelines

### Python

- Follow **PEP 8** style guide
- Use **type hints** for function parameters and return types
- Write **comprehensive docstrings** following Google style:

```python
def function_name(param: str) -> str:
    """
    Brief description of what the function does.
    
    Args:
        param: Description of the parameter
    
    Returns:
        Description of the return value
    
    Raises:
        ExceptionType: When this exception is raised
    """
```

- Use **section comments** with `===` for code organization:
```python
# =============================================================================
# SECTION NAME
# =============================================================================
```

- Error messages should be in **Arabic** for frontend display

### JavaScript

- Use **ES6+ features** (const/let, arrow functions, async/await)
- Write **JSDoc comments** for functions:

```javascript
/**
 * Brief description
 * @param {string} param - Parameter description
 * @returns {number} Return description
 */
function example(param) {
    // Implementation
}
```

- Use **strict equality** (`===` and `!==`)
- Organize code into logical sections with clear comments

### CSS

- Use **CSS variables** (custom properties) for colors and spacing
- Design for **RTL layouts** (`direction: rtl`)
- Use **BEM-like naming** for classes (`.component-element`)
- Include **mobile-first responsive breakpoints**

---

## Testing Strategy

Currently, the project does not have automated tests. When adding tests:

### Recommended Test Structure

```
tests/
├── test_main.py        # API endpoint tests
├── test_ai_client.py   # AI client unit tests
└── conftest.py         # pytest fixtures
```

### Manual Testing Checklist

1. **Text Generation**
   - Test all difficulty levels (beginner, intermediate, advanced)
   - Test all length options (short, medium, long)
   - Verify Arabic text is generated correctly

2. **Audio Recording**
   - Test microphone permission handling
   - Verify recording starts/stops correctly
   - Check audio playback in preview

3. **Evaluation**
   - Test text comparison accuracy
   - Verify score calculation (0-100%)
   - Test TTS audio generation and playback

4. **UI/UX**
   - Test RTL layout renders correctly
   - Verify mobile responsiveness
   - Test navigation between views

---

## Security Considerations

1. **API Key Protection**
   - API key is stored in `.env` file (not committed to git)
   - In production, use environment variables or secret management

2. **File Uploads**
   - Temporary audio files are stored in `speeches/` directory
   - Files are cleaned up after transcription
   - Generated MP3 files persist for TTS playback

3. **CORS**
   - Currently using default FastAPI CORS settings
   - For production, configure specific allowed origins

4. **Input Validation**
   - All API endpoints validate input parameters
   - File uploads are validated for audio MIME types

---

## Deployment Notes

### Required Environment
- Python 3.8+
- At least 512MB RAM (for AI API calls)
- Network access to `elmodels.ngrok.app`

### File Permissions
- Ensure `speeches/` directory is writable
- Generated audio files are served statically

### Scaling Considerations
- Application is stateless (except for generated audio files)
- Can be scaled horizontally with load balancer
- Consider using cloud storage (S3, etc.) for audio files in production

---

## Common Issues and Solutions

### Issue: Microphone not working
**Solution:** Ensure browser has microphone permissions. The app uses `getUserMedia()` which requires HTTPS in production.

### Issue: AI API errors
**Solution:** Check the `API_KEY` in `.env` file. Verify network connectivity to Elmodels API.

### Issue: Generated audio not playing
**Solution:** Check that the `speeches/` directory exists and is writable. Verify the audio file was generated successfully.

---

## Development Workflow

1. **Start the server:** `python main.py`
2. **Make changes** to code
3. **Test in browser:** `http://localhost:8000`
4. **Check logs** in terminal for errors
5. **Refresh browser** to see changes (auto-reload is enabled)

---

## Additional Resources

- **FastAPI Documentation:** https://fastapi.tiangolo.com/
- **Elmodels API:** Documentation available at the API base URL
- **MediaRecorder API:** https://developer.mozilla.org/en-US/docs/Web/API/MediaRecorder

---

## Contact and Support

For issues related to:
- **Application code:** Check FastAPI logs
- **AI models:** Contact Elmodels support
- **Frontend:** Check browser console for JavaScript errors

---

*Last updated: 2026-04-12*
