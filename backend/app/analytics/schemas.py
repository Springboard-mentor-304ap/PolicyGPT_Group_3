from pydantic import BaseModel


class AnalyticsOverview(BaseModel):
    total_users: int
    total_policies: int
    total_schemes: int
    total_searches: int