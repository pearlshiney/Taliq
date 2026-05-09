"""
main.py - FastAPI Backend for طَلِقْ (Taliq) Arabic Reading Evaluation App

This is the main entry point for the web application. It provides:
- REST API endpoints for AI operations
- Static file serving (CSS, JS, audio files)
- HTML template rendering
- Student management, assignment management, and admin settings

API Endpoints:
- POST /api/generate-text    : Generate Arabic text using LLM via OpenRouter
- POST /api/transcribe       : Transcribe audio using ASR via OpenRouter
- POST /api/generate-speech  : Generate TTS audio via OpenRouter
- POST /api/evaluate         : Evaluate reading performance
- GET  /api/students         : List all students
- POST /api/students         : Create a new student
- PUT  /api/students/{id}    : Update a student
- DELETE /api/students/{id}  : Delete a student
- GET  /api/assignments      : List all assignments
- POST /api/assignments      : Create a new assignment
- DELETE /api/assignments/{id} : Delete an assignment
- GET  /api/student-assignments/{student_id} : Get current assignment for student
- GET  /api/settings         : Read admin settings
- POST /api/settings         : Update admin settings
- GET  /api/results          : List all evaluation results
- GET  /api/dashboard-stats  : School-wide aggregated statistics
- GET  /api/health           : Health check
"""

import os
import sqlite3
import uuid
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, File, Form, Request, UploadFile
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

# Import our AI client module
from ai_client import (
    ask_llm,
    ensure_speeches_folder,
    generate_speech_file,
    remove_tashkeel,
    transcribe_audio,
)

# =============================================================================
# FASTAPI APP INITIALIZATION
# =============================================================================

app = FastAPI(
    title="طَلِقْ - Arabic Reading Evaluation",
    description="Web application for evaluating Arabic reading skills using AI",
    version="2.0.0"
)

BASE_DIR = Path(__file__).parent.resolve()
SPEECHES_DIR = BASE_DIR / "speeches"
RECORDINGS_DIR = BASE_DIR / "recordings"
DB_PATH = BASE_DIR / "evaluations.db"

ensure_speeches_folder(str(SPEECHES_DIR))
os.makedirs(RECORDINGS_DIR, exist_ok=True)

app.mount("/static", StaticFiles(directory=str(BASE_DIR / "static")), name="static")
app.mount("/speeches", StaticFiles(directory=str(SPEECHES_DIR)), name="speeches")
app.mount("/recordings", StaticFiles(directory=str(RECORDINGS_DIR)), name="recordings")

templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))


# =============================================================================
# DATABASE SETUP & MIGRATION
# =============================================================================

def init_db():
    """Initialize the SQLite database with all required tables."""
    conn = sqlite3.connect(str(DB_PATH))
    cursor = conn.cursor()

    # Students table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS students (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id_number TEXT NOT NULL UNIQUE,
            name TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # Assignments table (pre-generated paragraphs per student)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS assignments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id INTEGER NOT NULL,
            difficulty TEXT NOT NULL,
            length TEXT NOT NULL,
            generated_text TEXT NOT NULL,
            assigned_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            completed BOOLEAN DEFAULT 0,
            FOREIGN KEY (student_id) REFERENCES students(id)
        )
    """)

    # Settings table (admin-customizable parameters)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS settings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            key TEXT NOT NULL UNIQUE,
            value TEXT NOT NULL
        )
    """)

    # Check if old evaluations schema exists (has student_name column)
    cursor.execute("PRAGMA table_info(evaluations)")
    columns = {row[1] for row in cursor.fetchall()}

    if columns and "student_name" in columns:
        # Migrate old data
        cursor.execute("ALTER TABLE evaluations RENAME TO evaluations_old")
        cursor.execute("""
            CREATE TABLE evaluations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                assignment_id INTEGER,
                transcribed_text TEXT,
                recording_file_path TEXT,
                tts_file_path TEXT,
                overall_score REAL,
                grade TEXT,
                grade_color TEXT,
                word_match_score REAL,
                pace_score REAL,
                pace_evaluation TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (assignment_id) REFERENCES assignments(id)
            )
        """)
        cursor.execute("SELECT * FROM evaluations_old ORDER BY id")
        old_rows = cursor.fetchall()
        for row in old_rows:
            # row indices: id, student_name, difficulty, length, generated_text, ...
            student_name = row[1]
            difficulty = row[2]
            length = row[3]
            generated_text = row[4]
            transcribed_text = row[5]
            recording_file_path = row[6]
            tts_file_path = row[7]
            overall_score = row[8]
            grade = row[9]
            grade_color = row[10]
            word_match_score = row[11]
            pace_score = row[12]
            pace_evaluation = row[13]
            created_at = row[14]

            # Find or create student
            cursor.execute(
                "SELECT id FROM students WHERE name = ? LIMIT 1",
                (student_name,)
            )
            student_row = cursor.fetchone()
            if student_row:
                student_id = student_row[0]
            else:
                cursor.execute(
                    "INSERT INTO students (student_id_number, name) VALUES (?, ?)",
                    (str(uuid.uuid4().hex)[:8], student_name)
                )
                student_id = cursor.lastrowid

            # Create assignment
            cursor.execute(
                """
                INSERT INTO assignments (student_id, difficulty, length, generated_text, completed)
                VALUES (?, ?, ?, ?, ?)
                """,
                (student_id, difficulty, length, generated_text, 1)
            )
            assignment_id = cursor.lastrowid

            # Create new evaluation
            cursor.execute(
                """
                INSERT INTO evaluations (
                    assignment_id, transcribed_text, recording_file_path,
                    tts_file_path, overall_score, grade, grade_color,
                    word_match_score, pace_score, pace_evaluation, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    assignment_id, transcribed_text, recording_file_path,
                    tts_file_path, overall_score, grade, grade_color,
                    word_match_score, pace_score, pace_evaluation, created_at
                )
            )
        cursor.execute("DROP TABLE evaluations_old")
    else:
        # Fresh create or already migrated
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS evaluations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                assignment_id INTEGER,
                transcribed_text TEXT,
                recording_file_path TEXT,
                tts_file_path TEXT,
                overall_score REAL,
                grade TEXT,
                grade_color TEXT,
                word_match_score REAL,
                pace_score REAL,
                pace_evaluation TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (assignment_id) REFERENCES assignments(id)
            )
        """)

    # Insert default settings if empty
    cursor.execute("SELECT COUNT(*) FROM settings")
    if cursor.fetchone()[0] == 0:
        defaults = [
            ("words_per_minute_normal", "120"),
            ("ratio_ideal_min", "0.8"),
            ("ratio_ideal_max", "1.3"),
            ("ratio_fast_min", "0.6"),
            ("ratio_slow_max", "1.8"),
            ("word_match_weight", "0.7"),
            ("pace_weight", "0.3"),
            ("score_excellent", "90"),
            ("score_very_good", "75"),
            ("score_good", "60"),
            ("score_needs_improvement", "40"),
        ]
        cursor.executemany(
            "INSERT INTO settings (key, value) VALUES (?, ?)",
            defaults
        )

    conn.commit()
    conn.close()


init_db()


# =============================================================================
# SETTINGS HELPER
# =============================================================================

def get_settings() -> dict:
    """Read all admin settings from the database as a dictionary."""
    conn = sqlite3.connect(str(DB_PATH))
    cursor = conn.cursor()
    cursor.execute("SELECT key, value FROM settings")
    settings = {row[0]: row[1] for row in cursor.fetchall()}
    conn.close()

    # Convert numeric strings to floats/ints
    numeric_keys = [
        "words_per_minute_normal",
        "ratio_ideal_min", "ratio_ideal_max",
        "ratio_fast_min", "ratio_slow_max",
        "word_match_weight", "pace_weight",
        "score_excellent", "score_very_good",
        "score_good", "score_needs_improvement",
    ]
    for key in numeric_keys:
        if key in settings:
            try:
                settings[key] = float(settings[key])
            except ValueError:
                pass
    return settings


# =============================================================================
# HTML PAGE ROUTES
# =============================================================================

@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    """Serve the main HTML page for students."""
    return templates.TemplateResponse(request, "index.html")


@app.get("/dashboard", response_class=HTMLResponse)
async def dashboard(request: Request):
    """Serve the dashboard HTML page for decision makers."""
    return templates.TemplateResponse(request, "dashboard.html")


@app.get("/control-panel", response_class=HTMLResponse)
async def control_panel(request: Request):
    """Serve the control panel HTML page for admins."""
    return templates.TemplateResponse(request, "control_panel.html")


# =============================================================================
# STUDENT MANAGEMENT ENDPOINTS
# =============================================================================

@app.get("/api/students")
async def api_list_students():
    """List all registered students."""
    try:
        conn = sqlite3.connect(str(DB_PATH))
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM students ORDER BY name")
        students = [dict(row) for row in cursor.fetchall()]
        conn.close()
        return JSONResponse({"students": students})
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})


@app.post("/api/students")
async def api_create_student(
    student_id_number: str = Form(...),
    name: str = Form(...)
):
    """Create a new student."""
    try:
        conn = sqlite3.connect(str(DB_PATH))
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO students (student_id_number, name) VALUES (?, ?)",
            (student_id_number, name)
        )
        student_id = cursor.lastrowid
        conn.commit()
        conn.close()
        return JSONResponse({"id": student_id, "message": "تم إضافة الطالب بنجاح"})
    except sqlite3.IntegrityError:
        return JSONResponse(
            status_code=400,
            content={"error": "رقم الطالب موجود مسبقاً"}
        )
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})


@app.put("/api/students/{student_id}")
async def api_update_student(
    student_id: int,
    student_id_number: str = Form(...),
    name: str = Form(...)
):
    """Update a student's information."""
    try:
        conn = sqlite3.connect(str(DB_PATH))
        cursor = conn.cursor()
        cursor.execute(
            "UPDATE students SET student_id_number = ?, name = ? WHERE id = ?",
            (student_id_number, name, student_id)
        )
        if cursor.rowcount == 0:
            conn.close()
            return JSONResponse(status_code=404, content={"error": "الطالب غير موجود"})
        conn.commit()
        conn.close()
        return JSONResponse({"message": "تم تحديث بيانات الطالب بنجاح"})
    except sqlite3.IntegrityError:
        return JSONResponse(
            status_code=400,
            content={"error": "رقم الطالب موجود مسبقاً"}
        )
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})


@app.delete("/api/students/{student_id}")
async def api_delete_student(student_id: int):
    """Delete a student and all related assignments/evaluations."""
    try:
        conn = sqlite3.connect(str(DB_PATH))
        cursor = conn.cursor()
        cursor.execute("DELETE FROM students WHERE id = ?", (student_id,))
        if cursor.rowcount == 0:
            conn.close()
            return JSONResponse(status_code=404, content={"error": "الطالب غير موجود"})
        conn.commit()
        conn.close()
        return JSONResponse({"message": "تم حذف الطالب بنجاح"})
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})


# =============================================================================
# ASSIGNMENT MANAGEMENT ENDPOINTS
# =============================================================================

@app.get("/api/assignments")
async def api_list_assignments():
    """List all assignments with student names."""
    try:
        conn = sqlite3.connect(str(DB_PATH))
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute("""
            SELECT a.*, s.name AS student_name, s.student_id_number
            FROM assignments a
            JOIN students s ON a.student_id = s.id
            ORDER BY a.assigned_at DESC
        """)
        assignments = [dict(row) for row in cursor.fetchall()]
        conn.close()
        return JSONResponse({"assignments": assignments})
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})


@app.post("/api/assignments")
async def api_create_assignment(
    student_id: int = Form(...),
    difficulty: str = Form(...),
    length: str = Form(...),
    generated_text: str = Form(...)
):
    """Create a new assignment by generating text via LLM."""
    try:
        # generated_text = ask_llm(difficulty, length)

        conn = sqlite3.connect(str(DB_PATH))
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO assignments (student_id, difficulty, length, generated_text)
            VALUES (?, ?, ?, ?)
            """,
            (student_id, difficulty, length, generated_text)
        )
        assignment_id = cursor.lastrowid
        conn.commit()
        conn.close()

        return JSONResponse({
            "id": assignment_id,
            "generated_text": generated_text,
            "message": "تم إنشاء النص وتحديده للطالب بنجاح"
        })
    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={"error": f"حدث خطأ أثناء إنشاء التكليف: {str(e)}"}
        )


@app.delete("/api/assignments/{assignment_id}")
async def api_delete_assignment(assignment_id: int):
    """Delete an assignment."""
    try:
        conn = sqlite3.connect(str(DB_PATH))
        cursor = conn.cursor()
        cursor.execute("DELETE FROM assignments WHERE id = ?", (assignment_id,))
        if cursor.rowcount == 0:
            conn.close()
            return JSONResponse(status_code=404, content={"error": "التكليف غير موجود"})
        conn.commit()
        conn.close()
        return JSONResponse({"message": "تم حذف التكليف بنجاح"})
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})


@app.get("/api/student-assignments/{student_id}")
async def api_get_student_assignment(student_id: int):
    """Get the current (latest incomplete) assignment for a student."""
    try:
        conn = sqlite3.connect(str(DB_PATH))
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute("""
            SELECT a.*, s.name AS student_name
            FROM assignments a
            JOIN students s ON a.student_id = s.id
            WHERE a.student_id = ? AND a.completed = 0
            ORDER BY a.assigned_at DESC
            LIMIT 1
        """, (student_id,))
        row = cursor.fetchone()
        conn.close()

        if row:
            return JSONResponse({"assignment": dict(row)})
        else:
            return JSONResponse(
                status_code=404,
                content={"error": "لا يوجد نص معين لهذا الطالب"}
            )
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})


# =============================================================================
# ADMIN SETTINGS ENDPOINTS
# =============================================================================

@app.get("/api/settings")
async def api_get_settings():
    """Get all admin settings."""
    try:
        settings = get_settings()
        return JSONResponse({"settings": settings})
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})


@app.post("/api/settings")
async def api_update_settings(
    words_per_minute_normal: float = Form(...),
    ratio_ideal_min: float = Form(...),
    ratio_ideal_max: float = Form(...),
    ratio_fast_min: float = Form(...),
    ratio_slow_max: float = Form(...),
    word_match_weight: float = Form(...),
    pace_weight: float = Form(...),
    score_excellent: float = Form(...),
    score_very_good: float = Form(...),
    score_good: float = Form(...),
    score_needs_improvement: float = Form(...)
):
    """Update admin settings."""
    try:
        conn = sqlite3.connect(str(DB_PATH))
        cursor = conn.cursor()
        updates = [
            ("words_per_minute_normal", str(words_per_minute_normal)),
            ("ratio_ideal_min", str(ratio_ideal_min)),
            ("ratio_ideal_max", str(ratio_ideal_max)),
            ("ratio_fast_min", str(ratio_fast_min)),
            ("ratio_slow_max", str(ratio_slow_max)),
            ("word_match_weight", str(word_match_weight)),
            ("pace_weight", str(pace_weight)),
            ("score_excellent", str(score_excellent)),
            ("score_very_good", str(score_very_good)),
            ("score_good", str(score_good)),
            ("score_needs_improvement", str(score_needs_improvement)),
        ]
        for key, value in updates:
            cursor.execute(
                "INSERT INTO settings (key, value) VALUES (?, ?) ON CONFLICT(key) DO UPDATE SET value = ?",
                (key, value, value)
            )
        conn.commit()
        conn.close()
        return JSONResponse({"message": "تم حفظ الإعدادات بنجاح"})
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})


# =============================================================================
# CORE API ENDPOINTS
# =============================================================================

@app.post("/api/generate-text")
async def api_generate_text(
    difficulty: str = Form(...),
    length: str = Form(...)
):
    """Generate Arabic text using LLM via OpenRouter."""
    try:
        valid_difficulties = ["beginner", "intermediate", "advanced"]
        valid_lengths = ["short", "medium", "long"]
        if difficulty not in valid_difficulties:
            return JSONResponse(status_code=400, content={"error": f"مستوى الصعوبة يجب أن يكون: {', '.join(valid_difficulties)}"})
        if length not in valid_lengths:
            return JSONResponse(status_code=400, content={"error": f"الطول يجب أن يكون: {', '.join(valid_lengths)}"})
        generated_text = ask_llm(difficulty, length)
        return JSONResponse({"text": generated_text})
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": f"حدث خطأ أثناء توليد النص: {str(e)}"})


@app.post("/api/transcribe")
async def api_transcribe(
    audio_file: UploadFile = File(...),
    recording_duration: float = Form(0.0)
):
    """Transcribe audio to Arabic text using ASR via OpenRouter."""
    try:
        file_extension = Path(audio_file.filename).suffix or ".webm"
        recording_filename = f"recording_{uuid.uuid4().hex}{file_extension}"
        recording_filepath = RECORDINGS_DIR / recording_filename

        with open(recording_filepath, "wb") as f:
            content = await audio_file.read()
            f.write(content)

        transcribed_text = transcribe_audio(str(recording_filepath))

        # Remove tashkeel via LLM
        # try:
        #     transcribed_text = remove_tashkeel(transcribed_text)
        # except Exception as te:
        #     print(f"[WARN] Tashkeel removal failed: {te}")

        recording_url = f"/recordings/{recording_filename}"

        return JSONResponse({
            "transcription": transcribed_text,
            "recording_duration": recording_duration,
            "recording_url": recording_url
        })
    except Exception as e:
        if 'recording_filepath' in locals() and os.path.exists(recording_filepath):
            os.remove(recording_filepath)
        return JSONResponse(status_code=500, content={"error": f"حدث خطأ أثناء تحويل الصوت لنص: {str(e)}"})


@app.post("/api/evaluate")
async def api_evaluate(
    assignment_id: int = Form(...),
    transcribed_text: str = Form(...),
    recording_duration: float = Form(0.0),
    recording_url: str = Form(...)
):
    """Evaluate reading performance and persist the result."""
    try:
        # Fetch assignment details
        conn = sqlite3.connect(str(DB_PATH))
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute(
            "SELECT * FROM assignments WHERE id = ?",
            (assignment_id,)
        )
        assignment = cursor.fetchone()
        if not assignment:
            conn.close()
            return JSONResponse(status_code=404, content={"error": "التكليف غير موجود"})
        assignment = dict(assignment)

        # Evaluate
        evaluation = evaluate_reading(
            assignment["generated_text"],
            transcribed_text,
            recording_duration
        )

        # Persist evaluation
        cursor.execute("""
            INSERT INTO evaluations (
                assignment_id, transcribed_text, recording_file_path,
                overall_score, grade, grade_color, word_match_score,
                pace_score, pace_evaluation
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            assignment_id,
            transcribed_text,
            recording_url,
            evaluation["overall_score"],
            evaluation["grade"],
            evaluation["grade_color"],
            evaluation["word_match_score"],
            evaluation["pace_score"],
            evaluation["pace_evaluation"]
        ))
        evaluation_id = cursor.lastrowid

        # Mark assignment as completed
        cursor.execute(
            "UPDATE assignments SET completed = 1 WHERE id = ?",
            (assignment_id,)
        )

        conn.commit()
        conn.close()

        return JSONResponse({
            "evaluation": evaluation,
            "evaluation_id": evaluation_id
        })
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": f"حدث خطأ أثناء التقييم: {str(e)}"})


@app.post("/api/generate-speech")
async def api_generate_speech(
    text: str = Form(...),
    evaluation_id: Optional[str] = Form(None)
):
    """Generate TTS audio from Arabic text via OpenRouter."""
    try:
        if not text or not text.strip():
            return JSONResponse(status_code=400, content={"error": "النص فارغ"})

        # Remove tashkeel before TTS
        try:
            text = remove_tashkeel(text)
        except Exception as te:
            print(f"[WARN] Tashkeel removal failed for TTS: {te}")

        filename = f"speech_{uuid.uuid4().hex}.mp3"
        filepath = SPEECHES_DIR / filename
        generate_speech_file(text, str(filepath))
        audio_url = f"/speeches/{filename}"

        if evaluation_id:
            conn = sqlite3.connect(str(DB_PATH))
            cursor = conn.cursor()
            cursor.execute(
                "UPDATE evaluations SET tts_file_path = ? WHERE id = ?",
                (audio_url, evaluation_id)
            )
            conn.commit()
            conn.close()

        return JSONResponse({"audio_url": audio_url})
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": f"حدث خطأ أثناء توليد الصوت: {str(e)}"})


# =============================================================================
# RESULTS & DASHBOARD ENDPOINTS
# =============================================================================

@app.get("/api/results")
async def api_results():
    """Retrieve all evaluation results with assignment/student details."""
    try:
        conn = sqlite3.connect(str(DB_PATH))
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute("""
            SELECT
                e.id,
                s.name AS student_name,
                s.student_id_number,
                a.difficulty,
                a.length,
                a.generated_text,
                e.transcribed_text,
                e.recording_file_path,
                e.tts_file_path,
                e.overall_score,
                e.grade,
                e.grade_color,
                e.word_match_score,
                e.pace_score,
                e.pace_evaluation,
                e.created_at
            FROM evaluations e
            JOIN assignments a ON e.assignment_id = a.id
            JOIN students s ON a.student_id = s.id
            ORDER BY e.created_at DESC
        """)
        rows = cursor.fetchall()
        conn.close()
        results = [dict(row) for row in rows]
        return JSONResponse({"results": results})
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": f"حدث خطأ أثناء جلب النتائج: {str(e)}"})


@app.get("/api/dashboard-stats")
async def api_dashboard_stats():
    """Retrieve school-wide aggregated statistics."""
    try:
        conn = sqlite3.connect(str(DB_PATH))
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        cursor.execute("""
            SELECT
                COUNT(DISTINCT s.id) AS total_students,
                COUNT(*) AS total_evaluations,
                ROUND(AVG(e.overall_score), 1) AS mean_score,
                ROUND(MAX(e.overall_score), 1) AS best_score,
                ROUND(AVG(e.word_match_score), 1) AS mean_word_match
            FROM evaluations e
            JOIN assignments a ON e.assignment_id = a.id
            JOIN students s ON a.student_id = s.id
        """)
        top_row = dict(cursor.fetchone())

        cursor.execute("""
            SELECT a.difficulty, COUNT(*) AS count
            FROM evaluations e
            JOIN assignments a ON e.assignment_id = a.id
            WHERE a.difficulty IS NOT NULL
            GROUP BY a.difficulty
        """)
        difficulty_breakdown = {row["difficulty"]: row["count"] for row in cursor.fetchall()}

        cursor.execute("""
            SELECT a.length, COUNT(*) AS count
            FROM evaluations e
            JOIN assignments a ON e.assignment_id = a.id
            WHERE a.length IS NOT NULL
            GROUP BY a.length
        """)
        length_breakdown = {row["length"]: row["count"] for row in cursor.fetchall()}

        cursor.execute("""
            SELECT e.grade_color, COUNT(*) AS count
            FROM evaluations e
            WHERE e.grade_color IS NOT NULL
            GROUP BY e.grade_color
        """)
        grade_distribution = {row["grade_color"]: row["count"] for row in cursor.fetchall()}

        cursor.execute("""
            SELECT e.pace_evaluation, COUNT(*) AS count
            FROM evaluations e
            WHERE e.pace_evaluation IS NOT NULL
            GROUP BY e.pace_evaluation
        """)
        pace_distribution = {row["pace_evaluation"]: row["count"] for row in cursor.fetchall()}

        conn.close()

        stats = {
            "total_students": top_row["total_students"] or 0,
            "total_evaluations": top_row["total_evaluations"] or 0,
            "mean_score": top_row["mean_score"] or 0.0,
            "best_score": top_row["best_score"] or 0.0,
            "mean_word_match": top_row["mean_word_match"] or 0.0,
            "difficulty_breakdown": difficulty_breakdown,
            "length_breakdown": length_breakdown,
            "grade_distribution": grade_distribution,
            "pace_distribution": pace_distribution,
        }
        return JSONResponse({"stats": stats})
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": f"حدث خطأ أثناء جلب الإحصائيات: {str(e)}"})


# =============================================================================
# HEALTH CHECK
# =============================================================================

@app.get("/api/health")
async def health_check():
    return JSONResponse({"status": "ok", "service": "طَلِقْ - Arabic Reading Evaluation"})


# =============================================================================
# EVALUATION LOGIC
# =============================================================================

def evaluate_reading(
    original_text: str,
    transcribed_text: str,
    recording_duration: float = 0.0
) -> dict:
    """
    Evaluate reading performance by comparing original and transcribed text.

    No normalization is applied — words are compared as-is (case-insensitive).
    No hesitation sound logic is used.
    All scoring parameters are read from the settings table.
    """
    settings = get_settings()

        # Remove tashkeel via LLM
    try:
        original_tokens_no_tashkeel = remove_tashkeel(original_text)
    except Exception as te:
        print(f"[WARN] Tashkeel removal failed: {te}")

    
    # Raw tokenization (preserve original words, only lower-case for comparison)
    original_tokens_raw = original_tokens_no_tashkeel.split()
    transcribed_tokens_raw = transcribed_text.split()
    original_words = [w.lower() for w in original_tokens_raw]
    transcribed_words = [w.lower() for w in transcribed_tokens_raw]

    # Diff token lists
    original_diff = []
    transcribed_diff = []
    correct_words = []
    missing_words = []
    extra_words = []

    i, j = 0, 0
    while i < len(original_words) and j < len(transcribed_words):
        orig_word = original_words[i]
        trans_word = transcribed_words[j]
        orig_raw = original_tokens_raw[i]
        trans_raw = transcribed_tokens_raw[j]

        if orig_word == trans_word:
            original_diff.append({"word": orig_raw, "type": "match"})
            transcribed_diff.append({"word": trans_raw, "type": "match"})
            correct_words.append(orig_word)
            i += 1
            j += 1
        else:
            found_later = False
            for k in range(j + 1, min(j + 4, len(transcribed_words))):
                if transcribed_words[k] == orig_word:
                    for extra_idx in range(j, k):
                        extra_raw = transcribed_tokens_raw[extra_idx]
                        extra_norm = transcribed_words[extra_idx]
                        transcribed_diff.append({"word": extra_raw, "type": "extra"})
                        extra_words.append(extra_norm)
                    j = k
                    found_later = True
                    break

            if not found_later:
                for k in range(i + 1, min(i + 4, len(original_words))):
                    if original_words[k] == trans_word:
                        for miss_idx in range(i, k):
                            miss_raw = original_tokens_raw[miss_idx]
                            miss_norm = original_words[miss_idx]
                            original_diff.append({"word": miss_raw, "type": "missing"})
                            missing_words.append(miss_norm)
                        i = k
                        found_later = True
                        break

            if not found_later:
                original_diff.append({"word": orig_raw, "type": "missing"})
                missing_words.append(orig_word)
                transcribed_diff.append({"word": trans_raw, "type": "extra"})
                extra_words.append(trans_word)
                i += 1
                j += 1

    while i < len(original_words):
        miss_raw = original_tokens_raw[i]
        miss_norm = original_words[i]
        original_diff.append({"word": miss_raw, "type": "missing"})
        missing_words.append(miss_norm)
        i += 1

    while j < len(transcribed_words):
        extra_raw = transcribed_tokens_raw[j]
        extra_norm = transcribed_words[j]
        transcribed_diff.append({"word": extra_raw, "type": "extra"})
        extra_words.append(extra_norm)
        j += 1

    # Scoring
    total_original_words = len(original_words)
    if total_original_words > 0:
        word_match_score = round((len(correct_words) / total_original_words) * 100, 1)
    else:
        word_match_score = 0.0

    words_per_minute_normal = settings.get("words_per_minute_normal", 120)
    expected_duration_seconds = (total_original_words / words_per_minute_normal) * 60

    ratio_ideal_min = settings.get("ratio_ideal_min", 0.8)
    ratio_ideal_max = settings.get("ratio_ideal_max", 1.3)
    ratio_fast_min = settings.get("ratio_fast_min", 0.6)
    ratio_slow_max = settings.get("ratio_slow_max", 1.8)

    pace_score = 100.0
    pace_evaluation = "مثالي"
    pace_feedback = "سرعة القراءة ممتازة"

    if recording_duration > 0 and expected_duration_seconds > 0:
        ratio = recording_duration / expected_duration_seconds

        if ratio_ideal_min <= ratio <= ratio_ideal_max:
            pace_score = 100.0
            pace_evaluation = "مثالي"
            pace_feedback = "سرعة القراءة ممتازة - إيقاع طبيعي"
        elif ratio_fast_min <= ratio < ratio_ideal_min:
            pace_score = 85.0
            pace_evaluation = "جيد"
            pace_feedback = "القراءة أسرع من المتوسط قليلاً"
        elif ratio_ideal_max < ratio <= ratio_slow_max:
            pace_score = 80.0
            pace_evaluation = "جيد"
            pace_feedback = "القراءة أبطأ من المتوسط - ربما يحتاج للمزيد من التدريب"
        elif ratio < ratio_fast_min:
            pace_score = 60.0
            pace_evaluation = "سريع جداً"
            pace_feedback = "القراءة سريعة جداً - قد تفقد الوضوح"
        else:
            pace_score = 60.0
            pace_evaluation = "بطيء جداً"
            pace_feedback = "القراءة بطيئة جداً - حاول القراءة بثقة أكبر"
    else:
        expected_duration_seconds = 0.0

    word_match_weight = settings.get("word_match_weight", 0.7)
    pace_weight = settings.get("pace_weight", 0.3)
    overall_score = round((word_match_score * word_match_weight) + (pace_score * pace_weight), 1)

    score_excellent = settings.get("score_excellent", 90)
    score_very_good = settings.get("score_very_good", 75)
    score_good = settings.get("score_good", 60)
    score_needs_improvement = settings.get("score_needs_improvement", 40)

    if overall_score >= score_excellent:
        grade = "ممتاز"
        grade_color = "excellent"
    elif overall_score >= score_very_good:
        grade = "جيد جداً"
        grade_color = "very-good"
    elif overall_score >= score_good:
        grade = "جيد"
        grade_color = "good"
    elif overall_score >= score_needs_improvement:
        grade = "يحتاج تحسين"
        grade_color = "needs-improvement"
    else:
        grade = "ضعيف"
        grade_color = "poor"

    return {
        "overall_score": overall_score,
        "grade": grade,
        "grade_color": grade_color,
        "word_match_score": word_match_score,
        "total_original_words": total_original_words,
        "correct_words_count": len(correct_words),
        "correct_words": correct_words,
        "missing_words": missing_words,
        "missing_words_count": len(missing_words),
        "extra_words": extra_words,
        "extra_words_count": len(extra_words),
        "pace_score": pace_score,
        "pace_evaluation": pace_evaluation,
        "pace_feedback": pace_feedback,
        "expected_duration_seconds": round(expected_duration_seconds, 1),
        "actual_duration_seconds": round(recording_duration, 1),
        "words_per_minute": round((len(transcribed_words) / recording_duration) * 60, 1) if recording_duration > 0 else 0,
        "diff": {
            "original": original_diff,
            "transcribed": transcribed_diff
        },
        "summary": {
            "accuracy": f"{word_match_score}%",
            "pace": pace_evaluation,
            "fluency": "متدفق"
        }
    }


# =============================================================================
# ERROR HANDLERS
# =============================================================================

@app.exception_handler(404)
async def not_found_handler(request: Request, exc):
    return JSONResponse(
        status_code=404,
        content={"error": "الصفحة أو المورد المطلوب غير موجود"}
    )


# =============================================================================
# MAIN ENTRY POINT
# =============================================================================

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info"
    )
