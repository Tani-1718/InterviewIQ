import json
from pathlib import Path

import pytest
from groq import NotFoundError, RateLimitError
from httpx import Request, Response
from langchain_core.messages import AIMessage
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import RunnableLambda

from ai_engine.answer_evaluator import evaluate_answer
from ai_engine.chat_history import build_chat_history
from ai_engine.llm import (
    AIConfigurationError,
    AIProviderError,
    AIRateLimitError,
    AIResponseError,
    AIService,
    create_chat_model,
)
from ai_engine.prompts import (
    ANSWER_EVALUATION_PROMPT,
    FINAL_ANALYSIS_PROMPT,
    FOLLOW_UP_QUESTION_PROMPT,
    LEARNING_RECOMMENDATIONS_PROMPT,
    QUESTION_GENERATION_PROMPT,
)
from ai_engine.question_generator import generate_question
from config.settings import Settings


@pytest.fixture
def settings():
    return Settings(
        groq_api_key=None,
        groq_model="openai/gpt-oss-20b",
        database_path=Path("interviewiq-test.sqlite3"),
        groq_request_timeout=10,
        groq_max_retries=0,
    )


def test_groq_model_configuration_requires_a_real_api_key(settings):
    with pytest.raises(AIConfigurationError, match="GROQ_API_KEY"):
        AIService(settings).invoke(
            ChatPromptTemplate.from_template("Hello {name}"),
            {"name": "candidate"},
        )


def test_injected_chat_runnable_can_exercise_prompt_without_network(settings):
    prompt_values = []

    def fake_model(prompt_value):
        prompt_values.extend(prompt_value.to_messages())
        return AIMessage(content="  Tell me about a project you are proud of?  ")

    service = AIService(settings, llm=RunnableLambda(fake_model))
    result = service.invoke(
        ChatPromptTemplate.from_messages(
            [("system", "You are a coach."), ("human", "Role: {role}")]
        ),
        {"role": "Data Analyst"},
    )

    assert result == "Tell me about a project you are proud of?"
    assert "Role: Data Analyst" in prompt_values[1].content


def test_empty_model_response_is_not_returned_as_success(settings):
    service = AIService(
        settings,
        llm=RunnableLambda(lambda _: AIMessage(content="  ")),
    )

    with pytest.raises(AIResponseError, match="empty"):
        service.invoke(
            ChatPromptTemplate.from_template("Hello {name}"),
            {"name": "candidate"},
        )


def test_groq_rate_limit_is_reported_as_a_retryable_service_error(settings):
    response = Response(
        429,
        request=Request("POST", "https://api.groq.com/openai/v1/chat/completions"),
    )
    rate_limit_error = RateLimitError(
        "rate limited",
        response=response,
        body={"error": "rate limited"},
    )

    def reject_request(_prompt):
        raise rate_limit_error

    service = AIService(settings, llm=RunnableLambda(reject_request))

    with pytest.raises(AIRateLimitError, match="rate-limiting"):
        service.invoke(
            ChatPromptTemplate.from_template("Hello {name}"),
            {"name": "candidate"},
        )


def test_provider_error_includes_model_and_safe_provider_detail(settings):
    settings = Settings(
        groq_api_key="gsk-test-secret",
        groq_model=settings.groq_model,
        database_path=settings.database_path,
        groq_request_timeout=settings.groq_request_timeout,
        groq_max_retries=settings.groq_max_retries,
    )
    response = Response(
        404,
        request=Request("POST", "https://api.groq.com/openai/v1/chat/completions"),
    )
    provider_error = NotFoundError(
        "Not found",
        response=response,
        body={
            "error": {
                "message": "The requested model was not found; gsk-test-secret",
                "code": "model_not_found",
            }
        },
    )
    def reject_request(_prompt):
        raise provider_error

    service = AIService(settings, llm=RunnableLambda(reject_request))

    with pytest.raises(AIProviderError) as error:
        service.invoke(
            ChatPromptTemplate.from_template("Hello {name}"),
            {"name": "candidate"},
        )

    message = str(error.value)
    assert "openai/gpt-oss-20b" in message
    assert "HTTP 404" in message
    assert "The requested model was not found" in message
    assert "model_not_found" in message
    assert "gsk-test-secret" not in message


def test_create_chat_model_uses_groq_api_host(monkeypatch, settings):
    settings = Settings(
        groq_api_key="gsk-test-secret",
        groq_model=settings.groq_model,
        database_path=settings.database_path,
        groq_request_timeout=settings.groq_request_timeout,
        groq_max_retries=settings.groq_max_retries,
    )
    captured = {}

    class FakeChatGroq:
        def __init__(self, **kwargs):
            captured.update(kwargs)

    monkeypatch.setattr("ai_engine.llm.ChatGroq", FakeChatGroq)
    create_chat_model(settings)

    assert captured["model"] == "openai/gpt-oss-20b"
    assert captured["base_url"] == "https://api.groq.com"


def test_question_generation_and_answer_evaluation_work_end_to_end_offline(settings):
    payload = {
        "overall_score": 72,
        "scores": {
            "relevance": 80,
            "technical_accuracy": 70,
            "depth": 60,
            "clarity": 75,
            "structure": 70,
            "completeness": 65,
        },
        "what_went_well": ["You identified SQL as part of your approach."],
        "what_was_missing": ["No result or impact was stated."],
        "mistakes_or_inaccuracies": [],
        "suggestions": ['Explain what you did with "SQL" and the outcome.'],
        "stronger_example_answer": "I used SQL to compare the records and report the trend.",
        "concepts_to_revise": ["SQL aggregation"],
    }
    responses = [
        "How would you use SQL to validate a data pipeline?",
        json.dumps(payload),
    ]
    prompts = []

    def fake_model(prompt_value):
        prompts.append(prompt_value.to_messages())
        return AIMessage(content=responses.pop(0))

    service = AIService(settings, llm=RunnableLambda(fake_model))
    question = generate_question(
        service,
        role="Data Analyst",
        skills="SQL",
        experience_level="Intermediate",
        difficulty="Medium",
        interview_type="Technical",
        company_focus="",
        question_number=1,
        question_count=5,
        previous_questions="",
        chat_history=[],
        previous_answer="",
    )
    evaluation = evaluate_answer(
        service,
        role="Data Analyst",
        experience_level="Intermediate",
        interview_type="Technical",
        question=question,
        answer="I used SQL.",
    )

    assert question == "How would you use SQL to validate a data pipeline?"
    assert evaluation.overall_score == 72
    assert len(prompts) == 2
    assert "I used SQL." in str(prompts[1])


def test_prompt_templates_have_explicit_workflow_inputs():
    assert set(QUESTION_GENERATION_PROMPT.input_variables) == {
        "role",
        "skills",
        "experience_level",
        "difficulty",
        "interview_type",
        "company_focus",
        "question_number",
        "question_count",
        "previous_questions",
        "previous_answer",
    }
    assert "chat_history" in QUESTION_GENERATION_PROMPT.optional_variables
    assert set(FOLLOW_UP_QUESTION_PROMPT.input_variables) == {
        "role",
        "experience_level",
        "difficulty",
        "interview_type",
        "last_question",
        "previous_answer",
        "previous_questions",
    }
    assert "chat_history" in FOLLOW_UP_QUESTION_PROMPT.optional_variables
    assert set(ANSWER_EVALUATION_PROMPT.input_variables) == {
        "role",
        "experience_level",
        "interview_type",
        "question",
        "answer",
        "short_answer_note",
        "format_feedback",
    }
    assert set(FINAL_ANALYSIS_PROMPT.input_variables) == {
        "role",
        "experience_level",
        "evaluations",
        "format_feedback",
    }
    assert set(LEARNING_RECOMMENDATIONS_PROMPT.input_variables) == {
        "role",
        "experience_level",
        "answer_feedback",
        "format_feedback",
    }


def test_langchain_history_preserves_interviewer_and_candidate_turns():
    history = build_chat_history(
        [
            ("Describe your approach to a difficult problem.", "I break it into smaller steps."),
            ("What would you do next?", ""),
        ]
    )

    assert [(message.type, message.content) for message in history] == [
        ("ai", "Describe your approach to a difficult problem."),
        ("human", "I break it into smaller steps."),
        ("ai", "What would you do next?"),
        ("human", "I skipped that question."),
    ]
