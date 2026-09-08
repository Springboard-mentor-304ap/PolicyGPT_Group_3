from uuid import UUID
from datetime import date
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.models.user_profile import UserProfile
from backend.app.models.scheme import Scheme
from backend.app.models.eligibility_rule import EligibilityRule, EligibilityOperator, EligibilityParameter

from backend.app.eligibility.schemas import (
    EligibilityCheckResponse,
    EligibilityStatus
)

def calculate_age(date_of_birth: date) -> int:
    today = date.today()

    age = today.year - date_of_birth.year

    if (today.month, today.day) < (date_of_birth.month, date_of_birth.day):
        age -= 1

    return age

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

    return False


def evaluate_age_rule(
        profile: UserProfile,
        rule: EligibilityRule,
) -> tuple[bool, str]:
    if profile.date_of_birth is None:
        return False, "Date of birth is required"

    expected_age = int(rule.value)
    actual_age = calculate_age(profile.date_of_birth)

    satisfied = compare_values(
        actual_age,
        rule.operator,
        expected_age,
    )

    if satisfied: 
        message= f"Age requirement satisfied: {actual_age} {rule.operator.value} {expected_age}"

    else: 
        message= f"Age requirement not satisfied: {actual_age} {rule.operator.value} {expected_age}"

    return satisfied, message

def evaluate_gender_rule(
        profile: UserProfile,
        rule: EligibilityRule,
) -> tuple[bool, str]:

    if profile.gender is None:
        return False, "Gender is required"

    actual_gender = profile.gender.value
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
    profile: UserProfile,
    rule: EligibilityRule,
) -> tuple[bool, str]:

    if profile.annual_income is None:
        return False, "Annual income is required"

    actual_income = profile.annual_income
    expected_income = Decimal(rule.value)

    satisfied = compare_values(
        actual_income,
        rule.operator,
        expected_income,
    )

    if satisfied:
        message = (
            f"Income requirement satisfied: "
            f"{actual_income} {rule.operator.value} {expected_income}"
        )
    else:
        message = (
            f"Income requirement not satisfied: "
            f"{actual_income} {rule.operator.value} {expected_income}"
        )

    return satisfied, message

def evaluate_occupation_rule(
    profile: UserProfile,
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
    profile: UserProfile,
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
    profile: UserProfile,
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
    profile: UserProfile,
    rule: EligibilityRule,
) -> tuple[bool, str]:

    if profile.social_category is None:
        return False, "Social category is required"

    actual_category = profile.social_category.value
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
    profile: UserProfile,
    rule: EligibilityRule,
) -> tuple[bool, str]:

    actual_status = profile.disability_status
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
        profile: UserProfile,
        rule: EligibilityRule,
) -> tuple[bool, str, str | None]:

    if rule.parameter == EligibilityParameter.AGE:
        satisfied, message = evaluate_age_rule(profile, rule)
        actual_value = (
            str(calculate_age(profile.date_of_birth))
            if profile.date_of_birth
            else None
        )

    elif rule.parameter == EligibilityParameter.GENDER:
        satisfied, message = evaluate_gender_rule(profile, rule)
        actual_value = (
            profile.gender.value
            if profile.gender
            else None
        )

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
        actual_value = (
            profile.social_category.value
            if profile.social_category
            else None
        )

    elif rule.parameter == EligibilityParameter.DISABILITY_STATUS:
        satisfied, message = evaluate_disability_rule(profile, rule)
        actual_value = str(profile.disability_status)

    else:
        return False, "Unsupported eligibility parameter", None

    return satisfied, message, actual_value


async def check_eligibility(
        db: AsyncSession,
        user_id: UUID,
        scheme_id: UUID,
) -> EligibilityCheckResponse:

    # Fetch User Profile
    profile_result = await db.execute(
        select(UserProfile).where(UserProfile.user_id == user_id)
    )

    profile = profile_result.scalar_one_or_none()

    if profile is None:
        raise ValueError("User profile not found")

    # Fetch scheme
    scheme_result = await db.execute(
        select(Scheme).where(Scheme.id == scheme_id)
    )
    scheme = scheme_result.scalar_one_or_none()

    if scheme is None:
        raise ValueError("Scheme not found")

    # Fetch eligibility rules for the scheme

    rules_result = await db.execute(
        select(EligibilityRule)
        .where(EligibilityRule.scheme_id == scheme_id)
    )

    rules = rules_result.scalars().all()

    rule_results = []
    missing_information = []
    all_rules_satisfied = True

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
            all_rules_satisfied = False


    if missing_information:
        status = EligibilityStatus.MORE_INFORMATION_REQUIRED
        summary = (
            "More information is required to determine your eligibility."
        )
    elif all_rules_satisfied:
        status = EligibilityStatus.ELIGIBLE
        summary = "You are eligible for this scheme."
    else:
        status = EligibilityStatus.NOT_ELIGIBLE
        summary = "You are not eligible for this scheme."


    return EligibilityCheckResponse(
        scheme_id=scheme.id,
        scheme_title=scheme.title,
        status=status,
        summary=summary,
        rules=rule_results,
        missing_information=missing_information,
    )