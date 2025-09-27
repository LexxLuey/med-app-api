from fastapi import APIRouter

from shared.schemas import HealthCheck

router = APIRouter(
    tags=["Health"],
    responses={404: {"description": "Not found"}},
)


@router.get(
    "/health",
    response_model=HealthCheck,
    summary="Health check",
    description="Check the health status of the API.",
)
def health_check():
    return {"status": "healthy", "message": "API is running"}
