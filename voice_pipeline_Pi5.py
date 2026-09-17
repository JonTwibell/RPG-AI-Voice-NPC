import os
import io
import math
import time
import json
import glob
import struct
import subprocess
import pyaudio
from dotenv import load_dotenv
from groq import Groq
from elevenlabs.client import ElevenLabs

# Load environment configuration
load_dotenv()

GROQ_API_KEY = os.getenv("GROQ_API_KEY")
ELEVENLABS_API_KEY = os.getenv("ELEVENLABS_API_KEY")
DEFAULT_VOICE_ID = os.getenv("ELEVENLABS_VOICE_ID", "21m00Tcm4TlvDq8ikWAM")

# Initialize API clients
groq_client = Groq(api_key=GROQ_API_KEY)
eleven_client = ElevenLabs(api_key=ELEVENLABS_API_KEY)

# Audio Recording Configurations
FORMAT = pyaudio.paInt16
CHANNELS = 1
RATE = 16000
CHUNK = 1024
SILENCE_THRESHOLD = 300  # Adjust based on mic sensitivity
SILENCE_DURATION = 3.0   # Seconds of silence to trigger processing

def calculate_rms(data):
    """Calculate Root Mean Square (RMS) volume from raw audio chunk."""
    count = len(data) // 2
    format_str = f"{count}h"
    shorts = struct.unpack(format_str, data)
    sum_squares = sum(s ** 2 for s in shorts)
    return math.sqrt(sum_squares / count) if count > 0 else 0

def load_character_profiles():
    """Load character JSON configurations from the profiles directory."""
    profiles = {}
    for filepath in glob.glob("profiles/*.json"):
        try:
            with open(filepath, "r") as f:
                data = json.load(f)
                for kw in data.get("keywords", []):
                    profiles[kw.lower()] = data
        except Exception as e:
            print(f"[Error] Failed to load profile {filepath}: {e}")
    return profiles

def play_audio_linux(audio_data):
    """Play back MP3 audio bytes using mpv on Raspberry Pi."""
    try:
        process = subprocess.Popen(
            ["mpv", "--no-terminal", "--", "-"],
            stdin=subprocess.PIPE,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL
        )
        process.communicate(input=audio_data)
    except Exception as e:
        print(f"[Error] Audio playback failed: {e}")

def record_until_silence():
    """Record microphone stream until prolonged silence is detected."""
    p = pyaudio.PyAudio()
    stream = p.open(
        format=FORMAT,
        channels=CHANNELS,
        rate=RATE,
        input=True,
        frames_per_buffer=CHUNK
    )

    print("\n[Listening...] Speak into your microphone.")
    frames = []
    silent_chunks = 0
    num_silent_chunks_needed = int((RATE / CHUNK) * SILENCE_DURATION)
    has_spoken = False

    while True:
        data = stream.read(CHUNK, exception_on_overflow=False)
        frames.append(data)
        rms = calculate_rms(data)

        if rms > SILENCE_THRESHOLD:
            has_spoken = True
            silent_chunks = 0
        elif has_spoken:
            silent_chunks += 1
            if silent_chunks >= num_silent_chunks_needed:
                print("[Silence Detected] Processing input...")
                break

    stream.stop_stream()
    stream.close()
    p.terminate()

    # Package as WAV bytes
    import wave
    wav_buffer = io.BytesIO()
    wf = wave.open(wav_buffer, "wb")
    wf.setnchannels(CHANNELS)
    wf.setsampwidth(p.get_sample_size(FORMAT))
    wf.setframerate(RATE)
    wf.writeframes(b"".join(frames))
    wav_buffer.seek(0)
    wav_buffer.name = "input.wav"
    return wav_buffer

def process_voice_pipeline():
    profiles = load_character_profiles()
    
    while True:
        try:
            wav_file = record_until_silence()

            # 1. Speech-to-Text via Groq Whisper
            transcription = groq_client.audio.transcriptions.create(
                file=(wav_file.name, wav_file.read()),
                model="whisper-large-v3-turbo",
                response_format="text"
            )
            
            user_text = transcription.strip()
            if not user_text:
                continue

            print(f"\nUser Said: \"{user_text}\"")

            # 2. Keyword & Profile Routing
            matched_profile = None
            words = user_text.lower().split()
            for kw, profile in profiles.items():
                if any(kw in word for word in words):
                    matched_profile = profile
                    print(f"[Matched Persona]: {kw.upper()}")
                    break

            if not matched_profile:
                matched_profile = profiles.get("default", {
                    "voice_id": DEFAULT_VOICE_ID,
                    "model_id": "eleven_turbo_v2_5",
                    "voice_settings": {"stability": 0.5, "similarity_boost": 0.75},
                    "system_instruction": "You are a helpful assistant."
                })

            # 3. LLM Generation via Groq
            completion = groq_client.chat.completions.create(
                model="llama-3.3-70b-versatile",
                messages=[
                    {"role": "system", "content": matched_profile["system_instruction"]},
                    {"role": "user", "content": user_text}
                ],
                max_tokens=150
            )
            response_text = completion.choices[0].message.content
            print(f"Assistant: {response_text}")

            # 4. TTS Generation via ElevenLabs
            voice_settings = matched_profile.get("voice_settings", {})
            audio_generator = eleven_client.generate(
                text=response_text,
                voice=matched_profile.get("voice_id", DEFAULT_VOICE_ID),
                model=matched_profile.get("model_id", "eleven_multilingual_v2"),
                voice_settings=voice_settings
            )

            # Consume generator stream to bytes
            audio_bytes = b"".join(audio_generator)

            # 5. Linux Audio Playback
            play_audio_linux(audio_bytes)

        except KeyboardInterrupt:
            print("\nExiting pipeline.")
            break
        except Exception as e:
            print(f"[Pipeline Error]: {e}")

if __name__ == "__main__":
    process_voice_pipeline()
