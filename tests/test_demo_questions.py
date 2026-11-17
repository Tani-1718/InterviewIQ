import pytest

from config.demo_questions import DEMO_QUESTIONS, get_demo_question


def test_demo_questions_are_available_and_distinct_for_every_role():
    assert len(DEMO_QUESTIONS) == 5
    for role_id, questions in DEMO_QUESTIONS.items():
        assert len(questions) == 5
        assert len({question.casefold() for question in questions}) == 5
        assert get_demo_question(role_id, 1) == questions[0]
        assert get_demo_question(role_id, 5) == questions[-1]


@pytest.mark.parametrize(
    ("role_id", "sequence_number"),
    [("unknown", 1), ("software_engineer", 0), ("software_engineer", 6)],
)
def test_invalid_demo_question_requests_are_explicit(role_id, sequence_number):
    with pytest.raises(ValueError):
        get_demo_question(role_id, sequence_number)
