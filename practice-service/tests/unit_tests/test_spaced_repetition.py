from datetime import UTC, datetime

from src.application.services.spaced_repetition import compute_next_review


def test_compute_next_review_again():
    base = datetime(2026, 1, 1, tzinfo=UTC)
    nxt = compute_next_review("again", base)
    assert nxt == datetime(2026, 1, 2, tzinfo=UTC)


def test_compute_next_review_easy():
    base = datetime(2026, 1, 1, tzinfo=UTC)
    nxt = compute_next_review("easy", base)
    assert nxt == datetime(2026, 1, 8, tzinfo=UTC)
