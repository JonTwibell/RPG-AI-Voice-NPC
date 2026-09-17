import os
import glob
import json
import wave
import time
import math
import struct
import subprocess
import pyaudio
from dotenv import load_dotenv
from groq import Groq
from elevenlabs import ElevenLabs, VoiceSettings

# Load Environment Variables
load_dotenv()
GROQ_KEY = os.getenv("GROQ_API_KEY")
ELEVEN_KEY = os.getenv("ELEVENLABS_API_KEY")

groq_client = Groq(api_key=GROQ_KEY)
eleven_client = ElevenLabs(api_key=ELEVEN_KEY)

# Audio Parameters
FORMAT = pyaudio.paInt16
CHANNELS = 1
RATE = 16000
CHUNK = 1024
SILENCE_THRESHOLD = 800  # Adjust higher/lower based on ambient room noise
SILENCE_DURATION = 3.0   # Seconds of continuous silence required to stop recording

AUDIO_INPUT_FILE = "input_mic.wav"
AUDIO_OUTPUT_FILE = "response.mp3"

def load_profiles():
    """Loads all JSON profile configurations from the profiles directory."""
    profiles = []
    for filepath in glob.glob("profiles/*.json"):
        try:
            with open(filepath, "r") as f:
                data = json.load(f)
                profiles.append(data)
        except Exception as e:
            print(f"[x] Error loading {filepath}: {e}")
            
    # Fallback default profile if no default.json is explicitly defined
    default_profile = {
        "voice_id": os.getenv("ELEVENLABS_VOICE_ID", ""),
        "model_id": "eleven_multilingual_v2",
        "language_code": "en",
        "voice_settings": {"stability": 0.5, "similarity_boost": 0.75},
        "system_instruction": "You are a helpful assistant. State clearly: 'Who are you talking to?'"
    }
    
    for p in profiles:
        if "default" in p.get("keywords", []):
            default_profile = p
            break

    return profiles, default_profile

def calculate_rms(data):
    """Calculates RMS audio volume using Python standard libraries (Python 3.13+ safe)."""
    count = len(data) // 2
    if count == 0:
        return 0
    shorts = struct.unpack(f"{count}h", data)
    sum_squares = sum(s ** 2 for s in shorts)
    return math.sqrt(sum_squares / count)

def record_until_silence():
    """Continuously listens and starts recording when speech is detected, 
    then stops after 3 seconds of continuous silence."""
    audio = pyaudio.PyAudio()
    stream = audio.open(format=FORMAT, channels=CHANNELS, rate=RATE, 
                       input=True, frames_per_buffer=CHUNK)

    print("\n[ Listening... Speak a keyword like 'Donut' to start ]")

    frames = []
    is_speaking = False
    silence_start_time = None

    while True:
        data = stream.read(CHUNK, exception_on_overflow=False)
        rms = calculate_rms(data)

        if rms > SILENCE_THRESHOLD:
            if not is_speaking:
                print("[!] Speech detected, recording...")
                is_speaking = True
            silence_start_time = None
            frames.append(data)
        elif is_speaking:
            frames.append(data)
            if silence_start_time is None:
                silence_start_time = time.time()
            elif time.time() - silence_start_time >= SILENCE_DURATION:
                print("[+] 3 seconds of silence detected. Processing input...")
                break

    stream.stop_stream()
    stream.close()
    audio.terminate()

    with wave.open(AUDIO_INPUT_FILE, 'wb') as wf:
        wf.setnchannels(CHANNELS)
        wf.setsampwidth(audio.get_sample_size(FORMAT))
        wf.setframerate(RATE)
        wf.writeframes(b''.join(frames))

def transcribe_audio(file_path):
    """Transcribes mic input using Groq Whisper."""
    with open(file_path, "rb") as file:
        transcription = groq_client.audio.transcriptions.create(
            file=(file_path, file.read()),
            model="whisper-large-v3-turbo",
            response_format="text"
        )
    return transcription.strip()

def parse_profile(user_text, profiles, default_profile):
    """Checks if any keyword from the loaded profiles exists in user text."""
    clean_text = user_text.lower()
    for profile in profiles:
        for keyword in profile.get("keywords", []):
            if keyword.lower() in clean_text:
                print(f"[+] Keyword Matched: '{keyword}'")
                return profile
    
    print("[-] No keyword match found. Using Default Profile.")
    return default_profile

def generate_llm_response(user_text, system_instruction):
    """Generates AI response using Groq LLM with persona system instructions."""
    response = groq_client.chat.completions.create(
        model="openai/gpt-oss-20b",
        messages=[
            {"role": "system", "content": system_instruction},
            {"role": "user", "content": user_text}
        ],
        temperature=0.7,
        max_tokens=1024,
        extra_body={"reasoning_format": "hidden"}
    )
    content = response.choices[0].message.content
    return content if content else "Who are you talking to?"

def speak_text(text, profile):
    """Converts response text to audio via ElevenLabs using custom profile settings."""
    voice_id = profile.get("voice_id")
    if not voice_id:
        print("[x] Error: No Voice ID provided for TTS.")
        return

    # Extract settings or use defaults
    model_id = profile.get("model_id", "eleven_multilingual_v2")
    language_code = profile.get("language_code", "en")
    
    v_settings = profile.get("voice_settings", {})
    stability = v_settings.get("stability", 0.5)
    similarity_boost = v_settings.get("similarity_boost", 0.75)

    # Request voice audio with accent/model parameters applied
    audio_stream = eleven_client.text_to_speech.convert(
        voice_id=voice_id,
        text=text,
        model_id=model_id,
        language_code=language_code,
        voice_settings=VoiceSettings(
            stability=stability,
            similarity_boost=similarity_boost
        ),
        output_format="mp3_44100_128"
    )
    
    with open(AUDIO_OUTPUT_FILE, "wb") as f:
        for chunk in audio_stream:
            if chunk:
                f.write(chunk)
                
    subprocess.run(["afplay", AUDIO_OUTPUT_FILE])

def main():
    profiles, default_profile = load_profiles()
    print(f"[ System Initialized with {len(profiles)} character profiles ]")

    try:
        while True:
            # Step 1: Wait for speech and 3 seconds silence
            record_until_silence()

            # Step 2: Transcribe speech
            user_text = transcribe_audio(AUDIO_INPUT_FILE)
            print(f"User Said: \"{user_text}\"")

            if not user_text:
                continue

            # Step 3: Match Keyword Profile
            matched_profile = parse_profile(user_text, profiles, default_profile)

            # Step 4: Generate LLM Response
            llm_reply = generate_llm_response(user_text, matched_profile["system_instruction"])
            print(f"AI Reply: \"{llm_reply}\"")

            # Step 5: Output Speech using matched profile settings
            print("[+] Speaking response...")
            speak_text(llm_reply, matched_profile)

    except KeyboardInterrupt:
        print("\n[!] Loop terminated by user (CTRL+C). Goodbye!")

if __name__ == "__main__":
    main()
