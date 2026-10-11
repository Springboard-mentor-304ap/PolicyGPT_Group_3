import pytest
from pydantic import ValidationError

from backend.app.finder.schemas import ExtractedProfile


def test_extracted_profile_accepts_complete_profile():
    profile = ExtractedProfile(
        age=24,
        gender="male",
        annual_income=200000,
        occupation="student",
        education="undergraduate",
        state="Karnataka",
        district="Bengaluru",
        social_category="general",
        disability_status=False,
    )

    assert profile.age == 24
    assert profile.annual_income == 200000
    assert profile.occupation == "student"


def test_extracted_profile_allows_unknown_fields():
    profile = ExtractedProfile(
        age=24,
        gender=None,
        annual_income=None,
        occupation="student",
        education=None,
        state="Karnataka",
        district=None,
        social_category=None,
        disability_status=None,
    )

    assert profile.age == 24
    assert profile.gender is None
    assert profile.annual_income is None
    assert profile.district is None


def test_extracted_profile_rejects_invalid_age():
    with pytest.raises(ValidationError):
        ExtractedProfile(
            age=150,
            gender=None,
            annual_income=None,
            occupation=None,
            education=None,
            state=None,
            district=None,
            social_category=None,
            disability_status=None,
        )


def test_extracted_profile_rejects_extra_fields():
    with pytest.raises(ValidationError):
        ExtractedProfile(
            age=24,
            gender=None,
            annual_income=None,
            occupation=None,
            education=None,
            state=None,
            district=None,
            social_category=None,
            disability_status=None,
            unexpected_field="should fail",
        )