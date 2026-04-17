/**
 * app.js - Main Frontend Logic for طَلِقْ (Taliq)
 *
 * Simplified student flow:
 * 1. Select student name
 * 2. Load assigned text
 * 3. Record reading
 * 4. Evaluate and show diff
 */

// =============================================================================
// GLOBAL STATE MANAGEMENT
// =============================================================================

const appState = {
    currentView: 1,
    generatedText: '',
    transcribedText: '',
    audioBlob: null,
    audioUrl: null,
    ttsAudioUrl: null,
    recordingDuration: 0,
    evaluation: null,
    assignmentId: null,
    studentName: '',
    recordingUrl: null,
    evaluationId: null,
};

// =============================================================================
// VIEW NAVIGATION
// =============================================================================

function showView(viewNumber) {
    if (viewNumber < 1 || viewNumber > 3) {
        console.error(`Invalid view number: ${viewNumber}`);
        return;
    }
    appState.currentView = viewNumber;
    document.querySelectorAll('.view').forEach(view => view.classList.remove('active'));
    const targetView = document.getElementById(`view-${viewNumber}`);
    if (targetView) targetView.classList.add('active');
    updateProgressSteps(viewNumber);
    window.scrollTo({ top: 0, behavior: 'smooth' });
}

function updateProgressSteps(currentStep) {
    document.querySelectorAll('.step').forEach(step => {
        const stepNum = parseInt(step.dataset.step);
        step.classList.remove('active');
        if (stepNum === currentStep) step.classList.add('active');
    });
}

// =============================================================================
// VIEW 1: STUDENT SELECTOR
// =============================================================================

async function loadStudents() {
    const loadingEl = document.getElementById('student-loading');
    const formEl = document.getElementById('student-form');
    const errorEl = document.getElementById('student-error');
    const selectEl = document.getElementById('student-select');

    try {
        const response = await fetch('/api/students');
        const data = await response.json();
        if (!response.ok) throw new Error(data.error || 'فشل في جلب قائمة الطلاب');

        loadingEl.style.display = 'none';
        formEl.style.display = 'block';

        data.students.forEach(student => {
            const option = document.createElement('option');
            option.value = student.id;
            option.textContent = `${student.name} (${student.student_id_number})`;
            selectEl.appendChild(option);
        });
    } catch (error) {
        loadingEl.style.display = 'none';
        errorEl.textContent = error.message;
        errorEl.style.display = 'block';
        console.error('Error loading students:', error);
    }
}

async function loadAssignment(studentId) {
    const infoEl = document.getElementById('assignment-info');
    const noAssignEl = document.getElementById('no-assignment');
    const textEl = document.getElementById('assigned-text');
    const levelEl = document.getElementById('assignment-level');
    const lengthEl = document.getElementById('assignment-length');

    hideError('student-error');

    try {
        const response = await fetch(`/api/student-assignments/${studentId}`);
        const data = await response.json();

        if (!response.ok) {
            infoEl.style.display = 'none';
            noAssignEl.style.display = 'block';
            appState.assignmentId = null;
            appState.generatedText = '';
            return;
        }

        const assignment = data.assignment;
        appState.assignmentId = assignment.id;
        appState.generatedText = assignment.generated_text;
        appState.studentName = assignment.student_name;

        textEl.textContent = assignment.generated_text;
        levelEl.textContent = formatLevel(assignment.difficulty);
        lengthEl.textContent = formatLength(assignment.length);

        infoEl.style.display = 'block';
        noAssignEl.style.display = 'none';
    } catch (error) {
        showError('student-error', error.message);
        console.error('Error loading assignment:', error);
    }
}

function goToRecordView() {
    if (!appState.assignmentId) {
        showError('student-error', 'يرجى اختيار طالب ولديه نص معين');
        return;
    }
    const originalTextDisplay = document.getElementById('original-text-display');
    originalTextDisplay.textContent = appState.generatedText;
    showView(2);
}

function handleStudentChange() {
    const selectEl = document.getElementById('student-select');
    const studentId = selectEl.value;
    if (studentId) {
        loadAssignment(studentId);
    } else {
        document.getElementById('assignment-info').style.display = 'none';
        document.getElementById('no-assignment').style.display = 'none';
    }
}

// =============================================================================
// VIEW 2: RECORDING
// =============================================================================

let mediaRecorder = null;
let audioChunks = [];
let stream = null;
let recordingStartTime = null;

async function startRecording() {
    try {
        stream = await navigator.mediaDevices.getUserMedia({ audio: true });
        mediaRecorder = new MediaRecorder(stream, { mimeType: 'audio/webm' });
        audioChunks = [];

        mediaRecorder.ondataavailable = (event) => {
            if (event.data.size > 0) audioChunks.push(event.data);
        };

        mediaRecorder.onstop = () => {
            recordingDuration = (Date.now() - recordingStartTime) / 1000;
            appState.recordingDuration = recordingDuration;
            const audioBlob = new Blob(audioChunks, { type: 'audio/webm' });
            appState.audioBlob = audioBlob;
            const audioUrl = URL.createObjectURL(audioBlob);
            appState.audioUrl = audioUrl;
            document.getElementById('audio-preview').src = audioUrl;
            document.getElementById('audio-preview-container').style.display = 'block';
            document.getElementById('submit-evaluation-btn').disabled = false;
            stream.getTracks().forEach(track => track.stop());
        };

        recordingStartTime = Date.now();
        mediaRecorder.start();
        document.getElementById('start-record-btn').style.display = 'none';
        document.getElementById('stop-record-btn').style.display = 'inline-flex';
        document.getElementById('recording-status').style.display = 'flex';
        hideError('record-error');
    } catch (error) {
        console.error('Error starting recording:', error);
        showError('record-error', 'لا يمكن الوصول للميكروفون. يرجى السماح بالوصول والمحاولة مرة أخرى.');
    }
}

function stopRecording() {
    if (mediaRecorder && mediaRecorder.state !== 'inactive') {
        mediaRecorder.stop();
        document.getElementById('start-record-btn').style.display = 'inline-flex';
        document.getElementById('stop-record-btn').style.display = 'none';
        document.getElementById('recording-status').style.display = 'none';
    }
}

async function submitForEvaluation() {
    if (!appState.audioBlob) {
        showError('record-error', 'يرجى تسجيل الصوت أولاً');
        return;
    }
    if (!appState.assignmentId) {
        showError('record-error', 'لا يوجد تكليف محدد');
        return;
    }

    const submitBtn = document.getElementById('submit-evaluation-btn');
    const btnText = submitBtn.querySelector('.btn-text');
    const btnLoading = submitBtn.querySelector('.btn-loading');

    submitBtn.disabled = true;
    btnText.style.display = 'none';
    btnLoading.style.display = 'inline';
    hideError('record-error');

    try {
        // Step 1: Transcribe audio
        const audioFile = new File([appState.audioBlob], 'recording.webm', { type: 'audio/webm' });
        const formData = new FormData();
        formData.append('audio_file', audioFile);
        formData.append('recording_duration', appState.recordingDuration.toString());

        const transcribeResponse = await fetch('/api/transcribe', { method: 'POST', body: formData });
        const transcribeData = await transcribeResponse.json();

        if (!transcribeResponse.ok) {
            throw new Error(transcribeData.error || 'فشل في تحويل الصوت لنص');
        }

        appState.transcribedText = transcribeData.transcription;
        appState.recordingUrl = transcribeData.recording_url || null;

        // Step 2: Evaluate reading performance
        const evalFormData = new FormData();
        evalFormData.append('assignment_id', appState.assignmentId.toString());
        evalFormData.append('transcribed_text', appState.transcribedText);
        evalFormData.append('recording_duration', appState.recordingDuration.toString());
        evalFormData.append('recording_url', appState.recordingUrl || '');

        const evalResponse = await fetch('/api/evaluate', { method: 'POST', body: evalFormData });
        const evalData = await evalResponse.json();

        if (!evalResponse.ok) {
            throw new Error(evalData.error || 'فشل في تقييم القراءة');
        }

        appState.evaluation = evalData.evaluation;
        appState.evaluationId = evalData.evaluation_id || null;

        showEvaluationView();
    } catch (error) {
        showError('record-error', error.message);
        console.error('Error in evaluation:', error);
    } finally {
        submitBtn.disabled = false;
        btnText.style.display = 'inline';
        btnLoading.style.display = 'none';
    }
}

// =============================================================================
// VIEW 3: EVALUATION
// =============================================================================

function showEvaluationView() {
    const evalData = appState.evaluation;

    if (evalData && evalData.diff) {
        renderDiff(evalData.diff);
    } else {
        document.getElementById('eval-original-text').textContent = appState.generatedText;
        document.getElementById('eval-transcribed-text').textContent = appState.transcribedText;
    }

    if (evalData) {
        displayDetailedEvaluation(evalData);
    } else {
        const score = calculateScore(appState.generatedText, appState.transcribedText);
        displayScore(score);
        analyzeMistakes(appState.generatedText, appState.transcribedText);
    }

    showView(3);
}

function renderDiff(diff) {
    const originalEl = document.getElementById('eval-original-text');
    const transcribedEl = document.getElementById('eval-transcribed-text');

    const originalHtml = (diff.original || [])
        .map(token => {
            const word = escapeHtml(token.word);
            if (token.type === 'match') return `<span class="diff-match">${word}</span>`;
            if (token.type === 'missing') return `<span class="diff-missing">${word}</span>`;
            return word;
        })
        .join(' ');

    const transcribedHtml = (diff.transcribed || [])
        .map(token => {
            const word = escapeHtml(token.word);
            if (token.type === 'match') return `<span class="diff-match">${word}</span>`;
            if (token.type === 'extra') return `<span class="diff-extra">${word}</span>`;
            return word;
        })
        .join(' ');

    originalEl.innerHTML = originalHtml || '<em class="text-muted">لا يوجد نص</em>';
    transcribedEl.innerHTML = transcribedHtml || '<em class="text-muted">لا يوجد نص</em>';
}

function displayDetailedEvaluation(evaluation) {
    const overallScore = Math.round(evaluation.overall_score);
    displayScore(overallScore);

    const gradeBadge = document.getElementById('grade-badge');
    if (gradeBadge) {
        gradeBadge.textContent = evaluation.grade;
        gradeBadge.className = `grade-badge ${evaluation.grade_color}`;
    }

    const wordMatchEl = document.getElementById('word-match-score');
    if (wordMatchEl) wordMatchEl.textContent = `${evaluation.word_match_score}%`;

    const correctCountEl = document.getElementById('correct-count');
    const missingCountEl = document.getElementById('missing-count');
    const extraCountEl = document.getElementById('extra-count');

    if (correctCountEl) correctCountEl.textContent = evaluation.correct_words_count;
    if (missingCountEl) missingCountEl.textContent = evaluation.missing_words_count;
    if (extraCountEl) extraCountEl.textContent = evaluation.extra_words_count;

    const paceScoreEl = document.getElementById('pace-score');
    const paceEvalEl = document.getElementById('pace-evaluation');
    const paceFeedbackEl = document.getElementById('pace-feedback');
    const durationInfoEl = document.getElementById('duration-info');

    if (paceScoreEl) paceScoreEl.textContent = `${evaluation.pace_score}%`;
    if (paceEvalEl) paceEvalEl.textContent = evaluation.pace_evaluation;
    if (paceFeedbackEl) paceFeedbackEl.textContent = evaluation.pace_feedback;
    if (durationInfoEl) {
        durationInfoEl.textContent = `المدة: ${evaluation.actual_duration_seconds}ث (متوقع: ${evaluation.expected_duration_seconds}ث)`;
    }

    displayDetailedMistakes(evaluation);

    const summaryEl = document.getElementById('evaluation-summary');
    if (summaryEl && evaluation.summary) {
        summaryEl.innerHTML = `
            <div class="summary-item">
                <span class="summary-label">الدقة:</span>
                <span class="summary-value">${evaluation.summary.accuracy}</span>
            </div>
            <div class="summary-item">
                <span class="summary-label">الإيقاع:</span>
                <span class="summary-value">${evaluation.summary.pace}</span>
            </div>
            <div class="summary-item">
                <span class="summary-label">الطلاقة:</span>
                <span class="summary-value">${evaluation.summary.fluency}</span>
            </div>
        `;
    }
}

function displayDetailedMistakes(evaluation) {
    const mistakesContainer = document.getElementById('mistakes-container');
    const mistakesList = document.getElementById('mistakes-list');
    if (!mistakesList) return;

    mistakesList.innerHTML = '';
    const { missing_words, extra_words, correct_words_count, total_original_words } = evaluation;

    if (missing_words.length === 0 && extra_words.length === 0) {
        const li = document.createElement('li');
        li.className = 'perfect-reading';
        li.innerHTML = '🎉 قراءة ممتازة! لا يوجد أخطاء.';
        mistakesList.appendChild(li);
        if (mistakesContainer) mistakesContainer.style.display = 'block';
        return;
    }

    if (missing_words.length > 0) {
        const header = document.createElement('li');
        header.className = 'mistake-category';
        header.textContent = `❌ كلمات لم تنطق (${missing_words.length}):`;
        mistakesList.appendChild(header);
        missing_words.forEach(word => {
            const li = document.createElement('li');
            li.className = 'missing-word';
            li.innerHTML = `<span class="word-text">"${word}"</span> <span class="mistake-type">- لم تُنطق</span>`;
            mistakesList.appendChild(li);
        });
    }

    if (extra_words.length > 0) {
        const header = document.createElement('li');
        header.className = 'mistake-category';
        header.textContent = `➕ كلمات إضافية غير موجودة في النص (${extra_words.length}):`;
        mistakesList.appendChild(header);
        extra_words.forEach(word => {
            const li = document.createElement('li');
            li.className = 'extra-word';
            li.innerHTML = `<span class="word-text">"${word}"</span> <span class="mistake-type">- كلمة زائدة</span>`;
            mistakesList.appendChild(li);
        });
    }

    const summaryHeader = document.createElement('li');
    summaryHeader.className = 'mistake-summary';
    summaryHeader.innerHTML = `
        <strong>الملخص:</strong> ${correct_words_count} من ${total_original_words} كلمة صحيحة
        (${evaluation.word_match_score}% دقة)
    `;
    mistakesList.appendChild(summaryHeader);
    if (mistakesContainer) mistakesContainer.style.display = 'block';
}

function calculateScore(original, transcribed) {
    const normalizeText = (text) => {
        return text
            .replace(/[.,!?؛،:;"'()«»]/g, '')
            .replace(/\s+/g, ' ')
            .trim()
            .toLowerCase();
    };

    const normalizedOriginal = normalizeText(original);
    const normalizedTranscribed = normalizeText(transcribed);
    const originalWords = normalizedOriginal.split(' ').filter(w => w.length > 0);
    const transcribedWords = normalizedTranscribed.split(' ').filter(w => w.length > 0);

    if (originalWords.length === 0) return 0;

    let matchCount = 0;
    for (let i = 0; i < Math.min(originalWords.length, transcribedWords.length); i++) {
        if (originalWords[i] === transcribedWords[i]) matchCount++;
    }

    const score = Math.round((matchCount / originalWords.length) * 100);
    return Math.min(score, 100);
}

function displayScore(score) {
    const scoreValue = document.getElementById('score-value');
    const scoreCircle = document.querySelector('.score-circle');
    animateScore(scoreValue, 0, score, 1000);
    scoreCircle.classList.remove('low-score', 'medium-score');
    if (score < 50) scoreCircle.classList.add('low-score');
    else if (score < 80) scoreCircle.classList.add('medium-score');
}

function animateScore(element, start, end, duration) {
    const startTime = performance.now();
    function update(currentTime) {
        const elapsed = currentTime - startTime;
        const progress = Math.min(elapsed / duration, 1);
        const easeOutQuart = 1 - Math.pow(1 - progress, 4);
        const current = Math.round(start + (end - start) * easeOutQuart);
        element.textContent = current + '%';
        if (progress < 1) requestAnimationFrame(update);
    }
    requestAnimationFrame(update);
}

function analyzeMistakes(original, transcribed) {
    const mistakesContainer = document.getElementById('mistakes-container');
    const mistakesList = document.getElementById('mistakes-list');
    mistakesList.innerHTML = '';

    const normalizeText = (text) => {
        return text
            .replace(/[.,!?؛،:;"'()«»]/g, '')
            .replace(/\s+/g, ' ')
            .trim()
            .toLowerCase();
    };

    const originalWords = normalizeText(original).split(' ').filter(w => w.length > 0);
    const transcribedWords = normalizeText(transcribed).split(' ').filter(w => w.length > 0);
    const mistakes = [];

    const maxLength = Math.max(originalWords.length, transcribedWords.length);
    for (let i = 0; i < maxLength; i++) {
        const orig = originalWords[i] || '(غير موجود)';
        const trans = transcribedWords[i] || '(غير موجود)';
        if (orig !== trans) {
            if (originalWords[i] && !transcribedWords[i]) {
                mistakes.push(`كلمة "${originalWords[i]}" لم يتم نطقها`);
            } else if (!originalWords[i] && transcribedWords[i]) {
                mistakes.push(`كلمة إضافية "${transcribedWords[i]}" تمت إضافتها`);
            } else {
                mistakes.push(`"${originalWords[i]}" تم نطقها "${transcribedWords[i]}"`);
            }
        }
    }

    if (mistakes.length > 0) {
        mistakes.forEach(mistake => {
            const li = document.createElement('li');
            li.textContent = mistake;
            mistakesList.appendChild(li);
        });
        mistakesContainer.style.display = 'block';
    } else {
        const li = document.createElement('li');
        li.textContent = '🎉 قراءة ممتازة! لا يوجد أخطاء.';
        mistakesList.appendChild(li);
        mistakesContainer.style.display = 'block';
    }
}

async function playCorrectSpeech() {
    const playBtn = document.getElementById('play-tts-btn');
    const btnText = playBtn.querySelector('.btn-text');
    const btnLoading = playBtn.querySelector('.btn-loading');
    const ttsAudio = document.getElementById('tts-audio');

    playBtn.disabled = true;
    btnText.style.display = 'none';
    btnLoading.style.display = 'inline';
    hideError('eval-error');

    try {
        if (appState.ttsAudioUrl) {
            ttsAudio.src = appState.ttsAudioUrl;
            ttsAudio.style.display = 'block';
            ttsAudio.play();
            return;
        }

        const formData = new FormData();
        formData.append('text', appState.generatedText);
        if (appState.evaluationId) {
            formData.append('evaluation_id', appState.evaluationId.toString());
        }

        const response = await fetch('/api/generate-speech', { method: 'POST', body: formData });
        const data = await response.json();

        if (!response.ok) throw new Error(data.error || 'فشل في توليد الصوت');

        appState.ttsAudioUrl = data.audio_url;
        ttsAudio.src = data.audio_url;
        ttsAudio.style.display = 'block';
        ttsAudio.play();
    } catch (error) {
        showError('eval-error', error.message);
        console.error('Error generating TTS:', error);
    } finally {
        playBtn.disabled = false;
        btnText.style.display = 'inline';
        btnLoading.style.display = 'none';
    }
}

function resetApp() {
    appState.generatedText = '';
    appState.transcribedText = '';
    appState.audioBlob = null;
    appState.audioUrl = null;
    appState.ttsAudioUrl = null;
    appState.recordingDuration = 0;
    appState.evaluation = null;
    appState.assignmentId = null;
    appState.studentName = '';
    appState.recordingUrl = null;
    appState.evaluationId = null;
    recordingDuration = 0;

    document.getElementById('assignment-info').style.display = 'none';
    document.getElementById('no-assignment').style.display = 'none';
    document.getElementById('student-select').value = '';
    document.getElementById('original-text-display').textContent = '';
    document.getElementById('audio-preview-container').style.display = 'none';
    document.getElementById('audio-preview').src = '';
    document.getElementById('submit-evaluation-btn').disabled = true;
    document.getElementById('tts-audio').src = '';
    document.getElementById('tts-audio').style.display = 'none';
    document.getElementById('mistakes-container').style.display = 'none';
    document.getElementById('mistakes-list').innerHTML = '';

    hideError('student-error');
    hideError('record-error');
    hideError('eval-error');

    showView(1);
}

// =============================================================================
// UTILITY FUNCTIONS
// =============================================================================

function showError(elementId, message) {
    const errorElement = document.getElementById(elementId);
    if (errorElement) {
        errorElement.textContent = message;
        errorElement.style.display = 'block';
    }
}

function hideError(elementId) {
    const errorElement = document.getElementById(elementId);
    if (errorElement) {
        errorElement.style.display = 'none';
        errorElement.textContent = '';
    }
}

function escapeHtml(text) {
    if (!text) return '';
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

function formatLevel(difficulty) {
    const levels = { 'beginner': 'مبتدئ', 'intermediate': 'متوسط', 'advanced': 'متقدم' };
    return levels[difficulty] || difficulty || '-';
}

function formatLength(length) {
    const lengths = { 'short': 'قصير', 'medium': 'متوسط', 'long': 'طويل' };
    return lengths[length] || length || '-';
}

// =============================================================================
// EVENT LISTENERS
// =============================================================================

document.addEventListener('DOMContentLoaded', () => {
    loadStudents();

    document.getElementById('student-select').addEventListener('change', handleStudentChange);
    document.getElementById('go-to-record-btn').addEventListener('click', goToRecordView);
    document.getElementById('start-record-btn').addEventListener('click', startRecording);
    document.getElementById('stop-record-btn').addEventListener('click', stopRecording);
    document.getElementById('submit-evaluation-btn').addEventListener('click', submitForEvaluation);
    document.getElementById('back-to-student-btn').addEventListener('click', () => showView(1));
    document.getElementById('play-tts-btn').addEventListener('click', playCorrectSpeech);
    document.getElementById('try-again-btn').addEventListener('click', resetApp);

    console.log('🚀 طَلِقْ initialized');
});
