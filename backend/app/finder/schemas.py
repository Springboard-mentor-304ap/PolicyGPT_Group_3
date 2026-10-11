from typing import Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from backend.app.eligibility.schemas import (
    EligibilityRuleResult,
    EligibilityStatus,
)


class ExtractedProfile(BaseModel):
    model_config = ConfigDict(extra="forbid")

    age: Optional[int] = Field(ge=0, le=120)
    gender: Optional[str]
    annual_income: Optional[float] = Field(ge=0)
    occupation: Optional[str]
    education: Optional[str]
    state: Optional[str]
    district: Optional[str]
    social_category: Optional[str]
    disability_status: Optional[bool]


class ProfileExtractionRequest(BaseModel):
    text: str = Field(min_length=1, max_length=5000)


class SchemeMatchRequest(BaseModel):
    profile: ExtractedProfile


class SchemeMatch(BaseModel):
    scheme_id: UUID
    scheme_title: str
    status: EligibilityStatus | str
    summary: str
    rules: list[EligibilityRuleResult]
    missing_information: list[str]


class SchemeMatchResponse(BaseModel):
    eligible: list[SchemeMatch]
    more_information_required: list[SchemeMatch]
    not_eligible: list[SchemeMatch]
    no_criteria_defined: list[SchemeMatch]