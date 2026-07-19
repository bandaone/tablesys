from __future__ import annotations

from copy import deepcopy
from typing import Any, Dict, List


DEFAULT_SCHEDULING_POLICY: Dict[str, Any] = {
    "default_lecture_frequency": 2,
    "default_tutorial_frequency": 1,
    "default_practical_frequency": 1,
    "daily_max_teaching_hours": 8,
    "enforce_lunch_break": True,
    "lunch_start": "13:00",
    "lunch_end": "14:00",
    "institution_template_key": "custom",
    "room_tag_catalog": [],
    "solver_timeout_seconds": 120,
}


INSTITUTION_TEMPLATES: Dict[str, Dict[str, Any]] = {
    "engineering": {
        "label": "Engineering University",
        "auto_seed_single_school": False,
        "default_school_name": "School of Engineering",
        "default_school_code": "ENG",
        "room_tags": ["lecture_hall", "tutorial_room", "lab", "drawing_room", "projector", "whiteboard"],
        "activity_types": [
            {"key": "lecture", "display_name": "Lecture", "color": "#2563EB", "default_duration_periods": 2, "default_frequency_per_week": 2, "requires_subgroups": False, "resource_tags_required": ["lecture_hall"]},
            {"key": "tutorial", "display_name": "Tutorial", "color": "#16A34A", "default_duration_periods": 1, "default_frequency_per_week": 1, "requires_subgroups": True, "resource_tags_required": ["tutorial_room"]},
            {"key": "practical", "display_name": "Practical/Lab", "color": "#F59E0B", "default_duration_periods": 2, "default_frequency_per_week": 1, "requires_subgroups": True, "resource_tags_required": ["lab"]},
            {"key": "drawing", "display_name": "Drawing Session", "color": "#DC2626", "default_duration_periods": 2, "default_frequency_per_week": 1, "requires_subgroups": True, "resource_tags_required": ["drawing_room"]},
        ],
    },
    "medical": {
        "label": "Medical / Health Sciences",
        "auto_seed_single_school": False,
        "default_school_name": "School of Medicine",
        "default_school_code": "MED",
        "room_tags": ["lecture_hall", "seminar_room", "anatomy_lab", "clinical_skills_lab", "projector"],
        "activity_types": [
            {"key": "lecture", "display_name": "Lecture", "color": "#2563EB", "default_duration_periods": 2, "default_frequency_per_week": 2, "requires_subgroups": False, "resource_tags_required": ["lecture_hall"]},
            {"key": "seminar", "display_name": "Seminar", "color": "#7C3AED", "default_duration_periods": 1, "default_frequency_per_week": 1, "requires_subgroups": False, "resource_tags_required": ["seminar_room"]},
            {"key": "anatomy_lab", "display_name": "Anatomy Lab", "color": "#F97316", "default_duration_periods": 2, "default_frequency_per_week": 1, "requires_subgroups": True, "resource_tags_required": ["anatomy_lab"]},
            {"key": "clinical_skills", "display_name": "Clinical Skills", "color": "#059669", "default_duration_periods": 2, "default_frequency_per_week": 1, "requires_subgroups": True, "resource_tags_required": ["clinical_skills_lab"]},
        ],
    },
    "nursing": {
        "label": "Nursing / Allied Health",
        "auto_seed_single_school": True,
        "default_school_name": "Nursing School",
        "default_school_code": "NUR",
        "room_tags": ["theory_room", "clinical_skills_lab", "ward", "discussion_room"],
        "activity_types": [
            {"key": "theory", "display_name": "Theory", "color": "#2563EB", "default_duration_periods": 2, "default_frequency_per_week": 3, "requires_subgroups": False, "resource_tags_required": ["theory_room"]},
            {"key": "clinical_skills", "display_name": "Clinical Skills Lab", "color": "#059669", "default_duration_periods": 2, "default_frequency_per_week": 1, "requires_subgroups": True, "resource_tags_required": ["clinical_skills_lab"]},
            {"key": "ward_placement", "display_name": "Ward Placement", "color": "#D97706", "default_duration_periods": 2, "default_frequency_per_week": 1, "requires_subgroups": True, "resource_tags_required": ["ward"]},
            {"key": "group_discussion", "display_name": "Group Discussion", "color": "#7C3AED", "default_duration_periods": 1, "default_frequency_per_week": 1, "requires_subgroups": False, "resource_tags_required": ["discussion_room"]},
        ],
    },
    "education": {
        "label": "Education / Teaching",
        "auto_seed_single_school": True,
        "default_school_name": "School of Education",
        "default_school_code": "EDU",
        "room_tags": ["lecture_hall", "tutorial_room", "micro_teaching_lab", "school_site"],
        "activity_types": [
            {"key": "lecture", "display_name": "Lecture", "color": "#2563EB", "default_duration_periods": 2, "default_frequency_per_week": 2, "requires_subgroups": False, "resource_tags_required": ["lecture_hall"]},
            {"key": "tutorial", "display_name": "Tutorial", "color": "#16A34A", "default_duration_periods": 1, "default_frequency_per_week": 1, "requires_subgroups": True, "resource_tags_required": ["tutorial_room"]},
            {"key": "micro_teaching", "display_name": "Micro-Teaching", "color": "#DC2626", "default_duration_periods": 2, "default_frequency_per_week": 1, "requires_subgroups": True, "resource_tags_required": ["micro_teaching_lab"]},
            {"key": "practicum", "display_name": "Practicum", "color": "#D97706", "default_duration_periods": 2, "default_frequency_per_week": 1, "requires_subgroups": True, "resource_tags_required": ["school_site"]},
        ],
    },
    "business": {
        "label": "Business / Commerce",
        "auto_seed_single_school": True,
        "default_school_name": "School of Business",
        "default_school_code": "BUS",
        "room_tags": ["lecture_hall", "seminar_room", "case_room", "project_space"],
        "activity_types": [
            {"key": "lecture", "display_name": "Lecture", "color": "#2563EB", "default_duration_periods": 2, "default_frequency_per_week": 2, "requires_subgroups": False, "resource_tags_required": ["lecture_hall"]},
            {"key": "seminar", "display_name": "Seminar", "color": "#7C3AED", "default_duration_periods": 1, "default_frequency_per_week": 1, "requires_subgroups": False, "resource_tags_required": ["seminar_room"]},
            {"key": "case_study", "display_name": "Case Study", "color": "#F97316", "default_duration_periods": 1, "default_frequency_per_week": 1, "requires_subgroups": True, "resource_tags_required": ["case_room"]},
            {"key": "group_project", "display_name": "Group Project", "color": "#059669", "default_duration_periods": 1, "default_frequency_per_week": 1, "requires_subgroups": True, "resource_tags_required": ["project_space"]},
        ],
    },
    "trades": {
        "label": "Trades / Technical",
        "auto_seed_single_school": True,
        "default_school_name": "Technical School",
        "default_school_code": "TVT",
        "room_tags": ["theory_room", "workshop", "demonstration_bay", "assessment_room"],
        "activity_types": [
            {"key": "theory", "display_name": "Theory", "color": "#2563EB", "default_duration_periods": 1, "default_frequency_per_week": 2, "requires_subgroups": False, "resource_tags_required": ["theory_room"]},
            {"key": "workshop", "display_name": "Workshop", "color": "#F97316", "default_duration_periods": 2, "default_frequency_per_week": 1, "requires_subgroups": True, "resource_tags_required": ["workshop"]},
            {"key": "practical_demo", "display_name": "Practical Demonstration", "color": "#059669", "default_duration_periods": 2, "default_frequency_per_week": 1, "requires_subgroups": True, "resource_tags_required": ["demonstration_bay"]},
            {"key": "assessment", "display_name": "Assessment", "color": "#7C3AED", "default_duration_periods": 1, "default_frequency_per_week": 1, "requires_subgroups": False, "resource_tags_required": ["assessment_room"]},
        ],
    },
    "custom": {
        "label": "Start from Scratch",
        "auto_seed_single_school": False,
        "default_school_name": "Main School",
        "default_school_code": "MAIN",
        "room_tags": [],
        "activity_types": [],
    },
}


for template_key, template in INSTITUTION_TEMPLATES.items():
    seen_keys = set()
    for activity in template.get("activity_types", []):
        key = str(activity.get("key", "")).strip().lower()
        if not key:
            raise ValueError(f"Template '{template_key}' contains a blank activity key")
        if key in seen_keys:
            raise ValueError(f"Template '{template_key}' contains duplicate activity key '{key}'")
        seen_keys.add(key)


def get_template_payload(template_key: str) -> Dict[str, Any]:
    key = (template_key or "custom").strip().lower()
    template = INSTITUTION_TEMPLATES.get(key, INSTITUTION_TEMPLATES["custom"])
    payload = deepcopy(template)
    payload["key"] = key
    return payload


def build_policy(template_key: str, overrides: Dict[str, Any] | None = None) -> Dict[str, Any]:
    policy = deepcopy(DEFAULT_SCHEDULING_POLICY)
    template = get_template_payload(template_key)
    policy["institution_template_key"] = template["key"]
    policy["room_tag_catalog"] = list(template.get("room_tags") or [])
    if overrides:
        policy.update({k: v for k, v in overrides.items() if v is not None})
    return policy


def template_catalog() -> List[Dict[str, Any]]:
    return [
        {
            "key": key,
            "label": value["label"],
            "auto_seed_single_school": bool(value.get("auto_seed_single_school")),
            "default_school_name": value.get("default_school_name"),
            "default_school_code": value.get("default_school_code"),
            "room_tags": list(value.get("room_tags") or []),
            "activity_types": deepcopy(value.get("activity_types") or []),
        }
        for key, value in INSTITUTION_TEMPLATES.items()
    ]
