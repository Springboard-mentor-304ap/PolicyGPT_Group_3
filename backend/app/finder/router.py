from fastapi import APIRouter

from backend.app.finder.schemas import ExtractedProfile, ProfileExtractionRequest
from backend.app.finder.service import extract_profile

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