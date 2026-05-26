import asyncio
import copy
import json
import os
import re
import uuid
from collections import Counter
from datetime import datetime


MAX_HISTORY = 24
WORDS_PER_SECOND = 2.35
TRANSCRIPT_STOPWORDS = {
    "a", "an", "and", "are", "as", "at", "be", "because", "but", "by", "for", "from",
    "have", "if", "in", "into", "is", "it", "of", "on", "or", "our", "so", "that",
    "the", "their", "them", "there", "they", "this", "to", "we", "with", "you", "your",
    "will", "can", "just", "then", "than", "also", "very", "really", "about", "what",
}
FILLER_PATTERNS = [
    "um",
    "uh",
    "like",
    "you know",
    "i mean",
    "sort of",
    "kind of",
    "basically",
    "actually",
]
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(BASE_DIR, "data")
STORE_PATH = os.path.join(DATA_DIR, "academic_companion_store.json")
STORE_LOCK = asyncio.Lock()
CAPABILITY_PRESENTATION = "presentation"
CAPABILITY_REFLECTION = "reflection_coach"
CAPABILITY_GUARDIAN = "learning_state_guardian"
SUPPORTED_EVENT_TYPES = ("text_chat", "state_update", "difficulty_event", "session_review")
REFLECTION_MODEL_PROVIDERS = {"ollama", "remote", "openai"}
PRESENTATION_OPERATIONS = (
    "upsert_mission",
    "extract_intake",
    "update_script_section",
    "presentation_control",
    "record_rehearsal",
)
REFLECTION_OPERATIONS = {
    "set_reflection_focus",
    "capture_reflection",
    "log_reflection",
    "plan_next_step",
}
GUARDIAN_OPERATIONS = {
    "set_learning_context",
    "record_learning_state",
    "record_focus_signal",
}
CAPABILITY_ALIASES = {
    "academic_companion": CAPABILITY_PRESENTATION,
    "academic_presentation": CAPABILITY_PRESENTATION,
    "learning_reflection": CAPABILITY_REFLECTION,
    "learning_state": CAPABILITY_GUARDIAN,
    "presentation": CAPABILITY_PRESENTATION,
    "presentation_companion": CAPABILITY_PRESENTATION,
    "reflection": CAPABILITY_REFLECTION,
    "reflection_coach": CAPABILITY_REFLECTION,
    "state_guardian": CAPABILITY_GUARDIAN,
    "study_state": CAPABILITY_GUARDIAN,
    "learning_state_guardian": CAPABILITY_GUARDIAN,
}
CAPABILITY_STATE_UPDATE_OPERATIONS = {
    CAPABILITY_PRESENTATION: PRESENTATION_OPERATIONS,
    CAPABILITY_REFLECTION: tuple(sorted(REFLECTION_OPERATIONS)),
    CAPABILITY_GUARDIAN: tuple(sorted(GUARDIAN_OPERATIONS)),
}
CONTROL_ACTION_ALIASES = {
    "next": "next_chunk",
    "next_chunk": "next_chunk",
    "forward": "next_chunk",
    "single_tap": "next_chunk",
    "tap": "next_chunk",
    "next_slide": "next_slide",
    "swipe_right": "next_slide",
    "previous": "previous_chunk",
    "previous_chunk": "previous_chunk",
    "back": "previous_chunk",
    "double_tap": "previous_chunk",
    "previous_slide": "previous_slide",
    "swipe_left": "previous_slide",
    "toggle": "toggle_cue",
    "toggle_cue": "toggle_cue",
    "hide_cue": "toggle_cue",
    "show_cue": "toggle_cue",
    "cue_toggle": "toggle_cue",
}
REVIEW_SCOPE_ALIASES = {
    "guardian": "guardian",
    "learning_state": "learning_state",
    "learning": "learning_state",
    "reflection": "reflection",
    "reflect": "reflection",
    "presentation": "mission",
    "mission": "mission",
}
GUARDIAN_TASK_MODE_ALIASES = {
    "lecture": "lecture",
    "reading": "reading",
    "review": "review",
    "note_taking": "note-taking",
    "note-taking": "note-taking",
    "notes": "note-taking",
}
GUARDIAN_TASK_MODE_PROFILES = {
    "lecture": {
        "load_medium": 44.0,
        "load_high": 78.0,
        "fatigue_medium": 34.0,
        "fatigue_high": 60.0,
        "behavioral_drifting": 68.0,
        "behavioral_misaligned": 40.0,
        "uncertainty_medium": 30.0,
        "uncertainty_high": 54.0,
        "productive_alignment": 74.0,
        "productive_load_low": 30.0,
        "productive_load_high": 66.0,
        "switching_high": 76.0,
        "drift_rising": 30.0,
    },
    "reading": {
        "load_medium": 46.0,
        "load_high": 78.0,
        "fatigue_medium": 38.0,
        "fatigue_high": 65.0,
        "behavioral_drifting": 72.0,
        "behavioral_misaligned": 42.0,
        "uncertainty_medium": 34.0,
        "uncertainty_high": 55.0,
        "productive_alignment": 76.0,
        "productive_load_low": 35.0,
        "productive_load_high": 72.0,
        "switching_high": 72.0,
        "drift_rising": 32.0,
    },
    "note-taking": {
        "load_medium": 50.0,
        "load_high": 82.0,
        "fatigue_medium": 40.0,
        "fatigue_high": 67.0,
        "behavioral_drifting": 64.0,
        "behavioral_misaligned": 36.0,
        "uncertainty_medium": 36.0,
        "uncertainty_high": 58.0,
        "productive_alignment": 70.0,
        "productive_load_low": 38.0,
        "productive_load_high": 76.0,
        "switching_high": 80.0,
        "drift_rising": 36.0,
    },
    "review": {
        "load_medium": 48.0,
        "load_high": 80.0,
        "fatigue_medium": 38.0,
        "fatigue_high": 64.0,
        "behavioral_drifting": 68.0,
        "behavioral_misaligned": 40.0,
        "uncertainty_medium": 34.0,
        "uncertainty_high": 56.0,
        "productive_alignment": 74.0,
        "productive_load_low": 34.0,
        "productive_load_high": 72.0,
        "switching_high": 76.0,
        "drift_rising": 34.0,
    },
}
GUARDIAN_STATE_HINT_ALIASES = {
    "stable": "stable",
    "load_rising": "load_rising",
    "fatigue_risk": "fatigue_risk",
    "off_task_risk": "off_task_risk",
    "productive_struggle": "productive_struggle",
    "signal_check": "signal_check",
}
GUARDIAN_STATE_HINT_LABELS = {
    "stable": "Stable learning state",
    "load_rising": "Load rising",
    "fatigue_risk": "Fatigue risk rising",
    "off_task_risk": "Off-task risk",
    "productive_struggle": "Productive struggle",
    "signal_check": "Signal quality check",
}
GUARDIAN_CHALLENGE_ALIASES = {
    "look_away": "attention drift",
    "attention_drop": "attention drift",
    "focus_drop": "attention drift",
    "context_switching": "context switching",
    "tab_switching": "context switching",
    "notification_pull": "notification distraction",
    "fatigue": "low energy",
    "blink_fatigue": "fatigue signal",
    "hesitation": "task hesitation",
    "long_pause": "task hesitation",
    "lost_track": "lost task thread",
}
GUARDIAN_SWITCH_SIGNAL_WEIGHTS = {
    "attention drift": 18.0,
    "context switching": 28.0,
    "notification distraction": 22.0,
    "fatigue signal": 18.0,
    "low energy": 16.0,
    "task hesitation": 16.0,
    "lost task thread": 20.0,
}
GUARDIAN_SENSOR_FIELD_ALIASES = {
    "stability": ("stability", "stability_score"),
    "relative_pitch": ("relative_pitch", "pitch_drift"),
    "signed_pitch_delta": ("signed_pitch_delta",),
    "relative_yaw": ("relative_yaw", "yaw_drift"),
    "relative_roll": ("relative_roll", "roll_drift"),
    "combined_drift": ("combined_drift", "drift_score", "drift"),
    "orientation_drift": ("orientation_drift",),
    "movement_intensity": ("movement_intensity", "motion_intensity"),
    "drift_trend": ("drift_trend",),
    "switching_index": ("switching_index",),
    "scene_content_score": ("scene_content_score",),
    "scene_text_score": ("scene_text_score", "text_presence_score"),
    "scene_stability_score": ("scene_stability_score",),
    "scene_switch_rate": ("scene_switch_rate",),
    "study_surface_score": ("study_surface_score",),
    "scene_lock_score": ("scene_lock_score",),
    "blur_score": ("blur_score",),
    "brightness_score": ("brightness_score",),
    "external_uncertainty": ("external_uncertainty",),
    "scene_signal_active": ("scene_signal_active",),
}
GUARDIAN_DIFFICULTY_TRIGGER_COUNTS = {
    "medium": 3,
    "high": 2,
    "resolve": 2,
}

GUARDIAN_TREND_WINDOW_SIZE = 6
GUARDIAN_BASELINE_WINDOW_SIZE = 8
OPERATION_ALIASES = {
    CAPABILITY_PRESENTATION: {
        "brief": "extract_intake",
        "extract_brief": "extract_intake",
        "extract_task": "extract_intake",
        "intake": "extract_intake",
        "mission_update": "upsert_mission",
        "set_mission": "upsert_mission",
        "slide_control": "presentation_control",
        "teleprompter_control": "presentation_control",
        "section_update": "update_script_section",
        "update_section": "update_script_section",
        "log_rehearsal": "record_rehearsal",
        "rehearsal": "record_rehearsal",
    },
    CAPABILITY_REFLECTION: {
        "capture": "capture_reflection",
        "log": "log_reflection",
        "reflect": "capture_reflection",
        "reflection": "capture_reflection",
        "set_focus": "set_reflection_focus",
        "set_theme": "set_reflection_focus",
        "next_step": "plan_next_step",
        "plan": "plan_next_step",
    },
    CAPABILITY_GUARDIAN: {
        "context": "set_learning_context",
        "set_context": "set_learning_context",
        "state": "record_learning_state",
        "snapshot": "record_learning_state",
        "state_snapshot": "record_learning_state",
        "focus_signal": "record_focus_signal",
        "signal": "record_focus_signal",
    },
}


def _now_iso():
    return datetime.utcnow().isoformat(timespec="seconds") + "Z"


def _ensure_payload_dict(payload):
    if isinstance(payload, dict):
        return payload
    return {}


def _normalize_capability(value):
    normalized = _safe_text(value, max_length=80).lower()
    return CAPABILITY_ALIASES.get(normalized, "")


def _safe_text(value, max_length=240, preserve_lines=False):
    text = str(value or "")
    if preserve_lines:
        lines = [line.rstrip() for line in text.replace("\r\n", "\n").replace("\r", "\n").split("\n")]
        cleaned = "\n".join(line for line in lines if line.strip())
    else:
        cleaned = " ".join(text.split())
    return cleaned[:max_length]


def _safe_float(value, default=0.0):
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _safe_int(value, default=0):
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _safe_bool(value, default=False):
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        lowered = value.strip().lower()
        if lowered in {"true", "1", "yes", "y", "on"}:
            return True
        if lowered in {"false", "0", "no", "n", "off"}:
            return False
    return default


def _infer_capability_from_message(message):
    lowered = _safe_text(message, max_length=600, preserve_lines=True).lower()
    if any(token in lowered for token in ("reflection", "reflect", "what did i learn", "lesson learned", "journal")):
        return CAPABILITY_REFLECTION
    if any(token in lowered for token in ("focus", "energy", "distracted", "burnout", "overwhelmed", "state", "tired")):
        return CAPABILITY_GUARDIAN
    return CAPABILITY_PRESENTATION


def _infer_capability_from_payload(payload, event_type=""):
    payload = _ensure_payload_dict(payload)
    reflection_markers = (
        "focus_theme",
        "theme",
        "summary",
        "session_summary",
        "lesson",
        "insight",
        "what_i_learned",
        "next_action",
        "action_commitment",
    )
    guardian_markers = (
        "attention_score",
        "focus_score",
        "focus_level",
        "cognitive_load",
        "behavioral_alignment",
        "fatigue_risk",
        "uncertainty_score",
        "task_mode",
        "state_hint",
        "stability",
        "combined_drift",
        "orientation_drift",
        "movement_intensity",
        "switching_index",
        "drift_trend",
        "scene_text_score",
        "scene_stability_score",
        "scene_switch_rate",
        "study_surface_score",
        "scene_lock_score",
        "blur_score",
        "brightness_score",
        "external_uncertainty",
        "energy_level",
        "fatigue_score",
        "stress_level",
        "stress_score",
        "current_task",
        "task",
        "session_goal",
        "support_needed",
        "device_event_type",
        "signal_type",
    )
    presentation_markers = (
        "gesture",
        "button",
        "rokid_action",
        "control_action",
        "assignment_text",
        "task_text",
        "brief_text",
        "transcript_excerpt",
        "section_timings",
        "teleprompter_script",
        "speaker_notes",
    )

    if any(_first_present_value(payload, (key,)) is not None for key in reflection_markers):
        return CAPABILITY_REFLECTION
    if any(_first_present_value(payload, (key,)) is not None for key in guardian_markers):
        return CAPABILITY_GUARDIAN
    if any(_first_present_value(payload, (key,)) is not None for key in presentation_markers):
        return CAPABILITY_PRESENTATION

    if event_type == "difficulty_event" and _first_present_value(payload, ("device_event_type", "signal_type")) is not None:
        return CAPABILITY_GUARDIAN
    if event_type == "session_review":
        scope = _normalize_review_scope(_first_present_value(payload, ("review_scope", "scope")), "")
        if scope in {"reflection"}:
            return CAPABILITY_REFLECTION
        if scope in {"guardian", "learning_state"}:
            return CAPABILITY_GUARDIAN
    return ""


def _first_present_value(payload, keys):
    payload = _ensure_payload_dict(payload)
    for key in keys:
        value = payload.get(key)
        if value is None:
            continue
        if isinstance(value, str) and not value.strip():
            continue
        return value
    return None


def _canonical_operation(capability, operation):
    normalized = _safe_text(operation, max_length=80).lower()
    if not normalized:
        if capability == CAPABILITY_REFLECTION:
            return "capture_reflection"
        if capability == CAPABILITY_GUARDIAN:
            return "record_learning_state"
        return "upsert_mission"
    aliases = OPERATION_ALIASES.get(capability, {})
    return aliases.get(normalized, normalized)


def _score_to_level(value, invert=False):
    if value is None or value == "":
        return None
    score = max(0.0, min(100.0, _safe_float(value, default=-1.0)))
    if score < 0:
        return None
    if invert:
        score = 100.0 - score
    if score < 20:
        return 1
    if score < 40:
        return 2
    if score < 60:
        return 3
    if score < 80:
        return 4
    return 5


def _safe_score_100(value, default=0.0):
    return round(max(0.0, min(100.0, _safe_float(value, default=default))), 1)


def _optional_score_100(value):
    if value in (None, ""):
        return None
    try:
        score = float(value)
    except (TypeError, ValueError):
        return None
    return round(max(0.0, min(100.0, score)), 1)


def _level_to_score(value, invert=False):
    if value in (None, ""):
        return None
    try:
        level = int(value)
    except (TypeError, ValueError):
        return None
    if level <= 0:
        return None
    level = max(1, min(5, level))
    score = round(((level - 1) / 4.0) * 100.0, 1)
    if invert:
        return round(100.0 - score, 1)
    return score


def _normalize_control_action(value):
    normalized = _safe_text(value, max_length=80).lower()
    if not normalized:
        return ""
    return CONTROL_ACTION_ALIASES.get(normalized, normalized)


def _normalize_review_scope(value, default_scope):
    normalized = _safe_text(value, max_length=80).lower()
    if not normalized:
        return default_scope
    return REVIEW_SCOPE_ALIASES.get(normalized, normalized)


def _normalize_guardian_challenge(value):
    normalized = _safe_text(value, max_length=120).lower()
    if not normalized:
        return ""
    return GUARDIAN_CHALLENGE_ALIASES.get(normalized, normalized.replace("_", " "))


def _normalize_guardian_task_mode(value):
    normalized = _safe_text(value, max_length=80).lower()
    if not normalized:
        return ""
    return GUARDIAN_TASK_MODE_ALIASES.get(normalized, normalized.replace("_", "-"))


def _guardian_task_profile(task_mode):
    normalized = _normalize_guardian_task_mode(task_mode) or "reading"
    return GUARDIAN_TASK_MODE_PROFILES.get(normalized, GUARDIAN_TASK_MODE_PROFILES["reading"])


def _normalize_guardian_state_hint(value):
    normalized = _safe_text(value, max_length=80).lower()
    if not normalized:
        return ""
    return GUARDIAN_STATE_HINT_ALIASES.get(normalized, normalized.replace(" ", "_"))


def _guardian_state_hint_label(value):
    normalized = _normalize_guardian_state_hint(value) or "stable"
    return GUARDIAN_STATE_HINT_LABELS.get(normalized, normalized.replace("_", " ").title())


def _derive_guardian_load_level(cognitive_load, task_mode=""):
    score = _safe_score_100(cognitive_load, default=0.0)
    profile = _guardian_task_profile(task_mode)
    if score >= profile["load_high"]:
        return "high"
    if score >= profile["load_medium"]:
        return "medium"
    return "low"


def _derive_guardian_fatigue_level(fatigue_risk, task_mode=""):
    score = _safe_score_100(fatigue_risk, default=0.0)
    profile = _guardian_task_profile(task_mode)
    if score >= profile["fatigue_high"]:
        return "high"
    if score >= profile["fatigue_medium"]:
        return "medium"
    return "low"


def _derive_guardian_behavioral_level(behavioral_alignment, task_mode=""):
    score = _safe_score_100(behavioral_alignment, default=100.0)
    profile = _guardian_task_profile(task_mode)
    if score < profile["behavioral_misaligned"]:
        return "misaligned"
    if score < profile["behavioral_drifting"]:
        return "drifting"
    return "aligned"


def _derive_guardian_confidence_level(uncertainty_score, task_mode=""):
    score = _safe_score_100(uncertainty_score, default=35.0)
    profile = _guardian_task_profile(task_mode)
    if score >= profile["uncertainty_high"]:
        return "low"
    if score >= profile["uncertainty_medium"]:
        return "medium"
    return "high"


def _derive_guardian_state_hint(snapshot):
    if not isinstance(snapshot, dict):
        return "stable"
    task_mode = _normalize_guardian_task_mode(snapshot.get("task_mode")) or "reading"
    profile = _guardian_task_profile(task_mode)
    fatigue_risk = _safe_score_100(snapshot.get("fatigue_risk"), default=0.0)
    uncertainty_score = _safe_score_100(snapshot.get("uncertainty_score"), default=profile["uncertainty_medium"])
    behavioral_alignment = _safe_score_100(snapshot.get("behavioral_alignment"), default=100.0)
    cognitive_load = _safe_score_100(snapshot.get("cognitive_load"), default=0.0)
    switching_index = _safe_score_100(snapshot.get("switching_index"), default=0.0)
    drift_trend = _safe_score_100(snapshot.get("drift_trend"), default=0.0)
    behavioral_level = _safe_text(snapshot.get("behavioral_level"), max_length=40).lower() or _derive_guardian_behavioral_level(
        behavioral_alignment,
        task_mode=task_mode,
    )

    if uncertainty_score >= profile["uncertainty_high"]:
        return "signal_check"
    if fatigue_risk >= profile["fatigue_high"] or (drift_trend >= 55 and fatigue_risk >= profile["fatigue_medium"]):
        return "fatigue_risk"
    if (
        behavioral_level == "misaligned"
        or behavioral_alignment < profile["behavioral_misaligned"]
        or switching_index >= profile["switching_high"]
        or cognitive_load >= profile["load_high"]
    ):
        return "off_task_risk"
    if (
        behavioral_alignment >= profile["productive_alignment"]
        and fatigue_risk < profile["fatigue_medium"]
        and uncertainty_score < profile["uncertainty_medium"]
        and profile["productive_load_low"] <= cognitive_load <= profile["productive_load_high"]
        and switching_index < max(20.0, profile["switching_high"] * 0.55)
    ):
        return "productive_struggle"
    if (
        behavioral_level == "drifting"
        or behavioral_alignment < profile["behavioral_drifting"]
        or cognitive_load >= profile["load_medium"]
        or drift_trend >= profile["drift_rising"]
    ):
        return "load_rising"
    return "stable"


def _derive_guardian_load_reason(snapshot):
    if not isinstance(snapshot, dict):
        return "Stable learning state"
    task_mode = _normalize_guardian_task_mode(snapshot.get("task_mode")) or "reading"
    fatigue_level = _safe_text(snapshot.get("fatigue_level"), max_length=40).lower() or _derive_guardian_fatigue_level(
        snapshot.get("fatigue_risk"),
        task_mode=task_mode,
    )
    uncertainty_score = _safe_score_100(snapshot.get("uncertainty_score"), default=_guardian_task_profile(task_mode)["uncertainty_medium"])
    state_hint = _safe_text(snapshot.get("state_hint"), max_length=80).lower() or _derive_guardian_state_hint(snapshot)
    cognitive_load = _safe_score_100(snapshot.get("cognitive_load"), default=0.0)
    switching_index = _safe_score_100(snapshot.get("switching_index"), default=0.0)
    behavioral_level = _safe_text(snapshot.get("behavioral_level"), max_length=40).lower() or _derive_guardian_behavioral_level(
        snapshot.get("behavioral_alignment"),
        task_mode=task_mode,
    )

    if fatigue_level == "high":
        return f"Fatigue is becoming the main limiter during this {task_mode} block"
    if uncertainty_score >= _guardian_task_profile(task_mode)["uncertainty_high"]:
        return "Signal warming up or mode transition"
    if state_hint == "productive_struggle":
        return f"Effort is high but still aligned for this {task_mode} block"
    if switching_index >= _guardian_task_profile(task_mode)["switching_high"]:
        return f"Frequent task switching is disrupting {task_mode} flow"
    if state_hint == "off_task_risk" or cognitive_load >= _guardian_task_profile(task_mode)["load_high"] or behavioral_level == "misaligned":
        return f"Behavior is drifting away from the expected {task_mode} pattern"
    if cognitive_load >= _guardian_task_profile(task_mode)["load_medium"] or behavioral_level == "drifting":
        return f"{task_mode.title()} effort is rising and needs tighter regulation"
    return "Stable learning state"


def _guardian_numeric_average(items, field):
    values = []
    for item in items:
        if not isinstance(item, dict):
            continue
        value = item.get(field)
        if value in (None, ""):
            continue
        values.append(_safe_float(value, default=0.0))
    if not values:
        return 0.0
    return round(sum(values) / len(values), 1)


def _weighted_average(pairs):
    total_weight = 0.0
    total_value = 0.0
    for value, weight in pairs:
        if value is None or weight <= 0:
            continue
        total_weight += float(weight)
        total_value += float(value) * float(weight)
    if total_weight <= 0:
        return None
    return round(total_value / total_weight, 1)


def _guardian_metric_trend(items, field, higher_is_better=True, threshold=6.0):
    values = []
    for item in items:
        if not isinstance(item, dict):
            continue
        value = item.get(field)
        if value in (None, ""):
            continue
        values.append(_safe_float(value, default=0.0))
    if len(values) < 2:
        return {"direction": "stable", "delta": 0.0}
    delta = round(values[-1] - values[0], 1)
    if abs(delta) < threshold:
        return {"direction": "stable", "delta": delta}
    if higher_is_better:
        return {"direction": "improving" if delta > 0 else "worsening", "delta": delta}
    return {"direction": "improving" if delta < 0 else "worsening", "delta": delta}


def _guardian_recent_window(history, size=GUARDIAN_TREND_WINDOW_SIZE):
    history = [item for item in (history or []) if isinstance(item, dict)]
    return history[-max(1, size) :]


def _guardian_is_baseline_candidate(snapshot, task_mode=""):
    snapshot = snapshot if isinstance(snapshot, dict) else {}
    if not snapshot:
        return False
    normalized_task_mode = _normalize_guardian_task_mode(task_mode)
    snapshot_mode = _normalize_guardian_task_mode(snapshot.get("task_mode"))
    if normalized_task_mode and snapshot_mode and normalized_task_mode != snapshot_mode:
        return False

    state_hint = _normalize_guardian_state_hint(snapshot.get("state_hint")) or "stable"
    if state_hint in {"off_task_risk", "fatigue_risk"}:
        return False

    cognitive_load = _safe_score_100(snapshot.get("cognitive_load"), default=100.0)
    fatigue_risk = _safe_score_100(snapshot.get("fatigue_risk"), default=100.0)
    behavioral_alignment = _safe_score_100(snapshot.get("behavioral_alignment"), default=0.0)
    uncertainty_score = _safe_score_100(snapshot.get("uncertainty_score"), default=100.0)
    switching_index = _safe_score_100(snapshot.get("switching_index"), default=100.0)
    drift_trend = _safe_score_100(snapshot.get("drift_trend"), default=100.0)

    return (
        cognitive_load <= 68.0
        and fatigue_risk <= 66.0
        and behavioral_alignment >= 58.0
        and uncertainty_score <= 72.0
        and switching_index <= 72.0
        and drift_trend <= 76.0
    )


def _build_guardian_personal_baseline(history, task_mode=""):
    history = [item for item in (history or []) if isinstance(item, dict)]
    if not history:
        return {}

    normalized_task_mode = _normalize_guardian_task_mode(task_mode) or _normalize_guardian_task_mode(history[-1].get("task_mode")) or "reading"
    candidate_pool = [item for item in history if _guardian_is_baseline_candidate(item, task_mode=normalized_task_mode)]
    source = "stable_samples"

    if len(candidate_pool) < 3:
        source = "recent_window"
        task_mode_history = [
            item
            for item in history
            if _normalize_guardian_task_mode(item.get("task_mode")) == normalized_task_mode
        ]
        candidate_pool = task_mode_history[-GUARDIAN_BASELINE_WINDOW_SIZE:]
        if len(candidate_pool) < 3:
            candidate_pool = history[-GUARDIAN_BASELINE_WINDOW_SIZE:]

    candidate_pool = candidate_pool[-GUARDIAN_BASELINE_WINDOW_SIZE:]
    if not candidate_pool:
        return {}

    return {
        "task_mode": normalized_task_mode,
        "source": source,
        "sample_count": len(candidate_pool),
        "window_size": min(len(history), GUARDIAN_BASELINE_WINDOW_SIZE),
        "focus_score": _guardian_numeric_average(candidate_pool, "focus_score"),
        "cognitive_load": _guardian_numeric_average(candidate_pool, "cognitive_load"),
        "behavioral_alignment": _guardian_numeric_average(candidate_pool, "behavioral_alignment"),
        "fatigue_risk": _guardian_numeric_average(candidate_pool, "fatigue_risk"),
        "uncertainty_score": _guardian_numeric_average(candidate_pool, "uncertainty_score"),
        "switching_index": _guardian_numeric_average(candidate_pool, "switching_index"),
        "drift_trend": _guardian_numeric_average(candidate_pool, "drift_trend"),
        "stability": _guardian_numeric_average(candidate_pool, "stability"),
        "updated_at": _safe_text(candidate_pool[-1].get("recorded_at"), max_length=40),
    }


def _guardian_baseline_delta(latest_state, baseline):
    latest_state = latest_state if isinstance(latest_state, dict) else {}
    baseline = baseline if isinstance(baseline, dict) else {}
    if not latest_state or not baseline:
        return {}

    return {
        "focus_score": round(_safe_float(latest_state.get("focus_score"), default=0.0) - _safe_float(baseline.get("focus_score"), default=0.0), 1),
        "cognitive_load": round(_safe_float(latest_state.get("cognitive_load"), default=0.0) - _safe_float(baseline.get("cognitive_load"), default=0.0), 1),
        "behavioral_alignment": round(_safe_float(latest_state.get("behavioral_alignment"), default=0.0) - _safe_float(baseline.get("behavioral_alignment"), default=0.0), 1),
        "fatigue_risk": round(_safe_float(latest_state.get("fatigue_risk"), default=0.0) - _safe_float(baseline.get("fatigue_risk"), default=0.0), 1),
        "uncertainty_score": round(_safe_float(latest_state.get("uncertainty_score"), default=0.0) - _safe_float(baseline.get("uncertainty_score"), default=0.0), 1),
        "switching_index": round(_safe_float(latest_state.get("switching_index"), default=0.0) - _safe_float(baseline.get("switching_index"), default=0.0), 1),
        "drift_trend": round(_safe_float(latest_state.get("drift_trend"), default=0.0) - _safe_float(baseline.get("drift_trend"), default=0.0), 1),
    }


def _build_guardian_recent_trend_window(history, latest_state, baseline=None):
    history = _guardian_recent_window(history)
    latest_state = latest_state if isinstance(latest_state, dict) else {}
    if not history and latest_state:
        history = [latest_state]
    if not history:
        return {}

    current_task_mode = _normalize_guardian_task_mode(latest_state.get("task_mode")) or _normalize_guardian_task_mode(history[-1].get("task_mode")) or "reading"
    return {
        "task_mode": current_task_mode,
        "window_size": len(history),
        "from_timestamp": _safe_text(history[0].get("recorded_at"), max_length=40),
        "to_timestamp": _safe_text(history[-1].get("recorded_at"), max_length=40),
        "averages": {
            "focus_score": _guardian_numeric_average(history, "focus_score"),
            "cognitive_load": _guardian_numeric_average(history, "cognitive_load"),
            "behavioral_alignment": _guardian_numeric_average(history, "behavioral_alignment"),
            "fatigue_risk": _guardian_numeric_average(history, "fatigue_risk"),
            "uncertainty_score": _guardian_numeric_average(history, "uncertainty_score"),
            "switching_index": _guardian_numeric_average(history, "switching_index"),
            "drift_trend": _guardian_numeric_average(history, "drift_trend"),
        },
        "signals": {
            "focus_score": _guardian_metric_trend(history, "focus_score", higher_is_better=True, threshold=6.0),
            "cognitive_load": _guardian_metric_trend(history, "cognitive_load", higher_is_better=False, threshold=6.0),
            "behavioral_alignment": _guardian_metric_trend(history, "behavioral_alignment", higher_is_better=True, threshold=6.0),
            "fatigue_risk": _guardian_metric_trend(history, "fatigue_risk", higher_is_better=False, threshold=6.0),
            "uncertainty_score": _guardian_metric_trend(history, "uncertainty_score", higher_is_better=False, threshold=6.0),
            "switching_index": _guardian_metric_trend(history, "switching_index", higher_is_better=False, threshold=6.0),
            "drift_trend": _guardian_metric_trend(history, "drift_trend", higher_is_better=False, threshold=6.0),
        },
        "vs_baseline": _guardian_baseline_delta(latest_state, baseline),
    }


def _extract_guardian_sensor_fields(payload):
    payload = _ensure_payload_dict(payload)
    extracted = {}
    for field, aliases in GUARDIAN_SENSOR_FIELD_ALIASES.items():
        value = _first_present_value(payload, aliases)
        if value is None:
            continue
        if field == "scene_signal_active":
            extracted[field] = _safe_bool(value, default=False)
            continue
        parsed = _optional_score_100(value)
        if parsed is not None:
            extracted[field] = parsed
    return extracted


def _guardian_sensor_snapshot_payload(snapshot):
    snapshot = _ensure_payload_dict(snapshot)
    result = {}
    for field in GUARDIAN_SENSOR_FIELD_ALIASES:
        value = snapshot.get(field)
        if field == "scene_signal_active":
            if isinstance(value, bool):
                result[field] = value
            continue
        if value in (None, ""):
            continue
        result[field] = value
    return result


def _compute_guardian_switching_index(snapshot, focus_signals):
    snapshot = snapshot if isinstance(snapshot, dict) else {}
    focus_signals = focus_signals if isinstance(focus_signals, list) else []
    score = 0.0
    for item in focus_signals[-6:]:
        if not isinstance(item, dict):
            continue
        signal_type = _normalize_guardian_challenge(item.get("signal_type"))
        weight = GUARDIAN_SWITCH_SIGNAL_WEIGHTS.get(signal_type, 0.0)
        if weight <= 0:
            continue
        severity = _normalize_severity(item.get("severity"))
        multiplier = 1.0 if severity == "high" else 0.75 if severity == "medium" else 0.45
        if _safe_bool(item.get("resolved"), default=False):
            multiplier *= 0.45
        score += weight * multiplier
    if snapshot.get("distraction"):
        score += 16.0
    signal_score = round(max(0.0, min(100.0, score)), 1)
    scene_switch_rate = _optional_score_100(snapshot.get("scene_switch_rate"))
    movement_intensity = _optional_score_100(snapshot.get("movement_intensity"))
    combined_drift = _optional_score_100(snapshot.get("combined_drift"))
    derived = _weighted_average(
        [
            (signal_score, 0.46),
            (scene_switch_rate, 0.28),
            (movement_intensity, 0.16),
            (combined_drift, 0.10),
        ]
    )
    if derived is None:
        return signal_score
    return round(max(0.0, min(100.0, derived)), 1)


def _compute_guardian_drift_trend(snapshot, recent_history):
    snapshot = snapshot if isinstance(snapshot, dict) else {}
    recent_history = [item for item in (recent_history or []) if isinstance(item, dict)]
    combined_drift = _optional_score_100(snapshot.get("combined_drift"))
    orientation_drift = _optional_score_100(snapshot.get("orientation_drift"))
    movement_intensity = _optional_score_100(snapshot.get("movement_intensity"))
    switching_index = _optional_score_100(snapshot.get("switching_index"))
    if not recent_history:
        baseline = _weighted_average(
            [
                (combined_drift, 0.34),
                (orientation_drift, 0.26),
                (switching_index, 0.22),
                (movement_intensity, 0.18),
            ]
        )
        if baseline is None:
            baseline = 0.0
            if _safe_text(snapshot.get("behavioral_level"), max_length=40).lower() == "drifting":
                baseline += 18.0
            if _safe_text(snapshot.get("behavioral_level"), max_length=40).lower() == "misaligned":
                baseline += 28.0
            if _safe_text(snapshot.get("load_level"), max_length=40).lower() == "medium":
                baseline += 14.0
            if _safe_text(snapshot.get("load_level"), max_length=40).lower() == "high":
                baseline += 24.0
        return round(min(100.0, baseline), 1)

    previous = recent_history[-1]
    focus_drop = max(0.0, _safe_float(previous.get("focus_score"), default=0.0) - _safe_float(snapshot.get("focus_score"), default=0.0))
    load_rise = max(0.0, _safe_float(snapshot.get("cognitive_load"), default=0.0) - _safe_float(previous.get("cognitive_load"), default=0.0))
    alignment_drop = max(
        0.0,
        _safe_float(previous.get("behavioral_alignment"), default=100.0) - _safe_float(snapshot.get("behavioral_alignment"), default=100.0),
    )
    fatigue_rise = max(0.0, _safe_float(snapshot.get("fatigue_risk"), default=0.0) - _safe_float(previous.get("fatigue_risk"), default=0.0))
    drift_change = max(0.0, combined_drift - _safe_float(previous.get("combined_drift"), default=0.0)) if combined_drift is not None else 0.0
    trend = (focus_drop * 0.24) + (load_rise * 0.22) + (alignment_drop * 0.18) + (fatigue_rise * 0.12) + (drift_change * 0.24)
    return round(max(0.0, min(100.0, trend)), 1)


def _finalize_guardian_snapshot(snapshot, recent_history=None, focus_signals=None):
    snapshot = copy.deepcopy(_ensure_payload_dict(snapshot))
    snapshot.update(_extract_guardian_sensor_fields(snapshot))
    task_mode = _normalize_guardian_task_mode(snapshot.get("task_mode")) or "reading"
    snapshot["task_mode"] = task_mode
    scene_signal_active = _safe_bool(
        snapshot.get("scene_signal_active"),
        default=bool(_guardian_sensor_snapshot_payload(snapshot)),
    )
    snapshot["scene_signal_active"] = scene_signal_active

    stability = _optional_score_100(snapshot.get("stability"))
    combined_drift = _optional_score_100(snapshot.get("combined_drift"))
    orientation_drift = _optional_score_100(snapshot.get("orientation_drift"))
    movement_intensity = _optional_score_100(snapshot.get("movement_intensity"))
    scene_text_score = _optional_score_100(snapshot.get("scene_text_score"))
    scene_stability_score = _optional_score_100(snapshot.get("scene_stability_score"))
    scene_switch_rate = _optional_score_100(snapshot.get("scene_switch_rate"))
    study_surface_score = _optional_score_100(snapshot.get("study_surface_score"))
    scene_lock_score = _optional_score_100(snapshot.get("scene_lock_score"))
    blur_score = _optional_score_100(snapshot.get("blur_score"))
    brightness_score = _optional_score_100(snapshot.get("brightness_score"))
    external_uncertainty = _optional_score_100(snapshot.get("external_uncertainty"))

    focus_score = _optional_score_100(snapshot.get("focus_score"))
    if focus_score is None:
        focus_score = _level_to_score(snapshot.get("focus_level"))

    stress_score = _optional_score_100(snapshot.get("stress_score"))
    if stress_score is None:
        stress_score = _level_to_score(snapshot.get("stress_level"))
    if stress_score is not None:
        snapshot["stress_score"] = stress_score

    clarity_score = _optional_score_100(snapshot.get("clarity_score"))
    if clarity_score is None:
        clarity_score = _level_to_score(snapshot.get("comprehension_level"))
    if clarity_score is not None:
        snapshot["clarity_score"] = clarity_score

    fatigue_risk = _optional_score_100(snapshot.get("fatigue_risk"))
    if fatigue_risk is None:
        fatigue_risk = _level_to_score(snapshot.get("energy_level"), invert=True)
    if fatigue_risk is not None:
        snapshot["fatigue_risk"] = fatigue_risk

    behavioral_alignment = _optional_score_100(snapshot.get("behavioral_alignment"))
    if behavioral_alignment is None and focus_score is not None:
        penalty = 0.0
        if snapshot.get("distraction"):
            penalty += 24.0
        if snapshot.get("support_needed"):
            penalty += 10.0
        behavioral_alignment = round(max(0.0, focus_score - penalty), 1)
    if behavioral_alignment is None:
        behavioral_alignment = _weighted_average(
            [
                (max(0.0, 100.0 - (orientation_drift or 0.0)) if orientation_drift is not None else None, 0.24),
                (max(0.0, 100.0 - (scene_switch_rate or 0.0)) if scene_switch_rate is not None else None, 0.14),
                (max(0.0, 100.0 - (combined_drift or 0.0)) if combined_drift is not None else None, 0.12),
                (max(0.0, 100.0 - (movement_intensity or 0.0)) if movement_intensity is not None else None, 0.10),
                (scene_lock_score, 0.18),
                (study_surface_score, 0.14),
                (scene_stability_score, 0.08),
                (stability, 0.10),
            ]
        )
    if behavioral_alignment is not None:
        snapshot["behavioral_alignment"] = behavioral_alignment

    uncertainty_score = _optional_score_100(snapshot.get("uncertainty_score"))
    if uncertainty_score is None:
        confidence_score = _optional_score_100(snapshot.get("confidence_score"))
        if confidence_score is not None:
            uncertainty_score = round(max(0.0, 100.0 - confidence_score), 1)
        elif clarity_score is not None:
            uncertainty_score = round(
                max(0.0, min(100.0, 100.0 - clarity_score + (10.0 if snapshot.get("support_needed") else 0.0))),
                1,
            )
    if uncertainty_score is None:
        blur_penalty = None if blur_score is None else round(max(0.0, min(100.0, (22.0 - blur_score) * 4.5)), 1)
        brightness_penalty = None
        if brightness_score is not None:
            if brightness_score < 14.0:
                brightness_penalty = round(min(100.0, (14.0 - brightness_score) * 5.2), 1)
            elif brightness_score > 88.0:
                brightness_penalty = round(min(100.0, (brightness_score - 88.0) * 4.8), 1)
            else:
                brightness_penalty = 0.0
        uncertainty_score = _weighted_average(
            [
                (external_uncertainty, 0.28),
                (blur_penalty, 0.14),
                (brightness_penalty, 0.10),
                (max(0.0, 100.0 - (scene_stability_score or 100.0)) if scene_stability_score is not None else None, 0.16),
                (max(0.0, 100.0 - (study_surface_score or 100.0)) if study_surface_score is not None else None, 0.10),
                (max(0.0, 100.0 - (scene_lock_score or 100.0)) if scene_lock_score is not None else None, 0.08),
                (max(0.0, 100.0 - (clarity_score or 100.0)) if clarity_score is not None else None, 0.06),
                (movement_intensity, 0.04),
                (orientation_drift, 0.04),
            ]
        )
        if uncertainty_score is not None and scene_signal_active and scene_lock_score is not None:
            uncertainty_score = round(max(0.0, uncertainty_score - (scene_lock_score * 0.06)), 1)
    if uncertainty_score is not None:
        snapshot["uncertainty_score"] = uncertainty_score

    cognitive_load = _optional_score_100(snapshot.get("cognitive_load"))
    if cognitive_load is None:
        components = []
        if stress_score is not None:
            components.append(stress_score * 0.55)
        if clarity_score is not None:
            components.append((100.0 - clarity_score) * 0.35)
        if snapshot.get("distraction"):
            components.append(12.0)
        if snapshot.get("support_needed"):
            components.append(8.0)
        if components:
            cognitive_load = round(max(0.0, min(100.0, sum(components))), 1)
    if cognitive_load is None:
        cognitive_load = _weighted_average(
            [
                (stress_score, 0.22),
                (fatigue_risk, 0.14),
                (max(0.0, 100.0 - (clarity_score or 100.0)) if clarity_score is not None else None, 0.14),
                (orientation_drift, 0.14),
                (movement_intensity, 0.08),
                (scene_switch_rate, 0.10),
                (max(0.0, 100.0 - (scene_stability_score or 100.0)) if scene_stability_score is not None else None, 0.08),
                (max(0.0, 100.0 - (scene_lock_score or 100.0)) if scene_lock_score is not None else None, 0.06),
                (max(0.0, 100.0 - (study_surface_score or 100.0)) if study_surface_score is not None else None, 0.04),
            ]
        )
    if cognitive_load is not None:
        snapshot["cognitive_load"] = cognitive_load

    if focus_score is None and behavioral_alignment is not None and cognitive_load is not None:
        focus_score = round(max(0.0, min(100.0, (behavioral_alignment * 0.65) + ((100.0 - cognitive_load) * 0.35))), 1)
    if focus_score is not None:
        snapshot["focus_score"] = focus_score

    snapshot["behavioral_level"] = _safe_text(snapshot.get("behavioral_level"), max_length=40).lower() or _derive_guardian_behavioral_level(
        snapshot.get("behavioral_alignment"),
        task_mode=task_mode,
    )
    snapshot["fatigue_level"] = _safe_text(snapshot.get("fatigue_level"), max_length=40).lower() or _derive_guardian_fatigue_level(
        snapshot.get("fatigue_risk"),
        task_mode=task_mode,
    )
    snapshot["confidence_level"] = _safe_text(snapshot.get("confidence_level"), max_length=40).lower() or _derive_guardian_confidence_level(
        snapshot.get("uncertainty_score"),
        task_mode=task_mode,
    )
    snapshot["load_level"] = _safe_text(snapshot.get("load_level"), max_length=40).lower() or _derive_guardian_load_level(
        snapshot.get("cognitive_load"),
        task_mode=task_mode,
    )
    snapshot["switching_index"] = _safe_score_100(
        snapshot.get("switching_index"),
        default=_compute_guardian_switching_index(snapshot, focus_signals),
    )
    snapshot["drift_trend"] = _safe_score_100(
        snapshot.get("drift_trend"),
        default=_compute_guardian_drift_trend(snapshot, recent_history),
    )
    snapshot["state_hint"] = _normalize_guardian_state_hint(snapshot.get("state_hint")) or _derive_guardian_state_hint(snapshot)
    snapshot["load_reason"] = _safe_text(snapshot.get("load_reason"), max_length=220) or _derive_guardian_load_reason(snapshot)
    return snapshot


def _default_guardian_difficulty_tracker():
    return {
        "event_counter": 0,
        "candidate_label": "",
        "candidate_reason": "",
        "candidate_rank": 0,
        "candidate_count": 0,
        "stable_count": 0,
        "active_event": {},
    }


def _guardian_event_status(rank):
    if rank >= 2:
        return "high"
    if rank == 1:
        return "medium"
    return "low"


def _guardian_event_review_note(event):
    if _safe_text(event.get("primary_label"), max_length=80).lower() == "productive struggle":
        return "Review this segment as a challenge point: effort stayed aligned, so the difficulty is likely conceptual rather than pure distraction."
    if event.get("severity") == "high":
        return "Review this segment first: load rose enough to trigger a high-priority study-state event."
    return "Review this segment: sustained rising load suggests a meaningful learning-state difficulty point."


def _guardian_difficulty_public_event(event, status="active"):
    event = event if isinstance(event, dict) else {}
    if not event:
        return {}
    return {
        "event_id": _safe_int(event.get("event_id"), default=0),
        "status": status,
        "severity": _safe_text(event.get("severity"), max_length=20) or "medium",
        "primary_label": _safe_text(event.get("primary_label"), max_length=120),
        "trigger_reason": _safe_text(event.get("trigger_reason"), max_length=220),
        "start_timestamp": _safe_text(event.get("start_timestamp"), max_length=40),
        "end_timestamp": _safe_text(event.get("end_timestamp"), max_length=40),
        "sample_count": _safe_int(event.get("sample_count"), default=0),
        "task_mode": _safe_text(event.get("task_mode"), max_length=40),
        "peak_load": _optional_score_100(event.get("peak_load")),
        "min_focus": _optional_score_100(event.get("min_focus")),
        "highest_switching_index": _optional_score_100(event.get("highest_switching_index")),
        "review_note": _safe_text(event.get("review_note"), max_length=260) or _guardian_event_review_note(event),
    }


def _guardian_event_rank(snapshot, signal=None):
    snapshot = snapshot if isinstance(snapshot, dict) else {}
    signal = signal if isinstance(signal, dict) else {}
    task_mode = _normalize_guardian_task_mode(snapshot.get("task_mode")) or "reading"
    profile = _guardian_task_profile(task_mode)
    state_hint = _normalize_guardian_state_hint(snapshot.get("state_hint"))
    load_level = _safe_text(snapshot.get("load_level"), max_length=40).lower()
    fatigue_level = _safe_text(snapshot.get("fatigue_level"), max_length=40).lower()
    switching_index = _safe_score_100(snapshot.get("switching_index"), default=0.0)
    signal_severity = _normalize_severity(signal.get("severity")) if signal else "low"
    signal_type = _normalize_guardian_challenge(signal.get("signal_type")) if signal else ""
    label = _guardian_state_hint_label(state_hint)
    reason = _safe_text(snapshot.get("load_reason"), max_length=220)

    if state_hint == "productive_struggle":
        return 1, "Productive struggle", reason or "Effort is high but still aligned."
    if (
        load_level == "high"
        or fatigue_level == "high"
        or switching_index >= profile["switching_high"]
        or signal_severity == "high"
        or state_hint in {"fatigue_risk", "off_task_risk"}
    ):
        if signal_type:
            label = signal_type.title()
        return 2, label, reason
    if (
        load_level == "medium"
        or fatigue_level == "medium"
        or signal_severity == "medium"
        or state_hint in {"load_rising", "signal_check"}
    ):
        if signal_type and label == "Stable learning state":
            label = signal_type.title()
        return 1, label, reason
    return 0, label, reason


def _update_guardian_difficulty_tracking(state, snapshot=None, signal=None, recorded_at=""):
    state = _ensure_payload_dict(state)
    tracker = state.get("difficulty_tracker")
    if not isinstance(tracker, dict):
        tracker = _default_guardian_difficulty_tracker()
    else:
        defaults = _default_guardian_difficulty_tracker()
        for key, value in defaults.items():
            tracker.setdefault(key, copy.deepcopy(value))
    events = [item for item in state.get("difficulty_events", []) if isinstance(item, dict)]

    latest_snapshot = snapshot if isinstance(snapshot, dict) else _ensure_payload_dict(state.get("latest_state"))
    rank, label, reason = _guardian_event_rank(latest_snapshot, signal=signal)
    severity = _guardian_event_status(rank)
    timestamp = _safe_text(recorded_at, max_length=40) or _now_iso()

    active_event = tracker.get("active_event") if isinstance(tracker.get("active_event"), dict) else {}
    if not active_event:
        if rank == 0:
            tracker["candidate_label"] = ""
            tracker["candidate_reason"] = ""
            tracker["candidate_rank"] = 0
            tracker["candidate_count"] = 0
            tracker["stable_count"] = tracker.get("stable_count", 0) + 1
            tracker["active_event"] = {}
            state["difficulty_tracker"] = tracker
            state["difficulty_events"] = events[-MAX_HISTORY:]
            return None

        if label == tracker.get("candidate_label"):
            tracker["candidate_count"] = _safe_int(tracker.get("candidate_count"), default=0) + 1
        else:
            tracker["candidate_label"] = label
            tracker["candidate_reason"] = reason
            tracker["candidate_count"] = 1
        tracker["candidate_rank"] = max(_safe_int(tracker.get("candidate_rank"), default=0), rank)
        tracker["candidate_reason"] = reason or tracker.get("candidate_reason", "")
        tracker["stable_count"] = 0

        trigger_key = "high" if tracker["candidate_rank"] >= 2 else "medium"
        if tracker["candidate_count"] >= GUARDIAN_DIFFICULTY_TRIGGER_COUNTS[trigger_key]:
            tracker["event_counter"] = _safe_int(tracker.get("event_counter"), default=0) + 1
            tracker["active_event"] = {
                "event_id": tracker["event_counter"],
                "severity": "high" if tracker["candidate_rank"] >= 2 else "medium",
                "primary_label": tracker.get("candidate_label") or label,
                "trigger_reason": tracker.get("candidate_reason") or reason,
                "start_timestamp": timestamp,
                "end_timestamp": timestamp,
                "sample_count": 1,
                "task_mode": _safe_text(latest_snapshot.get("task_mode"), max_length=40),
                "peak_load": _safe_score_100(latest_snapshot.get("cognitive_load"), default=0.0),
                "min_focus": _safe_score_100(latest_snapshot.get("focus_score"), default=100.0),
                "highest_switching_index": _safe_score_100(latest_snapshot.get("switching_index"), default=0.0),
            }
            tracker["candidate_label"] = ""
            tracker["candidate_reason"] = ""
            tracker["candidate_rank"] = 0
            tracker["candidate_count"] = 0
        state["difficulty_tracker"] = tracker
        state["difficulty_events"] = events[-MAX_HISTORY:]
        return _guardian_difficulty_public_event(tracker.get("active_event", {}), status="active")

    active_event["end_timestamp"] = timestamp
    active_event["sample_count"] = _safe_int(active_event.get("sample_count"), default=0) + 1
    active_event["peak_load"] = max(
        _safe_float(active_event.get("peak_load"), default=0.0),
        _safe_float(latest_snapshot.get("cognitive_load"), default=0.0),
    )
    active_event["min_focus"] = min(
        _safe_float(active_event.get("min_focus"), default=100.0),
        _safe_float(latest_snapshot.get("focus_score"), default=100.0),
    )
    active_event["highest_switching_index"] = max(
        _safe_float(active_event.get("highest_switching_index"), default=0.0),
        _safe_float(latest_snapshot.get("switching_index"), default=0.0),
    )
    if rank >= 2:
        active_event["severity"] = "high"
    if rank > 0 and label:
        active_event["primary_label"] = label
    if rank > 0 and reason:
        active_event["trigger_reason"] = reason

    if rank == 0:
        tracker["stable_count"] = _safe_int(tracker.get("stable_count"), default=0) + 1
        if tracker["stable_count"] >= GUARDIAN_DIFFICULTY_TRIGGER_COUNTS["resolve"]:
            resolved_event = copy.deepcopy(active_event)
            resolved_event["review_note"] = _guardian_event_review_note(resolved_event)
            _append_limited(events, resolved_event)
            tracker["active_event"] = {}
            tracker["stable_count"] = 0
            state["difficulty_events"] = events[-MAX_HISTORY:]
            state["difficulty_tracker"] = tracker
            return _guardian_difficulty_public_event(resolved_event, status="resolved")
    else:
        tracker["stable_count"] = 0
        tracker["active_event"] = active_event

    state["difficulty_events"] = events[-MAX_HISTORY:]
    state["difficulty_tracker"] = tracker
    return _guardian_difficulty_public_event(active_event, status="active")


def _interface_contract(capability, event_type, operation=""):
    return {
        "capability": capability,
        "event_type": event_type,
        "operation": operation or "",
        "supported_event_types": list(SUPPORTED_EVENT_TYPES),
        "supported_state_update_operations": list(CAPABILITY_STATE_UPDATE_OPERATIONS.get(capability, ())),
    }


def _routing_metadata(capability, event_type, operation=""):
    return {
        "capability": capability,
        "event_type": event_type,
        "operation": operation or "",
    }


def _resolve_capability(payload, event_type=""):
    payload = _ensure_payload_dict(payload)
    explicit = (
        payload.get("capability")
        or payload.get("module")
        or payload.get("feature")
        or payload.get("skill_area")
        or payload.get("companion_mode")
    )
    capability = _normalize_capability(explicit)
    if capability:
        return capability

    operation = _safe_text(payload.get("operation"), max_length=80).lower()
    if operation in REFLECTION_OPERATIONS:
        return CAPABILITY_REFLECTION
    if operation in GUARDIAN_OPERATIONS:
        return CAPABILITY_GUARDIAN
    for candidate_capability, aliases in OPERATION_ALIASES.items():
        if operation in aliases:
            return candidate_capability

    inferred_from_payload = _infer_capability_from_payload(payload, event_type=event_type)
    if inferred_from_payload:
        return inferred_from_payload

    if event_type == "text_chat":
        return _infer_capability_from_message(payload.get("message") or payload.get("text"))

    return CAPABILITY_PRESENTATION


def _normalize_presentation_payload(payload, event_type):
    payload = copy.deepcopy(_ensure_payload_dict(payload))
    if event_type == "text_chat":
        payload["message"] = _safe_text(
            _first_present_value(payload, ("message", "text", "prompt")),
            max_length=2000,
            preserve_lines=True,
        )
        return payload

    if event_type == "state_update":
        raw_operation = _safe_text(payload.get("operation"), max_length=80).lower()
        if not raw_operation:
            if _first_present_value(payload, ("gesture", "button", "rokid_action", "command", "control_action", "action")):
                raw_operation = "presentation_control"
            elif _first_present_value(payload, ("transcript_excerpt", "transcript", "transcript_text", "section_timings", "section_times")):
                raw_operation = "record_rehearsal"
            elif _first_present_value(payload, ("task_text", "assignment_text", "brief_text", "prompt_text")):
                raw_operation = "extract_intake"
            elif _first_present_value(payload, ("section_id", "card_id", "slide_id")) and _first_present_value(
                payload,
                ("outline", "speaker_notes", "teleprompter_script", "cue_cards"),
            ):
                raw_operation = "update_script_section"
        operation = _canonical_operation(CAPABILITY_PRESENTATION, raw_operation)
        payload["operation"] = operation
        if operation == "extract_intake":
            payload["task_text"] = _safe_text(
                _first_present_value(payload, ("task_text", "assignment_text", "brief_text", "prompt_text")),
                max_length=4000,
                preserve_lines=True,
            )
        elif operation == "presentation_control":
            payload["action"] = _normalize_control_action(
                _first_present_value(payload, ("action", "command", "control_action", "gesture", "button", "rokid_action"))
            )
            payload["control_source"] = _safe_text(
                _first_present_value(payload, ("control_source", "input_source", "source", "device_source")),
                max_length=40,
            ) or payload.get("control_source", "")
        elif operation == "record_rehearsal":
            transcript_source = _first_present_value(payload, ("transcript_excerpt", "transcript", "transcript_text"))
            if transcript_source is not None:
                payload["transcript_excerpt"] = _safe_text(transcript_source, max_length=4000, preserve_lines=True)
            section_timings = _first_present_value(payload, ("section_timings", "section_times", "timings_by_section"))
            if section_timings is not None:
                payload["section_timings"] = section_timings
        elif operation == "update_script_section":
            section_id = _first_present_value(payload, ("section_id", "card_id", "slide_id"))
            if section_id is not None:
                payload["section_id"] = _safe_text(section_id, max_length=80)
            slide_index = _first_present_value(payload, ("slide_index", "section_index"))
            if slide_index is not None:
                payload["slide_index"] = slide_index
        return payload

    if event_type == "difficulty_event":
        payload["challenge"] = _safe_text(
            _first_present_value(payload, ("challenge", "difficulty", "blocker", "obstacle")),
            max_length=180,
        )
        payload["context"] = _safe_text(
            _first_present_value(payload, ("context", "note", "details")),
            max_length=1200,
            preserve_lines=True,
        )
        return payload

    if event_type == "session_review":
        payload["review_scope"] = _normalize_review_scope(_first_present_value(payload, ("review_scope", "scope")), "mission")
    return payload


def _normalize_reflection_payload(payload, event_type):
    payload = copy.deepcopy(_ensure_payload_dict(payload))
    if event_type == "text_chat":
        payload["message"] = _safe_text(
            _first_present_value(payload, ("message", "text", "prompt")),
            max_length=2000,
            preserve_lines=True,
        )
        payload["learner_note"] = _safe_text(
            _first_present_value(payload, ("learner_note", "note")),
            max_length=1200,
            preserve_lines=True,
        )
        payload["next_goal"] = _safe_text(
            _first_present_value(payload, ("next_goal", "goal")),
            max_length=240,
            preserve_lines=True,
        )
        return payload

    if event_type == "state_update":
        raw_operation = _safe_text(payload.get("operation"), max_length=80).lower()
        if not raw_operation:
            if _first_present_value(payload, ("focus_theme", "theme", "target_habit", "habit")) and not _first_present_value(
                payload,
                ("summary", "session_summary", "lesson", "insight", "what_i_learned"),
            ):
                raw_operation = "set_reflection_focus"
            elif _first_present_value(payload, ("steps", "actions", "next_actions")):
                raw_operation = "plan_next_step"
            else:
                raw_operation = "capture_reflection"
        operation = _canonical_operation(CAPABILITY_REFLECTION, raw_operation)
        payload["operation"] = operation
        payload["learner_note"] = _safe_text(
            _first_present_value(payload, ("learner_note", "note")),
            max_length=1200,
            preserve_lines=True,
        )
        payload["next_goal"] = _safe_text(
            _first_present_value(payload, ("next_goal", "goal")),
            max_length=240,
            preserve_lines=True,
        )
        payload["provider_override"] = _safe_text(
            _first_present_value(payload, ("provider_override", "provider")),
            max_length=40,
        )
        payload["model_override"] = _safe_text(
            _first_present_value(payload, ("model_override", "model")),
            max_length=120,
        )
        payload["use_llm"] = _safe_bool(_first_present_value(payload, ("use_llm", "llm", "model_polish")), default=False)
        if operation == "set_reflection_focus":
            payload["focus_theme"] = _safe_text(
                _first_present_value(payload, ("focus_theme", "theme", "focus", "current_focus")),
                max_length=180,
            )
            payload["current_course"] = _safe_text(
                _first_present_value(payload, ("current_course", "course", "module", "subject")),
                max_length=180,
            )
            payload["target_habit"] = _safe_text(
                _first_present_value(payload, ("target_habit", "habit", "target")),
                max_length=180,
            )
        elif operation in {"capture_reflection", "log_reflection"}:
            payload["what_happened"] = _safe_text(
                _first_present_value(payload, ("what_happened", "summary", "session_summary")),
                max_length=1800,
                preserve_lines=True,
            )
            payload["what_worked"] = _safe_text(
                _first_present_value(payload, ("what_worked", "worked", "win", "wins")),
                max_length=1400,
                preserve_lines=True,
            )
            payload["what_was_hard"] = _safe_text(
                _first_present_value(payload, ("what_was_hard", "blocker", "obstacle", "struggle", "challenge")),
                max_length=1400,
                preserve_lines=True,
            )
            payload["lesson"] = _safe_text(
                _first_present_value(payload, ("lesson", "insight", "what_i_learned")),
                max_length=1400,
                preserve_lines=True,
            )
            payload["next_step"] = _safe_text(
                _first_present_value(payload, ("next_step", "next_action", "action_commitment")),
                max_length=600,
                preserve_lines=True,
            )
        elif operation == "plan_next_step":
            steps = _first_present_value(payload, ("steps", "actions", "next_actions"))
            if steps is not None:
                payload["steps"] = steps
            else:
                payload["next_step"] = _safe_text(
                    _first_present_value(payload, ("next_step", "plan", "next_action")),
                    max_length=1200,
                    preserve_lines=True,
                )
        return payload

    if event_type == "difficulty_event":
        payload["challenge"] = _safe_text(
            _first_present_value(payload, ("challenge", "difficulty", "blocker", "obstacle")),
            max_length=180,
        )
        payload["context"] = _safe_text(
            _first_present_value(payload, ("context", "note", "details")),
            max_length=1200,
            preserve_lines=True,
        )
        return payload

    if event_type == "session_review":
        payload["review_scope"] = _normalize_review_scope(_first_present_value(payload, ("review_scope", "scope")), "reflection")
    return payload


def _normalize_guardian_payload(payload, event_type):
    payload = copy.deepcopy(_ensure_payload_dict(payload))
    if event_type == "text_chat":
        payload["message"] = _safe_text(
            _first_present_value(payload, ("message", "text", "prompt")),
            max_length=2000,
            preserve_lines=True,
        )
        return payload

    if event_type == "state_update":
        raw_operation = _safe_text(payload.get("operation"), max_length=80).lower()
        if not raw_operation:
            if _first_present_value(payload, ("signal_type", "challenge", "category", "signal")):
                raw_operation = "record_focus_signal"
            elif _first_present_value(
                payload,
                (
                    "focus_level",
                    "focus",
                    "attention_score",
                    "focus_score",
                    "cognitive_load",
                    "behavioral_alignment",
                    "fatigue_risk",
                    "uncertainty_score",
                    "state_hint",
                    "stability",
                    "combined_drift",
                    "orientation_drift",
                    "movement_intensity",
                    "switching_index",
                    "drift_trend",
                    "scene_text_score",
                    "scene_stability_score",
                    "scene_switch_rate",
                    "study_surface_score",
                    "scene_lock_score",
                    "blur_score",
                    "brightness_score",
                    "external_uncertainty",
                    "energy_level",
                    "energy",
                    "fatigue_score",
                    "stress_level",
                    "stress",
                    "stress_score",
                ),
            ):
                raw_operation = "record_learning_state"
            elif _first_present_value(payload, ("current_task", "task", "session_goal", "goal", "environment", "course", "task_mode")):
                raw_operation = "set_learning_context"
        operation = _canonical_operation(CAPABILITY_GUARDIAN, raw_operation)
        payload["operation"] = operation
        if operation == "set_learning_context":
            payload["current_task"] = _safe_text(
                _first_present_value(payload, ("current_task", "task", "study_task", "current_focus_task")),
                max_length=220,
            )
            payload["session_goal"] = _safe_text(
                _first_present_value(payload, ("session_goal", "goal", "intended_outcome")),
                max_length=320,
            )
            payload["current_course"] = _safe_text(
                _first_present_value(payload, ("current_course", "course", "module", "subject")),
                max_length=180,
            )
            payload["environment"] = _safe_text(
                _first_present_value(payload, ("environment", "location", "study_environment")),
                max_length=180,
            )
            payload["task_mode"] = _normalize_guardian_task_mode(
                _first_present_value(payload, ("task_mode", "study_mode", "mode", "session_mode"))
            )
        elif operation == "record_learning_state":
            payload["current_task"] = _safe_text(
                _first_present_value(payload, ("current_task", "task", "study_task")),
                max_length=220,
            )
            payload["progress_status"] = _safe_text(
                _first_present_value(payload, ("progress_status", "progress", "status")),
                max_length=180,
            )
            payload["distraction"] = _safe_text(
                _first_present_value(payload, ("distraction", "blocker", "obstacle")),
                max_length=240,
            )
            payload["support_needed"] = _safe_text(
                _first_present_value(payload, ("support_needed", "help_needed", "support")),
                max_length=320,
                preserve_lines=True,
            )
            payload["note"] = _safe_text(
                _first_present_value(payload, ("note", "context", "details")),
                max_length=1200,
                preserve_lines=True,
            )
            payload["environment"] = _safe_text(
                _first_present_value(payload, ("environment", "location", "study_environment")),
                max_length=180,
            )
            payload["current_course"] = _safe_text(
                _first_present_value(payload, ("current_course", "course", "module", "subject")),
                max_length=180,
            )
            payload["task_mode"] = _normalize_guardian_task_mode(
                _first_present_value(payload, ("task_mode", "study_mode", "mode", "session_mode"))
            )
            payload.update(_extract_guardian_sensor_fields(payload))
            for field, aliases in {
                "focus_level": ("focus_level", "focus", "attention_level"),
                "energy_level": ("energy_level", "energy"),
                "stress_level": ("stress_level", "stress", "pressure_level"),
                "comprehension_level": ("comprehension_level", "comprehension", "clarity_level"),
            }.items():
                value = _first_present_value(payload, aliases)
                if value is not None:
                    payload[field] = value
            for field, aliases, invert in (
                ("focus_level", ("attention_score", "focus_score"), False),
                ("energy_level", ("fatigue_score", "fatigue"), True),
                ("stress_level", ("stress_score",), False),
                ("comprehension_level", ("clarity_score", "understanding_score"), False),
            ):
                if payload.get(field) in (None, ""):
                    derived = _score_to_level(_first_present_value(payload, aliases), invert=invert)
                    if derived is not None:
                        payload[field] = derived
            focus_score = _optional_score_100(_first_present_value(payload, ("focus_score", "attention_score")))
            if focus_score is None:
                focus_score = _level_to_score(payload.get("focus_level"))
            if focus_score is not None:
                payload["focus_score"] = focus_score

            stress_score = _optional_score_100(_first_present_value(payload, ("stress_score", "pressure_score")))
            if stress_score is None:
                stress_score = _level_to_score(payload.get("stress_level"))
            if stress_score is not None:
                payload["stress_score"] = stress_score

            clarity_score = _optional_score_100(
                _first_present_value(payload, ("clarity_score", "understanding_score", "comprehension_score"))
            )
            if clarity_score is None:
                clarity_score = _level_to_score(payload.get("comprehension_level"))
            if clarity_score is not None:
                payload["clarity_score"] = clarity_score

            fatigue_risk = _optional_score_100(_first_present_value(payload, ("fatigue_risk", "fatigue_score")))
            if fatigue_risk is None:
                fatigue_risk = _level_to_score(payload.get("energy_level"), invert=True)
            if fatigue_risk is not None:
                payload["fatigue_risk"] = fatigue_risk

            behavioral_alignment = _optional_score_100(
                _first_present_value(payload, ("behavioral_alignment", "behavior_alignment", "alignment_score"))
            )
            if behavioral_alignment is None and focus_score is not None:
                penalty = 0.0
                if payload.get("distraction"):
                    penalty += 24.0
                if payload.get("support_needed"):
                    penalty += 10.0
                behavioral_alignment = round(max(0.0, focus_score - penalty), 1)
            if behavioral_alignment is not None:
                payload["behavioral_alignment"] = behavioral_alignment

            uncertainty_score = _optional_score_100(_first_present_value(payload, ("uncertainty_score", "uncertainty")))
            if uncertainty_score is None:
                confidence_score = _optional_score_100(_first_present_value(payload, ("confidence_score",)))
                if confidence_score is not None:
                    uncertainty_score = round(max(0.0, 100.0 - confidence_score), 1)
                elif clarity_score is not None:
                    uncertainty_score = round(
                        max(0.0, min(100.0, 100.0 - clarity_score + (10.0 if payload.get("support_needed") else 0.0))),
                        1,
                    )
            if uncertainty_score is not None:
                payload["uncertainty_score"] = uncertainty_score

            cognitive_load = _optional_score_100(
                _first_present_value(payload, ("cognitive_load", "load_score", "workload_score", "mental_load", "mental_load_score"))
            )
            if cognitive_load is None:
                components = []
                if stress_score is not None:
                    components.append(stress_score * 0.55)
                if clarity_score is not None:
                    components.append((100.0 - clarity_score) * 0.35)
                if payload.get("distraction"):
                    components.append(12.0)
                if payload.get("support_needed"):
                    components.append(8.0)
                if components:
                    cognitive_load = round(max(0.0, min(100.0, sum(components))), 1)
            if cognitive_load is not None:
                payload["cognitive_load"] = cognitive_load

            preview_snapshot = _finalize_guardian_snapshot(
                {
                    **_extract_guardian_sensor_fields(payload),
                    "task_mode": payload.get("task_mode"),
                    "focus_level": payload.get("focus_level"),
                    "energy_level": payload.get("energy_level"),
                    "stress_level": payload.get("stress_level"),
                    "comprehension_level": payload.get("comprehension_level"),
                    "focus_score": payload.get("focus_score"),
                    "stress_score": payload.get("stress_score"),
                    "clarity_score": payload.get("clarity_score"),
                    "cognitive_load": payload.get("cognitive_load"),
                    "behavioral_alignment": payload.get("behavioral_alignment"),
                    "fatigue_risk": payload.get("fatigue_risk"),
                    "uncertainty_score": payload.get("uncertainty_score"),
                    "distraction": payload.get("distraction"),
                    "support_needed": payload.get("support_needed"),
                    "state_hint": _normalize_guardian_state_hint(
                        _first_present_value(payload, ("state_hint", "state_label", "state_classification", "hint"))
                    ),
                    "load_reason": _safe_text(
                        _first_present_value(payload, ("load_reason", "review_note")),
                        max_length=220,
                    ),
                }
            )
            for field in (
                "task_mode",
                "focus_score",
                "stress_score",
                "clarity_score",
                "cognitive_load",
                "behavioral_alignment",
                "behavioral_level",
                "fatigue_risk",
                "fatigue_level",
                "uncertainty_score",
                "confidence_level",
                "load_level",
                "switching_index",
                "drift_trend",
                "state_hint",
                "load_reason",
            ):
                if preview_snapshot.get(field) not in (None, ""):
                    payload[field] = preview_snapshot.get(field)
        elif operation == "record_focus_signal":
            payload["signal_type"] = _normalize_guardian_challenge(
                _first_present_value(payload, ("signal_type", "challenge", "category", "signal", "device_event_type"))
            )
            payload["note"] = _safe_text(
                _first_present_value(payload, ("note", "context", "why", "details")),
                max_length=1200,
                preserve_lines=True,
            )
        return payload

    if event_type == "difficulty_event":
        payload["challenge"] = _normalize_guardian_challenge(
            _first_present_value(payload, ("challenge", "signal_type", "difficulty", "blocker", "device_event_type"))
        )
        payload["context"] = _safe_text(
            _first_present_value(payload, ("context", "note", "details")),
            max_length=1200,
            preserve_lines=True,
        )
        return payload

    if event_type == "session_review":
        payload["review_scope"] = _normalize_review_scope(_first_present_value(payload, ("review_scope", "scope")), "learning_state")
    return payload


def _normalize_request_payload(payload, event_type):
    safe_payload = copy.deepcopy(_ensure_payload_dict(payload))
    capability = _resolve_capability(safe_payload, event_type=event_type)
    safe_payload["capability"] = capability
    if capability == CAPABILITY_REFLECTION:
        return _normalize_reflection_payload(safe_payload, event_type)
    if capability == CAPABILITY_GUARDIAN:
        return _normalize_guardian_payload(safe_payload, event_type)
    return _normalize_presentation_payload(safe_payload, event_type)


def _slugify(value, fallback):
    lowered = _safe_text(value, max_length=120).lower()
    slug = re.sub(r"[^a-z0-9]+", "_", lowered).strip("_")
    return slug or fallback


def _build_id(prefix):
    return f"{prefix}_{uuid.uuid4().hex[:8]}"


def _empty_store():
    return {
        "missions": [],
        "updated_at": "",
    }


def _ensure_store_dir():
    os.makedirs(DATA_DIR, exist_ok=True)


def _read_store():
    _ensure_store_dir()
    if not os.path.exists(STORE_PATH) or os.stat(STORE_PATH).st_size < 2:
        return _empty_store()
    try:
        with open(STORE_PATH, "r", encoding="utf-8") as handle:
            payload = json.load(handle)
    except (OSError, json.JSONDecodeError):
        return _empty_store()
    if not isinstance(payload, dict):
        return _empty_store()
    payload.setdefault("missions", [])
    payload.setdefault("updated_at", "")
    return payload


def _write_store(store):
    _ensure_store_dir()
    payload = copy.deepcopy(store or _empty_store())
    payload["updated_at"] = _now_iso()
    temp_path = f"{STORE_PATH}.tmp"
    with open(temp_path, "w", encoding="utf-8") as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2)
    os.replace(temp_path, STORE_PATH)


def _find_mission(store, mission_id):
    target_id = str(mission_id or "").strip()
    if not target_id:
        return None
    for mission in store.get("missions", []):
        if str(mission.get("mission_id", "")).strip() == target_id:
            return copy.deepcopy(mission)
    return None


def _upsert_mission(store, mission):
    target_id = str((mission or {}).get("mission_id", "")).strip()
    if not target_id:
        raise ValueError("mission_id is required")
    missions = store.get("missions", [])
    replaced = False
    for index, item in enumerate(missions):
        if str(item.get("mission_id", "")).strip() == target_id:
            missions[index] = copy.deepcopy(mission)
            replaced = True
            break
    if not replaced:
        missions.append(copy.deepcopy(mission))
    store["missions"] = missions


def _append_limited(items, entry):
    items.append(entry)
    if len(items) > MAX_HISTORY:
        del items[:-MAX_HISTORY]


def _normalize_keywords(value):
    if isinstance(value, list):
        items = value
    else:
        items = re.split(r"[;,]", str(value or ""))
    normalized = []
    for item in items:
        keyword = _safe_text(item, max_length=40)
        if keyword:
            normalized.append(keyword)
    return normalized[:8]


def _normalize_section_status(value):
    normalized = _safe_text(value, max_length=20).lower()
    if normalized in {"draft", "ready", "rehearse", "complete"}:
        return normalized
    return "draft"


def _default_sections(target_duration_minutes, deliverable_type="presentation"):
    total_seconds = max(120, _safe_int(round(max(0.0, target_duration_minutes) * 60), default=0))
    if total_seconds <= 0:
        total_seconds = 300

    deliverable = _safe_text(deliverable_type, max_length=120).lower()
    if "poster" in deliverable or "pitch" in deliverable:
        skeleton = [
            ("Opening Hook", "Slide 1", "Open with the core problem and why it matters.", 0.18),
            ("Core Claim", "Slide 2", "State the main idea in one plain sentence.", 0.28),
            ("Evidence", "Slide 3", "Point the audience to the strongest proof or example.", 0.30),
            ("Takeaway", "Slide 4", "Close with the result and invite one short question.", 0.24),
        ]
    elif total_seconds <= 240:
        skeleton = [
            ("Opening", "Slide 1", "Frame the task and preview the structure.", 0.20),
            ("Main Point", "Slide 2", "Explain the key idea without reading full sentences.", 0.32),
            ("Example", "Slide 3", "Slow down and make one example easy to follow.", 0.28),
            ("Conclusion", "Slide 4", "Land the takeaway and pause for audience reaction.", 0.20),
        ]
    elif total_seconds <= 420:
        skeleton = [
            ("Opening", "Slide 1", "Set the topic, goal, and route for the audience.", 0.16),
            ("Background", "Slide 2", "Explain what the audience needs before the main point.", 0.18),
            ("Core Idea", "Slide 3", "State the main argument or method clearly.", 0.24),
            ("Evidence or Example", "Slide 4", "Use one clear example and signpost the transition.", 0.24),
            ("Conclusion", "Slide 5", "Summarize the takeaway and invite one question.", 0.18),
        ]
    else:
        skeleton = [
            ("Opening", "Slide 1", "Give the audience the roadmap and timing expectation.", 0.14),
            ("Context", "Slide 2", "Define the problem or assignment frame.", 0.16),
            ("Point One", "Slide 3", "Teach the first key point with a clean transition.", 0.20),
            ("Point Two", "Slide 4", "Extend the argument with one comparison or detail.", 0.20),
            ("Example", "Slide 5", "Use one concrete example and face the audience at the end.", 0.16),
            ("Conclusion", "Slide 6", "Finish with the takeaway, significance, and question cue.", 0.14),
        ]

    sections = []
    remaining = total_seconds
    for index, (name, slide_anchor, interaction_goal, weight) in enumerate(skeleton, start=1):
        if index == len(skeleton):
            target_seconds = max(15, remaining)
        else:
            target_seconds = max(15, int(round(total_seconds * weight)))
            remaining -= target_seconds
        section_id = _slugify(name, f"section_{index}")
        sections.append(
            {
                "section_id": section_id,
                "title": name,
                "name": name,
                "slide_index": index,
                "slide_title": name,
                "slide_anchor": slide_anchor,
                "interaction_goal": interaction_goal,
                "planned_seconds": target_seconds,
                "target_seconds": target_seconds,
                "outline": "",
                "speaker_notes": "",
                "teleprompter_script": "",
                "cue_cards": "",
                "keywords": [],
                "status": "draft",
            }
        )
    return sections


def _normalize_sections(sections, target_duration_minutes=0.0):
    if not isinstance(sections, list) or not sections:
        return _default_sections(target_duration_minutes)

    normalized = []
    seen_ids = set()
    for index, item in enumerate(sections):
        if isinstance(item, str):
            item = {"title": item}
        if not isinstance(item, dict):
            continue
        fallback_title = f"Section {index + 1}"
        title = _safe_text(item.get("title") or item.get("name") or item.get("heading"), max_length=120) or fallback_title
        section_id = _safe_text(item.get("section_id"), max_length=80) or _slugify(title, f"section_{index + 1}")
        while section_id in seen_ids:
            section_id = _build_id(f"section_{index + 1}")
        seen_ids.add(section_id)
        planned_seconds = max(
            0,
            _safe_int(
                item.get("planned_seconds"),
                default=_safe_int(item.get("target_seconds"), default=0),
            ),
        )
        normalized.append(
            {
                "section_id": section_id,
                "title": title,
                "name": title,
                "slide_index": max(1, _safe_int(item.get("slide_index"), default=index + 1)),
                "slide_title": _safe_text(item.get("slide_title"), max_length=120) or title,
                "slide_anchor": _safe_text(item.get("slide_anchor"), max_length=120),
                "interaction_goal": _safe_text(item.get("interaction_goal"), max_length=240),
                "planned_seconds": planned_seconds,
                "target_seconds": planned_seconds,
                "outline": _safe_text(item.get("outline"), max_length=2400, preserve_lines=True),
                "speaker_notes": _safe_text(item.get("speaker_notes") or item.get("notes"), max_length=4000, preserve_lines=True),
                "teleprompter_script": _safe_text(item.get("teleprompter_script"), max_length=9000, preserve_lines=True),
                "cue_cards": _safe_text(item.get("cue_cards"), max_length=1800, preserve_lines=True),
                "keywords": _normalize_keywords(item.get("keywords")),
                "status": _normalize_section_status(item.get("status")),
            }
        )

    if not normalized:
        return _default_sections(target_duration_minutes)

    if all(item.get("planned_seconds", 0) <= 0 for item in normalized):
        total_seconds = max(180, _safe_int(round(max(0.0, target_duration_minutes) * 60), default=0))
        even_seconds = max(30, int(total_seconds / len(normalized)))
        for item in normalized:
            item["planned_seconds"] = even_seconds
            item["target_seconds"] = even_seconds

    normalized.sort(key=lambda entry: (entry.get("slide_index", 0), entry.get("section_id", "")))
    return normalized


def _word_count(text):
    return len([word for word in str(text or "").split() if word.strip()])


def _format_mmss(total_seconds):
    safe_seconds = max(0, _safe_int(total_seconds, default=0))
    minutes, seconds = divmod(safe_seconds, 60)
    return f"{minutes}:{seconds:02d}"


def _estimated_script_words(section):
    outline_words = _word_count(section.get("outline", ""))
    teleprompter_words = _word_count(section.get("teleprompter_script", ""))
    notes_words = _word_count(section.get("speaker_notes", ""))
    cue_words = _word_count(section.get("cue_cards", ""))
    if teleprompter_words > 0:
        return int(round(outline_words * 0.2 + teleprompter_words + cue_words * 0.2))
    return int(round(outline_words * 0.45 + notes_words + cue_words * 0.7))


def _estimate_section_seconds(section):
    weighted_words = _estimated_script_words(section)
    if weighted_words <= 0:
        return 0
    return max(10, int(round(weighted_words / WORDS_PER_SECOND)))


def _section_duration_hint(estimated_seconds, target_seconds):
    target_seconds = max(0, _safe_int(target_seconds, default=0))
    estimated_seconds = max(0, _safe_int(estimated_seconds, default=0))
    if target_seconds <= 0:
        return {
            "status": "unknown",
            "note": "Set a target time for a clearer section pacing check.",
        }
    if estimated_seconds <= 0:
        return {
            "status": "empty",
            "note": "This section still needs your own outline or notes.",
        }
    ratio = estimated_seconds / max(target_seconds, 1)
    if ratio >= 1.2:
        return {
            "status": "long",
            "note": f"Estimated at {_format_mmss(estimated_seconds)}, which looks longer than the target window.",
        }
    if ratio <= 0.7:
        return {
            "status": "short",
            "note": f"Estimated at {_format_mmss(estimated_seconds)}, which may be too short for the target window.",
        }
    return {
        "status": "balanced",
        "note": f"Estimated at {_format_mmss(estimated_seconds)} and roughly aligned with the target window.",
    }


def _teleprompter_source(section):
    for field in ("teleprompter_script", "speaker_notes", "cue_cards", "outline", "slide_anchor"):
        value = _safe_text(section.get(field, ""), max_length=12000, preserve_lines=True)
        if value:
            return field, value
    return "empty", ""


def _split_long_unit(text, max_words=38):
    words = [word for word in str(text or "").split() if word]
    if not words:
        return []
    chunks = []
    for start in range(0, len(words), max_words):
        piece = " ".join(words[start:start + max_words]).strip()
        if piece:
            chunks.append(piece)
    return chunks


def _teleprompter_chunks(section, max_words=38, max_chars=280):
    source, raw_text = _teleprompter_source(section)
    text = _safe_text(raw_text, max_length=12000, preserve_lines=True)
    if not text:
        return {
            "source": source,
            "text": "",
            "chunks": [],
        }
    paragraphs = [part.strip() for part in re.split(r"\n{2,}", text) if part.strip()]
    if not paragraphs:
        paragraphs = [text]
    chunks = []
    for paragraph in paragraphs:
        units = [unit.strip() for unit in re.split(r"(?<=[\.\?!])\s+|\n+", paragraph) if unit.strip()]
        if not units:
            units = [paragraph.strip()]
        current = ""
        current_words = 0
        for unit in units:
            split_units = [unit]
            if _word_count(unit) > max_words or len(unit) > max_chars:
                split_units = _split_long_unit(unit, max_words=max_words)
            for split_unit in split_units:
                split_words = _word_count(split_unit)
                candidate = f"{current} {split_unit}".strip() if current else split_unit
                if current and (current_words + split_words > max_words or len(candidate) > max_chars):
                    chunks.append(current.strip())
                    current = split_unit
                    current_words = split_words
                else:
                    current = candidate
                    current_words = _word_count(candidate)
        if current:
            chunks.append(current.strip())
    return {
        "source": source,
        "text": text,
        "chunks": [_safe_text(item, max_length=600, preserve_lines=True) for item in chunks if item.strip()],
    }


def _teleprompter_state(section, active_chunk_index=0):
    payload = _teleprompter_chunks(section)
    chunks = payload.get("chunks", [])
    chunk_count = len(chunks)
    safe_index = (
        min(max(0, _safe_int(active_chunk_index, default=0)), max(0, chunk_count - 1))
        if chunk_count
        else 0
    )
    return {
        "teleprompter_source": payload.get("source", "empty"),
        "teleprompter_text": payload.get("text", ""),
        "teleprompter_chunks": chunks,
        "active_chunk_index": safe_index,
        "active_chunk_count": chunk_count,
        "active_chunk_text": chunks[safe_index] if chunk_count else "",
        "active_chunk_label": f"{safe_index + 1}/{chunk_count}" if chunk_count else "0/0",
        "previous_chunk_text": chunks[safe_index - 1] if safe_index > 0 else "",
        "next_chunk_text": chunks[safe_index + 1] if safe_index + 1 < chunk_count else "",
        "has_previous_chunk": safe_index > 0,
        "has_next_chunk": safe_index + 1 < chunk_count,
        "chunk_jump_supported": chunk_count > 1,
    }


def _card_brief_payload(section):
    teleprompter = _teleprompter_state(section, active_chunk_index=0)
    return {
        "section_id": section.get("section_id", ""),
        "title": section.get("title", ""),
        "slide_index": _safe_int(section.get("slide_index"), default=0),
        "slide_title": section.get("slide_title", ""),
        "slide_anchor": section.get("slide_anchor", ""),
        "interaction_goal": section.get("interaction_goal", ""),
        "target_seconds": _safe_int(section.get("target_seconds") or section.get("planned_seconds"), default=0),
        "target_label": _format_mmss(section.get("target_seconds") or section.get("planned_seconds")),
        "teleprompter_source": teleprompter.get("teleprompter_source", "empty"),
        "chunk_count": teleprompter.get("active_chunk_count", 0),
        "status": section.get("status", "draft"),
    }


def _card_payload(section, presentation_mode="rehearse", cue_view="visible", active_chunk_index=0):
    if not section:
        return {}
    teleprompter = _teleprompter_state(section, active_chunk_index=active_chunk_index)
    payload = {
        "section_id": section.get("section_id", ""),
        "title": section.get("title", ""),
        "slide_index": _safe_int(section.get("slide_index"), default=0),
        "slide_title": section.get("slide_title", ""),
        "slide_anchor": section.get("slide_anchor", ""),
        "interaction_goal": section.get("interaction_goal", ""),
        "outline": section.get("outline", ""),
        "speaker_notes": section.get("speaker_notes", ""),
        "teleprompter_script": section.get("teleprompter_script", ""),
        "cue_cards": section.get("cue_cards", ""),
        "keywords": copy.deepcopy(section.get("keywords", [])),
        "status": section.get("status", "draft"),
        "target_seconds": _safe_int(section.get("target_seconds") or section.get("planned_seconds"), default=0),
        "target_label": _format_mmss(section.get("target_seconds") or section.get("planned_seconds")),
        "presentation_mode": _normalize_presentation_mode(presentation_mode),
        "cue_view": _normalize_cue_view(cue_view),
        **teleprompter,
    }
    if payload["cue_view"] == "hidden":
        payload["speaker_notes"] = ""
        payload["teleprompter_script"] = ""
        payload["cue_cards"] = ""
    return payload


def _presentation_state_payload(state, sections):
    sections = _normalize_sections(sections)
    state = _normalize_presentation_state(sections, existing=state)
    active_id = _safe_text(state.get("active_section_id"), max_length=80)
    active_section = next((item for item in sections if item.get("section_id") == active_id), sections[0] if sections else {})
    active_card = _card_payload(
        active_section,
        presentation_mode=state.get("presentation_mode", "rehearse"),
        cue_view=state.get("cue_view", "visible"),
        active_chunk_index=state.get("active_chunk_index", 0),
    )
    next_card = {}
    for index, item in enumerate(sections):
        if item.get("section_id") == active_id and index + 1 < len(sections):
            next_card = _card_brief_payload(sections[index + 1])
            break
    return {
        **state,
        "active_card": active_card,
        "next_card": next_card,
        "active_chunk_count": active_card.get("active_chunk_count", 0),
        "active_chunk_text": active_card.get("active_chunk_text", ""),
        "chunk_progress_label": active_card.get("active_chunk_label", "0/0"),
        "previous_chunk_preview": _safe_text(active_card.get("previous_chunk_text", ""), max_length=96),
        "next_chunk_preview": _safe_text(active_card.get("next_chunk_text", ""), max_length=96),
        "chunk_jump_supported": bool(active_card.get("chunk_jump_supported")),
        "available_cards": [_card_brief_payload(item) for item in sections],
    }


def _build_script_summary(sections, target_minutes=0):
    target_total_seconds = sum(max(0, _safe_int(item.get("target_seconds") or item.get("planned_seconds"), default=0)) for item in sections)
    if target_total_seconds <= 0 and _safe_float(target_minutes, default=0) > 0:
        target_total_seconds = int(round(_safe_float(target_minutes, default=0) * 60))

    estimated_total_seconds = 0
    completed_sections = 0
    section_metrics = []
    for section in sections:
        estimated_seconds = _estimate_section_seconds(section)
        estimated_total_seconds += estimated_seconds
        has_core_content = any(
            section.get(field, "").strip()
            for field in ("outline", "speaker_notes", "teleprompter_script", "cue_cards")
        )
        if has_core_content:
            completed_sections += 1
        hint = _section_duration_hint(
            estimated_seconds,
            section.get("target_seconds") or section.get("planned_seconds") or 0,
        )
        section_metrics.append(
            {
                "section_id": section.get("section_id", ""),
                "title": section.get("title", ""),
                "slide_index": _safe_int(section.get("slide_index"), default=0),
                "estimated_seconds": estimated_seconds,
                "estimated_label": _format_mmss(estimated_seconds),
                "target_label": _format_mmss(section.get("target_seconds") or section.get("planned_seconds")),
                "estimated_words": _estimated_script_words(section),
                "duration_hint": hint["status"],
                "duration_note": hint["note"],
                "content_status": "ready" if has_core_content else "empty",
            }
        )

    overall_hint = _section_duration_hint(estimated_total_seconds, target_total_seconds)
    return {
        "section_count": len(sections),
        "completed_sections": completed_sections,
        "target_total_seconds": target_total_seconds,
        "target_total_label": _format_mmss(target_total_seconds),
        "estimated_total_seconds": estimated_total_seconds,
        "estimated_total_label": _format_mmss(estimated_total_seconds),
        "duration_hint": overall_hint["status"],
        "duration_note": overall_hint["note"],
        "section_metrics": section_metrics,
    }


def _distribute_section_seconds(sections, total_duration_seconds):
    safe_total = max(0, _safe_int(total_duration_seconds, default=0))
    if safe_total <= 0 or not sections:
        return []
    target_total = sum(
        max(0, _safe_int(item.get("target_seconds") or item.get("planned_seconds"), default=0))
        for item in sections
    )
    if target_total <= 0:
        even_seconds = int(round(safe_total / max(1, len(sections))))
        return [even_seconds for _ in sections]

    allocated = []
    used = 0
    for index, section in enumerate(sections):
        target_seconds = max(0, _safe_int(section.get("target_seconds") or section.get("planned_seconds"), default=0))
        if index == len(sections) - 1:
            actual_seconds = max(0, safe_total - used)
        else:
            actual_seconds = int(round(safe_total * (target_seconds / target_total)))
            used += actual_seconds
        allocated.append(actual_seconds)
    return allocated


def _normalize_section_timings(sections, section_timings=None, total_duration_seconds=0):
    normalized_sections = _normalize_sections(sections)
    provided = section_timings if isinstance(section_timings, list) else []
    distributed = _distribute_section_seconds(normalized_sections, total_duration_seconds) if not provided else []

    section_map = {}
    slide_map = {}
    for item in provided:
        if not isinstance(item, dict):
            continue
        section_id = _safe_text(item.get("section_id"), max_length=80)
        slide_index = _safe_int(item.get("slide_index"), default=0)
        if section_id:
            section_map[section_id] = item
        if slide_index > 0:
            slide_map[slide_index] = item

    normalized = []
    for index, section in enumerate(normalized_sections):
        raw_entry = section_map.get(section.get("section_id", "")) or slide_map.get(_safe_int(section.get("slide_index"), default=0)) or {}
        actual_seconds = max(
            0,
            _safe_int(
                raw_entry.get("actual_seconds"),
                default=_safe_int(
                    raw_entry.get("duration_seconds"),
                    default=_safe_int(raw_entry.get("seconds"), default=(distributed[index] if distributed else 0)),
                ),
            ),
        )
        target_seconds = max(0, _safe_int(section.get("target_seconds") or section.get("planned_seconds"), default=0))
        hint = _section_duration_hint(actual_seconds, target_seconds) if actual_seconds > 0 else {
            "status": "missing",
            "note": "No measured timing was recorded for this section yet.",
        }
        normalized.append(
            {
                "section_id": section.get("section_id", ""),
                "title": section.get("title", ""),
                "slide_index": _safe_int(section.get("slide_index"), default=0),
                "target_seconds": target_seconds,
                "target_label": _format_mmss(target_seconds),
                "actual_seconds": actual_seconds,
                "actual_label": _format_mmss(actual_seconds),
                "delta_seconds": actual_seconds - target_seconds,
                "delta_label": _format_mmss(abs(actual_seconds - target_seconds)),
                "timing_status": hint["status"],
                "timing_note": hint["note"],
                "notes": _safe_text(raw_entry.get("notes"), max_length=600, preserve_lines=True),
            }
        )
    return normalized


def _section_timing_summary(section_timings):
    if not isinstance(section_timings, list) or not section_timings:
        return {
            "count": 0,
            "covered_sections": 0,
            "overrun_sections": 0,
            "underrun_sections": 0,
            "balanced_sections": 0,
            "largest_overrun": {},
            "largest_underrun": {},
        }

    covered_sections = sum(1 for item in section_timings if _safe_int(item.get("actual_seconds"), default=0) > 0)
    overrun_sections = [item for item in section_timings if item.get("timing_status") == "long"]
    underrun_sections = [item for item in section_timings if item.get("timing_status") == "short"]
    balanced_sections = sum(1 for item in section_timings if item.get("timing_status") == "balanced")
    largest_overrun = max(overrun_sections, key=lambda item: _safe_int(item.get("delta_seconds"), default=0), default={})
    largest_underrun = min(underrun_sections, key=lambda item: _safe_int(item.get("delta_seconds"), default=0), default={})
    return {
        "count": len(section_timings),
        "covered_sections": covered_sections,
        "overrun_sections": len(overrun_sections),
        "underrun_sections": len(underrun_sections),
        "balanced_sections": balanced_sections,
        "largest_overrun": largest_overrun,
        "largest_underrun": largest_underrun,
    }


def _confidence_label(score):
    safe_score = max(0, min(5, _safe_int(score, default=0)))
    if safe_score >= 4:
        return "confident"
    if safe_score == 3:
        return "steady"
    if safe_score == 2:
        return "fragile"
    if safe_score == 1:
        return "very fragile"
    return "unrated"


def _transcript_density_status(word_count, target_minutes):
    if word_count <= 0:
        return "missing"
    target_words = max(1, int(round(max(0.0, _safe_float(target_minutes, default=0.0)) * 60 * WORDS_PER_SECOND)))
    ratio = word_count / target_words
    if ratio < 0.45:
        return "thin"
    if ratio > 1.25:
        return "dense"
    return "balanced"


def _default_fix_for_challenge(challenge, active_section_title="the current section"):
    normalized = _safe_text(challenge, max_length=120).lower()
    if "timing" in normalized:
        return f"Trim one example or shorten one explanation inside {active_section_title} before the next run."
    if "confidence" in normalized or "nervous" in normalized:
        return "Repeat the first 20 seconds three times and mark two breathing pauses."
    if "transition" in normalized:
        return "Add one bridge sentence at the end of the current section and rehearse it aloud."
    if "evidence" in normalized:
        return "Keep one stronger example and remove weaker supporting detail."
    if "question" in normalized or "qa" in normalized:
        return "Prepare a one-sentence answer frame: claim, evidence, takeaway."
    return "Turn this blocker into one concrete revision before the next rehearsal."


def _sentence_list(text):
    return [item.strip() for item in re.split(r"(?<=[\.\?!])\s+|\n+", str(text or "").strip()) if item.strip()]


def _section_role(section):
    combined = _safe_text(
        f"{(section or {}).get('title', '')} {(section or {}).get('interaction_goal', '')}",
        max_length=240,
    ).lower()
    if any(token in combined for token in ("opening", "intro", "hook")):
        return "opening"
    if any(token in combined for token in ("conclusion", "closing", "takeaway")):
        return "conclusion"
    if any(token in combined for token in ("evidence", "example", "proof", "data")):
        return "evidence"
    if any(token in combined for token in ("context", "background")):
        return "context"
    if any(token in combined for token in ("claim", "point", "argument", "core idea", "main point")):
        return "core_argument"
    return "general"


def _section_specific_guidance(section):
    role = _section_role(section)
    title = (section or {}).get("title", "this section")
    mapping = {
        "opening": {
            "focus": "Hook -> context -> roadmap",
            "coach_note": f"For {title}, open with one vivid cue, explain why the topic matters, then preview where you are going.",
            "revision_rule": "Do not spend too long on setup before the audience knows the main direction.",
        },
        "context": {
            "focus": "Only the background the audience actually needs",
            "coach_note": f"For {title}, define the problem quickly and move into the main claim before energy drops.",
            "revision_rule": "Cut details that belong later in the explanation.",
        },
        "core_argument": {
            "focus": "State the claim first, then unpack it",
            "coach_note": f"For {title}, say the main point in one clean sentence before adding explanation.",
            "revision_rule": "Avoid circling around the idea before naming it.",
        },
        "evidence": {
            "focus": "One strong example -> why it matters",
            "coach_note": f"For {title}, choose one example that proves the claim and explain the meaning immediately after it.",
            "revision_rule": "Do not stack multiple examples if one already makes the point.",
        },
        "conclusion": {
            "focus": "Takeaway -> significance -> confident ending",
            "coach_note": f"For {title}, restate the takeaway, say why it matters, and stop cleanly instead of reopening the argument.",
            "revision_rule": "Do not add new content in the last section.",
        },
        "general": {
            "focus": "One section, one clear job",
            "coach_note": f"For {title}, keep one clear purpose and make the transition to the next section explicit.",
            "revision_rule": "If two ideas compete, split them or cut one.",
        },
    }
    guidance = mapping.get(role, mapping["general"])
    return {
        "section_role": role,
        **guidance,
    }


def _dedupe_strings(items):
    seen = set()
    ordered = []
    for item in items:
        key = str(item or "").strip()
        if not key or key in seen:
            continue
        seen.add(key)
        ordered.append(key)
    return ordered


def _transcript_expression_analysis(transcript_text, active_section):
    cleaned = _safe_text(transcript_text, max_length=4000, preserve_lines=True)
    if not cleaned:
        return {
            "status": "missing",
            "issue_count": 0,
            "issues": [],
            "summary": "No transcript excerpt was provided for wording analysis yet.",
        }

    lowered = cleaned.lower()
    sentences = _sentence_list(cleaned)
    words = re.findall(r"[a-zA-Z']+", lowered)
    avg_sentence_words = round(len(words) / max(1, len(sentences)), 1)
    role = _section_role(active_section)
    issues = []

    filler_hits = []
    for phrase in FILLER_PATTERNS:
        count = len(re.findall(rf"(?<![a-z]){re.escape(phrase)}(?![a-z])", lowered))
        if count > 0:
            filler_hits.append({"phrase": phrase, "count": count})
    filler_total = sum(item["count"] for item in filler_hits)
    if filler_total >= 2:
        issues.append(
            {
                "type": "filler_words",
                "severity": "medium",
                "title": "Filler words are interrupting delivery",
                "note": f"Detected fillers such as {', '.join(item['phrase'] for item in filler_hits[:3])}.",
                "recommended_fix": "Replace filler words with a short pause and restart the sentence cleanly.",
            }
        )

    content_words = [
        word
        for word in words
        if len(word) > 3 and word not in TRANSCRIPT_STOPWORDS
    ]
    repeated_terms = [
        term for term, count in Counter(content_words).most_common(5)
        if count >= 3
    ]
    if repeated_terms:
        issues.append(
            {
                "type": "repetition",
                "severity": "medium",
                "title": "Some wording is repeating too much",
                "note": f"Repeated terms include {', '.join(repeated_terms[:3])}.",
                "recommended_fix": "Collapse repeated explanation into one line, then move forward.",
            }
        )

    if avg_sentence_words >= 24:
        issues.append(
            {
                "type": "dense_sentences",
                "severity": "high",
                "title": "Sentences are too dense for spoken delivery",
                "note": f"Average sentence length is about {avg_sentence_words} words.",
                "recommended_fix": "Break one long sentence into two shorter spoken units.",
            }
        )

    signpost_tokens = ("first", "next", "then", "because", "so", "however", "for example", "finally", "overall")
    has_signpost = any(token in lowered for token in signpost_tokens)
    if len(sentences) >= 2 and not has_signpost:
        issues.append(
            {
                "type": "weak_signposting",
                "severity": "medium",
                "title": "The explanation needs clearer signposting",
                "note": "The transcript sample does not show strong transition language.",
                "recommended_fix": "Add one signpost phrase such as 'next', 'for example', or 'overall'.",
            }
        )

    if role == "opening" and not any(token in lowered for token in ("today", "i want", "i will", "this presentation", "this talk")):
        issues.append(
            {
                "type": "weak_opening_frame",
                "severity": "medium",
                "title": "The opening frame is still soft",
                "note": "The audience may not hear the purpose of the talk quickly enough.",
                "recommended_fix": "State the topic and direction explicitly in the first two sentences.",
            }
        )
    if role == "conclusion" and not any(token in lowered for token in ("in summary", "overall", "therefore", "takeaway", "in conclusion", "to conclude")):
        issues.append(
            {
                "type": "weak_conclusion",
                "severity": "medium",
                "title": "The ending does not land the takeaway yet",
                "note": "The sample lacks a clear concluding signal.",
                "recommended_fix": "Add one final takeaway sentence and a clear stopping point.",
            }
        )
    if role == "evidence" and not any(token in lowered for token in ("for example", "for instance", "evidence", "data", "shows", "suggests", "because")):
        issues.append(
            {
                "type": "weak_evidence_link",
                "severity": "medium",
                "title": "The evidence section needs a stronger proof link",
                "note": "The sample does not clearly mark where the proof appears or why it matters.",
                "recommended_fix": "Name the example clearly, then say what it proves in one sentence.",
            }
        )

    status = "stable" if not issues else ("attention_needed" if any(item["severity"] == "high" for item in issues) else "needs_refinement")
    summary = (
        "Transcript wording looks usable for a live rehearsal."
        if not issues
        else f"Transcript analysis found {len(issues)} wording risk(s), led by: {issues[0]['title']}."
    )
    return {
        "status": status,
        "sentence_count": len(sentences),
        "avg_sentence_words": avg_sentence_words,
        "filler_total": filler_total,
        "repeated_terms": repeated_terms[:3],
        "issue_count": len(issues),
        "issues": issues[:4],
        "summary": summary,
    }


def _build_rehearsal_analysis(mission, rehearsal_entry):
    if not rehearsal_entry:
        return {}

    active_section = _active_section(mission)
    duration_minutes = _safe_float(rehearsal_entry.get("duration_minutes"), default=0.0)
    target_minutes = _safe_float(mission.get("target_duration_minutes"), default=0.0)
    actual_seconds = int(round(duration_minutes * 60)) if duration_minutes > 0 else 0
    target_seconds = int(round(target_minutes * 60)) if target_minutes > 0 else 0
    script_summary = _build_script_summary(
        mission.get("script_sections", []),
        target_minutes=mission.get("target_duration_minutes", 0.0),
    )
    section_timing_summary = _section_timing_summary(rehearsal_entry.get("section_timings", []))
    pacing = _section_duration_hint(actual_seconds, target_seconds) if target_seconds > 0 else {
        "status": "unknown",
        "note": "Set a target duration to compare rehearsal pacing.",
    }
    transcript_words = _safe_int(rehearsal_entry.get("transcript_word_count"), default=_word_count(rehearsal_entry.get("transcript_excerpt", "")))
    transcript_density = _transcript_density_status(transcript_words, target_minutes)
    transcript_analysis = _transcript_expression_analysis(rehearsal_entry.get("transcript_excerpt", ""), active_section)
    confidence_score = max(
        _safe_int(rehearsal_entry.get("confidence_level"), default=0),
        _safe_int(rehearsal_entry.get("self_rating"), default=0),
    )

    recommendations = []
    if pacing["status"] == "long":
        recommendations.append("Trim one example or compress one explanation before the next full run.")
    elif pacing["status"] == "short":
        recommendations.append("Add one clarifying sentence or one stronger example to reach the target window.")
    if section_timing_summary.get("largest_overrun"):
        overrun = section_timing_summary["largest_overrun"]
        recommendations.append(
            f"Your biggest overrun is {overrun.get('title', 'one section')}; trim about {overrun.get('delta_label', '0:00')} there first."
        )
    elif section_timing_summary.get("largest_underrun"):
        underrun = section_timing_summary["largest_underrun"]
        recommendations.append(
            f"{underrun.get('title', 'One section')} is running short; add one clarifying line or example there."
        )
    if transcript_density == "thin":
        recommendations.append("Your transcript sample is still thin; capture a fuller rehearsal excerpt for better feedback.")
    elif transcript_density == "dense":
        recommendations.append("The spoken script may be too dense; convert one sentence block into cue words.")
    for issue in transcript_analysis.get("issues", []):
        recommendations.append(issue.get("recommended_fix", "Refine the wording before the next run."))
    if confidence_score and confidence_score <= 2:
        recommendations.append("Stabilize the opening and first transition before changing later slides.")
    if script_summary.get("completed_sections", 0) < script_summary.get("section_count", 0):
        recommendations.append("At least one section still lacks usable speaking material; complete the empty card first.")
    if rehearsal_entry.get("needs_improvement"):
        recommendations.append(_safe_text(rehearsal_entry.get("needs_improvement"), max_length=200))
    if rehearsal_entry.get("next_focus"):
        recommendations.append(_safe_text(rehearsal_entry.get("next_focus"), max_length=200))
    if not recommendations:
        recommendations.append("Keep the structure stable and do one more timed rehearsal with the same outline.")

    delta_seconds = actual_seconds - target_seconds if target_seconds > 0 else 0
    recommendations = _dedupe_strings(recommendations)
    return {
        "timing_status": pacing["status"],
        "timing_note": pacing["note"],
        "timing_delta_seconds": delta_seconds,
        "timing_delta_label": _format_mmss(abs(delta_seconds)),
        "transcript_density": transcript_density,
        "transcript_word_count": transcript_words,
        "active_section_role": _section_role(active_section),
        "active_section_guidance": _section_specific_guidance(active_section),
        "transcript_analysis": transcript_analysis,
        "confidence_label": _confidence_label(confidence_score),
        "script_completion_ratio": (
            round(script_summary.get("completed_sections", 0) / max(1, script_summary.get("section_count", 0)), 2)
        ),
        "section_timing_summary": section_timing_summary,
        "recommendations": recommendations[:4],
    }


def _build_coaching_summary(mission, script_summary, difficulty_events, rehearsal_history):
    latest_difficulty = difficulty_events[-1] if difficulty_events else {}
    latest_rehearsal = rehearsal_history[-1] if rehearsal_history else {}
    rehearsal_analysis = latest_rehearsal.get("analysis", {}) or _build_rehearsal_analysis(mission, latest_rehearsal)
    active_section = _active_section(mission)

    if latest_difficulty:
        priority = latest_difficulty.get("challenge") or "latest blocker"
        coach_message = _safe_text(
            latest_difficulty.get("suggested_fix")
            or _default_fix_for_challenge(priority, active_section.get("title", "the current section")),
            max_length=240,
            preserve_lines=True,
        )
    elif rehearsal_analysis.get("timing_status") == "long":
        priority = "timing"
        coach_message = "Your run is still long. Cut one example or compress one explanation before the next rehearsal."
    elif rehearsal_analysis.get("section_timing_summary", {}).get("largest_overrun"):
        priority = "section pacing"
        largest_overrun = rehearsal_analysis["section_timing_summary"]["largest_overrun"]
        coach_message = (
            f"The main pacing risk is {largest_overrun.get('title', 'one section')}. "
            f"Trim about {largest_overrun.get('delta_label', '0:00')} there first."
        )
    elif script_summary.get("completed_sections", 0) < script_summary.get("section_count", 0):
        priority = "script completion"
        coach_message = "Finish the empty speaking cards first so the next rehearsal measures delivery, not missing content."
    else:
        priority = "delivery flow"
        coach_message = "Keep the structure stable and improve one transition instead of rewriting the whole script."

    return {
        "priority": priority,
        "coach_message": coach_message,
        "confidence_label": rehearsal_analysis.get("confidence_label", "unrated"),
        "timing_status": rehearsal_analysis.get("timing_status", "unknown"),
        "recommended_focus": (
            latest_rehearsal.get("next_focus")
            or latest_difficulty.get("challenge")
            or mission.get("presentation_state", {}).get("focus_area", "")
        ),
        "recommended_actions": rehearsal_analysis.get("recommendations", [])[:3],
    }


def _build_delivery_risks(mission, script_summary, latest_difficulty, latest_rehearsal_analysis):
    risks = []
    if latest_difficulty:
        risks.append(
            {
                "type": "difficulty_event",
                "severity": latest_difficulty.get("severity", "medium"),
                "title": latest_difficulty.get("challenge") or "recent blocker",
                "note": latest_difficulty.get("context") or latest_difficulty.get("suggested_fix") or "",
                "recommended_fix": latest_difficulty.get("suggested_fix") or "",
            }
        )

    if latest_rehearsal_analysis.get("timing_status") in {"long", "short"}:
        risks.append(
            {
                "type": "overall_timing",
                "severity": "high" if latest_rehearsal_analysis.get("timing_status") == "long" else "medium",
                "title": f"Overall pacing is {latest_rehearsal_analysis.get('timing_status')}",
                "note": latest_rehearsal_analysis.get("timing_note", ""),
                "recommended_fix": (latest_rehearsal_analysis.get("recommendations") or [""])[0],
            }
        )

    largest_overrun = latest_rehearsal_analysis.get("section_timing_summary", {}).get("largest_overrun", {})
    if largest_overrun:
        risks.append(
            {
                "type": "section_timing",
                "severity": "high",
                "title": f"{largest_overrun.get('title', 'Section')} is overrunning",
                "note": largest_overrun.get("timing_note", ""),
                "recommended_fix": f"Trim about {largest_overrun.get('delta_label', '0:00')} from this section first.",
            }
        )

    if script_summary.get("completed_sections", 0) < script_summary.get("section_count", 0):
        missing_count = script_summary.get("section_count", 0) - script_summary.get("completed_sections", 0)
        risks.append(
            {
                "type": "content_gap",
                "severity": "medium",
                "title": "Some speaking cards are still empty",
                "note": f"{missing_count} section(s) still need outline, notes, or teleprompter content.",
                "recommended_fix": "Complete the empty cards before the next full rehearsal.",
            }
        )
    for issue in (latest_rehearsal_analysis.get("transcript_analysis", {}) or {}).get("issues", [])[:2]:
        risks.append(
            {
                "type": "wording_risk",
                "severity": issue.get("severity", "medium"),
                "title": issue.get("title", "Wording risk"),
                "note": issue.get("note", ""),
                "recommended_fix": issue.get("recommended_fix", ""),
            }
        )
    return risks[:4]


def _build_qa_prep(mission):
    title = mission.get("title", "") or "this presentation"
    focus_goal = mission.get("focus_goal", "")
    requirements = (mission.get("teacher_requirements", "") or "").lower()
    active_section = _active_section(mission)
    evidence_section = next(
        (
            item for item in mission.get("script_sections", [])
            if any(token in (item.get("title", "") + " " + item.get("interaction_goal", "")).lower() for token in ("evidence", "example", "proof"))
        ),
        {},
    )

    likely_questions = [
        f"What is the one main takeaway you want the audience to remember from {title}?",
        f"What is the strongest piece of evidence or example supporting {title}?",
        f"Why does {active_section.get('title', 'your current section')} matter to the overall argument?",
    ]
    if "cite" in requirements or "reference" in requirements or "source" in requirements:
        likely_questions.append("Which source or reference is most important here, and why is it credible?")
    if focus_goal:
        likely_questions.append(f"How does this presentation achieve the goal: {focus_goal}?")

    answer_tips = [
        "Answer first, then justify with one example, then return to the takeaway.",
        "Keep answers shorter than your main slide explanation unless the teacher asks for detail.",
        "If you are unsure, restate the question in your own words before answering.",
    ]
    if evidence_section:
        answer_tips.append(
            f"Re-use one example from {evidence_section.get('title', 'your evidence section')} instead of inventing a new answer under pressure."
        )

    return {
        "likely_questions": likely_questions[:4],
        "answer_framework": "Claim -> Evidence -> Takeaway",
        "answer_tips": answer_tips[:4],
    }


def _readiness_band(score):
    safe_score = max(0, min(100, _safe_int(score, default=0)))
    if safe_score >= 85:
        return "ready"
    if safe_score >= 70:
        return "almost ready"
    if safe_score >= 50:
        return "developing"
    return "early stage"


def _build_readiness_summary(mission, script_summary, latest_difficulty, latest_rehearsal_analysis):
    score = 100
    completed_sections = script_summary.get("completed_sections", 0)
    section_count = max(1, script_summary.get("section_count", 0))
    completion_ratio = completed_sections / section_count
    score -= int(round((1 - completion_ratio) * 30))

    timing_status = latest_rehearsal_analysis.get("timing_status", "unknown")
    if timing_status == "long":
        score -= 15
    elif timing_status == "short":
        score -= 10
    elif timing_status == "unknown":
        score -= 6

    confidence_label = latest_rehearsal_analysis.get("confidence_label", "unrated")
    if confidence_label == "very fragile":
        score -= 20
    elif confidence_label == "fragile":
        score -= 12
    elif confidence_label == "unrated":
        score -= 6

    section_timing_summary = latest_rehearsal_analysis.get("section_timing_summary", {}) or {}
    score -= min(15, section_timing_summary.get("overrun_sections", 0) * 5)
    if latest_difficulty and not _safe_bool(latest_difficulty.get("resolved"), default=False):
        score -= 8
    transcript_issue_count = (latest_rehearsal_analysis.get("transcript_analysis", {}) or {}).get("issue_count", 0)
    score -= min(12, transcript_issue_count * 4)

    safe_score = max(0, min(100, score))
    strengths = []
    blockers = []
    if completion_ratio >= 0.8:
        strengths.append("Most speaking cards already contain usable rehearsal material.")
    if latest_rehearsal_analysis.get("timing_status") == "balanced":
        strengths.append("Overall rehearsal pacing is close to the target window.")
    if confidence_label in {"steady", "confident"}:
        strengths.append(f"Delivery confidence is currently {confidence_label}.")
    if section_timing_summary.get("balanced_sections", 0) >= max(1, section_count // 2):
        strengths.append("Several sections are already pacing at a balanced speed.")

    if completion_ratio < 1.0:
        blockers.append("Some speaking cards are still incomplete.")
    if section_timing_summary.get("largest_overrun"):
        blockers.append(
            f"{section_timing_summary['largest_overrun'].get('title', 'One section')} is still your biggest pacing risk."
        )
    if latest_difficulty and not _safe_bool(latest_difficulty.get("resolved"), default=False):
        blockers.append(
            f"The latest blocker is still {latest_difficulty.get('challenge') or 'unresolved'}."
        )
    if latest_rehearsal_analysis.get("transcript_density") == "thin":
        blockers.append("The transcript sample is still too thin for strong rehearsal feedback.")
    transcript_issues = (latest_rehearsal_analysis.get("transcript_analysis", {}) or {}).get("issues", [])
    if transcript_issues:
        blockers.append(transcript_issues[0].get("title", "There is still a wording issue in the current transcript."))
    if not strengths:
        strengths.append("The structure is now stable enough to support targeted rehearsal.")
    if not blockers:
        blockers.append("No major blocker is dominating right now; refine delivery instead of rewriting structure.")

    return {
        "score": safe_score,
        "band": _readiness_band(safe_score),
        "strengths": strengths[:3],
        "blockers": blockers[:3],
    }


def _build_practice_drills(mission, latest_difficulty, latest_rehearsal_analysis):
    active_section = _active_section(mission)
    section_timing_summary = latest_rehearsal_analysis.get("section_timing_summary", {}) or {}
    largest_overrun = section_timing_summary.get("largest_overrun", {}) or {}
    transcript_issues = (latest_rehearsal_analysis.get("transcript_analysis", {}) or {}).get("issues", [])
    drills = []

    if largest_overrun:
        drills.append(
            {
                "drill_type": "timing_trim",
                "title": f"Trim {largest_overrun.get('title', 'the longest section')}",
                "goal": f"Recover about {largest_overrun.get('delta_label', '0:00')} from the most overloaded section.",
                "steps": [
                    f"Read {largest_overrun.get('title', 'that section')} aloud once at normal speed.",
                    "Underline the one sentence that repeats an idea you already made.",
                    "Cut that sentence and rehearse the section again immediately.",
                ],
            }
        )

    if latest_difficulty and "transition" in _safe_text(latest_difficulty.get("challenge"), max_length=120).lower():
        drills.append(
            {
                "drill_type": "transition_bridge",
                "title": "Bridge the transition",
                "goal": "Make the move between sections feel intentional instead of abrupt.",
                "steps": [
                    f"Write one bridge sentence at the end of {active_section.get('title', 'the current section')}.",
                    "Say that bridge sentence aloud three times without changing the wording.",
                    "Then deliver the last line of the current section plus the first line of the next section as one unit.",
                ],
            }
        )

    if latest_rehearsal_analysis.get("confidence_label") in {"fragile", "very fragile"}:
        drills.append(
            {
                "drill_type": "opening_stability",
                "title": "Stabilize the opening",
                "goal": "Lower anxiety by making the first 20 seconds automatic.",
                "steps": [
                    "Stand up and deliver only the first 20 seconds.",
                    "Pause, reset your breath, and repeat it two more times.",
                    "Keep the wording stable; do not improvise in this drill.",
                ],
            }
        )
    if any(issue.get("type") == "dense_sentences" for issue in transcript_issues):
        drills.append(
            {
                "drill_type": "sentence_split",
                "title": "Split dense sentences",
                "goal": "Make the spoken wording easier to deliver live.",
                "steps": [
                    "Pick the longest sentence from your transcript excerpt.",
                    "Break it into two shorter spoken lines with one pause.",
                    "Rehearse only that rewritten pair three times before the next full run.",
                ],
            }
        )
    if any(issue.get("type") == "weak_signposting" for issue in transcript_issues):
        drills.append(
            {
                "drill_type": "signpost_upgrade",
                "title": "Add explicit signposts",
                "goal": "Make the audience feel the structure instead of guessing it.",
                "steps": [
                    "Add one transition phrase to the current section: next, for example, however, or overall.",
                    "Deliver the section once with the new signpost.",
                    "Check whether the transition now sounds easier to follow aloud.",
                ],
            }
        )
    if any(issue.get("type") == "repetition" for issue in transcript_issues):
        drills.append(
            {
                "drill_type": "repetition_cut",
                "title": "Cut repeated explanation",
                "goal": "Remove one repeated idea so the point lands faster.",
                "steps": [
                    "Underline the repeated term or repeated idea in the transcript excerpt.",
                    "Keep the strongest line and delete the weaker repetition.",
                    "Say the shorter version aloud once immediately.",
                ],
            }
        )

    if not drills:
        drills.append(
            {
                "drill_type": "full_run_refresh",
                "title": "One focused full run",
                "goal": "Keep the structure stable while improving one delivery variable.",
                "steps": [
                    "Pick one target: timing, confidence, or transitions.",
                    "Run the full presentation once without rewriting the script mid-way.",
                    "Write one note on what improved and one note on what still feels unstable.",
                ],
            }
        )
    return drills[:3]


def _build_mock_qa_prompt(mission):
    qa_prep = _build_qa_prep(mission)
    likely_questions = qa_prep.get("likely_questions", [])
    question = likely_questions[0] if likely_questions else "What is the main takeaway of your presentation?"
    return {
        "question": question,
        "answer_framework": qa_prep.get("answer_framework", "Claim -> Evidence -> Takeaway"),
        "tip": (qa_prep.get("answer_tips") or ["Answer first, then justify with one example."])[0],
    }


def _build_section_coaching(mission, latest_rehearsal_analysis):
    active_section = _active_section(mission)
    guidance = _section_specific_guidance(active_section)
    transcript_issues = (latest_rehearsal_analysis.get("transcript_analysis", {}) or {}).get("issues", [])
    primary_issue = transcript_issues[0] if transcript_issues else {}
    return {
        "active_section_id": active_section.get("section_id", ""),
        "active_section_title": active_section.get("title", ""),
        **guidance,
        "primary_issue": primary_issue,
        "coaching_prompt": primary_issue.get("recommended_fix") or guidance.get("coach_note", ""),
    }


def _normalize_phase(value):
    normalized = _safe_text(value, max_length=24).lower()
    if normalized in {"planning", "drafting", "rehearsing", "refining", "complete"}:
        return normalized
    return "planning"


def _normalize_presentation_mode(value):
    normalized = _safe_text(value, max_length=24).lower()
    if normalized in {"outline", "teleprompter", "rehearse", "qa", "present"}:
        return normalized
    return "rehearse"


def _normalize_cue_view(value):
    return "hidden" if _safe_text(value, max_length=16).lower() == "hidden" else "visible"


def _normalize_severity(value):
    normalized = _safe_text(value, max_length=20).lower()
    if normalized in {"low", "medium", "high", "critical"}:
        return normalized
    return "medium"


def _detect_deliverable_type(lowered_text):
    mapping = [
        ("poster presentation", "poster presentation"),
        ("oral presentation", "oral presentation"),
        ("group presentation", "group presentation"),
        ("seminar", "seminar presentation"),
        ("pitch", "pitch presentation"),
        ("defense", "presentation defense"),
        ("slides", "slide presentation"),
        ("presentation", "presentation"),
        ("present", "presentation"),
    ]
    for needle, label in mapping:
        if needle in lowered_text:
            return label
    return ""


def _extract_duration_minutes(text):
    patterns = [
        re.compile(r"(\d+)\s*(?:-|to)\s*(\d+)\s*(minutes|minute|min|mins)\b", re.I),
        re.compile(r"(\d+(?:\.\d+)?)\s*(minutes|minute|min|mins)\b", re.I),
    ]
    for pattern in patterns:
        match = pattern.search(text)
        if not match:
            continue
        try:
            if len(match.groups()) >= 3 and match.group(2) and match.group(2).isdigit():
                return round((float(match.group(1)) + float(match.group(2))) / 2.0, 1)
        except Exception:
            pass
        try:
            return round(float(match.group(1)), 1)
        except Exception:
            continue
    return 0


def _extract_labeled_value(text, labels):
    for label in labels:
        match = re.search(rf"{re.escape(label)}\s*[:\-]\s*(.+)", text, re.I)
        if match:
            value = match.group(1).strip()
            value = value.splitlines()[0].strip()
            return _safe_text(value, max_length=180)
    return ""


def _extract_title(text, lines):
    labeled = _extract_labeled_value(text, ("title", "topic", "presentation title"))
    if labeled:
        return labeled
    quoted = re.search(r"\"([^\"]{4,120})\"", text)
    if quoted:
        return _safe_text(quoted.group(1), max_length=120)
    first_line = lines[0] if lines else ""
    if 4 <= len(first_line) <= 90 and ":" not in first_line:
        return _safe_text(first_line, max_length=120)
    return ""


def _extract_deadline(text):
    patterns = [
        re.compile(r"(?:deadline|due(?: date)?|presentation date|present on)\s*[:\-]?\s*([^\n\.]{4,80})", re.I),
        re.compile(r"\b(on\s+[A-Z][a-z]+\s+\d{1,2}(?:,\s*\d{4})?)", re.I),
        re.compile(r"\b(\d{4}-\d{2}-\d{2})\b"),
    ]
    for pattern in patterns:
        match = pattern.search(text)
        if match:
            return _safe_text(match.group(1), max_length=80)
    return ""


def _detect_audience(lowered_text):
    if "classmates" in lowered_text or "class" in lowered_text:
        return "Classmates and teacher"
    if "teacher" in lowered_text and "class" not in lowered_text:
        return "Teacher"
    if "panel" in lowered_text or "jury" in lowered_text:
        return "Panel"
    if "audience" in lowered_text:
        return "General audience"
    return ""


def _extract_teacher_requirements(text):
    requirement_lines = []
    for raw_line in text.splitlines():
        line = raw_line.strip(" -*\t")
        lowered = line.lower()
        if not line:
            continue
        if any(token in lowered for token in ("must", "should", "need to", "required", "include", "at least", "cite", "reference", "submit")):
            requirement_lines.append(line)
    if not requirement_lines:
        sentences = re.split(r"(?<=[\.\?!])\s+", text.strip())
        for sentence in sentences:
            lowered = sentence.lower()
            if any(token in lowered for token in ("must", "need to", "required", "include", "at least", "cite", "reference")):
                requirement_lines.append(sentence.strip())
    cleaned = [_safe_text(line, max_length=280) for line in requirement_lines[:5] if _safe_text(line, max_length=280)]
    if not cleaned:
        return ""
    return "\n".join(f"- {item}" for item in cleaned)


def _heuristic_intake_candidates(task_text):
    lines = [line.strip(" -*\t") for line in task_text.splitlines() if line.strip()]
    lowered = task_text.lower()
    deliverable_type = _detect_deliverable_type(lowered)
    duration_minutes = _extract_duration_minutes(task_text)
    title = _extract_title(task_text, lines) or "Academic Presentation"
    course = _extract_labeled_value(task_text, ("course", "class", "module", "subject"))
    deadline = _extract_deadline(task_text)
    audience = _detect_audience(lowered)
    teacher_requirements = _extract_teacher_requirements(task_text)
    suggested_sections = _normalize_sections(
        _default_sections(duration_minutes or 5, deliverable_type or "presentation"),
        target_duration_minutes=duration_minutes or 5,
    )
    return {
        "candidates": {
            "title": title,
            "course": course,
            "deadline": deadline,
            "deliverable_type": deliverable_type or "presentation",
            "target_duration_minutes": duration_minutes or 0,
            "audience": audience,
            "teacher_requirements": teacher_requirements,
            "task_description": task_text,
            "intake_task_text": task_text,
        },
        "suggested_sections": suggested_sections,
        "notes": [
            "The intake extractor looked for explicit duration, deliverable, audience, and requirement cues.",
            "All extracted fields stay editable before you save the mission.",
        ],
    }


def _normalize_presentation_state(sections, existing=None, incoming=None):
    existing = existing if isinstance(existing, dict) else {}
    incoming = incoming if isinstance(incoming, dict) else {}
    first_section_id = sections[0]["section_id"] if sections else ""
    active_section_id = _safe_text(
        incoming.get("active_section_id") or existing.get("active_section_id") or first_section_id,
        max_length=80,
    )
    if sections and active_section_id not in {item["section_id"] for item in sections}:
        active_section_id = first_section_id

    return {
        "phase": _normalize_phase(incoming.get("phase") or existing.get("phase")),
        "presentation_mode": _normalize_presentation_mode(
            incoming.get("presentation_mode") or existing.get("presentation_mode")
        ),
        "cue_view": _normalize_cue_view(incoming.get("cue_view") or existing.get("cue_view")),
        "active_section_id": active_section_id,
        "active_chunk_index": max(
            0,
            _safe_int(incoming.get("active_chunk_index"), default=_safe_int(existing.get("active_chunk_index"), default=0)),
        ),
        "progress_note": _safe_text(
            incoming.get("progress_note") or existing.get("progress_note"),
            max_length=1200,
            preserve_lines=True,
        ),
        "focus_area": _safe_text(incoming.get("focus_area") or existing.get("focus_area"), max_length=240),
        "focus_level": _safe_text(incoming.get("focus_level") or existing.get("focus_level"), max_length=40),
        "confidence_level": max(
            0,
            min(5, _safe_int(incoming.get("confidence_level"), default=_safe_int(existing.get("confidence_level"), default=0))),
        ),
        "control_source": _safe_text(incoming.get("control_source") or existing.get("control_source"), max_length=40)
        or "websocket",
        "last_action": _safe_text(incoming.get("last_action") or existing.get("last_action"), max_length=40),
        "last_control_at": _safe_text(incoming.get("last_control_at") or existing.get("last_control_at"), max_length=40),
        "last_rehearsed_at": _safe_text(incoming.get("last_rehearsed_at") or existing.get("last_rehearsed_at"), max_length=40),
        "rehearsal_count": max(
            0,
            _safe_int(incoming.get("rehearsal_count"), default=_safe_int(existing.get("rehearsal_count"), default=0)),
        ),
    }


def _default_reflection_state(created_at=""):
    timestamp = created_at or _now_iso()
    return {
        "focus_theme": "",
        "current_course": "",
        "target_habit": "",
        "learner_note": "",
        "next_goal": "",
        "provider_override": "",
        "model_override": "",
        "use_llm": False,
        "latest_reflection": {},
        "reflection_history": [],
        "action_commitments": [],
        "wins": [],
        "updated_at": timestamp,
    }


def _default_learning_state_guardian(created_at=""):
    timestamp = created_at or _now_iso()
    return {
        "current_task": "",
        "session_goal": "",
        "current_course": "",
        "environment": "",
        "task_mode": "",
        "latest_state": {},
        "state_history": [],
        "focus_signals": [],
        "difficulty_events": [],
        "difficulty_tracker": _default_guardian_difficulty_tracker(),
        "risk_flags": [],
        "personal_baseline": {},
        "recent_trend_window": {},
        "state_transition_summary": {},
        "recovery_confidence": {},
        "continuity_profile": {},
        "intervention_plan": {},
        "updated_at": timestamp,
    }


def _ensure_mission_extensions(mission):
    created_at = _safe_text((mission or {}).get("created_at"), max_length=40) or _now_iso()
    reflection_state = mission.get("reflection_coach")
    if not isinstance(reflection_state, dict):
        reflection_state = _default_reflection_state(created_at)
    else:
        defaults = _default_reflection_state(created_at)
        for key, value in defaults.items():
            reflection_state.setdefault(key, copy.deepcopy(value))
    reflection_state["reflection_history"] = [
        item for item in reflection_state.get("reflection_history", []) if isinstance(item, dict)
    ][-MAX_HISTORY:]
    reflection_state["action_commitments"] = [
        _safe_text(item, max_length=280, preserve_lines=True)
        for item in reflection_state.get("action_commitments", [])
        if _safe_text(item, max_length=280, preserve_lines=True)
    ][-MAX_HISTORY:]
    reflection_state["wins"] = [
        _safe_text(item, max_length=280, preserve_lines=True)
        for item in reflection_state.get("wins", [])
        if _safe_text(item, max_length=280, preserve_lines=True)
    ][-MAX_HISTORY:]
    reflection_state["learner_note"] = _safe_text(
        reflection_state.get("learner_note"),
        max_length=1200,
        preserve_lines=True,
    )
    reflection_state["next_goal"] = _safe_text(
        reflection_state.get("next_goal"),
        max_length=240,
        preserve_lines=True,
    )
    reflection_state["provider_override"] = _normalize_reflection_provider(reflection_state.get("provider_override"))
    reflection_state["model_override"] = _safe_text(reflection_state.get("model_override"), max_length=120)
    reflection_state["use_llm"] = _safe_bool(reflection_state.get("use_llm"), default=False)
    mission["reflection_coach"] = reflection_state

    guardian_state = mission.get("learning_state_guardian")
    if not isinstance(guardian_state, dict):
        guardian_state = _default_learning_state_guardian(created_at)
    else:
        defaults = _default_learning_state_guardian(created_at)
        for key, value in defaults.items():
            guardian_state.setdefault(key, copy.deepcopy(value))
    guardian_state["state_history"] = [item for item in guardian_state.get("state_history", []) if isinstance(item, dict)][
        -MAX_HISTORY:
    ]
    guardian_state["focus_signals"] = [item for item in guardian_state.get("focus_signals", []) if isinstance(item, dict)][
        -MAX_HISTORY:
    ]
    guardian_state["difficulty_events"] = [
        item for item in guardian_state.get("difficulty_events", []) if isinstance(item, dict)
    ][-MAX_HISTORY:]
    tracker = guardian_state.get("difficulty_tracker")
    if not isinstance(tracker, dict):
        tracker = _default_guardian_difficulty_tracker()
    else:
        defaults = _default_guardian_difficulty_tracker()
        for key, value in defaults.items():
            tracker.setdefault(key, copy.deepcopy(value))
    if not isinstance(tracker.get("active_event"), dict):
        tracker["active_event"] = {}
    guardian_state["difficulty_tracker"] = tracker
    guardian_state["risk_flags"] = [
        _safe_text(item, max_length=220)
        for item in guardian_state.get("risk_flags", [])
        if _safe_text(item, max_length=220)
    ][-8:]
    mission["learning_state_guardian"] = guardian_state
    return mission


def _build_default_mission(session_id, mission_id):
    created_at = _now_iso()
    script_sections = _default_sections(0.0)
    mission = {
        "mission_id": mission_id,
        "session_id": session_id,
        "title": "",
        "course": "",
        "deadline": "",
        "deliverable_type": "presentation",
        "target_duration_minutes": 0.0,
        "audience": "",
        "teacher_requirements": "",
        "task_description": "",
        "intake_task_text": "",
        "focus_goal": "",
        "script_sections": script_sections,
        "presentation_state": _normalize_presentation_state(script_sections),
        "difficulty_events": [],
        "rehearsal_history": [],
        "chat_history": [],
        "created_at": created_at,
        "updated_at": created_at,
    }
    mission["reflection_coach"] = _default_reflection_state(created_at)
    mission["learning_state_guardian"] = _default_learning_state_guardian(created_at)
    return mission


def _resolve_mission(store, session_id, payload, create_if_missing=True):
    mission_id = _safe_text(payload.get("mission_id"), max_length=80) or f"mission_{_slugify(session_id, 'anonymous')}"
    mission = _find_mission(store, mission_id)
    if mission is None and create_if_missing:
        mission = _build_default_mission(session_id, mission_id)
    if mission is not None:
        mission["session_id"] = session_id
        mission = _ensure_mission_extensions(mission)
    return mission


def _active_section(mission):
    sections = mission.get("script_sections", [])
    active_section_id = (mission.get("presentation_state") or {}).get("active_section_id", "")
    for item in sections:
        if item.get("section_id") == active_section_id:
            return item
    return sections[0] if sections else {}


def _build_next_actions(mission):
    actions = []
    sections = mission.get("script_sections", [])
    state = mission.get("presentation_state", {})
    difficulties = mission.get("difficulty_events", [])
    rehearsals = mission.get("rehearsal_history", [])
    reflection_state = _ensure_payload_dict(mission.get("reflection_coach"))
    guardian_state = _ensure_payload_dict(mission.get("learning_state_guardian"))
    reflection_history = reflection_state.get("reflection_history", [])
    guardian_latest = guardian_state.get("latest_state", {}) if isinstance(guardian_state.get("latest_state"), dict) else {}
    guardian_risks = guardian_state.get("risk_flags", [])

    if not mission.get("title") and not mission.get("task_description"):
        actions.append("Capture the presentation brief so the companion can anchor feedback to one task.")
    if sections and all(not any(item.get(field) for field in ("outline", "speaker_notes", "teleprompter_script", "cue_cards")) for item in sections):
        actions.append("Add outline points or speaker notes to each section before the next rehearsal.")
    if not rehearsals:
        actions.append("Run one timed rehearsal and log what worked and what needs improvement.")
    if difficulties:
        latest = difficulties[-1]
        challenge = latest.get("challenge") or latest.get("context") or "the latest blocker"
        actions.append(f"Turn {challenge} into one concrete next step before the next practice round.")
    if state.get("phase") in {"planning", "drafting"}:
        actions.append("Move the mission into a rehearsal-ready outline with an opening, evidence, and closing.")
    if state.get("phase") == "rehearsing" and not difficulties:
        actions.append("Trim one section or add one transition cue to improve delivery flow.")
    if reflection_history and not reflection_state.get("action_commitments"):
        actions.append("Turn the latest reflection into one specific next-step commitment for the next study block.")
    if guardian_latest and guardian_risks:
        actions.append(f"Reduce the top study-state risk first: {guardian_risks[0]}.")
    if guardian_latest and not guardian_state.get("focus_signals"):
        actions.append("Log one focus signal or distraction pattern so the guardian can catch repeated friction.")
    if not actions:
        actions.append("Keep rehearsing the current section and tighten transitions between slides.")
    return actions[:4]


def _reflection_mode_label(task_mode):
    normalized = _normalize_guardian_task_mode(task_mode) or "reading"
    return normalized.replace("-", " ").title()


def _normalize_reflection_provider(value):
    normalized = _safe_text(value, max_length=40).lower()
    if normalized in {"", "default"}:
        return "auto"
    if normalized in {"heuristic", "ollama", "remote", "openai", "auto"}:
        return normalized
    return "heuristic"


def _reflection_provider_label(provider):
    mapping = {
        "auto": "Default Provider",
        "heuristic": "Heuristic",
        "ollama": "Ollama Local",
        "remote": "Remote API",
        "openai": "OpenAI",
    }
    return mapping.get(_normalize_reflection_provider(provider), "Heuristic")


def _configured_reflection_provider():
    provider = _normalize_reflection_provider(os.getenv("LLM_PROVIDER", "ollama"))
    return "ollama" if provider == "auto" else provider


def _reflection_provider_model_name(provider, model_override=""):
    cleaned_override = _safe_text(model_override, max_length=120)
    if cleaned_override:
        return cleaned_override
    provider = _normalize_reflection_provider(provider)
    if provider == "ollama":
        return os.getenv("OLLAMA_MODEL", "qwen3:4b").strip() or "qwen3:4b"
    if provider == "remote":
        return os.getenv("REFLECTION_REMOTE_LABEL", "remote-reflection-service").strip() or "remote-reflection-service"
    if provider == "openai":
        return os.getenv("OPENAI_MODEL", "gpt-4.1-mini").strip() or "gpt-4.1-mini"
    return ""


def _reflection_provider_options():
    return [
        {"value": "auto", "label": "Use Default Provider"},
        {"value": "heuristic", "label": "Heuristic Only"},
        {"value": "ollama", "label": "Ollama Local"},
        {"value": "remote", "label": "Remote API"},
        {"value": "openai", "label": "OpenAI"},
    ]


def _reflection_provider_is_configured(provider):
    provider = _normalize_reflection_provider(provider)
    if provider in {"auto", "heuristic"}:
        return True
    if provider == "ollama":
        return bool(_reflection_provider_model_name("ollama")) and bool(
            os.getenv("OLLAMA_BASE_URL", "http://127.0.0.1:11434/api").strip()
        )
    if provider == "remote":
        return bool(os.getenv("REFLECTION_REMOTE_URL", "").strip())
    if provider == "openai":
        return bool(os.getenv("OPENAI_API_KEY", "").strip())
    return False


def _reflection_any_model_provider_configured():
    return any(_reflection_provider_is_configured(provider) for provider in REFLECTION_MODEL_PROVIDERS)


def _reflection_generation_meta(requested_provider="auto", configured_provider="ollama", model_override="", note=""):
    requested_provider = _normalize_reflection_provider(requested_provider)
    configured_provider = _normalize_reflection_provider(configured_provider)
    resolved_provider = "heuristic"
    provider_for_note = configured_provider if requested_provider == "auto" else requested_provider
    if requested_provider == "heuristic":
        fallback_note = "Heuristic mode is active. Turn on model polish only if you want a provider-backed wording pass."
    else:
        fallback_note = (
            f"Heuristic mode is active. The configured default provider is {_reflection_provider_label(configured_provider)}. "
            "If that provider is unavailable at runtime, the coach will still fall back safely."
        )
    return {
        "mode": "heuristic",
        "used_llm": False,
        "llm_available": _reflection_any_model_provider_configured(),
        "requested_provider": requested_provider,
        "resolved_provider": resolved_provider,
        "configured_provider": configured_provider,
        "provider_available": _reflection_provider_is_configured(provider_for_note),
        "provider_label": _reflection_provider_label(resolved_provider),
        "configured_label": _reflection_provider_label(configured_provider),
        "model": "",
        "configured_model": _reflection_provider_model_name(configured_provider, model_override=model_override),
        "model_override": _safe_text(model_override, max_length=120),
        "note": _safe_text(note, max_length=360, preserve_lines=True) or fallback_note,
    }


def _reflection_effective_provider(requested_provider="auto", configured_provider="ollama"):
    requested_provider = _normalize_reflection_provider(requested_provider)
    configured_provider = _normalize_reflection_provider(configured_provider)
    if requested_provider == "auto":
        return configured_provider
    return requested_provider


def _reflection_supports_model_override(requested_provider="auto", configured_provider="ollama"):
    requested_provider = _normalize_reflection_provider(requested_provider)
    configured_provider = _normalize_reflection_provider(configured_provider)
    return requested_provider == "ollama" or (requested_provider == "auto" and configured_provider == "ollama")


def _reflection_model_options(configured_provider="ollama", supports_model_override=False, model_override=""):
    configured_model = _reflection_provider_model_name(configured_provider)
    if not supports_model_override:
        return [{"value": "", "label": "Use default model"}]
    options = [{"value": "", "label": f"Use default model ({configured_model or 'none'})"}]
    cleaned_override = _safe_text(model_override, max_length=120)
    if cleaned_override and cleaned_override != configured_model:
        options.append({"value": cleaned_override, "label": f"Use explicit override ({cleaned_override})"})
    return options


def _reflection_provider_status(requested_provider="auto", model_override=""):
    requested_provider = _normalize_reflection_provider(requested_provider)
    configured_provider = _configured_reflection_provider()
    effective_provider = _reflection_effective_provider(requested_provider, configured_provider)
    supports_model_override = _reflection_supports_model_override(requested_provider, configured_provider)
    provider_available = _reflection_provider_is_configured(effective_provider)
    configured_model = _reflection_provider_model_name(configured_provider)
    selected_model = _reflection_provider_model_name(effective_provider, model_override=model_override)
    return {
        "requested_provider": requested_provider,
        "configured_provider": configured_provider,
        "configured_label": _reflection_provider_label(configured_provider),
        "effective_provider": effective_provider,
        "effective_label": _reflection_provider_label(effective_provider),
        "provider_available": provider_available,
        "llm_available": _reflection_any_model_provider_configured(),
        "configured_model": configured_model,
        "selected_model": selected_model,
        "model_override": _safe_text(model_override, max_length=120),
        "supports_model_override": supports_model_override,
        "provider_options": _reflection_provider_options(),
        "model_options": _reflection_model_options(
            configured_provider=configured_provider,
            supports_model_override=supports_model_override,
            model_override=model_override,
        ),
    }


def _reflection_focus_window_label(context):
    active_event = _ensure_payload_dict(context.get("active_event"))
    if active_event.get("time_window"):
        return _safe_text(active_event.get("time_window"), max_length=80)
    if active_event.get("recorded_at"):
        return f"the {active_event.get('recorded_at')} checkpoint"
    latest_reflection = _ensure_payload_dict(context.get("latest_reflection"))
    if latest_reflection.get("recorded_at"):
        return f"the {latest_reflection.get('recorded_at')} reflection"
    return "the latest study block"


def _reflection_context_from_mission(mission, state, history, latest):
    guardian_review = _build_learning_state_review(mission)
    guardian_state = _ensure_payload_dict(guardian_review.get("latest_state"))
    core_metrics = _ensure_payload_dict(guardian_review.get("core_metrics"))
    state_classification = _ensure_payload_dict(guardian_review.get("state_classification"))
    state_explanation = _ensure_payload_dict(guardian_review.get("state_explanation"))
    difficulty_tracking = _ensure_payload_dict(guardian_review.get("difficulty_tracking"))
    active_event = _ensure_payload_dict(difficulty_tracking.get("active_event"))
    trend_averages = _ensure_payload_dict(guardian_review.get("trend_averages"))

    return {
        "task_mode": guardian_review.get("task_mode") or guardian_state.get("task_mode") or "reading",
        "mode_label": _reflection_mode_label(guardian_review.get("task_mode") or guardian_state.get("task_mode")),
        "state_hint": _normalize_guardian_state_hint(state_classification.get("state_hint")) or "stable",
        "state_hint_label": state_classification.get("state_hint_label") or _guardian_state_hint_label(
            state_classification.get("state_hint")
        ),
        "active_event": active_event,
        "difficulty_count": max(
            _safe_int(difficulty_tracking.get("event_count"), default=0),
            len([item for item in mission.get("difficulty_events", []) if isinstance(item, dict)]),
        ),
        "risk_flags": guardian_review.get("risk_flags", []),
        "core_metrics": core_metrics,
        "trend_averages": trend_averages,
        "state_explanation": state_explanation,
        "current_course": state.get("current_course", ""),
        "target_habit": state.get("target_habit", ""),
        "focus_theme": state.get("focus_theme", ""),
        "learner_note": state.get("learner_note", ""),
        "next_goal": state.get("next_goal", ""),
        "provider_override": state.get("provider_override", ""),
        "model_override": state.get("model_override", ""),
        "use_llm": _safe_bool(state.get("use_llm"), default=False),
        "latest_reflection": latest,
        "reflection_count": len(history),
        "updated_at": guardian_review.get("updated_at", ""),
    }


def _select_reflection_signature(context):
    state_hint = _normalize_guardian_state_hint(context.get("state_hint")) or "stable"
    risk_flags = [str(item).lower() for item in context.get("risk_flags", []) if item]
    active_event = _ensure_payload_dict(context.get("active_event"))
    difficulty_count = _safe_int(context.get("difficulty_count"), default=0)
    trend_averages = _ensure_payload_dict(context.get("trend_averages"))
    core_metrics = _ensure_payload_dict(context.get("core_metrics"))

    avg_load = _safe_float(trend_averages.get("cognitive_load"), default=_safe_float(core_metrics.get("cognitive_load"), default=0.0))
    avg_fatigue = _safe_float(trend_averages.get("fatigue_risk"), default=_safe_float(core_metrics.get("fatigue_risk"), default=0.0))
    avg_alignment = _safe_float(
        trend_averages.get("behavioral_alignment"),
        default=_safe_float(core_metrics.get("behavioral_alignment"), default=100.0),
    )
    avg_switching = _safe_float(core_metrics.get("switching_index"), default=0.0)
    uncertainty = _safe_float(
        trend_averages.get("uncertainty_score"),
        default=_safe_float(core_metrics.get("uncertainty_score"), default=0.0),
    )

    if state_hint == "signal_check" or uncertainty >= 55 or any("confidence" in item for item in risk_flags):
        return {
            "key": "signal_check",
            "label": "Signal Check",
            "tone": "signal",
            "title": "This reflection needs cleaner signal conditions before deep interpretation.",
            "detail": "Low-confidence or noisy state periods were frequent enough that setup quality matters before strategy changes.",
            "next_boundary": "Keep the opening minute physically and visually stable so the next session starts from a cleaner baseline.",
        }
    if state_hint == "fatigue_risk" or avg_fatigue >= 46 or any("fatigue" in item or "energy" in item for item in risk_flags):
        return {
            "key": "fatigue_drag",
            "label": "Fatigue Drag",
            "tone": "warn",
            "title": "Fatigue likely became a stronger limiter than the material itself.",
            "detail": "The recent state pattern shows sustained fatigue pressure, so recovery timing matters as much as review strategy.",
            "next_boundary": "Treat the next replay as a shorter, cleaner attempt instead of pushing through the same pace.",
        }
    if state_hint == "productive_struggle":
        return {
            "key": "productive_challenge",
            "label": "Productive Challenge",
            "tone": "cool",
            "title": "This looks more like productive struggle than simple drift.",
            "detail": "Load rose while the learner stayed comparatively aligned, which points to real conceptual effort rather than random disengagement.",
            "next_boundary": "Protect the exact segment where effort turned heavy, and replay it more slowly without changing targets.",
        }
    if (
        state_hint == "off_task_risk"
        or avg_switching >= 38
        or active_event.get("primary_label") == "Context switching"
        or any("drift" in item or "switch" in item for item in risk_flags)
    ):
        return {
            "key": "switching_drift",
            "label": "Switching Drift",
            "tone": "high",
            "title": "Target switching likely disrupted the learning rhythm.",
            "detail": "The stronger pattern here is drift pressure: attention kept moving between targets or actions faster than the task could settle.",
            "next_boundary": "Reduce switching pressure before trying to rescue understanding with more effort.",
        }
    if difficulty_count == 0 and avg_load < 35 and avg_alignment >= 70:
        return {
            "key": "steady_control",
            "label": "Steady Control",
            "tone": "good",
            "title": "The study rhythm stayed controlled and review-ready.",
            "detail": "This recent pattern stayed comparatively stable, so the next opportunity is to preserve what worked and add a slightly harder target.",
            "next_boundary": "Keep the same setup and turn one stable block into a deliberate stretch block next time.",
        }
    return {
        "key": "mixed_regulation",
        "label": "Mixed Regulation",
        "tone": "warn",
        "title": "The recent session pattern shows mixed regulation pressure.",
        "detail": "Several pressures appeared together, so the best next step is to control one variable tightly instead of changing everything at once.",
        "next_boundary": "Pick one boundary for the next attempt: pace, switching, or recovery timing.",
    }


def _reflection_experiment(title, detail, success_marker):
    return {
        "title": _safe_text(title, max_length=120),
        "detail": _safe_text(detail, max_length=360, preserve_lines=True),
        "success_marker": _safe_text(success_marker, max_length=220, preserve_lines=True),
    }


def _build_reflection_coach_summary(signature, context, latest):
    core_metrics = _ensure_payload_dict(context.get("core_metrics"))
    mode_label = context.get("mode_label", "Reading")
    focus_score = core_metrics.get("focus_score")
    avg_load = _safe_float(
        _ensure_payload_dict(context.get("trend_averages")).get("cognitive_load"),
        default=_safe_float(core_metrics.get("cognitive_load"), default=0.0),
    )
    avg_fatigue = _safe_float(
        _ensure_payload_dict(context.get("trend_averages")).get("fatigue_risk"),
        default=_safe_float(core_metrics.get("fatigue_risk"), default=0.0),
    )
    active_event = _ensure_payload_dict(context.get("active_event"))
    event_text = "No sustained difficulty event is active right now."
    if active_event:
        event_text = (
            f"The strongest active study-state event is {active_event.get('primary_label', 'a live blocker')} "
            f"with status {active_event.get('status', 'active')}."
        )
    note_text = ""
    if latest.get("what_was_hard"):
        note_text = f" The latest reflection named this difficulty: {latest.get('what_was_hard')}."
    learner_note = _safe_text(context.get("learner_note"), max_length=1200, preserve_lines=True)
    next_goal = _safe_text(context.get("next_goal"), max_length=240, preserve_lines=True)
    learner_line = f' Learner note: "{learner_note}".' if learner_note else ""
    goal_line = f' The next session goal is "{next_goal}".' if next_goal else ""
    return {
        "headline": signature.get("title", "Reflection coach summary"),
        "overview": (
            f"This {mode_label.lower()} pattern is currently reading around focus "
            f"{focus_score if focus_score is not None else 'n/a'}/100, load {int(round(avg_load))}, "
            f"and fatigue {int(round(avg_fatigue))}. {event_text}{note_text}{learner_line}{goal_line}"
        ),
        "why_it_matters": (
            f"{signature.get('detail', '')} The current evidence suggests that the review should focus on "
            "process regulation before adding more material."
        ).strip(),
        "next_boundary": signature.get("next_boundary", ""),
    }


def _build_reflection_coach_cards(signature, context, coach_summary):
    active_event = _ensure_payload_dict(context.get("active_event"))
    explanation = _ensure_payload_dict(context.get("state_explanation"))
    primary_driver = _ensure_payload_dict(explanation.get("primary_driver"))
    event_title = "No live blocker to replay first"
    event_detail = "Use the evidence cards below as a light reflection map."
    if active_event:
        event_title = f"{active_event.get('primary_label', 'Active blocker')} is the best replay target"
        event_detail = _safe_text(
            active_event.get("trigger_reason") or active_event.get("review_note") or "A sustained event is still active.",
            max_length=220,
        )
    carry_forward_title = context.get("state_hint_label", "Current learning state")
    carry_forward_detail = _safe_text(
        explanation.get("top_intervention") or "Keep the next session bounded so the pattern becomes easier to interpret.",
        max_length=220,
    )
    if primary_driver:
        carry_forward_detail = (
            f"The top driver is {primary_driver.get('label', 'the current signal')}. "
            f"{carry_forward_detail}"
        )
    return [
        {
            "eyebrow": "Session read",
            "title": signature.get("label", "Reflection signature"),
            "detail": coach_summary.get("why_it_matters", ""),
            "tone": signature.get("tone", "warn"),
        },
        {
            "eyebrow": "Replay point",
            "title": event_title,
            "detail": event_detail,
            "tone": "high" if active_event else "good",
        },
        {
            "eyebrow": "Carry-forward rule",
            "title": carry_forward_title,
            "detail": carry_forward_detail,
            "tone": "cool",
        },
    ]


def _build_reflection_questions(signature, context):
    key = signature.get("key", "mixed_regulation")
    time_window = _reflection_focus_window_label(context)
    mode_text = str(context.get("task_mode", "reading")).replace("-", " ")

    if key == "productive_challenge":
        return [
            {"question": f"During {time_window}, what exact step in {mode_text} mode first changed from understandable to effortful?"},
            {"question": "When load rose, were you still following one source consistently, or did you start scanning for rescue elsewhere?"},
            {"question": "If you replay that segment once, what would you slow down without changing the material itself?"},
        ]
    if key == "switching_drift":
        return [
            {"question": f"What triggered the first unnecessary switch before or during {time_window}?"},
            {"question": "Which extra source, window, or action felt helpful in the moment but actually fragmented the task?"},
            {"question": "What single anchor could keep the next attempt on one target for the first two minutes?"},
        ]
    if key == "fatigue_drag":
        return [
            {"question": "At what moment did effort stop feeling purposeful and start feeling heavy or dull?"},
            {"question": "What earlier cue could tell you to pause before fatigue turns into low-quality persistence?"},
            {"question": "How short should the next replay block be if the goal is clarity rather than endurance?"},
        ]
    if key == "signal_check":
        return [
            {"question": "What most likely destabilized the signal: posture baseline, movement, switching, or scene quality?"},
            {"question": "What can you keep physically and visually constant during the first clean minute of the next session?"},
            {"question": "What would count as a trustworthy calibration start before you interpret the coaching output seriously?"},
        ]
    if key == "steady_control":
        return [
            {"question": "Which part of this session felt easiest to sustain, and what behavior helped that stability?"},
            {"question": "What small challenge could you add next time without breaking the current rhythm?"},
            {"question": "What should stay exactly the same because it clearly supported control and clarity?"},
        ]
    return [
        {"question": "What changed first when the session stopped feeling smooth: pace, switching, uncertainty, or fatigue?"},
        {"question": f"Inside {time_window}, was the main issue understanding pressure or regulation pressure?"},
        {"question": "What one variable do you want to control more tightly in the next session so the pattern becomes easier to interpret?"},
    ]


def _build_reflection_experiments(signature, context):
    key = signature.get("key", "mixed_regulation")
    target_habit = _safe_text(context.get("target_habit"), max_length=160)
    next_goal = _safe_text(context.get("next_goal"), max_length=240)
    goal_suffix = ""
    if next_goal:
        goal_suffix = f" while aiming for {next_goal}"
    elif target_habit:
        goal_suffix = f" while reinforcing {target_habit}"

    if key == "productive_challenge":
        return [
            _reflection_experiment(
                "Slow replay, same target",
                "Replay the flagged segment once at a slower pace, but keep exactly one source in view instead of searching for help elsewhere.",
                "Load rises later than before and the difficult step becomes easier to name.",
            ),
            _reflection_experiment(
                "Confusion timestamp",
                "The moment effort jumps, mark the exact sentence, diagram, or reasoning step rather than only noting that it felt hard.",
                "You can point to one concrete trigger instead of describing the whole segment as confusing.",
            ),
            _reflection_experiment(
                "One-minute rebuild",
                f"After the replay, spend one minute rebuilding the logic in your own words{goal_suffix}, without opening new materials.",
                "The concept gap narrows without a big switching spike.",
            ),
        ]
    if key == "switching_drift":
        return [
            _reflection_experiment(
                "Two-minute source lock",
                "Choose one source before starting and do not switch windows, pages, or note formats for the first two minutes.",
                "Switching pressure falls and the session reaches a steadier opening rhythm.",
            ),
            _reflection_experiment(
                "Switch budget",
                "Allow yourself only one intentional switch inside the replay block, and decide in advance why that switch is allowed.",
                "Every switch becomes purposeful instead of reactive.",
            ),
            _reflection_experiment(
                "Pre-decide the action path",
                "Before replaying, decide whether this block is for watching, reading, or note-taking instead of blending them on the fly.",
                "The task mode feels clearer and the guidance stabilizes faster.",
            ),
        ]
    if key == "fatigue_drag":
        return [
            _reflection_experiment(
                "Break before rescue",
                "Take a short reset before replaying the flagged segment instead of trying to recover inside the same tired state.",
                "The second attempt starts with lower fatigue and cleaner alignment.",
            ),
            _reflection_experiment(
                "Short replay block",
                "Replay only the highest-value slice of the difficult segment instead of the full long block.",
                "Clarity improves without the session becoming another endurance test.",
            ),
            _reflection_experiment(
                "Earlier stop rule",
                "Define one clear fatigue boundary for the next session, such as posture heaviness or dull rereading, and stop before it deepens.",
                "You exit earlier but preserve a better-quality review state.",
            ),
        ]
    if key == "signal_check":
        return [
            _reflection_experiment(
                "Clean calibration minute",
                "Use the first minute only to stabilize posture, scene, and task mode before doing real study work.",
                "Low-confidence drops become rarer in the opening phase.",
            ),
            _reflection_experiment(
                "Stable surface setup",
                "Keep the book, screen, or page position more constant so the scene lock stays credible.",
                "The system spends less time in signal-check behavior.",
            ),
            _reflection_experiment(
                "Single-mode warm start",
                "Do not mix reading, note-taking, and review during warm-up. Start with one mode and switch later only if needed.",
                "The next session becomes easier to interpret with higher confidence.",
            ),
        ]
    if key == "steady_control":
        return [
            _reflection_experiment(
                "Promote one stable block",
                "Take the steadiest part of this session and turn it into a deliberate stretch block next time.",
                "You keep control while increasing challenge slightly.",
            ),
            _reflection_experiment(
                "Thirty-second recap",
                "After a stable block ends, spend thirty seconds naming what helped the rhythm stay clean.",
                "Useful study behaviors become easier to repeat on purpose.",
            ),
            _reflection_experiment(
                "Stretch without clutter",
                f"Raise difficulty slightly{goal_suffix}, but keep the setup and source strategy unchanged.",
                "You can test growth without losing the current stability signature.",
            ),
        ]
    return [
        _reflection_experiment(
            "One-variable retry",
            "Keep the same material but change only one factor next time: pace, switching, or break timing.",
            "The next session pattern becomes easier to diagnose.",
        ),
        _reflection_experiment(
            "Replay the strongest segment first",
            "Start the next review with the strongest blocker instead of doing a full passive recap.",
            "You learn faster which regulation change actually matters.",
        ),
        _reflection_experiment(
            "End with a boundary note",
            "Write one sentence after the session about where regulation started to slip and what boundary should be held next time.",
            "The next attempt begins with a sharper self-coaching rule.",
        ),
    ]


def _build_reflection_evidence_cards(signature, context):
    core_metrics = _ensure_payload_dict(context.get("core_metrics"))
    explanation = _ensure_payload_dict(context.get("state_explanation"))
    primary_driver = _ensure_payload_dict(explanation.get("primary_driver"))
    active_event = _ensure_payload_dict(context.get("active_event"))
    risk_flags = context.get("risk_flags", [])
    difficulty_count = _safe_int(context.get("difficulty_count"), default=0)

    return [
        {
            "label": "Signature",
            "value": signature.get("label", "Reflection signature"),
            "detail": signature.get("detail", ""),
            "tone": signature.get("tone", "warn"),
        },
        {
            "label": "Primary mode",
            "value": context.get("mode_label", "Reading"),
            "detail": f"{context.get('reflection_count', 0)} reflection entries captured so far.",
            "tone": "cool",
        },
        {
            "label": "Top driver",
            "value": primary_driver.get("label", "No dominant driver"),
            "detail": primary_driver.get("explanation", "The current pattern does not have one dominant driver yet."),
            "tone": "high" if primary_driver else "good",
        },
        {
            "label": "Focus / load / fatigue",
            "value": f"{core_metrics.get('focus_score', 'n/a')} / {core_metrics.get('cognitive_load', 'n/a')} / {core_metrics.get('fatigue_risk', 'n/a')}",
            "detail": "Latest guardian core metrics for reflection framing.",
            "tone": "warn",
        },
        {
            "label": "Active event",
            "value": active_event.get("primary_label", "No active event"),
            "detail": active_event.get("trigger_reason") or active_event.get("review_note") or "No sustained event is active.",
            "tone": "high" if active_event else "good",
        },
        {
            "label": "Risk flags",
            "value": ", ".join(risk_flags[:2]) if risk_flags else "No dominant risk flags",
            "detail": f"{difficulty_count} total difficulty markers captured across this mission.",
            "tone": "signal" if risk_flags else "cool",
        },
    ]


def _build_reflection_coach_memo(signature, context, coach_summary, latest):
    core_metrics = _ensure_payload_dict(context.get("core_metrics"))
    active_event = _ensure_payload_dict(context.get("active_event"))
    event_line = (
        f" The strongest live blocker is {active_event.get('primary_label')}."
        if active_event
        else " No sustained difficulty event is currently active."
    )
    reflection_note = ""
    if latest.get("lesson"):
        reflection_note = f" Current learner lesson: {latest.get('lesson')}."
    elif latest.get("what_was_hard"):
        reflection_note = f" Current blocker: {latest.get('what_was_hard')}."
    learner_line = ""
    if context.get("learner_note"):
        learner_line = f" Learner note: {context.get('learner_note')}."
    goal_line = ""
    if context.get("next_goal"):
        goal_line = f" Next goal: {context.get('next_goal')}."
    return (
        f"{coach_summary.get('headline', 'Reflection coach summary')} "
        f"Latest focus is {core_metrics.get('focus_score', 'n/a')}/100 with load "
        f"{core_metrics.get('cognitive_load', 'n/a')}/100 and fatigue {core_metrics.get('fatigue_risk', 'n/a')}/100."
        f"{event_line} The next coaching boundary is: {signature.get('next_boundary', '')}.{reflection_note}{learner_line}{goal_line}"
    ).strip()


def _build_reflection_review(mission):
    state = _ensure_payload_dict(mission.get("reflection_coach"))
    history = [item for item in state.get("reflection_history", []) if isinstance(item, dict)]
    latest = state.get("latest_reflection", {}) if isinstance(state.get("latest_reflection"), dict) else {}
    if not latest and history:
        latest = history[-1]

    context = _reflection_context_from_mission(mission, state, history, latest)
    signature = _select_reflection_signature(context)
    coach_summary = _build_reflection_coach_summary(signature, context, latest)
    coach_cards = _build_reflection_coach_cards(signature, context, coach_summary)
    reflection_questions = _build_reflection_questions(signature, context)
    next_session_experiments = _build_reflection_experiments(signature, context)
    evidence_cards = _build_reflection_evidence_cards(signature, context)
    coach_memo = _build_reflection_coach_memo(signature, context, coach_summary, latest)
    configured_provider = _configured_reflection_provider()
    provider_status = _reflection_provider_status(
        requested_provider=context.get("provider_override") or "auto",
        model_override=context.get("model_override", ""),
    )
    generation = _reflection_generation_meta(
        requested_provider=context.get("provider_override") or "auto",
        configured_provider=configured_provider,
        model_override=context.get("model_override", ""),
    )

    theme_counter = Counter()
    for item in history[-6:]:
        for field in ("focus_theme", "lesson", "what_was_hard", "next_step"):
            words = re.findall(r"[a-zA-Z]{4,}", str(item.get(field, "")).lower())
            for word in words[:4]:
                if word not in TRANSCRIPT_STOPWORDS:
                    theme_counter[word] += 1

    commitments = state.get("action_commitments", [])[-3:]
    wins = state.get("wins", [])[-3:]
    coach_message = "Capture one short reflection after the next study block so patterns become easier to coach."
    if latest.get("what_was_hard"):
        coach_message = (
            f"The current reflection theme is {latest.get('what_was_hard')}. "
            f"Turn it into one smaller next action: {latest.get('next_step') or 'define the first 10-minute step.'}"
        )
    elif commitments:
        coach_message = f"Your clearest next commitment is: {commitments[0]}"
    elif wins:
        coach_message = f"Anchor the next reflection in what already worked: {wins[0]}"

    return {
        "focus_theme": state.get("focus_theme", ""),
        "current_course": state.get("current_course", ""),
        "target_habit": state.get("target_habit", ""),
        "learner_note": state.get("learner_note", ""),
        "next_goal": state.get("next_goal", ""),
        "module_boundary": (
            "This module coaches reflection on learning process and self-regulation. "
            "It does not teach the content itself, replace tutoring, or overlap with note-taking features."
        ),
        "provider_options": _reflection_provider_options(),
        "configured_provider": configured_provider,
        "provider_status": provider_status,
        "signature": signature,
        "coach_summary": coach_summary,
        "coach_cards": coach_cards,
        "reflection_count": len(history),
        "latest_reflection": latest,
        "recent_commitments": commitments,
        "recent_wins": wins,
        "pattern_keywords": [item for item, _ in theme_counter.most_common(5)],
        "reflection_questions": reflection_questions,
        "next_session_experiments": next_session_experiments,
        "evidence_cards": evidence_cards,
        "coach_memo": coach_memo,
        "generation": generation,
        "coach_message": coach_message,
        "updated_at": state.get("updated_at", ""),
    }


def _guardian_risk_flags_from_state(latest_state, focus_signals):
    latest_state = latest_state if isinstance(latest_state, dict) else {}
    focus_signals = focus_signals if isinstance(focus_signals, list) else []
    risk_flags = []
    focus_score = _optional_score_100(latest_state.get("focus_score"))
    fatigue_risk = _optional_score_100(latest_state.get("fatigue_risk"))
    uncertainty_score = _optional_score_100(latest_state.get("uncertainty_score"))
    cognitive_load = _optional_score_100(latest_state.get("cognitive_load"))
    focus_level = _safe_int(latest_state.get("focus_level"), default=0)
    energy_level = _safe_int(latest_state.get("energy_level"), default=0)
    stress_level = _safe_int(latest_state.get("stress_level"), default=0)
    state_hint = _normalize_guardian_state_hint(latest_state.get("state_hint"))
    task_mode = _normalize_guardian_task_mode(latest_state.get("task_mode")) or "reading"
    behavioral_level = _safe_text(latest_state.get("behavioral_level"), max_length=40).lower()
    if not behavioral_level and latest_state.get("behavioral_alignment") not in (None, ""):
        behavioral_level = _derive_guardian_behavioral_level(latest_state.get("behavioral_alignment"), task_mode=task_mode)

    if focus_score is not None and focus_score <= 40:
        risk_flags.append("Low focus signal")
    elif focus_level and focus_level <= 2:
        risk_flags.append("Low focus signal")

    if fatigue_risk is not None and fatigue_risk >= 65:
        risk_flags.append("Fatigue risk rising")
    elif energy_level and energy_level <= 2:
        risk_flags.append("Low energy signal")

    if uncertainty_score is not None and uncertainty_score >= 55:
        risk_flags.append("Low-confidence signal quality")

    if behavioral_level == "misaligned":
        risk_flags.append("Behavior drift from current task")
    elif behavioral_level == "drifting":
        risk_flags.append("Behavior alignment is slipping")

    if cognitive_load is not None and cognitive_load >= 78:
        risk_flags.append("High cognitive load")

    if stress_level >= 4:
        risk_flags.append("High stress signal")
    if latest_state.get("distraction"):
        risk_flags.append("Active distraction noted")
    if latest_state.get("support_needed"):
        risk_flags.append("Support request still open")
    if state_hint == "off_task_risk":
        risk_flags.append("Study state is drifting off target")
    elif state_hint == "fatigue_risk":
        risk_flags.append("Fatigue risk is becoming dominant")
    elif state_hint == "signal_check":
        risk_flags.append("Signal confidence still warming up")
    recent_unresolved = [
        item
        for item in focus_signals[-4:]
        if isinstance(item, dict) and not _safe_bool(item.get("resolved"), default=False)
    ]
    if recent_unresolved:
        risk_flags.append("Unresolved focus blockers remain")
    deduped = []
    for item in risk_flags:
        if item not in deduped:
            deduped.append(item)
    return deduped[:5]


def _guardian_state_explanation(latest_state, focus_signals, risk_flags):
    latest_state = latest_state if isinstance(latest_state, dict) else {}
    focus_signals = focus_signals if isinstance(focus_signals, list) else []
    risk_flags = risk_flags if isinstance(risk_flags, list) else []
    task_mode = _normalize_guardian_task_mode(latest_state.get("task_mode")) or "reading"
    profile = _guardian_task_profile(task_mode)
    drivers = []

    def add_driver(key, label, value, impact, explanation, score):
        drivers.append(
            {
                "key": key,
                "label": label,
                "value": value,
                "impact": impact,
                "score": round(max(0.0, min(100.0, _safe_float(score, default=0.0))), 1),
                "explanation": _safe_text(explanation, max_length=220),
            }
        )

    switching_index = _optional_score_100(latest_state.get("switching_index"))
    if switching_index is not None and switching_index >= max(18.0, profile["switching_high"] * 0.45):
        impact = "high" if switching_index >= profile["switching_high"] else "medium"
        add_driver(
            "switching_index",
            "Task switching",
            switching_index,
            impact,
            f"Switching index is {switching_index}/100, which suggests attention is hopping across cues during this {task_mode} block.",
            switching_index,
        )

    cognitive_load = _optional_score_100(latest_state.get("cognitive_load"))
    if cognitive_load is not None and cognitive_load >= profile["load_medium"]:
        impact = "high" if cognitive_load >= profile["load_high"] else "medium"
        add_driver(
            "cognitive_load",
            "Cognitive load",
            cognitive_load,
            impact,
            f"Cognitive load is {cognitive_load}/100, so the current task is demanding more regulation than the {task_mode} baseline expects.",
            cognitive_load,
        )

    fatigue_risk = _optional_score_100(latest_state.get("fatigue_risk"))
    if fatigue_risk is not None and fatigue_risk >= profile["fatigue_medium"]:
        impact = "high" if fatigue_risk >= profile["fatigue_high"] else "medium"
        add_driver(
            "fatigue_risk",
            "Fatigue pressure",
            fatigue_risk,
            impact,
            f"Fatigue risk is {fatigue_risk}/100, which means energy regulation is starting to shape study performance.",
            fatigue_risk,
        )

    uncertainty_score = _optional_score_100(latest_state.get("uncertainty_score"))
    if uncertainty_score is not None and uncertainty_score >= profile["uncertainty_medium"]:
        impact = "high" if uncertainty_score >= profile["uncertainty_high"] else "medium"
        add_driver(
            "uncertainty_score",
            "Signal uncertainty",
            uncertainty_score,
            impact,
            f"Uncertainty is {uncertainty_score}/100, so the guardian is seeing a noisier-than-usual study-state signal.",
            uncertainty_score,
        )

    behavioral_alignment = _optional_score_100(latest_state.get("behavioral_alignment"))
    if behavioral_alignment is not None and behavioral_alignment <= profile["behavioral_drifting"]:
        impact = "high" if behavioral_alignment <= profile["behavioral_misaligned"] else "medium"
        add_driver(
            "behavioral_alignment",
            "Behavior alignment",
            behavioral_alignment,
            impact,
            f"Behavior alignment is only {behavioral_alignment}/100, which means the observed study pattern is drifting from the expected {task_mode} mode.",
            100.0 - behavioral_alignment,
        )

    scene_switch_rate = _optional_score_100(latest_state.get("scene_switch_rate"))
    if scene_switch_rate is not None and scene_switch_rate >= max(20.0, profile["switching_high"] * 0.5):
        impact = "high" if scene_switch_rate >= profile["switching_high"] else "medium"
        add_driver(
            "scene_switch_rate",
            "Scene switching",
            scene_switch_rate,
            impact,
            f"Scene switch rate is {scene_switch_rate}/100, which points to frequent context changes around the learner.",
            scene_switch_rate,
        )

    scene_lock_score = _optional_score_100(latest_state.get("scene_lock_score"))
    if scene_lock_score is not None and scene_lock_score <= 40:
        impact = "high" if scene_lock_score <= 28 else "medium"
        add_driver(
            "scene_lock_score",
            "Scene lock",
            scene_lock_score,
            impact,
            f"Scene lock is {scene_lock_score}/100, so the environment is not strongly anchoring the current task.",
            100.0 - scene_lock_score,
        )

    orientation_drift = _optional_score_100(latest_state.get("orientation_drift"))
    if orientation_drift is not None and orientation_drift >= 42:
        impact = "high" if orientation_drift >= 65 else "medium"
        add_driver(
            "orientation_drift",
            "Orientation drift",
            orientation_drift,
            impact,
            f"Orientation drift is {orientation_drift}/100, which suggests head or gaze alignment is pulling away from the intended study surface.",
            orientation_drift,
        )

    movement_intensity = _optional_score_100(latest_state.get("movement_intensity"))
    if movement_intensity is not None and movement_intensity >= 36:
        impact = "high" if movement_intensity >= 58 else "medium"
        add_driver(
            "movement_intensity",
            "Movement intensity",
            movement_intensity,
            impact,
            f"Movement intensity is {movement_intensity}/100, so physical motion is likely adding friction to this {task_mode} block.",
            movement_intensity,
        )

    blur_score = _optional_score_100(latest_state.get("blur_score"))
    if blur_score is not None and blur_score < 18:
        impact = "high" if blur_score < 10 else "medium"
        add_driver(
            "blur_score",
            "Scene clarity",
            blur_score,
            impact,
            f"Blur score is {blur_score}/100, which can make the signal noisier and weaken confidence in the current reading surface.",
            100.0 - blur_score,
        )

    brightness_score = _optional_score_100(latest_state.get("brightness_score"))
    if brightness_score is not None and (brightness_score < 14 or brightness_score > 88):
        impact = "high" if brightness_score < 8 or brightness_score > 94 else "medium"
        brightness_note = "too dim" if brightness_score < 14 else "too bright"
        add_driver(
            "brightness_score",
            "Brightness",
            brightness_score,
            impact,
            f"Brightness is {brightness_score}/100 and looks {brightness_note} for a stable {task_mode} signal.",
            abs(brightness_score - 50.0),
        )

    if latest_state.get("distraction"):
        add_driver(
            "distraction",
            "Reported distraction",
            latest_state.get("distraction"),
            "medium",
            f"Reported distraction: {latest_state.get('distraction')}. This is directly competing with the current study goal.",
            62.0,
        )
    if latest_state.get("support_needed"):
        add_driver(
            "support_needed",
            "Open support need",
            latest_state.get("support_needed"),
            "medium",
            "There is still an open support request, which usually raises load and slows recovery.",
            56.0,
        )

    unresolved_count = len(
        [item for item in focus_signals[-4:] if isinstance(item, dict) and not _safe_bool(item.get("resolved"), default=False)]
    )
    if unresolved_count:
        add_driver(
            "unresolved_signals",
            "Unresolved blockers",
            unresolved_count,
            "medium" if unresolved_count < 3 else "high",
            f"There are {unresolved_count} unresolved recent blocker signals, so the state has not fully settled yet.",
            min(100.0, 30.0 + (unresolved_count * 16.0)),
        )

    drivers.sort(key=lambda item: (0 if item["impact"] == "high" else 1, -item["score"]))
    primary_driver = drivers[0] if drivers else {}
    secondary_drivers = drivers[1:4]
    state_hint = _normalize_guardian_state_hint(latest_state.get("state_hint")) or "stable"
    state_hint_label = _guardian_state_hint_label(state_hint)

    why_this_state = f"The guardian marked this state as {state_hint_label.lower()}."
    if primary_driver:
        why_this_state = (
            f"The guardian marked this state as {state_hint_label.lower()} mainly because "
            f"{primary_driver.get('label', 'the top signal').lower()} is driving the pattern."
        )

    top_intervention = "Capture one more clean snapshot after the next focused block."
    if primary_driver:
        intervention_map = {
            "Task switching": "Reduce context switching first by keeping one surface open and hiding extra tabs or notifications.",
            "Cognitive load": "Reduce load first by shrinking the next checkpoint and removing any optional subtask.",
            "Fatigue pressure": "Shorten the next work block and take a recovery reset before pushing further.",
            "Signal uncertainty": "Collect one cleaner snapshot before changing the study plan so the signal can settle.",
            "Behavior alignment": "Realign the study behavior to the current task mode before trying to increase speed.",
            "Scene switching": "Stabilize the study environment and remove visual context changes before continuing.",
            "Scene lock": "Re-anchor the study surface so the learner has one clear visual target.",
            "Orientation drift": "Bring gaze and head alignment back to the study surface for one short block.",
            "Movement intensity": "Reduce physical movement and return to one stable work posture for the next checkpoint.",
            "Scene clarity": "Improve the visibility of the study surface before trusting the next state snapshot.",
            "Brightness": "Adjust lighting first so the signal is easier to read.",
            "Reported distraction": "Remove the named distraction before resuming the task.",
            "Open support need": "Resolve the open support need before pushing into a harder segment.",
            "Unresolved blockers": "Clear the unresolved blockers one by one so the state can settle.",
        }
        top_intervention = intervention_map.get(primary_driver.get("label"), top_intervention)

    return {
        "why_this_state": why_this_state,
        "primary_driver": primary_driver,
        "secondary_drivers": secondary_drivers,
        "drivers": drivers[:6],
        "top_intervention": top_intervention,
        "risk_flags": risk_flags[:5],
    }


def _guardian_transition_type(previous_hint, current_hint, previous_task_mode="", current_task_mode=""):
    previous_hint = _normalize_guardian_state_hint(previous_hint)
    current_hint = _normalize_guardian_state_hint(current_hint)
    previous_task_mode = _normalize_guardian_task_mode(previous_task_mode)
    current_task_mode = _normalize_guardian_task_mode(current_task_mode)

    if previous_task_mode and current_task_mode and previous_task_mode != current_task_mode:
        return "mode_shift"
    if not previous_hint:
        return "initial"
    if previous_hint == current_hint:
        return "steady"

    stable_family = {"stable", "productive_struggle"}
    risk_family = {"off_task_risk", "fatigue_risk", "signal_check", "load_rising"}

    if previous_hint in risk_family and current_hint in stable_family:
        return "recovery"
    if previous_hint in stable_family and current_hint in risk_family:
        return "worsening"
    if previous_hint == "productive_struggle" and current_hint == "stable":
        return "stabilized"
    if previous_hint == "stable" and current_hint == "productive_struggle":
        return "effort_rising"
    return "mixed_shift"


def _build_guardian_state_transition_summary(history, latest_state, tracker=None):
    history = [item for item in (history or []) if isinstance(item, dict)]
    latest_state = latest_state if isinstance(latest_state, dict) else {}
    tracker = tracker if isinstance(tracker, dict) else {}
    if not latest_state:
        return {}

    previous_state = history[-2] if len(history) >= 2 else {}
    previous_hint = _normalize_guardian_state_hint(previous_state.get("state_hint"))
    current_hint = _normalize_guardian_state_hint(latest_state.get("state_hint")) or "stable"
    previous_task_mode = _normalize_guardian_task_mode(previous_state.get("task_mode"))
    current_task_mode = _normalize_guardian_task_mode(latest_state.get("task_mode")) or "reading"
    transition_type = _guardian_transition_type(previous_hint, current_hint, previous_task_mode, current_task_mode)

    focus_delta = round(_safe_float(latest_state.get("focus_score"), default=0.0) - _safe_float(previous_state.get("focus_score"), default=0.0), 1)
    load_delta = round(_safe_float(latest_state.get("cognitive_load"), default=0.0) - _safe_float(previous_state.get("cognitive_load"), default=0.0), 1)
    fatigue_delta = round(_safe_float(latest_state.get("fatigue_risk"), default=0.0) - _safe_float(previous_state.get("fatigue_risk"), default=0.0), 1)
    alignment_delta = round(
        _safe_float(latest_state.get("behavioral_alignment"), default=0.0) - _safe_float(previous_state.get("behavioral_alignment"), default=0.0),
        1,
    )

    if transition_type == "initial":
        summary = "This is the first guardian snapshot, so there is no earlier state transition to compare yet."
    elif transition_type == "mode_shift":
        summary = f"The guardian shifted from {previous_task_mode or 'the previous mode'} into {current_task_mode}, so thresholds and expectations also changed."
    elif transition_type == "recovery":
        summary = (
            f"The state moved from {_guardian_state_hint_label(previous_hint).lower()} to "
            f"{_guardian_state_hint_label(current_hint).lower()}, with focus {focus_delta:+.1f} and load {load_delta:+.1f}."
        )
    elif transition_type == "worsening":
        summary = (
            f"The state moved from {_guardian_state_hint_label(previous_hint).lower()} to "
            f"{_guardian_state_hint_label(current_hint).lower()}, with focus {focus_delta:+.1f} and load {load_delta:+.1f}."
        )
    elif transition_type == "steady":
        summary = (
            f"The guardian kept the state in {_guardian_state_hint_label(current_hint).lower()}, "
            f"with focus {focus_delta:+.1f} and load {load_delta:+.1f} across the latest window."
        )
    else:
        summary = (
            f"The state shifted from {_guardian_state_hint_label(previous_hint).lower()} to "
            f"{_guardian_state_hint_label(current_hint).lower()}, with focus {focus_delta:+.1f} and load {load_delta:+.1f}."
        )

    active_event = tracker.get("active_event") if isinstance(tracker.get("active_event"), dict) else {}
    return {
        "transition_type": transition_type,
        "from_state_hint": previous_hint or "",
        "from_state_label": _guardian_state_hint_label(previous_hint) if previous_hint else "",
        "to_state_hint": current_hint,
        "to_state_label": _guardian_state_hint_label(current_hint),
        "focus_delta": focus_delta,
        "load_delta": load_delta,
        "fatigue_delta": fatigue_delta,
        "behavioral_alignment_delta": alignment_delta,
        "active_event_present": bool(active_event),
        "summary": summary,
    }


def _build_guardian_recovery_confidence(latest_state, baseline, tracker, risk_flags, transition_summary=None):
    latest_state = latest_state if isinstance(latest_state, dict) else {}
    baseline = baseline if isinstance(baseline, dict) else {}
    tracker = tracker if isinstance(tracker, dict) else {}
    risk_flags = risk_flags if isinstance(risk_flags, list) else []
    transition_summary = transition_summary if isinstance(transition_summary, dict) else {}

    active_event = tracker.get("active_event") if isinstance(tracker.get("active_event"), dict) else {}
    stable_count = _safe_int(tracker.get("stable_count"), default=0)
    sample_count = _safe_int(baseline.get("sample_count"), default=0)

    if not latest_state:
        return {}

    baseline_delta = _guardian_baseline_delta(latest_state, baseline)
    if active_event:
        score = 18.0
        if transition_summary.get("transition_type") == "recovery":
            score += 6.0
        score = max(0.0, min(100.0, score))
        label = "low"
        summary = (
            f"Recovery confidence is low because a guardian event is still active: "
            f"{_safe_text(active_event.get('primary_label'), max_length=120) or 'study-state difficulty'}."
        )
        return {
            "score": round(score, 1),
            "label": label,
            "stable_count": stable_count,
            "baseline_sample_count": sample_count,
            "baseline_delta": baseline_delta,
            "summary": summary,
        }

    closeness_penalty = 0.0
    if baseline_delta:
        closeness_penalty += abs(_safe_float(baseline_delta.get("focus_score"), default=0.0)) * 0.36
        closeness_penalty += max(0.0, _safe_float(baseline_delta.get("cognitive_load"), default=0.0)) * 0.34
        closeness_penalty += max(0.0, -_safe_float(baseline_delta.get("behavioral_alignment"), default=0.0)) * 0.20
        closeness_penalty += max(0.0, _safe_float(baseline_delta.get("fatigue_risk"), default=0.0)) * 0.16
        closeness_penalty += max(0.0, _safe_float(baseline_delta.get("uncertainty_score"), default=0.0)) * 0.10

    score = 76.0
    score -= min(48.0, closeness_penalty)
    score += min(12.0, stable_count * 5.0)
    score -= min(18.0, len(risk_flags) * 4.0)

    transition_type = transition_summary.get("transition_type")
    if transition_type == "recovery":
        score += 8.0
    elif transition_type == "worsening":
        score -= 10.0
    elif transition_type == "mode_shift":
        score -= 6.0

    state_hint = _normalize_guardian_state_hint(latest_state.get("state_hint")) or "stable"
    if state_hint == "stable":
        score += 6.0
    elif state_hint == "productive_struggle":
        score += 2.0
    elif state_hint in {"off_task_risk", "fatigue_risk"}:
        score -= 14.0

    if sample_count < 3:
        score -= 8.0

    score = round(max(0.0, min(100.0, score)), 1)
    if score >= 78.0:
        label = "high"
    elif score >= 52.0:
        label = "medium"
    else:
        label = "low"

    if label == "high":
        summary = "Recovery confidence is high: the latest state is close to the learner's recent baseline and no active guardian event remains."
    elif label == "medium":
        summary = "Recovery confidence is moderate: the state is stabilizing, but another clean block would confirm the recovery."
    else:
        summary = "Recovery confidence is still limited: the state has improved, but it has not yet fully returned to the learner's recent baseline."

    return {
        "score": score,
        "label": label,
        "stable_count": stable_count,
        "baseline_sample_count": sample_count,
        "baseline_delta": baseline_delta,
        "summary": summary,
    }


def _build_guardian_continuity_profile(history, latest_state, transition_summary=None, recovery_confidence=None, active_event=None):
    history = _guardian_recent_window(history)
    latest_state = latest_state if isinstance(latest_state, dict) else {}
    transition_summary = transition_summary if isinstance(transition_summary, dict) else {}
    recovery_confidence = recovery_confidence if isinstance(recovery_confidence, dict) else {}
    active_event = active_event if isinstance(active_event, dict) else {}
    if not history and not latest_state:
        return {}

    if not history and latest_state:
        history = [latest_state]

    def metric_volatility(field):
        values = []
        for item in history:
            if not isinstance(item, dict):
                continue
            value = item.get(field)
            if value in (None, ""):
                continue
            values.append(_safe_float(value, default=0.0))
        if len(values) < 2:
            return 0.0
        deltas = [abs(values[idx] - values[idx - 1]) for idx in range(1, len(values))]
        return round(sum(deltas) / len(deltas), 1)

    focus_volatility = metric_volatility("focus_score")
    load_volatility = metric_volatility("cognitive_load")
    alignment_volatility = metric_volatility("behavioral_alignment")
    fatigue_volatility = metric_volatility("fatigue_risk")

    volatility_index = round(
        min(
            100.0,
            (focus_volatility * 0.30)
            + (load_volatility * 0.30)
            + (alignment_volatility * 0.22)
            + (fatigue_volatility * 0.18),
        ),
        1,
    )

    continuity_score = 100.0 - volatility_index
    transition_type = transition_summary.get("transition_type")
    if transition_type == "mode_shift":
        continuity_score -= 14.0
    elif transition_type == "worsening":
        continuity_score -= 10.0
    elif transition_type == "recovery":
        continuity_score += 8.0
    elif transition_type == "steady":
        continuity_score += 4.0

    if active_event:
        continuity_score -= 24.0

    recovery_label = _safe_text(recovery_confidence.get("label"), max_length=20).lower()
    if recovery_label == "high":
        continuity_score += 8.0
    elif recovery_label == "low":
        continuity_score -= 10.0

    continuity_score = round(max(0.0, min(100.0, continuity_score)), 1)
    if continuity_score >= 74.0:
        stability_band = "stable"
    elif continuity_score >= 46.0:
        stability_band = "mixed"
    else:
        stability_band = "volatile"

    if stability_band == "stable":
        summary = "The guardian sees this study state as relatively stable across the recent window."
    elif stability_band == "mixed":
        summary = "The guardian sees partial stability, but the recent window still shows meaningful swings."
    else:
        summary = "The guardian sees a volatile state pattern, so short-term interventions matter more than long planning."

    return {
        "continuity_score": continuity_score,
        "stability_band": stability_band,
        "volatility_index": volatility_index,
        "focus_volatility": focus_volatility,
        "load_volatility": load_volatility,
        "behavioral_volatility": alignment_volatility,
        "fatigue_volatility": fatigue_volatility,
        "window_size": len(history),
        "summary": summary,
    }


def _build_guardian_intervention_plan(
    latest_state,
    state_explanation,
    recent_trend_window,
    recovery_confidence,
    transition_summary,
    active_event,
    risk_flags,
):
    latest_state = latest_state if isinstance(latest_state, dict) else {}
    state_explanation = state_explanation if isinstance(state_explanation, dict) else {}
    recent_trend_window = recent_trend_window if isinstance(recent_trend_window, dict) else {}
    recovery_confidence = recovery_confidence if isinstance(recovery_confidence, dict) else {}
    transition_summary = transition_summary if isinstance(transition_summary, dict) else {}
    active_event = active_event if isinstance(active_event, dict) else {}
    risk_flags = risk_flags if isinstance(risk_flags, list) else []

    primary_driver = _ensure_payload_dict(state_explanation.get("primary_driver"))
    driver_label = _safe_text(primary_driver.get("label"), max_length=80)
    driver_key = _safe_text(primary_driver.get("key"), max_length=80).lower()
    transition_type = _safe_text(transition_summary.get("transition_type"), max_length=40).lower()
    recovery_label = _safe_text(recovery_confidence.get("label"), max_length=20).lower()
    trend_signals = _ensure_payload_dict(recent_trend_window.get("signals"))
    load_trend = _ensure_payload_dict(trend_signals.get("cognitive_load"))
    fatigue_trend = _ensure_payload_dict(trend_signals.get("fatigue_risk"))
    switching_trend = _ensure_payload_dict(trend_signals.get("switching_index"))
    uncertainty_trend = _ensure_payload_dict(trend_signals.get("uncertainty_score"))

    category = "maintain_focus"
    priority = "medium"
    immediate_action = "Keep the next block narrow and log one more clean state snapshot."
    next_checkpoint = "Re-check the guardian state after the next focused block."
    rationale = state_explanation.get("why_this_state", "The guardian is using the current state pattern to suggest the next action.")

    if active_event:
        priority = "high"
        next_checkpoint = "Check again after the active guardian event has been intentionally addressed."
        if "switch" in driver_key or "switch" in driver_label.lower():
            category = "switching_containment"
            immediate_action = "Close extra tabs or surfaces and keep only one study target open for the next block."
        elif "fatigue" in driver_key or "fatigue" in driver_label.lower():
            category = "fatigue_reset"
            immediate_action = "Take a short recovery reset and restart with a smaller checkpoint instead of pushing through."
        elif "uncertainty" in driver_key or "signal" in driver_label.lower():
            category = "signal_cleanup"
            immediate_action = "Stabilize the study setup first and capture one cleaner snapshot before making a bigger decision."
        else:
            category = "load_trim"
            immediate_action = "Shrink the task scope immediately and remove one friction point before continuing."
    elif transition_type == "worsening" or load_trend.get("direction") == "worsening":
        category = "load_trim"
        priority = "high" if recovery_label == "low" else "medium"
        immediate_action = "Reduce the next checkpoint so the learner only has one visible sub-goal to finish."
        next_checkpoint = "Review the load signal after one smaller checkpoint instead of a full study block."
    elif fatigue_trend.get("direction") == "worsening" or _safe_text(latest_state.get("fatigue_level"), max_length=20).lower() == "high":
        category = "fatigue_reset"
        priority = "high" if recovery_label == "low" else "medium"
        immediate_action = "Shorten the next work block and recover before attempting another deep-focus segment."
        next_checkpoint = "Capture a fresh snapshot after the recovery reset."
    elif switching_trend.get("direction") == "worsening" or "switching" in driver_key or "scene switching" in driver_label.lower():
        category = "switching_containment"
        priority = "medium"
        immediate_action = "Reduce context switching by committing to one surface and one next action only."
        next_checkpoint = "Check whether switching and drift drop after one stable block."
    elif uncertainty_trend.get("direction") == "worsening" or recovery_label == "low":
        category = "signal_cleanup"
        priority = "medium"
        immediate_action = "Clean up the study setup and capture one clearer signal before making a plan change."
        next_checkpoint = "Collect one cleaner state snapshot in the same task mode."
    elif transition_type == "recovery" and recovery_label in {"medium", "high"}:
        category = "recovery_hold"
        priority = "low"
        immediate_action = "Hold the current routine steady for one more block instead of changing strategy again."
        next_checkpoint = "Confirm that the recovered state remains stable across one more block."
    elif risk_flags:
        category = "risk_first"
        priority = "medium"
        immediate_action = f"Address the top risk first: {risk_flags[0]}."
        next_checkpoint = "Re-check the guardian after the top risk has been reduced."

    summary = f"Priority: {priority}. Immediate action: {immediate_action}"
    return {
        "category": category,
        "priority": priority,
        "driver_label": driver_label,
        "immediate_action": immediate_action,
        "next_checkpoint": next_checkpoint,
        "rationale": rationale,
        "summary": summary,
    }


def _refresh_guardian_derived_state(state):
    state = _ensure_payload_dict(state)
    history = [item for item in state.get("state_history", []) if isinstance(item, dict)]
    signals = [item for item in state.get("focus_signals", []) if isinstance(item, dict)]
    latest_state = state.get("latest_state", {}) if isinstance(state.get("latest_state"), dict) else {}
    if latest_state:
        latest_state = _finalize_guardian_snapshot(
            latest_state,
            recent_history=history[:-1] if history else [],
            focus_signals=signals,
        )
        state["latest_state"] = latest_state

    task_mode = _normalize_guardian_task_mode(state.get("task_mode")) or _normalize_guardian_task_mode(latest_state.get("task_mode")) or "reading"
    baseline = _build_guardian_personal_baseline(history, task_mode=task_mode)
    risk_flags = state.get("risk_flags", []) or _guardian_risk_flags_from_state(latest_state, signals)
    tracker = state.get("difficulty_tracker") if isinstance(state.get("difficulty_tracker"), dict) else _default_guardian_difficulty_tracker()
    trend_window = _build_guardian_recent_trend_window(history, latest_state, baseline)
    transition_summary = _build_guardian_state_transition_summary(history, latest_state, tracker=tracker)
    recovery_confidence = _build_guardian_recovery_confidence(
        latest_state,
        baseline,
        tracker,
        risk_flags,
        transition_summary=transition_summary,
    )
    active_event = tracker.get("active_event") if isinstance(tracker.get("active_event"), dict) else {}
    continuity_profile = _build_guardian_continuity_profile(
        history,
        latest_state,
        transition_summary=transition_summary,
        recovery_confidence=recovery_confidence,
        active_event=active_event,
    )
    state_explanation = _guardian_state_explanation(latest_state, signals, risk_flags)
    intervention_plan = _build_guardian_intervention_plan(
        latest_state,
        state_explanation,
        trend_window,
        recovery_confidence,
        transition_summary,
        active_event,
        risk_flags,
    )

    state["task_mode"] = task_mode
    state["risk_flags"] = risk_flags
    state["personal_baseline"] = baseline
    state["recent_trend_window"] = trend_window
    state["state_transition_summary"] = transition_summary
    state["recovery_confidence"] = recovery_confidence
    state["state_explanation"] = state_explanation
    state["continuity_profile"] = continuity_profile
    state["intervention_plan"] = intervention_plan
    return state


def _build_learning_state_review(mission):
    state = _ensure_payload_dict(mission.get("learning_state_guardian"))
    state = _refresh_guardian_derived_state(state)
    history = [item for item in state.get("state_history", []) if isinstance(item, dict)]
    signals = [item for item in state.get("focus_signals", []) if isinstance(item, dict)]
    latest_state = state.get("latest_state", {}) if isinstance(state.get("latest_state"), dict) else {}
    if not latest_state and history:
        latest_state = history[-1]

    recent_history = _guardian_recent_window(history)
    averages = {
        "focus_level": round(sum(_safe_int(item.get("focus_level"), default=0) for item in recent_history) / len(recent_history), 1)
        if recent_history
        else 0.0,
        "energy_level": round(sum(_safe_int(item.get("energy_level"), default=0) for item in recent_history) / len(recent_history), 1)
        if recent_history
        else 0.0,
        "stress_level": round(sum(_safe_int(item.get("stress_level"), default=0) for item in recent_history) / len(recent_history), 1)
        if recent_history
        else 0.0,
        "focus_score": _guardian_numeric_average(recent_history, "focus_score"),
        "cognitive_load": _guardian_numeric_average(recent_history, "cognitive_load"),
        "behavioral_alignment": _guardian_numeric_average(recent_history, "behavioral_alignment"),
        "fatigue_risk": _guardian_numeric_average(recent_history, "fatigue_risk"),
        "uncertainty_score": _guardian_numeric_average(recent_history, "uncertainty_score"),
    }
    risk_flags = state.get("risk_flags", [])
    active_difficulty_event = _guardian_difficulty_public_event(
        _ensure_payload_dict(_ensure_payload_dict(state.get("difficulty_tracker")).get("active_event")),
        status="active",
    )
    recent_difficulty_events = [
        _guardian_difficulty_public_event(item, status="resolved")
        for item in [entry for entry in state.get("difficulty_events", []) if isinstance(entry, dict)][-4:]
    ]
    state_explanation = _ensure_payload_dict(state.get("state_explanation")) or _guardian_state_explanation(latest_state, signals, risk_flags)
    personal_baseline = _ensure_payload_dict(state.get("personal_baseline"))
    recent_trend_window = _ensure_payload_dict(state.get("recent_trend_window"))
    state_transition_summary = _ensure_payload_dict(state.get("state_transition_summary"))
    recovery_confidence = _ensure_payload_dict(state.get("recovery_confidence"))
    continuity_profile = _ensure_payload_dict(state.get("continuity_profile"))
    intervention_plan = _ensure_payload_dict(state.get("intervention_plan"))
    recent_hints = [
        _normalize_guardian_state_hint(item.get("state_hint"))
        for item in recent_history
        if _normalize_guardian_state_hint(item.get("state_hint"))
    ]
    hint_counter = Counter(recent_hints)
    dominant_state_hint = hint_counter.most_common(1)[0][0] if hint_counter else _normalize_guardian_state_hint(
        latest_state.get("state_hint")
    )
    trend_signals = {
        "focus_score": _guardian_metric_trend(recent_history, "focus_score", higher_is_better=True, threshold=8.0),
        "cognitive_load": _guardian_metric_trend(recent_history, "cognitive_load", higher_is_better=False, threshold=8.0),
        "behavioral_alignment": _guardian_metric_trend(
            recent_history,
            "behavioral_alignment",
            higher_is_better=True,
            threshold=8.0,
        ),
        "fatigue_risk": _guardian_metric_trend(recent_history, "fatigue_risk", higher_is_better=False, threshold=8.0),
        "uncertainty_score": _guardian_metric_trend(
            recent_history,
            "uncertainty_score",
            higher_is_better=False,
            threshold=8.0,
        ),
    }
    coach_message = _safe_text(intervention_plan.get("summary"), max_length=240) or "Record one state snapshot with focus, load, and fatigue so the guardian can spot trends."
    if not intervention_plan:
        if dominant_state_hint == "fatigue_risk":
            coach_message = "Fatigue risk is rising. Shorten the next block, reduce scope, and return only after a clear reset."
        elif dominant_state_hint == "off_task_risk":
            coach_message = "Your study behavior is drifting from the task. Remove one distraction and restate the next checkpoint before continuing."
        elif active_difficulty_event:
            coach_message = (
                f"A sustained guardian event is active: {active_difficulty_event.get('primary_label') or 'study-state difficulty'}. "
                "Treat this as a live intervention point before pushing deeper into the task."
            )
        elif dominant_state_hint == "signal_check":
            coach_message = "The signal is still warming up. Capture one more clean snapshot before making a bigger study decision."
        elif dominant_state_hint == "productive_struggle":
            coach_message = "This looks like productive struggle. Stay with the current task, but keep the finish line narrow."
        elif risk_flags:
            coach_message = f"The main study-state risk is {risk_flags[0]}. Reduce one friction point before the next work block."
        elif latest_state.get("current_task") or state.get("current_task"):
            coach_message = (
                f"Stay with {latest_state.get('current_task') or state.get('current_task')} until one visible checkpoint is finished, "
                "then log the next state snapshot."
            )

    return {
        "current_task": state.get("current_task", ""),
        "session_goal": state.get("session_goal", ""),
        "current_course": state.get("current_course", ""),
        "environment": state.get("environment", ""),
        "task_mode": state.get("task_mode", "") or latest_state.get("task_mode", ""),
        "latest_state": latest_state,
        "core_metrics": {
            "focus_score": latest_state.get("focus_score"),
            "cognitive_load": latest_state.get("cognitive_load"),
            "behavioral_alignment": latest_state.get("behavioral_alignment"),
            "fatigue_risk": latest_state.get("fatigue_risk"),
            "uncertainty_score": latest_state.get("uncertainty_score"),
            "switching_index": latest_state.get("switching_index"),
            "drift_trend": latest_state.get("drift_trend"),
            "stability": latest_state.get("stability"),
        },
        "state_classification": {
            "state_hint": latest_state.get("state_hint", ""),
            "state_hint_label": _guardian_state_hint_label(latest_state.get("state_hint")),
            "load_level": latest_state.get("load_level", ""),
            "fatigue_level": latest_state.get("fatigue_level", ""),
            "behavioral_level": latest_state.get("behavioral_level", ""),
            "confidence_level": latest_state.get("confidence_level", ""),
            "load_reason": latest_state.get("load_reason", ""),
        },
        "sensor_snapshot": _guardian_sensor_snapshot_payload(latest_state),
        "state_history_count": len(history),
        "recent_focus_signals": signals[-4:],
        "risk_flags": risk_flags,
        "state_explanation": state_explanation,
        "difficulty_tracking": {
            "active_event": active_difficulty_event,
            "recent_events": recent_difficulty_events,
            "event_count": len([item for item in state.get("difficulty_events", []) if isinstance(item, dict)]),
        },
        "personal_baseline": personal_baseline,
        "recent_trend_window": recent_trend_window,
        "state_transition_summary": state_transition_summary,
        "recovery_confidence": recovery_confidence,
        "continuity_profile": continuity_profile,
        "intervention_plan": intervention_plan,
        "trend_averages": averages,
        "trend_signals": trend_signals,
        "dominant_state_hint": dominant_state_hint,
        "coach_message": coach_message,
        "updated_at": state.get("updated_at", ""),
    }


def _build_presentation_live_hud(mission, latest_rehearsal_analysis=None):
    mission = mission if isinstance(mission, dict) else {}
    sections = _normalize_sections(mission.get("script_sections", []), target_duration_minutes=mission.get("target_duration_minutes", 0.0))
    presentation_state = _presentation_state_payload(mission.get("presentation_state", {}), sections)
    active_card = _ensure_payload_dict(presentation_state.get("active_card"))
    next_card = _ensure_payload_dict(presentation_state.get("next_card"))
    latest_rehearsal_analysis = _ensure_payload_dict(latest_rehearsal_analysis)
    transcript_analysis = _ensure_payload_dict(latest_rehearsal_analysis.get("transcript_analysis"))
    section_timing_summary = _ensure_payload_dict(latest_rehearsal_analysis.get("section_timing_summary"))

    section_hint = _section_duration_hint(
        _estimate_section_seconds(_active_section(mission)),
        active_card.get("target_seconds", 0),
    )
    if latest_rehearsal_analysis.get("timing_status") == "long":
        status_line = "Current run is still long against the target window."
    elif latest_rehearsal_analysis.get("timing_status") == "short":
        status_line = "Current run is still short and needs one more beat."
    elif section_hint.get("status") == "long":
        status_line = "Current slide looks dense for the target window."
    elif section_hint.get("status") == "short":
        status_line = "Current slide may need one more beat."
    else:
        status_line = "Current slide looks ready for the next rehearsal pass."

    cue_line = ""
    if presentation_state.get("cue_view") == "visible":
        cue_line = (
            active_card.get("cue_cards")
            or active_card.get("outline")
            or active_card.get("slide_anchor")
            or ""
        )

    issue_line = ""
    issues = transcript_analysis.get("issues", [])
    if issues:
        first_issue = _ensure_payload_dict(issues[0])
        issue_line = first_issue.get("message") or first_issue.get("label") or ""
    elif section_timing_summary.get("largest_overrun"):
        largest_overrun = _ensure_payload_dict(section_timing_summary.get("largest_overrun"))
        issue_line = (
            f"{largest_overrun.get('section_title', 'A section')} is still over target by "
            f"{largest_overrun.get('over_seconds', 0)} seconds."
        )

    next_action_line = ""
    recommendations = latest_rehearsal_analysis.get("recommendations", [])
    if isinstance(recommendations, list) and recommendations:
        next_action_line = _safe_text(recommendations[0], max_length=120, preserve_lines=True)
    elif latest_rehearsal_analysis.get("timing_note"):
        next_action_line = _safe_text(latest_rehearsal_analysis.get("timing_note"), max_length=120, preserve_lines=True)
    elif mission.get("presentation_state", {}).get("focus_area"):
        next_action_line = f"Stay with {mission.get('presentation_state', {}).get('focus_area')} for the next rehearsal checkpoint."

    return {
        "mode": "presentation_live",
        "mission_id": mission.get("mission_id", ""),
        "presentation_mode": presentation_state.get("presentation_mode", "rehearse"),
        "cue_view": presentation_state.get("cue_view", "visible"),
        "control_source": presentation_state.get("control_source", "phone"),
        "active_slide_index": active_card.get("slide_index", 0),
        "active_slide_title": active_card.get("slide_title", ""),
        "active_slide_anchor": active_card.get("slide_anchor", ""),
        "active_chunk_index": active_card.get("active_chunk_index", 0),
        "active_chunk_count": active_card.get("active_chunk_count", 0),
        "chunk_progress_label": active_card.get("active_chunk_label", "0/0"),
        "previous_chunk_preview": _safe_text(active_card.get("previous_chunk_text", ""), max_length=96, preserve_lines=True),
        "next_chunk_preview": _safe_text(active_card.get("next_chunk_text", ""), max_length=96, preserve_lines=True),
        "chunk_jump_supported": bool(active_card.get("chunk_jump_supported")),
        "teleprompter_source": active_card.get("teleprompter_source", "empty"),
        "teleprompter_text": _safe_text(active_card.get("active_chunk_text") or active_card.get("teleprompter_text"), max_length=320, preserve_lines=True),
        "cue_line": _safe_text(cue_line, max_length=96, preserve_lines=True),
        "interaction_hint": _safe_text(active_card.get("interaction_goal", ""), max_length=84, preserve_lines=True),
        "status_line": _safe_text(status_line, max_length=100, preserve_lines=True),
        "issue_line": _safe_text(issue_line, max_length=120, preserve_lines=True),
        "next_action_line": _safe_text(next_action_line, max_length=120, preserve_lines=True),
        "next_slide_index": next_card.get("slide_index", 0),
        "next_slide_title": next_card.get("slide_title", ""),
        "target_seconds": _safe_int(active_card.get("target_seconds"), default=0),
        "target_label": _format_mmss(active_card.get("target_seconds", 0)),
        "updated_at": _now_iso(),
    }


def _build_review(mission):
    sections = mission.get("script_sections", [])
    state = _presentation_state_payload(mission.get("presentation_state", {}), sections)
    difficulty_events = mission.get("difficulty_events", [])
    rehearsal_history = mission.get("rehearsal_history", [])
    latest_difficulty = difficulty_events[-1] if difficulty_events else {}
    latest_rehearsal = rehearsal_history[-1] if rehearsal_history else {}
    script_summary = _build_script_summary(sections, target_minutes=mission.get("target_duration_minutes", 0.0))
    latest_rehearsal_analysis = latest_rehearsal.get("analysis", {}) or _build_rehearsal_analysis(mission, latest_rehearsal)
    readiness_summary = _build_readiness_summary(
        mission,
        script_summary,
        latest_difficulty,
        latest_rehearsal_analysis,
    )
    live_hud = _build_presentation_live_hud(mission, latest_rehearsal_analysis=latest_rehearsal_analysis)

    return {
        "mission_id": mission.get("mission_id"),
        "session_id": mission.get("session_id"),
        "mission_brief": {
            "title": mission.get("title", ""),
            "course": mission.get("course", ""),
            "deadline": mission.get("deadline", ""),
            "deliverable_type": mission.get("deliverable_type", "presentation"),
            "target_duration_minutes": mission.get("target_duration_minutes", 0.0),
            "audience": mission.get("audience", ""),
            "focus_goal": mission.get("focus_goal", ""),
            "teacher_requirements": mission.get("teacher_requirements", ""),
        },
        "script_overview": {
            **script_summary,
            "sections": [
                {
                    "section_id": item.get("section_id", ""),
                    "title": item.get("title", ""),
                    "slide_index": item.get("slide_index", 0),
                    "slide_title": item.get("slide_title", ""),
                    "planned_seconds": item.get("planned_seconds", 0),
                    "target_seconds": item.get("target_seconds", item.get("planned_seconds", 0)),
                    "interaction_goal": item.get("interaction_goal", ""),
                    "teleprompter_source": _teleprompter_state(item).get("teleprompter_source", "empty"),
                    "status": item.get("status", "draft"),
                }
                for item in sections
            ],
        },
        "presentation_state": state,
        "live_hud": live_hud,
        "difficulty_overview": {
            "count": len(difficulty_events),
            "latest": latest_difficulty,
            "recent": difficulty_events[-3:],
        },
        "rehearsal_overview": {
            "count": len(rehearsal_history),
            "latest": latest_rehearsal,
            "latest_analysis": latest_rehearsal_analysis,
        },
        "section_coaching": _build_section_coaching(mission, latest_rehearsal_analysis),
        "delivery_risks": _build_delivery_risks(
            mission,
            script_summary,
            latest_difficulty,
            latest_rehearsal_analysis,
        ),
        "readiness_summary": readiness_summary,
        "practice_drills": _build_practice_drills(
            mission,
            latest_difficulty,
            latest_rehearsal_analysis,
        ),
        "qa_prep": _build_qa_prep(mission),
        "reflection_coach": _build_reflection_review(mission),
        "learning_state_guardian": _build_learning_state_review(mission),
        "coaching_summary": _build_coaching_summary(mission, script_summary, difficulty_events, rehearsal_history),
        "next_actions": _build_next_actions(mission),
        "updated_at": mission.get("updated_at", ""),
    }


def _mission_payload(mission):
    reflection_state = _ensure_payload_dict(mission.get("reflection_coach"))
    guardian_state = _ensure_payload_dict(mission.get("learning_state_guardian"))
    return {
        "mission_id": mission.get("mission_id", ""),
        "session_id": mission.get("session_id", ""),
        "title": mission.get("title", ""),
        "course": mission.get("course", ""),
        "deadline": mission.get("deadline", ""),
        "deliverable_type": mission.get("deliverable_type", "presentation"),
        "target_duration_minutes": mission.get("target_duration_minutes", 0.0),
        "audience": mission.get("audience", ""),
        "teacher_requirements": mission.get("teacher_requirements", ""),
        "task_description": mission.get("task_description", ""),
        "intake_task_text": mission.get("intake_task_text", ""),
        "focus_goal": mission.get("focus_goal", ""),
        "script_sections": copy.deepcopy(mission.get("script_sections", [])),
        "presentation_state": _presentation_state_payload(
            mission.get("presentation_state", {}),
            mission.get("script_sections", []),
        ),
        "live_hud": _build_presentation_live_hud(mission),
        "script_summary": _build_script_summary(
            mission.get("script_sections", []),
            target_minutes=mission.get("target_duration_minutes", 0.0),
        ),
        "difficulty_events": copy.deepcopy(mission.get("difficulty_events", [])[-6:]),
        "rehearsal_history": copy.deepcopy(mission.get("rehearsal_history", [])[-6:]),
        "chat_history": copy.deepcopy(mission.get("chat_history", [])[-10:]),
        "reflection_coach": {
            "focus_theme": reflection_state.get("focus_theme", ""),
            "current_course": reflection_state.get("current_course", ""),
            "target_habit": reflection_state.get("target_habit", ""),
            "learner_note": reflection_state.get("learner_note", ""),
            "next_goal": reflection_state.get("next_goal", ""),
            "latest_reflection": copy.deepcopy(reflection_state.get("latest_reflection", {})),
            "recent_commitments": copy.deepcopy(reflection_state.get("action_commitments", [])[-5:]),
            "recent_wins": copy.deepcopy(reflection_state.get("wins", [])[-5:]),
            "updated_at": reflection_state.get("updated_at", ""),
        },
        "learning_state_guardian": {
            "current_task": guardian_state.get("current_task", ""),
            "session_goal": guardian_state.get("session_goal", ""),
            "current_course": guardian_state.get("current_course", ""),
            "environment": guardian_state.get("environment", ""),
            "latest_state": copy.deepcopy(guardian_state.get("latest_state", {})),
            "recent_focus_signals": copy.deepcopy(guardian_state.get("focus_signals", [])[-5:]),
            "risk_flags": copy.deepcopy(guardian_state.get("risk_flags", [])[-5:]),
            "updated_at": guardian_state.get("updated_at", ""),
        },
        "created_at": mission.get("created_at", ""),
        "updated_at": mission.get("updated_at", ""),
    }


def _apply_mission_update(mission, payload):
    mission["title"] = _safe_text(payload.get("title"), max_length=180) or mission.get("title", "")
    mission["course"] = _safe_text(payload.get("course"), max_length=180) or mission.get("course", "")
    mission["deadline"] = _safe_text(payload.get("deadline"), max_length=120) or mission.get("deadline", "")
    mission["deliverable_type"] = (
        _safe_text(payload.get("deliverable_type"), max_length=80) or mission.get("deliverable_type", "presentation")
    )
    mission["target_duration_minutes"] = round(
        _safe_float(payload.get("target_duration_minutes"), default=mission.get("target_duration_minutes", 0.0)),
        1,
    )
    mission["audience"] = _safe_text(payload.get("audience"), max_length=240) or mission.get("audience", "")
    mission["teacher_requirements"] = (
        _safe_text(payload.get("teacher_requirements"), max_length=2400, preserve_lines=True)
        or mission.get("teacher_requirements", "")
    )
    mission["task_description"] = (
        _safe_text(payload.get("task_description"), max_length=6000, preserve_lines=True)
        or mission.get("task_description", "")
    )
    mission["intake_task_text"] = (
        _safe_text(payload.get("intake_task_text"), max_length=6000, preserve_lines=True)
        or mission.get("intake_task_text", "")
    )
    mission["focus_goal"] = _safe_text(payload.get("focus_goal"), max_length=240) or mission.get("focus_goal", "")

    outline_points = payload.get("outline_points")
    if isinstance(outline_points, list) and outline_points and "script_sections" not in payload:
        payload = {
            **payload,
            "script_sections": [{"title": point} for point in outline_points if _safe_text(point, max_length=120)],
        }

    if "script_sections" in payload:
        mission["script_sections"] = _normalize_sections(
            payload.get("script_sections"),
            target_duration_minutes=mission.get("target_duration_minutes", 0.0),
        )
    else:
        mission["script_sections"] = _normalize_sections(
            mission.get("script_sections", []),
            target_duration_minutes=mission.get("target_duration_minutes", 0.0),
        )

    direct_state = {
        "phase": payload.get("phase"),
        "presentation_mode": payload.get("presentation_mode"),
        "cue_view": payload.get("cue_view"),
        "active_section_id": payload.get("active_section_id"),
        "active_chunk_index": payload.get("active_chunk_index"),
        "progress_note": payload.get("progress_note"),
        "focus_area": payload.get("focus_area"),
        "focus_level": payload.get("focus_level"),
        "confidence_level": payload.get("confidence_level"),
        "control_source": payload.get("control_source"),
        "last_action": payload.get("last_action"),
        "last_control_at": payload.get("last_control_at"),
        "last_rehearsed_at": payload.get("last_rehearsed_at"),
        "rehearsal_count": payload.get("rehearsal_count"),
    }
    incoming_state = _ensure_payload_dict(payload.get("presentation_state"))
    mission["presentation_state"] = _normalize_presentation_state(
        mission.get("script_sections", []),
        existing=mission.get("presentation_state"),
        incoming={**incoming_state, **{k: v for k, v in direct_state.items() if v is not None}},
    )
    return {
        "operation": "upsert_mission",
        "updated_title": mission.get("title", ""),
        "section_count": len(mission.get("script_sections", [])),
    }


def _apply_script_section_update(mission, payload):
    sections = _normalize_sections(
        mission.get("script_sections", []),
        target_duration_minutes=mission.get("target_duration_minutes", 0.0),
    )
    requested_section_id = _safe_text(payload.get("section_id"), max_length=80)
    requested_slide_index = max(1, _safe_int(payload.get("slide_index"), default=len(sections) + 1))

    target_index = None
    for index, section in enumerate(sections):
        if requested_section_id and section.get("section_id") == requested_section_id:
            target_index = index
            break
    if target_index is None and payload.get("create_if_missing"):
        sections.append(
            {
                "section_id": requested_section_id or _build_id("section"),
                "title": _safe_text(payload.get("title"), max_length=120) or f"Section {len(sections) + 1}",
                "slide_index": requested_slide_index,
                "slide_title": _safe_text(payload.get("slide_title"), max_length=120) or _safe_text(payload.get("title"), max_length=120),
                "slide_anchor": "",
                "interaction_goal": "",
                "planned_seconds": max(15, _safe_int(payload.get("target_seconds"), default=45)),
                "target_seconds": max(15, _safe_int(payload.get("target_seconds"), default=45)),
                "outline": "",
                "speaker_notes": "",
                "teleprompter_script": "",
                "cue_cards": "",
                "keywords": [],
                "status": "draft",
            }
        )
        target_index = len(sections) - 1
    if target_index is None:
        raise ValueError("section_id was not found. Pass create_if_missing=true to add a new section.")

    section = dict(sections[target_index])
    title = _safe_text(payload.get("title"), max_length=120) or section.get("title", "")
    section["title"] = title or section.get("title", "")
    section["name"] = section["title"]
    section["slide_index"] = max(1, _safe_int(payload.get("slide_index"), default=section.get("slide_index", target_index + 1)))
    section["slide_title"] = _safe_text(payload.get("slide_title"), max_length=120) or section.get("slide_title", "") or section["title"]
    section["slide_anchor"] = _safe_text(payload.get("slide_anchor"), max_length=120) or section.get("slide_anchor", "")
    section["interaction_goal"] = _safe_text(payload.get("interaction_goal"), max_length=240) or section.get("interaction_goal", "")
    if "target_seconds" in payload or "planned_seconds" in payload:
        section_seconds = max(10, _safe_int(payload.get("target_seconds"), default=_safe_int(payload.get("planned_seconds"), default=section.get("target_seconds", 45))))
        section["planned_seconds"] = section_seconds
        section["target_seconds"] = section_seconds
    section["outline"] = _safe_text(payload.get("outline"), max_length=2400, preserve_lines=True) or section.get("outline", "")
    section["speaker_notes"] = _safe_text(payload.get("speaker_notes"), max_length=4000, preserve_lines=True) or section.get("speaker_notes", "")
    section["teleprompter_script"] = _safe_text(payload.get("teleprompter_script"), max_length=9000, preserve_lines=True) or section.get("teleprompter_script", "")
    section["cue_cards"] = _safe_text(payload.get("cue_cards"), max_length=1800, preserve_lines=True) or section.get("cue_cards", "")
    if "keywords" in payload:
        section["keywords"] = _normalize_keywords(payload.get("keywords"))
    section["status"] = _normalize_section_status(payload.get("status") or section.get("status"))
    sections[target_index] = section

    mission["script_sections"] = _normalize_sections(
        sections,
        target_duration_minutes=mission.get("target_duration_minutes", 0.0),
    )
    mission["presentation_state"] = _normalize_presentation_state(
        mission.get("script_sections", []),
        existing=mission.get("presentation_state"),
        incoming={
            **_ensure_payload_dict(payload.get("presentation_state")),
            "active_section_id": section.get("section_id", ""),
        },
    )
    return {
        "operation": "update_script_section",
        "section": _card_payload(
            _active_section(mission),
            presentation_mode=mission.get("presentation_state", {}).get("presentation_mode", "rehearse"),
            cue_view=mission.get("presentation_state", {}).get("cue_view", "visible"),
            active_chunk_index=mission.get("presentation_state", {}).get("active_chunk_index", 0),
        ),
        "script_summary": _build_script_summary(
            mission.get("script_sections", []),
            target_minutes=mission.get("target_duration_minutes", 0.0),
        ),
    }


def _extract_intake_result(payload):
    task_text = _safe_text(payload.get("task_text") or payload.get("intake_task_text"), max_length=6000, preserve_lines=True)
    if not task_text:
        raise ValueError("task_text is required for intake extraction.")

    heuristic = _heuristic_intake_candidates(task_text)
    candidates = heuristic["candidates"]
    if payload.get("mission_id"):
        candidates["mission_id"] = _safe_text(payload.get("mission_id"), max_length=80)
    return {
        "operation": "extract_intake",
        "task_text": task_text,
        "candidates": candidates,
        "suggested_sections": heuristic["suggested_sections"],
        "notes": heuristic["notes"],
    }


def _apply_control_action(mission, payload):
    sections = mission.get("script_sections", [])
    state = mission.get("presentation_state", {})
    if not sections:
        mission["script_sections"] = _default_sections(
            mission.get("target_duration_minutes", 0.0),
            mission.get("deliverable_type", "presentation"),
        )
        sections = mission["script_sections"]
        state = _normalize_presentation_state(sections, existing=state)

    section_ids = [item.get("section_id", "") for item in sections if item.get("section_id")]
    current_id = state.get("active_section_id") or (section_ids[0] if section_ids else "")
    current_index = section_ids.index(current_id) if current_id in section_ids else 0
    action = _safe_text(payload.get("action"), max_length=40).lower() or "next_slide"
    current_section = sections[current_index] if sections and 0 <= current_index < len(sections) else {}
    current_chunks = _teleprompter_state(current_section, active_chunk_index=state.get("active_chunk_index", 0))
    current_chunk_index = current_chunks.get("active_chunk_index", 0)

    def move_to_section(index, chunk_index=0):
        if not section_ids:
            state["active_section_id"] = ""
            state["active_chunk_index"] = 0
            return
        safe_index = min(len(section_ids) - 1, max(0, index))
        target_section = sections[safe_index]
        teleprompter = _teleprompter_state(target_section, active_chunk_index=chunk_index)
        state["active_section_id"] = target_section.get("section_id", "")
        state["active_chunk_index"] = teleprompter.get("active_chunk_index", 0)

    if action in {"next", "next_chunk"}:
        if current_chunks.get("has_next_chunk"):
            state["active_chunk_index"] = current_chunk_index + 1
        else:
            move_to_section(current_index + 1, chunk_index=0)
    elif action in {"previous", "previous_chunk"}:
        if current_chunks.get("has_previous_chunk"):
            state["active_chunk_index"] = max(0, current_chunk_index - 1)
        else:
            previous_index = max(0, current_index - 1)
            previous_section = sections[previous_index] if sections and previous_index < len(sections) else {}
            previous_chunks = _teleprompter_state(previous_section, active_chunk_index=10_000)
            move_to_section(previous_index, chunk_index=previous_chunks.get("active_chunk_index", 0))
    elif action == "next_slide":
        move_to_section(current_index + 1, chunk_index=0)
    elif action == "previous_slide":
        move_to_section(current_index - 1, chunk_index=0)
    elif action == "jump":
        requested_section_id = _safe_text(payload.get("section_id"), max_length=80)
        requested_slide_index = _safe_int(payload.get("slide_index"), default=0)
        if requested_section_id and requested_section_id in section_ids:
            move_to_section(section_ids.index(requested_section_id), chunk_index=0)
        elif requested_slide_index > 0:
            for index, section in enumerate(sections):
                if _safe_int(section.get("slide_index"), default=0) == requested_slide_index:
                    move_to_section(index, chunk_index=0)
                    break
    elif action == "jump_chunk":
        requested_chunk_index = _safe_int(payload.get("chunk_index"), default=current_chunk_index)
        requested_section_id = _safe_text(payload.get("section_id"), max_length=80)
        requested_slide_index = _safe_int(payload.get("slide_index"), default=0)
        if requested_section_id and requested_section_id in section_ids:
            move_to_section(section_ids.index(requested_section_id), chunk_index=requested_chunk_index)
        elif requested_slide_index > 0:
            for index, section in enumerate(sections):
                if _safe_int(section.get("slide_index"), default=0) == requested_slide_index:
                    move_to_section(index, chunk_index=requested_chunk_index)
                    break
        else:
            move_to_section(current_index, chunk_index=requested_chunk_index)
    elif action == "set_mode":
        state["presentation_mode"] = _normalize_presentation_mode(payload.get("presentation_mode"))
    elif action == "toggle_cue":
        state["cue_view"] = "hidden" if state.get("cue_view") == "visible" else "visible"

    state["last_action"] = action
    state["control_source"] = _safe_text(payload.get("control_source"), max_length=40) or "websocket"
    state["last_control_at"] = _now_iso()
    mission["presentation_state"] = _normalize_presentation_state(sections, existing=state, incoming=state)
    active_state = _presentation_state_payload(mission.get("presentation_state", {}), sections)
    active_section = _active_section(mission)
    return {
        "operation": "presentation_control",
        "action": action,
        "active_section_id": active_section.get("section_id", ""),
        "active_section_title": active_section.get("title", ""),
        "active_card": active_state.get("active_card", {}),
        "next_card": active_state.get("next_card", {}),
    }


def _record_rehearsal(mission, payload):
    recorded_at = _now_iso()
    transcript_excerpt = _safe_text(payload.get("transcript_excerpt"), max_length=4000, preserve_lines=True)
    duration_minutes = round(_safe_float(payload.get("duration_minutes"), default=0.0), 1)
    target_minutes = max(0.0, _safe_float(mission.get("target_duration_minutes"), default=0.0))
    transcript_word_count = _word_count(transcript_excerpt)
    target_seconds = int(round(target_minutes * 60)) if target_minutes > 0 else 0
    actual_seconds = int(round(duration_minutes * 60)) if duration_minutes > 0 else 0
    pacing_hint = _section_duration_hint(actual_seconds, target_seconds) if target_seconds > 0 else {
        "status": "unknown",
        "note": "Set a target duration to compare rehearsal timing.",
    }
    section_timings = _normalize_section_timings(
        mission.get("script_sections", []),
        section_timings=payload.get("section_timings"),
        total_duration_seconds=actual_seconds,
    )
    rehearsal_entry = {
        "rehearsal_id": _safe_text(payload.get("rehearsal_id"), max_length=80) or _build_id("rehearsal"),
        "recorded_at": recorded_at,
        "duration_minutes": duration_minutes,
        "confidence_level": max(0, min(5, _safe_int(payload.get("confidence_level"), default=0))),
        "self_rating": max(0, min(5, _safe_int(payload.get("self_rating"), default=0))),
        "what_worked": _safe_text(payload.get("what_worked"), max_length=2400, preserve_lines=True),
        "needs_improvement": _safe_text(payload.get("needs_improvement"), max_length=2400, preserve_lines=True),
        "next_focus": _safe_text(payload.get("next_focus"), max_length=600, preserve_lines=True),
        "transcript_excerpt": transcript_excerpt,
        "transcript_word_count": transcript_word_count,
        "timing_status": pacing_hint["status"],
        "timing_note": pacing_hint["note"],
        "section_timings": section_timings,
    }
    rehearsal_entry["analysis"] = _build_rehearsal_analysis(mission, rehearsal_entry)
    rehearsal_history = mission.get("rehearsal_history", [])
    _append_limited(rehearsal_history, rehearsal_entry)
    mission["rehearsal_history"] = rehearsal_history

    state = mission.get("presentation_state", {})
    state["phase"] = "rehearsing"
    state["last_rehearsed_at"] = recorded_at
    state["rehearsal_count"] = len(rehearsal_history)
    if rehearsal_entry["confidence_level"] > 0:
        state["confidence_level"] = rehearsal_entry["confidence_level"]
    if rehearsal_entry["next_focus"]:
        state["focus_area"] = rehearsal_entry["next_focus"]
    mission["presentation_state"] = _normalize_presentation_state(
        mission.get("script_sections", []),
        existing=state,
        incoming=state,
    )
    return rehearsal_entry


def _apply_reflection_update(mission, payload, operation):
    state = _ensure_payload_dict(mission.get("reflection_coach"))
    recorded_at = _now_iso()
    learner_note = _safe_text(payload.get("learner_note"), max_length=1200, preserve_lines=True)
    next_goal = _safe_text(payload.get("next_goal"), max_length=240, preserve_lines=True)
    if learner_note:
        state["learner_note"] = learner_note
    if next_goal:
        state["next_goal"] = next_goal
    provider_override_raw = _safe_text(payload.get("provider_override"), max_length=40)
    provider_override = _normalize_reflection_provider(provider_override_raw)
    if provider_override_raw and provider_override != "auto":
        state["provider_override"] = provider_override
    elif provider_override_raw:
        state["provider_override"] = provider_override
    model_override_raw = _safe_text(payload.get("model_override"), max_length=120)
    model_override = model_override_raw
    if model_override:
        state["model_override"] = model_override
    elif model_override_raw == "":
        pass
    elif payload.get("model_override") is not None:
        state["model_override"] = ""
    if payload.get("use_llm") is not None:
        state["use_llm"] = _safe_bool(payload.get("use_llm"), default=False)

    if operation == "set_reflection_focus":
        state["focus_theme"] = _safe_text(payload.get("focus_theme"), max_length=180) or state.get("focus_theme", "")
        state["current_course"] = _safe_text(payload.get("current_course") or payload.get("course"), max_length=180) or state.get(
            "current_course",
            "",
        )
        state["target_habit"] = _safe_text(payload.get("target_habit"), max_length=180) or state.get("target_habit", "")
        state["updated_at"] = recorded_at
        mission["reflection_coach"] = state
        return {
            "operation": operation,
            "focus_theme": state.get("focus_theme", ""),
            "current_course": state.get("current_course", ""),
            "target_habit": state.get("target_habit", ""),
            "learner_note": state.get("learner_note", ""),
            "next_goal": state.get("next_goal", ""),
        }

    if operation in {"capture_reflection", "log_reflection"}:
        reflection_entry = {
            "reflection_id": _safe_text(payload.get("reflection_id"), max_length=80) or _build_id("reflection"),
            "recorded_at": recorded_at,
            "focus_theme": _safe_text(payload.get("focus_theme"), max_length=180) or state.get("focus_theme", ""),
            "what_happened": _safe_text(payload.get("what_happened"), max_length=1800, preserve_lines=True),
            "what_worked": _safe_text(payload.get("what_worked"), max_length=1400, preserve_lines=True),
            "what_was_hard": _safe_text(
                payload.get("what_was_hard") or payload.get("blocker") or payload.get("challenge"),
                max_length=1400,
                preserve_lines=True,
            ),
            "lesson": _safe_text(
                payload.get("lesson") or payload.get("insight") or payload.get("what_i_learned"),
                max_length=1400,
                preserve_lines=True,
            ),
            "next_step": _safe_text(payload.get("next_step"), max_length=600, preserve_lines=True),
            "energy_level": max(0, min(5, _safe_int(payload.get("energy_level"), default=0))),
            "confidence_level": max(0, min(5, _safe_int(payload.get("confidence_level"), default=0))),
        }
        history = state.get("reflection_history", [])
        _append_limited(history, reflection_entry)
        state["reflection_history"] = history
        state["latest_reflection"] = reflection_entry
        if reflection_entry["focus_theme"]:
            state["focus_theme"] = reflection_entry["focus_theme"]
        if reflection_entry["next_step"]:
            commitments = state.get("action_commitments", [])
            _append_limited(commitments, reflection_entry["next_step"])
            state["action_commitments"] = commitments
        if reflection_entry["what_worked"]:
            wins = state.get("wins", [])
            _append_limited(wins, reflection_entry["what_worked"])
            state["wins"] = wins
        state["updated_at"] = recorded_at
        mission["reflection_coach"] = state
        return {
            "operation": operation,
            "reflection_entry": reflection_entry,
            "reflection_count": len(history),
            "learner_note": state.get("learner_note", ""),
            "next_goal": state.get("next_goal", ""),
        }

    if operation == "plan_next_step":
        commitments = state.get("action_commitments", [])
        steps = payload.get("steps")
        normalized_steps = []
        if isinstance(steps, list):
            normalized_steps = [_safe_text(item, max_length=280, preserve_lines=True) for item in steps]
        else:
            candidate = _safe_text(payload.get("next_step") or payload.get("plan"), max_length=1200, preserve_lines=True)
            if candidate:
                normalized_steps = [_safe_text(item, max_length=280, preserve_lines=True) for item in re.split(r"[\n;]+", candidate)]
        normalized_steps = [item for item in normalized_steps if item]
        for step in normalized_steps:
            _append_limited(commitments, step)
        state["action_commitments"] = commitments
        state["updated_at"] = recorded_at
        mission["reflection_coach"] = state
        return {
            "operation": operation,
            "planned_steps": normalized_steps,
            "recent_commitments": commitments[-5:],
            "next_goal": state.get("next_goal", ""),
        }

    raise ValueError(f"Unsupported reflection operation: {operation}")


def _apply_learning_state_update(mission, payload, operation):
    state = _ensure_payload_dict(mission.get("learning_state_guardian"))
    recorded_at = _now_iso()

    if operation == "set_learning_context":
        state["current_task"] = _safe_text(payload.get("current_task") or payload.get("task"), max_length=220) or state.get(
            "current_task",
            "",
        )
        state["session_goal"] = _safe_text(payload.get("session_goal") or payload.get("goal"), max_length=320) or state.get(
            "session_goal",
            "",
        )
        state["current_course"] = _safe_text(payload.get("current_course") or payload.get("course"), max_length=180) or state.get(
            "current_course",
            "",
        )
        state["environment"] = _safe_text(payload.get("environment"), max_length=180) or state.get("environment", "")
        state["task_mode"] = _normalize_guardian_task_mode(payload.get("task_mode")) or state.get("task_mode", "")
        state["updated_at"] = recorded_at
        mission["learning_state_guardian"] = state
        return {
            "operation": operation,
            "current_task": state.get("current_task", ""),
            "session_goal": state.get("session_goal", ""),
            "current_course": state.get("current_course", ""),
            "environment": state.get("environment", ""),
            "task_mode": state.get("task_mode", ""),
        }

    if operation == "record_learning_state":
        focus_level = max(0, min(5, _safe_int(payload.get("focus_level"), default=0)))
        energy_level = max(0, min(5, _safe_int(payload.get("energy_level"), default=0)))
        stress_level = max(0, min(5, _safe_int(payload.get("stress_level"), default=0)))
        comprehension_level = max(0, min(5, _safe_int(payload.get("comprehension_level"), default=0)))
        focus_score = _optional_score_100(payload.get("focus_score"))
        if focus_score is None:
            focus_score = _level_to_score(focus_level)
        stress_score = _optional_score_100(payload.get("stress_score"))
        if stress_score is None:
            stress_score = _level_to_score(stress_level)
        clarity_score = _optional_score_100(payload.get("clarity_score"))
        if clarity_score is None:
            clarity_score = _level_to_score(comprehension_level)
        fatigue_risk = _optional_score_100(payload.get("fatigue_risk"))
        if fatigue_risk is None:
            fatigue_risk = _level_to_score(energy_level, invert=True)
        behavioral_alignment = _optional_score_100(payload.get("behavioral_alignment"))
        if behavioral_alignment is None and focus_score is not None:
            penalty = 0.0
            if payload.get("distraction"):
                penalty += 24.0
            if payload.get("support_needed"):
                penalty += 10.0
            behavioral_alignment = round(max(0.0, focus_score - penalty), 1)
        uncertainty_score = _optional_score_100(payload.get("uncertainty_score"))
        if uncertainty_score is None:
            confidence_score = _optional_score_100(payload.get("confidence_score"))
            if confidence_score is not None:
                uncertainty_score = round(max(0.0, 100.0 - confidence_score), 1)
            elif clarity_score is not None:
                uncertainty_score = round(
                    max(0.0, min(100.0, 100.0 - clarity_score + (10.0 if payload.get("support_needed") else 0.0))),
                    1,
                )
        cognitive_load = _optional_score_100(payload.get("cognitive_load"))
        if cognitive_load is None:
            components = []
            if stress_score is not None:
                components.append(stress_score * 0.55)
            if clarity_score is not None:
                components.append((100.0 - clarity_score) * 0.35)
            if payload.get("distraction"):
                components.append(12.0)
            if payload.get("support_needed"):
                components.append(8.0)
            if components:
                cognitive_load = round(max(0.0, min(100.0, sum(components))), 1)
        snapshot = {
            "snapshot_id": _safe_text(payload.get("snapshot_id"), max_length=80) or _build_id("state"),
            "recorded_at": recorded_at,
            "current_task": _safe_text(payload.get("current_task") or payload.get("task"), max_length=220)
            or state.get("current_task", ""),
            "current_course": _safe_text(payload.get("current_course"), max_length=180) or state.get("current_course", ""),
            "task_mode": _normalize_guardian_task_mode(payload.get("task_mode")) or state.get("task_mode", ""),
            "focus_level": focus_level,
            "energy_level": energy_level,
            "stress_level": stress_level,
            "comprehension_level": comprehension_level,
            "progress_status": _safe_text(payload.get("progress_status"), max_length=180),
            "environment": _safe_text(payload.get("environment"), max_length=180) or state.get("environment", ""),
            "distraction": _safe_text(payload.get("distraction"), max_length=240),
            "support_needed": _safe_text(payload.get("support_needed"), max_length=320, preserve_lines=True),
            "note": _safe_text(payload.get("note"), max_length=1200, preserve_lines=True),
        }
        snapshot.update(_extract_guardian_sensor_fields(payload))
        if focus_score is not None:
            snapshot["focus_score"] = focus_score
        if stress_score is not None:
            snapshot["stress_score"] = stress_score
        if clarity_score is not None:
            snapshot["clarity_score"] = clarity_score
        if fatigue_risk is not None:
            snapshot["fatigue_risk"] = fatigue_risk
            snapshot["fatigue_level"] = _safe_text(payload.get("fatigue_level"), max_length=40).lower() or _derive_guardian_fatigue_level(
                fatigue_risk
            )
        if behavioral_alignment is not None:
            snapshot["behavioral_alignment"] = behavioral_alignment
            snapshot["behavioral_level"] = _safe_text(payload.get("behavioral_level"), max_length=40).lower() or _derive_guardian_behavioral_level(
                behavioral_alignment
            )
        if uncertainty_score is not None:
            snapshot["uncertainty_score"] = uncertainty_score
            snapshot["confidence_level"] = _safe_text(payload.get("confidence_level"), max_length=40).lower() or _derive_guardian_confidence_level(
                uncertainty_score
            )
        if cognitive_load is not None:
            snapshot["cognitive_load"] = cognitive_load
            snapshot["load_level"] = _safe_text(payload.get("load_level"), max_length=40).lower() or _derive_guardian_load_level(
                cognitive_load
            )
        snapshot["state_hint"] = _normalize_guardian_state_hint(payload.get("state_hint")) or snapshot.get("state_hint")
        snapshot["load_reason"] = _safe_text(payload.get("load_reason"), max_length=220) or snapshot.get("load_reason")
        snapshot = _finalize_guardian_snapshot(
            snapshot,
            recent_history=state.get("state_history", []),
            focus_signals=state.get("focus_signals", []),
        )
        history = state.get("state_history", [])
        _append_limited(history, snapshot)
        state["state_history"] = history
        state["latest_state"] = snapshot
        state["current_task"] = snapshot.get("current_task", "") or state.get("current_task", "")
        state["current_course"] = snapshot.get("current_course", "") or state.get("current_course", "")
        state["environment"] = snapshot.get("environment", "") or state.get("environment", "")
        state["task_mode"] = snapshot.get("task_mode", "") or state.get("task_mode", "")
        state["risk_flags"] = _guardian_risk_flags_from_state(snapshot, state.get("focus_signals", []))
        difficulty_event = _update_guardian_difficulty_tracking(state, snapshot=snapshot, recorded_at=recorded_at)
        state = _refresh_guardian_derived_state(state)
        state["updated_at"] = recorded_at
        mission["learning_state_guardian"] = state
        return {
            "operation": operation,
            "snapshot": snapshot,
            "risk_flags": state.get("risk_flags", []),
            "state_history_count": len(history),
            "difficulty_event": difficulty_event or {},
            "personal_baseline": state.get("personal_baseline", {}),
            "state_transition_summary": state.get("state_transition_summary", {}),
            "recovery_confidence": state.get("recovery_confidence", {}),
            "continuity_profile": state.get("continuity_profile", {}),
            "intervention_plan": state.get("intervention_plan", {}),
        }

    if operation == "record_focus_signal":
        signal = {
            "signal_id": _safe_text(payload.get("signal_id"), max_length=80) or _build_id("signal"),
            "recorded_at": recorded_at,
            "signal_type": _safe_text(payload.get("signal_type") or payload.get("challenge"), max_length=180),
            "severity": _normalize_severity(payload.get("severity")),
            "note": _safe_text(payload.get("note") or payload.get("context"), max_length=1200, preserve_lines=True),
            "resolved": _safe_bool(payload.get("resolved"), default=False),
        }
        signals = state.get("focus_signals", [])
        _append_limited(signals, signal)
        state["focus_signals"] = signals
        state["risk_flags"] = _guardian_risk_flags_from_state(state.get("latest_state", {}), signals)
        difficulty_event = _update_guardian_difficulty_tracking(
            state,
            snapshot=state.get("latest_state", {}),
            signal=signal,
            recorded_at=recorded_at,
        )
        state = _refresh_guardian_derived_state(state)
        state["updated_at"] = recorded_at
        mission["learning_state_guardian"] = state
        return {
            "operation": operation,
            "signal": signal,
            "risk_flags": state.get("risk_flags", []),
            "focus_signal_count": len(signals),
            "difficulty_event": difficulty_event or {},
            "recovery_confidence": state.get("recovery_confidence", {}),
            "continuity_profile": state.get("continuity_profile", {}),
            "intervention_plan": state.get("intervention_plan", {}),
        }

    raise ValueError(f"Unsupported learning-state operation: {operation}")


def _apply_reflection_difficulty(mission, difficulty_entry):
    state = _ensure_payload_dict(mission.get("reflection_coach"))
    if difficulty_entry.get("challenge") and not state.get("focus_theme"):
        state["focus_theme"] = difficulty_entry.get("challenge", "")
    if difficulty_entry.get("suggested_fix"):
        commitments = state.get("action_commitments", [])
        _append_limited(commitments, difficulty_entry["suggested_fix"])
        state["action_commitments"] = commitments
    state["updated_at"] = difficulty_entry.get("recorded_at", "")
    mission["reflection_coach"] = state


def _apply_guardian_difficulty(mission, difficulty_entry):
    state = _ensure_payload_dict(mission.get("learning_state_guardian"))
    signal = {
        "signal_id": _build_id("signal"),
        "recorded_at": difficulty_entry.get("recorded_at", ""),
        "signal_type": difficulty_entry.get("challenge", ""),
        "severity": difficulty_entry.get("severity", "medium"),
        "note": difficulty_entry.get("context", ""),
        "resolved": difficulty_entry.get("resolved", False),
    }
    signals = state.get("focus_signals", [])
    _append_limited(signals, signal)
    state["focus_signals"] = signals
    state["risk_flags"] = _guardian_risk_flags_from_state(state.get("latest_state", {}), signals)
    _update_guardian_difficulty_tracking(
        state,
        snapshot=state.get("latest_state", {}),
        signal=signal,
        recorded_at=difficulty_entry.get("recorded_at", ""),
    )
    state["updated_at"] = difficulty_entry.get("recorded_at", "")
    mission["learning_state_guardian"] = state


def _build_reflection_chat_reply(message, mission):
    review = _build_reflection_review(mission)
    latest = review.get("latest_reflection", {}) or {}
    provider_status = _ensure_payload_dict(review.get("provider_status"))
    lowered = (message or "").lower()
    if not message:
        return "Reflection coach is ready. Share what happened, what felt hard, and what you want to do differently next time."
    if "provider" in lowered or "model" in lowered or "status" in lowered:
        return (
            f"Reflection coach provider status: requested {provider_status.get('requested_provider', 'auto')}, "
            f"effective {provider_status.get('effective_provider', 'heuristic')}, "
            f"configured model {provider_status.get('configured_model', 'none') or 'none'}, "
            f"selected model {provider_status.get('selected_model', 'none') or 'none'}, "
            f"LLM available: {provider_status.get('llm_available', False)}."
        )
    if "goal" in lowered or "aim" in lowered:
        if review.get("next_goal"):
            return f"Your current next-session goal is: {review.get('next_goal')}. Keep the next reflection tied to that boundary."
        return "Set one next-session goal so the reflection can stay anchored to a concrete outcome."
    if "note" in lowered or "memo" in lowered:
        if review.get("coach_memo"):
            return review["coach_memo"]
        if review.get("learner_note"):
            return f"Your saved learner note is: {review.get('learner_note')}"
        return "Save one learner note if you want the coach memo to anchor around your own wording."
    if "question" in lowered or "prompt" in lowered:
        questions = review.get("reflection_questions", [])
        if questions:
            return f"Start with this reflection prompt: {questions[0].get('question', 'What changed first when the session became hard to regulate?')}"
        return "Start with: what changed first when the session became harder to regulate?"
    if "experiment" in lowered or "try" in lowered or "next session" in lowered:
        experiments = review.get("next_session_experiments", [])
        if experiments:
            first = _ensure_payload_dict(experiments[0])
            return (
                f"Try this next-session experiment: {first.get('title', 'One-variable retry')}. "
                f"{first.get('detail', 'Change only one regulation variable next time.')}"
            )
        return "Change only one regulation variable next time so the pattern becomes easier to interpret."
    if "evidence" in lowered or "pattern" in lowered or "why" in lowered:
        cards = review.get("evidence_cards", [])
        if cards:
            first = _ensure_payload_dict(cards[0])
            return (
                f"The strongest reflection evidence is {first.get('label', 'the current pattern')}: "
                f"{first.get('value', 'mixed regulation')}. {first.get('detail', '')}"
            ).strip()
        summary = _ensure_payload_dict(review.get("coach_summary"))
        if summary.get("why_it_matters"):
            return summary["why_it_matters"]
        return review.get("coach_message", "The main pattern is still forming, so capture one more honest reflection entry.")
    if "next step" in lowered or "plan" in lowered:
        commitments = review.get("recent_commitments", [])
        if commitments:
            return f"Your best next step is: {commitments[0]}. Keep it small enough to finish in one study block."
        return "Turn the reflection into one concrete next step you can start within 10 minutes."
    if "learned" in lowered or "lesson" in lowered or "reflect" in lowered:
        if latest.get("lesson"):
            return f"The clearest lesson right now is: {latest['lesson']}. Keep that lesson visible in the next session plan."
        return review.get("coach_message", "Name one lesson from the last session before moving on.")
    if "stuck" in lowered or "hard" in lowered or "block" in lowered:
        if latest.get("what_was_hard"):
            return (
                f"The current blocker is {latest['what_was_hard']}. "
                f"Shrink the next step to this: {latest.get('next_step') or 'start with the smallest repeatable action.'}"
            )
        return "Describe the blocker in one sentence, then convert it into a smaller action you can repeat tomorrow."
    if "win" in lowered or "worked" in lowered or "strength" in lowered:
        wins = review.get("recent_wins", [])
        if wins:
            return f"What already worked is: {wins[0]}. Reuse that pattern instead of rebuilding from scratch."
        return "Before fixing weaknesses, capture one thing that already worked so you can repeat it."
    return review.get("coach_message", "Capture one honest reflection entry so the coach can turn it into a next action.")


def _build_learning_state_chat_reply(message, mission):
    review = _build_learning_state_review(mission)
    latest = review.get("latest_state", {}) or {}
    active_difficulty_event = _ensure_payload_dict(review.get("difficulty_tracking", {})).get("active_event") or {}
    state_explanation = _ensure_payload_dict(review.get("state_explanation"))
    personal_baseline = _ensure_payload_dict(review.get("personal_baseline"))
    recent_trend_window = _ensure_payload_dict(review.get("recent_trend_window"))
    recovery_confidence = _ensure_payload_dict(review.get("recovery_confidence"))
    transition_summary = _ensure_payload_dict(review.get("state_transition_summary"))
    continuity_profile = _ensure_payload_dict(review.get("continuity_profile"))
    intervention_plan = _ensure_payload_dict(review.get("intervention_plan"))
    lowered = (message or "").lower()
    if not message:
        return (
            "Learning-state guardian is online. Tell me your current task, focus, fatigue, and load so I can spot the biggest risk."
        )
    if "why" in lowered or "reason" in lowered or "explain" in lowered:
        primary_driver = _ensure_payload_dict(state_explanation.get("primary_driver"))
        if primary_driver:
            return (
                f"{state_explanation.get('why_this_state', 'The guardian has a state explanation ready.')} "
                f"The top driver is {primary_driver.get('label', 'the current signal').lower()}: "
                f"{primary_driver.get('explanation', 'it is contributing the most to the current state.')}"
            )
        return "The current state looks relatively stable, so there is no dominant explanation driver yet."
    if "baseline" in lowered:
        if personal_baseline:
            return (
                f"Your recent guardian baseline for {personal_baseline.get('task_mode', 'study')} uses "
                f"{personal_baseline.get('sample_count', 0)} snapshots. Focus baseline is "
                f"{personal_baseline.get('focus_score', 'n/a')}/100 and load baseline is "
                f"{personal_baseline.get('cognitive_load', 'n/a')}/100."
            )
        return "The guardian does not have enough stable snapshots yet to build a personal baseline."
    if "trend" in lowered:
        signals = _ensure_payload_dict(recent_trend_window.get("signals"))
        focus_trend = _ensure_payload_dict(signals.get("focus_score"))
        load_trend = _ensure_payload_dict(signals.get("cognitive_load"))
        return (
            f"In the recent trend window, focus is {focus_trend.get('direction', 'stable')} "
            f"({focus_trend.get('delta', 0.0):+.1f}) and load is {load_trend.get('direction', 'stable')} "
            f"({load_trend.get('delta', 0.0):+.1f})."
        )
    if "recover" in lowered or "recovery" in lowered:
        if recovery_confidence:
            return (
                f"{recovery_confidence.get('summary', 'Recovery confidence is still forming.')} "
                f"Current recovery confidence is {recovery_confidence.get('score', 'n/a')}/100 "
                f"({recovery_confidence.get('label', 'unknown')})."
            )
        return "Recovery confidence is still warming up because the guardian needs more state history."
    if "transition" in lowered or "shift" in lowered:
        if transition_summary:
            return transition_summary.get("summary", "The guardian does not have a clear state transition summary yet.")
        return "The guardian needs at least two snapshots before it can summarize a state transition."
    if "intervention" in lowered or "next step" in lowered or "what should" in lowered:
        if intervention_plan:
            return (
                f"{intervention_plan.get('summary', 'The guardian has an intervention plan ready.')} "
                f"Next checkpoint: {intervention_plan.get('next_checkpoint', 'Re-check after the next focused block.')}"
            )
        return "The guardian needs one more stable review before it can turn the state into a stronger intervention plan."
    if "stable" in lowered or "stability" in lowered or "volatile" in lowered:
        if continuity_profile:
            return (
                f"{continuity_profile.get('summary', 'The guardian has a continuity profile ready.')} "
                f"Continuity score is {continuity_profile.get('continuity_score', 'n/a')}/100 "
                f"({continuity_profile.get('stability_band', 'unknown')})."
            )
        return "The guardian needs a few more snapshots before it can describe state stability."
    if "focus" in lowered or "distracted" in lowered:
        if active_difficulty_event:
            return (
                f"There is an active study-state event: {active_difficulty_event.get('primary_label')}. "
                "Pause and resolve that friction before starting a deeper block."
            )
        risks = review.get("risk_flags", [])
        if risks:
            return f"The strongest focus signal is: {risks[0]}. Remove one distraction before you keep studying."
        return "Your focus state looks stable enough for another work block. Keep the task narrow and log the next snapshot."
    if "energy" in lowered or "tired" in lowered or "fatigue" in lowered:
        fatigue_risk = latest.get("fatigue_risk")
        fatigue_level = latest.get("fatigue_level") or "unknown"
        return (
            f"Your latest fatigue signal is {fatigue_risk if fatigue_risk is not None else 'n/a'}/100 ({fatigue_level}). "
            "If that feels accurate, shorten the next work block and define one finish line before you continue."
        )
    if "stress" in lowered or "overwhelmed" in lowered:
        level = latest.get("stress_level", 0)
        return (
            f"Your latest stress level is {level}/5. "
            "Reduce the scope to one checkpoint and remove any optional task until that checkpoint is done."
        )
    if "load" in lowered or "workload" in lowered:
        cognitive_load = latest.get("cognitive_load")
        load_level = latest.get("load_level") or "unknown"
        load_reason = latest.get("load_reason") or review.get("state_classification", {}).get("load_reason", "")
        return (
            f"Current cognitive load is {cognitive_load if cognitive_load is not None else 'n/a'}/100 ({load_level}). "
            f"{load_reason or 'Keep the next study block narrow and re-check after one checkpoint.'}"
        )
    if "confidence" in lowered or "uncertain" in lowered or "signal" in lowered:
        uncertainty_score = latest.get("uncertainty_score")
        confidence_level = latest.get("confidence_level") or "unknown"
        return (
            f"Signal confidence is {confidence_level} with uncertainty at {uncertainty_score if uncertainty_score is not None else 'n/a'}/100. "
            "Use one more clean snapshot before you make a bigger study decision if the signal still feels noisy."
        )
    if "mode" in lowered or "task type" in lowered:
        task_mode = review.get("task_mode") or "general study"
        return f"The guardian currently reads this block as {task_mode}. Keep your study behavior matched to that mode for cleaner signals."
    if "task" in lowered or "progress" in lowered or "state" in lowered:
        task = latest.get("current_task") or review.get("current_task") or "your current study task"
        state_hint = review.get("state_classification", {}).get("state_hint_label") or "current learning state"
        if active_difficulty_event:
            return (
                f"Stay with {task}, but note that a sustained event is active: {active_difficulty_event.get('primary_label')}. "
                f"{review.get('coach_message', 'Log one more state snapshot after the next focused block.')}"
            )
        return (
            f"Stay with {task}. The guardian reads the state as {state_hint.lower()}. "
            f"{review.get('coach_message', 'Log one more state snapshot after the next focused block.')}"
        )
    return review.get("coach_message", "Record one learning-state snapshot so the guardian can identify the next intervention.")


def _build_chat_reply(message, mission):
    review = _build_review(mission)
    active_title = review["presentation_state"].get("active_section_title") or "the current section"
    mission_title = review["mission_brief"].get("title") or "your presentation"
    latest_difficulty = review["difficulty_overview"].get("latest") or {}
    coaching_summary = review.get("coaching_summary", {})
    latest_rehearsal_analysis = review.get("rehearsal_overview", {}).get("latest_analysis", {}) or {}
    readiness_summary = review.get("readiness_summary", {}) or {}
    practice_drills = review.get("practice_drills", []) or []
    section_coaching = review.get("section_coaching", {}) or {}
    transcript_analysis = latest_rehearsal_analysis.get("transcript_analysis", {}) or {}
    lowered = message.lower()

    if not message:
        return (
            "Academic companion is online. Share your presentation brief, a rehearsal blocker, "
            "or the section you want to tighten next."
        )

    if "opening" in lowered or "intro" in lowered:
        return (
            f"For {mission_title}, shape the opening around three beats: a hook, a clear context line, "
            "and one sentence that previews your direction."
        )
    if "conclusion" in lowered or "closing" in lowered:
        return (
            "Keep the closing short: restate the core takeaway, explain why it matters, "
            "and end on a confident final sentence instead of adding new content."
        )
    if "timing" in lowered or latest_difficulty.get("challenge") == "timing":
        return (
            f"Timing issues usually improve fastest when you trim one idea from {active_title} "
            "and rehearse with a visible minute target for each section."
        )
    if "transition" in lowered:
        return (
            f"Use the end of {active_title} to preview the next section in one sentence: "
            "\"Now that we have the problem, I can show the evidence.\""
        )
    if "evidence" in lowered or "example" in lowered:
        return (
            "Choose one example that directly proves your main claim, then say why it matters instead of stacking more detail."
        )
    if "transcript" in lowered or "wording" in lowered or "phrasing" in lowered:
        if transcript_analysis.get("issues"):
            first_issue = transcript_analysis["issues"][0]
            return (
                f"The main wording issue right now is: {first_issue.get('title', 'wording clarity')}. "
                f"{first_issue.get('recommended_fix', 'Tighten one sentence before the next run.')}"
            )
        return "The current transcript wording looks stable enough for another rehearsal; now focus on pacing and delivery."
    if "question" in lowered or "qa" in lowered:
        mock_prompt = _build_mock_qa_prompt(mission)
        if any(token in lowered for token in ("ask me", "quiz", "mock", "practice question")):
            return (
                f"Mock Q&A for {mission_title}: {mock_prompt['question']} "
                f"Answer with {mock_prompt['answer_framework']}. Tip: {mock_prompt['tip']}"
            )
        return (
            "Prepare short answers with a 3-step frame: answer first, justify with one example, then return to the takeaway."
        )
    if "ready" in lowered or "prepared" in lowered:
        return (
            f"Right now {mission_title} looks {readiness_summary.get('band', 'in progress')} "
            f"with a readiness score of {readiness_summary.get('score', 0)}/100. "
            f"The main blocker is: {(readiness_summary.get('blockers') or ['keep rehearsing the structure'])[0]}"
        )
    if "drill" in lowered or "practice" in lowered:
        first_drill = practice_drills[0] if practice_drills else {}
        if first_drill:
            steps = first_drill.get("steps", [])
            return (
                f"Try this drill next: {first_drill.get('title', 'Focused rehearsal drill')}. "
                f"Goal: {first_drill.get('goal', 'Improve one delivery variable.')}. "
                f"Step 1: {steps[0] if len(steps) > 0 else 'Run one focused repetition.'} "
                f"Step 2: {steps[1] if len(steps) > 1 else 'Note what changed.'}"
            )
        return "Pick one delivery variable and rehearse only that: timing, confidence, or transitions."
    if "current section" in lowered or "this section" in lowered or "active section" in lowered:
        return (
            f"The current section is {section_coaching.get('active_section_title', active_title)}. "
            f"Focus: {section_coaching.get('focus', 'one clear job')}. "
            f"{section_coaching.get('coaching_prompt', section_coaching.get('coach_note', 'Tighten the wording and rehearse it aloud.'))}"
        )
    if "slide" in lowered or "card" in lowered:
        return (
            f"The current active card is {active_title}. Keep the slide text minimal and move the fuller explanation into speaker notes."
        )
    if "nervous" in lowered or "confidence" in lowered:
        return (
            "Treat confidence as a delivery routine problem: rehearse your first 20 seconds three times, "
            "mark two breathing points, and keep the opening wording stable."
        )

    if review["difficulty_overview"]["count"] > 0:
        challenge = latest_difficulty.get("challenge") or "the latest blocker"
        return (
            f"I can anchor this to {mission_title}. Your latest blocker is {challenge}, "
            f"and the current active section is {active_title}. I would solve that blocker before expanding the script."
        )

    if latest_rehearsal_analysis.get("timing_status") in {"long", "short"}:
        return (
            f"I can anchor this to {mission_title}. Your latest pacing status is {latest_rehearsal_analysis.get('timing_status')}, "
            f"so I would follow this next: {coaching_summary.get('coach_message', 'adjust one section before the next run.')}"
        )

    return (
        f"I can anchor this to {mission_title}. Right now the active section is {active_title}. "
        "If you want a more grounded recommendation, send a state_update with your outline, notes, or rehearsal result."
    )


def _build_capability_chat_reply(message, mission, capability):
    if capability == CAPABILITY_REFLECTION:
        return _build_reflection_chat_reply(message, mission)
    if capability == CAPABILITY_GUARDIAN:
        return _build_learning_state_chat_reply(message, mission)
    return _build_chat_reply(message, mission)


async def _handle_text_chat(session_id, payload):
    message = _safe_text(payload.get("message") or payload.get("text"), max_length=2000, preserve_lines=True)
    capability = _resolve_capability(payload, event_type="text_chat")
    contract = _interface_contract(capability, "text_chat")
    async with STORE_LOCK:
        store = _read_store()
        mission = _resolve_mission(store, session_id, payload, create_if_missing=True)
        recorded_at = _now_iso()
        if message:
            _append_limited(
                mission["chat_history"],
                {
                    "role": "user",
                    "message": message,
                    "recorded_at": recorded_at,
                    "capability": capability,
                },
            )
        reply = _build_capability_chat_reply(message, mission, capability)
        _append_limited(
            mission["chat_history"],
            {
                "role": "assistant",
                "message": reply,
                "recorded_at": recorded_at,
                "capability": capability,
            },
        )
        mission["updated_at"] = recorded_at
        _upsert_mission(store, mission)
        _write_store(store)
        return {
            "status": "success",
            "data": {
                "session_id": session_id,
                "mission_id": mission["mission_id"],
                "event_type": "text_chat",
                "capability": capability,
                "routing": _routing_metadata(capability, "text_chat"),
                "interface_contract": contract,
                "reply": reply,
                "received_message": message,
                "review": _build_review(mission),
            },
        }


async def _handle_state_update(session_id, payload):
    operation = _safe_text(payload.get("operation"), max_length=40).lower() or "upsert_mission"
    capability = _resolve_capability(payload, event_type="state_update")
    contract = _interface_contract(capability, "state_update", operation=operation)
    async with STORE_LOCK:
        store = _read_store()
        mission = _resolve_mission(store, session_id, payload, create_if_missing=True)

        if capability == CAPABILITY_REFLECTION:
            result = _apply_reflection_update(mission, payload, operation)
        elif capability == CAPABILITY_GUARDIAN:
            result = _apply_learning_state_update(mission, payload, operation)
        elif operation == "extract_intake":
            result = _extract_intake_result(payload)
            if _safe_bool(payload.get("apply_to_mission"), default=False):
                mission_payload = {
                    **result["candidates"],
                    "script_sections": result["suggested_sections"],
                }
                if payload.get("mission_id"):
                    mission_payload["mission_id"] = _safe_text(payload.get("mission_id"), max_length=80)
                mission = _resolve_mission(store, session_id, mission_payload, create_if_missing=True)
                _apply_mission_update(mission, mission_payload)
                mission["updated_at"] = _now_iso()
                _upsert_mission(store, mission)
                _write_store(store)
                return {
                    "status": "success",
                    "data": {
                        "session_id": session_id,
                        "mission_id": mission["mission_id"],
                        "event_type": "state_update",
                        "capability": capability,
                        "routing": _routing_metadata(capability, "state_update", "extract_intake"),
                        "interface_contract": _interface_contract(capability, "state_update", "extract_intake"),
                        "operation": "extract_intake",
                        "result": result,
                        "mission": _mission_payload(mission),
                        "review": _build_review(mission),
                    },
                }
            return {
                "status": "success",
                "data": {
                    "session_id": session_id,
                    "mission_id": mission["mission_id"],
                    "event_type": "state_update",
                    "capability": capability,
                    "routing": _routing_metadata(capability, "state_update", "extract_intake"),
                    "interface_contract": _interface_contract(capability, "state_update", "extract_intake"),
                    "operation": "extract_intake",
                    "result": result,
                    "mission": _mission_payload(mission),
                    "review": _build_review(mission),
                },
            }
        elif operation == "presentation_control":
            result = _apply_control_action(mission, payload)
        elif operation == "record_rehearsal":
            rehearsal = _record_rehearsal(mission, payload)
            result = {
                "operation": "record_rehearsal",
                "rehearsal": rehearsal,
            }
        elif operation == "update_script_section":
            result = _apply_script_section_update(mission, payload)
        else:
            result = _apply_mission_update(mission, payload)

        mission["updated_at"] = _now_iso()
        _upsert_mission(store, mission)
        _write_store(store)
        return {
            "status": "success",
            "data": {
                "session_id": session_id,
                "mission_id": mission["mission_id"],
                "event_type": "state_update",
                "capability": capability,
                "routing": _routing_metadata(capability, "state_update", result.get("operation", operation)),
                "interface_contract": contract,
                "operation": result.get("operation", operation),
                "result": result,
                "mission": _mission_payload(mission),
                "review": _build_review(mission),
            },
        }


async def _handle_difficulty_event(session_id, payload):
    capability = _resolve_capability(payload, event_type="difficulty_event")
    contract = _interface_contract(capability, "difficulty_event")
    async with STORE_LOCK:
        store = _read_store()
        mission = _resolve_mission(store, session_id, payload, create_if_missing=True)
        recorded_at = _now_iso()
        difficulty_entry = {
            "event_id": _safe_text(payload.get("event_id"), max_length=80) or _build_id("difficulty"),
            "recorded_at": recorded_at,
            "capability": capability,
            "challenge": _safe_text(payload.get("challenge") or payload.get("difficulty"), max_length=180),
            "severity": _normalize_severity(payload.get("severity")),
            "section_id": _safe_text(payload.get("section_id"), max_length=80),
            "context": _safe_text(payload.get("context"), max_length=1200, preserve_lines=True),
            "suggested_fix": "",
            "resolved": _safe_bool(payload.get("resolved"), default=False),
        }
        difficulty_entry["suggested_fix"] = _safe_text(
            payload.get("suggested_fix")
            or _default_fix_for_challenge(
                difficulty_entry["challenge"],
                _active_section(mission).get("title", "the current section"),
            ),
            max_length=1200,
            preserve_lines=True,
        )

        difficulty_events = mission.get("difficulty_events", [])
        _append_limited(difficulty_events, difficulty_entry)
        mission["difficulty_events"] = difficulty_events

        state = mission.get("presentation_state", {})
        if capability == CAPABILITY_REFLECTION:
            _apply_reflection_difficulty(mission, difficulty_entry)
        elif capability == CAPABILITY_GUARDIAN:
            _apply_guardian_difficulty(mission, difficulty_entry)
        elif difficulty_entry["challenge"]:
            state["focus_area"] = difficulty_entry["challenge"]
        mission["presentation_state"] = _normalize_presentation_state(mission.get("script_sections", []), existing=state, incoming=state)
        mission["updated_at"] = recorded_at
        _upsert_mission(store, mission)
        _write_store(store)
        return {
            "status": "success",
            "data": {
                "session_id": session_id,
                "mission_id": mission["mission_id"],
                "event_type": "difficulty_event",
                "capability": capability,
                "routing": _routing_metadata(capability, "difficulty_event"),
                "interface_contract": contract,
                "difficulty_event": difficulty_entry,
                "difficulty_count": len(difficulty_events),
                "review": _build_review(mission),
            },
        }


async def _handle_session_review(session_id, payload):
    include_history = _safe_bool(payload.get("include_history"), default=False)
    capability = _resolve_capability(payload, event_type="session_review")
    contract = _interface_contract(capability, "session_review")
    async with STORE_LOCK:
        store = _read_store()
        mission = _resolve_mission(store, session_id, payload, create_if_missing=True)
        review = _build_review(mission)
        response = {
            "status": "success",
            "data": {
                "session_id": session_id,
                "mission_id": mission["mission_id"],
                "event_type": "session_review",
                "capability": capability,
                "routing": _routing_metadata(capability, "session_review"),
                "interface_contract": contract,
                "review_scope": _safe_text(payload.get("review_scope"), max_length=80) or "mission",
                "review": review,
                "mission": _mission_payload(mission),
            },
        }
        if capability == CAPABILITY_REFLECTION:
            response["data"]["capability_review"] = review.get("reflection_coach", {})
        elif capability == CAPABILITY_GUARDIAN:
            response["data"]["capability_review"] = review.get("learning_state_guardian", {})
        else:
            response["data"]["capability_review"] = {
                "script_overview": review.get("script_overview", {}),
                "presentation_state": review.get("presentation_state", {}),
                "readiness_summary": review.get("readiness_summary", {}),
            }
        if include_history:
            response["data"]["recent_chat_history"] = copy.deepcopy(mission.get("chat_history", [])[-10:])
        return response


async def handle_request(event_type, session_id, payload):
    safe_payload = _ensure_payload_dict(payload)
    safe_session_id = str(session_id or "anonymous")
    normalized_payload = _normalize_request_payload(safe_payload, event_type)

    try:
        if event_type == "text_chat":
            return await _handle_text_chat(safe_session_id, normalized_payload)
        if event_type == "state_update":
            return await _handle_state_update(safe_session_id, normalized_payload)
        if event_type == "difficulty_event":
            return await _handle_difficulty_event(safe_session_id, normalized_payload)
        if event_type == "session_review":
            return await _handle_session_review(safe_session_id, normalized_payload)
    except Exception as exc:
        return {
            "status": "error",
            "message": f"academic_companion failed to process {event_type}: {exc}",
        }

    return {
        "status": "error",
        "message": f"academic_companion does not support event_type: {event_type}",
    }
