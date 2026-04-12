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
async def api_transcribe(
    audio_file: UploadFile = File(...),
    recording_duration: float = Form(0.0)
):
    """
    API endpoint to transcribe audio to Arabic text using Elm-ASR.
    
    This endpoint receives an audio file, saves it temporarily,
    calls the Elm-ASR model for transcription, and returns the text.
    Also performs detailed evaluation by comparing with original text.
    
    Args:
        audio_file (UploadFile): The uploaded audio file (webm, mp3, wav, etc.)
        recording_duration (float): Duration of recording in seconds (from frontend)
    
    Returns:
        JSONResponse: {"transcription": "...", "evaluation": {...}} on success
        JSONResponse: {"error": "..."} on failure (status 500)
    
    Example Request:
        POST /api/transcribe
        Content-Type: multipart/form-data
        File: audio_file=<binary audio data>
        recording_duration=15.5
    
    Example Response:
        {
            "transcription": "مرحبا كيف حالك",
            "evaluation": {
                "word_match_score": 85.0,
                "correct_words": ["مرحبا", "كيف"],
                "missing_words": ["اليوم"],
                "extra_words": ["مم"],
                "pace_score": 90.0,
                "pace_evaluation": "جيد",
                "expected_duration": 12.0,
                "actual_duration": 15.5
            }
        }
    """
    try:
        # Generate a unique filename for the temporary audio file
        file_extension = Path(audio_file.filename).suffix or ".webm"
        temp_filename = f"temp_{uuid.uuid4().hex}{file_extension}"
        temp_filepath = SPEECHES_DIR / temp_filename
        
        # Save the uploaded audio file to disk
        with open(temp_filepath, "wb") as f:
            content = await audio_file.read()
            f.write(content)
        
        # Call the AI client to transcribe the audio
        transcribed_text = transcribe_audio(str(temp_filepath))
        
        # Clean up: remove the temporary audio file
        os.remove(temp_filepath)
        
        return JSONResponse({
            "transcription": transcribed_text,
            "recording_duration": recording_duration
        })
        
    except Exception as e:
        # Cleanup on error if file exists
        if 'temp_filepath' in locals() and os.path.exists(temp_filepath):
            os.remove(temp_filepath)
        
        return JSONResponse(
            status_code=500,
            content={"error": f"حدث خطأ أثناء تحويل الصوت لنص: {str(e)}"}
        )


# =============================================================================
# EVALUATION ENDPOINT
# =============================================================================

@app.post("/api/evaluate")
async def api_evaluate(
    original_text: str = Form(...),
    transcribed_text: str = Form(...),
    recording_duration: float = Form(0.0)
):
    """
    API endpoint to evaluate reading performance.
    
    Compares transcribed text with original text and calculates:
    - Word match score (exact matching)
    - Missing words (words in original but not transcribed)
    - Extra words (words transcribed but not in original)
    - Reading pace evaluation
    
    Args:
        original_text (str): The original Arabic text that should be read
        transcribed_text (str): The text transcribed from user's audio
        recording_duration (float): Duration of recording in seconds
    
    Returns:
        JSONResponse: Detailed evaluation metrics
    """
    try:
        evaluation = evaluate_reading(
            original_text, 
            transcribed_text, 
            recording_duration
        )
        
        return JSONResponse({"evaluation": evaluation})
        
    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={"error": f"حدث خطأ أثناء التقييم: {str(e)}"}
        )


def evaluate_reading(
    original_text: str, 
    transcribed_text: str, 
    recording_duration: float = 0.0
) -> dict:
    """
    Evaluate reading performance by comparing original and transcribed text.
    
    Metrics calculated:
    1. Word Match Score: Percentage of correctly matched words
    2. Missing Words: Words from original that weren't transcribed
    3. Extra Words: Words transcribed that aren't in original (hesitation sounds)
    4. Pace Score: Evaluation of reading speed vs expected duration
    
    Args:
        original_text: The original text that should have been read
        transcribed_text: The text transcribed from user's audio
        recording_duration: Recording duration in seconds
    
    Returns:
        Dictionary containing all evaluation metrics
    """
    # Normalize text: remove punctuation, normalize spaces
    def normalize(text: str) -> list:
        # Arabic-specific normalization
        normalized = (
            text
            .replace('أ', 'ا')
            .replace('إ', 'ا')
            .replace('آ', 'ا')
            .replace('ة', 'ه')
            .replace('ى', 'ي')
            .replace('ؤ', 'و')
            .replace('ئ', 'ي')
        )
        # Remove punctuation and extra spaces
        import re
        normalized = re.sub(r'[^\w\s\u0600-\u06FF]', ' ', normalized)
        normalized = re.sub(r'\s+', ' ', normalized).strip()
        return normalized.lower().split()
    
    original_words = normalize(original_text)
    transcribed_words = normalize(transcribed_text)
    
    # Common hesitation sounds in Arabic ( filler words, stutters)
    hesitation_sounds = {
        'مم', 'ام', 'ااه', 'اوم', 'هم', 'ها', 'هو', 'اي', 'ايه',
        'umm', 'uh', 'ah', 'um', 'oh', 'eh', 'hmm', 'mm', 'err', 'er'
    }
    
    # Find matches using longest common subsequence approach
    correct_words = []
    missing_words = []
    extra_words = []
    hesitation_words = []
    
    # Simple word-by-word matching with alignment
    i, j = 0, 0
    while i < len(original_words) and j < len(transcribed_words):
        orig_word = original_words[i]
        trans_word = transcribed_words[j]
        
        if orig_word == trans_word:
            correct_words.append(orig_word)
            i += 1
            j += 1
        elif trans_word in hesitation_sounds:
            # This is a hesitation sound, skip it
            hesitation_words.append(trans_word)
            j += 1
        else:
            # Check if it's an extra word or a wrong word
            # Look ahead to see if current original word appears later in transcribed
            found_later = False
            for k in range(j + 1, min(j + 4, len(transcribed_words))):
                if transcribed_words[k] == orig_word:
                    # Words between j and k are extra/missing
                    for extra_idx in range(j, k):
                        extra_word = transcribed_words[extra_idx]
                        if extra_word in hesitation_sounds:
                            hesitation_words.append(extra_word)
                        else:
                            extra_words.append(extra_word)
                    j = k
                    found_later = True
                    break
            
            if not found_later:
                # Check if current transcribed word appears later in original
                for k in range(i + 1, min(i + 4, len(original_words))):
                    if original_words[k] == trans_word:
                        # Words between i and k are missing
                        for miss_idx in range(i, k):
                            missing_words.append(original_words[miss_idx])
                        i = k
                        found_later = True
                        break
            
            if not found_later:
                # Mismatch - count as wrong and move both
                missing_words.append(orig_word)
                if trans_word not in hesitation_sounds:
                    extra_words.append(trans_word)
                else:
                    hesitation_words.append(trans_word)
                i += 1
                j += 1
    
    # Handle remaining words
    while i < len(original_words):
        missing_words.append(original_words[i])
        i += 1
    
    while j < len(transcribed_words):
        word = transcribed_words[j]
        if word in hesitation_sounds:
            hesitation_words.append(word)
        else:
            extra_words.append(word)
        j += 1
    
    # Calculate Word Match Score
    total_original_words = len(original_words)
    if total_original_words > 0:
        word_match_score = round((len(correct_words) / total_original_words) * 100, 1)
    else:
        word_match_score = 0.0
    
    # Calculate Pace Score
    # Expected reading speed: ~120 words per minute (2 words per second) for normal pace
    # Range: 80-150 wpm is acceptable
    words_per_minute_normal = 120
    expected_duration_seconds = (total_original_words / words_per_minute_normal) * 60
    
    pace_score = 100.0
    pace_evaluation = "مثالي"
    pace_feedback = "سرعة القراءة ممتازة"
    
    if recording_duration > 0 and expected_duration_seconds > 0:
        ratio = recording_duration / expected_duration_seconds
        
        if 0.8 <= ratio <= 1.3:
            pace_score = 100.0
            pace_evaluation = "مثالي"
            pace_feedback = "سرعة القراءة ممتازة - إيقاع طبيعي"
        elif 0.6 <= ratio < 0.8:
            pace_score = 85.0
            pace_evaluation = "جيد"
            pace_feedback = "القراءة أسرع من المتوسط قليلاً"
        elif 1.3 < ratio <= 1.8:
            pace_score = 80.0
            pace_evaluation = "جيد"
            pace_feedback = "القراءة أبطأ من المتوسط - ربما يحتاج للمزيد من التدريب"
        elif ratio < 0.6:
            pace_score = 60.0
            pace_evaluation = "سريع جداً"
            pace_feedback = "القراءة سريعة جداً - قد تفقد الوضوح"
        else:  # ratio > 1.8
            pace_score = 60.0
            pace_evaluation = "بطيء جداً"
            pace_feedback = "القراءة بطيئة جداً - حاول القراءة بثقة أكبر"
    else:
        expected_duration_seconds = 0.0
    
    # Calculate Overall Score (weighted average)
    # Word match: 70%, Pace: 30%
    overall_score = round((word_match_score * 0.7) + (pace_score * 0.3), 1)
    
    # Determine grade
    if overall_score >= 90:
        grade = "ممتاز"
        grade_color = "excellent"
    elif overall_score >= 75:
        grade = "جيد جداً"
        grade_color = "very-good"
    elif overall_score >= 60:
        grade = "جيد"
        grade_color = "good"
    elif overall_score >= 40:
        grade = "يحتاج تحسين"
        grade_color = "needs-improvement"
    else:
        grade = "ضعيف"
        grade_color = "poor"
    
    return {
        # Core metrics
        "overall_score": overall_score,
        "grade": grade,
        "grade_color": grade_color,
        
        # Word matching metrics
        "word_match_score": word_match_score,
        "total_original_words": total_original_words,
        "correct_words_count": len(correct_words),
        "correct_words": correct_words,
        "missing_words": missing_words,
        "missing_words_count": len(missing_words),
        "extra_words": extra_words,
        "extra_words_count": len(extra_words),
        "hesitation_words": hesitation_words,
        "hesitation_count": len(hesitation_words),
        
        # Pace metrics
        "pace_score": pace_score,
        "pace_evaluation": pace_evaluation,
        "pace_feedback": pace_feedback,
        "expected_duration_seconds": round(expected_duration_seconds, 1),
        "actual_duration_seconds": round(recording_duration, 1),
        "words_per_minute": round((len(transcribed_words) / recording_duration) * 60, 1) if recording_duration > 0 else 0,
        
        # Summary
        "summary": {
            "accuracy": f"{word_match_score}%",
            "pace": pace_evaluation,
            "fluency": "متدفق" if len(hesitation_words) == 0 else f"بهesitation_words {len(hesitation_words)} تردد"
        }
    }


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
