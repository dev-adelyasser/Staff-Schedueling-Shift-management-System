from datetime import datetime
from pydantic import BaseModel, model_validator

def _parse_datetime(val: Any) -> datetime | None:
    if isinstance(val, datetime):
        return val
    if isinstance(val, str):
        try:
            # Handle standard ISO formats (including trailing Z)
            return datetime.fromisoformat(val.replace("Z", "+00:00"))
        except ValueError:
            return None
    return None

class ShiftCreate(BaseModel):
    """Spec section 10: exactly these 5 fields. User assignment is a separate endpoint."""
    title: str
    start_time: datetime
    end_time: datetime
    department_id: int
    headcount: int = 1

    @model_validator(mode="before")  # spec: mode='before' to catch errors early
    @classmethod
    def end_after_start(cls, values: Any) -> Any:
        if not isinstance(values, dict):
            return values
            
        start_val = values.get("start_time")
        end_val = values.get("end_time")
        
        start = _parse_datetime(start_val)
        end = _parse_datetime(end_val)
        
        if start and end and end <= start:
            raise ValueError("end_time must be after start_time")
        return values


class ShiftUpdate(BaseModel):
    title: str | None = None
    start_time: datetime | None = None
    end_time: datetime | None = None
    department_id: int | None = None
    headcount: int | None = None

    @model_validator(mode="before")
    @classmethod
    def end_after_start(cls, values: Any) -> Any:
        if not isinstance(values, dict):
            return values
            
        start_val = values.get("start_time")
        end_val = values.get("end_time")
        
        start = _parse_datetime(start_val)
        end = _parse_datetime(end_val)
        
        if start and end and end <= start:
            raise ValueError("end_time must be after start_time")
        return values


class ShiftResponse(BaseModel):
    id: int
    title: str
    start_time: datetime
    end_time: datetime
    department_id: int
    headcount: int
    is_deleted: bool
    created_by: int | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class ShiftAssign(BaseModel):
    """POST /shifts/{id}/assign — user assignment is separate from creation."""
    user_id: int
