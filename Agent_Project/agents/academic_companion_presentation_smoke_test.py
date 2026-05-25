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


def build_presentation_ready_mission(mod, mission_id):
    mission = mod._build_default_mission(mission_id, mission_id)
    mission = mod._ensure_mission_extensions(mission)

    mod._apply_mission_update(
        mission,
        {
            "title": "Climate Policy Brief",
            "course": "POL302",
            "target_duration_minutes": 4,
            "audience": "Seminar group",
            "focus_goal": "Stay concise while keeping one clear example",
        },
    )

    mod._apply_script_section_update(
        mission,
        {
            "section_id": "opening",
            "title": "Opening",
            "slide_title": "Opening",
            "slide_anchor": "Slide 1",
            "interaction_goal": "Frame the task and preview the structure.",
            "target_seconds": 36,
            "outline": "Introduce the policy problem and roadmap.",
            "speaker_notes": "State the question, the stakes, and the route.",
            "teleprompter_script": "Today I will explain the policy problem, the trade-off, and the recommendation.",
            "cue_cards": "Problem -> trade-off -> recommendation",
            "status": "ready",
        },
    )
    mod._apply_script_section_update(
        mission,
        {
            "section_id": "main_point",
            "title": "Main Point",
            "slide_title": "Main Point",
            "slide_anchor": "Slide 2",
            "interaction_goal": "Explain the key argument without reading full sentences.",
            "target_seconds": 64,
            "outline": "Compare the two policy options and explain the preferred route.",
            "speaker_notes": "Move from cost to impact, then justify the recommendation.",
            "teleprompter_script": (
                "Option one lowers cost quickly but weakens long-term coverage. "
                "Option two costs more now, but it protects access over time. "
                "That is why I recommend the second route."
            ),
            "cue_cards": "Cost now -> access later -> recommend option two",
            "status": "ready",
        },
    )
    return mission


def run_live_hud_navigation_flow(mod):
    mission = build_presentation_ready_mission(mod, "presentation_smoke_nav")
    control = mod._apply_control_action(
        mission,
        {"action": "jump", "section_id": "opening", "control_source": "rokid_hud"},
    )
    review = mod._build_review(mission)
    live_hud = review["live_hud"]

    assert_true(control["operation"] == "presentation_control", "control flow should return presentation_control")
    assert_true(live_hud["mode"] == "presentation_live", "live_hud should expose presentation_live mode")
    assert_true(live_hud["active_slide_title"] == "Opening", "hud should expose the active slide title")
    assert_true(live_hud["chunk_progress_label"] != "0/0", "hud should expose chunk progress")
    assert_true(live_hud["teleprompter_text"], "hud should expose active teleprompter text")
    assert_true(live_hud["cue_line"], "hud should expose a cue line when cue view is visible")
    assert_true(live_hud["next_slide_title"] == "Main Point", "hud should expose the next slide title")
    print("PASS presentation_live_hud_navigation")


def run_live_hud_rehearsal_flow(mod):
    mission = build_presentation_ready_mission(mod, "presentation_smoke_rehearsal")
    rehearsal = mod._record_rehearsal(
        mission,
        {
            "duration_minutes": 4.6,
            "confidence_level": 3,
            "self_rating": 4,
            "next_focus": "tighten the main point transition",
            "needs_improvement": "Trim one long explanation in the middle section.",
            "transcript_excerpt": (
                "Today I will explain the policy problem and the trade-off. "
                "Option one lowers cost quickly, but it weakens long-term coverage. "
                "Option two costs more now, but it protects access over time."
            ),
            "section_timings": [
                {"section_id": "opening", "actual_seconds": 42},
                {"section_id": "main_point", "actual_seconds": 104},
                {"section_id": "example", "actual_seconds": 78},
                {"section_id": "conclusion", "actual_seconds": 52},
            ],
        },
    )
    review = mod._build_review(mission)
    live_hud = review["live_hud"]
    mission_payload = mod._mission_payload(mission)

    assert_true(rehearsal["analysis"]["timing_status"] in {"long", "short", "balanced"}, "rehearsal should compute timing status")
    assert_true(live_hud["status_line"], "hud should expose a status line after rehearsal")
    assert_true(live_hud["next_action_line"], "hud should expose a next action line after rehearsal")
    assert_true("live_hud" in mission_payload, "mission payload should expose live_hud")
    assert_true(mission_payload["live_hud"]["mode"] == "presentation_live", "mission payload live_hud should be presentation_live")
    print("PASS presentation_live_hud_rehearsal")


def main():
    mod = load_module()
    run_live_hud_navigation_flow(mod)
    run_live_hud_rehearsal_flow(mod)
    print("ALL PRESENTATION SMOKE TESTS PASSED")


if __name__ == "__main__":
    main()
