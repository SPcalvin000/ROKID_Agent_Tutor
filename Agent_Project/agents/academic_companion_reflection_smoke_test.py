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


def build_reflection_ready_mission(mod, mission_id):
    mission = mod._build_default_mission(mission_id, mission_id)
    mission = mod._ensure_mission_extensions(mission)

    guardian_context = mod._normalize_guardian_payload(
        {
            "current_task": "Review chemistry notes",
            "session_goal": "Keep one source stable",
            "task_mode": "review",
        },
        "state_update",
    )
    mod._apply_learning_state_update(mission, guardian_context, guardian_context["operation"])

    guardian_state = mod._normalize_guardian_payload(
        {
            "task_mode": "review",
            "focus_score": 52,
            "cognitive_load": 58,
            "fatigue_risk": 37,
            "behavioral_alignment": 66,
            "uncertainty_score": 19,
            "state_hint": "load_rising",
        },
        "state_update",
    )
    mod._apply_learning_state_update(mission, guardian_state, guardian_state["operation"])

    reflection_focus = mod._normalize_reflection_payload(
        {
            "operation": "set_reflection_focus",
            "focus_theme": "keeping one source stable",
            "target_habit": "avoid extra tab switching",
            "current_course": "Chemistry",
            "learner_note": "I panic-switch when load rises.",
            "next_goal": "Finish one page before opening another source.",
            "provider_override": "heuristic",
        },
        "state_update",
    )
    mod._apply_reflection_update(mission, reflection_focus, reflection_focus["operation"])

    reflection_capture = mod._normalize_reflection_payload(
        {
            "operation": "capture_reflection",
            "what_happened": "I switched tabs too early.",
            "what_worked": "Reading aloud slowed me down.",
            "what_was_hard": "I lost the main thread midway.",
            "lesson": "I need a stronger opening anchor.",
            "next_step": "Finish one page before opening another source.",
        },
        "state_update",
    )
    mod._apply_reflection_update(mission, reflection_capture, reflection_capture["operation"])
    return mission


def run_reflection_review_flow(mod):
    mission = build_reflection_ready_mission(mod, "reflection_smoke_review")
    review = mod._build_reflection_review(mission)

    assert_true(review["signature"]["key"], "review should include a reflection signature")
    assert_true(len(review["reflection_questions"]) == 3, "review should provide three reflection questions")
    assert_true(len(review["next_session_experiments"]) == 3, "review should provide three next-session experiments")
    assert_true(len(review["evidence_cards"]) >= 4, "review should include evidence cards")
    print("PASS reflection_review")


def run_reflection_meta_flow(mod):
    mission = build_reflection_ready_mission(mod, "reflection_smoke_meta")
    review = mod._build_reflection_review(mission)
    provider_status = review.get("provider_status", {})
    generation = review.get("generation", {})

    assert_true(review["learner_note"] == "I panic-switch when load rises.", "review should retain learner_note")
    assert_true(review["next_goal"] == "Finish one page before opening another source.", "review should retain next_goal")
    assert_true(provider_status.get("requested_provider") == "heuristic", "provider_status should preserve requested provider")
    assert_true(generation.get("mode") == "heuristic", "generation mode should remain heuristic")
    assert_true(review.get("module_boundary"), "review should expose module boundary text")
    print("PASS reflection_meta")


def run_reflection_chat_flow(mod):
    mission = build_reflection_ready_mission(mod, "reflection_smoke_chat")

    question_reply = mod._build_reflection_chat_reply("Give me one reflection question.", mission)
    experiment_reply = mod._build_reflection_chat_reply("Give me one experiment for next session.", mission)
    goal_reply = mod._build_reflection_chat_reply("What is my goal?", mission)
    provider_reply = mod._build_reflection_chat_reply("Show provider status.", mission)

    assert_true("reflection prompt" in question_reply.lower(), "question chat should return a reflection prompt")
    assert_true("next-session experiment" in experiment_reply.lower(), "experiment chat should return an experiment")
    assert_true("next-session goal" in goal_reply.lower(), "goal chat should return the saved goal")
    assert_true("provider status" in provider_reply.lower(), "provider chat should expose provider status")
    print("PASS reflection_chat")


def main():
    mod = load_module()
    run_reflection_review_flow(mod)
    run_reflection_meta_flow(mod)
    run_reflection_chat_flow(mod)
    print("ALL REFLECTION SMOKE TESTS PASSED")


if __name__ == "__main__":
    main()
