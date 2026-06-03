# Learning State Guardian Integration

This document defines the optional Learning State Guardian bridge for `ROKID_Agent_Tutor`.

## Scope

- This bridge is an optional sidecar, not the default runtime path.
- It is designed to send image frames to an external Learning State Guardian Flask backend.
- Phase one is frame-only.
- Phase one does not include head pose or IMU.
- Phase one does not include a real Rokid SDK integration.
- Phase one does not claim that real Rokid deployment is already stable.

## Boundary

This bridge must stay separate from the repository's existing `academic_companion` guardian logic.

- Do not import `academic_companion.py` into the sidecar client.
- Do not treat this bridge as a replacement for the internal `academic_companion` guardian capability.
- Do not mix the two protocols or merge their response shapes.

## Feature Flag

The bridge is disabled by default and must be enabled explicitly:

```env
ENABLE_LSG_BRIDGE=false
LSG_BASE_URL=http://127.0.0.1:5000
LSG_TIMEOUT_SECONDS=0.8
```

Expected behavior:

- when `ENABLE_LSG_BRIDGE=false`, the client returns `None`
- when the external backend is unavailable, the client returns `None`
- when a request times out or fails, the client returns `None`
- the bridge must never break the existing Qwen, Speaking, or Academic Companion flows

## Current Behavior

The sidecar client is intentionally passive:

- it can build a multipart frame request
- it can best-effort send a frame to `/api/v1/rokid/frame`
- it can best-effort fetch `/status`
- it can build a compact learning-state summary from a status payload

It does not:

- modify the current WebSocket protocol
- change the existing `description|||question` parsing contract
- append learning-state text into existing message returns
- alter any agent routing behavior

## Future Hook Guidance

If the bridge is connected to a live path in the future, the safest first hook is:

- `Agent_Project/agents/Speaking_agent.py -> process_image()`

Even there, the first integration should remain:

- behind `ENABLE_LSG_BRIDGE=true`
- side-effect only
- warning-only on failure
- no protocol changes
- no response-shape changes

## Out Of Scope

The following are not part of the current integration step:

- real Rokid SDK access
- head pose / IMU forwarding
- automatic response augmentation
- Presentation Assistant integration

Presentation Assistant is out of scope because the current goal is only to prepare a safe, optional frame bridge to an external learning-state sensing prototype.
