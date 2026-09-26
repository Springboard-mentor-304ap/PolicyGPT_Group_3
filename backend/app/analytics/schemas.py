from typing import Optional, List, Any
from pydantic import BaseModel


class OverviewMetrics(BaseModel):
    total_users: Optional[int] = None
    total_policies: int = 0
    total_schemes: int = 0
    total_searches: Optional[int] = None


class CategoryMetric(BaseModel):
    category: str
    label: str
    count: int
    percentage: float


class StatusMetric(BaseModel):
    status: str
    label: str
    count: int
    percentage: float


class DepartmentMetric(BaseModel):
    department: str
    count: int


class StateMetric(BaseModel):
    state: str
    count: int


class SchemeUsageItem(BaseModel):
    id: str
    title: str
    category: str
    department: Optional[str] = None
    view_count: int = 0
    status: str


class TopQueryMetric(BaseModel):
    query: str
    count: int


class SearchIntelligence(BaseModel):
    total_searches: int
    top_queries: List[TopQueryMetric]
    recent_searches_count: int


class ActivityItem(BaseModel):
    id: str
    action: str
    target_table: str
    actor_name: Optional[str] = None
    actor_role: Optional[str] = None
    created_at: str
    details: Optional[str] = None


class TimeSeriesDataPoint(BaseModel):
    date: str
    searches: int = 0
    policies_created: int = 0
    schemes_created: int = 0


class DashboardAnalyticsResponse(BaseModel):
    user_role: str
    user_department: Optional[str] = None
    overview: OverviewMetrics
    policies_by_category: List[CategoryMetric]
    policies_by_status: Optional[List[StatusMetric]] = None
    policies_by_department: List[DepartmentMetric]
    schemes_by_category: List[CategoryMetric]
    schemes_by_status: Optional[List[StatusMetric]] = None
    schemes_by_department: List[DepartmentMetric]
    schemes_by_state: List[StateMetric]
    top_viewed_schemes: Optional[List[SchemeUsageItem]] = None
    search_intelligence: Optional[SearchIntelligence] = None
    user_activity: Optional[List[ActivityItem]] = None
    usage_over_time: Optional[List[TimeSeriesDataPoint]] = None
