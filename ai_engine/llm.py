"""Groq chat-model construction and explicit provider error handling."""

import re
from typing import Any

from groq import (
    APIConnectionError,
    APIError,
    APITimeoutError,
    AuthenticationError,
    RateLimitError,
)
from langchain_core.messages import BaseMessage
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import Runnable
from langchain_groq import ChatGroq

from config.settings import DEFAULT_MODEL, GROQ_API_BASE_URL, Settings


class AIServiceError(RuntimeError):
    """Base error for a user-facing AI service failure."""


class AIConfigurationError(AIServiceError):
    """Raised when the Groq client cannot be configured."""


class AIResponseError(AIServiceError):
    """Raised when the model does not return usable text."""


class AIRateLimitError(AIServiceError):
    """Raised when Groq rejects the request because of rate limits."""


class AITimeoutError(AIServiceError):
    """Raised when a Groq request exceeds its configured timeout."""


class AIProviderError(AIServiceError):
    """Raised for other explicit Groq provider or connection failures."""


def create_chat_model(settings: Settings | None = None) -> ChatGroq:
    """Create the configured Groq model, refusing to run without an API key."""
    config = settings or Settings.from_env()
    if not config.groq_api_key:
        raise AIConfigurationError(
            "Groq API key is missing. Add GROQ_API_KEY to your .env file "
            "to enable AI interview practice."
        )
    return ChatGroq(
        model=config.groq_model,
        api_key=config.groq_api_key,
        base_url=GROQ_API_BASE_URL,
        temperature=0.3,
        timeout=config.groq_request_timeout,
        max_retries=config.groq_max_retries,
    )


class AIService:
    """Invoke LangChain prompt templates using one shared Groq chat model."""

    def __init__(
        self,
        settings: Settings | None = None,
        *,
        llm: Runnable[Any, BaseMessage] | None = None,
    ) -> None:
        self._settings = settings
        self._llm = llm

    def _get_llm(self) -> Runnable[Any, BaseMessage]:
        if self._llm is None:
            self._settings = self._settings or Settings.from_env()
            self._llm = create_chat_model(self._settings)
        return self._llm

    def _provider_error_message(self, exc: Exception) -> str:
        model = self._settings.groq_model if self._settings else DEFAULT_MODEL
        status_code = getattr(exc, "status_code", None)
        status = f" (HTTP {status_code})" if status_code else ""
        body = getattr(exc, "body", None)

        if isinstance(body, dict):
            provider_error = body.get("error", body)
            if isinstance(provider_error, dict):
                detail = provider_error.get("message") or provider_error.get("detail")
                code = provider_error.get("code")
                if detail and code:
                    detail = f"{detail} (code: {code})"
                elif not detail:
                    detail = code
            elif isinstance(provider_error, str):
                detail = provider_error
            else:
                detail = None
        elif isinstance(body, str):
            detail = body
        else:
            detail = None

        if not detail:
            detail = getattr(exc, "message", None) or str(exc)
        detail = str(detail)
        if self._settings and self._settings.groq_api_key:
            detail = detail.replace(self._settings.groq_api_key, "[REDACTED]")
        detail = re.sub(r"\b(?:gsk_|sk-)[A-Za-z0-9_-]+\b", "[REDACTED]", detail)
        detail = detail.strip() or exc.__class__.__name__
        return f"model '{model}'{status}: {detail}"

    def invoke(
        self, prompt: ChatPromptTemplate, values: dict[str, Any]
    ) -> str:
        """Format and invoke one prompt, returning validated non-empty text."""
        try:
            response = (prompt | self._get_llm()).invoke(values)
        except RateLimitError as exc:
            raise AIRateLimitError(
                "Groq is temporarily rate-limiting requests for "
                f"{self._provider_error_message(exc)}. Wait a moment and retry."
            ) from exc
        except APITimeoutError as exc:
            raise AITimeoutError(
                f"The Groq request for {self._provider_error_message(exc)} "
                "timed out. Please retry in a moment."
            ) from exc
        except AuthenticationError as exc:
            raise AIConfigurationError(
                "Groq authentication failed for "
                f"{self._provider_error_message(exc)}. Check GROQ_API_KEY "
                "in your .env file."
            ) from exc
        except APIConnectionError as exc:
            raise AIProviderError(
                f"Could not connect to Groq for {self._provider_error_message(exc)}. "
                "Check your connection and retry."
            ) from exc
        except APIError as exc:
            raise AIProviderError(
                "Groq could not complete the request for "
                f"{self._provider_error_message(exc)}. Please retry."
            ) from exc

        content = response.content
        if not isinstance(content, str) or not content.strip():
            raise AIResponseError("Groq returned an empty or non-text response.")
        return content.strip()
