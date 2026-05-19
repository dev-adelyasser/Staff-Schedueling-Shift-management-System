"""
app/services/shift_service.py
──────────────────────────────
Business logic for the Shift slice.

Contracts:
  - Every method converts ORM → schema before returning (DetachedInstanceError prevention).
  - Audit log is written in the SAME flush cycle as the write (AU-07).
  - check_overlap() → single DB round-trip via AssignmentRepository (AU-04).
  - 503 on OperationalError is handled by the exception middleware in main.py;
    services raise the raw SQLAlchemy error so the handler can inspect it.
"""

import csv
import io
import uuid
from datetime import datetime
from typing import Any

import sqlalchemy.exc
from sqlalchemy.orm import Session

from app.models.audit_log import AuditActionType
from app.repositories.assignment_repository import AssignmentRepository
from app.repositories.audit_log_repository import AuditLogRepository
from app.repositories.shift_repository import ShiftRepository
from app.schemas.shift import (
    BulkUploadResultSchema,
    ShiftCreateSchema,
    ShiftListResponseSchema,
    ShiftResponseSchema,
)


class ShiftConflictError(Exception):
    pass


class ShiftNotFoundError(Exception):
    pass


class ShiftService:
    def __init__(self, db: Session) -> None:
        self._db = db
        self._shifts = ShiftRepository(db)
        self._assignments = AssignmentRepository(db)
        self._audit = AuditLogRepository(db)

    # ── Queries ────────────────────────────────────────────────────────── #

    def get_shift(self, shift_id: uuid.UUID) -> ShiftResponseSchema:
        shift = self._shifts.get(shift_id)
        if shift is None or shift.is_deleted:
            raise ShiftNotFoundError(str(shift_id))
        return ShiftResponseSchema.model_validate(shift)

    def list_shifts(
        self,
        *,
        skip: int = 0,
        limit: int = 100,
        department_id: int | None = None,
    ) -> ShiftListResponseSchema:
        rows, total = self._shifts.list(
            skip=skip, limit=limit, department_id=department_id
        )
        return ShiftListResponseSchema(
            items=[ShiftResponseSchema.model_validate(r) for r in rows],
            total=total,
            skip=skip,
            limit=limit,
        )

    # ── Create ─────────────────────────────────────────────────────────── #

    def create_shift(
        self,
        payload: ShiftCreateSchema,
        *,
        actor_id: int,
    ) -> ShiftResponseSchema:
        shift = self._shifts.create(payload, created_by=actor_id)

        # AU-07: audit log in the SAME transaction as the INSERT
        self._audit.record(
            actor_id=actor_id,
            action_type=AuditActionType.CREATE,
            target_table="shifts",
            target_id=shift.id,
            before_state=None,
            after_state=self._shift_snapshot(shift),
        )

        return ShiftResponseSchema.model_validate(shift)

    # ── Assign staff to shift ──────────────────────────────────────────── #

    def assign_staff(
        self,
        shift_id: uuid.UUID,
        staff_id: int,
        *,
        actor_id: int,
    ) -> ShiftResponseSchema:
        shift = self._shifts.get(shift_id)
        if shift is None or shift.is_deleted:
            raise ShiftNotFoundError(str(shift_id))

        # AU-04: overlap check — single DB round-trip, filtered on staff_id index
        if self._assignments.has_overlapping_assignment(
            staff_id, shift.start_time, shift.end_time,
            exclude_shift_id=shift_id,
        ):
            raise ShiftConflictError(
                f"Staff {staff_id} already has an overlapping shift assignment"
            )

        before = self._shift_snapshot(shift)
        assignment = self._assignments.create(
            shift_id, staff_id, assigned_by=actor_id
        )

        self._audit.record(
            actor_id=actor_id,
            action_type=AuditActionType.UPDATE,
            target_table="shifts",
            target_id=shift_id,
            before_state=before,
            after_state={**before, "assigned_staff_id": staff_id},
        )

        return ShiftResponseSchema.model_validate(shift)

    # ── Bulk CSV upload ────────────────────────────────────────────────── #

    def bulk_upload(
        self,
        csv_content: str,
        *,
        actor_id: int,
    ) -> BulkUploadResultSchema:
        """
        POST /api/v1/shifts/bulk-upload.

        CSV columns (in order): title, start_time, end_time, department_id, headcount
        Returns 201 (all created), 207 (partial), 400 (unparseable CSV), 422 (empty).
        HTTP status selection is the router's responsibility.
        """
        created: list[ShiftResponseSchema] = []
        errors: list[dict[str, Any]] = []

        try:
            reader = csv.DictReader(io.StringIO(csv_content))
            rows = list(reader)
        except Exception as exc:
            raise ValueError(f"Could not parse CSV: {exc}") from exc

        for row_idx, raw in enumerate(rows, start=2):  # row 1 = header
            try:
                payload = ShiftCreateSchema(
                    title=raw["title"].strip(),
                    start_time=raw["start_time"].strip(),
                    end_time=raw["end_time"].strip(),
                    department_id=int(raw["department_id"]),
                    headcount=int(raw.get("headcount", 1)),
                )
                result = self.create_shift(payload, actor_id=actor_id)
                created.append(result)
            except Exception as exc:
                errors.append({"row": row_idx, "data": dict(raw), "error": str(exc)})

        return BulkUploadResultSchema(created=created, errors=errors)

    # ── Private ────────────────────────────────────────────────────────── #

    @staticmethod
    def _shift_snapshot(shift) -> dict[str, Any]:
        return {
            "id": str(shift.id),
            "title": shift.title,
            "start_time": shift.start_time.isoformat(),
            "end_time": shift.end_time.isoformat(),
            "department_id": shift.department_id,
            "headcount": shift.headcount,
        }
