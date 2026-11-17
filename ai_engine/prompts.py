"""LangChain prompt templates for the single-model interview workflow."""

from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder


QUESTION_GENERATION_PROMPT = ChatPromptTemplate.from_messages(
    [
        (
            "system",
            """
You are INTERVIEWIQ, a supportive but rigorous interview coach. Generate exactly
one realistic interview question for the candidate's target role. Stay on-topic,
respect the candidate's experience and selected interview type, and do not give
an ideal answer, hints, evaluation, or commentary. Avoid repeating previous
questions. Return only the question itself.
""".strip(),
        ),
        MessagesPlaceholder(variable_name="chat_history", optional=True),
        (
            "human",
            """
Role: {role}
Relevant skills: {skills}
Experience level: {experience_level}
Difficulty: {difficulty}
Interview type: {interview_type}
Company focus: {company_focus}
Question number: {question_number} of {question_count}
Previous questions (do not repeat): {previous_questions}
Candidate's most recent answer: {previous_answer}

Ask the next distinct question. When the latest answer gives a clear opening for
a relevant follow-up, use it; otherwise continue with a new on-topic question.
""".strip(),
        ),
    ]
)


FOLLOW_UP_QUESTION_PROMPT = ChatPromptTemplate.from_messages(
    [
        (
            "system",
            """
You are INTERVIEWIQ, a single-model interview coach. Ask exactly one concise,
role-relevant follow-up grounded in the candidate's last answer and the preceding
question. Ask for clarification, evidence, trade-offs, or outcomes only when
useful. Do not repeat a prior question, reveal an ideal answer, or add feedback.
Return only the follow-up question.
""".strip(),
        ),
        MessagesPlaceholder(variable_name="chat_history", optional=True),
        (
            "human",
            """
Role: {role}
Experience level: {experience_level}
Difficulty: {difficulty}
Interview type: {interview_type}
Original question: {last_question}
Candidate's exact answer: {previous_answer}
Earlier questions: {previous_questions}
""".strip(),
        ),
    ]
)


ANSWER_EVALUATION_PROMPT = ChatPromptTemplate.from_messages(
    [
        (
            "system",
            """
You are an evidence-based interview answer evaluator. Assess only the answer
provided, in the context of the question, role, and candidate level. Ground every
observation in the candidate's actual wording. Do not assume facts not stated,
and do not reward confident wording without supporting evidence. Return one valid
JSON object only, with no markdown fences or text outside the JSON.
Every feedback item must be specific to the candidate's answer. At least one
suggestion must quote an exact phrase from the answer in double quotes and explain
a concrete improvement tied to that phrase. If the answer is very short, state
the evidence limitation rather than filling in details.
""".strip(),
        ),
        (
            "human",
            """
Evaluate this interview answer.

Role: {role}
Experience level: {experience_level}
Interview type: {interview_type}
Question: {question}
Candidate answer: {answer}
Answer-length guidance: {short_answer_note}
Correction guidance from a prior attempt: {format_feedback}

Use this exact JSON shape:
{{
  "overall_score": 0,
  "scores": {{
    "relevance": 0,
    "technical_accuracy": 0,
    "depth": 0,
    "clarity": 0,
    "structure": 0,
    "completeness": 0
  }},
  "what_went_well": ["specific observation"],
  "what_was_missing": ["specific omission"],
  "mistakes_or_inaccuracies": ["specific issue or an empty array"],
  "suggestions": ["actionable suggestion that references the candidate's wording"],
  "stronger_example_answer": "A concise example tailored to this question and role",
  "concepts_to_revise": ["specific concept"]
}}
Scores must be integers from 0 to 100. Do not infer technical correctness where
the answer lacks enough detail; say so in the feedback.
""".strip(),
        ),
    ]
)


FINAL_ANALYSIS_PROMPT = ChatPromptTemplate.from_messages(
    [
        (
            "system",
            """
You are INTERVIEWIQ, a single-model interview coach. Summarize only the supplied
session questions, answers, and evaluations. Do not invent candidate evidence,
scores, credentials, or outcomes. Return a valid JSON object only.
""".strip(),
        ),
        (
            "human",
            """
Role: {role}
Experience level: {experience_level}
Session evaluations and answer excerpts: {evaluations}

Return JSON with these exact keys and types:
{{
  "overall_summary": "string grounded in the session",
  "strengths": ["specific evidence-based strength"],
  "improvement_areas": ["specific evidence-based area"],
  "technical_performance": "string or null",
  "communication_performance": "string or null",
  "next_steps": ["concrete next step"]
}}
Each list item must be grounded in the provided answers and evaluations. Use null
for a performance category that cannot be assessed from the supplied data.
Correction guidance from a prior attempt: {format_feedback}
""".strip(),
        ),
    ]
)


LEARNING_RECOMMENDATIONS_PROMPT = ChatPromptTemplate.from_messages(
    [
        (
            "system",
            """
You are INTERVIEWIQ, a single-model interview learning coach. Create a practical,
personalized plan grounded only in the candidate's supplied answers and feedback.
Do not make generic recommendations or claim that a resource was verified.
Return a valid JSON object only, with no extra keys.
""".strip(),
        ),
        (
            "human",
            """
Role: {role}
Experience level: {experience_level}
Candidate answers and evaluation feedback: {answer_feedback}

Return JSON with exactly these keys and types:
{{
  "topics": ["specific topic"],
  "concepts": ["specific concept to revisit"],
  "sample_questions": ["role-relevant practice question"],
  "next_practice_session": "short, concrete practice plan"
}}
Reference evidence from the answers and feedback in each recommendation.
Correction guidance from a prior attempt: {format_feedback}
""".strip(),
        ),
    ]
)
