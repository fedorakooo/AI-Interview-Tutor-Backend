from datetime import UTC, datetime, timedelta


def compute_next_review(rating: str, from_time: datetime | None = None) -> datetime:
    """SM-2-lite intervals for flashcard spaced repetition."""
    base = from_time or datetime.now(UTC)
    mapping = {"again": 1, "good": 3, "easy": 7}
    days = mapping.get(str(rating).lower(), 3)
    return base + timedelta(days=days)
