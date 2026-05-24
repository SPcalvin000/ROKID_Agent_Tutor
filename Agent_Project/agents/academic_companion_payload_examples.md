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

## 5A. Reflection Focus And Metadata

Use this when you want the reflection coach to remember the current theme,
the learner's own note, the next-session goal, and the preferred provider mode.

```json
{
  "agent_type": "academic_companion",
  "event_type": "state_update",
  "session_id": "reflection_demo",
  "timestamp": 1710000000000,
  "payload": {
    "capability": "reflection_coach",
    "operation": "set_reflection_focus",
    "focus_theme": "switching during review",
    "target_habit": "stay on one source for two minutes",
    "current_course": "Biology",
    "learner_note": "I panic-switch when load rises.",
    "next_goal": "Finish one page before opening another source.",
    "provider_override": "heuristic"
  }
}
```

This keeps the reflection review anchored around:

- `focus_theme`
- `target_habit`
- `learner_note`
- `next_goal`
- `provider_override`

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

## 7. Learning State Sensor Snapshot

Low-level posture or scene-style payload:

```json
{
  "agent_type": "academic_companion",
  "event_type": "state_update",
  "session_id": "guardian_sensor_demo",
  "timestamp": 1710000000000,
  "payload": {
    "task_mode": "review",
    "current_task": "Review problem set solutions",
    "orientation_drift": 61,
    "movement_intensity": 43,
    "combined_drift": 58,
    "scene_switch_rate": 64,
    "scene_stability_score": 37,
    "scene_lock_score": 28,
    "study_surface_score": 42,
    "scene_text_score": 71,
    "blur_score": 12,
    "brightness_score": 94,
    "external_uncertainty": 33
  }
}
```

This auto-normalizes to:

- capability: `learning_state_guardian`
- operation: `record_learning_state`

And can directly drive derived fields like:

- `focus_score`
- `cognitive_load`
- `uncertainty_score`
- `switching_index`
- `drift_trend`
- `state_hint`

## 8. Learning State Signal

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

## 9. Guardian Sustained Difficulty Sequence

To trigger a guardian difficulty event, send repeated medium or high state updates or signal updates in the same session.

Example active-event sequence:

```json
{
  "agent_type": "academic_companion",
  "event_type": "state_update",
  "session_id": "guardian_event_demo",
  "timestamp": 1710000000000,
  "payload": {
    "task_mode": "note-taking",
    "focus_score": 44,
    "fatigue_risk": 58,
    "stress_score": 63,
    "clarity_score": 40,
    "behavioral_alignment": 52,
    "support_needed": "Need a cleaner note structure"
  }
}
```

If similar payloads repeat in the same session, the response can include:

- `difficulty_event.status = "active"`
- `difficulty_event.primary_label`
- `difficulty_event.trigger_reason`

To resolve the event, send stable follow-up snapshots, for example:

```json
{
  "agent_type": "academic_companion",
  "event_type": "state_update",
  "session_id": "guardian_event_demo",
  "timestamp": 1710000005000,
  "payload": {
    "task_mode": "note-taking",
    "focus_score": 84,
    "fatigue_risk": 18,
    "stress_score": 22,
    "clarity_score": 82,
    "behavioral_alignment": 88
  }
}
```

After the state settles, the response can include:

- `difficulty_event.status = "resolved"`

## 10. Session Review

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

Reflection review is the main place to inspect:

- `signature`
- `coach_summary`
- `coach_cards`
- `reflection_questions`
- `next_session_experiments`
- `evidence_cards`
- `coach_memo`
- `learner_note`
- `next_goal`
- `provider_status`
- `generation`

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

Guardian review is the main place to inspect:

- `core_metrics`
- `sensor_snapshot`
- `state_classification`
- `state_explanation`
- `difficulty_tracking`

## 10A. Reflection Review Fields

Example reflection review fields to expect:

```json
{
  "focus_theme": "switching during review",
  "target_habit": "stay on one source for two minutes",
  "learner_note": "I panic-switch when load rises.",
  "next_goal": "Finish one page before opening another source.",
  "signature": {
    "key": "switching_drift",
    "label": "Switching Drift"
  },
  "coach_summary": {
    "headline": "Target switching likely disrupted the learning rhythm."
  },
  "reflection_questions": [
    {
      "question": "What triggered the first unnecessary switch before or during the latest study block?"
    }
  ],
  "next_session_experiments": [
    {
      "title": "Two-minute source lock"
    }
  ],
  "provider_status": {
    "requested_provider": "heuristic",
    "effective_provider": "heuristic",
    "configured_model": "qwen3:4b",
    "selected_model": "",
    "llm_available": true
  },
  "generation": {
    "mode": "heuristic",
    "used_llm": false
  }
}
```

## 11. Text Chat

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

Reflection question prompt:

```json
{
  "agent_type": "academic_companion",
  "event_type": "text_chat",
  "session_id": "reflection_demo",
  "timestamp": 1710000000000,
  "payload": {
    "capability": "reflection_coach",
    "message": "Give me one reflection question."
  }
}
```

Reflection experiment prompt:

```json
{
  "agent_type": "academic_companion",
  "event_type": "text_chat",
  "session_id": "reflection_demo",
  "timestamp": 1710000000000,
  "payload": {
    "capability": "reflection_coach",
    "message": "Give me one experiment for next session."
  }
}
```

Reflection memo prompt:

```json
{
  "agent_type": "academic_companion",
  "event_type": "text_chat",
  "session_id": "reflection_demo",
  "timestamp": 1710000000000,
  "payload": {
    "capability": "reflection_coach",
    "message": "Show me the memo."
  }
}
```

Reflection provider-status prompt:

```json
{
  "agent_type": "academic_companion",
  "event_type": "text_chat",
  "session_id": "reflection_demo",
  "timestamp": 1710000000000,
  "payload": {
    "capability": "reflection_coach",
    "message": "Show provider status."
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

Guardian explanation chat:

```json
{
  "agent_type": "academic_companion",
  "event_type": "text_chat",
  "session_id": "guardian_demo",
  "timestamp": 1710000000000,
  "payload": {
    "message": "Why did you mark this state like that?"
  }
}
```

This is useful after:

- a sensor-style state snapshot
- a review that returns `off_task_risk`, `fatigue_risk`, or `signal_check`
- an active guardian difficulty event

## 12. Guardian Review Fields

Example learning-state review fields to expect:

```json
{
  "current_task": "Review problem set solutions",
  "task_mode": "review",
  "core_metrics": {
    "focus_score": 39.3,
    "cognitive_load": 60.1,
    "fatigue_risk": 58.0,
    "uncertainty_score": 45.3,
    "switching_index": 30.6,
    "drift_trend": 50.1,
    "stability": 0.0
  },
  "state_classification": {
    "state_hint": "off_task_risk",
    "state_hint_label": "Off-task risk",
    "load_level": "medium",
    "fatigue_level": "medium",
    "behavioral_level": "misaligned",
    "confidence_level": "medium",
    "load_reason": "Behavior is drifting away from the expected review pattern"
  },
  "state_explanation": {
    "why_this_state": "The guardian marked this state as off-task risk mainly because scene lock is driving the pattern.",
    "primary_driver": {
      "label": "Scene lock"
    },
    "top_intervention": "Re-anchor the study surface so the learner has one clear visual target."
  },
  "difficulty_tracking": {
    "active_event": {},
    "recent_events": [],
    "event_count": 0
  }
}
```

## 13. Success Shape

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

## 14. Error Shape

```json
{
  "status": "error",
  "message": "academic_companion failed to process ..."
}
```
