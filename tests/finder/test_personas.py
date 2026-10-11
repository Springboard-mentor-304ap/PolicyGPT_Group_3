from uuid import uuid4
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import Mock

from backend.app.eligibility.service import EligibilityProfile
from backend.app.finder.match_service import match_profile_to_schemes
from backend.app.models.eligibility_rule import (
    EligibilityOperator,
    EligibilityParameter,
)
from backend.app.models.scheme import SchemeStatus


def make_scheme(title):
    return SimpleNamespace(
        id=uuid4(),
        title=title,
        status=SchemeStatus.ACTIVE,
    )


def make_rule(scheme_id, parameter, operator, value):
    return SimpleNamespace(
        scheme_id=scheme_id,
        parameter=parameter,
        operator=operator,
        value=value,
    )


def run_match(profile, schemes, rules):
    db = Mock()

    schemes_result = Mock()
    schemes_result.scalars.return_value.all.return_value = schemes

    rules_result = Mock()
    rules_result.scalars.return_value.all.return_value = rules

    db.execute.side_effect = [schemes_result, rules_result]

    return match_profile_to_schemes(db, profile)


def test_persona_young_karnataka_student():
    scheme = make_scheme("Student Scheme")
    rules = [
        make_rule(
            scheme.id,
            EligibilityParameter.AGE,
            EligibilityOperator.GTE,
            "18",
        ),
        make_rule(
            scheme.id,
            EligibilityParameter.INCOME,
            EligibilityOperator.LTE,
            "500000",
        ),
    ]

    profile = EligibilityProfile(
        age=24,
        annual_income=Decimal("200000"),
        occupation="student",
        state="Karnataka",
    )

    result = run_match(profile, [scheme], rules)

    assert len(result.eligible) == 1
    assert result.eligible[0].scheme_title == "Student Scheme"


def test_persona_low_income_karnataka():
    scheme = make_scheme("Housing Scheme")
    rules = [
        make_rule(
            scheme.id,
            EligibilityParameter.INCOME,
            EligibilityOperator.LTE,
            "300000",
        ),
        make_rule(
            scheme.id,
            EligibilityParameter.STATE,
            EligibilityOperator.EQ,
            "Karnataka",
        ),
    ]

    profile = EligibilityProfile(
        age=30,
        annual_income=Decimal("250000"),
        state="Karnataka",
    )

    result = run_match(profile, [scheme], rules)

    assert len(result.eligible) == 1


def test_persona_farmer_in_age_range():
    scheme = make_scheme("Farmer Scheme")
    rules = [
        make_rule(
            scheme.id,
            EligibilityParameter.AGE,
            EligibilityOperator.GTE,
            "18",
        ),
        make_rule(
            scheme.id,
            EligibilityParameter.AGE,
            EligibilityOperator.LTE,
            "40",
        ),
        make_rule(
            scheme.id,
            EligibilityParameter.OCCUPATION,
            EligibilityOperator.EQ,
            "farmer",
        ),
    ]

    profile = EligibilityProfile(
        age=40,
        occupation="farmer",
    )

    result = run_match(profile, [scheme], rules)

    assert len(result.eligible) == 1


def test_persona_missing_required_information():
    scheme = make_scheme("Education Scheme")
    rules = [
        make_rule(
            scheme.id,
            EligibilityParameter.AGE,
            EligibilityOperator.GTE,
            "18",
        ),
        make_rule(
            scheme.id,
            EligibilityParameter.EDUCATION,
            EligibilityOperator.EQ,
            "graduate",
        ),
    ]

    profile = EligibilityProfile(age=24)

    result = run_match(profile, [scheme], rules)

    assert len(result.more_information_required) == 1
    assert "education" in result.more_information_required[0].missing_information


def test_persona_wrong_occupation():
    scheme = make_scheme("Business Scheme")
    rules = [
        make_rule(
            scheme.id,
            EligibilityParameter.AGE,
            EligibilityOperator.GTE,
            "18",
        ),
        make_rule(
            scheme.id,
            EligibilityParameter.OCCUPATION,
            EligibilityOperator.EQ,
            "self-employed",
        ),
    ]

    profile = EligibilityProfile(
        age=30,
        occupation="student",
    )

    result = run_match(profile, [scheme], rules)

    assert len(result.not_eligible) == 1


def test_persona_wrong_state():
    scheme = make_scheme("Gujarat Scheme")
    rules = [
        make_rule(
            scheme.id,
            EligibilityParameter.STATE,
            EligibilityOperator.EQ,
            "Gujarat",
        ),
    ]

    profile = EligibilityProfile(
        age=30,
        state="Karnataka",
    )

    result = run_match(profile, [scheme], rules)

    assert len(result.not_eligible) == 1


def test_persona_income_boundary_is_eligible():
    scheme = make_scheme("Income Scheme")
    rules = [
        make_rule(
            scheme.id,
            EligibilityParameter.INCOME,
            EligibilityOperator.LTE,
            "300000",
        ),
    ]

    profile = EligibilityProfile(
        annual_income=Decimal("300000"),
    )

    result = run_match(profile, [scheme], rules)

    assert len(result.eligible) == 1


def test_persona_income_above_boundary_is_not_eligible():
    scheme = make_scheme("Income Scheme")
    rules = [
        make_rule(
            scheme.id,
            EligibilityParameter.INCOME,
            EligibilityOperator.LTE,
            "300000",
        ),
    ]

    profile = EligibilityProfile(
        annual_income=Decimal("300001"),
    )

    result = run_match(profile, [scheme], rules)

    assert len(result.not_eligible) == 1