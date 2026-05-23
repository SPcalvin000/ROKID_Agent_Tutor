# academic_companion Payload Examples

This file is a quick reference for sending requests to the single gateway-facing
`academic_companion` module.

The gateway still sees only one agent:

```json
{
  "agent_type": "academic_companion",
  "event_type": "state_update",
  "session_id": "demo_session_001",
  "timestamp": 1710000000000,
  "payload": {}
}
```

Inside `payload`, the module can auto-route to:

- `presentation`
- `reflection_coach`
- `learning_state_guardian`

## 1. Presentation Control

Device-style gesture payload:

```json
{
  "agent_type": "academic_companion",
  "event_type": "state_update",
  "session_id": "presentation_demo",
  "timestamp": 1710000000000,
  "payload": {
    "gesture": "swipe_right",
    "source": "rokid_glasses"
  }
}
```

This auto-normalizes to:

- capability: `presentation`
- operation: `presentation_control`
- action: `next_slide`

## 2. Presentation Intake

Assignment-style payload:

```json
{
  "agent_type": "academic_companion",
  "event_type": "state_update",
  "session_id": "presentation_demo",
  "timestamp": 1710000000000,
  "payload": {
    "operation": "intake",
    "assignment_text": "Title: Public Health Brief\nCourse: SOC220\nDuration: 4 minutes\nDeliverable: presentation",
    "apply_to_mission": true
  }
}
```

This auto-normalizes to:

- capability: `presentation`
- operation: `extract_intake`

## 3. Presentation Rehearsal

Transcript-style payload:

```json
{
  "agent_type": "academic_companion",
  "event_type": "state_update",
  "session_id": "presentation_demo",
  "timestamp": 1710000000000,
  "payload": {
    "transcript": "Today I want to explain the policy change and why it matters...",
    "duration_minutes": 4.8,
    "section_times": [
      { "section_id": "opening", "actual_seconds": 42 },
      { "section_id": "main_point", "actual_seconds": 96 },
      { "section_id": "example", "actual_seconds": 88 },
      { "section_id": "conclusion", "actual_seconds": 41 }
    ]
  }
}
```

This auto-normalizes to:

- capability: `presentation`
- operation: `record_rehearsal`

## 4. Reflection Capture

Short reflection payload without explicit capability:

```json
{
  "agent_type": "academic_companion",
  "event_type": "state_update",
  "session_id": "reflection_demo",
  "timestamp": 1710000000000,
  "payload": {
    "theme": "after-class reflection",
    "summary": "I understood the lecture but did not test recall.",
    "worked": "Writing margin notes helped me follow the structure.",
    "insight": "I need a retrieval step before I stop studying.",
    "next_action": "Write 3 recall questions after the next lecture."
  }
}
```

This auto-normalizes to:

- capability: `reflection_coach`
- operation: `capture_reflection`

## 5. Reflection Planning

```json
{
  "agent_type": "academic_companion",
  "event_type": "state_update",
  "session_id": "reflection_demo",
  "timestamp": 1710000000000,
  "payload": {
    "capability": "reflection_coach",
    "operation": "plan",
    "actions": [
      "Start each reading block with one prediction question.",
      "End each reading block with a 5-line recap."
    ]
  }
}
```

This auto-normalizes to:

- capability: `reflection_coach`
- operation: `plan_next_step`

## 6. Learning State Snapshot

Score-style payload from device or frontend:

```json
{
  "agent_type": "academic_companion",
  "event_type": "state_update",
  "session_id": "guardian_demo",
  "timestamp": 1710000000000,
  "payload": {
    "attention_score": 18,
    "fatigue_score": 84,
    "stress_score": 76,
    "task": "Revise summary notes",
    "progress": "halfway",
    "blocker": "message checking",
    "support": "Need a smaller checklist"
  }
}
```

This auto-normalizes to:

- capability: `learning_state_guardian`
- operation: `record_learning_state`

And derives levels like:

- `attention_score` -> `focus_level`
- `fatigue_score` -> `energy_level`
- `stress_score` -> `stress_level`

## 7. Learning State Signal

Device-event payload:

```json
{
  "agent_type": "academic_companion",
  "event_type": "difficulty_event",
  "session_id": "guardian_demo",
  "timestamp": 1710000000000,
  "payload": {
    "device_event_type": "look_away",
    "note": "looked away from work repeatedly",
    "severity": "medium"
  }
}
```

This auto-normalizes to:

- capability: `learning_state_guardian`
- challenge: `attention drift`

## 8. Session Review

Presentation review:

```json
{
  "agent_type": "academic_companion",
  "event_type": "session_review",
  "session_id": "presentation_demo",
  "timestamp": 1710000000000,
  "payload": {
    "scope": "mission"
  }
}
```

Reflection review:

```json
{
  "agent_type": "academic_companion",
  "event_type": "session_review",
  "session_id": "reflection_demo",
  "timestamp": 1710000000000,
  "payload": {
    "scope": "reflection"
  }
}
```

Learning-state review:

```json
{
  "agent_type": "academic_companion",
  "event_type": "session_review",
  "session_id": "guardian_demo",
  "timestamp": 1710000000000,
  "payload": {
    "scope": "learning"
  }
}
```

## 9. Text Chat

Presentation coaching:

```json
{
  "agent_type": "academic_companion",
  "event_type": "text_chat",
  "session_id": "presentation_demo",
  "timestamp": 1710000000000,
  "payload": {
    "message": "How should I fix the timing issue?"
  }
}
```

Reflection coaching:

```json
{
  "agent_type": "academic_companion",
  "event_type": "text_chat",
  "session_id": "reflection_demo",
  "timestamp": 1710000000000,
  "payload": {
    "capability": "reflection_coach",
    "message": "What is my next step from this reflection?"
  }
}
```

Learning-state coaching:

```json
{
  "agent_type": "academic_companion",
  "event_type": "text_chat",
  "session_id": "guardian_demo",
  "timestamp": 1710000000000,
  "payload": {
    "message": "How is my focus state right now?"
  }
}
```

## 10. Success Shape

Every successful module response stays compatible with the gateway:

```json
{
  "status": "success",
  "data": {
    "capability": "learning_state_guardian",
    "routing": {
      "capability": "learning_state_guardian",
      "event_type": "state_update",
      "operation": "record_learning_state"
    },
    "interface_contract": {
      "capability": "learning_state_guardian",
      "event_type": "state_update",
      "operation": "record_learning_state",
      "supported_event_types": [
        "text_chat",
        "state_update",
        "difficulty_event",
        "session_review"
      ],
      "supported_state_update_operations": [
        "record_focus_signal",
        "record_learning_state",
        "set_learning_context"
      ]
    }
  }
}
```

## 11. Error Shape

```json
{
  "status": "error",
  "message": "academic_companion failed to process ..."
}
```
