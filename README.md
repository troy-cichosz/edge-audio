# edge-audio

Containerized Raspberry Pi audio capture service for the AI Legal Edge platform.

`edge-audio` provides local-first audio acquisition, processing, recording, metadata generation, controller integration, hardware calibration, and integration with the local `edge-time` service for capture-time context.

The service is designed to operate independently at the edge so a temporary controller/network outage does not prevent local audio capture.

## Current Status

**Working MVP / active development**

The current implementation has been tested on Raspberry Pi 4 nodes with a two-channel I2S microphone configuration.

Verified functionality includes:

* Raspberry Pi audio capture
* 48 kHz operation
* Two-channel capture
* Raw WAV recording
* Processed WAV recording
* Per-recording metadata
* DC-offset removal
* High-pass filtering
* Per-channel enable/disable
* Per-channel gain
* Limiting
* Controller registration
* Controller configuration retrieval
* Generic node/service integration
* Remote calibration job creation
* Calibration job polling
* Calibration measurement
* Calibration result submission
* Controller-side calibration result storage
* Controller GUI calibration initiation and result display
* Local edge-time Capture Time Context acquisition immediately before audio capture

The next development increment is extending the existing GUI calibration workflow so operators can review, adjust, save, and verify the audio configuration.

---

## Architecture

`edge-audio` is one service in the Edge platform.

The controller supports multiple services per node; `edge-audio` is not a special-case controller service.

```text
Raspberry Pi
    |
    +-- edge-audio
    |      |
    |      +-- ALSA/I2S capture
    |      +-- DSP
    |      +-- recording
    |      +-- metadata
    |      +-- calibration
    |      +-- local edge-time context
    |
    +-- edge-time
    |      |
    |      +-- capture-time context
    |      +-- source/freshness state
    |      +-- signed attestation reference
    |
    +-- future edge services
           |
           v
     edge-controller
           |
           v
     service configuration
```

The service follows the same generic node/service API model used by the other Edge services.

`edge-controller` remains the control/configuration plane. `edge-audio` obtains capture-time context directly from the `edge-time` service running on the hosting node; the controller is not used as a time broker.

---

## Audio Pipeline

The current processing path is:

```text
I2S microphone
      |
      v
ALSA capture
      |
      v
raw audio
      |
      +--> raw WAV
      |
      v
DC offset removal
      |
      v
high-pass filter
      |
      v
per-channel enable
      |
      v
per-channel gain
      |
      v
limiter
      |
      v
processed WAV
      |
      v
metadata + capture-time context
```

Raw recordings are retained separately from processed recordings.

Calibration measurements are performed against captured audio and report channel-level characteristics.

---

## Configuration

The local configuration file is:

```text
/app/config/audio.yaml
```

The configuration contains capture, processing, output, and per-channel settings.

Example structure:

```yaml
capture:
  device: plughw:3,0
  sample_rate: 48000
  channels: 2
  chunk_seconds: 1

channels:
  - id: 0
    name: left
    enabled: true
    gain_db: 0

  - id: 1
    name: right
    enabled: true
    gain_db: 0

processing:
  highpass_hz: 80
  limiter_db: -3
```

The exact deployed configuration may differ by hardware.

Do not assume the microphone device number is universal across Raspberry Pi nodes.

---

## Controller Configuration

`edge-audio` can retrieve service configuration from `edge-controller`.

```text
GET
/api/v1/nodes/{node_id}/services/{service_id}/configuration
```

Controller-provided configuration is recursively merged with the local configuration and validated before being used by the service.

Configuration can be persisted by the controller through:

```text
PUT
/api/v1/nodes/{node_id}/services/{service_id}/configuration
```

This allows the controller GUI to manage service configuration without modifying the container image or local configuration file.

---

## Calibration

Calibration is implemented as a controller-managed job.

### Create a calibration

```text
POST
/api/v1/nodes/{node_id}/services/{service_id}/calibration
```

Example:

```json
{
  "duration_seconds": 10
}
```

Supported duration:

```text
1–60 seconds
```

The edge service polls:

```text
GET
/api/v1/nodes/{node_id}/calibration/pending?service_id=edge-audio
```

The calibration worker captures the requested interval and reports:

* sample/frame count
* channel count
* peak
* RMS
* peak dBFS
* RMS dBFS
* DC offset
* clipping sample count

The result is returned through:

```text
POST
/api/v1/nodes/{node_id}/calibration/{calibration_id}/result
```

### Current GUI

The controller GUI currently supports:

* calibration duration selection
* starting a calibration
* calibration status polling
* completion/failure reporting
* per-channel calibration results

The next planned increment is GUI-based adjustment and persistence of per-channel audio configuration.

---

## Controller Failure Behavior

Local capture is intentionally not dependent on continuous controller availability.

If the controller is temporarily unavailable:

* registration may fail
* configuration retrieval may fail
* calibration polling may temporarily fail

but the audio service continues operating with its local configuration.

Once the controller becomes available again, normal controller communication resumes.

This local-first behavior is intentional.

---

## Edge-Time Capture Time Context

Before each audio recording, `edge-audio` attempts to obtain a Capture Time Context from the `edge-time` service running on the same host.

The request is made immediately before `audio.record()` and is protected by the same capture lock used by the calibration worker. This prevents calibration from acquiring the audio device between time-context acquisition and the actual recording operation.

The endpoint is:

```text
POST /time/context
```

The optional endpoint override is supplied through:

```text
EDGE_TIME_URL
```

and the request timeout through:

```text
EDGE_TIME_TIMEOUT
```

When `EDGE_TIME_URL` is empty or unset, `edge-audio` dynamically derives the local endpoint from the hosting node's hostname and the standard `edge-time` host port:

```text
http://<hosting-node-hostname>:8095
```

This is the normal deployment behavior and avoids hardcoding individual node hostnames. `EDGE_TIME_URL` remains available as an explicit override when a deployment requires a different reachable `edge-time` endpoint.

If an explicit `EDGE_TIME_URL` is used, it must reference the appropriate node hostname/address and exposed `edge-time` host port. Do not use an `edge-time` Docker service/container name as the URL. The audio container uses the host's exposed endpoint.

The returned context is retained in the capture metadata. It provides a correlation identifier and the edge-time acquisition state, including the capture UTC value, selected time source, uncertainty/freshness and synchronization state, authority/consistency information where available, and the signed attestation reference produced by `edge-time`.

If `edge-time` cannot be reached or returns invalid context, local audio capture continues. The metadata records:

```json
{
  "time_context": {
    "status": "unavailable",
    "reason": "edge-time Capture Time Context could not be acquired immediately before capture"
  }
}
```

The existing `capture.timestamp_utc` field is retained for compatibility, but it is not itself the authoritative timing record.

A Capture Time Context represents the time context acquired immediately before the recording operation. It does **not** prove the exact physical microphone-sample exposure time, external source truth, scene truth, or legal admissibility. Future work can correlate an evidence service's monotonic capture position with the physical acquisition path where that distinction is required.

`edge-time` remains responsible for time-source selection, freshness, synchronization/consistency state, and signed attestation. `edge-gps` remains responsible for GNSS hardware and observations that can feed authoritative timing into `edge-time`; GNSS/PPS hardware logic is not moved into `edge-audio`.

---

## Output

Typical runtime paths are:

```text
/recordings/raw/
    <node>_<timestamp>.wav

/recordings/processed/
    <node>_<timestamp>.wav

/metadata/
    <node>_<timestamp>.json
```

The exact host paths are deployment-specific.

Metadata records information associated with the capture, processing operation, and available capture-time context.

---

## Evidence Model

The service is intended to support the AI Legal platform's local-first evidence workflow.

Raw evidence and processed derivatives are kept separate.

Current evidence-oriented metadata includes:

* SHA-256 hashes for raw and processed audio artifacts
* capture identity and hostname
* processing configuration
* per-channel configuration and measurements
* local edge-time Capture Time Context when available
* timing source/freshness and uncertainty information supplied by edge-time
* synchronization/consistency state supplied by edge-time
* signed edge-time attestation reference when available

Future evidence hardening will include:

* immutable metadata
* configuration snapshots
* calibration state/history
* stronger append-only evidence handling
* correlation of evidence acquisition positions with physical capture timing
* GPS/PPS-derived authoritative timing through edge-time

Calibration must never modify previously finalized raw evidence.

Calibration affects subsequent capture/processing configuration.

The presence of a signed time attestation establishes integrity and continuity of the edge-time record; it does not independently prove external source truth, scene truth, or legal admissibility.

---

## Hardware

The tested audio capture target is a Raspberry Pi 4 using an I2S microphone interface. The current tested capture configuration is:

```text
ALSA device: plughw:3,0
Sample rate: 48000 Hz
Channels: 2
```

ALSA device numbering may differ between hosts. Keep hardware-specific values configurable.

---

## Controller Integration

The service uses the generic Edge controller API for:

```text
POST /api/v1/nodes
POST /api/v1/nodes/{node_id}/services
GET  /api/v1/nodes/{node_id}/services/{service_id}/configuration
PUT  /api/v1/nodes/{node_id}/services/{service_id}/status
```

Calibration adds:

```text
POST /api/v1/nodes/{node_id}/services/{service_id}/calibration
GET  /api/v1/nodes/{node_id}/services/{service_id}/calibration/{calibration_id}
GET  /api/v1/nodes/{node_id}/calibration/pending?service_id={service_id}
POST /api/v1/nodes/{node_id}/calibration/{calibration_id}/result
```

The service therefore participates in the same multi-service node architecture as the other Edge services.

Timing is intentionally outside the controller API path. `edge-audio` obtains local timing context directly from `edge-time`.

---

## Timing

The legacy audio capture timestamp remains based on the Raspberry Pi/system clock and must not be interpreted by itself as GPS/PPS-authoritative.

The current integration adds an `edge-time` Capture Time Context immediately before each recording. The context records the timing state selected by `edge-time`, including source, freshness, uncertainty, synchronization/consistency information, and an attestation reference when available.

When no explicit endpoint override is configured, the local `edge-time` endpoint is derived dynamically from the hosting node's hostname and standard host port 8095. This keeps node identity out of the service configuration while preserving an explicit `EDGE_TIME_URL` override for exceptional deployments.

The broader platform uses `edge-gps` for GNSS hardware/observations and `edge-time` for time-source selection and attestation. GPS/PPS authority is therefore represented through `edge-time` rather than by embedding GNSS logic in the audio service.

---

## Current Development Boundary

The local edge-time Capture Time Context integration is implemented and verified. The remaining audio work is focused on configuration/calibration refinement and later evidence-hardening work.

## Design Principles

`edge-audio` follows these principles:

1. **Local-first** — audio capture must continue when the controller is unavailable.
2. **Evidence preservation** — raw recordings are not modified by later processing or calibration.
3. **Controller-managed configuration** — persistent operational settings belong in the controller rather than being baked into container images.
4. **Generic service architecture** — nodes may host multiple services.
5. **Hardware-aware configuration** — device-specific values must remain configurable.
6. **Reproducibility** — capture, processing, configuration, calibration, and timing state should ultimately be recorded with the evidence.
7. **No cloud dependency** — the edge service is designed to operate locally.
8. **Direct local timing context** — evidence services obtain timing context from the local `edge-time` service rather than routing time through the controller.
9. **Dynamic node identity** — normal local service-to-service endpoints derive the hosting node identity from the runtime host rather than hardcoding individual node names.

---

## Related Edge Services

* `edge-controller` — node/service management, configuration, calibration jobs, and service status.
* `edge-time` — local time-source selection, capture-time context, synchronization/consistency state, and signed time attestations.
* `edge-video` — Raspberry Pi CSI camera evidence capture.
* `edge-gps` — GNSS hardware and observations that can feed authoritative timing into `edge-time`.

The `edge-video` service follows the same local-first and generic node/service architecture and uses immutable finalized evidence with accompanying metadata/manifests.

---