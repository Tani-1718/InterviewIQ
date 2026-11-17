"""System Usability Scale-style questionnaire and standard scoring."""

import sqlite3
from collections.abc import Sequence
from pathlib import Path

import plotly.graph_objects as go
import streamlit as st

from config.surveys import SUS_BENCHMARK, SUS_ITEMS, SUS_SCALE_OPTIONS
from database.db import get_sus_responses, save_sus_responses


def calculate_sus_score(responses: Sequence[int]) -> float:
    """Calculate the standard 0–100 SUS score from ten 1–5 responses."""
    if len(responses) != 10 or any(
        not isinstance(value, int)
        or isinstance(value, bool)
        or value not in range(1, 6)
        for value in responses
    ):
        raise ValueError("SUS responses must contain exactly 10 integers from 1 to 5.")
    contribution = sum(
        response - 1 if item_number % 2 else 5 - response
        for item_number, response in enumerate(responses, start=1)
    )
    return contribution * 2.5


def _render_saved_score(score: float, *, is_demo: bool) -> None:
    delta = score - SUS_BENCHMARK
    st.metric(
        "SUS score",
        f"{score:.1f}/100",
        delta=f"{delta:+.1f} vs. {SUS_BENCHMARK} benchmark",
    )
    figure = go.Figure(
        go.Bar(
            x=[score],
            y=["Usability score"],
            orientation="h",
            marker_color="#a78bfa",
            hovertemplate="Score: %{x:.1f}/100<extra></extra>",
        )
    )
    figure.add_vline(
        x=SUS_BENCHMARK,
        line_color="#66d9e8",
        line_dash="dash",
        annotation_text=f"{SUS_BENCHMARK} benchmark",
        annotation_position="top",
    )
    figure.update_layout(
        template="plotly_dark",
        height=150,
        margin={"l": 8, "r": 12, "t": 42, "b": 8},
        xaxis={"range": [0, 100], "title": "SUS score"},
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font={"color": "#c8cede"},
        showlegend=False,
    )
    st.plotly_chart(figure, use_container_width=True, config={"displayModeBar": False})
    st.caption(
        "68 is the commonly used SUS reference benchmark; it is not a pass/fail threshold."
    )
    if is_demo:
        st.caption(
            "Demo-session SUS responses are labeled separately and excluded from real-session research exports."
        )


def render_sus_questionnaire(
    *,
    session: dict,
    user_id: int,
    db_path: str | Path,
) -> None:
    """Collect ten post-session usability responses once, then show the score."""
    st.markdown("#### Usability questionnaire")
    st.caption(
        "Adapted, paraphrased item wording; standard SUS scoring is applied. "
        "For validated research comparisons, use the authorized original instrument."
    )
    try:
        saved_responses = get_sus_responses(
            session["id"], user_id, db_path=db_path
        )
    except ValueError as exc:
        st.error(f"Couldn’t load saved usability responses: {exc}")
        return
    if saved_responses is not None:
        _render_saved_score(
            calculate_sus_score(saved_responses),
            is_demo=bool(session["is_demo"]),
        )
        return

    with st.form(f"sus-questionnaire-{session['id']}"):
        response_options: list[str | None] = []
        for item_number, prompt in enumerate(SUS_ITEMS, start=1):
            response_options.append(
                st.radio(
                    f"{item_number}. {prompt}",
                    options=SUS_SCALE_OPTIONS,
                    horizontal=True,
                    index=None,
                    key=f"sus-{session['id']}-{item_number}",
                )
            )
        submitted = st.form_submit_button(
            "Save usability responses",
            type="primary",
            use_container_width=True,
        )
        if submitted:
            if any(response is None for response in response_options):
                st.error("Select a response for all ten statements.")
            else:
                responses = [
                    SUS_SCALE_OPTIONS.index(response) + 1
                    for response in response_options
                    if response is not None
                ]
                try:
                    save_sus_responses(
                        session["id"],
                        responses,
                        user_id=user_id,
                        db_path=db_path,
                    )
                except (ValueError, sqlite3.Error) as exc:
                    st.error(f"Couldn’t save usability responses: {exc}")
                else:
                    st.rerun()
