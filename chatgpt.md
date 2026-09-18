# edge-audio — ChatGPT Development Context

## Purpose

`edge-audio` is the Raspberry Pi audio capture service for the AI Legal Edge platform.

It is a containerized, local-first audio acquisition service intended to run on Raspberry Pi 4 nodes with I2S microphone hardware. It captures evidentiary audio locally, generates raw and processed recordings, records per-capture metadata, and integrates with `edge-controller` for node/service registration, configuration, status, and calibration.

The service is one component of the larger Edge platform. A node is expected to host multiple independent services; `edge-audio` must not be treated as the controller's only service.

---

# GitHub access
If there are issues using the API to pull from the public code base, always try to access any files via direct access/links for reference. 
GitHub public repos will ALWAYS be up to date on builds/commits. 

---

# Current Development State

## Repository / Source of Truth

The user's active working tree is:

```text
D:\src\edge-audio
```

The repository is maintained through the user's ADO workflow and successfully pushed/released to GitHub.

The active Git branch observed during this development cycle was:

```text
develop
```

At the point immediately before this handoff, the working tree contained a modification to:

```text
edge-audio/app/controller.py
```

The user intends to commit the current working state to ADO master/develop workflow because the current implementation is working sufficiently for this development checkpoint. That commit will update the GitHub codebase through the existing workflow.

Do not assume that a stale GitHub `public` branch view represents the user's current local `develop` source.

---

# Verified Hardware

Current Raspberry Pi nodes:

```text
pi4nVME
pi4SSD
```

Audio hardware is an I2S microphone configuration using the Raspberry Pi audio subsystem.

The currently working capture device is:

```text
plughw:3,0
```

Current capture parameters verified in runtime logs:

```text
Sample rate: 48000 Hz
Channels: 2
```

The service is successfully capturing audio on the Pi.

---

# Verified Runtime State

The edge-audio container name is:

```text
edge-audio-edge-audio-1
```

Do NOT assume the generic name `edge-audio`.

The controller API container is:

```text
edge-controller-controller-api-1
```

The controller PostgreSQL container is:

```text
edge-controller-postgres
```

The controller is running on:

```text
spoo-lin
```

Controller endpoint:

```text
http://spoo-lin.spoocannon.com:8080
```

The edge-audio container currently has:

```text
EDGE_CONTROLLER_URL=http://spoo-lin.spoocannon.com:8080
EDGE_CONTROLLER_TIMEOUT=5
EDGE_SERVICE_ID=edge-audio
EDGE_SERVICE_NAME=edge-audio
EDGE_SERVICE_VERSION=0.0.1
AUDIO_CONFIG=/app/config/audio.yaml
```

---

# Controller Connectivity

A transient controller outage was observed.

At startup the audio service logged:

```text
Controller registration failed: <urlopen error [Errno 111] Connection refused>
Controller configuration unavailable: <urlopen error [Errno 111] Connection refused>
```

The calibration worker still started and the audio capture service continued operating.

After the controller became available again, connectivity was verified directly from inside the audio container:

```text
GET http://spoo-lin.spoocannon.com:8080/health
STATUS 200
{"status":"ok"}
```

The pending calibration endpoint was also verified:

```text
GET http://spoo-lin.spoocannon.com:8080/api/v1/nodes/pi4nVME/calibration/pending?service_id=edge-audio
STATUS 200
null
```

Therefore:

* Controller DNS works.
* TCP connectivity works.
* HTTP connectivity works.
* `/health` works.
* The generic node/service API is reachable.
* Calibration polling works.
* Temporary controller unavailability does not prevent local audio capture.

This behavior is desirable for the local-first architecture.

---

# Audio Capture

The service is successfully producing captures continuously.

Example runtime output:

```text
RAW     left Peak 2147483616.0000 RMS 224827168.3588
RAW     right Peak 128277504.0000 RMS 4223333.6216

PROCESSED left Peak 0.7079 RMS 0.0857
PROCESSED right Peak 0.0589 RMS 0.0013

Saved capture: 20260901_134339

Raw:
 /recordings/raw/pi4nVME_20260901_134339.wav

Processed:
 /recordings/processed/pi4nVME_20260901_134339.wav

Metadata:
 /metadata/pi4nVME_20260901_134339.json
```

Subsequent captures were also successfully produced.

The service is therefore beyond basic startup testing: sustained recording, processing, output generation, and metadata generation are working.

---

# Audio Processing

The configuration model supports:

## Capture

```yaml
capture:
  device:
  sample_rate:
  channels:
  chunk_seconds:
```

## Processing

```yaml
processing:
  highpass_hz:
  limiter_db:
```

## Per-channel configuration

Each channel supports:

```yaml
channels:
  - id:
    name:
    enabled:
    gain_db:
```

The current DSP implementation:

1. Removes DC offset independently per channel.
2. Applies the configured high-pass filter.
3. Applies per-channel enabled/disabled state.
4. Applies per-channel gain in dB.
5. Applies the limiter.

The DSP gain calculation is:

```text
multiplier = 10 ** (gain_db / 20)
```

This is already the mechanism that the future GUI calibration workflow should control.

---

# Current Audio Configuration

The container contains:

```text
/app/config/audio.yaml
```

The current configuration structure includes:

```yaml
capture:
  channels: 2

channels:
  - id: 0
    name: left
    ...
    gain_db: 0

  - id: 1
    name: right
    ...
    gain_db: 0

processing:
  highpass_hz: 80
  limiter_db: -3
```

Do not redesign this configuration model unless there is a demonstrated requirement to do so.

The service already has the correct abstraction for controller-provided configuration overrides.

---

# Controller Configuration Integration

`edge-audio/app/controller.py` already implements:

```text
get_configuration()
```

The service obtains configuration from:

```text
GET /api/v1/nodes/{node_id}/services/{service_id}/configuration
```

The main application:

1. Loads the local `audio.yaml`.
2. Retrieves controller configuration.
3. Recursively merges controller overrides into the local configuration.
4. Validates the resulting configuration.
5. Uses the resulting configuration to construct capture/DSP runtime behavior.

This is important:

## The controller configuration mechanism already exists.

The next calibration GUI work should therefore use this mechanism rather than creating a second configuration system.

---

# Calibration

Calibration is now working end-to-end.

The controller has a generic calibration job model and API.

## Create calibration

Correct route:

```text
POST
/api/v1/nodes/{node_id}/services/{service_id}/calibration
```

Request:

```json
{
  "duration_seconds": 10
}
```

Valid duration:

```text
1–60 seconds
```

An earlier attempted route:

```text
/api/v1/nodes/{node_id}/calibration
```

returned:

```json
{
  "detail": "Not Found"
}
```

That was not a code failure; it was simply the wrong route.

---

# Calibration Worker

`edge-audio` polls:

```text
GET
/api/v1/nodes/{node_id}/calibration/pending?service_id=edge-audio
```

The controller changes the job from:

```text
pending
```

to:

```text
running
```

when the edge service claims it.

The edge-audio calibration worker then captures the requested duration and submits the result through:

```text
POST
/api/v1/nodes/{node_id}/calibration/{calibration_id}/result
```

The completed job is persisted by `edge-controller`.

---

# Verified Calibration Job

A real calibration job completed successfully:

```text
Calibration job:
66ec14f3-d9b4-4293-aaf2-0276273d052c
```

Result:

```text
status = complete
duration_seconds = 10
frames = 480000
channels = 2
```

Channel 0:

```text
peak       = 2147474400.0
rms        = 193818294.45557857
peak_dbfs  = -0.0000374053
rms_dbfs   = -20.8907019599
dc_offset  = -8990753.069583334
clipping   = 0
```

Channel 1:

```text
peak       = 130127904.0
rms        = 7434927.567453671
peak_dbfs  = -24.3511886204
rms_dbfs   = -49.2130624738
dc_offset  = -593733.2313333333
clipping   = 0
```

The calibration API returned:

```json
{
  "status": "complete",
  "duration_seconds": 10,
  "result": "...",
  "error": null
}
```

Therefore calibration is not merely theoretical or partially implemented. The complete workflow has been demonstrated against real hardware.

---

# Important Calibration Observation

The measured RMS levels showed a very large channel imbalance:

```text
Left RMS:  -20.89 dBFS
Right RMS: -49.21 dBFS

Difference: approximately 28.32 dB
```

The raw peak values show the same basic imbalance.

The left channel is essentially at the digital full-scale ceiling while the right channel is substantially lower.

However:

## Do NOT automatically apply +28.32 dB to the right channel yet.

The correct GUI behavior needs to account for:

* target calibration level
* peak headroom
* limiter threshold
* clipping
* current gain
* channel imbalance
* whether calibration is intended to equalize channels or establish absolute recording level
* whether the microphone hardware itself has different sensitivity
* whether the current test signal represents the desired calibration source

The GUI should recommend adjustments rather than blindly applying measured differences.

---

# Current Controller Calibration GUI

The controller already has a service-specific calibration section for:

```text
edge-audio
```

Current GUI functionality:

* Select calibration duration.
* Default duration = 10 seconds.
* Minimum = 1 second.
* Maximum = 60 seconds.
* Start calibration.
* Poll the calibration job.
* Display pending/running/complete/failed state.
* Display calibration results.
* Display per-channel:

  * peak
  * RMS
  * peak dBFS
  * RMS dBFS
  * DC offset
  * clipping samples

The GUI currently performs measurement/reporting.

It does NOT yet provide the desired complete calibration-control workflow.

---

# Immediate Development Goal

The next major feature is:

## GUI-based audio calibration and adjustment.

The GUI should become capable of:

1. Starting a calibration measurement.
2. Showing the measured channel characteristics.
3. Showing the current configured channel settings.
4. Providing editable per-channel gain.
5. Providing channel enable/disable controls where appropriate.
6. Providing a calculated/recommended gain adjustment.
7. Allowing the operator to accept or modify the recommendation.
8. Saving the resulting configuration through the existing controller configuration API.
9. Showing the saved/applied configuration.
10. Allowing another calibration run to verify the adjustment.

The workflow should be iterative:

```text
Measure
   ↓
Analyze
   ↓
Recommend
   ↓
Operator adjusts/accepts
   ↓
Save controller configuration
   ↓
edge-audio retrieves configuration
   ↓
Audio processing uses configuration
   ↓
Measure again
   ↓
Verify
```

---

# Existing Configuration API

`edge-controller` already exposes:

```text
GET
/api/v1/nodes/{node_id}/services/{service_id}/configuration
```

and:

```text
PUT
/api/v1/nodes/{node_id}/services/{service_id}/configuration
```

The PUT payload is:

```json
{
  "configuration": {}
}
```

The existing `ServiceConfiguration` model persists the configuration in PostgreSQL.

Use this API for GUI-controlled audio settings.

Do not create a new calibration-specific configuration persistence mechanism unless necessary.

---

# Configuration Architecture

The intended architecture is:

```text
edge-controller
      |
      | persisted service configuration
      v
ServiceConfiguration
      |
      | GET configuration
      v
edge-audio ControllerClient
      |
      | recursive merge
      v
local audio.yaml + controller overrides
      |
      v
validated runtime configuration
      |
      +--> capture
      |
      +--> DSP
             |
             +--> channel enabled
             +--> channel gain_db
             +--> high-pass
             +--> limiter
```

This is already substantially implemented.

---

# Generic Multi-Service Architecture

The controller is deliberately generic.

The node model supports multiple services.

Do not hard-code the controller GUI around `edge-audio`.

`edge-video` follows the same generic node/service architecture.

The current `edge-video` repository documents:

```text
POST /api/v1/nodes
POST /api/v1/nodes/{node_id}/services
GET /api/v1/nodes/{node_id}/services/{service_id}/configuration
PUT /api/v1/nodes/{node_id}/services/{service_id}/status
```

and explicitly preserves the multi-service-per-node model.

Therefore future controller GUI work should remain generic wherever possible, with service-specific controls only where a service exposes service-specific capabilities.

---

# Relationship to edge-video

`edge-video` establishes the broader Edge platform pattern:

* Raspberry Pi edge acquisition.
* Containerized service.
* Local-first evidence.
* Controller registration.
* Generic node/service API.
* Configurable runtime.
* Local evidence storage.
* Future server-side processing.
* GPS/PPS-based authoritative timing later.
* AI analysis consuming immutable/read-only evidence copies.

The video service currently uses Raspberry Pi CSI cameras through `rpicam`/libcamera, hardware H.264 encoding, segmented evidence files, SHA-256 hashing, JSON manifests, and explicit timestamp-quality metadata.

The audio service should follow the same overall philosophy.

---

# Evidence / Legal Architecture Implications

Audio recordings are intended to become evidence for the AI Legal platform.

Therefore future development should preserve:

* original/raw recording
* processed derivative
* metadata
* capture timestamp
* node identity
* service identity
* configuration used
* calibration state where relevant
* cryptographic hashes
* immutable/append-only evidence semantics

Do not modify an already-finalized raw evidence recording as part of calibration.

Calibration affects subsequent processing/configuration.

It should not retroactively alter existing evidence.

This mirrors the `edge-video` design where finalized evidence is not modified and downstream AI analysis consumes a read-only copy/replica.

---

# Timing

Current edge-audio timestamps should not be considered GPS-authoritative.

The broader platform currently has an `edge-gps` service intended to provide authoritative timing later.

The edge-video design explicitly uses:

```text
clock_source: system
time_quality: unsynchronized
gps_authority: false
```

until GPS/PPS is available.

The same conceptual model should eventually apply to audio evidence.

Do not claim synchronized/legal-grade time merely because the system clock contains UTC timestamps.

---

# Current Service Files

The running container contains:

```text
/app/app/calibration.py
/app/app/capture.py
/app/app/config.py
/app/app/controller.py
/app/app/dsp.py
/app/app/health.py
/app/app/main.py
/app/app/publisher.py
/app/app/recorder.py
/app/app/util.py
/app/config/audio.yaml
/app/requirements.txt
```

Important components:

### `controller.py`

Handles:

* controller connectivity
* registration
* configuration retrieval
* calibration polling
* calibration result submission

### `config.py`

Handles:

* local configuration loading
* validation
* backward compatibility
* channel configuration normalization

### `capture.py`

Handles:

* ALSA capture
* sample rate
* channels
* chunking

### `dsp.py`

Handles:

* DC removal
* high-pass filtering
* per-channel enable
* per-channel gain
* limiting

### `calibration.py`

Handles:

* calibration capture
* channel statistics
* peak
* RMS
* dBFS
* DC offset
* clipping detection
* calibration result generation

### `recorder.py`

Handles recording output.

### `main.py`

Coordinates:

* configuration
* controller configuration
* capture
* DSP
* recording
* metadata
* calibration worker
* service startup

---

# Current Failure/Recovery Behavior

Controller failure does not prevent the audio service from starting.

Observed sequence:

```text
controller unavailable
    ↓
registration fails
configuration unavailable
    ↓
calibration worker starts
    ↓
audio capture starts
    ↓
recording continues
    ↓
controller becomes available
    ↓
pending-calibration polling succeeds
```

This is an important property and should be preserved.

A controller outage must not make local evidence capture unavailable.

---

# Next Development Phases

## Phase 1 — GUI Calibration Controls

Immediate priority.

Add to the existing calibration UI:

* current configuration display
* per-channel gain controls
* enable/disable controls
* recommended adjustment
* save/apply configuration
* configuration save status
* distinction between measured and configured values
* re-run calibration workflow

Do not yet introduce unnecessary new infrastructure.

---

## Phase 2 — Calibration Intelligence

Improve the calibration algorithm.

Potential outputs:

```text
measured RMS
measured peak
target RMS
target peak
recommended gain
post-gain predicted peak
headroom
clipping risk
channel balance
```

The algorithm should explicitly account for the limiter and available headroom.

The operator must be able to override the recommendation.

---

## Phase 3 — Calibration Profiles

Eventually support persistent calibration metadata such as:

```text
microphone identity
node identity
channel identity
calibration timestamp
calibration duration
test conditions
measured values
applied gains
operator-selected values
resulting configuration
```

This is particularly important for evidentiary reproducibility.

---

## Phase 4 — Runtime Configuration Refresh

Current configuration retrieval occurs as part of service startup/configuration handling.

Future work should determine whether audio settings should be:

* restart-required,
* periodically refreshed,
* explicitly reloaded,
* or dynamically applied.

For safety and predictability, do not implement live DSP mutation until the configuration lifecycle is clearly defined.

A GUI "Save" operation should not falsely imply that a currently running capture process has immediately changed if the service only reads configuration at startup.

---

## Phase 5 — Evidence Integrity

Add/verify:

* SHA-256 hashing
* immutable metadata
* configuration snapshot per recording
* calibration state in metadata
* clock quality
* future GPS/PPS authority
* append-only evidence semantics

This should eventually align audio evidence with the video evidence model.

---

## Phase 6 — Platform Integration

Integrate audio and video into the broader Edge evidence architecture:

```text
edge-audio
edge-video
edge-gps
     |
     v
edge-controller
     |
     v
AI Legal evidence / analysis platform
```

Later stages can add:

* centralized evidence ingestion
* server-side verification
* retention
* event markers
* synchronized multimodal timestamps
* AI analysis workers
* speech STT
* speaker/channel analysis
* incident/event correlation

---

# Do Not Do Yet

Do not prematurely implement:

* server-side media gateways
* cloud storage
* external AI APIs
* dynamic Kubernetes deployment
* complex distributed messaging
* automatic blind gain correction
* automatic modification of raw evidence
* GPS-authoritative claims
* complicated calibration databases
* a second configuration persistence system

The current architecture already provides enough infrastructure to finish the next useful increment.

---

# Handoff Starting Point

When continuing this project in a new chat:

1. Treat the committed/pushed current `edge-audio` source as the baseline.
2. Verify the current local `develop` tree before changing code.
3. Do not assume the GitHub `public` branch is equivalent to local `develop`.
4. Preserve the existing controller configuration API.
5. Preserve generic multi-service controller architecture.
6. Preserve local-first capture behavior.
7. Preserve the working calibration job workflow.
8. Implement GUI adjustment on top of the existing configuration mechanism.
9. Test against `pi4nVME` first.
10. Then verify `pi4SSD`.
11. Build and deploy through the existing ADO/container release workflow.
12. Update documentation after verified behavior changes.

The immediate objective is **not to make calibration work**—that already works.

The immediate objective is to make the **existing working calibration system actually control and persist the audio configuration through the GUI, then verify the resulting audio behavior**.