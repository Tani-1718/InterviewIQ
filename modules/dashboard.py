"""Database-backed dashboard and progress views."""

import html
from pathlib import Path

import plotly.graph_objects as go
import streamlit as st

from database.db import get_dashboard_data
from modules.confidence import render_confidence_history


def _dashboard_header() -> None:
    st.markdown(
        """
        <header class="topbar app-topbar">
          <a class="brand" href="?page=landing#top" target="_self"><span class="brand-mark">✦</span><span>interview<span class="brand-iq">iq</span></span></a>
          <nav class="topnav" aria-label="Main navigation">
            <a href="?page=dashboard" target="_self" class="nav-current">Dashboard</a>
            <a href="?page=onboarding" target="_self">Profile</a>
            <a href="?page=history" target="_self">History</a>
            <a href="?page=settings" target="_self">Settings &amp; export</a>
          </nav>
          <a class="nav-cta" href="?page=landing" target="_self">Home <span aria-hidden="true">↗</span></a>
        </header>
        """,
        unsafe_allow_html=True,
    )


def render_dashboard(profile: dict | None, db_path: str | Path) -> None:
    """Render personal practice metrics and honest empty states."""
    _dashboard_header()
    if profile is None:
        st.markdown(
            """
            <section class="empty-dashboard">
              <span class="empty-mark">✦</span>
              <div class="eyebrow">YOUR SPACE TO GROW</div>
              <h1>Let’s start with you.</h1>
              <p>Set up your profile to personalize practice and track your progress here.</p>
              <a class="button-primary" href="?page=onboarding" target="_self">Set up your profile <span>→</span></a>
            </section>
            """,
            unsafe_allow_html=True,
        )
        return

    data = get_dashboard_data(profile["id"], db_path=db_path)
    first_name = html.escape(profile["name"].split()[0])
    target_role = html.escape(profile["target_role"] or "your next role")
    st.markdown(
        f"""
        <div class="dashboard-title-row">
          <div class="page-intro dashboard-intro">
            <div class="eyebrow">YOUR PRACTICE, IN ONE PLACE</div>
            <h1>Welcome back, {first_name}.</h1>
            <p>Every practice is a step toward feeling ready for <strong>{target_role}</strong>.</p>
          </div>
          <a class="button-primary dashboard-start-link" href="?page=roles" target="_self">Start New Interview <span>→</span></a>
        </div>
        """,
        unsafe_allow_html=True,
    )

    average_score = data["average_score"]
    score_detail = (
        "Across evaluated answers" if average_score is not None else "No evaluations yet"
    )
    metrics = [
        ("Interviews completed", str(data["interviews_completed"]), "Completed practice sessions"),
        ("Average score", f"{average_score:.1f}" if average_score is not None else "—", score_detail),
        ("Questions answered", str(data["questions_answered"]), "Across non-demo sessions"),
    ]
    metric_columns = st.columns(3)
    for column, (label, value, detail) in zip(metric_columns, metrics):
        column.markdown(
            f"""
            <div class="dashboard-metric">
              <span class="metric-label">{label}</span>
              <strong>{value}</strong>
              <small>{detail}</small>
            </div>
            """,
            unsafe_allow_html=True,
        )

    left, right = st.columns([1.45, 1])
    with left:
        st.markdown(
            """
            <div class="dashboard-section-heading">
              <div><div class="eyebrow">YOUR MOMENTUM</div><h2>Progress over time</h2></div>
              <span class="chart-caption">Average evaluated score by session</span>
            </div>
            """,
            unsafe_allow_html=True,
        )
        if data["progress"]:
            progress = data["progress"]
            figure = go.Figure()
            figure.add_trace(
                go.Scatter(
                    x=[row["date"][:10] for row in progress],
                    y=[row["average_score"] for row in progress],
                    mode="lines+markers",
                    line={"color": "#9b84f6", "width": 3, "shape": "spline"},
                    marker={
                        "color": "#9b84f6",
                        "size": 8,
                        "line": {"color": "#ded5ff", "width": 1.5},
                    },
                    customdata=[[html.escape(row["role"])] for row in progress],
                    hovertemplate="%{customdata[0]}<br>%{x}<br>Score: %{y:.1f}<extra></extra>",
                    name="Average score",
                )
            )
            figure.update_layout(
                height=270,
                margin={"l": 8, "r": 12, "t": 18, "b": 8},
                paper_bgcolor="rgba(0,0,0,0)",
                plot_bgcolor="rgba(0,0,0,0)",
                font={"color": "#9ba3b7", "family": "DM Sans, sans-serif", "size": 10},
                showlegend=False,
                hoverlabel={"bgcolor": "#191d2a", "font": {"color": "#f2f4fb"}},
                xaxis={
                    "showgrid": False,
                    "linecolor": "rgba(165,177,209,.13)",
                    "tickfont": {"color": "#858da0"},
                },
                yaxis={
                    "range": [0, 100],
                    "gridcolor": "rgba(165,177,209,.09)",
                    "zeroline": False,
                    "tickfont": {"color": "#858da0"},
                    "ticksuffix": "",
                },
            )
            st.plotly_chart(figure, use_container_width=True, config={"displayModeBar": False})
        else:
            st.markdown(
                """
                <div class="dashboard-empty-chart">
                  <span class="empty-chart-icon">⌁</span>
                  <strong>Your progress chart starts with your first evaluation.</strong>
                  <p>Practice sessions and evaluated answers will appear here. Demo activity is not included.</p>
                </div>
                """,
                unsafe_allow_html=True,
            )

    with right:
        avg = average_score
        if avg is None:
            readiness, readiness_note, readiness_class = (
                "Not enough data",
                "Complete a practice session to establish your baseline.",
                "readiness-pending",
            )
        elif avg >= 80:
            readiness, readiness_note, readiness_class = (
                "Strong momentum",
                "Your evaluated answers are showing consistent strengths.",
                "readiness-strong",
            )
        elif avg >= 60:
            readiness, readiness_note, readiness_class = (
                "Building confidence",
                "Keep practicing to strengthen your interview baseline.",
                "readiness-growing",
            )
        else:
            readiness, readiness_note, readiness_class = (
                "Room to grow",
                "Use feedback from each answer to guide your next practice.",
                "readiness-growing",
            )
        st.markdown(
            f"""
            <div class="dashboard-section-heading">
              <div><div class="eyebrow">YOUR BASELINE</div><h2>Practice readiness</h2></div>
            </div>
            <div class="readiness-card {readiness_class}">
              <div class="readiness-top"><span class="readiness-indicator"></span><span>Based on evaluated answers</span></div>
              <strong>{readiness}</strong>
              <p>{readiness_note}</p>
              <small>This reflects practice scores only; it is not a hiring prediction.</small>
            </div>
            """,
            unsafe_allow_html=True,
        )

        strongest = data["strongest_skill"]
        weak_areas = data["weak_areas"]
        strongest_label = html.escape(strongest.replace("_", " ").title()) if strongest else "Awaiting evaluations"
        weak_label = ", ".join(
            html.escape(area.replace("_", " ").title()) for area in weak_areas
        ) if weak_areas else "No evaluated areas yet"
        st.markdown(
            f"""
            <div class="skill-summary">
              <div class="eyebrow">WHAT YOUR EVALUATIONS SHOW</div>
              <div class="skill-row"><span class="skill-dot strength-dot">↗</span><div><small>Strongest skill</small><strong>{strongest_label}</strong></div></div>
              <div class="skill-row"><span class="skill-dot growth-dot">✧</span><div><small>Areas to practice</small><strong>{weak_label}</strong></div></div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    st.markdown(
        """
        <div class="dashboard-section-heading recent-heading">
          <div><div class="eyebrow">PICK UP WHERE YOU LEFT OFF</div><h2>Recent sessions</h2></div>
          <span class="chart-caption">Most recent activity</span>
        </div>
        """,
        unsafe_allow_html=True,
    )
    if not data["recent_sessions"]:
        st.markdown(
            """
            <div class="recent-empty">
              <span class="empty-chart-icon">◷</span>
              <div><strong>No practice sessions yet</strong><p>Your real interview sessions will show up here when you start practicing.</p></div>
            </div>
            """,
            unsafe_allow_html=True,
        )
    else:
        for session in data["recent_sessions"]:
            role = html.escape(session["role"])
            status = html.escape(session["status"].replace("_", " ").title())
            score = (
                f'{session["average_score"]:.1f}'
                if session["average_score"] is not None
                else "—"
            )
            date = html.escape(session["started_at"][:10])
            st.markdown(
                f"""
                <div class="recent-session">
                  <span class="session-symbol">✦</span>
                  <div class="recent-session-main"><strong>{role}</strong><small>{date} · {session["questions_answered"]} questions answered</small></div>
                  <span class="session-status">{status}</span>
                  <span class="session-score">{score}<small>AVG</small></span>
                </div>
                """,
                unsafe_allow_html=True,
            )

    render_confidence_history(profile["id"], db_path)
    st.markdown(
        '<p class="dashboard-footnote">All metrics exclude Demo Mode activity and reflect records saved to this device.</p>',
        unsafe_allow_html=True,
    )
