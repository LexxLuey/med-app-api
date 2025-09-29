from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from auth.router import get_current_user
from shared.database import get_db
from shared.schemas import Claim, ClaimCreate

from .services import create_claim as create_claim_service
from .services import delete_claim as delete_claim_service
from .services import get_claim as get_claim_service
from .services import get_claims as get_claims_service
from .services import update_claim as update_claim_service

router = APIRouter(
    prefix="/api/v1/claims",
    tags=["Claims"],
    responses={404: {"description": "Not found"}},
)


@router.post(
    "/",
    response_model=Claim,
    summary="Create a new claim",
    description="Create a new claim with the provided data.",
)
def create_claim(
    claim: ClaimCreate, db: Session = Depends(get_db), current_user=Depends(get_current_user)
):
    db_claim = get_claim_service(db, claim_id=claim.claim_id)
    if db_claim:
        raise HTTPException(status_code=400, detail="Claim already exists")
    return create_claim_service(db=db, claim=claim)


@router.get(
    "/",
    response_model=list[Claim],
    summary="List claims",
    description="Retrieve a list of claims with pagination.",
)
def read_claims(
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    claims = get_claims_service(db, skip=skip, limit=limit)
    return claims


@router.get(
    "/{claim_id}",
    response_model=Claim,
    summary="Get claim by ID",
    description="Retrieve a specific claim by its ID.",
)
def read_claim(
    claim_id: str, db: Session = Depends(get_db), current_user=Depends(get_current_user)
):
    db_claim = get_claim_service(db, claim_id=claim_id)
    if db_claim is None:
        raise HTTPException(status_code=404, detail="Claim not found")
    return db_claim


@router.put(
    "/{claim_id}",
    response_model=Claim,
    summary="Update claim",
    description="Update an existing claim with new data.",
)
def update_claim(
    claim_id: str,
    claim: ClaimCreate,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    db_claim = update_claim_service(db, claim_id=claim_id, claim=claim)
    if db_claim is None:
        raise HTTPException(status_code=404, detail="Claim not found")
    return db_claim


@router.delete("/{claim_id}", summary="Delete claim", description="Delete a claim by its ID.")
def delete_claim_endpoint(
    claim_id: str, db: Session = Depends(get_db), current_user=Depends(get_current_user)
):
    db_claim = delete_claim_service(db, claim_id=claim_id)
    if db_claim is None:
        raise HTTPException(status_code=404, detail="Claim not found")
    return {"message": "Claim deleted"}
