from types import SimpleNamespace
from uuid import uuid4
from unittest.mock import Mock

from backend.app.eligibility.schemas import EligibilityStatus
from backend.app.eligibility.service import EligibilityProfile
from backend.app.finder.match_service import match_profile_to_schemes
from backend.app.models.eligibility_rule import (
    EligibilityOperator,
    EligibilityParameter,
)
from backend.app.models.scheme import SchemeStatus


def make_scheme(title="Test Scheme"):
    return SimpleNamespace(
        id=uuid4(),
        title=title,
        status=SchemeStatus.ACTIVE,
    )


def make_rule(scheme_id, parameter, operator, value):
    return SimpleNamespace(
        id=uuid4(),
        scheme_id=scheme_id,
        parameter=parameter,
        operator=operator,
        value=value,
    )


def make_db(schemes, rules):
    db = Mock()

    schemes_result = Mock()
    schemes_result.scalars.return_value.all.return_value = schemes

    rules_result = Mock()
    rules_result.scalars.return_value.all.return_value = rules

    db.execute.side_effect = [
        schemes_result,
        rules_result,
    ]

    return db


def test_match_profile_returns_eligible():
    scheme = make_scheme("Student Support")
    rule = make_rule(
        scheme.id,
        EligibilityParameter.AGE,
        EligibilityOperator.GTE,
        "18",
    )

    db = make_db([scheme], [rule])

    profile = EligibilityProfile(age=24)

    response = match_profile_to_schemes(db, profile)

    assert len(response.eligible) == 1
    assert response.eligible[0].scheme_title == "Student Support"
    assert response.eligible[0].status == EligibilityStatus.ELIGIBLE


def test_match_profile_returns_more_information_required():
    scheme = make_scheme("Category Support")
    rule = make_rule(
        scheme.id,
        EligibilityParameter.SOCIAL_CATEGORY,
        EligibilityOperator.EQ,
        "st",
    )

    db = make_db([scheme], [rule])

    profile = EligibilityProfile(age=24)

    response = match_profile_to_schemes(db, profile)

    assert len(response.more_information_required) == 1
    assert (
        response.more_information_required[0].status
        == EligibilityStatus.MORE_INFORMATION_REQUIRED
    )
    assert response.more_information_required[0].missing_information == [
        "social_category"
    ]


def test_match_profile_returns_not_eligible():
    scheme = make_scheme("Senior Support")
    rule = make_rule(
        scheme.id,
        EligibilityParameter.AGE,
        EligibilityOperator.GTE,
        "60",
    )

    db = make_db([scheme], [rule])

    profile = EligibilityProfile(age=24)

    response = match_profile_to_schemes(db, profile)

    assert len(response.not_eligible) == 1
    assert response.not_eligible[0].status == EligibilityStatus.NOT_ELIGIBLE


def test_match_profile_returns_no_criteria_defined():
    scheme = make_scheme("Scheme Without Rules")

    db = make_db([scheme], [])

    profile = EligibilityProfile(age=24)

    response = match_profile_to_schemes(db, profile)

    assert len(response.no_criteria_defined) == 1
    assert response.no_criteria_defined[0].status == "no_criteria_defined"