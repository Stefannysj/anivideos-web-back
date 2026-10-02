from fastapi import APIRouter, HTTPException, status

from app.database import database_is_healthy
from app.schemas import HealthResponse

router = APIRouter()


@router.get('/health', response_model=HealthResponse)
def health() -> HealthResponse:
    # Dependency health is checked internally without exposing the database engine.
    if not database_is_healthy():
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail='Service unavailable')
    return HealthResponse(status='ok', service='anivideos-api')
