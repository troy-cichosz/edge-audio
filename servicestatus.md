# edge-audio — Service Status

**Purpose:** Current development phase and maturity of the edge-audio service.  
**Status:** Working MVP / active refinement  
**Last reviewed:** September 2026

## Current Phase

**Phase 1 — Evidence-Facing Temporal Integration: COMPLETE / VERIFIED**

The service has a working local-first audio capture pipeline and has completed integration with local `edge-time` Capture Time Context.

## Verified Capabilities

- Raspberry Pi audio capture
- 48 kHz, two-channel operation
- Raw and processed WAV recording
- Per-recording metadata
- DC-offset removal, high-pass filtering, per-channel enable/disable, gain, and limiting
- Generic controller registration and configuration retrieval/merge
- Controller-managed calibration measurement and result workflow
- Controller GUI calibration initiation/result display
- Capture Time Context acquisition immediately before recording
- Local capture continuity during temporary controller unavailability

## Temporal Integration

Before each recording, the service obtains Capture Time Context directly from node-local `edge-time`. The context is retained with capture metadata and preserves timing source, freshness, uncertainty, synchronization/consistency state, authority information where available, and attestation reference.

Failure to obtain context does not stop local capture; the unavailable condition is recorded.

This integration does not claim exact physical microphone-sample exposure time or GPS/PPS authority.

## Current Calibration Position

Calibration measurement is operational. The next refinement is operator-controlled calibration adjustment through the existing controller configuration mechanism.

Recommendations must account for target level, headroom, limiter behavior, clipping, channel characteristics, and test conditions. Calibration changes affect subsequent captures and must not modify finalized raw evidence.

## Evidence Position

Raw and processed audio remain separate. Evidence-oriented metadata preserves capture identity, configuration, calibration/timing information, and hashes where implemented. Common evidence-model integration remains platform work.

## Remaining Service Work

- GUI-driven calibration adjustment
- Clear configuration lifecycle for saved calibration changes
- Evidence-integrity hardening
- Alignment with the common evidence model
- Later stronger authoritative timing integration

Detailed future capabilities belong in `wishlist.md`; active work belongs in `sprintstatus.md`.
