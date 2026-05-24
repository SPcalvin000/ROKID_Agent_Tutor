from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path


MODULE_PATH = Path(__file__).with_name("academic_companion.py")


def load_module():
    spec = spec_from_file_location("academic_companion", MODULE_PATH)
    module = module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def assert_true(condition, message):
    if not condition:
        raise AssertionError(message)


def run_high_level_snapshot_flow(mod):
    mission = mod._build_default_mission("guardian_smoke_high", "guardian_smoke_high")
    mission = mod._ensure_mission_extensions(mission)

    context_payload = mod._normalize_guardian_payload(
        {
            "current_task": "Draft a summary paragraph",
            "session_goal": "Finish one clean summary paragraph",
            "current_course": "Learning Science",
            "task_mode": "reading",
        },
        "state_update",
    )
    context_result = mod._apply_learning_state_update(mission, context_payload, context_payload["operation"])
    assert_true(context_result["task_mode"] == "reading", "context task_mode should be reading")

    state_payload = mod._normalize_guardian_payload(
        {
            "attention_score": 76,
            "fatigue_score": 31,
            "stress_score": 44,
            "clarity_score": 71,
            "current_task": "Draft a summary paragraph",
            "task_mode": "reading",
        },
        "state_update",
    )
    state_result = mod._apply_learning_state_update(mission, state_payload, state_payload["operation"])
    review = mod._build_learning_state_review(mission)

    assert_true(state_result["snapshot"]["focus_score"] == 76.0, "high-level flow should preserve focus_score")
    assert_true(review["task_mode"] == "reading", "review task_mode should stay reading")
    assert_true(review["core_metrics"]["focus_score"] == 76.0, "review focus_score should match")
    print("PASS high_level_snapshot")


def run_sensor_snapshot_flow(mod):
    mission = mod._build_default_mission("guardian_smoke_sensor", "guardian_smoke_sensor")
    mission = mod._ensure_mission_extensions(mission)

    context_payload = mod._normalize_guardian_payload(
        {
            "current_task": "Review problem set solutions",
            "session_goal": "Understand two mistakes",
            "task_mode": "review",
        },
        "state_update",
    )
    mod._apply_learning_state_update(mission, context_payload, context_payload["operation"])

    sensor_payload = mod._normalize_guardian_payload(
        {
            "task_mode": "review",
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
            "external_uncertainty": 33,
            "progress_status": "checking mistake pattern",
            "distraction": "browser tabs",
        },
        "state_update",
    )
    state_result = mod._apply_learning_state_update(mission, sensor_payload, sensor_payload["operation"])
    review = mod._build_learning_state_review(mission)

    assert_true(state_result["snapshot"]["orientation_drift"] == 61.0, "sensor flow should store orientation_drift")
    assert_true(review["sensor_snapshot"]["scene_switch_rate"] == 64.0, "sensor snapshot should expose scene_switch_rate")
    assert_true(review["core_metrics"]["switching_index"] > 0, "sensor flow should derive switching_index")
    assert_true(review["core_metrics"]["drift_trend"] > 0, "sensor flow should derive drift_trend")
    assert_true(review["state_explanation"]["primary_driver"], "sensor flow should produce explanation drivers")
    print("PASS sensor_snapshot")


def run_sustained_event_flow(mod):
    mission = mod._build_default_mission("guardian_smoke_event", "guardian_smoke_event")
    mission = mod._ensure_mission_extensions(mission)

    context_payload = mod._normalize_guardian_payload(
        {
            "current_task": "Summarise lecture notes into a concept map",
            "session_goal": "Finish one concept map draft",
            "task_mode": "note-taking",
        },
        "state_update",
    )
    mod._apply_learning_state_update(mission, context_payload, context_payload["operation"])

    active_event = {}
    for idx in range(3):
        state_payload = mod._normalize_guardian_payload(
            {
                "task_mode": "note-taking",
                "focus_score": 44,
                "fatigue_risk": 58,
                "stress_score": 63,
                "clarity_score": 40,
                "behavioral_alignment": 52,
                "support_needed": "Need a cleaner note structure",
                "progress_status": f"checkpoint {idx}",
            },
            "state_update",
        )
        state_result = mod._apply_learning_state_update(mission, state_payload, state_payload["operation"])
        active_event = state_result.get("difficulty_event") or active_event

    assert_true(active_event.get("status") == "active", "sustained medium states should activate guardian event")

    signal_payload = mod._normalize_guardian_payload(
        {
            "signal_type": "context_switching",
            "severity": "high",
            "note": "Jumped between tabs repeatedly",
        },
        "state_update",
    )
    signal_result = mod._apply_learning_state_update(mission, signal_payload, signal_payload["operation"])
    assert_true(signal_result["difficulty_event"].get("status") == "active", "signal update should keep event active")

    resolved_event = {}
    for idx in range(2):
        stable_payload = mod._normalize_guardian_payload(
            {
                "task_mode": "note-taking",
                "focus_score": 84,
                "fatigue_risk": 18,
                "stress_score": 22,
                "clarity_score": 82,
                "behavioral_alignment": 88,
                "progress_status": f"stable {idx}",
            },
            "state_update",
        )
        stable_result = mod._apply_learning_state_update(mission, stable_payload, stable_payload["operation"])
        resolved_event = stable_result.get("difficulty_event") or resolved_event

    review = mod._build_learning_state_review(mission)
    assert_true(resolved_event.get("status") == "resolved", "stable recovery should resolve event")
    assert_true(review["difficulty_tracking"]["event_count"] >= 1, "review should keep resolved guardian events")
    assert_true(review["difficulty_tracking"]["recent_events"], "review should expose recent guardian events")
    print("PASS sustained_event")


def run_explain_chat_flow(mod):
    mission = mod._build_default_mission("guardian_smoke_explain", "guardian_smoke_explain")
    mission = mod._ensure_mission_extensions(mission)

    context_payload = mod._normalize_guardian_payload(
        {
            "current_task": "Review problem set solutions",
            "session_goal": "Understand two mistakes",
            "task_mode": "review",
        },
        "state_update",
    )
    mod._apply_learning_state_update(mission, context_payload, context_payload["operation"])

    sensor_payload = mod._normalize_guardian_payload(
        {
            "task_mode": "review",
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
            "external_uncertainty": 33,
        },
        "state_update",
    )
    mod._apply_learning_state_update(mission, sensor_payload, sensor_payload["operation"])

    reply = mod._build_learning_state_chat_reply("Why did you mark this state like that?", mission)
    assert_true("mainly because" in reply.lower() or "top driver" in reply.lower(), "why-chat should explain the state")
    print("PASS explain_chat")


def main():
    mod = load_module()
    run_high_level_snapshot_flow(mod)
    run_sensor_snapshot_flow(mod)
    run_sustained_event_flow(mod)
    run_explain_chat_flow(mod)
    print("ALL GUARDIAN SMOKE TESTS PASSED")


if __name__ == "__main__":
    main()
