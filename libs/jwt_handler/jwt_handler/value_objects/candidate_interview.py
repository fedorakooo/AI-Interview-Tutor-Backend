CANDIDATE_INTERVIEW_AUDIENCE = "candidate-interview"


def candidate_interview_scope(attempt_id: str) -> str:
    return f"candidate_interview:{attempt_id}"
