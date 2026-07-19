import pytest


@pytest.mark.asyncio
async def test_institution_setup_templates_and_save(async_client, auth_headers):
    templates_response = await async_client.get(
        "/api/v1/institution-setup/templates",
        headers=auth_headers,
    )
    assert templates_response.status_code == 200
    templates = templates_response.json()["templates"]
    assert any(item["key"] == "nursing" for item in templates)

    save_response = await async_client.put(
        "/api/v1/institution-setup/",
        headers=auth_headers,
        json={
            "template_key": "nursing",
            "calendar_name": "Nursing Calendar",
            "days_of_week": ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"],
            "start_time": "08:00",
            "end_time": "17:00",
            "slot_duration_minutes": 90,
            "lunch_start": "12:30",
            "lunch_end": "13:30",
            "scheduling_policy": {
                "default_lecture_frequency": 3,
                "default_tutorial_frequency": 1,
                "default_practical_frequency": 1,
                "daily_max_teaching_hours": 8,
                "enforce_lunch_break": True,
            },
            "room_tags": ["theory_room", "clinical_skills_lab", "ward"],
            "activity_types": [
                {
                    "key": "theory",
                    "display_name": "Theory",
                    "color": "#2563EB",
                    "default_duration_periods": 2,
                    "default_frequency_per_week": 3,
                    "requires_subgroups": False,
                    "resource_tags_required": ["theory_room"],
                    "counts_toward_contact_hours": True,
                    "is_active": True,
                },
                {
                    "key": "clinical_skills",
                    "display_name": "Clinical Skills",
                    "color": "#059669",
                    "default_duration_periods": 2,
                    "default_frequency_per_week": 1,
                    "requires_subgroups": True,
                    "resource_tags_required": ["clinical_skills_lab"],
                    "counts_toward_contact_hours": True,
                    "is_active": True,
                },
            ],
        },
    )
    assert save_response.status_code == 200, save_response.text
    payload = save_response.json()
    assert payload["template_key"] == "nursing"
    assert payload["calendar"]["slot_duration_minutes"] == 90
    assert len(payload["activity_types"]) == 2
    assert payload["room_tags"] == ["theory_room", "clinical_skills_lab", "ward"]
    assert payload["active_days"] == ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"]


@pytest.mark.asyncio
async def test_institution_setup_save_emits_audit_event(async_client, auth_headers, monkeypatch):
    captured = {}

    def fake_log_event(**kwargs):
        captured.update(kwargs)

    monkeypatch.setattr("app.routers.institution_setup.AuditLogger.log_event", fake_log_event)

    response = await async_client.put(
        "/api/v1/institution-setup/",
        headers=auth_headers,
        json={
            "template_key": "custom",
            "calendar_name": "Institution Calendar",
            "days_of_week": ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"],
            "start_time": "08:00",
            "end_time": "17:00",
            "slot_duration_minutes": 60,
            "lunch_start": "13:00",
            "lunch_end": "14:00",
            "scheduling_policy": {
                "default_lecture_frequency": 2,
                "default_tutorial_frequency": 1,
                "default_practical_frequency": 1,
                "daily_max_teaching_hours": 8,
                "enforce_lunch_break": True,
            },
            "room_tags": [],
            "activity_types": [],
        },
    )
    assert response.status_code == 200, response.text
    assert captured["event_type"] == "UPDATE_INSTITUTION_SETUP"
    assert captured["details"]["template_key"] == "custom"


@pytest.mark.asyncio
async def test_institution_setup_get_requires_coordinator(async_client, hod_headers):
    response = await async_client.get(
        "/api/v1/institution-setup/",
        headers=hod_headers,
    )
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_course_create_rejects_unknown_activity_type_key(async_client, auth_headers, get_department_id):
    response = await async_client.post(
        "/api/v1/courses/",
        headers=auth_headers,
        json={
            "code": "BAD401",
            "name": "Bad Activity Key Course",
            "department_id": get_department_id,
            "level": 400,
            "credits": 3,
            "lecture_hours": 0,
            "tutorial_hours": 0,
            "practical_hours": 0,
            "preferred_room_type": "any",
            "course_type": "department_specific",
            "group_division_type": "full_group",
            "activity_requirements": [
                {"activity_type_key": "unknown_key", "hours_per_session": 2, "frequency_per_week": 1}
            ],
        },
    )
    assert response.status_code == 422
    assert "unknown activity_type_key" in response.text.lower()


@pytest.mark.asyncio
async def test_course_update_accepts_valid_activity_requirements(async_client, auth_headers, get_department_id):
    setup_response = await async_client.put(
        "/api/v1/institution-setup/",
        headers=auth_headers,
        json={
            "template_key": "nursing",
            "calendar_name": "Nursing Calendar",
            "days_of_week": ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"],
            "start_time": "08:00",
            "end_time": "17:00",
            "slot_duration_minutes": 90,
            "lunch_start": "12:30",
            "lunch_end": "13:30",
            "scheduling_policy": {
                "default_lecture_frequency": 3,
                "default_tutorial_frequency": 1,
                "default_practical_frequency": 1,
                "daily_max_teaching_hours": 8,
                "enforce_lunch_break": True,
            },
            "room_tags": ["theory_room"],
            "activity_types": [
                {
                    "key": "theory",
                    "display_name": "Theory",
                    "default_duration_periods": 2,
                    "default_frequency_per_week": 3,
                    "requires_subgroups": False,
                    "resource_tags_required": ["theory_room"],
                    "counts_toward_contact_hours": True,
                    "is_active": True,
                }
            ],
        },
    )
    assert setup_response.status_code == 200

    create_response = await async_client.post(
        "/api/v1/courses/",
        headers=auth_headers,
        json={
            "code": "NUR210",
            "name": "Nursing Theory",
            "department_id": get_department_id,
            "level": 200,
            "credits": 3,
            "lecture_hours": 2,
            "tutorial_hours": 0,
            "practical_hours": 0,
            "preferred_room_type": "any",
            "course_type": "department_specific",
            "group_division_type": "full_group",
        },
    )
    assert create_response.status_code == 201, create_response.text
    course_id = create_response.json()["id"]

    update_response = await async_client.put(
        f"/api/v1/courses/{course_id}",
        headers=auth_headers,
        json={
            "activity_requirements": [
                {"activity_type_key": "theory", "hours_per_session": 2, "frequency_per_week": 2}
            ]
        },
    )
    assert update_response.status_code == 200, update_response.text
    assert update_response.json()["activity_requirements"][0]["activity_type_key"] == "theory"


@pytest.mark.asyncio
async def test_student_group_update_accepts_custom_subtype(async_client, auth_headers, get_department_id):
    create_response = await async_client.post(
        "/api/v1/groups/",
        headers=auth_headers,
        json={
            "name": "NUR Y2 Group A",
            "level": 200,
            "department_id": get_department_id,
            "size": 40,
            "group_type": "department",
        },
    )
    assert create_response.status_code == 201, create_response.text
    group_id = create_response.json()["id"]

    update_response = await async_client.put(
        f"/api/v1/groups/{group_id}",
        headers=auth_headers,
        json={"custom_subtype": "Ward Team"},
    )
    assert update_response.status_code == 200, update_response.text
    assert update_response.json()["custom_subtype"] == "ward_team"
