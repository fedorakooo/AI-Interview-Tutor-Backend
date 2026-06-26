from dataclasses import dataclass
from enum import StrEnum


class OrderField(StrEnum):
    DESC = "DESC"
    ASC = "ASC"


class UserSortField(StrEnum):
    FIRST_NAME = "first_name"
    SECOND_NAME = "second_name"
    USERNAME = "username"
    CREATED_AT = "created_at"


@dataclass
class UserFilter:
    page: int
    limit: int
    sort_by: UserSortField
    order_by: OrderField
    name: str | None = None
