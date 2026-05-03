"""
Timetable Version Service

Handles version creation, restoration, and comparison for timetables.
Supports rollback to previous states and version history tracking.
"""

from sqlalchemy.orm import Session
from typing import List, Dict, Any, Optional
from datetime import datetime, timezone, time as dt_time
from ..models import Timetable, TimetableSlot, TimetableVersion, User


class VersionService:
    """Service for managing timetable versions"""
    
    def __init__(self, db: Session):
        self.db = db

    def _serialize_timetable(self, timetable: Timetable) -> Dict[str, Any]:
        return {
            "name": timetable.name,
            "semester": timetable.semester,
            "year": timetable.year,
            "academic_half": timetable.academic_half,
            "is_active": timetable.is_active,
            "generation_metadata": timetable.generation_metadata,
        }

    def _serialize_slots(self, slots: List[TimetableSlot]) -> List[Dict[str, Any]]:
        return [
            {
                "id": slot.id,
                "course_id": slot.course_id,
                "room_id": slot.room_id,
                "lecturer_id": slot.lecturer_id,
                "group_id": slot.group_id,
                "day_of_week": slot.day_of_week,
                "start_time": slot.start_time.isoformat() if slot.start_time else None,
                "end_time": slot.end_time.isoformat() if slot.end_time else None,
            }
            for slot in slots
        ]

    def _slot_key(self, slot_data: Dict[str, Any]) -> str:
        return (
            f"{slot_data.get('day_of_week')}_"
            f"{slot_data.get('start_time')}_"
            f"{slot_data.get('course_id')}_"
            f"{slot_data.get('group_id')}"
        )

    def _build_full_snapshot(self, timetable: Timetable, slots: List[TimetableSlot]) -> Dict[str, Any]:
        return {
            "timetable": self._serialize_timetable(timetable),
            "slots": self._serialize_slots(slots),
        }

    def _compute_diff(
        self,
        previous_snapshot: Dict[str, Any],
        current_snapshot: Dict[str, Any],
    ) -> Dict[str, Any]:
        prev_slots = {
            self._slot_key(slot): slot for slot in previous_snapshot.get("slots", [])
        }
        curr_slots = {
            self._slot_key(slot): slot for slot in current_snapshot.get("slots", [])
        }

        added = [slot for key, slot in curr_slots.items() if key not in prev_slots]
        removed = [slot for key, slot in prev_slots.items() if key not in curr_slots]

        modified = []
        for key in prev_slots:
            if key in curr_slots and prev_slots[key] != curr_slots[key]:
                modified.append({"old": prev_slots[key], "new": curr_slots[key]})

        timetable_patch = {}
        prev_timetable = previous_snapshot.get("timetable", {})
        curr_timetable = current_snapshot.get("timetable", {})
        for field, value in curr_timetable.items():
            if prev_timetable.get(field) != value:
                timetable_patch[field] = value

        return {
            "storage_mode": "diff",
            "changes": {
                "timetable_patch": timetable_patch,
                "added_slots": added,
                "removed_slot_keys": [self._slot_key(slot) for slot in removed],
                "modified_slots": modified,
            },
        }

    def _apply_diff(
        self,
        base_snapshot: Dict[str, Any],
        diff_payload: Dict[str, Any],
    ) -> Dict[str, Any]:
        snapshot = {
            "timetable": dict(base_snapshot.get("timetable", {})),
            "slots": [dict(slot) for slot in base_snapshot.get("slots", [])],
        }

        changes = diff_payload.get("changes", {})
        snapshot["timetable"].update(changes.get("timetable_patch", {}))

        slot_map = {self._slot_key(slot): slot for slot in snapshot.get("slots", [])}

        for key in changes.get("removed_slot_keys", []):
            slot_map.pop(key, None)

        for mod in changes.get("modified_slots", []):
            new_slot = mod.get("new", {})
            slot_map[self._slot_key(new_slot)] = new_slot

        for new_slot in changes.get("added_slots", []):
            slot_map[self._slot_key(new_slot)] = new_slot

        snapshot["slots"] = list(slot_map.values())
        return snapshot

    def _materialize_version_snapshot(self, version: TimetableVersion) -> Dict[str, Any]:
        chain = self.db.query(TimetableVersion).filter(
            TimetableVersion.timetable_id == version.timetable_id,
            TimetableVersion.version_number <= version.version_number,
        ).order_by(TimetableVersion.version_number.asc()).all()

        materialized = {"timetable": {}, "slots": []}
        for item in chain:
            payload = item.snapshot_data or {}
            mode = payload.get("storage_mode", "full")

            if mode == "full":
                materialized = payload.get("state", payload)
            elif mode == "diff":
                materialized = self._apply_diff(materialized, payload)
            else:
                materialized = payload

        return materialized
    
    def create_version(
        self, 
        timetable_id: int, 
        user_id: int, 
        description: Optional[str] = None
    ) -> TimetableVersion:
        """
        Create a new version snapshot of the current timetable state.
        
        Args:
            timetable_id: ID of the timetable to version
            user_id: ID of the user creating the version
            description: Optional description of the version
            
        Returns:
            TimetableVersion: The created version
        """
        # Get the timetable
        timetable = self.db.query(Timetable).filter(Timetable.id == timetable_id).first()
        if not timetable:
            raise ValueError(f"Timetable {timetable_id} not found")
        
        # Get all slots for this timetable
        slots = self.db.query(TimetableSlot).filter(
            TimetableSlot.timetable_id == timetable_id
        ).all()
        
        current_snapshot = self._build_full_snapshot(timetable, slots)
        
        # Get the next version number
        last_version = self.db.query(TimetableVersion).filter(
            TimetableVersion.timetable_id == timetable_id
        ).order_by(TimetableVersion.version_number.desc()).first()
        
        next_version_number = (last_version.version_number + 1) if last_version else 1
        
        if last_version:
            previous_snapshot = self._materialize_version_snapshot(last_version)
            snapshot_data = self._compute_diff(previous_snapshot, current_snapshot)
            snapshot_data["base_version_number"] = last_version.version_number
        else:
            snapshot_data = {
                "storage_mode": "full",
                "state": current_snapshot,
            }

        # Create the version
        version = TimetableVersion(
            timetable_id=timetable_id,
            version_number=next_version_number,
            description=description or f"Version {next_version_number}",
            snapshot_data=snapshot_data,
            created_at=datetime.now(timezone.utc),
            created_by_id=user_id
        )
        
        self.db.add(version)
        self.db.commit()
        self.db.refresh(version)
        
        return version
    
    def get_versions(self, timetable_id: int) -> List[Dict[str, Any]]:
        """
        Get all versions for a timetable.
        
        Args:
            timetable_id: ID of the timetable
            
        Returns:
            List of version data with metadata
        """
        versions = self.db.query(TimetableVersion).filter(
            TimetableVersion.timetable_id == timetable_id
        ).order_by(TimetableVersion.version_number.desc()).all()
        
        result = []
        for version in versions:
            # Get creator info
            creator = self.db.query(User).filter(User.id == version.created_by_id).first()
            
            materialized = self._materialize_version_snapshot(version)

            result.append({
                "id": version.id,
                "version_number": version.version_number,
                "description": version.description,
                "created_at": version.created_at,
                "created_by": {
                    "id": creator.id,
                    "username": creator.username,
                    "full_name": creator.full_name
                } if creator else None,
                "storage_mode": (version.snapshot_data or {}).get("storage_mode", "full"),
                "slot_count": len(materialized.get("slots", []))
            })
        
        return result
    
    def get_version(self, version_id: int) -> Optional[TimetableVersion]:
        """
        Get a specific version by ID.
        
        Args:
            version_id: ID of the version
            
        Returns:
            TimetableVersion or None
        """
        return self.db.query(TimetableVersion).filter(
            TimetableVersion.id == version_id
        ).first()
    
    def restore_version(
        self, 
        timetable_id: int, 
        version_id: int, 
        user_id: int
    ) -> Dict[str, Any]:
        """
        Restore a timetable to a previous version.
        Creates a new version of the current state before restoring.
        
        Args:
            timetable_id: ID of the timetable
            version_id: ID of the version to restore
            user_id: ID of the user performing the restore
            
        Returns:
            Dict with restoration summary
        """
        # Get the version to restore
        version = self.db.query(TimetableVersion).filter(
            TimetableVersion.id == version_id,
            TimetableVersion.timetable_id == timetable_id
        ).first()
        
        if not version:
            raise ValueError(f"Version {version_id} not found for timetable {timetable_id}")
        
        # Create a backup version of the current state before restoring
        backup_version = self.create_version(
            timetable_id, 
            user_id, 
            f"Auto-backup before restoring to v{version.version_number}"
        )
        
        # Get the timetable
        timetable = self.db.query(Timetable).filter(Timetable.id == timetable_id).first()
        if not timetable:
            raise ValueError(f"Timetable {timetable_id} not found")
        
        # Delete all existing slots
        self.db.query(TimetableSlot).filter(
            TimetableSlot.timetable_id == timetable_id
        ).delete()
        
        # Restore timetable metadata
        snapshot = self._materialize_version_snapshot(version)
        timetable_data = snapshot.get("timetable", {})
        timetable.name = timetable_data.get("name", timetable.name)
        timetable.semester = timetable_data.get("semester", timetable.semester)
        timetable.year = timetable_data.get("year", timetable.year)
        timetable.academic_half = timetable_data.get("academic_half", timetable.academic_half)
        # Don't restore is_active to prevent accidental activation
        timetable.generation_metadata = timetable_data.get("generation_metadata")
        
        # Restore slots
        restored_slots = []
        for slot_data in snapshot.get("slots", []):
            start_time = None
            if slot_data.get("start_time"):
                start_time = dt_time.fromisoformat(slot_data["start_time"])
            
            end_time = None
            if slot_data.get("end_time"):
                end_time = dt_time.fromisoformat(slot_data["end_time"])
            
            slot = TimetableSlot(
                timetable_id=timetable_id,
                course_id=slot_data.get("course_id"),
                room_id=slot_data.get("room_id"),
                lecturer_id=slot_data.get("lecturer_id"),
                group_id=slot_data.get("group_id"),
                day_of_week=slot_data.get("day_of_week"),
                start_time=start_time,
                end_time=end_time
            )
            self.db.add(slot)
            restored_slots.append(slot)
        
        self.db.commit()
        
        return {
            "status": "success",
            "message": f"Timetable restored to version {version.version_number}",
            "version_number": version.version_number,
            "backup_version_id": backup_version.id,
            "slots_restored": len(restored_slots)
        }
    
    def compare_versions(
        self, 
        timetable_id: int, 
        version1_id: int, 
        version2_id: int
    ) -> Dict[str, Any]:
        """
        Compare two versions of a timetable.
        
        Args:
            timetable_id: ID of the timetable
            version1_id: ID of the first version
            version2_id: ID of the second version
            
        Returns:
            Dict with comparison data
        """
        version1 = self.db.query(TimetableVersion).filter(
            TimetableVersion.id == version1_id,
            TimetableVersion.timetable_id == timetable_id
        ).first()
        
        version2 = self.db.query(TimetableVersion).filter(
            TimetableVersion.id == version2_id,
            TimetableVersion.timetable_id == timetable_id
        ).first()
        
        if not version1 or not version2:
            raise ValueError("One or both versions not found")
        
        snapshot1 = self._materialize_version_snapshot(version1)
        snapshot2 = self._materialize_version_snapshot(version2)

        # Get slots from both versions
        slots1 = {
            f"{s['day_of_week']}_{s['start_time']}_{s['course_id']}": s 
            for s in snapshot1.get("slots", [])
        }
        slots2 = {
            f"{s['day_of_week']}_{s['start_time']}_{s['course_id']}": s 
            for s in snapshot2.get("slots", [])
        }
        
        # Find differences
        added_slots = [s for key, s in slots2.items() if key not in slots1]
        removed_slots = [s for key, s in slots1.items() if key not in slots2]
        modified_slots = []
        
        for key in slots1.keys():
            if key in slots2:
                s1 = slots1[key]
                s2 = slots2[key]
                # Check if any field changed
                if (s1.get("lecturer_id") != s2.get("lecturer_id") or 
                    s1.get("room_id") != s2.get("room_id") or
                    s1.get("group_id") != s2.get("group_id")):
                    modified_slots.append({
                        "old": s1,
                        "new": s2
                    })
        
        return {
            "version1": {
                "id": version1.id,
                "version_number": version1.version_number,
                "description": version1.description,
                "created_at": version1.created_at
            },
            "version2": {
                "id": version2.id,
                "version_number": version2.version_number,
                "description": version2.description,
                "created_at": version2.created_at
            },
            "summary": {
                "added_slots": len(added_slots),
                "removed_slots": len(removed_slots),
                "modified_slots": len(modified_slots)
            },
            "details": {
                "added": added_slots,
                "removed": removed_slots,
                "modified": modified_slots
            }
        }
    
    def delete_version(self, version_id: int) -> bool:
        """
        Delete a specific version.
        
        Args:
            version_id: ID of the version to delete
            
        Returns:
            bool: True if deleted successfully
        """
        version = self.db.query(TimetableVersion).filter(
            TimetableVersion.id == version_id
        ).first()
        
        if not version:
            return False
        
        self.db.delete(version)
        self.db.commit()
        return True
