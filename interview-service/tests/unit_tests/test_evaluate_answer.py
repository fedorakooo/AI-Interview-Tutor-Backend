import json

from src.agent.state.evaluate_answer import _parse_evaluation


def test_parse_evaluation_json():
    complete, score, feedback = _parse_evaluation(
        json.dumps({"complete": True, "score": 8.5, "feedback": "Good structure"})
    )
    assert complete is True
    assert score == 8.5
    assert feedback == "Good structure"


def test_parse_evaluation_legacy_complete_word():
    complete, score, feedback = _parse_evaluation("complete")
    assert complete is True
    assert score is None
    assert feedback is None
