# edge-audio — Sprint Status

**Current sprint:** Calibration refinement / evidence integration preparation  
**Status:** ACTIVE  
**Development phase:** Phase 1 temporal integration complete

## Sprint Objective

Refine the controller-managed audio calibration workflow without creating a second configuration system, while preserving the completed edge-time integration.

## Completed

- Local-first audio capture
- Controller registration/configuration integration
- Generic calibration job workflow and real calibration measurement
- Controller GUI calibration measurement/result display
- Node-local edge-time Capture Time Context integration
- Controller outage tolerance during local capture

## Current Work

```
measure → review → recommend → operator adjustment
        → save controller configuration → capture
        → measure again → verify
```

The existing controller configuration API remains the persistence mechanism.

## Verification Requirements

Saved configuration must be retrievable and used according to the actual configuration lifecycle; recommendations must account for headroom/clipping/limiter behavior; raw evidence must remain untouched; relevant failure behavior must be understood; documentation must reflect verified behavior.

## Handoff

After calibration refinement, audio should participate in common evidence-model work alongside edge-video.
