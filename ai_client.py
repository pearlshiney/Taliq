"""
ai_client.py - AI Model Client for Arabic Reading Evaluation App

This module provides a clean wrapper around the Elmodels AI API.
It handles all interactions with three AI models:
1. Nuha-2.0 (LLM) - For generating Arabic text
2. Elm-TTS - For text-to-speech synthesis
3. Elm-ASR - For automatic speech recognition


"""

import os
from openai import OpenAI
from dotenv import load_dotenv

# Load variables from .env into the system environment
load_dotenv()

# Access them using os.getenv()
API_KEY=os.getenv('API_KEY')

# =============================================================================
# CONFIGURATION
# =============================================================================

# Initialize the OpenAI client with Elmodels API configuration
# This client is compatible with OpenAI's API format
client = OpenAI(
    api_key = API_KEY,  # API key for Elmodels
    base_url="https://elmodels.ngrok.app/v1"  # Base URL for Elmodels API
)

# Model names as specified in requirements
LLM_MODEL = "nuha-2.0"      # For Arabic text generation
TTS_MODEL = "elm-tts"       # For text-to-speech
ASR_MODEL = "elm-asr"       # For speech-to-text

# Default voice for TTS (as per API requirements)
TTS_VOICE = "default"


# =============================================================================
# NUHA LLM FUNCTIONS
# =============================================================================

def ask_nuha(difficulty: str, length: str) -> str:
    """
    Generate Arabic text using the Nuha-2.0 LLM model.
    
    This function sends a prompt to Nuha asking for Arabic text suitable
    for reading practice based on the specified difficulty and length.
    
    Args:
        difficulty (str): Difficulty level - "beginner", "intermediate", or "advanced"
        length (str): Text length - "short", "medium", or "long"
    
    Returns:
        str: Generated Arabic text
    
    Raises:
        Exception: If the API call fails
    
    Example:
        >>> text = ask_nuha("beginner", "short")
        >>> print(text)
        "مرحباً، كيف حالك اليوم؟ أتمنى أن تكون بخير..."
    """
    try:
        # Build the system prompt to guide the model
        # We instruct Nuha to generate appropriate Arabic text
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
        )
        
        # Prepare messages for the chat completion API
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ]
        
        # Call the Nuha LLM model
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
        print(f"[ERROR] Failed to generate text with Nuha: {str(e)}")
        raise Exception(f"فشل في توليد النص: {str(e)}")


# =============================================================================
# ELM TTS FUNCTIONS
# =============================================================================

def generate_speech_file(text: str, output_path: str) -> str:
    """
    Generate speech audio file from Arabic text using Elm-TTS.
    
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
        
        # Call the Elm TTS model with streaming response
        # We use with_streaming_response for efficient file writing
        with client.audio.speech.with_streaming_response.create(
            model=TTS_MODEL,
            voice=TTS_VOICE,
            input=text,
        ) as response:
            # Stream the audio data directly to the file
            response.stream_to_file(output_path)
        
        return output_path
        
    except Exception as e:
        # Log the error and re-raise with a user-friendly message
        print(f"[ERROR] Failed to generate speech with Elm-TTS: {str(e)}")
        raise Exception(f"فشل في توليد الصوت: {str(e)}")


# =============================================================================
# ELM ASR FUNCTIONS
# =============================================================================

def transcribe_audio(audio_file_path: str) -> str:
    """
    Transcribe Arabic audio to text using Elm-ASR.
    
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
        with open(audio_file_path, "rb") as audio_file:
            # Call the Elm ASR model for transcription
            transcription = client.audio.transcriptions.create(
                model=ASR_MODEL,
                file=audio_file
            )
        
        # Extract the transcribed text
        # The response object has a 'text' attribute
        transcribed_text = transcription.text.strip()
        
        return transcribed_text
        
    except FileNotFoundError as e:
        # Re-raise file not found errors with Arabic message
        raise Exception(f"ملف الصوت غير موجود: {str(e)}")
        
    except Exception as e:
        # Log the error and re-raise with a user-friendly message
        print(f"[ERROR] Failed to transcribe audio with Elm-ASR: {str(e)}")
        raise Exception(f"فشل في تحويل الصوت لنص: {str(e)}")


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
    print("Use the functions: ask_nuha(), generate_speech_file(), transcribe_audio()")
