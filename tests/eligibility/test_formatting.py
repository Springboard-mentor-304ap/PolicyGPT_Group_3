"""Tests for the shared human-readable eligibility rule formatter.

The comparison endpoint and the AI knowledge ingestion both render rules
through ``format_rule``; these tests pin its wording.
"""

from backend.app.eligibility.formatting import format_rule
from backend.app.models.eligibility_rule import (
    EligibilityOperator,
    EligibilityParameter,
)


def test_format_rule_matches_the_documented_examples():
    assert (
        format_rule(
            EligibilityParameter.AGE, EligibilityOperator.GTE, "18"
        )
        == "Age: 18 or above"
    )
    assert (
        format_rule(
            EligibilityParameter.INCOME, EligibilityOperator.LT, "300000"
        )
        == "Income: below 300000"
    )
    assert (
        format_rule(
            EligibilityParameter.GENDER, EligibilityOperator.EQ, "female"
        )
        == "Gender: female"
    )


def test_format_rule_covers_every_operator():
    assert (
        format_rule(EligibilityParameter.GENDER, EligibilityOperator.NEQ, "other")
        == "Gender: not other"
    )
    assert (
        format_rule(EligibilityParameter.AGE, EligibilityOperator.LTE, "18")
        == "Age: 18 or below"
    )
    assert (
        format_rule(EligibilityParameter.AGE, EligibilityOperator.GT, "18")
        == "Age: above 18"
    )
    assert (
        format_rule(
            EligibilityParameter.STATE,
            EligibilityOperator.IN,
            "karnataka,maharashtra",
        )
        == "State: one of karnataka, maharashtra"
    )
    assert (
        format_rule(
            EligibilityParameter.GENDER,
            EligibilityOperator.NOT_IN,
            "male, female",
        )
        == "Gender: not one of male, female"
    )


def test_format_rule_accepts_raw_strings_and_labels_multiword_parameters():
    assert (
        format_rule("social_category", "eq", "obc")
        == "Social category: obc"
    )
    assert (
        format_rule("disability_status", "eq", "true")
        == "Disability status: true"
    )
    # Unknown operator: readable fallback, never a crash.
    assert format_rule("age", "between", "18") == "Age: between 18"
