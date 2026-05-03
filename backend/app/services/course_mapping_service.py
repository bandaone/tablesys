from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Sequence, Set

from sqlalchemy import or_
from sqlalchemy.orm import Session

from ..models import Course, CourseGroupLink, GroupAssignment, GroupType, StudentGroup
from ..utils.department_utils import find_general_department, is_general_department


def normalize_course_level(level: int) -> int:
    return level * 100 if 1 <= level <= 7 else level


@dataclass
class EligibleGroupOption:
    group: StudentGroup
    ownership_kind: str


class CourseMappingService:
    """
    Centralizes course enrolment and lecture-delivery mapping for main groups.

    Main cohorts are managed from the course side.
    Stream-specific refinement is handled elsewhere and only survives when the
    parent cohort is not explicitly enrolled from the course page.
    """

    def __init__(self, db: Session) -> None:
        self.db = db

    def eligible_main_groups_for_course(self, course: Course) -> List[EligibleGroupOption]:
        target_level = normalize_course_level(course.level)
        alternate_level = target_level // 100 if target_level >= 100 else target_level * 100
        general_department = find_general_department(self.db)
        general_department_id = general_department.id if general_department else None

        query = (
            self.db.query(StudentGroup)
            .filter(
                StudentGroup.parent_group_id.is_(None),
                StudentGroup.level.in_([target_level, alternate_level]),
                or_(
                    StudentGroup.group_type.is_(None),
                    StudentGroup.group_type.in_([GroupType.GENERAL, GroupType.DEPARTMENT]),
                ),
            )
        )

        shared_department_ids = set(course.shared_with_department_ids or [])
        owner_department_id = course.department_id

        if is_general_department(getattr(course, "department", None)) and course.shared_with_department_ids is None:
            groups = query.order_by(StudentGroup.department_id.asc(), StudentGroup.name.asc()).all()
            return [
                EligibleGroupOption(
                    group=group,
                    ownership_kind="owner" if group.department_id == owner_department_id else "shared",
                )
                for group in groups
            ]

        allowed_department_ids: Set[int] = {owner_department_id}
        allowed_department_ids.update(shared_department_ids)
        if general_department_id and general_department_id in allowed_department_ids:
            allowed_department_ids.add(general_department_id)

        groups = (
            query.filter(StudentGroup.department_id.in_(sorted(allowed_department_ids)))
            .order_by(StudentGroup.department_id.asc(), StudentGroup.name.asc())
            .all()
        )

        return [
            EligibleGroupOption(
                group=group,
                ownership_kind="owner" if group.department_id == owner_department_id else "shared",
            )
            for group in groups
        ]

    def current_selected_main_group_ids(self, course: Course, eligible_group_ids: Sequence[int]) -> List[int]:
        if not eligible_group_ids:
            return []
        rows = (
            self.db.query(GroupAssignment.group_id)
            .filter(
                GroupAssignment.course_id == course.id,
                GroupAssignment.group_id.in_(list(eligible_group_ids)),
            )
            .all()
        )
        return sorted({row[0] for row in rows})

    def current_lecture_mode(self, course: Course, selected_group_ids: Sequence[int]) -> str:
        selected_ids = sorted(set(selected_group_ids))
        if len(selected_ids) <= 1:
            return "separate"

        lecture_links = (
            self.db.query(CourseGroupLink)
            .filter(
                CourseGroupLink.course_id == course.id,
                CourseGroupLink.session_type == "lecture",
                CourseGroupLink.group_id.in_(selected_ids),
            )
            .all()
        )
        if len(lecture_links) != len(selected_ids):
            return "separate"

        batch_ids = {link.shared_batch_id for link in lecture_links if link.is_shared}
        linked_group_ids = sorted(link.group_id for link in lecture_links)
        if (
            len(batch_ids) == 1
            and None not in batch_ids
            and all(link.is_shared for link in lecture_links)
            and linked_group_ids == selected_ids
        ):
            return "shared"
        return "separate"

    def save_main_group_mapping(self, course: Course, group_ids: Sequence[int], lecture_mode: str) -> Dict[str, int | str]:
        eligible_groups = self.eligible_main_groups_for_course(course)
        eligible_group_ids = {item.group.id for item in eligible_groups}
        requested_group_ids = sorted(set(int(group_id) for group_id in group_ids))

        invalid_group_ids = [group_id for group_id in requested_group_ids if group_id not in eligible_group_ids]
        if invalid_group_ids:
            raise ValueError(f"Invalid groups for this course: {invalid_group_ids}")

        # Update main-cohort enrolment only inside the course's eligible scope.
        self.db.query(GroupAssignment).filter(
            GroupAssignment.course_id == course.id,
            GroupAssignment.group_id.in_(list(eligible_group_ids)),
        ).delete(synchronize_session=False)
        for group_id in requested_group_ids:
            self.db.add(GroupAssignment(course_id=course.id, group_id=group_id))

        # If a parent cohort is explicitly enrolled here, remove stream-specific
        # enrolment/lecture remnants under that parent so the course is clearly
        # treated as a cohort-wide course again.
        if requested_group_ids:
            selected_stream_ids = [
                row[0]
                for row in self.db.query(StudentGroup.id).filter(
                    StudentGroup.parent_group_id.in_(requested_group_ids),
                    StudentGroup.group_type == GroupType.STREAM,
                ).all()
            ]
            if selected_stream_ids:
                self.db.query(GroupAssignment).filter(
                    GroupAssignment.course_id == course.id,
                    GroupAssignment.group_id.in_(selected_stream_ids),
                ).delete(synchronize_session=False)
                self.db.query(CourseGroupLink).filter(
                    CourseGroupLink.course_id == course.id,
                    CourseGroupLink.group_id.in_(selected_stream_ids),
                    CourseGroupLink.session_type == "lecture",
                ).delete(synchronize_session=False)

        # Rebuild main-group lecture delivery links so the generator sees one
        # clear source of truth for main cohorts.
        self.db.query(CourseGroupLink).filter(
            CourseGroupLink.course_id == course.id,
            CourseGroupLink.group_id.in_(list(eligible_group_ids)),
            CourseGroupLink.session_type == "lecture",
        ).delete(synchronize_session=False)

        if requested_group_ids:
            should_share = lecture_mode == "shared" and len(requested_group_ids) > 1
            shared_batch_id = self._next_shared_batch_id(course.id) if should_share else None
            for group_id in requested_group_ids:
                self.db.add(
                    CourseGroupLink(
                        course_id=course.id,
                        group_id=group_id,
                        is_shared=should_share,
                        shared_batch_id=shared_batch_id,
                        session_type="lecture",
                    )
                )

        self.db.flush()
        return {
            "selected_group_count": len(requested_group_ids),
            "lecture_mode": "shared" if lecture_mode == "shared" and len(requested_group_ids) > 1 else "separate",
        }

    def _next_shared_batch_id(self, course_id: int) -> int:
        rows = (
            self.db.query(CourseGroupLink.shared_batch_id)
            .filter(
                CourseGroupLink.course_id == course_id,
                CourseGroupLink.shared_batch_id.isnot(None),
            )
            .all()
        )
        batch_ids = [row[0] for row in rows if row[0] is not None]
        return (max(batch_ids) + 1) if batch_ids else 1
