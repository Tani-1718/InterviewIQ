from config.roles import ROLES, ROLE_BY_ID
from modules.interview_config import (
    DIFFICULTIES,
    EXPERIENCE_LEVELS,
    INTERVIEW_TYPES,
    QUESTION_COUNTS,
)


def test_supported_roles_are_unique_and_complete():
    assert [role["title"] for role in ROLES] == [
        "Software Engineer",
        "Product Designer",
        "Marketing Associate",
        "Data Analyst",
        "Customer Service",
    ]
    assert len(ROLE_BY_ID) == len(ROLES)
    assert all(role["skills"] and role["description"] and role["difficulty"] for role in ROLES)


def test_interview_configuration_options_match_supported_values():
    assert EXPERIENCE_LEVELS == ("Fresher", "Intermediate", "Experienced")
    assert DIFFICULTIES == ("Easy", "Medium", "Hard")
    assert QUESTION_COUNTS == (5, 10, 15)
    assert INTERVIEW_TYPES == ("Technical", "HR", "Behavioral", "Mixed")
