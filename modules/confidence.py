"""Self-reported confidence capture and non-demo history visualization."""

import sqlite3
from pathlib import Path

import plotly.graph_objects as go
import streamlit as st

from config.surveys import CONFIDENCE_LABELS
from database.db import (
    get_confidence_history,
    get_session_confidence,
    save_confidence,
)


def render_post_interview_confidence(
    *,
    session: dict,
    user_id: int,
    db_path: str | Path,
) -> None:
    """Collect and show the participant's post-session confidence rating."""
    confidence = get_session_confidence(session["id"], user_id, db_path=db_path)
    before_rating = confidence.get("before")
    after_rating = confidence.get("after")
    st.markdown("#### Self-reported confidence")
    st.caption(
        "Your reflection about attending a real interview—not an objective measure of performance."
    )
    if session["is_demo"]:
        st.caption(
            "Demo session: these self-reported ratings are kept separate from real-session confidence history."
        )

    if after_rating is None:
        with st.form(f"post-confidence-{session['id']}"):
            rating = st.radio(
                "After this practice, how confident do you feel about attending a real interview for this role?",
                options=(1, 2, 3, 4, 5),
                format_func=lambda value: f"{value} · {CONFIDENCE_LABELS[value]}",
                horizontal=True,
                index=None,
                key=f"post-confidence-rating-{session['id']}",
            )
            submitted = st.form_submit_button(
                "Save post-interview confidence",
                type="primary",
                use_container_width=True,
            )
            if submitted:
                if rating is None:
                    st.error("Choose a confidence rating from 1 to 5.")
                else:
                    try:
                        save_confidence(
                            user_id,
                            session["id"],
                            stage="after",
                            rating=rating,
                            db_path=db_path,
                        )
                    except (ValueError, sqlite3.Error) as exc:
                        st.error(f"Couldn’t save your confidence rating: {exc}")
                    else:
                        st.rerun()
        return

    if before_rating is None:
        st.warning("A before-session confidence rating was not recorded.")
        st.metric(
            "After practice",
            f"{after_rating} · {CONFIDENCE_LABELS[after_rating]}",
        )
        return

    change = after_rating - before_rating
    change_label = f"{change:+d}" if change else "0"
    before, after, difference = st.columns(3)
    before.metric(
        "Before practice",
        f"{before_rating} · {CONFIDENCE_LABELS[before_rating]}",
    )
    after.metric(
        "After practice",
        f"{after_rating} · {CONFIDENCE_LABELS[after_rating]}",
    )
    difference.metric("Change", change_label)
    st.caption("Confidence is self-reported; a change is not an objective performance score.")


def render_confidence_history(user_id: int, db_path: str | Path) -> None:
    """Show confidence trends for completed real sessions only."""
    st.markdown(
        """
        <div class="dashboard-section-heading confidence-history-heading">
          <div><div class="eyebrow">SELF-REPORTED CONFIDENCE</div><h2>How confidence changes over time</h2></div>
          <span class="chart-caption">Before and after practice · scale of 1–5</span>
        </div>
        """,
        unsafe_allow_html=True,
    )
    records = get_confidence_history(user_id, db_path=db_path)
    st.caption(
        "This chart reflects participants’ own reported confidence, not interview ability or objective performance. Demo sessions are excluded."
    )
    if not records:
        st.markdown(
            """
            <div class="dashboard-empty-chart confidence-empty">
              <span class="empty-chart-icon">◷</span>
              <strong>Confidence history starts after your first completed real session.</strong>
              <p>Submit both before- and after-practice self-ratings to add a session.</p>
            </div>
            """,
            unsafe_allow_html=True,
        )
        return

    latest = records[-1]
    latest_columns = st.columns(3)
    latest_columns[0].metric("Latest before", f"{latest['before_rating']}/5")
    latest_columns[1].metric("Latest after", f"{latest['after_rating']}/5")
    latest_columns[2].metric("Latest change", f"{latest['change']:+d}")

    figure = go.Figure()
    custom_data = [
        [record["role"], record["session_id"]]
        for record in records
    ]
    x_values = [record["completed_at"][:10] for record in records]
    for stage, label, color in (
        ("before_rating", "Before practice", "#6ea8fe"),
        ("after_rating", "After practice", "#b39aff"),
    ):
        figure.add_trace(
            go.Scatter(
                x=x_values,
                y=[record[stage] for record in records],
                customdata=custom_data,
                mode="lines+markers",
                name=label,
                line={"color": color, "width": 2},
                marker={"color": color, "size": 8},
                hovertemplate=(
                    "%{customdata[0]}<br>%{x}<br>"
                    + label
                    + ": %{y}/5<extra></extra>"
                ),
            )
        )
    figure.update_layout(
        height=270,
        margin={"l": 8, "r": 12, "t": 18, "b": 8},
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font={"color": "#9ba3b7", "family": "DM Sans, sans-serif", "size": 10},
        hoverlabel={"bgcolor": "#191d2a", "font": {"color": "#f2f4fb"}},
        legend={"orientation": "h", "y": 1.12, "x": 0},
        xaxis={"showgrid": False, "linecolor": "rgba(165,177,209,.13)"},
        yaxis={
            "range": [0.5, 5.5],
            "tickvals": [1, 2, 3, 4, 5],
            "title": "Self-rating",
            "gridcolor": "rgba(165,177,209,.09)",
            "zeroline": False,
        },
    )
    st.plotly_chart(figure, use_container_width=True, config={"displayModeBar": False})
