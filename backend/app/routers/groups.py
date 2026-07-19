from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, Request
from sqlalchemy.orm import Session
from typing import Dict, List, Optional, Set
from collections import defaultdict
import pandas as pd
import io
from ..database import get_db
from ..schemas import (
    StudentGroup,
    StudentGroupCreate,
    StudentGroupUpdate,
    SubGroupBulkCreate,
    GroupType,
    Course,
    GroupCourseUpdate,
    GroupCourseMapping,
)
from ..models import UserRole, StudentGroup as StudentGroupModel, User, Department
from ..auth import get_current_user, get_current_active_coordinator, get_current_active_hod
from ..utils.sanitization import sanitize_input
from ..utils.audit_logger import AuditLogger
from ..services.notification_service import NotificationService
from ..services.group_course_mapping_service import GroupCourseMappingService
from ..utils.bulk_import_helpers import resolve_department_id, ffill_department_columns
from ..utils.department_utils import find_general_department, is_general_department
from ..utils.school_scope import filter_group_query_for_user

router = APIRouter(prefix="/api/v1/groups", tags=["student-groups"])

# Validation helpers
def validate_group_fields(name: str, size: int, level: int) -> Optional[dict]:
    """Validate student group field values. Returns error dict if invalid, None if valid."""
    if not name or len(name.strip()) == 0:
        return {"detail": "Group name cannot be empty", "field": "name"}
    if len(name) > 100:
        return {"detail": "Group name must be 100 characters or less", "field": "name"}
    if size < 1 or size > 500:
        return {"detail": "Group size must be between 1 and 500", "field": "size"}
    # Accept both year-level format (1-7) and hundred-level format (100-700)
    valid_hundred_levels = [100, 200, 300, 400, 500, 600, 700]
    valid_year_levels = [1, 2, 3, 4, 5, 6, 7]
    if level not in valid_hundred_levels and level not in valid_year_levels:
        return {"detail": "Level must be a year (1-7) or hundred level (100-700)", "field": "level"}
    return None


def normalize_level(level: int) -> int:
    """Normalize year-level (1-7) to hundred-level (100-700)."""
    if 1 <= level <= 7:
        return level * 100
    return level


def _inherit_parent_courses_to_stream(db: Session, stream_group: StudentGroupModel) -> None:
    """
    Copy the current parent group's course assignments onto a new stream.

    This gives every fresh stream the parent's baseline course set. The
    coordinator can then remove stream-specific exclusions afterwards.
    """
    if str(stream_group.group_type) != "stream" or not stream_group.parent_group_id:
        return

    from ..models import GroupAssignment, CourseGroupLink

    parent_course_ids = {
        row.course_id
        for row in db.query(GroupAssignment).filter(
            GroupAssignment.group_id == stream_group.parent_group_id
        ).all()
    }
    parent_course_ids.update(
        {
            row.course_id
            for row in db.query(CourseGroupLink).filter(
                CourseGroupLink.group_id == stream_group.parent_group_id
            ).all()
        }
    )

    existing_course_ids = {
        row.course_id
        for row in db.query(GroupAssignment).filter(GroupAssignment.group_id == stream_group.id).all()
    }
    existing_link_course_ids = {
        row.course_id
        for row in db.query(CourseGroupLink).filter(CourseGroupLink.group_id == stream_group.id).all()
    }

    # Inherit only for brand-new/unconfigured streams. Once a stream has
    # explicit course choices, keep coordinator-defined differences intact.
    if existing_course_ids or existing_link_course_ids:
        return

    for course_id in sorted(parent_course_ids):
        if course_id in existing_course_ids:
            continue
        db.add(GroupAssignment(group_id=stream_group.id, course_id=course_id))
        existing_course_ids.add(course_id)


def _effective_course_ids_for_group(db: Session, group: StudentGroupModel) -> Set[int]:
    """
    Resolve a group's effective course set.

    For streams, this includes parent baseline courses so a newly created stream
    immediately shows inherited courses in the assignment UI.
    """
    from ..models import GroupAssignment, CourseGroupLink

    direct_group_assignment_ids = {
        row.course_id
        for row in db.query(GroupAssignment).filter(GroupAssignment.group_id == group.id).all()
    }
    direct_link_ids = {
        row.course_id
        for row in db.query(CourseGroupLink).filter(CourseGroupLink.group_id == group.id).all()
    }
    direct_course_ids = set(direct_group_assignment_ids)
    direct_course_ids.update(direct_link_ids)

    if str(group.group_type) == "stream" and group.parent_group_id:
        parent_group = db.query(StudentGroupModel).filter(StudentGroupModel.id == group.parent_group_id).first()
        if parent_group:
            parent_course_ids = {
                row.course_id
                for row in db.query(GroupAssignment).filter(GroupAssignment.group_id == parent_group.id).all()
            }
            parent_course_ids.update(
                {
                    row.course_id
                    for row in db.query(CourseGroupLink).filter(CourseGroupLink.group_id == parent_group.id).all()
                }
            )

            if not direct_course_ids:
                return parent_course_ids

            all_relevant_ids = sorted(parent_course_ids | direct_course_ids)
            if not all_relevant_ids:
                return set()

            from ..models import Course

            owner_by_course_id = {
                row.id: row.department_id
                for row in db.query(Course.id, Course.department_id).filter(Course.id.in_(all_relevant_ids)).all()
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
                return inherited_parent_scoped_ids | direct_local_ids

            inherited_local_ids = {
                course_id
                for course_id in parent_course_ids
                if owner_by_course_id.get(course_id) == group.department_id
            }
            return inherited_parent_scoped_ids | inherited_local_ids

    return direct_course_ids


def _next_shared_batch_id_for_course(db: Session, course_id: int) -> int:
    from ..models import CourseGroupLink

    existing = db.query(CourseGroupLink.shared_batch_id).filter(
        CourseGroupLink.course_id == course_id,
        CourseGroupLink.shared_batch_id != None,
    ).all()
    batch_ids = [row[0] for row in existing if row[0] is not None]
    return (max(batch_ids) + 1) if batch_ids else 1


def _synchronize_stream_lecture_links(db: Session, stream_group: StudentGroupModel) -> None:
    """
    Keep lecture links aligned with stream assignments:
    - courses selected on 2+ sibling streams become shared
    - courses selected on one stream remain stream-specific
    """
    if str(stream_group.group_type) != "stream" or not stream_group.parent_group_id:
        return

    from ..models import GroupAssignment, CourseGroupLink

    parent_id = stream_group.parent_group_id
    sibling_streams = db.query(StudentGroupModel).filter(
        StudentGroupModel.parent_group_id == parent_id,
        StudentGroupModel.group_type == "stream",
    ).all()
    if not sibling_streams:
        return

    stream_ids = [s.id for s in sibling_streams]
    stream_scope_ids = stream_ids + [parent_id]

    assignment_rows = db.query(GroupAssignment.group_id, GroupAssignment.course_id).filter(
        GroupAssignment.group_id.in_(stream_ids)
    ).all()

    course_to_streams: Dict[int, Set[int]] = defaultdict(set)
    for group_id, course_id in assignment_rows:
        course_to_streams[course_id].add(group_id)

    existing_link_rows = db.query(CourseGroupLink.course_id).filter(
        CourseGroupLink.session_type == "lecture",
        CourseGroupLink.group_id.in_(stream_scope_ids),
    ).all()

    affected_course_ids: Set[int] = set(course_to_streams.keys())
    affected_course_ids.update({row[0] for row in existing_link_rows if row[0] is not None})

    if not affected_course_ids:
        return

    db.query(CourseGroupLink).filter(
        CourseGroupLink.session_type == "lecture",
        CourseGroupLink.course_id.in_(list(affected_course_ids)),
        CourseGroupLink.group_id.in_(stream_scope_ids),
    ).delete(synchronize_session=False)

    for course_id in sorted(affected_course_ids):
        selected_stream_ids = sorted(course_to_streams.get(course_id, set()))
        if not selected_stream_ids:
            continue

        if len(selected_stream_ids) > 1:
            batch_id = _next_shared_batch_id_for_course(db, course_id)
            for group_id in selected_stream_ids:
                db.add(
                    CourseGroupLink(
                        course_id=course_id,
                        group_id=group_id,
                        is_shared=True,
                        shared_batch_id=batch_id,
                        session_type="lecture",
                    )
                )
        else:
            db.add(
                CourseGroupLink(
                    course_id=course_id,
                    group_id=selected_stream_ids[0],
                    is_shared=False,
                    shared_batch_id=None,
                    session_type="lecture",
                )
            )

@router.get("/", response_model=List[StudentGroup])
async def get_groups(
    skip: int = 0,
    limit: int = 100,
    tier: Optional[str] = None,  # 'main' | 'stream' | 'lab' | None (returns all)
    department_id: Optional[int] = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get all student groups. HODs see only their department's groups.
    Use ?tier=main for main groups only, ?tier=stream for stream groups,
    ?tier=lab for lab subgroups.
    """
    query = filter_group_query_for_user(db.query(StudentGroupModel), current_user)

    # Optional department filter
    if department_id:
        query = query.filter(StudentGroupModel.department_id == department_id)

    # Tier filtering
    if tier == "main":
        # Main groups: no parent, type is general or department
        query = query.filter(
            StudentGroupModel.parent_group_id == None,
            StudentGroupModel.group_type.in_(["general", "department"])
        )
    elif tier == "stream":
        query = query.filter(StudentGroupModel.group_type == "stream")
    elif tier == "lab":
        query = query.filter(
            StudentGroupModel.group_type.in_(["lab_group", "tutorial_group", "drawing_group"])
        )

    groups = query.offset(skip).limit(limit).all()
    return groups

@router.post("/", response_model=StudentGroup, status_code=status.HTTP_201_CREATED)
async def create_group(
    request: Request,
    group: StudentGroupCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Create a new student group."""
    # Accept 'group_name' as an alias for 'name' (frontend sends group_name)
    resolved_name = group.name

    # Normalize level: accept year format (2-6) and convert to hundred format (200-600)
    resolved_level = normalize_level(group.level)

    # Validate field values
    validation_error = validate_group_fields(resolved_name, group.size, resolved_level)
    if validation_error:
        raise HTTPException(status_code=422, detail=validation_error["detail"])
    
    # Verify department exists
    if group.department_id:
        dept = db.query(Department).filter(Department.id == group.department_id).first()
        if not dept:
            raise HTTPException(status_code=422, detail="Invalid department_id")

    if group.parent_group_id:
        parent_group = db.query(StudentGroupModel).filter(StudentGroupModel.id == group.parent_group_id).first()
        if not parent_group:
            raise HTTPException(status_code=422, detail="Invalid parent_group_id")
    
    sanitized_name = sanitize_input(resolved_name, max_length=100)
    
    # Check for duplicate group name
    existing = db.query(StudentGroupModel).filter(StudentGroupModel.name == sanitized_name).first()
    if existing:
        raise HTTPException(status_code=409, detail=f"Group '{resolved_name}' already exists")
    
    # Sanitize inputs
    group_data = group.model_dump()
    group_data['name'] = sanitized_name
    group_data['level'] = resolved_level

    # Inject university_id to satisfy not-null constraint
    group_data['university_id'] = getattr(current_user, 'university_id', None) or 1

    
    db_group = StudentGroupModel(**group_data)
    db.add(db_group)
    db.flush()
    _inherit_parent_courses_to_stream(db, db_group)
    _synchronize_stream_lecture_links(db, db_group)
    db.commit()
    db.refresh(db_group)
    
    AuditLogger.log_data_modification(
        request=request,
        user_id=current_user.id,
        username=current_user.username,
        operation="CREATE",
        resource_type="group",
        resource_id=db_group.id,
        details={"group_name": db_group.name}
    )
    NotificationService(db).notify_coordinators(
        title="New Student Group",
        message=f"{current_user.username} has added student group {db_group.name}.",
        type="info"
    )
    
    return db_group

@router.put("/{group_id}", response_model=StudentGroup)
async def update_group(
    request: Request,
    group_id: int,
    group_update: StudentGroupUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Update a student group."""
    db_group = db.query(StudentGroupModel).filter(StudentGroupModel.id == group_id).first()
    
    if not db_group:
        raise HTTPException(status_code=404, detail="Group not found")
    
    update_data = group_update.model_dump(exclude_unset=True)
    
    # Build full group data for validation (merge existing with updates)
    current_data = {
        "name": db_group.name,
        "size": db_group.size,
        "level": db_group.level,
    }
    current_data.update(update_data)
    
    # Validate updated field values
    validation_error = validate_group_fields(
        current_data["name"], current_data["size"], current_data["level"]
    )
    if validation_error:
        raise HTTPException(status_code=422, detail=validation_error["detail"])
    
    # Verify department exists if being updated
    if "department_id" in update_data and update_data["department_id"]:
        dept = db.query(Department).filter(Department.id == update_data["department_id"]).first()
        if not dept:
            raise HTTPException(status_code=422, detail="Invalid department_id")

    if "parent_group_id" in update_data and update_data["parent_group_id"]:
        parent_group = db.query(StudentGroupModel).filter(StudentGroupModel.id == update_data["parent_group_id"]).first()
        if not parent_group:
            raise HTTPException(status_code=422, detail="Invalid parent_group_id")
    
    # Sanitize incoming name before checking or updating
    if "name" in update_data:
        sanitized_update_name = sanitize_input(update_data["name"], max_length=100)
        
        # Check for duplicate name if being updated (and it actually changed)
        if sanitized_update_name != db_group.name:
            existing = db.query(StudentGroupModel).filter(StudentGroupModel.name == sanitized_update_name).first()
            if existing:
                raise HTTPException(status_code=409, detail=f"Group '{update_data['name']}' already exists")
        
        update_data["name"] = sanitized_update_name
    
    for field, value in update_data.items():
        setattr(db_group, field, value)
    db.flush()
    _inherit_parent_courses_to_stream(db, db_group)
    _synchronize_stream_lecture_links(db, db_group)
    db.commit()
    db.refresh(db_group)
    
    AuditLogger.log_data_modification(
        request=request,
        user_id=current_user.id,
        username=current_user.username,
        operation="UPDATE",
        resource_type="group",
        resource_id=db_group.id,
        details={"group_name": db_group.name, "updates": list(update_data.keys())}
    )
    
    return db_group


@router.get("/{group_id}/courses", response_model=List[Course])
async def get_group_courses(
    group_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get the effective courses for this group (including stream inheritance)."""
    db_group = db.query(StudentGroupModel).filter(StudentGroupModel.id == group_id).first()
    if not db_group:
        raise HTTPException(status_code=404, detail="Group not found")

    from ..models import Course

    course_ids = _effective_course_ids_for_group(db, db_group)
    if not course_ids:
        return []

    courses = db.query(Course).filter(Course.id.in_(list(course_ids))).all()
    return courses


@router.get("/{group_id}/course-map", response_model=GroupCourseMapping)
async def get_group_course_map(
    group_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Return the group-side course catalogue with auto-mapped same-level recommendations."""
    db_group = db.query(StudentGroupModel).filter(StudentGroupModel.id == group_id).first()
    if not db_group:
        raise HTTPException(status_code=404, detail="Group not found")

    gen_dept = find_general_department(db)
    gen_dept_id = gen_dept.id if gen_dept else -1
    if current_user.role == UserRole.HOD:
        if db_group.department_id != current_user.department_id and db_group.department_id != gen_dept_id:
            raise HTTPException(status_code=403, detail="You can only manage groups in your own department or the GEN department.")

    mapping_service = GroupCourseMappingService(db)
    eligible_courses = mapping_service.eligible_courses_for_group(db_group)
    recommended_course_ids = mapping_service.recommended_course_ids(db_group)
    can_edit_all = current_user.role == UserRole.COORDINATOR

    def _course_editability(course: Course) -> tuple[bool, str, str | None]:
        if can_edit_all:
            return True, "owner", None
        owner_department_id = course.department_id
        if owner_department_id == current_user.department_id:
            return True, "owner", None
        owner_code = course.department.code if course.department else "owner department"
        return False, "read_only", f"Controlled by {owner_code}. Open the course to change shared enrolment."

    editable_course_ids = [
        item.course.id
        for item in eligible_courses
        if _course_editability(item.course)[0]
    ]
    readonly_course_ids = [
        item.course.id
        for item in eligible_courses
        if not _course_editability(item.course)[0]
    ]
    selected_course_ids = mapping_service.selected_course_ids_for_group_map(
        db_group,
        editable_available_ids=editable_course_ids,
        readonly_available_ids=readonly_course_ids,
    )
    selected_lookup = set(selected_course_ids)
    recommended_lookup = set(recommended_course_ids)
    inherited_parent_ids = mapping_service.inherited_parent_course_ids_for_stream(db_group)

    return {
        "group_id": db_group.id,
        "group_name": db_group.name,
        "group_level": db_group.level,
        "group_department_id": db_group.department_id,
        "group_department_name": db_group.department.name if db_group.department else None,
        "selected_course_ids": selected_course_ids,
        "recommended_course_ids": recommended_course_ids,
        "available_courses": [
            {
                "id": item.course.id,
                "code": item.course.code,
                "name": item.course.name,
                "level": item.course.level,
                "department_id": item.course.department_id,
                "department_name": item.course.department.name if item.course.department else None,
                "department_code": item.course.department.code if item.course.department else None,
                "course_type": item.course.course_type.value if hasattr(item.course.course_type, "value") else str(item.course.course_type),
                "shared_with_department_ids": item.course.shared_with_department_ids,
                "source_kind": item.source_kind,
                "owner_department_id": item.course.department_id,
                "owner_department_name": item.course.department.name if item.course.department else None,
                "owner_department_code": item.course.department.code if item.course.department else None,
                "editable": _course_editability(item.course)[0],
                "control_scope": _course_editability(item.course)[1],
                "read_only_reason": _course_editability(item.course)[2],
                "inherited_from_parent": item.course.id in inherited_parent_ids,
                "selected": item.course.id in selected_lookup,
                "recommended": item.course.id in recommended_lookup,
            }
            for item in eligible_courses
        ],
        "note": (
            "Courses are auto-suggested from the same level using own-department, general, "
            "and explicitly shared cross-department rules. Streams can still refine the baseline."
        ),
    }

@router.post("/{group_id}/courses", response_model=List[Course])
async def update_group_courses(
    request: Request,
    group_id: int,
    assignment_data: GroupCourseUpdate,
    current_user: User = Depends(get_current_active_hod),
    db: Session = Depends(get_db)
):
    """Update course assignments for a group. Coordinators can update any group; HODs can only update their department's groups."""
    db_group = db.query(StudentGroupModel).filter(StudentGroupModel.id == group_id).first()
    if not db_group:
        raise HTTPException(status_code=404, detail="Group not found")

    from ..models import UserRole, GroupAssignment, Course

    gen_dept = find_general_department(db)
    gen_dept_id = gen_dept.id if gen_dept else -1

    # HODs can only manage their own department's groups OR GEN groups
    if current_user.role == UserRole.HOD:
        if db_group.department_id != current_user.department_id and db_group.department_id != gen_dept_id:
            raise HTTPException(status_code=403, detail="You can only manage groups in your own department or the GEN department.")

    # Check if courses exist
    if assignment_data.course_ids:
        valid_courses = db.query(Course).filter(Course.id.in_(assignment_data.course_ids)).count()
        if valid_courses != len(assignment_data.course_ids):
            raise HTTPException(status_code=400, detail="One or more courses provided do not exist.")

    # Bootstrap sibling streams once from parent baseline if they are still
    # unconfigured, so common courses can be recognized as shared.
    if (
        str(db_group.group_type) == "stream"
        and db_group.parent_group_id
        and current_user.role != UserRole.HOD
    ):
        sibling_streams = db.query(StudentGroupModel).filter(
            StudentGroupModel.parent_group_id == db_group.parent_group_id,
            StudentGroupModel.group_type == "stream"
        ).all()
        for sibling in sibling_streams:
            _inherit_parent_courses_to_stream(db, sibling)

    if current_user.role == UserRole.HOD:
        dept_id = current_user.department_id
        allowed_course_ids = {
            row[0]
            for row in db.query(Course.id).filter(Course.department_id == dept_id).all()
        }

        # Receiving departments can see shared-in / general courses on the group
        # view, but they do not control those rows from the group side.
        assignment_data.course_ids = [cid for cid in assignment_data.course_ids if cid in allowed_course_ids]

        if allowed_course_ids:
            db.query(GroupAssignment).filter(
                GroupAssignment.group_id == group_id,
                GroupAssignment.course_id.in_(list(allowed_course_ids))
            ).delete(synchronize_session=False)
    else:
        # Clear existing for Coordinator
        db.query(GroupAssignment).filter(GroupAssignment.group_id == group_id).delete(synchronize_session=False)

    # Insert new
    for cid in assignment_data.course_ids:
        new_assignment = GroupAssignment(group_id=group_id, course_id=cid)
        db.add(new_assignment)

    _synchronize_stream_lecture_links(db, db_group)

    db.commit()
    
    AuditLogger.log_data_modification(
        request=request,
        user_id=current_user.id,
        username=current_user.username,
        operation="UPDATE",
        resource_type="group_courses",
        resource_id=group_id,
        details={"group_name": db_group.name, "course_ids": assignment_data.course_ids}
    )
    
    # Return updated effective list
    effective_course_ids = _effective_course_ids_for_group(db, db_group)
    if not effective_course_ids:
        return []

    return db.query(Course).filter(Course.id.in_(list(effective_course_ids))).all()

@router.delete("/{group_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_group(
    request: Request,
    group_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Delete a student group."""
    db_group = db.query(StudentGroupModel).filter(StudentGroupModel.id == group_id).first()
    
    if not db_group:
        raise HTTPException(status_code=404, detail="Group not found")
        
    from ..models import UserRole, GroupAssignment, CourseGroupLink, TimetableSlot
    
    # Cascade delete related entries safely
    db.query(GroupAssignment).filter(GroupAssignment.group_id == group_id).delete(synchronize_session=False)
    db.query(CourseGroupLink).filter(CourseGroupLink.group_id == group_id).delete(synchronize_session=False)
    db.query(TimetableSlot).filter(TimetableSlot.group_id == group_id).delete(synchronize_session=False)
    
    # Also delete child subgroups first
    db.query(StudentGroupModel).filter(StudentGroupModel.parent_group_id == group_id).delete(synchronize_session=False)
    
    db.delete(db_group)
    db.commit()
    
    name = db_group.name
    AuditLogger.log_data_modification(
        request=request,
        user_id=current_user.id,
        username=current_user.username,
        operation="DELETE",
        resource_type="group",
        resource_id=group_id,
        details={"group_name": name}
    )
    NotificationService(db).notify_coordinators(
        title="Group Deleted",
        message=f"Student group {name} was deleted by {current_user.username}.",
        type="warning"
    )
    
    return None

@router.delete("/", status_code=status.HTTP_200_OK)
async def delete_all_groups(
    request: Request,
    current_user: User = Depends(get_current_active_coordinator),
    db: Session = Depends(get_db)
):
    """Delete all student groups. Coordinator only. Use before bulk re-upload."""
    from ..models import UserRole, GroupAssignment, CourseGroupLink, TimetableSlot
    
    # Pre-clear child records to avoid FK constraint errors when deleting all groups
    db.query(GroupAssignment).delete(synchronize_session=False)
    db.query(CourseGroupLink).delete(synchronize_session=False)
    db.query(TimetableSlot).delete(synchronize_session=False)
    
    # Subgroups map to parent groups, so they're all wiped together
    count = db.query(StudentGroupModel).count()
    db.query(StudentGroupModel).delete(synchronize_session=False)
    db.commit()
    
    AuditLogger.log_data_modification(
        request=request,
        user_id=current_user.id,
        username=current_user.username,
        operation="DELETE",
        resource_type="group_bulk",
        details={"count_deleted": count}
    )
    NotificationService(db).notify_coordinators(
        title="All Groups Cleared",
        message=f"A bulk clear of all {count} groups was executed by {current_user.username}.",
        type="warning"
    )
    
    return {"status": "success", "deleted": count, "message": f"Deleted {count} groups"}

@router.post("/bulk-upload", response_model=dict)
async def bulk_upload_groups(
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_active_coordinator),
    db: Session = Depends(get_db)
):
    """
    Bulk upload student groups from Excel/CSV file. Coordinator only.

    Required columns : name (or group_name) | level | size
    Dept identifier  : at least one of department_id | department_code | department_name
    Optional columns : group_type | parent_name

    group_type values (case-insensitive):
        department (default) | stream | lab_group | tutorial_group | drawing_group | general

    parent_name : name of the parent group in this file or already in the DB.
        Used for elective streams and session subgroups.
        Two-pass resolution — order of rows in the file does not matter.
    """
    if file.content_type not in ["text/csv", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", "application/vnd.ms-excel"]:
        raise HTTPException(status_code=400, detail="File must be CSV or Excel format")

    try:
        contents = await file.read()

        if file.content_type == "text/csv":
            text = contents.decode("utf-8", errors="replace")
            sep = "\t" if ("\t" in text and text.count("\t") > text.count(",")) else \
                  (";" if text.count(";") > text.count(",") else ",")
            df = pd.read_csv(io.StringIO(text), sep=sep)
        else:
            df = pd.read_excel(io.BytesIO(contents))

        df.columns = [c.strip().lower() for c in df.columns]

        # Allow 'group_name' alias
        has_name = 'name' in df.columns or 'group_name' in df.columns
        missing = [c for c in ['level', 'size'] if c not in df.columns]
        if not has_name:
            missing.append('name (or group_name)')
        if missing:
            raise HTTPException(status_code=400,
                detail=f"Missing required column(s): {', '.join(missing)}")

        dept_columns = ['department_id', 'department_code', 'department_name']
        if not any(col in df.columns for col in dept_columns):
            raise HTTPException(status_code=400,
                detail="Must provide at least one department identifier: department_id, department_code, or department_name")

        # Pre-fetch departments
        departments = db.query(Department).filter(
            Department.university_id == current_user.university_id
        ).all() if current_user.university_id else db.query(Department).all()

        dept_id_map   = {d.id: d.id for d in departments}
        dept_id_map[0] = 0
        dept_code_map = {d.code.upper(): d.id for d in departments if d.code}
        dept_name_map = {d.name.lower(): d.id for d in departments if d.name}
        general_dept = next((d for d in departments if is_general_department(d)), None)
        general_dept_id = general_dept.id if general_dept else 0
        dept_id_map[0] = general_dept_id
        dept_code_map['GEN'] = general_dept_id
        dept_code_map['ENG'] = general_dept_id

        # Valid group types (normalised)
        VALID_TYPES = {t.value for t in GroupType}

        created_count = 0
        skipped_count = 0
        errors: list[str] = []

        # ── Pass 1: create all groups (without parent links yet) ──────────
        created_names: dict[str, StudentGroupModel] = {}   # name → ORM object

        for idx, row in df.iterrows():
            row_label = f"Row {idx + 2}"
            try:
                resolved_dept_id = resolve_department_id(
                    row, departments, dept_id_map, dept_code_map, dept_name_map
                )
                if resolved_dept_id is None:
                    bad_val = str(row.get('department_code', row.get('department_name', 'MISSING')))
                    errors.append(f"{row_label}: Cannot match department '{bad_val}'")
                    skipped_count += 1
                    continue

                group_name_val = str(
                    row['name'] if 'name' in df.columns and pd.notna(row.get('name'))
                    else row.get('group_name', '')
                ).strip()

                if not group_name_val:
                    errors.append(f"{row_label}: Empty group name")
                    skipped_count += 1
                    continue
                    
                # Auto-append level to ensure uniqueness across different years (e.g., if user just inputs 'Computer Science')
                row_level_str = str(row['level']).strip()
                if row_level_str and row_level_str not in group_name_val:
                    group_name_val = f"{group_name_val} Yr{row_level_str}"

                sanitized_name = sanitize_input(group_name_val, max_length=200)

                # Check for existing group — also check legacy HTML-escaped
                # variants (e.g. "&amp;" stored from old sanitization)
                import html as _html
                escaped_name = _html.escape(sanitized_name)
                existing = db.query(StudentGroupModel).filter(
                    StudentGroupModel.name.in_([sanitized_name, escaped_name])
                ).first()
                if existing:
                    created_names[group_name_val] = existing
                    skipped_count += 1
                    continue

                # Resolve group_type
                raw_type = str(row.get('group_type', 'department')).strip().lower() \
                    if 'group_type' in df.columns and pd.notna(row.get('group_type')) \
                    else 'department'
                group_type = raw_type if raw_type in VALID_TYPES else 'department'

                # Infer group_type from name patterns if not explicit
                if raw_type not in VALID_TYPES:
                    lower_name = group_name_val.lower()
                    if any(k in lower_name for k in ('lab', 'drawing', 'practical')):
                        group_type = 'lab_group'
                    elif 'tutorial' in lower_name:
                        group_type = 'tutorial_group'

                group = StudentGroupModel(
                    university_id=current_user.university_id,
                    name=sanitized_name,
                    level=normalize_level(int(row['level'])),
                    department_id=resolved_dept_id,
                    size=int(row.get('size', 0)),
                    group_type=group_type,
                    display_code=sanitize_input(str(row.get('display_code', group_name_val))[:20], max_length=20)
                        if 'display_code' in df.columns and pd.notna(row.get('display_code'))
                        else None,
                )
                db.add(group)
                try:
                    db.flush()   # get the id without full commit
                except Exception as flush_err:
                    db.rollback()
                    errors.append(f"{row_label}: Duplicate or DB error for '{group_name_val}': {flush_err}")
                    skipped_count += 1
                    continue
                created_names[group_name_val] = group
                created_count += 1

            except Exception as e:
                errors.append(f"{row_label}: {e}")
                skipped_count += 1

        db.flush()

        # ── Pass 2: resolve parent_name links ─────────────────────────────
        if 'parent_name' in df.columns:
            # Build a name→id lookup that includes freshly created rows
            all_groups_by_name: dict[str, int] = {
                g.name: g.id
                for g in db.query(StudentGroupModel).filter(
                    StudentGroupModel.university_id == current_user.university_id
                ).all()
            }

            for idx, row in df.iterrows():
                row_label = f"Row {idx + 2} (parent link)"
                if 'parent_name' not in df.columns:
                    break
                raw_parent = row.get('parent_name')
                if not raw_parent or not pd.notna(raw_parent):
                    continue
                parent_name_str = str(raw_parent).strip()
                if not parent_name_str:
                    continue

                child_name = str(
                    row['name'] if 'name' in df.columns and pd.notna(row.get('name'))
                    else row.get('group_name', '')
                ).strip()

                parent_id = all_groups_by_name.get(parent_name_str)
                child_id  = all_groups_by_name.get(child_name)

                if not parent_id:
                    errors.append(f"{row_label}: parent '{parent_name_str}' not found in DB or this file")
                    continue
                if not child_id:
                    continue  # row was skipped in pass-1 (duplicate or error)

                child_obj = db.query(StudentGroupModel).filter(StudentGroupModel.id == child_id).first()
                if child_obj and child_obj.parent_group_id != parent_id:
                    child_obj.parent_group_id = parent_id
                if child_obj:
                    _inherit_parent_courses_to_stream(db, child_obj)
                    _synchronize_stream_lecture_links(db, child_obj)

        db.commit()

        return {
            "status": "success",
            "created": created_count,
            "skipped": skipped_count,
            "errors": errors if errors else None,
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Error processing file: {e}")


@router.post("/{group_id}/subgroups/bulk", response_model=List[StudentGroup], status_code=status.HTTP_201_CREATED)
async def generate_subgroups(
    group_id: int,
    request: SubGroupBulkCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Bulk generate subgroups for a parent group.
    Accessible to coordinator, hod, or lab_coordinator.
    
    naming_mode:
      - 'alpha'   -> A, B, C, D (up to 26)
      - 'numeric' -> {prefix}1, {prefix}2, {prefix}3
      - 'custom'  -> uses request.custom_names list
    
    size_per_group is enforced between 4 and 13 for lab groups.
    """
    allowed_roles = ["coordinator", "hod", "lab_coordinator"]
    if current_user.role not in allowed_roles:
        raise HTTPException(status_code=403, detail="Permission denied")

    parent_group = db.query(StudentGroupModel).filter(StudentGroupModel.id == group_id).first()
    if not parent_group:
        raise HTTPException(status_code=404, detail="Parent group not found")

    # Enforce size constraints for lab subgroups
    is_lab_type = request.group_type in ["lab_group", "tutorial_group", "drawing_group"]

    # Resolve subgroup label suffixes based on naming_mode
    ALPHA = list("ABCDEFGHIJKLMNOPQRSTUVWXYZ")

    if request.naming_mode == "alpha":
        if request.count > 26:
            raise HTTPException(status_code=422, detail="Alpha mode supports at most 26 groups (A-Z)")
        suffixes = ALPHA[:request.count]

    elif request.naming_mode == "custom":
        if not request.custom_names or len(request.custom_names) < request.count:
            raise HTTPException(
                status_code=422,
                detail=f"custom_names must have at least {request.count} entries"
            )
        suffixes = [str(n).strip() for n in request.custom_names[:request.count]]

    else:  # default: numeric  →  prefix + number (e.g. A1, A2)
        suffixes = [f"{request.prefix}{i}" for i in range(1, request.count + 1)]

    created_groups = []

    for suffix in suffixes:
        subgroup_name = f"{parent_group.name} - {suffix}"

        # Skip if already exists
        existing = db.query(StudentGroupModel).filter(
            StudentGroupModel.name == subgroup_name,
            StudentGroupModel.parent_group_id == group_id
        ).first()
        if existing:
            continue

        group_data = {
            "name": sanitize_input(subgroup_name, max_length=150),
            "level": parent_group.level,
            "department_id": parent_group.department_id,
            "size": request.size_per_group,
            "group_type": request.group_type,
            "parent_group_id": parent_group.id,
            "display_code": suffix,
            "university_id": getattr(current_user, "university_id", None) or 1
        }

        db_group = StudentGroupModel(**group_data)
        db.add(db_group)
        created_groups.append(db_group)

    db.flush()
    for grp in created_groups:
        _inherit_parent_courses_to_stream(db, grp)
        _synchronize_stream_lecture_links(db, grp)

    db.commit()
    for grp in created_groups:
        db.refresh(grp)

    return created_groups


@router.get("/{group_id}/subgroups", response_model=List[StudentGroup])
async def get_subgroups(
    group_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get all subgroups for a specific parent group."""
    parent_group = db.query(StudentGroupModel).filter(StudentGroupModel.id == group_id).first()
    if not parent_group:
        raise HTTPException(status_code=404, detail="Parent group not found")

    subgroups = db.query(StudentGroupModel).filter(
        StudentGroupModel.parent_group_id == group_id
    ).all()
    return subgroups


@router.get("/{group_id}/streams", response_model=List[StudentGroup])
async def get_streams(
    group_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get all stream (elective) subgroups for a main group."""
    parent_group = db.query(StudentGroupModel).filter(StudentGroupModel.id == group_id).first()
    if not parent_group:
        raise HTTPException(status_code=404, detail="Parent group not found")

    streams = db.query(StudentGroupModel).filter(
        StudentGroupModel.parent_group_id == group_id,
        StudentGroupModel.group_type == "stream"
    ).all()
    return streams


@router.delete("/{group_id}/subgroups/{subgroup_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_subgroup(
    group_id: int,
    subgroup_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Delete a single subgroup. Must belong to the specified parent group."""
    allowed_roles = ["coordinator", "hod", "lab_coordinator"]
    if current_user.role not in allowed_roles:
        raise HTTPException(status_code=403, detail="Permission denied")

    subgroup = db.query(StudentGroupModel).filter(
        StudentGroupModel.id == subgroup_id,
        StudentGroupModel.parent_group_id == group_id
    ).first()
    if not subgroup:
        raise HTTPException(status_code=404, detail="Subgroup not found under this parent group")

    db.delete(subgroup)
    db.commit()
    return None


@router.delete("/{group_id}/subgroups", status_code=status.HTTP_200_OK)
async def delete_all_subgroups(
    group_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Delete all subgroups for a parent group."""
    allowed_roles = ["coordinator", "hod", "lab_coordinator"]
    if current_user.role not in allowed_roles:
        raise HTTPException(status_code=403, detail="Permission denied")

    parent_group = db.query(StudentGroupModel).filter(StudentGroupModel.id == group_id).first()
    if not parent_group:
        raise HTTPException(status_code=404, detail="Parent group not found")

    count = db.query(StudentGroupModel).filter(
        StudentGroupModel.parent_group_id == group_id
    ).count()

    db.query(StudentGroupModel).filter(
        StudentGroupModel.parent_group_id == group_id
    ).delete()
    db.commit()
    return {"status": "success", "deleted": count}
