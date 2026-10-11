from datetime import date
from decimal import Decimal
from types import SimpleNamespace
from uuid import uuid4

from backend.app.eligibility.service import (
    EligibilityProfile,
    calculate_age,
    compare_values,
    evaluate_age_rule,
    evaluate_rule,
    evaluate_profile_against_rules,
)
from backend.app.models.eligibility_rule import (
    EligibilityOperator,
    EligibilityParameter,
)
from backend.app.eligibility.schemas import EligibilityStatus

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


# ─── Bug: IN and NOT_IN were defined but compared nothing ────────────────

def test_compare_values_covers_every_operator():
    assert compare_values("female", EligibilityOperator.EQ, "female") is True
    assert compare_values("female", EligibilityOperator.NEQ, "male") is True
    assert compare_values(17, EligibilityOperator.LT, 18) is True
    assert compare_values(18, EligibilityOperator.LTE, 18) is True
    assert compare_values(19, EligibilityOperator.GT, 18) is True
    assert compare_values(18, EligibilityOperator.GTE, 18) is True
    assert compare_values(20, EligibilityOperator.IN, "18,20") is True
    assert compare_values(20, EligibilityOperator.NOT_IN, "18,20") is False


def test_compare_values_in_is_case_insensitive_for_text():
    assert compare_values(
        "FEMALE", EligibilityOperator.IN, "female, other"
    ) is True
    assert compare_values(
        "male", EligibilityOperator.IN, "female, other"
    ) is False
    assert compare_values(
        " male ", EligibilityOperator.IN, "male"
    ) is True
    assert compare_values(
        "male", EligibilityOperator.NOT_IN, "female, other"
    ) is True
    assert compare_values(
        "other", EligibilityOperator.NOT_IN, "female, other"
    ) is False


def test_compare_values_in_is_numeric_for_numbers():
    assert compare_values(20, EligibilityOperator.IN, "18, 20, 22") is True
    assert compare_values(21, EligibilityOperator.IN, "18,20") is False
    assert compare_values(
        Decimal("300000"), EligibilityOperator.IN, "100000,300000"
    ) is True
    assert compare_values(
        Decimal("250000"), EligibilityOperator.NOT_IN, "100000,300000"
    ) is True
    assert compare_values(
        Decimal("300000"), EligibilityOperator.NOT_IN, "100000,300000"
    ) is False
    # A non-numeric entry simply never matches instead of raising.
    assert compare_values(20, EligibilityOperator.IN, "abc,20") is True
    assert compare_values(20, EligibilityOperator.IN, "abc") is False


def test_in_and_not_in_through_rule_evaluators():
    profile = EligibilityProfile(
        age=20,
        annual_income=Decimal("200000"),
        gender="male",
    )

    # Age used to crash on int("18,20") (500 for the whole check).
    age_rule = SimpleNamespace(
        parameter=EligibilityParameter.AGE,
        value="18,20,22",
        operator=EligibilityOperator.IN,
    )
    satisfied, message, actual = evaluate_rule(profile, age_rule)
    assert satisfied is True
    assert actual == "20"
    assert message

    age_rule.value = "18,22"
    satisfied, message, _ = evaluate_rule(profile, age_rule)
    assert satisfied is False
    assert message

    income_rule = SimpleNamespace(
        parameter=EligibilityParameter.INCOME,
        value="100000, 200000",
        operator=EligibilityOperator.IN,
    )
    satisfied, _, _ = evaluate_rule(profile, income_rule)
    assert satisfied is True

    gender_rule = SimpleNamespace(
        parameter=EligibilityParameter.GENDER,
        value="other",
        operator=EligibilityOperator.NOT_IN,
    )
    satisfied, _, _ = evaluate_rule(profile, gender_rule)
    assert satisfied is True

    gender_rule.value = "male,other"
    satisfied, _, _ = evaluate_rule(profile, gender_rule)
    assert satisfied is False


# ─── Bug: disability_status defaulted to False, never "missing" ──────────

def _disability_rule(operator=EligibilityOperator.EQ, value="true"):
    return SimpleNamespace(
        parameter=EligibilityParameter.DISABILITY_STATUS,
        value=value,
        operator=operator,
    )


def test_disability_status_none_is_missing_information():
    profile = EligibilityProfile(disability_status=None)

    satisfied, message, actual = evaluate_rule(profile, _disability_rule())

    assert satisfied is False
    assert message == "Disability status is required"
    assert actual is None

    scheme = SimpleNamespace(id=uuid4(), title="Disability Scheme")
    result = evaluate_profile_against_rules(
        profile, scheme, [_disability_rule()]
    )

    # An unanswered question is "more information required", not "not
    # eligible".
    assert result.status == EligibilityStatus.MORE_INFORMATION_REQUIRED
    assert result.missing_information == ["disability_status"]


def test_disability_status_false_is_a_definite_answer():
    profile = EligibilityProfile(disability_status=False)

    satisfied, _, actual = evaluate_rule(profile, _disability_rule())

    assert satisfied is False
    assert actual == "False"

    scheme = SimpleNamespace(id=uuid4(), title="Disability Scheme")
    age_rule = SimpleNamespace(
        parameter=EligibilityParameter.AGE,
        value="18",
        operator=EligibilityOperator.GTE,
    )
    # Age is missing, disability answered False: the definite failure wins
    # (precedence unchanged).
    result = evaluate_profile_against_rules(
        profile, scheme, [_disability_rule(), age_rule]
    )
    assert result.status == EligibilityStatus.NOT_ELIGIBLE


def test_disability_status_true_satisfies_the_rule():
    profile = EligibilityProfile(disability_status=True)

    satisfied, _, actual = evaluate_rule(profile, _disability_rule())

    assert satisfied is True
    assert actual == "True"

    scheme = SimpleNamespace(id=uuid4(), title="Disability Scheme")
    result = evaluate_profile_against_rules(
        profile, scheme, [_disability_rule()]
    )
    assert result.status == EligibilityStatus.ELIGIBLE


def test_disability_status_explicit_false_fails_a_not_disabled_rule():
    profile = EligibilityProfile(disability_status=False)

    satisfied, _, _ = evaluate_rule(
        profile, _disability_rule(value="false")
    )

    assert satisfied is True