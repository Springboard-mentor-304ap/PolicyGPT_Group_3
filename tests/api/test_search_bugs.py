"""Search / FAQ bugs (items 2 and 3).

Item 2: search history stores the caller's user_id, is logged only for the
first page of a search, and the ministry filter applies to schemes through
their parent policy.
Item 3: every user-supplied ILIKE input is escaped, so % and _ are literals.
"""

from backend.app.models.faq import FAQ
from backend.app.models.policy import PolicyStatus
from backend.app.models.scheme import SchemeStatus
from backend.app.models.search_history import SearchHistory
from backend.app.faq.service import list_faqs
from backend.app.search.schemas import SearchType
from backend.app.search.service import search
from tests.api.conftest import _policy, _scheme


def _titles(result) -> list[str]:
    return [item.title for item in result["results"]]


# ─── Item 2: history user_id + page-1 only ─────────────────────────────────
def test_search_history_stores_user_id_and_only_logs_first_page(
    session_factory, seed, citizen, official,
):
    seed(
        _policy(
            title="Solar Panels For Farms",
            status=PolicyStatus.APPROVED,
            uploaded_by=official.id,
        )
    )

    db = session_factory()

    try:
        # Normal path: a logged-in caller is recorded on the history row.
        result = search(db=db, query="Solar", current_user=citizen, page=1)
        assert result["total"] == 1

        rows = db.query(SearchHistory).all()
        assert len(rows) == 1
        assert rows[0].user_id == citizen.id
        assert rows[0].query_text == "Solar"
        assert rows[0].result_count == 1

        # Bug: every page of the same search used to write another row.
        search(db=db, query="Solar", current_user=citizen, page=2)
        db.expire_all()
        assert db.query(SearchHistory).count() == 1

        # Guests are still logged, without a user_id.
        search(db=db, query="Solar", current_user=None, page=1)
        rows = (
            db.query(SearchHistory)
            .order_by(SearchHistory.searched_at.asc())
            .all()
        )
        assert len(rows) == 2
        assert rows[1].user_id is None
    finally:
        db.close()


# ─── Item 2: ministry filter for schemes ───────────────────────────────────
def test_ministry_filter_applies_to_schemes_through_parent_policy(
    session_factory, seed, official,
):
    health_policy = seed(
        _policy(
            title="Health Policy",
            ministry="Health",
            status=PolicyStatus.APPROVED,
            uploaded_by=official.id,
        )
    )
    finance_policy = seed(
        _policy(
            title="Finance Policy",
            ministry="Finance",
            status=PolicyStatus.APPROVED,
            uploaded_by=official.id,
        )
    )
    health_scheme = seed(
        _scheme(
            title="Health Scheme",
            policy_id=health_policy.id,
            created_by=official.id,
            status=SchemeStatus.ACTIVE,
        )
    )
    finance_scheme = seed(
        _scheme(
            title="Finance Scheme",
            policy_id=finance_policy.id,
            created_by=official.id,
            status=SchemeStatus.ACTIVE,
        )
    )

    db = session_factory()

    try:
        # Normal path: without the filter both active schemes are returned.
        result = search(db=db, search_type=SearchType.SCHEME)
        assert set(item.id for item in result["results"]) == {
            health_scheme.id,
            finance_scheme.id,
        }

        # Bug: `ministry` was ignored for schemes. It now reaches the parent
        # policy (and is case-insensitive, like the rest of the filters).
        result = search(
            db=db, search_type=SearchType.SCHEME, ministry="health"
        )
        assert [item.id for item in result["results"]] == [health_scheme.id]

        # "all" search applies it to both result sets.
        result = search(db=db, search_type=SearchType.ALL, ministry="health")
        assert set(item.id for item in result["results"]) == {
            health_policy.id,
            health_scheme.id,
        }
    finally:
        db.close()


# ─── Item 3: escaped wildcards ─────────────────────────────────────────────
def test_ilike_wildcards_are_escaped_in_search_and_faq_search(
    session_factory, seed, citizen, official,
):
    percent_policy = seed(
        _policy(
            title="100% Support Grant",
            status=PolicyStatus.APPROVED,
            uploaded_by=official.id,
        )
    )
    seed(
        _policy(
            title="Support Grant Programme",
            status=PolicyStatus.APPROVED,
            uploaded_by=official.id,
        )
    )
    underscore_policy = seed(
        _policy(
            title="Grant_Area",
            status=PolicyStatus.APPROVED,
            uploaded_by=official.id,
        )
    )
    seed(
        _policy(
            title="Grant Area",
            status=PolicyStatus.APPROVED,
            uploaded_by=official.id,
        )
    )
    numbered = seed(
        _policy(
            title="Numbered Scheme",
            department="Health_1",
            status=PolicyStatus.APPROVED,
            uploaded_by=official.id,
        )
    )
    seed(
        _policy(
            title="Spaced Scheme",
            department="Health 1",
            status=PolicyStatus.APPROVED,
            uploaded_by=official.id,
        )
    )

    faq_percent = seed(
        FAQ(
            question="What is the 100% subsidy?",
            answer="It covers the full cost.",
            is_active=True,
            created_by=official.id,
        )
    )
    seed(
        FAQ(
            question="What is the subsidy rate?",
            answer="It depends on the scheme.",
            is_active=True,
            created_by=official.id,
        )
    )
    faq_underscore = seed(
        FAQ(
            question="Which form Q_A do I need?",
            answer="Form Q_A.",
            is_active=True,
            created_by=official.id,
        )
    )
    seed(
        FAQ(
            question="Which form Q B do I need?",
            answer="Form Q B.",
            is_active=True,
            created_by=official.id,
        )
    )

    db = session_factory()

    try:
        # Bug: "%" matched every policy (wildcard), not just the one that
        # literally contains a percent sign.
        result = search(
            db=db, query="%", search_type=SearchType.POLICY
        )
        assert [item.id for item in result["results"]] == [percent_policy.id]

        # Bug: "_" matched any single character, so "Grant_A" also matched
        # "Grant Area".
        result = search(
            db=db, query="Grant_A", search_type=SearchType.POLICY
        )
        assert [item.id for item in result["results"]] == [underscore_policy.id]

        # The filter fields are escaped the same way.
        result = search(db=db, department="Health_1")
        assert [item.id for item in result["results"]] == [numbered.id]

        # FAQ search: same escaping for "%" and "_".
        rows, _total = list_faqs(db, current_user=citizen, search="%")
        assert [faq.id for faq in rows] == [faq_percent.id]

        rows, _total = list_faqs(db, current_user=citizen, search="Q_A")
        assert [faq.id for faq in rows] == [faq_underscore.id]

        # Normal path: a plain term still matches as a substring.
        result = search(
            db=db, query="Support Grant", search_type=SearchType.POLICY
        )
        assert set(item.title for item in result["results"]) == {
            "100% Support Grant",
            "Support Grant Programme",
        }
    finally:
        db.close()
