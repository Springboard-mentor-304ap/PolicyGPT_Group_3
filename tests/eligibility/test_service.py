from datetime import date
from types import SimpleNamespace

from backend.app.eligibility.service import (
    EligibilityProfile,
    calculate_age,
    evaluate_age_rule,
)
from backend.app.models.eligibility_rule import EligibilityOperator

def test_calculate_age():
    today = date.today()
    dob = date(today.year - 22, today.month, today.day)

    assert calculate_age(dob) == 22

def test_evaluate_age_rule():
    profile = EligibilityProfile(age=22)

    rule = SimpleNamespace(
        value="18",
        operator=EligibilityOperator.GTE,
    )

    satisfied, message = evaluate_age_rule(profile, rule)

    assert satisfied is True
    assert message

def test_evaluate_age_rule_missing_age():
    profile = EligibilityProfile(age=None)

    rule = SimpleNamespace(
        value="18",
        operator=EligibilityOperator.GTE,
    )

    satisfied, message = evaluate_age_rule(profile, rule)

    assert satisfied is False
    assert message == "Age is required"

def test_eligibility_profile():
    profile = EligibilityProfile(
        age=22,
        gender="male",
        annual_income=200000,
        state="karnataka",
    )

    assert profile.age == 22
    assert profile.gender == "male"
    assert profile.annual_income == 200000
    assert profile.state == "karnataka"