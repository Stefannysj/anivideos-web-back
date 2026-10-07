from datetime import date, timedelta

from fastapi import APIRouter, Query

from app.database import list_season_calendar, list_weekly_calendar
from app.schemas import (
    CalendarEntryResponse,
    ContentItemResponse,
    SeasonCalendarResponse,
    SeasonName,
    WeeklyCalendarResponse,
)

router = APIRouter()


def _monday_for(value: date) -> date:
    return value - timedelta(days=value.weekday())


@router.get('/calendar/week', response_model=WeeklyCalendarResponse)
def weekly_calendar(
    week_start: date | None = Query(default=None, alias='weekStart'),
) -> WeeklyCalendarResponse:
    resolved = _monday_for(week_start or date.today())
    items = [CalendarEntryResponse(**entry) for entry in list_weekly_calendar(resolved)]
    return WeeklyCalendarResponse(week_start=resolved.isoformat(), items=items)


@router.get('/calendar/season', response_model=SeasonCalendarResponse)
def season_calendar(
    season: SeasonName = Query(),
    year: int = Query(ge=1900, le=2200),
) -> SeasonCalendarResponse:
    items = [ContentItemResponse(**item) for item in list_season_calendar(season, year)]
    return SeasonCalendarResponse(season=season, year=year, items=items)
