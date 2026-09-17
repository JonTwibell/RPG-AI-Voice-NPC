# Raspberry Pi 5 Setup Guide & Voice Pipeline

This guide details how to set up and run the Multi-Character AI Voice Assistant on a Raspberry Pi 5 running **Raspberry Pi OS (64-bit Bookworm)**.

---

## Hardware Requirements

* **Single Board Computer:** Raspberry Pi 5 (4GB or 8GB RAM recommended)
* **Microphone:** USB Microphone or USB Webcam with built-in mic
* **Audio Output:** USB Speakers, HDMI display/audio, or I2S DAC HAT *(Note: Pi 5 omits the 3.5mm analog audio jack)*
* **Power Supply:** Official 27W USB-C Power Supply

---

## 1. System Dependencies Installation

Update system packages and install Linux audio libraries along with `mpv` for lightweight MP3/WAV playback:

```bash
sudo apt update && sudo apt upgrade -y
sudo apt install -y python3-dev python3-venv portaudio19-dev libasound2-dev mpv

2. Environment Setup
Clone the repository:

Bash
git clone [https://github.com/your-username/mac-voice-assistant.git](https://github.com/your-username/mac-voice-assistant.git)
cd mac-voice-assistant
Create a Virtual Environment (with system site-packages access if needed):

Bash
python3 -m venv venv
source venv/bin/activate
Install Python Packages:

Bash
pip install --upgrade pip
pip install groq elevenlabs pyaudio python-dotenv
3. Audio Input/Output Verification
Verify that PyAudio and Linux ALSA recognize your USB hardware before running the main script:

Bash
# List recording devices
arecord -l

# List playback devices
aplay -l
If multiple audio interfaces are connected, configure your primary output device in ~/.asoundrc:

Plaintext
pcm.!default {
    type hw
    card 1
}
ctl.!default {
    type hw
    card 1
}
4. Raspberry Pi Compatible voice_pipeline.py
This version replaces macOS afplay execution with cross-platform subprocess invocation using mpv.

5. Auto-Start Service (Optional)
To configure the pipeline to run headless at boot on your Raspberry Pi:

Create a systemd service file:

Bash
sudo nano /etc/systemd/system/voice-assistant.service
Add the following configuration (replace pi with your actual username):

Ini, TOML
[Unit]
Description=Multi-Character AI Voice Assistant
After=network-online.target sound.target

[Service]
Type=simple
User=pi
WorkingDirectory=/home/pi/mac-voice-assistant
ExecStart=/home/pi/mac-voice-assistant/venv/bin/python3 voice_pipeline.py
Restart=on-failure
RestartSec=5s

[Install]
WantedBy=multi-user.target
Enable and start the service:

Bash
sudo systemctl daemon-reload
sudo systemctl enable voice-assistant.service
sudo systemctl start voice-assistant.service

<ElicitationsGroup message="Next options for hardware deployment:">
  <Elicitation label="Configure I2S DAC hardware settings for high quality audio" query="How do I configure Raspberry Pi boot overlays to output audio through an I2S DAC HAT like the Adafruit I2S DAC?"/>
  <Elicitation label="Add push-to-talk button trigger via GPIO" query="How can I update voice_pipeline.py to use a physical button connected to the Pi 5 GPIO pins instead of silence detection?"/>
</ElicitationsGroup>
