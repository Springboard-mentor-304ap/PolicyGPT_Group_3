from pydantic import BaseModel


class DepartmentOptionsResponse(BaseModel):
    """Department values already present in the platform data.

    `department` stays a free-form string column, so the list is derived from
    the stored values instead of a hardcoded catalogue: it is exactly what an
    existing policy or scheme can be attributed to.
    """

    departments: list[str]
