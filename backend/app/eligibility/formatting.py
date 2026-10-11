"""Human-readable rendering of eligibility rules.

Rules are stored as the raw triple (parameter, operator, value); strings like
``age gte 18`` only make sense to the engine. Everything that shows a rule to
a human goes through :func:`format_rule` so the wording lives in one place:

* the comparison endpoint (``/comparison``)
* the AI knowledge-base chunks built by ``backend.app.ai.knowledge_ingestion``

This module is deliberately a leaf: it imports only the rule enums, so any
module can use it without import cycles.
"""

from backend.app.models.eligibility_rule import (
    EligibilityOperator,
    EligibilityParameter,
)

# How each operator reads in plain text. ``{value}`` is the rule's value; the
# list operators are handled separately because their value is a list.
_OPERATOR_TEXT = {
    "eq": "{value}",
    "neq": "not {value}",
    "lt": "below {value}",
    "lte": "{value} or below",
    "gt": "above {value}",
    "gte": "{value} or above",
}


def _parameter_label(parameter) -> str:
    value = (
        parameter.value
        if isinstance(parameter, EligibilityParameter)
        else str(parameter)
    )
    return value.replace("_", " ").capitalize()


def _operator_value(operator) -> str:
    if isinstance(operator, EligibilityOperator):
        return operator.value
    return str(operator)


def _list_text(raw: str) -> str:
    return ", ".join(
        part.strip() for part in raw.split(",") if part.strip()
    )


def format_rule(parameter, operator, value) -> str:
    """Render one rule as human-readable text.

    Accepts the enums or their raw string values, e.g.::

        format_rule(EligibilityParameter.AGE, EligibilityOperator.GTE, "18")
        # "Age: 18 or above"
        format_rule("income", "lt", "300000")
        # "Income: below 300000"
        format_rule("gender", "eq", "female")
        # "Gender: female"
    """
    label = _parameter_label(parameter)
    op = _operator_value(operator)
    raw = "" if value is None else str(value).strip()

    if op == EligibilityOperator.IN.value:
        return f"{label}: one of {_list_text(raw)}"

    if op == EligibilityOperator.NOT_IN.value:
        return f"{label}: not one of {_list_text(raw)}"

    text = _OPERATOR_TEXT.get(op)

    if text is None:
        # Unknown operator: fall back to the readable-but-raw form instead of
        # dropping information.
        return f"{label}: {op} {raw}".rstrip()

    return f"{label}: {text.format(value=raw)}"
