from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from backend.app.db.database import get_db
from backend.app.finder.schemas import ExtractedProfile, ProfileExtractionRequest, SchemeMatchRequest, SchemeMatchResponse
from backend.app.finder.service import extract_profile, extracted_to_eligibility_profile
from backend.app.finder.match_service import match_profile_to_schemes

router = APIRouter(
    prefix="/finder",
    tags=["Finder"],
)

@router.post(
    "/extract",
    response_model=ExtractedProfile,
)
def extract_profile_endpoint(
    request: ProfileExtractionRequest,
) -> ExtractedProfile:
    return extract_profile(request.text)

@router.post(
    "/match",
    response_model=SchemeMatchResponse,
)
def match_profile_endpoint(
    request: SchemeMatchRequest,
    db: Session = Depends(get_db),
) -> SchemeMatchResponse:
    profile = extracted_to_eligibility_profile(request.profile)

    return match_profile_to_schemes(
        db=db,
        profile=profile,
    )