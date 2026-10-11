from decimal import Decimal

from backend.app.finder.schemas import ExtractedProfile
from backend.app.ai.llm_client import LLMClient
from backend.app.eligibility.service import EligibilityProfile




def extracted_to_eligibility_profile(
    profile: ExtractedProfile,
) -> EligibilityProfile:
    return EligibilityProfile(
        age=profile.age,
        gender=profile.gender,
        annual_income=(
            Decimal(str(profile.annual_income))
            if profile.annual_income is not None
            else None
        ),
        occupation=profile.occupation,
        education=profile.education,
        state=profile.state,
        district=profile.district,
        social_category=profile.social_category,
        disability_status=profile.disability_status,
    )

EXTRACTION_SYSTEM_PROMPT = """
You are a profile information extraction system for a government scheme discovery platform.

Your job is ONLY to extract profile information explicitly stated or clearly implied by the user's message.

Rules:
- Never guess missing information.
- Use null for information that is not provided.
- Convert income amounts into annual numeric income.
- Examples: 
    - "2 lakh" -> 200000
    - "2.5 lakh" -> 250000
    ' "3 crore" -> 30000000
- If the user provides monthly income, convert it into annual income.
- Extract age directly when given.
- Extract state and district separately when possible.
- Preserve the user's meaning for occupation and education.
- Convert disability information to true/false only when clearly stated.
- Do not determine scheme eligibility.
- Do not recommend schemes.
- Do not infer sensitive attributes that the user did not provide.
"""

def extract_profile(text: str) -> ExtractedProfile:
    client = LLMClient()

    return client.generate_structured(
        system_prompt=EXTRACTION_SYSTEM_PROMPT,
        user_prompt=text,
        response_model=ExtractedProfile,
    )