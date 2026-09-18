import os
import re
import wave
import random
import glob
import time
import math
import struct
import subprocess
import pyaudio
from dotenv import load_dotenv
from groq import Groq
from elevenlabs import ElevenLabs

# Load API Keys
load_dotenv()

GROQ_KEY = os.getenv("GROQ_API_KEY")
ELEVEN_KEY = os.getenv("ELEVENLABS_API_KEY")
VOICE_ID = "8dEUmyPMdDdK91vboYih"

# Initialize SDK Clients
groq_client = Groq(api_key=GROQ_KEY)
eleven_client = ElevenLabs(api_key=ELEVEN_KEY)

# Audio Recording Configuration
FORMAT = pyaudio.paInt16
CHANNELS = 1
RATE = 16000
CHUNK = 1024
AUDIO_INPUT_FILE = "input_mic.wav"
AUDIO_OUTPUT_FILE = "response.mp3"

# Silence & Threshold Parameters
SILENCE_LIMIT = 2.0  # Seconds of silence to trigger submission
SILENCE_THRESHOLD = 500  # RMS Volume Threshold (Adjust based on mic sensitivity)

# Pre-generated audio directories
STATEMENT_DIR = "./lawyerstatement"
QUESTION_DIR = "./lawyerquestion"

SYSTEM_INSTRUCTION = (
    "You are the rules lawyer.  You love rules but most of all when it helps you.  Your job is to look up rules for Dungeons and Dragons 5.5e (2024) unless specified what ruleset to use.  Look for sources that are the most reputable (official sources) like dndbeyond, roll20, before looking for other resources.  Be sure to be as snooty and insulting as possible when responding.  Keep the response brief when possible.  Try to limit response to 5 sentenses or fewer."
)

def calculate_rms(chunk):
    """Calculates the Root Mean Square volume of an audio frame chunk."""
    count = len(chunk) / 2
    format_str = f"%dh" % count
    shorts = struct.unpack(format_str, chunk)
    sum_squares = sum(s ** 2 for s in shorts)
    return math.sqrt(sum_squares / count) if count > 0 else 0

def record_audio_vad(output_filename, silence_limit=SILENCE_LIMIT):
    """Continuously listens and collects audio once voice is detected, stopping after silence_limit seconds."""
    audio = pyaudio.PyAudio()
    stream = audio.open(format=FORMAT, channels=CHANNELS, rate=RATE, input=True, frames_per_buffer=CHUNK)

    print("\n[!] Listening continuously... (Unmute mic to speak)")
    frames = []
    has_started_speaking = False
    silence_start_time = None

    while True:
        data = stream.read(CHUNK, exception_on_overflow=False)
        rms = calculate_rms(data)

        if rms > SILENCE_THRESHOLD:
            if not has_started_speaking:
                print("[+] Voice detected! Recording...")
                has_started_speaking = True
            frames.append(data)
            silence_start_time = None
        elif has_started_speaking:
            frames.append(data)
            if silence_start_time is None:
                silence_start_time = time.time()
            elif time.time() - silence_start_time >= silence_limit:
                print(f"[+] {silence_limit}s silence detected. Processing segment...")
                break

    stream.stop_stream()
    stream.close()
    audio.terminate()

    with wave.open(output_filename, 'wb') as wf:
        wf.setnchannels(CHANNELS)
        wf.setsampwidth(audio.get_sample_size(FORMAT))
        wf.setframerate(RATE)
        wf.writeframes(b''.join(frames))

def play_audio_file(file_path):
    """Plays audio via macOS afplay and waits until completion."""
    if os.path.exists(file_path):
        subprocess.run(["afplay", file_path])

def play_preroll_audio(user_text):
    """Plays a random pre-recorded mp3 from question or statement folder."""
    is_question = user_text.strip().endswith("?")
    folder = QUESTION_DIR if is_question else STATEMENT_DIR
    files = glob.glob(os.path.join(folder, "*.mp3"))

    if files:
        selected_file = random.choice(files)
        print(f"[+] Playing pre-roll sound: {selected_file}")
        play_audio_file(selected_file)

def transcribe_audio(file_path):
    """Sends recorded WAV file to Groq Whisper."""
    with open(file_path, "rb") as file:
        transcription = groq_client.audio.transcriptions.create(
            file=(file_path, file.read()),
            model="whisper-large-v3-turbo",
            response_format="text"
        )
    return transcription

def generate_llm_response(conversation_history):
    """Sends transcription to Groq LLM with chat history retained."""
    response = groq_client.chat.completions.create(
        model="openai/gpt-oss-20b",
        messages=conversation_history,
        temperature=0.7,
        max_tokens=1024,
        extra_body={"reasoning_format": "hidden"}
    )
    content = response.choices[0].message.content
    return content if content else "What do you want, little fly?"

def speak_text(text, voice_id):
    """Converts text to cloned voice via ElevenLabs and plays audio via macOS afplay."""
    audio_stream = eleven_client.text_to_speech.convert(
        voice_id=voice_id,
        text=text,
        model_id="eleven_turbo_v2_5",
        output_format="mp3_44100_128"
    )
    
    with open(AUDIO_OUTPUT_FILE, "wb") as f:
        for chunk in audio_stream:
            if chunk:
                f.write(chunk)
                
    play_audio_file(AUDIO_OUTPUT_FILE)

def main():
    # Initialize folder structures if missing
    os.makedirs(STATEMENT_DIR, exist_ok=True)
    os.makedirs(QUESTION_DIR, exist_ok=True)

    # Initialize continuous session conversation history
    conversation_history = [{"role": "system", "content": SYSTEM_INSTRUCTION}]

    print("[+] Conversation session initialized.")

    while True:
        try:
            record_audio_vad(AUDIO_INPUT_FILE, silence_limit=SILENCE_LIMIT)

            user_text = transcribe_audio(AUDIO_INPUT_FILE)
            clean_text = user_text.strip()

            if not clean_text:
                print("[-] No transcript detected. Retrying...")
                continue

            print(f"\nUser Said: \"{clean_text}\"")

            # 1. Play pre-recorded buffer file based on input sentence end-point
            play_preroll_audio(clean_text)

            # 2. Append turn to persistent history context
            conversation_history.append({"role": "user", "content": clean_text})

            # 3. Generate response using updated context
            llm_reply = generate_llm_response(conversation_history)
            print(f"AI Reply: \"{llm_reply.strip()}\"")

            # 4. Save response to history and synthesize audio output
            conversation_history.append({"role": "assistant", "content": llm_reply})
            speak_text(llm_reply, VOICE_ID)

        except KeyboardInterrupt:
            print("\n[+] Exiting conversation loop.")
            break
        except Exception as e:
            print(f"[x] Error encountered: {e}")

if __name__ == "__main__":
    main()
