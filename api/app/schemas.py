from pydantic import BaseModel
from datetime import datetime


class ProjectSummary(BaseModel):
    id: str
    title: str
    window: str | None = None
    shoot_days: int
    created_at: datetime

    class Config:
        from_attributes = True


class ProjectDetail(ProjectSummary):
    unit_cols: list[str] = []
    total_days: int = 0


class DayOut(BaseModel):
    date_raw: str
    day_label: str
    is_shoot: bool
    shoot_day_no: int | None = None
    location: str = ""
    film_location: str = ""
    shift: str = ""
    cast: list[str] = []
    supporting_cast: list[str] = []
    picture_vehicles: list[str] = []
    extras: str = ""
    notes: str = ""
    units: dict[str, float] = {}


class MainScheduleView(BaseModel):
    project_id: str
    title: str
    window: str | None
    days: list[DayOut]
