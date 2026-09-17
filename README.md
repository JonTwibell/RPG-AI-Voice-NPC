Markdown
# Multi-Character AI Voice Assistant

An interactive, multi-character AI voice pipeline built for macOS. This project continuously listens to room audio, detects spoken keywords (e.g., `"Donut"`), routes the query to an LLM with character-specific personality traits, and speaks the response using a custom-cloned ElevenLabs AI voice.

---

## Features

* **Keyword Routing:** Supports multiple character personas stored in modular `.json` profile files.
* **Low-Cost Cloud Pipeline:** Offloads STT to Groq Whisper and LLM generation to Groq Cloud for sub-second processing.
* **Auto-Silence Detection:** Hands-free microphone recording using native math RMS volume detection (compatible with Python 3.13+).
* **Accent & Voice Customization:** Explicitly configures ElevenLabs model settings (`eleven_multilingual_v2`, `similarity_boost`, `stability`) to preserve regional accents and vocal quirks.
* **Continuous Loop:** Listens continuously until interrupted via `CTRL+C`.

---

## Architecture Overview

[ Microphone ] ---> (1) STT: Groq Whisper Large v3
|
v
(2) Keyword Router (profiles/*.json)
|
v
(3) LLM: Groq (openai/gpt-oss-20b)
|
v
(4) TTS: ElevenLabs API (afplay)


---

## Prerequisites

* **OS:** macOS (uses native `afplay` utility for audio playback)
* **Language:** Python 3.10+ (tested through Python 3.13)
* **System Packages:** [Homebrew](https://brew.sh/) and `portaudio`

```bash
brew install portaudio
Installation
Clone the repository:

Bash
git clone [https://github.com/your-username/mac-voice-assistant.git](https://github.com/your-username/mac-voice-assistant.git)
cd mac-voice-assistant
Create and activate a Python Virtual Environment:

Bash
python3 -m venv venv
source venv/bin/activate
Install dependencies:

Bash
pip install --upgrade pip
pip install groq elevenlabs pyaudio python-dotenv
Configuration
1. Environment Variables (.env)
Create a .env file in the root directory:

Code snippet
GROQ_API_KEY="gsk_YOUR_GROQ_API_KEY"
ELEVENLABS_API_KEY="YOUR_ELEVENLABS_API_KEY"
ELEVENLABS_VOICE_ID="YOUR_DEFAULT_FALLBACK_VOICE_ID"
2. Character Profiles (profiles/)
Create JSON profiles inside the profiles/ directory for each character keyword you want to support.

profiles/donut.json
JSON
{
  "keywords": ["donut", "doughnut"],
  "voice_id": "YOUR_DONUT_ELEVENLABS_VOICE_ID",
  "model_id": "eleven_multilingual_v2",
  "language_code": "en",
  "voice_settings": {
    "stability": 0.40,
    "similarity_boost": 0.85
  },
  "system_instruction": "You are a quick, witty, talking cat named Princess Donut The Queen Anne Chonk. Speak in plain, conversational sentences without lists. Keep responses under 3 sentences."
}
profiles/default.json
JSON
{
  "keywords": ["default"],
  "voice_id": "YOUR_DEFAULT_ELEVENLABS_VOICE_ID",
  "model_id": "eleven_turbo_v2_5",
  "language_code": "en",
  "voice_settings": {
    "stability": 0.50,
    "similarity_boost": 0.75
  },
  "system_instruction": "You are a helpful assistant. State clearly: 'Who are you talking to?'"
}
Usage
Run the main pipeline from your terminal:

Bash
python3 voice_pipeline.py
Speak naturally into your microphone.

Include a character keyword (e.g., "Donut, what should I do with this gold?").

Pause for 3 seconds of silence to trigger transcription and processing.

To exit the loop, press CTRL + C.

Troubleshooting
Microphone Permissions: If no audio is captured, go to System Settings -> Privacy & Security -> Microphone and ensure Terminal/iTerm is enabled.

Accent Loss: Ensure "model_id": "eleven_multilingual_v2" is set in your profile JSON and similarity_boost is set between 0.80 and 0.90.
