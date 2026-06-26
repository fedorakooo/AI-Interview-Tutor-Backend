from pydantic import BaseModel, Field, field_validator

from src.domain.value_objects.user_filter import OrderField, UserFilter, UserSortField


class UserFilterRequest(BaseModel):
    page: int = Field(default=1, ge=1, description="Page number must be positive")
    limit: int = Field(default=30, ge=1, le=100, description="Limit must be between 1 and 100")
    filter_by_name: str | None = Field(
        default=None,
        max_length=100,
        description="Name filter max length is 100 characters",
    )
    sort_by: UserSortField = UserSortField.SECOND_NAME
    order_by: OrderField = OrderField.ASC

    @field_validator("filter_by_name")
    def validate_name_filter(cls, v) -> str:
        if v is not None and len(v.strip()) == 0:
            raise ValueError("Name filter cannot be empty string")
        return v

    def to_entity(self) -> UserFilter:
        return UserFilter(
            page=self.page,
            limit=self.limit,
            name=self.filter_by_name,
            sort_by=self.sort_by,
            order_by=self.order_by,
        )
