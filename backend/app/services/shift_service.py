from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.models.user import UserRole
from app.repositories.shift_repository import ShiftRepository
from app.schemas.shift import ShiftCreate, ShiftResponse, ShiftUpdate


class ShiftConflictError(Exception):
    pass


class ShiftNotFoundError(Exception):
    pass


class ShiftService:
    def __init__(self, db: Session) -> None:
        self._db = db
        self._repo = ShiftRepository(db)


    def list_shifts(self, *, skip: int = 0, limit: int = 100) -> list[ShiftResponse]:
        shifts = self._repo.list(skip=skip, limit=limit)
        return [ShiftResponse.model_validate(s) for s in shifts]

    def get_by_id(self, shift_id: int) -> ShiftResponse | None:
        shift = self._repo.get(shift_id)
        if shift is None or shift.is_deleted:
            return None
        return ShiftResponse.model_validate(shift)


    def create_shift(
        self,
        payload: ShiftCreate,
        *,
        actor_id: int,
        actor_role: UserRole,
    ) -> ShiftResponse:
        # FR-02 / FR-07: overlap check before writing
        if self._check_overlap(payload.start_time, payload.end_time):
            raise ShiftConflictError("Schedule conflict detected")

        shift = self._repo.create(payload, created_by=actor_id)

        # AU-07 / FR-05: audit log in same transaction
        self._write_audit(
            actor_id=actor_id,
            action="CREATE",
            target_id=shift.id,
            before=None,
            after=self._shift_dict(shift),
        )

        return ShiftResponse.model_validate(shift)

    def update_shift(
        self,
        shift_id: int,
        payload: ShiftUpdate,
        *,
        actor_id: int,
    ) -> ShiftResponse:
        shift = self._repo.get(shift_id)
        if shift is None or shift.is_deleted:
            raise ShiftNotFoundError(shift_id)

        before = self._shift_dict(shift)

        # Re-check overlap if times are being changed
        new_start = payload.start_time or shift.start_time
        new_end = payload.end_time or shift.end_time
        if self._check_overlap(new_start, new_end, exclude_id=shift_id):
            raise ShiftConflictError("Schedule conflict detected")

        shift = self._repo.update(shift, payload)

        self._write_audit(
            actor_id=actor_id,
            action="UPDATE",
            target_id=shift.id,
            before=before,
            after=self._shift_dict(shift),
        )

        return ShiftResponse.model_validate(shift)

def delete_shift(self, shift_id: int, *, actor_id: int, actor_role: UserRole) -> None:
        shift = self._repo.get(shift_id)
        if shift is None or shift.is_deleted:
            raise ShiftNotFoundError(shift_id)

        before = self._shift_dict(shift)

        # Spec security checklist: soft delete only — no hard DELETEs on shift records
        self._repo.soft_delete(shift)

        self._write_audit(
            actor_id=actor_id,   # Fix: Record the actual user who deleted the shift
            action="DELETE",
            target_id=shift_id,
            before=before,
            after=None,
        )
    def assign_shift(
        self,
        shift_id: int,
        user_id: int,
        *,
        actor_id: int,
    ) -> ShiftResponse:
        shift = self._repo.get(shift_id)
        if shift is None or shift.is_deleted:
            raise ShiftNotFoundError(shift_id)

        # Check overlap for the specific user being assigned
        if self._check_overlap(shift.start_time, shift.end_time, user_id=user_id):
            raise ShiftConflictError(f"Conflict for user_id {user_id}")

        before = self._shift_dict(shift)
        shift = self._repo.assign(shift, user_id=user_id)

        self._write_audit(
            actor_id=actor_id,
            action="ASSIGN",
            target_id=shift.id,
            before=before,
            after=self._shift_dict(shift),
        )

        return ShiftResponse.model_validate(shift)

    # ------------------------------------------------------------------ #
    # Private helpers
    # ------------------------------------------------------------------ #

    def _check_overlap(
        self,
        start: datetime,
        end: datetime,
        *,
        user_id: int | None = None,
        exclude_id: int | None = None,
    ) -> bool:
        """
        AU-04 closed-interval predicate:
            existing.start_time < new.end_time AND existing.end_time > new.start_time
        """
        return self._repo.has_overlapping_shift(
            start, end, user_id=user_id, exclude_id=exclude_id
        )

    def _write_audit(
        self,
        *,
        actor_id: int | None,
        action: str,
        target_id: int,
        before: dict | None,
        after: dict | None,
    ) -> None:
        """FR-05 / AU-07: write audit log entry inside the current transaction."""
        from app.models.audit_log import AuditLog  # local import avoids circular deps

        entry = AuditLog(
            actor_id=actor_id,
            action_type=action,
            target_table="shifts",
            target_id=target_id,
            before_state=before,
            after_state=after,
            occurred_at=datetime.now(timezone.utc),
        )
        self._db.add(entry)
        # flush so the entry is part of the same transaction commit
        self._db.flush()

    @staticmethod
    def _shift_dict(shift) -> dict:
        return {
            "id": shift.id,
            "title": shift.title,
            "start_time": shift.start_time.isoformat(),
            "end_time": shift.end_time.isoformat(),
            "department_id": shift.department_id,
            "headcount": shift.headcount,
        }
