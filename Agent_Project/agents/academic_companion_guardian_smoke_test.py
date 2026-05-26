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
    assert_true("recent_trend_window" in review, "review should expose recent_trend_window")
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
    assert_true(review["state_transition_summary"]["to_state_hint"], "sensor flow should expose a state transition summary")
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
    assert_true(review["recovery_confidence"]["label"] in {"medium", "high"}, "resolved recovery should raise recovery confidence")
    assert_true(review["intervention_plan"]["category"], "review should expose an intervention plan after sustained events")
    print("PASS sustained_event")


def run_baseline_and_trend_flow(mod):
    mission = mod._build_default_mission("guardian_smoke_baseline", "guardian_smoke_baseline")
    mission = mod._ensure_mission_extensions(mission)

    context_payload = mod._normalize_guardian_payload(
        {
            "current_task": "Read and annotate one journal section",
            "session_goal": "Finish one annotated section",
            "task_mode": "reading",
        },
        "state_update",
    )
    mod._apply_learning_state_update(mission, context_payload, context_payload["operation"])

    stable_snapshots = [
        {"attention_score": 81, "fatigue_score": 24, "stress_score": 33, "clarity_score": 78},
        {"attention_score": 79, "fatigue_score": 27, "stress_score": 36, "clarity_score": 75},
        {"attention_score": 83, "fatigue_score": 23, "stress_score": 31, "clarity_score": 80},
        {"attention_score": 80, "fatigue_score": 25, "stress_score": 34, "clarity_score": 77},
    ]
    for idx, payload_seed in enumerate(stable_snapshots):
        payload = mod._normalize_guardian_payload(
            {
                **payload_seed,
                "task_mode": "reading",
                "progress_status": f"baseline {idx}",
            },
            "state_update",
        )
        mod._apply_learning_state_update(mission, payload, payload["operation"])

    strain_payload = mod._normalize_guardian_payload(
        {
            "task_mode": "reading",
            "focus_score": 48,
            "fatigue_risk": 61,
            "stress_score": 67,
            "clarity_score": 43,
            "behavioral_alignment": 57,
            "progress_status": "strain checkpoint",
            "support_needed": "Need to re-anchor main argument",
        },
        "state_update",
    )
    mod._apply_learning_state_update(mission, strain_payload, strain_payload["operation"])

    recovery_payload = mod._normalize_guardian_payload(
        {
            "task_mode": "reading",
            "focus_score": 82,
            "fatigue_risk": 26,
            "stress_score": 32,
            "clarity_score": 79,
            "behavioral_alignment": 84,
            "progress_status": "recovered checkpoint",
        },
        "state_update",
    )
    mod._apply_learning_state_update(mission, recovery_payload, recovery_payload["operation"])
    review = mod._build_learning_state_review(mission)

    assert_true(review["personal_baseline"]["sample_count"] >= 3, "guardian should build a personal baseline from stable snapshots")
    assert_true(review["recent_trend_window"]["window_size"] >= 5, "guardian should expose a recent trend window")
    assert_true(review["state_transition_summary"]["transition_type"] in {"recovery", "steady", "mixed_shift"}, "guardian should summarize the latest transition")
    assert_true(review["recovery_confidence"]["score"] > 40, "guardian should expose recovery confidence after recovery snapshots")
    assert_true(review["continuity_profile"]["stability_band"] in {"stable", "mixed", "volatile"}, "guardian should expose a continuity profile")
    assert_true(review["intervention_plan"]["priority"] in {"low", "medium", "high"}, "guardian should expose intervention priority")
    assert_true(review["baseline_deviation_summary"]["strongest_deviation"], "guardian should expose a strongest baseline deviation")
    assert_true(review["trajectory_outlook"]["label"] in {"stable", "stabilizing", "recovering", "oscillating", "deteriorating", "active_risk"}, "guardian should expose a trajectory outlook")
    assert_true(review["state_streaks"]["same_hint_streak"] >= 1, "guardian should expose state streaks")

    baseline_reply = mod._build_learning_state_chat_reply("What is my baseline?", mission)
    compare_reply = mod._build_learning_state_chat_reply("Compare this state to my baseline.", mission)
    trend_reply = mod._build_learning_state_chat_reply("Show me the trend.", mission)
    recovery_reply = mod._build_learning_state_chat_reply("Has my state recovered?", mission)
    stability_reply = mod._build_learning_state_chat_reply("How stable is this state?", mission)
    intervention_reply = mod._build_learning_state_chat_reply("What should I do next?", mission)
    trajectory_reply = mod._build_learning_state_chat_reply("What is the trajectory outlook?", mission)
    streak_reply = mod._build_learning_state_chat_reply("Show me the current streak.", mission)
    assert_true("baseline" in baseline_reply.lower(), "baseline chat should reference the guardian baseline")
    assert_true("strongest deviation" in compare_reply.lower(), "compare chat should reference the strongest baseline deviation")
    assert_true("recent trend window" in trend_reply.lower(), "trend chat should reference the trend window")
    assert_true("recovery confidence" in recovery_reply.lower(), "recovery chat should mention recovery confidence")
    assert_true("continuity score" in stability_reply.lower(), "stability chat should mention continuity score")
    assert_true("next checkpoint" in intervention_reply.lower(), "intervention chat should mention the next checkpoint")
    assert_true("current outlook" in trajectory_reply.lower(), "trajectory chat should mention the current outlook")
    assert_true("streak" in streak_reply.lower(), "streak chat should mention streaks")
    print("PASS baseline_and_trend")


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
    run_baseline_and_trend_flow(mod)
    run_explain_chat_flow(mod)
    print("ALL GUARDIAN SMOKE TESTS PASSED")


if __name__ == "__main__":
    main()
