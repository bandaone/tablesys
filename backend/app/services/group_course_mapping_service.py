from __future__ import annotations

from dataclasses import dataclass
from typing import List, Sequence, Set

from sqlalchemy.orm import Session

from ..models import Course, CourseGroupLink, GroupAssignment, GroupType, StudentGroup
from ..utils.department_utils import find_general_department


def normalize_course_level(level: int) -> int:
    return level * 100 if 1 <= level <= 7 else level


@dataclass
class EligibleCourseOption:
    course: Course
    source_kind: str
    recommended: bool


class GroupCourseMappingService:
    """Resolve level-strict course visibility and sensible defaults for one group."""

    def __init__(self, db: Session) -> None:
        self.db = db

    def eligible_courses_for_group(self, group: StudentGroup) -> List[EligibleCourseOption]:
        target_level = normalize_course_level(group.level)
        alternate_level = target_level // 100 if target_level >= 100 else target_level * 100
        general_department = find_general_department(self.db)
        general_department_id = general_department.id if general_department else None

        query = (
            self.db.query(Course)
            .filter(Course.level.in_([target_level, alternate_level]))
            .order_by(Course.department_id.asc(), Course.code.asc())
        )

        eligible: List[EligibleCourseOption] = []
        for course in query.all():
            if course.department_id == group.department_id:
                eligible.append(EligibleCourseOption(course=course, source_kind="own", recommended=True))
                continue

            if general_department_id and course.department_id == general_department_id:
                is_universal_general = course.shared_with_department_ids is None
                is_targeted_general = group.department_id in (course.shared_with_department_ids or [])
                if is_universal_general or is_targeted_general:
                    eligible.append(EligibleCourseOption(course=course, source_kind="general", recommended=True))
                continue

            if group.department_id in (course.shared_with_department_ids or []):
                eligible.append(EligibleCourseOption(course=course, source_kind="shared", recommended=True))

        return eligible

    def direct_selected_course_ids(self, group: StudentGroup) -> List[int]:
        rows = (
            self.db.query(GroupAssignment.course_id)
            .filter(GroupAssignment.group_id == group.id)
            .all()
        )
        return sorted({row[0] for row in rows})

    def parent_effective_course_ids(self, group: StudentGroup) -> List[int]:
        if str(group.group_type) != GroupType.STREAM.value or not group.parent_group_id:
            return []

        parent_group = self.db.query(StudentGroup).filter(StudentGroup.id == group.parent_group_id).first()
        if not parent_group:
            return []

        parent_assignment_ids = {
            row.course_id
            for row in self.db.query(GroupAssignment).filter(GroupAssignment.group_id == parent_group.id).all()
        }
        parent_link_ids = {
            row.course_id
            for row in self.db.query(CourseGroupLink).filter(CourseGroupLink.group_id == parent_group.id).all()
        }
        return sorted(parent_assignment_ids | parent_link_ids)

    def inherited_parent_course_ids_for_stream(self, group: StudentGroup) -> Set[int]:
        if str(group.group_type) != GroupType.STREAM.value or not group.parent_group_id:
            return set()
        return set(self.parent_effective_course_ids(group))

    def effective_selected_course_ids(self, group: StudentGroup) -> List[int]:
        direct_group_assignment_ids = set(self.direct_selected_course_ids(group))
        direct_link_ids = {
            row.course_id
            for row in self.db.query(CourseGroupLink).filter(CourseGroupLink.group_id == group.id).all()
        }
        direct_course_ids = set(direct_group_assignment_ids) | direct_link_ids

        if str(group.group_type) == GroupType.STREAM.value and group.parent_group_id:
            parent_course_ids = set(self.parent_effective_course_ids(group))
            if not direct_course_ids:
                return sorted(parent_course_ids)

            all_relevant_ids = sorted(parent_course_ids | direct_course_ids)
            owner_by_course_id = {
                row.id: row.department_id
                for row in self.db.query(Course.id, Course.department_id).filter(Course.id.in_(all_relevant_ids)).all()
            }

            inherited_parent_scoped_ids = {
                course_id
                for course_id in parent_course_ids
                if owner_by_course_id.get(course_id) != group.department_id
            }
            direct_local_ids = {
                course_id
                for course_id in direct_course_ids
                if owner_by_course_id.get(course_id) == group.department_id
            }
            if direct_local_ids:
                return sorted(inherited_parent_scoped_ids | direct_local_ids)

            inherited_local_ids = {
                course_id
                for course_id in parent_course_ids
                if owner_by_course_id.get(course_id) == group.department_id
            }
            return sorted(inherited_parent_scoped_ids | inherited_local_ids)

        return sorted(direct_course_ids)

    def selected_course_ids_for_group_map(
        self,
        group: StudentGroup,
        *,
        editable_available_ids: Sequence[int],
        readonly_available_ids: Sequence[int],
    ) -> List[int]:
        editable_ids = set(editable_available_ids)
        readonly_ids = set(readonly_available_ids)

        if str(group.group_type) == GroupType.STREAM.value and group.parent_group_id:
            parent_ids = set(self.parent_effective_course_ids(group))
            direct_ids = set(self.direct_selected_course_ids(group))

            direct_editable_ids = direct_ids & editable_ids
            if direct_editable_ids:
                editable_selected = direct_editable_ids
            else:
                editable_selected = parent_ids & editable_ids

            readonly_selected = parent_ids & readonly_ids
            return sorted(editable_selected | readonly_selected)

        effective_ids = set(self.effective_selected_course_ids(group))
        selected_ids = effective_ids & (editable_ids | readonly_ids)
        if selected_ids:
            return sorted(selected_ids)

        return sorted(set(self.recommended_course_ids(group)) & editable_ids)

    def recommended_course_ids(self, group: StudentGroup) -> List[int]:
        return sorted({item.course.id for item in self.eligible_courses_for_group(group) if item.recommended})

    def initial_selected_course_ids(self, group: StudentGroup, available_course_ids: Sequence[int]) -> List[int]:
        available_ids = set(available_course_ids)
        effective_ids = [
            course_id for course_id in self.effective_selected_course_ids(group)
            if course_id in available_ids
        ]
        if effective_ids:
            return sorted(effective_ids)
        return [
            course_id for course_id in self.recommended_course_ids(group)
            if course_id in available_ids
        ]
