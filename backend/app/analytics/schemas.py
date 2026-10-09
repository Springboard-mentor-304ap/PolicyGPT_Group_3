from pydantic import BaseModel


class AnalyticsOverview(BaseModel):
    # Platform-wide totals are null for every role except administrators.
    total_users: int | None
    total_policies: int
    total_schemes: int
    total_searches: int | None