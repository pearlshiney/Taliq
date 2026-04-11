"""
main.py - FastAPI Backend for Arabic Reading Evaluation App

This is the main entry point for the web application. It provides:
- REST API endpoints for AI operations
- Static file serving (CSS, JS, audio files)
- HTML template rendering

API Endpoints:
- POST /api/generate-text    : Generate Arabic text using Nuha LLM
- POST /api/transcribe       : Transcribe audio using Elm-ASR
- POST /api/generate-speech  : Generate TTS audio using Elm-TTS


"""

import os
import uuid
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, File, Form, Request, UploadFile
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

# Import our AI client module
from ai_client import (
    ask_nuha,
    ensure_speeches_folder,
    generate_speech_file,
    transcribe_audio,
)

# =============================================================================
# FASTAPI APP INITIALIZATION
# =============================================================================

# Create the FastAPI application instance
app = FastAPI(
    title="Arabic Reading Evaluation",
    description="Web application for evaluating Arabic reading skills using AI",
    version="1.0.0"
)

# Get absolute paths for file serving
BASE_DIR = Path(__file__).parent.resolve()
SPEECHES_DIR = BASE_DIR / "speeches"

# Ensure speeches folder exists on startup
# This is where generated TTS audio files will be stored
ensure_speeches_folder(str(SPEECHES_DIR))

# Mount static files directories
# /static serves CSS and JS files
app.mount("/static", StaticFiles(directory=str(BASE_DIR / "static")), name="static")

# /speeches serves generated audio files
app.mount("/speeches", StaticFiles(directory=str(SPEECHES_DIR)), name="speeches")

# Setup Jinja2 templates for HTML rendering
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))


# =============================================================================
# HTML PAGE ROUTES
# =============================================================================

@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    """
    Serve the main HTML page (Single Page Application).
    
    This is the entry point for users. It returns the HTML template
    which contains all three views (Generator, Recorder, Evaluation)
    controlled by JavaScript.
    
    Args:
        request: FastAPI request object
    
    Returns:
        HTMLResponse: The rendered index.html template
    """
    return templates.TemplateResponse(request, "index.html")


# =============================================================================
# API ENDPOINTS
# =============================================================================

@app.post("/api/generate-text")
async def api_generate_text(
    difficulty: str = Form(...),
    length: str = Form(...)
):
    """
    API endpoint to generate Arabic text using Nuha LLM.
    
    This endpoint receives difficulty and length parameters, calls the
    Nuha-2.0 model, and returns the generated Arabic text.
    
    Args:
        difficulty (str): "beginner", "intermediate", or "advanced"
        length (str): "short", "medium", or "long"
    
    Returns:
        JSONResponse: {"text": "..."} on success
        JSONResponse: {"error": "..."} on failure (status 500)
    
    Example Request:
        POST /api/generate-text
        Form Data: difficulty=beginner&length=short
    
    Example Response:
        {"text": "مرحباً، كيف حالك اليوم؟"}
    """
    try:
        # Validate input parameters
        valid_difficulties = ["beginner", "intermediate", "advanced"]
        valid_lengths = ["short", "medium", "long"]
        
        if difficulty not in valid_difficulties:
            return JSONResponse(
                status_code=400,
                content={"error": f"مستوى الصعوبة يجب أن يكون: {', '.join(valid_difficulties)}"}
            )
        
        if length not in valid_lengths:
            return JSONResponse(
                status_code=400,
                content={"error": f"الطول يجب أن يكون: {', '.join(valid_lengths)}"}
            )
        
        # Call the AI client to generate text
        generated_text = ask_nuha(difficulty, length)
        
        return JSONResponse({"text": generated_text})
        
    except Exception as e:
        # Return error message in Arabic for frontend display
        return JSONResponse(
            status_code=500,
            content={"error": f"حدث خطأ أثناء توليد النص: {str(e)}"}
        )


@app.post("/api/transcribe")
async def api_transcribe(audio_file: UploadFile = File(...)):
    """
    API endpoint to transcribe audio to Arabic text using Elm-ASR.
    
    This endpoint receives an audio file, saves it temporarily,
    calls the Elm-ASR model for transcription, and returns the text.
    
    Args:
        audio_file (UploadFile): The uploaded audio file (webm, mp3, wav, etc.)
    
    Returns:
        JSONResponse: {"transcription": "..."} on success
        JSONResponse: {"error": "..."} on failure (status 500)
    
    Example Request:
        POST /api/transcribe
        Content-Type: multipart/form-data
        File: audio_file=<binary audio data>
    
    Example Response:
        {"transcription": "مرحبا كيف حالك"}
    """
    try:
        # Generate a unique filename for the temporary audio file
        file_extension = Path(audio_file.filename).suffix or ".webm"
        temp_filename = f"temp_{uuid.uuid4().hex}{file_extension}"
        temp_filepath = SPEECHES_DIR / temp_filename
        
        # Save the uploaded audio file to disk
        # We need to save it first because the ASR client reads from file path
        with open(temp_filepath, "wb") as f:
            content = await audio_file.read()
            f.write(content)
        
        # Call the AI client to transcribe the audio
        transcribed_text = transcribe_audio(str(temp_filepath))
        
        # Clean up: remove the temporary audio file
        # We don't need to keep user's recordings on the server
        os.remove(temp_filepath)
        
        return JSONResponse({"transcription": transcribed_text})
        
    except Exception as e:
        # Cleanup on error if file exists
        if 'temp_filepath' in locals() and os.path.exists(temp_filepath):
            os.remove(temp_filepath)
        
        return JSONResponse(
            status_code=500,
            content={"error": f"حدث خطأ أثناء تحويل الصوت لنص: {str(e)}"}
        )


@app.post("/api/generate-speech")
async def api_generate_speech(text: str = Form(...)):
    """
    API endpoint to generate TTS audio from Arabic text using Elm-TTS.
    
    This endpoint receives Arabic text, calls the Elm-TTS model to
    generate speech, saves the audio file, and returns the URL.
    
    Args:
        text (str): Arabic text to convert to speech
    
    Returns:
        JSONResponse: {"audio_url": "/speeches/filename.mp3"} on success
        JSONResponse: {"error": "..."} on failure (status 500)
    
    Example Request:
        POST /api/generate-speech
        Form Data: text=مرحباً كيف حالك
    
    Example Response:
        {"audio_url": "/speeches/speech_abc123.mp3"}
    """
    try:
        # Validate input
        if not text or not text.strip():
            return JSONResponse(
                status_code=400,
                content={"error": "النص فارغ، يرجى إدخال نص صالح"}
            )
        
        # Generate a unique filename for the speech file
        filename = f"speech_{uuid.uuid4().hex}.mp3"
        filepath = SPEECHES_DIR / filename
        
        # Call the AI client to generate speech
        generate_speech_file(text, str(filepath))
        
        # Return the URL path to access the audio file
        # The frontend will use this to play the audio
        audio_url = f"/speeches/{filename}"
        
        return JSONResponse({"audio_url": audio_url})
        
    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={"error": f"حدث خطأ أثناء توليد الصوت: {str(e)}"}
        )


# =============================================================================
# HEALTH CHECK ENDPOINT
# =============================================================================

@app.get("/api/health")
async def health_check():
    """
    Simple health check endpoint.
    
    Returns:
        JSONResponse: {"status": "ok"} if server is running
    """
    return JSONResponse({"status": "ok", "service": "Arabic Reading Evaluation"})


# =============================================================================
# ERROR HANDLERS
# =============================================================================

@app.exception_handler(404)
async def not_found_handler(request: Request, exc):
    """Handle 404 errors gracefully."""
    return JSONResponse(
        status_code=404,
        content={"error": "الصفحة أو المورد المطلوب غير موجود"}
    )


# =============================================================================
# MAIN ENTRY POINT
# =============================================================================

if __name__ == "__main__":
    """
    Run the FastAPI application using Uvicorn.
    
    Command line usage:
        python main.py
        
    Or using uvicorn directly:
        uvicorn main:app --reload --host 0.0.0.0 --port 8000
    """
    import uvicorn
    
    # Run the server with auto-reload for development
    # In production, use a proper ASGI server like gunicorn with uvicorn workers
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info"
    )
