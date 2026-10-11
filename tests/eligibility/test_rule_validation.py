"""Unit tests for eligibility rule create/update validation.

Covers the two validation layers in ``backend.app.schemes.service``:

* the operator/parameter compatibility map (400 on any mismatched pair), and
* the comma-separated list format required by IN/NOT_IN rules.
"""

import pytest
from fastapi import HTTPException

from backend.app.models.eligibility_rule import (
    EligibilityOperator,
    EligibilityParameter,
)
from backend.app.schemes.service import (
    PARAMETER_OPERATOR_COMPATIBILITY,
    _validate_rule_operator,
    _validate_rule_value,
)


def test_compatibility_map_matches_the_intended_matrix():
    categorical = {
        EligibilityOperator.EQ,
        EligibilityOperator.NEQ,
        EligibilityOperator.IN,
        EligibilityOperator.NOT_IN,
    }
    numeric = {
        EligibilityOperator.EQ,
        EligibilityOperator.NEQ,
        EligibilityOperator.LT,
        EligibilityOperator.LTE,
        EligibilityOperator.GT,
        EligibilityOperator.GTE,
        EligibilityOperator.IN,
    }

    for parameter in (
        EligibilityParameter.GENDER,
        EligibilityParameter.STATE,
        EligibilityParameter.DISTRICT,
        EligibilityParameter.SOCIAL_CATEGORY,
        EligibilityParameter.OCCUPATION,
        EligibilityParameter.EDUCATION,
    ):
        assert set(PARAMETER_OPERATOR_COMPATIBILITY[parameter]) == categorical

    for parameter in (
        EligibilityParameter.AGE,
        EligibilityParameter.INCOME,
    ):
        assert set(PARAMETER_OPERATOR_COMPATIBILITY[parameter]) == numeric

    assert set(
        PARAMETER_OPERATOR_COMPATIBILITY[EligibilityParameter.DISABILITY_STATUS]
    ) == {EligibilityOperator.EQ, EligibilityOperator.NEQ}


def test_every_incompatible_pair_is_rejected_and_every_compatible_one_passes():
    """Exhaustive check: all 9 parameters x all 8 operators."""
    for parameter in EligibilityParameter:
        for operator in EligibilityOperator:
            allowed = (
                operator in PARAMETER_OPERATOR_COMPATIBILITY[parameter]
            )

            if allowed:
                _validate_rule_operator(parameter, operator)
            else:
                with pytest.raises(HTTPException) as exc_info:
                    _validate_rule_operator(parameter, operator)
                assert exc_info.value.status_code == 400
                assert parameter.value in exc_info.value.detail


def test_in_rule_value_requires_a_well_formed_list():
    # Normal path: a valid list is accepted and returned stripped.
    assert (
        _validate_rule_value(
            EligibilityParameter.GENDER,
            "male, female",
            EligibilityOperator.IN,
        )
        == "male, female"
    )
    assert (
        _validate_rule_value(
            EligibilityParameter.AGE, "18,20,22", EligibilityOperator.IN
        )
        == "18,20,22"
    )
    assert (
        _validate_rule_value(
            EligibilityParameter.INCOME,
            "100000, 200000",
            EligibilityOperator.NOT_IN,
        )
        == "100000, 200000"
    )

    for bad_value in ("18,,20", "18,", ",18"):
        with pytest.raises(HTTPException) as exc_info:
            _validate_rule_value(
                EligibilityParameter.AGE,
                bad_value,
                EligibilityOperator.IN,
            )
        assert exc_info.value.status_code == 400


def test_in_rule_value_entries_are_validated_per_parameter():
    with pytest.raises(HTTPException) as exc_info:
        _validate_rule_value(
            EligibilityParameter.AGE, "18,abc", EligibilityOperator.IN
        )
    assert exc_info.value.status_code == 400

    with pytest.raises(HTTPException):
        _validate_rule_value(
            EligibilityParameter.INCOME,
            "100000,abc",
            EligibilityOperator.IN,
        )

    with pytest.raises(HTTPException):
        _validate_rule_value(
            EligibilityParameter.GENDER,
            "male,alien",
            EligibilityOperator.IN,
        )


def test_single_value_operators_keep_their_existing_validation():
    assert (
        _validate_rule_value(
            EligibilityParameter.AGE, " 18 ", EligibilityOperator.GTE
        )
        == "18"
    )

    # A comma list is not a valid value for eq/neq.
    with pytest.raises(HTTPException) as exc_info:
        _validate_rule_value(
            EligibilityParameter.GENDER,
            "male,female",
            EligibilityOperator.EQ,
        )
    assert exc_info.value.status_code == 400

    with pytest.raises(HTTPException):
        _validate_rule_value(
            EligibilityParameter.AGE, "18.5", EligibilityOperator.LTE
        )

    with pytest.raises(HTTPException):
        _validate_rule_value(
            EligibilityParameter.DISABILITY_STATUS,
            "maybe",
            EligibilityOperator.EQ,
        )
