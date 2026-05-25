# Academic Companion Docs

This directory contains delivery materials and references for the `academic_companion` module integrated into `ROKID_Agent_Tutor`.

## Documents

### Written Reports

- Chinese: [academic_companion_written_report_cn.md](./academic_companion_written_report_cn.md)
- English: [academic_companion_written_report_en.md](./academic_companion_written_report_en.md)

### Oral Presentation Scripts

- Chinese: [academic_companion_oral_report_cn.md](./academic_companion_oral_report_cn.md)
- English: [academic_companion_oral_report_en.md](./academic_companion_oral_report_en.md)

## Technical References

### Core Module

- [Agent_Project/agents/academic_companion.py](/C:/Users/11721/Desktop/focus_project_windows/ROKID_Agent_Tutor/Agent_Project/agents/academic_companion.py)

### Gateway Entry

- [Agent_Project/Agent_Main.py](/C:/Users/11721/Desktop/focus_project_windows/ROKID_Agent_Tutor/Agent_Project/Agent_Main.py)

### Payload Examples

- [Agent_Project/agents/academic_companion_payload_examples.md](/C:/Users/11721/Desktop/focus_project_windows/ROKID_Agent_Tutor/Agent_Project/agents/academic_companion_payload_examples.md)

### Smoke Tests

- [Guardian Smoke Test](/C:/Users/11721/Desktop/focus_project_windows/ROKID_Agent_Tutor/Agent_Project/agents/academic_companion_guardian_smoke_test.py)
- [Reflection Smoke Test](/C:/Users/11721/Desktop/focus_project_windows/ROKID_Agent_Tutor/Agent_Project/agents/academic_companion_reflection_smoke_test.py)
- [Presentation Smoke Test](/C:/Users/11721/Desktop/focus_project_windows/ROKID_Agent_Tutor/Agent_Project/agents/academic_companion_presentation_smoke_test.py)

## Current Scope

The current `academic_companion` integration includes three internal capabilities under one gateway-facing interface:

- academic presentation support
- reflection coach
- learning state guardian

External contract:

- `agent_type = academic_companion`
- `async def handle_request(event_type, session_id, payload)`

## Notes

- This documentation directory is for delivery, reporting, and team reference.
- Runtime data under `Agent_Project/data/` is not part of the delivery materials.
