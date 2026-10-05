from collections import defaultdict

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.eligibility.schemas import EligibilityStatus
from backend.app.eligibility.service import (
    EligibilityProfile,
    evaluate_profile_against_rules,
)
from backend.app.finder.schemas import (
    SchemeMatch,
    SchemeMatchResponse,
)
from backend.app.models.eligibility_rule import EligibilityRule
from backend.app.models.scheme import Scheme, SchemeStatus


def match_profile_to_schemes(
    db: Session,
    profile: EligibilityProfile,
) -> SchemeMatchResponse:
    schemes = db.execute(
        select(Scheme).where(
            Scheme.status == SchemeStatus.ACTIVE
        )
    ).scalars().all()

    results = {
        "eligible": [],
        "more_information_required": [],
        "not_eligible": [],
        "no_criteria_defined": [],
    }

    if not schemes:
        return SchemeMatchResponse(**results)

    scheme_ids = [scheme.id for scheme in schemes]

    rules = db.execute(
        select(EligibilityRule).where(
            EligibilityRule.scheme_id.in_(scheme_ids)
        )
    ).scalars().all()

    rules_by_scheme = defaultdict(list)

    for rule in rules:
        rules_by_scheme[rule.scheme_id].append(rule)

    for scheme in schemes:
        scheme_rules = rules_by_scheme.get(scheme.id, [])

        if not scheme_rules:
            results["no_criteria_defined"].append(
                SchemeMatch(
                    scheme_id=scheme.id,
                    scheme_title=scheme.title,
                    status="no_criteria_defined",
                    summary=(
                        "No eligibility criteria are defined "
                        "for this scheme."
                    ),
                    rules=[],
                    missing_information=[],
                )
            )
            continue

        result = evaluate_profile_against_rules(
            profile,
            scheme,
            scheme_rules,
        )

        match = SchemeMatch.model_validate(result)

        if result.status == EligibilityStatus.ELIGIBLE:
            results["eligible"].append(match)

        elif result.status == EligibilityStatus.MORE_INFORMATION_REQUIRED:
            results["more_information_required"].append(match)

        else:
            results["not_eligible"].append(match)

    return SchemeMatchResponse(**results)