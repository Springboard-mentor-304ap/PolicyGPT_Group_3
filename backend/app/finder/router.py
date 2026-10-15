from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from backend.app.ai.quota import FEATURE_FINDER_EXTRACT, consume_llm_quota
from backend.app.auth.dependencies import get_current_user
from backend.app.db.database import get_db
from backend.app.finder.schemas import ExtractedProfile, ProfileExtractionRequest, SchemeMatchRequest, SchemeMatchResponse
from backend.app.finder.service import extract_profile, extracted_to_eligibility_profile
from backend.app.finder.match_service import match_profile_to_schemes
from backend.app.models.user import User

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
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ExtractedProfile:
    # /extract calls the Groq LLM, so it is metered against the caller's
    # daily quota before the call is made. /match below is deterministic and
    # only needs authentication.
    consume_llm_quota(
        db,
        user_id=current_user.id,
        feature=FEATURE_FINDER_EXTRACT,
    )

    return extract_profile(request.text)

@router.post(
    "/match",
    response_model=SchemeMatchResponse,
)
def match_profile_endpoint(
    request: SchemeMatchRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> SchemeMatchResponse:
    profile = extracted_to_eligibility_profile(request.profile)

    return match_profile_to_schemes(
        db=db,
        profile=profile,
    )
