from datetime import datetime
from uuid import UUID

from sqlalchemy import Integer, String, text
from sqlalchemy.orm import Mapped, mapped_column

from src.infrastructure.postgres.database import Base


class ReferralCodeORM(Base):
    __tablename__ = "referral_codes"

    code: Mapped[str] = mapped_column(String(32), primary_key=True)
    owner_user_id: Mapped[UUID] = mapped_column()
    credits: Mapped[int] = mapped_column(Integer, default=0)
    redemptions: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(server_default=text("TIMEZONE('utc', now())"))
