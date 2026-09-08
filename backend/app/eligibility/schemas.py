from enum import Enum
from uuid import UUID

from pydantic import BaseModel, ConfigDict

class EligibilityStatus(str, Enum):
    ELIGIBLE = 'eligible'
    NOT_ELIGIBLE = 'not_eligible'
    MORE_INFORMATION_REQUIRED = "more_information_required"

class EligibilityRuleResult(BaseModel):
    parameter: str
    operator: str
    required_value:str
    actual_value: str | None
    satisfied: bool
    message: str

class EligibilityCheckResponse(BaseModel):
    scheme_id:UUID
    scheme_title: str
    status: EligibilityStatus
    summary: str
    rules: list[EligibilityRuleResult]
    missing_information: list[str] = []

    model_config = ConfigDict(from_attributes=True)

