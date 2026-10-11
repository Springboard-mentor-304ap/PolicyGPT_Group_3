from unittest.mock import patch

from backend.app.finder.schemas import ExtractedProfile
from backend.app.finder.service import extract_profile


def mock_extraction(profile: ExtractedProfile):
    return patch(
        "backend.app.finder.service.LLMClient.generate_structured",
        return_value=profile,
    )


def test_extract_profile_extracts_explicit_information():
    expected = ExtractedProfile(
        age=24,
        gender=None,
        annual_income=200000,
        occupation="student",
        education=None,
        state="Karnataka",
        district=None,
        social_category=None,
        disability_status=None,
    )

    with mock_extraction(expected):
        result = extract_profile(
            "I am 24 years old, live in Karnataka, earn 2 lakh per year and I am a student."
        )

    assert result == expected


def test_extract_profile_keeps_missing_information_null():
    expected = ExtractedProfile(
        age=24,
        gender=None,
        annual_income=None,
        occupation="student",
        education=None,
        state=None,
        district=None,
        social_category=None,
        disability_status=None,
    )

    with mock_extraction(expected):
        result = extract_profile("I am 24 years old and I am a student.")

    assert result.age == 24
    assert result.occupation == "student"
    assert result.annual_income is None
    assert result.state is None
    assert result.gender is None


def test_extract_profile_handles_monthly_income_as_annual():
    expected = ExtractedProfile(
        age=30,
        gender=None,
        annual_income=300000,
        occupation="software engineer",
        education=None,
        state=None,
        district=None,
        social_category=None,
        disability_status=None,
    )

    with mock_extraction(expected):
        result = extract_profile(
            "I am 30 years old, work as a software engineer and earn 25,000 rupees per month."
        )

    assert result.annual_income == 300000


def test_extract_profile_handles_lakh_income():
    expected = ExtractedProfile(
        age=25,
        gender=None,
        annual_income=250000,
        occupation=None,
        education=None,
        state=None,
        district=None,
        social_category=None,
        disability_status=None,
    )

    with mock_extraction(expected):
        result = extract_profile("I am 25 and my annual income is 2.5 lakh.")

    assert result.annual_income == 250000


def test_extract_profile_extracts_state_and_district():
    expected = ExtractedProfile(
        age=None,
        gender=None,
        annual_income=None,
        occupation=None,
        education=None,
        state="Karnataka",
        district="Bengaluru",
        social_category=None,
        disability_status=None,
    )

    with mock_extraction(expected):
        result = extract_profile("I live in Bengaluru, Karnataka.")

    assert result.state == "Karnataka"
    assert result.district == "Bengaluru"


def test_extract_profile_extracts_disability_when_explicit():
    expected = ExtractedProfile(
        age=40,
        gender=None,
        annual_income=None,
        occupation=None,
        education=None,
        state=None,
        district=None,
        social_category=None,
        disability_status=True,
    )

    with mock_extraction(expected):
        result = extract_profile(
            "I am 40 years old and I have a disability."
        )

    assert result.disability_status is True


def test_extract_profile_does_not_invent_missing_attributes():
    expected = ExtractedProfile(
        age=24,
        gender=None,
        annual_income=None,
        occupation="student",
        education=None,
        state=None,
        district=None,
        social_category=None,
        disability_status=None,
    )

    with mock_extraction(expected):
        result = extract_profile("I am 24 and I am a student.")

    assert result.gender is None
    assert result.education is None
    assert result.state is None
    assert result.social_category is None
    assert result.disability_status is None
