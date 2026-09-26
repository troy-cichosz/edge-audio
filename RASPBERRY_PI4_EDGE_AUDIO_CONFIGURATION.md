# Raspberry Pi 4 Edge-Audio Host Configuration

**Project:** `edge-audio`  
**Platform:** Raspberry Pi 4  
**OS:** Debian GNU/Linux 13 (Trixie), 64-bit  
**Microphone:** AITRIP INMP441 omnidirectional I2S MEMS microphone  
**Container runtime:** Docker Engine + Docker Compose  
**Status:** I2S capture proven functional; DSP tuning in progress

---

## 1. Purpose

This document records the known-good Raspberry Pi 4 host configuration, INMP441 wiring, ALSA/I2S setup, Docker configuration, audio testing commands, and the current `edge-audio` container architecture.

The intent is to provide a repeatable baseline for additional Raspberry Pi 4 edge-audio hosts.

---

# 2. Operating System

Known-good host:

```text
Debian GNU/Linux 13 (Trixie)
64-bit
```

Verify:

```bash
cat /etc/os-release
```

Expected:

```text
PRETTY_NAME="Debian GNU/Linux 13 (trixie)"
NAME="Debian GNU/Linux"
VERSION_ID="13"
```

The Raspberry Pi repository is enabled:

```text
http://archive.raspberrypi.com/debian
```

---

# 3. Base System Update

Update the system:

```bash
sudo apt update
sudo apt upgrade -y
```

Install audio utilities:

```bash
sudo apt install -y \
    alsa-utils \
    sox
```

`alsa-utils` provides:

- `arecord`
- `aplay`
- `alsamixer`

`sox` is used for WAV/audio analysis.

Install Raspberry Pi utilities:

```bash
sudo apt install raspi-utils
```

Note: on Debian Trixie, `raspi-gpio` was not available as a command on the configured system. `pinctrl` is available instead.

---

# 4. Docker Installation

Docker was installed using the Docker Debian repository.

Repository:

```text
https://download.docker.com/linux/debian
```

Target distribution:

```text
trixie
```

Required Docker components:

```text
docker-ce
docker-ce-cli
containerd.io
docker-buildx-plugin
docker-compose-plugin
```

Verify:

```bash
docker --version
docker compose version
```

Enable and start Docker:

```bash
sudo systemctl enable docker
sudo systemctl start docker
```

Verify:

```bash
sudo systemctl status docker
```

Allow the normal user to run Docker:

```bash
sudo usermod -aG docker $USER
```

Log out/in or reboot after changing group membership.

Test:

```bash
docker run hello-world
```

---

# 5. Raspberry Pi I2S Configuration

Edit:

```bash
sudo nano /boot/firmware/config.txt
```

Required settings:

```ini
dtparam=i2c_arm=on
dtparam=i2s=on
dtparam=audio=on
```

The original configuration contained:

```ini
#dtparam=i2s=on
```

This was changed to:

```ini
dtparam=i2s=on
```

I2S must be enabled for the INMP441 microphone.

---

# 6. Google Voice HAT Audio Overlay

The working Raspberry Pi uses the Raspberry Pi-provided Google Voice HAT sound-card overlay.

Verify that the overlay exists:

```bash
ls -l /boot/firmware/overlays/googlevoicehat-soundcard.dtbo
```

Add the overlay to:

```text
/boot/firmware/config.txt
```

```ini
dtoverlay=googlevoicehat-soundcard
```

The relevant configuration should contain approximately:

```ini
dtparam=i2c_arm=on
dtparam=i2s=on
#dtparam=spi=on

dtparam=audio=on

...

dtoverlay=vc4-kms-v3d
dtoverlay=googlevoicehat-soundcard
```

Reboot:

```bash
sudo reboot
```

---

# 7. Verify Audio Hardware

After reboot:

```bash
cat /proc/asound/cards
```

Known-good host showed:

```text
0 [vc4hdmi0       ]: vc4-hdmi - vc4-hdmi-0
                    vc4-hdmi-0
1 [vc4hdmi1       ]: vc4-hdmi - vc4-hdmi-1
                    vc4-hdmi-1
2 [Headphones     ]: bcm2835_headpho - bcm2835 Headphones
                    bcm2835 Headphones
3 [sndrpigooglevoi]: RPi-simple - snd_rpi_googlevoicehat_soundcar
                    snd_rpi_googlevoicehat_soundcard
```

Then:

```bash
arecord -l
```

Known-good capture device:

```text
**** List of CAPTURE Hardware Devices ****
card 3: sndrpigooglevoi [snd_rpi_googlevoicehat_soundcar],
device 0: Google voiceHAT SoundCard HiFi voicehat-hifi-0
```

This established the original working ALSA device as:

```text
hw:3,0
```

and the working ALSA conversion interface as:

```text
plughw:3,0
```

---

# 8. INMP441 Microphone

The microphone module is an:

```text
AITRIP INMP441 Omnidirectional Microphone
```

The module pins are:

```text
L/R
WS
SCK
SD
VDD
GND
```

## 8.1 Wiring

| INMP441 | Raspberry Pi 4 | GPIO |
|---|---:|---:|
| VDD | Pin 1 | 3.3V |
| GND | Ground | GND |
| SCK | Pin 12 | GPIO18 |
| WS | Pin 35 | GPIO19 |
| SD | Pin 38 | GPIO20 |
| L/R | Ground | Left channel |

Important:

```text
L/R -> GND
```

selects the left I2S channel.

Moving L/R to 3.3V selects the right channel. It does not increase microphone gain or sensitivity.

---

# 9. I2S GPIO Assignment

The working pin assignment is:

```text
GPIO18 / Physical Pin 12 = I2S SCK
GPIO19 / Physical Pin 35 = I2S WS / LRCLK
GPIO20 / Physical Pin 38 = I2S SD
```

The microphone uses:

```text
GPIO18 -> SCK
GPIO19 -> WS
GPIO20 -> SD
```

This pin group was selected because other GPIO hardware is using pins at the opposite end of the header.

---

# 10. ALSA Testing

Initial capture-device check:

```bash
arecord -l
```

Once the Google Voice HAT overlay is active, the capture device should appear.

## 10.1 Raw hardware test

```bash
arecord -D hw:3,0 \
    -f S32_LE \
    -r 48000 \
    -c 1 \
    -d 10 \
    test.wav
```

## 10.2 Stereo hardware test

```bash
arecord -D hw:3,0 \
    -f S32_LE \
    -r 48000 \
    -c 2 \
    -d 10 \
    stereo.wav
```

Separate channels:

```bash
sox stereo.wav left.wav remix 1
sox stereo.wav right.wav remix 2
```

Analyze:

```bash
sox left.wav -n stat
sox right.wav -n stat
```

Observed behavior:

```text
LEFT  = audio
RIGHT = zero
```

This confirmed that:

```text
L/R -> GND
```

is correct for the current configuration.

---

# 11. ALSA Hardware Parameters

Run:

```bash
arecord -D hw:3,0 --dump-hw-params
```

Known-good results included:

```text
ACCESS:  MMAP_INTERLEAVED RW_INTERLEAVED
FORMAT:  S32_LE
SUBFORMAT: STD MSBITS_MAX
SAMPLE_BITS: 32
FRAME_BITS: 64
CHANNELS: 2
RATE: 48000
```

Important:

```text
Format:       S32_LE
Sample rate:  48000 Hz
Hardware channels: 2
```

The application uses the useful left channel as mono.

---

# 12. Validated `plughw` Capture

The most successful manual capture command was:

```bash
arecord -D plughw:3,0 \
    -f S32_LE \
    -r 48000 \
    -c 1 \
    -d 10 \
    mic.wav
```

Analyze:

```bash
sox mic.wav -n stat
```

One successful test produced approximately:

```text
Maximum amplitude:     0.225130
Minimum amplitude:    -0.184471
RMS amplitude:         0.002620
```

This confirmed that the INMP441 was producing valid digital audio.

The microphone was relatively quiet but clean, with no significant hiss.

A loud cough approximately 18 inches from the microphone registered only around 9% on the level measurement.

The current development direction is therefore DSP processing and sensitivity/level optimization rather than replacing the microphone hardware.

Five INMP441 modules are currently available for testing.

---

# 13. Audio Processing Direction

The intended processing pipeline is:

```text
48 kHz / 32-bit capture
        |
        v
DC offset removal
        |
        v
80 Hz high-pass filter
        |
        v
Software gain / AGC
        |
        v
Limiter
        |
        v
Processed audio
```

Current initial processing configuration:

```yaml
processing:
  highpass_hz: 80
  gain_db: 20
  limiter_db: -3
```

The goal is far-field/environmental capture, not lapel-microphone use.

The microphone should therefore capture ambient audio at useful levels before downstream speech/event processing.

---

# 14. Edge-Audio Container

Service name:

```text
edge-audio
```

Repository structure:

```text
edge-audio/
+-- docker-compose.yml
+-- Dockerfile
+-- requirements.txt
+-- .env
+-- config/
|   +-- audio.yaml
+-- app/
|   +-- main.py
|   +-- config.py
|   +-- capture.py
|   +-- dsp.py
|   +-- recorder.py
+-- recordings/
|   +-- raw/
|   +-- processed/
+-- logs/
```

CI/CD has been established for the project.

---

# 15. Docker Compose

Current intended `docker-compose.yml`:

```yaml
services:
  edge-audio:
    build: .
    container_name: edge-audio
    restart: unless-stopped

    devices:
      - /dev/snd:/dev/snd

    group_add:
      - audio

    volumes:
      - ./config:/app/config:ro
      - ./recordings:/recordings
      - ./logs:/logs

    environment:
      AUDIO_CONFIG: /app/config/audio.yaml

    network_mode: host
```

The critical audio access configuration is:

```yaml
devices:
  - /dev/snd:/dev/snd
```

The container also receives the host `audio` group:

```yaml
group_add:
  - audio
```

---

# 16. Container Configuration

Current `config/audio.yaml`:

```yaml
capture:
  device: plughw:3,0
  sample_rate: 48000
  channels: 1
  dtype: int32
  chunk_seconds: 10

processing:
  highpass_hz: 80
  gain_db: 20
  limiter_db: -3

output:
  raw_path: /recordings/raw
  processed_path: /recordings/processed

logging:
  level: INFO
```

Note: `plughw:3,0` is currently a known-good device identifier on the original Pi, but it should not be considered a permanent multi-host identifier.

---

# 17. Dockerfile

Current intended Dockerfile:

```dockerfile
FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1

RUN apt-get update && apt-get install -y \
    alsa-utils \
    libsndfile1 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .

RUN pip install --no-cache-dir -r requirements.txt

COPY app ./app
COPY config ./config

CMD ["python3", "-u", "app/main.py"]
```

---

# 18. Python Dependencies

Current `requirements.txt`:

```text
numpy
scipy
soundfile
PyYAML
```

The original prototype used:

```text
sounddevice
```

but it was removed.

Reason:

`sounddevice` uses PortAudio and does not directly accept the ALSA PCM identifier:

```text
plughw:3,0
```

The validated container architecture therefore uses `arecord` directly.

---

# 19. Container Capture Architecture

Current capture path:

```text
Python
   |
   v
subprocess
   |
   v
arecord
   |
   v
ALSA
   |
   v
plughw:3,0
   |
   v
/dev/snd
   |
   v
Google Voice HAT sound-card driver
   |
   v
I2S
   |
   v
INMP441
```

This intentionally avoids PortAudio/PyAudio.

---

# 20. Container Capture Implementation

The capture implementation uses `arecord` directly.

The important command generated by the application is equivalent to:

```bash
arecord -q \
    -D plughw:3,0 \
    -t raw \
    -f S32_LE \
    -r 48000 \
    -c 1 \
    -d 10
```

The resulting raw PCM data is converted in Python using NumPy:

```text
S32_LE -> little-endian signed 32-bit integer
```

This matches the validated ALSA hardware format.

---

# 21. Container Testing

Build:

```bash
docker compose build
```

After dependency or Dockerfile changes:

```bash
docker compose build --no-cache
```

Start:

```bash
docker compose up
```

Interactive container test:

```bash
docker compose run --rm edge-audio bash
```

Inside the container:

```bash
arecord -l
```

Then:

```bash
arecord -D plughw:3,0 \
    -f S32_LE \
    -r 48000 \
    -c 1 \
    -d 5 \
    test.wav
```

Check:

```bash
ls -lh test.wav
```

If SoX is installed in the test environment:

```bash
sox test.wav -n stat
```

---

# 22. Original Container Failure and Resolution

The original Python implementation used `sounddevice`:

```python
sd.rec(
    ...
    device="plughw:3,0"
)
```

It failed with:

```text
ValueError: No input device matching 'plughw:3,0'
```

Reason:

```text
plughw:3,0
```

is an ALSA PCM identifier, not a PortAudio device name.

Resolution:

- Remove `sounddevice`.
- Remove PortAudio from the image.
- Use `arecord` directly from Python.
- Keep ALSA as the audio abstraction layer.

This matches the manually validated host capture path.

---

# 23. Second Pi Deployment Issue

A second Raspberry Pi 4 was brought online as a container target.

Before the microphone was moved to it, the container reported:

```text
ALSA lib confmisc.c:165:(snd_config_get_card) Cannot get card index for 3
arecord: main:850: audio open error: No such file or directory
```

This means:

```text
ALSA card 3 does not exist on the second Pi.
```

This is a host audio configuration issue, not a microphone failure.

The second Pi needs:

```ini
dtparam=i2s=on
dtparam=audio=on
dtoverlay=googlevoicehat-soundcard
```

in:

```text
/boot/firmware/config.txt
```

Then reboot:

```bash
sudo reboot
```

Verify:

```bash
cat /proc/asound/cards
```

and:

```bash
arecord -l
```

The microphone does not have to be physically connected for the sound-card overlay/device to appear.

---

# 24. Important Multi-Host Configuration Issue

Do not permanently depend on:

```text
plughw:3,0
```

ALSA card numbers are assigned by the host and are not guaranteed to remain identical across Raspberry Pi installations.

For example:

```text
Host A -> card 3
Host B -> card 1
```

could both be valid configurations.

The next architecture improvement should be to use a stable ALSA card/device name or host-specific device discovery rather than hard-coding:

```text
plughw:3,0
```

in `audio.yaml`.

The current `plughw:3,0` value should therefore be considered:

```text
KNOWN-GOOD DEVELOPMENT CONFIGURATION
```

rather than:

```text
PERMANENT PRODUCTION CONFIGURATION
```

---

# 25. Known-Good Baseline

## Host

```text
Raspberry Pi 4
Debian GNU/Linux 13 (Trixie)
64-bit
Docker Engine
Docker Compose Plugin
```

## Audio

```text
I2S enabled
Google Voice HAT sound-card overlay
ALSA
INMP441 digital MEMS microphone
```

## GPIO

```text
GPIO18 / Pin 12 = SCK
GPIO19 / Pin 35 = WS
GPIO20 / Pin 38 = SD
```

## Microphone

```text
VDD = 3.3V
GND = GND
L/R = GND
```

## Capture

```text
48 kHz
S32_LE
Mono application stream
ALSA plughw interface
```

## Known-good host device

```text
plughw:3,0
```

## Container

```text
edge-audio
/dev/snd mapped into container
arecord used for ALSA capture
Python DSP pipeline
Raw + processed WAV output
```

## DSP

```text
DC offset removal
80 Hz high-pass
Software gain
-3 dB limiter
```

## Current status

```text
I2S capture:              PROVEN
INMP441 operation:        PROVEN
Docker ALSA access:       PROVEN on original host
Container capture:        IMPLEMENTED
Ambient audio:            TOO QUIET for desired far-field use
DSP tuning:               CURRENT DEVELOPMENT FOCUS
Additional microphones:   NOT CURRENTLY PLANNED
Hardware replacement:     NOT CURRENTLY PLANNED
```

---

# 26. Recommended Next Steps

1. Complete host configuration on the second Pi.
2. Verify its ALSA capture device.
3. Do not assume the ALSA card number is `3`.
4. Establish a stable ALSA device identifier.
5. Update `audio.yaml` to use the stable identifier.
6. Move/connect an INMP441 to the second Pi.
7. Verify raw capture from the container.
8. Tune DSP gain/AGC for far-field ambient capture.
9. Add level/VU telemetry.
10. Add VAD.
11. Add chunk metadata.
12. Add SHA-256 evidence hashing.
13. Add event publishing/integration with the broader edge/evidence architecture.
