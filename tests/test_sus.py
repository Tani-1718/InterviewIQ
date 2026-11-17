import pytest

from modules.sus import calculate_sus_score


@pytest.mark.parametrize(
    ("responses", "expected"),
    [
        ([5, 1, 5, 1, 5, 1, 5, 1, 5, 1], 100.0),
        ([1, 5, 1, 5, 1, 5, 1, 5, 1, 5], 0.0),
        ([3] * 10, 50.0),
        ([1, 5, 2, 4, 3, 5, 1, 4, 2, 5], 15.0),
    ],
)
def test_sus_score_uses_standard_alternating_item_contributions(
    responses, expected
):
    assert calculate_sus_score(responses) == expected


@pytest.mark.parametrize(
    "responses",
    [[], [3] * 9, [3] * 9 + [0], [3] * 9 + [6], [True] * 10, [2.5] * 10],
)
def test_sus_score_rejects_invalid_responses(responses):
    with pytest.raises(ValueError, match="exactly 10 integers"):
        calculate_sus_score(responses)
