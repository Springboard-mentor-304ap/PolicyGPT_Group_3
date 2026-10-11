from uuid import UUID
from datetime import date
from decimal import Decimal, InvalidOperation
from dataclasses import dataclass
from typing import Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.models.user import User
from backend.app.models.user_profile import UserProfile
from backend.app.models.scheme import Scheme
from backend.app.models.eligibility_rule import EligibilityRule, EligibilityOperator, EligibilityParameter
# The eligibility check returns the scheme's rules, so it has to apply the
# same visibility rules as reading the scheme itself (shared with the
# scheme detail and eligibility-rules endpoints).
from backend.app.schemes.service import _assert_scheme_is_visible

from backend.app.eligibility.schemas import (
    EligibilityCheckResponse,
    EligibilityStatus
)

@dataclass
class EligibilityProfile:
    age: Optional[int] = None
    gender: Optional[str] = None
    annual_income: Optional[Decimal] = None
    occupation: Optional[str] = None
    education: Optional[str] = None
    state: Optional[str] = None
    district: Optional[str] = None
    social_category: Optional[str] = None
    disability_status: Optional[bool] = None

def calculate_age(date_of_birth: date) -> int:
    today = date.today()

    age = today.year - date_of_birth.year

    if (today.month, today.day) < (date_of_birth.month, date_of_birth.day):
        age -= 1

    return age

def _split_rule_list(expected) -> list[str]:
    """Split a rule's comma-separated list value into its entries.

    ``expected`` is the raw rule value (a string); entries are trimmed and
    blank entries are dropped so a malformed legacy value degrades instead of
    raising.
    """
    if isinstance(expected, str):
        parts = expected.split(",")
    elif isinstance(expected, (list, tuple, set)):
        parts = [str(item) for item in expected]
    else:
        parts = [str(expected)]

    return [part.strip() for part in parts if part.strip()]


def _value_matches_list(actual, items: list[str]) -> bool:
    """Membership test: numeric for numeric values, case-insensitive text.

    ``None`` matches nothing, so the callers that treat ``None`` as missing
    information are never bypassed by a list rule.
    """
    if actual is None:
        return False

    # bool is a subclass of int; compare it as text instead of as a number.
    if isinstance(actual, bool):
        haystack = str(actual).lower()
        return any(haystack == item.lower() for item in items)

    if isinstance(actual, (Decimal, int, float)):
        actual_number = Decimal(str(actual))
        for item in items:
            try:
                if actual_number == Decimal(item):
                    return True
            except InvalidOperation:
                continue
        return False

    haystack = str(actual).strip().lower()
    return any(haystack == item.lower() for item in items)


def compare_values(
        actual,
        operator: EligibilityOperator,
        expected,
) -> bool:

    if operator == EligibilityOperator.EQ:
        return actual == expected

    if operator == EligibilityOperator.NEQ:
        return actual != expected

    if operator == EligibilityOperator.LT:
        return actual < expected

    if operator == EligibilityOperator.LTE:
        return actual <= expected

    if operator == EligibilityOperator.GT:
        return actual > expected

    if operator == EligibilityOperator.GTE:
        return actual >= expected

    if operator == EligibilityOperator.IN:
        return _value_matches_list(actual, _split_rule_list(expected))

    if operator == EligibilityOperator.NOT_IN:
        return not _value_matches_list(actual, _split_rule_list(expected))

    return False


def evaluate_age_rule(profile: EligibilityProfile, rule):
    if profile.age is None:
        return False, "Age is required"

    # IN/NOT_IN values are comma-separated lists that compare_values parses;
    # the single-value operators need one number.
    if rule.operator in (
        EligibilityOperator.IN,
        EligibilityOperator.NOT_IN,
    ):
        expected = rule.value
    else:
        expected = int(rule.value)

    actual_age = profile.age

    satisfied = compare_values(actual_age, rule.operator, expected)

    message = (
        f"Age must be {rule.operator.value} {expected}"
        if not satisfied
        else f"Age satisfies {rule.operator.value} {expected}"
    )

    return satisfied, message

def evaluate_gender_rule(
        profile: EligibilityProfile,
        rule: EligibilityRule,
) -> tuple[bool, str]:

    if profile.gender is None:
        return False, "Gender is required"

    actual_gender = profile.gender.lower()
    expected_gender = rule.value.lower()

    satisfied = compare_values(
        actual_gender,
        rule.operator,
        expected_gender,
    )

    if satisfied:
        message = (
            f"Gender requirement satisfied: "
            f"{actual_gender} matches {expected_gender}"
        )
    else:
        message = (
            f"Gender requirement not satisfied: "
            f"{actual_gender} does not match {expected_gender}"
        )

    return satisfied, message

def evaluate_income_rule(
    profile: EligibilityProfile,
    rule: EligibilityRule,
) -> tuple[bool, str]:

    if profile.annual_income is None:
        return False, "Annual income is required"

    actual_income = profile.annual_income

    # IN/NOT_IN values are comma-separated lists that compare_values parses
    # numerically; the single-value operators need one amount.
    if rule.operator in (
        EligibilityOperator.IN,
        EligibilityOperator.NOT_IN,
    ):
        expected = rule.value
    else:
        expected = Decimal(rule.value)

    satisfied = compare_values(
        actual_income,
        rule.operator,
        expected,
    )

    if satisfied:
        message = (
            f"Income requirement satisfied: "
            f"{actual_income} {rule.operator.value} {expected}"
        )
    else:
        message = (
            f"Income requirement not satisfied: "
            f"{actual_income} {rule.operator.value} {expected}"
        )

    return satisfied, message

def evaluate_occupation_rule(
    profile: EligibilityProfile,
    rule: EligibilityRule,
) -> tuple[bool, str]:

    if profile.occupation is None:
        return False, "Occupation is required"

    actual_occupation = profile.occupation.lower()
    expected_occupation = rule.value.lower()

    satisfied = compare_values(
        actual_occupation,
        rule.operator,
        expected_occupation,
    )

    if satisfied:
        message = (
            f"Occupation requirement satisfied: "
            f"{actual_occupation} matches {expected_occupation}"
        )
    else:
        message = (
            f"Occupation requirement not satisfied: "
            f"{actual_occupation} does not match {expected_occupation}"
        )

    return satisfied, message

def evaluate_education_rule(
    profile: EligibilityProfile,
    rule: EligibilityRule,
) -> tuple[bool, str]:

    if profile.education is None:
        return False, "Education is required"

    actual_education = profile.education.lower()
    expected_education = rule.value.lower()

    satisfied = compare_values(
        actual_education,
        rule.operator,
        expected_education,
    )

    if satisfied:
        message = (
            f"Education requirement satisfied: "
            f"{actual_education} matches {expected_education}"
        )
    else:
        message = (
            f"Education requirement not satisfied: "
            f"{actual_education} does not match {expected_education}"
        )

    return satisfied, message

def evaluate_location_rule(
    profile: EligibilityProfile,
    rule: EligibilityRule,
) -> tuple[bool, str]:

    if rule.parameter == EligibilityParameter.STATE:
        actual_location = profile.state
        location_name = "State"

    elif rule.parameter == EligibilityParameter.DISTRICT:
        actual_location = profile.district
        location_name = "District"

    else:
        return False, "Invalid location parameter"

    if actual_location is None:
        return False, f"{location_name} is required"

    actual_location = actual_location.lower()
    expected_location = rule.value.lower()

    satisfied = compare_values(
        actual_location,
        rule.operator,
        expected_location,
    )

    if satisfied:
        message = (
            f"{location_name} requirement satisfied: "
            f"{actual_location} matches {expected_location}"
        )
    else:
        message = (
            f"{location_name} requirement not satisfied: "
            f"{actual_location} does not match {expected_location}"
        )

    return satisfied, message

def evaluate_social_category_rule(
    profile: EligibilityProfile,
    rule: EligibilityRule,
) -> tuple[bool, str]:

    if profile.social_category is None:
        return False, "Social category is required"

    actual_category = profile.social_category.lower()
    expected_category = rule.value.lower()

    satisfied = compare_values(
        actual_category,
        rule.operator,
        expected_category,
    )

    if satisfied:
        message = (
            f"Social category requirement satisfied: "
            f"{actual_category} matches {expected_category}"
        )
    else:
        message = (
            f"Social category requirement not satisfied: "
            f"{actual_category} does not match {expected_category}"
        )

    return satisfied, message

def evaluate_disability_rule(
    profile: EligibilityProfile,
    rule: EligibilityRule,
) -> tuple[bool, str]:

    actual_status = profile.disability_status

    # None means the question was never answered: report it as missing
    # information instead of comparing it against the rule's value (which
    # used to make "never filled in" indistinguishable from "no disability").
    if actual_status is None:
        return False, "Disability status is required"

    expected_status = rule.value.lower() == "true"

    satisfied = compare_values(
        actual_status,
        rule.operator,
        expected_status,
    )

    if satisfied:
        message = (
            f"Disability status requirement satisfied: "
            f"{actual_status} matches {expected_status}"
        )
    else:
        message = (
            f"Disability status requirement not satisfied: "
            f"{actual_status} does not match {expected_status}"
        )

    return satisfied, message

def evaluate_rule(
    profile: EligibilityProfile,
    rule: EligibilityRule,
) -> tuple[bool, str, str | None]:
    """Evaluate one rule, tolerating a legacy value that cannot be parsed.

    Rule values are validated when they are created or updated, but records
    written before that could still be malformed. Such a rule is reported as
    unevaluable (treated like missing information) instead of raising and
    turning the whole eligibility check into a 500.
    """
    try:
        return _evaluate_rule(profile, rule)
    except (ValueError, InvalidOperation, ArithmeticError, TypeError):
        return (
            False,
            (
                f"The rule for {rule.parameter.value} could not be "
                "evaluated because its stored value is invalid"
            ),
            None,
        )

def evaluate_profile_against_rules(
    profile: EligibilityProfile,
    scheme: Scheme,
    rules: list[EligibilityRule],
) -> EligibilityCheckResponse:
    rule_results = []
    missing_information = []
    has_definite_failure = False

    for rule in rules:
        satisfied, message, actual_value = evaluate_rule(
            profile,
            rule,
        )

        rule_results.append(
            {
                "parameter": rule.parameter.value,
                "operator": rule.operator.value,
                "required_value": rule.value,
                "actual_value": actual_value,
                "satisfied": satisfied,
                "message": message,
            }
        )

        if actual_value is None:
            missing_information.append(rule.parameter.value)
        elif not satisfied:
            has_definite_failure = True

    if has_definite_failure:
        status = EligibilityStatus.NOT_ELIGIBLE
        summary = "You are not eligible for this scheme."
    elif missing_information:
        status = EligibilityStatus.MORE_INFORMATION_REQUIRED
        summary = (
            "More information is required to determine your eligibility."
        )
    else:
        status = EligibilityStatus.ELIGIBLE
        summary = "You are eligible for this scheme."

    return EligibilityCheckResponse(
        scheme_id=scheme.id,
        scheme_title=scheme.title,
        status=status,
        summary=summary,
        rules=rule_results,
        missing_information=missing_information,
    )

def _evaluate_rule(
    profile: EligibilityProfile,
    rule: EligibilityRule,
) -> tuple[bool, str, str | None]:

    if rule.parameter == EligibilityParameter.AGE:
        satisfied, message = evaluate_age_rule(profile, rule)
        actual_value = (
            str(profile.age)
            if profile.age is not None
            else None
        )

    elif rule.parameter == EligibilityParameter.GENDER:
        satisfied, message = evaluate_gender_rule(profile, rule)
        actual_value = profile.gender

    elif rule.parameter == EligibilityParameter.INCOME:
        satisfied, message = evaluate_income_rule(profile, rule)
        actual_value = (
            str(profile.annual_income)
            if profile.annual_income is not None
            else None
        )

    elif rule.parameter == EligibilityParameter.OCCUPATION:
        satisfied, message = evaluate_occupation_rule(profile, rule)
        actual_value = profile.occupation

    elif rule.parameter == EligibilityParameter.EDUCATION:
        satisfied, message = evaluate_education_rule(profile, rule)
        actual_value = profile.education

    elif (
        rule.parameter == EligibilityParameter.STATE
        or rule.parameter == EligibilityParameter.DISTRICT
    ):
        satisfied, message = evaluate_location_rule(profile, rule)

        if rule.parameter == EligibilityParameter.STATE:
            actual_value = profile.state
        else:
            actual_value = profile.district

    elif rule.parameter == EligibilityParameter.SOCIAL_CATEGORY:
        satisfied, message = evaluate_social_category_rule(profile, rule)
        actual_value = profile.social_category

    elif rule.parameter == EligibilityParameter.DISABILITY_STATUS:
        satisfied, message = evaluate_disability_rule(profile, rule)
        actual_value = (
            str(profile.disability_status)
            if profile.disability_status is not None
            else None
        )

    else:
        return False, "Unsupported eligibility parameter", None

    return satisfied, message, actual_value

def build_eligibility_profile(
        profile: UserProfile,
) -> EligibilityProfile:
    age = None

    if profile.date_of_birth is not None:
        age = calculate_age(profile.date_of_birth)

    return EligibilityProfile(
        age=age,
        gender=profile.gender.value if profile.gender else None,
        annual_income=profile.annual_income,
        occupation=profile.occupation,
        education=profile.education,
        state=profile.state,
        district=profile.district,
        social_category=(
            profile.social_category.value
            if profile.social_category
            else None
        ),
        disability_status=profile.disability_status,
    )

def check_eligibility(
        db: Session,
        current_user: User,
        scheme_id: UUID,
) -> EligibilityCheckResponse:

    # Fetch scheme
    scheme_result = db.execute(
        select(Scheme).where(Scheme.id == scheme_id)
    )
    scheme = scheme_result.scalar_one_or_none()

    if scheme is None:
        raise ValueError("Scheme not found")

    # A scheme the caller cannot read (draft/pending/rejected/archived or
    # outside an official's scope) must not reveal its eligibility rules.
    _assert_scheme_is_visible(db, scheme, current_user)

    # Fetch eligibility rules for the scheme

    rules_result = db.execute(
        select(EligibilityRule)
        .where(EligibilityRule.scheme_id == scheme_id)
    )

    rules = rules_result.scalars().all()

    # Fetch User Profile
    profile_result = db.execute(
        select(UserProfile).where(UserProfile.user_id == current_user.id)
    )

    profile = profile_result.scalar_one_or_none()

    # A missing profile is not "not found": the user simply has not supplied
    # the data the rules need yet, so the verdict is "more information
    # required" (every rule parameter is missing) instead of a 404.
    if profile is None:
        return EligibilityCheckResponse(
            scheme_id=scheme.id,
            scheme_title=scheme.title,
            status=EligibilityStatus.MORE_INFORMATION_REQUIRED,
            summary=(
                "More information is required to determine your eligibility. "
                "Complete your profile to continue."
            ),
            rules=[],
            missing_information=[
                rule.parameter.value for rule in rules
            ],
        )

    eligibility_profile = build_eligibility_profile(profile)

    rule_results = []
    missing_information = []
    has_definite_failure = False

    for rule in rules:
        satisfied, message, actual_value = evaluate_rule(
            eligibility_profile,
            rule,
        )

        rule_results.append(
            {
                "parameter": rule.parameter.value,
                "operator": rule.operator.value,
                "required_value": rule.value,
                "actual_value": actual_value,
                "satisfied": satisfied,
                "message": message,
            }
        )

        if actual_value is None:
            missing_information.append(rule.parameter.value)
        elif not satisfied:
            has_definite_failure = True

    # A rule that was checked against real profile data and failed is a
    # definite verdict: it wins over rules that merely lack data. Otherwise a
    # user who is clearly ineligible could be told to supply more information
    # and be denied anyway.
    if has_definite_failure:
        status = EligibilityStatus.NOT_ELIGIBLE
        summary = "You are not eligible for this scheme."
    elif missing_information:
        status = EligibilityStatus.MORE_INFORMATION_REQUIRED
        summary = (
            "More information is required to determine your eligibility."
        )
    else:
        status = EligibilityStatus.ELIGIBLE
        summary = "You are eligible for this scheme."


    return EligibilityCheckResponse(
        scheme_id=scheme.id,
        scheme_title=scheme.title,
        status=status,
        summary=summary,
        rules=rule_results,
        missing_information=missing_information,
    )