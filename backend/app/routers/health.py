from fastapi import APIRouter, HTTPException, status

from app.database import database_is_healthy
from app.schemas import HealthResponse

router = APIRouter()


@router.get('/health', response_model=HealthResponse)
def health() -> HealthResponse:
    if not database_is_healthy():
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail='Database unavailable')
    return HealthResponse(
        status='ok',
        service='anivideos-api',
        database='ok',
        database_engine='sqlite',
    )
