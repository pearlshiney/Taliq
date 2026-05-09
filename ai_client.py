"""
ai_client.py - AI Model Client for Arabic Reading Evaluation App

This module provides a clean wrapper around the OpenRouter AI API.
It handles all interactions with three AI models:
1. LLM - For generating Arabic text (via OpenRouter chat completions)
2. TTS - For text-to-speech synthesis (via OpenRouter audio/speech)
3. ASR - For automatic speech recognition (via OpenRouter audio/transcriptions)

"""

import os
import requests
import base64
import json
from openai import OpenAI
from dotenv import load_dotenv

# Load variables from .env into the system environment
load_dotenv()

# Access them using os.getenv()
OPENROUTER_API_KEY = os.getenv('openrouter_api_key')

# =============================================================================
# CONFIGURATION
# =============================================================================

# Initialize the OpenAI client with OpenRouter API configuration
# This client is compatible with OpenAI's API format
client = OpenAI(
    api_key=OPENROUTER_API_KEY,  # API key for OpenRouter
    base_url="https://openrouter.ai/api/v1"  # Base URL for OpenRouter API
)

# Initialize the OpenRouter client with OpenRouter API configuration
opoenrouter_url="https://openrouter.ai/api/v1/audio/transcriptions"
opoenrouter_headers={
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json"
    }

# Model names as specified on OpenRouter
# These can be changed to any compatible model available on OpenRouter
LLM_MODEL = "google/gemma-4-31b-it"      # For Arabic text generation
TTS_MODEL = "openai/gpt-4o-mini-tts-2025-12-15"                     # For text-to-speech
ASR_MODEL = "openai/whisper-1"                 # For speech-to-text

# Default voice for TTS (OpenAI voices: alloy, echo, fable, onyx, nova, shimmer)
TTS_VOICE = "alloy"


# =============================================================================
# LLM FUNCTIONS
# =============================================================================

def ask_llm(difficulty: str, length: str) -> str:
    """
    Generate Arabic text using an LLM via OpenRouter.
    
    This function sends a prompt to the LLM asking for Arabic text suitable
    for reading practice based on the specified difficulty and length.
    
    Args:
        difficulty (str): Difficulty level - "beginner", "intermediate", or "advanced"
        length (str): Text length - "short", "medium", or "long"
    
    Returns:
        str: Generated Arabic text
    
    Raises:
        Exception: If the API call fails
    
    Example:
        >>> text = ask_llm("beginner", "short")
        >>> print(text)
        "مرحباً، كيف حالك اليوم؟ أتمنى أن تكون بخير..."
    """
    try:
        # Build the system prompt to guide the model
        # We instruct the LLM to generate appropriate Arabic text
        system_prompt = (
            "أنت مساعد متخصص في تعليم اللغة العربية. "
            "قم بإنشاء نصوص عربية مناسبة للطلاب لممارسة القراءة. "
            "يجب أن يكون النص واضحاً وخالياً من الأخطاء الإملائية."
        )
        
        # Build the user prompt with specific requirements
        # We map English difficulty/length to Arabic descriptions
        difficulty_ar = {
            "beginner": "مبتدئ (كلمات بسيطة، جمل قصيرة)",
            "intermediate": "متوسط (مفردات متنوعة، جمل متوسطة)",
            "advanced": "متقدم (مفردات صعبة، جمل معقدة)"
        }.get(difficulty, "مبتدئ")
        
        length_ar = {
            "short": "قصير (2-3 جمل)",
            "medium": "متوسط (4-6 جمل)",
            "long": "طويل (7-10 جمل)"
        }.get(length, "قصير")
        
        user_prompt = (
            f"أنشئ نصاً باللغة العربية للقراءة. "
            f"المستوى: {difficulty_ar}. "
            f"الطول: {length_ar}. "
            f"اكتب فقط النص بدون أي مقدمات أو تعليقات."
            f"اضف الحركات والتشكيل الصحيح على النص حسب الحاجة."
        )
        
        # Prepare messages for the chat completion API
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ]
        
        # Call the LLM model via OpenRouter
        # We use streaming=False to get the complete response at once
        response = client.chat.completions.create(
            model=LLM_MODEL,
            messages=messages,
            stream=False,
            temperature=0.7,  # Slight creativity but consistent
            max_tokens=500    # Limit response length
        )
        
        # Extract and clean the generated text
        generated_text = response.choices[0].message.content.strip()
        
        return generated_text
        
    except Exception as e:
        # Log the error and re-raise with a user-friendly message
        print(f"[ERROR] Failed to generate text with LLM: {str(e)}")
        raise Exception(f"فشل في توليد النص: {str(e)}")


# =============================================================================
# TTS FUNCTIONS
# =============================================================================

def generate_speech_file(text: str, output_path: str) -> str:
    """
    Generate speech audio file from Arabic text using TTS via OpenRouter.
    
    This function converts Arabic text to speech and saves it to the
    specified file path. The generated audio can be used for correct
    pronunciation reference.
    
    Args:
        text (str): Arabic text to convert to speech
        output_path (str): Full file path where the audio will be saved
    
    Returns:
        str: The output path (for convenience)
    
    Raises:
        Exception: If the API call or file writing fails
    
    Example:
        >>> generate_speech_file("مرحباً", "/path/to/speech.mp3")
        "/path/to/speech.mp3"
    """
    try:
        # Ensure the directory exists
        output_dir = os.path.dirname(output_path)
        if output_dir and not os.path.exists(output_dir):
            os.makedirs(output_dir, exist_ok=True)
        
        # Call the TTS model with streaming response
        # We use with_streaming_response for efficient file writing
        with client.audio.speech.with_streaming_response.create(
            model=TTS_MODEL,
            voice=TTS_VOICE,
            input=text,
            response_format="mp3"
        ) as response:
            # Stream the audio data directly to the file
            response.stream_to_file(output_path)
        
        return output_path
        
    except Exception as e:
        # Log the error and re-raise with a user-friendly message
        print(f"[ERROR] Failed to generate speech with TTS: {str(e)}")
        raise Exception(f"فشل في توليد الصوت: {str(e)}")


# =============================================================================
# ASR FUNCTIONS
# =============================================================================

def transcribe_audio(audio_file_path: str) -> str:
    """
    Transcribe Arabic audio to text using ASR via OpenRouter.
    
    This function takes an audio file and converts it to Arabic text.
    Supports common audio formats like MP3, WAV, OGG, WebM.
    
    Args:
        audio_file_path (str): Path to the audio file to transcribe
    
    Returns:
        str: Transcribed Arabic text
    
    Raises:
        Exception: If the API call fails or file not found
    
    Example:
        >>> text = transcribe_audio("/path/to/recording.webm")
        >>> print(text)
        "مرحبا كيف حالك"
    """
    try:
        # Verify the file exists
        if not os.path.exists(audio_file_path):
            raise FileNotFoundError(f"الملف غير موجود: {audio_file_path}")
        
        # Open the audio file in binary mode
        # The API handles format detection automatically


        with open(audio_file_path, "rb") as f:
            base64_audio = base64.b64encode(f.read()).decode("utf-8")

        response = requests.post(
            url=opoenrouter_url,
            headers=opoenrouter_headers,
            data=json.dumps({
                "model": ASR_MODEL,
                "input_audio": {
                    "data": base64_audio,
                    "format": "webm"
                },
                "language": "ar"
            })
        )
        # Extract the transcribed text
        # The response object has a 'text' attribute
        result = response.json()
        transcribed_text = result["text"].strip()
        
        # return transcribed_text
        return transcribed_text
    
    except FileNotFoundError as e:
        # Re-raise file not found errors with Arabic message
        raise Exception(f"ملف الصوت غير موجود: {str(e)}")
        
    except Exception as e:
        # Log the error and re-raise with a user-friendly message
        print(f"[ERROR] Failed to transcribe audio with ASR: {str(e)}")
        raise Exception(f"فشل في تحويل الصوت لنص: {str(e)}")


# =============================================================================
# UTILITY FUNCTIONS
# =============================================================================

# =============================================================================
# TASHKEEL REMOVAL
# =============================================================================

def remove_tashkeel(text: str) -> str:
    """
    Remove Arabic diacritics (tashkeel) from text using an LLM via OpenRouter.
    
    This ensures clean text for both TTS generation and text comparison,
    preventing pronunciation issues caused by incorrect harakat.
    
    Args:
        text (str): Arabic text potentially containing tashkeel
    
    Returns:
        str: The same text with all diacritics removed
    
    Raises:
        Exception: If the API call fails
    """
    try:
        system_prompt = (
            "أنت مساعد متخصص في معالجة النصوص العربية."
            "مهمتك إزالة التشكيل (الحركات) فقط من النصوص العربية."
            "لا تغير أي كلمة, ولا تضيف أو تحذف أي حرف."
            "أعد النص كما هو بالضبط لكن بدون أي تشكيل."
        )
        
        user_prompt = (
            "أزل جميع علامات الترقيم والتشكيل من النص التالي وأعد النص بدون أي علامات الترقيم وبدون أي تشكيل:/n"
            f"{text}"
        )
        
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ]
        
        response = client.chat.completions.create(
            model=LLM_MODEL,
            messages=messages,
            stream=False,
            temperature=0.1,
            max_tokens=1000
        )
        
        cleaned_text = response.choices[0].message.content.strip()
        return cleaned_text
        
    except Exception as e:
        print(f"[ERROR] Failed to remove tashkeel with LLM: {str(e)}")
        raise Exception(f"فشل في إزالة التشكيل: {str(e)}")


# =============================================================================
# UTILITY FUNCTIONS
# =============================================================================

def ensure_speeches_folder(folder_path: str = "speeches") -> str:
    """
    Ensure the speeches folder exists for storing generated audio files.
    
    Args:
        folder_path (str): Path to the speeches folder (default: "speeches")
    
    Returns:
        str: The absolute path to the speeches folder
    """
    abs_path = os.path.abspath(folder_path)
    os.makedirs(abs_path, exist_ok=True)
    return abs_path


# =============================================================================
# MODULE TEST
# =============================================================================

if __name__ == "__main__":
    """
    Simple test to verify the AI client is working.
    Run with: python ai_client.py
    """
    print("Testing AI Client...")
    print(f"LLM Model: {LLM_MODEL}")
    print(f"TTS Model: {TTS_MODEL}")
    print(f"ASR Model: {ASR_MODEL}")
    print("\nAI Client module loaded successfully!")
    print("Use the functions: ask_llm(), generate_speech_file(), transcribe_audio()")
