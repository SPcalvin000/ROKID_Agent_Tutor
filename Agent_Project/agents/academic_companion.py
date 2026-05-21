import asyncio
import copy
import json
import os
import re
import uuid
from datetime import datetime


MAX_HISTORY = 24
WORDS_PER_SECOND = 2.35
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(BASE_DIR, "data")
STORE_PATH = os.path.join(DATA_DIR, "academic_companion_store.json")
STORE_LOCK = asyncio.Lock()


def _now_iso():
    return datetime.utcnow().isoformat(timespec="seconds") + "Z"


def _ensure_payload_dict(payload):
    if isinstance(payload, dict):
        return payload
    return {}


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


def _build_rehearsal_analysis(mission, rehearsal_entry):
    if not rehearsal_entry:
        return {}

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
    return {
        "timing_status": pacing["status"],
        "timing_note": pacing["note"],
        "timing_delta_seconds": delta_seconds,
        "timing_delta_label": _format_mmss(abs(delta_seconds)),
        "transcript_density": transcript_density,
        "transcript_word_count": transcript_words,
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


def _build_default_mission(session_id, mission_id):
    created_at = _now_iso()
    script_sections = _default_sections(0.0)
    return {
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


def _resolve_mission(store, session_id, payload, create_if_missing=True):
    mission_id = _safe_text(payload.get("mission_id"), max_length=80) or f"mission_{_slugify(session_id, 'anonymous')}"
    mission = _find_mission(store, mission_id)
    if mission is None and create_if_missing:
        mission = _build_default_mission(session_id, mission_id)
    if mission is not None:
        mission["session_id"] = session_id
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
    if not actions:
        actions.append("Keep rehearsing the current section and tighten transitions between slides.")
    return actions[:4]


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
        "coaching_summary": _build_coaching_summary(mission, script_summary, difficulty_events, rehearsal_history),
        "next_actions": _build_next_actions(mission),
        "updated_at": mission.get("updated_at", ""),
    }


def _mission_payload(mission):
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
        "script_summary": _build_script_summary(
            mission.get("script_sections", []),
            target_minutes=mission.get("target_duration_minutes", 0.0),
        ),
        "difficulty_events": copy.deepcopy(mission.get("difficulty_events", [])[-6:]),
        "rehearsal_history": copy.deepcopy(mission.get("rehearsal_history", [])[-6:]),
        "chat_history": copy.deepcopy(mission.get("chat_history", [])[-10:]),
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


def _build_chat_reply(message, mission):
    review = _build_review(mission)
    active_title = review["presentation_state"].get("active_section_title") or "the current section"
    mission_title = review["mission_brief"].get("title") or "your presentation"
    latest_difficulty = review["difficulty_overview"].get("latest") or {}
    coaching_summary = review.get("coaching_summary", {})
    latest_rehearsal_analysis = review.get("rehearsal_overview", {}).get("latest_analysis", {}) or {}
    readiness_summary = review.get("readiness_summary", {}) or {}
    practice_drills = review.get("practice_drills", []) or []
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


async def _handle_text_chat(session_id, payload):
    message = _safe_text(payload.get("message") or payload.get("text"), max_length=2000, preserve_lines=True)
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
                },
            )
        reply = _build_chat_reply(message, mission)
        _append_limited(
            mission["chat_history"],
            {
                "role": "assistant",
                "message": reply,
                "recorded_at": recorded_at,
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
                "reply": reply,
                "received_message": message,
                "review": _build_review(mission),
            },
        }


async def _handle_state_update(session_id, payload):
    operation = _safe_text(payload.get("operation"), max_length=40).lower() or "upsert_mission"
    async with STORE_LOCK:
        store = _read_store()
        mission = _resolve_mission(store, session_id, payload, create_if_missing=True)

        if operation == "extract_intake":
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
                    "operation": "extract_intake",
                    "result": result,
                    "mission": _mission_payload(mission),
                    "review": _build_review(mission),
                },
            }
        if operation == "presentation_control":
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
                "operation": result.get("operation", operation),
                "result": result,
                "mission": _mission_payload(mission),
                "review": _build_review(mission),
            },
        }


async def _handle_difficulty_event(session_id, payload):
    async with STORE_LOCK:
        store = _read_store()
        mission = _resolve_mission(store, session_id, payload, create_if_missing=True)
        recorded_at = _now_iso()
        difficulty_entry = {
            "event_id": _safe_text(payload.get("event_id"), max_length=80) or _build_id("difficulty"),
            "recorded_at": recorded_at,
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
        if difficulty_entry["challenge"]:
            state["focus_area"] = difficulty_entry["challenge"]
        mission["presentation_state"] = _normalize_presentation_state(
            mission.get("script_sections", []),
            existing=state,
            incoming=state,
        )
        mission["updated_at"] = recorded_at
        _upsert_mission(store, mission)
        _write_store(store)
        return {
            "status": "success",
            "data": {
                "session_id": session_id,
                "mission_id": mission["mission_id"],
                "event_type": "difficulty_event",
                "difficulty_event": difficulty_entry,
                "difficulty_count": len(difficulty_events),
                "review": _build_review(mission),
            },
        }


async def _handle_session_review(session_id, payload):
    include_history = _safe_bool(payload.get("include_history"), default=False)
    async with STORE_LOCK:
        store = _read_store()
        mission = _resolve_mission(store, session_id, payload, create_if_missing=True)
        response = {
            "status": "success",
            "data": {
                "session_id": session_id,
                "mission_id": mission["mission_id"],
                "event_type": "session_review",
                "review_scope": _safe_text(payload.get("review_scope"), max_length=80) or "mission",
                "review": _build_review(mission),
                "mission": _mission_payload(mission),
            },
        }
        if include_history:
            response["data"]["recent_chat_history"] = copy.deepcopy(mission.get("chat_history", [])[-10:])
        return response


async def handle_request(event_type, session_id, payload):
    safe_payload = _ensure_payload_dict(payload)
    safe_session_id = str(session_id or "anonymous")

    try:
        if event_type == "text_chat":
            return await _handle_text_chat(safe_session_id, safe_payload)
        if event_type == "state_update":
            return await _handle_state_update(safe_session_id, safe_payload)
        if event_type == "difficulty_event":
            return await _handle_difficulty_event(safe_session_id, safe_payload)
        if event_type == "session_review":
            return await _handle_session_review(safe_session_id, safe_payload)
    except Exception as exc:
        return {
            "status": "error",
            "message": f"academic_companion failed to process {event_type}: {exc}",
        }

    return {
        "status": "error",
        "message": f"academic_companion does not support event_type: {event_type}",
    }
