"""Completed-session report, evidence-based charts, and learning plan."""

import html
import json
import sqlite3
from pathlib import Path

import plotly.graph_objects as go
import streamlit as st

from ai_engine.interview_manager import InterviewManager
from ai_engine.llm import AIService, AIServiceError
from config.settings import Settings
from database.db import (
    get_interview_snapshot,
    get_latest_user,
    get_session_report,
    save_session_report,
)
from utils.pdf_generator import generate_report_pdf


DIMENSION_LABELS = {
    "relevance": "Relevance",
    "technical_accuracy": "Technical accuracy",
    "depth": "Depth",
    "clarity": "Clarity",
    "structure": "Structure",
    "completeness": "Completeness",
}


def build_report_metrics(snapshot: dict) -> dict:
    """Calculate report metrics only from saved answers and evaluations."""
    questions = snapshot["questions"]
    is_demo = bool(snapshot["session"]["is_demo"])
    answered = [
        item
        for item in questions
        if item["answer_id"] is not None and not item["was_skipped"]
    ]
    skipped = [item for item in questions if item["was_skipped"]]
    evaluated = (
        []
        if is_demo
        else [item for item in answered if item["evaluation_id"] is not None]
    )
    scores = [item["overall_score"] for item in evaluated]
    average_score = sum(scores) / len(scores) if scores else None

    dimension_values: dict[str, list[float]] = {}
    for item in evaluated:
        for name, value in item["dimension_scores"].items():
            if isinstance(value, (int, float)) and not isinstance(value, bool):
                dimension_values.setdefault(name, []).append(float(value))
    dimension_averages = {
        name: sum(values) / len(values)
        for name, values in dimension_values.items()
        if values
    }

    durations = [
        item["duration_seconds"]
        for item in answered
        if item["duration_seconds"] is not None
    ]
    best_answer = (
        min(evaluated, key=lambda item: (-item["overall_score"], item["sequence_number"]))
        if evaluated
        else None
    )
    worst_answer = (
        min(evaluated, key=lambda item: (item["overall_score"], item["sequence_number"]))
        if evaluated
        else None
    )
    return {
        "questions_answered": len(answered),
        "questions_skipped": len(skipped),
        "evaluated_answers": len(evaluated),
        "overall_score": round(average_score) if average_score is not None else None,
        "average_score": average_score,
        "average_response_seconds": (
            sum(durations) / len(durations) if durations else None
        ),
        "dimension_averages": dimension_averages,
        "technical_performance": _mean_dimensions(
            dimension_averages, ("technical_accuracy", "depth")
        ),
        "communication_performance": _mean_dimensions(
            dimension_averages, ("clarity", "structure")
        ),
        "question_scores": [
            {
                "sequence_number": item["sequence_number"],
                "score": item["overall_score"],
            }
            for item in evaluated
        ],
        "best_answer": best_answer,
        "worst_answer": worst_answer,
    }


def _mean_dimensions(
    dimension_averages: dict[str, float], names: tuple[str, ...]
) -> float | None:
    scores = [dimension_averages[name] for name in names if name in dimension_averages]
    return sum(scores) / len(scores) if scores else None


def _unique_items(items: list[str]) -> list[str]:
    unique: list[str] = []
    seen: set[str] = set()
    for item in items:
        cleaned = item.strip()
        key = cleaned.casefold()
        if cleaned and key not in seen:
            unique.append(cleaned)
            seen.add(key)
    return unique


def _report_evidence(snapshot: dict) -> list[dict]:
    return [
        {
            "question": item["question_text"],
            "answer": item["answer_text"],
            "overall_score": item["overall_score"],
            "dimension_scores": item["dimension_scores"],
            "feedback": item["feedback_json"],
        }
        for item in snapshot["questions"]
        if item["answer_id"] is not None
        and not item["was_skipped"]
        and item["evaluation_id"] is not None
    ]


def _ensure_ai_report(
    snapshot: dict,
    profile: dict,
    settings: Settings,
    db_path: str | Path,
) -> tuple[dict, str | None]:
    session = snapshot["session"]
    cached = get_session_report(session["id"], profile["id"], db_path=db_path) or {
        "final_analysis": None,
        "learning_plan": None,
        "updated_at": None,
    }
    if session["is_demo"]:
        return cached, None
    evidence = _report_evidence(snapshot)
    if not evidence:
        return cached, None
    if cached["final_analysis"] is not None and cached["learning_plan"] is not None:
        return cached, None
    if not settings.groq_api_key:
        return cached, (
            "GROQ_API_KEY is not configured. Saved evaluation charts remain available, "
            "but the missing personalized report section requires the API key."
        )

    manager = InterviewManager(AIService(settings))
    evidence_json = json.dumps(evidence, ensure_ascii=False)
    try:
        if cached["final_analysis"] is None:
            analysis = manager.analyze(
                role=session["role"],
                experience_level=session["experience_level"],
                evaluations=evidence_json,
            )
            cached = save_session_report(
                session["id"],
                profile["id"],
                final_analysis=analysis.model_dump(),
                db_path=db_path,
            )
        if cached["learning_plan"] is None:
            learning_plan = manager.recommend(
                role=session["role"],
                experience_level=session["experience_level"],
                answer_feedback=evidence_json,
            )
            cached = save_session_report(
                session["id"],
                profile["id"],
                learning_plan=learning_plan.model_dump(),
                db_path=db_path,
            )
    except AIServiceError as exc:
        return cached, str(exc)
    except (ValueError, sqlite3.Error) as exc:
        return cached, f"Couldn’t save the personalized report: {exc}"
    return cached, None


def _score_figure(metrics: dict) -> go.Figure:
    items = metrics["question_scores"]
    figure = go.Figure(
        go.Bar(
            x=[item["sequence_number"] for item in items],
            y=[item["score"] for item in items],
            marker_color="#a78bfa",
            hovertemplate="Question %{x}<br>Score %{y}/100<extra></extra>",
        )
    )
    figure.update_layout(
        template="plotly_dark",
        title="Score by answer",
        xaxis_title="Question",
        yaxis_title="Score",
        yaxis=dict(range=[0, 100]),
        height=300,
        margin=dict(l=20, r=16, t=48, b=35),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font=dict(color="#c8cede"),
        showlegend=False,
    )
    return figure


def _dimension_figure(metrics: dict) -> go.Figure:
    dimensions = metrics["dimension_averages"]
    palette = ["#a78bfa", "#6ea8fe", "#66d9e8", "#e48abf", "#e8ad76", "#81cbb0"]
    figure = go.Figure(
        go.Bar(
            x=[DIMENSION_LABELS.get(name, name.replace("_", " ").title()) for name in dimensions],
            y=list(dimensions.values()),
            marker_color=[palette[index % len(palette)] for index in range(len(dimensions))],
            hovertemplate="%{x}<br>Average %{y:.1f}/100<extra></extra>",
        )
    )
    figure.update_layout(
        template="plotly_dark",
        title="Average answer dimensions",
        yaxis=dict(range=[0, 100], title="Score"),
        height=300,
        margin=dict(l=20, r=16, t=48, b=75),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font=dict(color="#c8cede"),
        showlegend=False,
    )
    return figure


def _render_header() -> None:
    st.markdown(
        """
        <header class="topbar app-topbar">
          <a class="brand" href="?page=landing#top" target="_self"><span class="brand-mark">✦</span><span>interview<span class="brand-iq">iq</span></span></a>
          <nav class="topnav" aria-label="Main navigation">
            <a href="?page=dashboard" target="_self">Dashboard</a><a href="?page=onboarding" target="_self">Profile</a><a href="?page=roles" target="_self" class="nav-current">Practice</a><a href="?page=history" target="_self">History</a><a href="?page=settings" target="_self">Settings &amp; export</a>
          </nav>
          <a class="nav-cta" href="?page=dashboard" target="_self">Dashboard <span aria-hidden="true">↗</span></a>
        </header>
        """,
        unsafe_allow_html=True,
    )


def render_results_page(
    settings: Settings,
    profile: dict | None = None,
) -> None:
    """Render a saved completed-session report and PDF download."""
    _render_header()
    profile = profile or get_latest_user(db_path=settings.database_path)
    if profile is None:
        st.warning("Set up your profile before opening an interview report.")
        return

    raw_session_id = st.query_params.get("session_id")
    try:
        session_id = int(raw_session_id) if raw_session_id else 0
    except (TypeError, ValueError):
        session_id = 0
    if session_id < 1:
        st.warning("No saved interview session was selected.")
        return

    snapshot = get_interview_snapshot(
        session_id, profile["id"], db_path=settings.database_path
    )
    if snapshot is None:
        st.warning("This session was not found for the current profile.")
        return

    session = snapshot["session"]
    if session["status"] != "completed":
        st.info("Finish the interview before opening its report.")
        st.markdown(
            f'<a class="button-primary" href="?page=interview&session_id={session_id}" target="_self">Return to interview <span>→</span></a>',
            unsafe_allow_html=True,
        )
        return

    metrics = build_report_metrics(snapshot)
    report: dict = {
        "session": session,
        "metrics": metrics,
        "questions": snapshot["questions"],
        "final_analysis": None,
        "learning_plan": None,
    }
    report_error = None
    if not session["is_demo"] and metrics["evaluated_answers"]:
        cached_report, report_error = _ensure_ai_report(
            snapshot, profile, settings, settings.database_path
        )
        report["final_analysis"] = cached_report["final_analysis"]
        report["learning_plan"] = cached_report["learning_plan"]

    mode = "DEMO PRACTICE REPORT" if session["is_demo"] else "INTERVIEW REPORT"
    st.markdown(
        f'<div class="results-title"><div class="eyebrow">{mode}</div><h1>{html.escape(session["role"])} interview report</h1><p>{html.escape(session["experience_level"])} · {html.escape(session["difficulty"])} · {html.escape(session["interview_type"])}</p></div>',
        unsafe_allow_html=True,
    )
    if session["is_demo"]:
        st.warning(
            "DEMO REPORT · Sample questions and your practice answers only. "
            "This is not an AI evaluation and is excluded from real statistics."
        )

    average_label = (
        f"{metrics['average_score']:.1f}"
        if metrics["average_score"] is not None
        else "—"
    )
    overall_label = (
        f"{metrics['overall_score']}/100"
        if metrics["overall_score"] is not None
        else "—"
    )
    response_time = metrics["average_response_seconds"]
    time_label = (
        f"{int(response_time // 60):02d}:{int(response_time % 60):02d}"
        if response_time is not None
        else "—"
    )
    kpi_columns = st.columns(4)
    kpi_columns[0].metric("Overall score", overall_label)
    kpi_columns[1].metric("Questions answered", metrics["questions_answered"])
    kpi_columns[2].metric("Average answer score", average_label)
    kpi_columns[3].metric("Average response time", time_label)
    st.caption(
        "Scores average submitted, evaluated answers only. Skipped and unevaluated answers are not scored."
    )

    if metrics["best_answer"] is not None:
        best, worst = st.columns(2)
        with best:
            st.markdown("#### Strongest answer")
            st.markdown(
                f"**Q{metrics['best_answer']['sequence_number']} · {metrics['best_answer']['overall_score']}/100**"
            )
            st.write(metrics["best_answer"]["answer_text"])
        with worst:
            st.markdown("#### Answer to revisit")
            st.markdown(
                f"**Q{metrics['worst_answer']['sequence_number']} · {metrics['worst_answer']['overall_score']}/100**"
            )
            st.write(metrics["worst_answer"]["answer_text"])
    else:
        if session["is_demo"]:
            st.info("Demo Mode answers are practice content, not evaluated results.")
        else:
            st.info("No evaluated answers are available for this session.")

    if metrics["question_scores"]:
        st.markdown(
            '<div class="results-section-heading"><div class="eyebrow">YOUR PERFORMANCE</div><h2>Patterns across your answers</h2></div>',
            unsafe_allow_html=True,
        )
        score_column, dimension_column = st.columns(2)
        score_column.plotly_chart(
            _score_figure(metrics),
            use_container_width=True,
            config={"displayModeBar": False},
        )
        dimension_column.plotly_chart(
            _dimension_figure(metrics),
            use_container_width=True,
            config={"displayModeBar": False},
        )
        technical = metrics["technical_performance"]
        communication = metrics["communication_performance"]
        if technical is not None or communication is not None:
            technical_label = (
                f"{technical:.1f}/100" if technical is not None else "Not enough data"
            )
            communication_label = (
                f"{communication:.1f}/100"
                if communication is not None
                else "Not enough data"
            )
            left, right = st.columns(2)
            left.metric("Technical performance", technical_label)
            right.metric("Communication performance", communication_label)
            st.caption(
                "Technical performance averages technical accuracy and depth; communication performance averages clarity and structure."
            )

    analysis = report["final_analysis"]
    strengths = (
        analysis["strengths"]
        if analysis
        else _unique_items(
            [
                item
                for question in metrics["question_scores"]
                for saved in snapshot["questions"]
                if saved["sequence_number"] == question["sequence_number"]
                for item in (saved["feedback_json"] or {}).get("what_went_well", [])
            ]
        )
    )
    improvement_areas = (
        analysis["improvement_areas"]
        if analysis
        else _unique_items(
            [
                item
                for question in metrics["question_scores"]
                for saved in snapshot["questions"]
                if saved["sequence_number"] == question["sequence_number"]
                for item in (
                    (saved["feedback_json"] or {}).get("what_was_missing", [])
                    + (saved["feedback_json"] or {}).get(
                        "mistakes_or_inaccuracies", []
                    )
                )
            ]
        )
    )
    if strengths or improvement_areas:
        st.markdown(
            '<div class="results-section-heading"><div class="eyebrow">EVIDENCE FROM YOUR ANSWERS</div><h2>Strengths and opportunities</h2></div>',
            unsafe_allow_html=True,
        )
        left, right = st.columns(2)
        with left:
            st.markdown("#### Strengths")
            for item in strengths:
                st.markdown(f"- {item}")
        with right:
            st.markdown("#### Improvement areas")
            for item in improvement_areas:
                st.markdown(f"- {item}")

    if analysis:
        st.markdown("#### Session analysis")
        st.write(analysis["overall_summary"])
        if analysis["technical_performance"]:
            st.caption(f"Technical: {analysis['technical_performance']}")
        if analysis["communication_performance"]:
            st.caption(f"Communication: {analysis['communication_performance']}")
        if analysis["next_steps"]:
            st.markdown("#### Suggested next steps")
            for item in analysis["next_steps"]:
                st.markdown(f"- {item}")

    learning_plan = report["learning_plan"]
    if learning_plan:
        st.markdown(
            '<div class="results-section-heading"><div class="eyebrow">YOUR NEXT PRACTICE</div><h2>A learning plan based on your answers</h2></div>',
            unsafe_allow_html=True,
        )
        plan_columns = st.columns(2)
        with plan_columns[0]:
            st.markdown("#### Topics")
            for item in learning_plan["topics"]:
                st.markdown(f"- {item}")
            st.markdown("#### Concepts to revisit")
            for item in learning_plan["concepts"]:
                st.markdown(f"- {item}")
        with plan_columns[1]:
            st.markdown("#### Practice questions")
            for item in learning_plan["sample_questions"]:
                st.markdown(f"- {item}")
        st.markdown("#### Next practice session")
        st.info(learning_plan["next_practice_session"])
    elif metrics["evaluated_answers"] and report_error:
        st.warning(report_error)
        if st.button(
            "Retry personalized report generation",
            type="primary",
            key=f"retry-report-{session_id}",
        ):
            st.rerun()
    elif metrics["evaluated_answers"]:
        st.info("The personalized learning plan could not be generated yet.")

    st.markdown("#### Session answers")
    for question in snapshot["questions"]:
        title = f"Question {question['sequence_number']}: {question['question_text']}"
        with st.expander(title):
            if question["was_skipped"]:
                st.caption("Skipped")
            else:
                st.markdown("**Your answer**")
                st.write(question["answer_text"])
            if question["feedback_json"]:
                st.markdown("**Saved evaluation**")
                st.write(question["feedback_json"].get("what_went_well", []))

    pdf_bytes = generate_report_pdf(report)
    st.download_button(
        "Download PDF report",
        data=pdf_bytes,
        file_name=f"interviewiq-report-{session_id}.pdf",
        mime="application/pdf",
        type="primary",
    )
    st.markdown(
        '<a class="text-link" href="?page=dashboard" target="_self">Back to dashboard →</a>',
        unsafe_allow_html=True,
    )
