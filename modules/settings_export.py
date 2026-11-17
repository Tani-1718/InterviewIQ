"""Local app settings and anonymous confidence/SUS CSV downloads."""

import csv
from io import StringIO
from uuid import uuid4

import streamlit as st

from config.settings import Settings
from config.surveys import SUS_BENCHMARK
from database.db import get_research_export_data
from modules.sus import calculate_sus_score


def build_research_csvs(
    records: list[dict],
    anonymous_participant_id: str,
    anonymous_session_ids: dict[int, str],
) -> tuple[str, str]:
    """Create confidence and SUS CSVs without exporting database identifiers."""
    confidence_buffer = StringIO(newline="")
    confidence_writer = csv.writer(confidence_buffer, lineterminator="\n")
    confidence_writer.writerow(
        [
            "anonymous_participant_id",
            "anonymous_session_id",
            "confidence_before",
            "confidence_after",
            "confidence_change",
        ]
    )

    sus_buffer = StringIO(newline="")
    sus_writer = csv.writer(sus_buffer, lineterminator="\n")
    sus_writer.writerow(
        [
            "anonymous_participant_id",
            "anonymous_session_id",
            "sus_score",
            "benchmark",
            *[f"sus_item_{number:02d}" for number in range(1, 11)],
        ]
    )

    for record in records:
        session_id = int(record["session_id"])
        anonymous_session_id = anonymous_session_ids[session_id]
        before = record["confidence_before"]
        after = record["confidence_after"]
        if before is not None or after is not None:
            change = after - before if before is not None and after is not None else ""
            confidence_writer.writerow(
                [
                    anonymous_participant_id,
                    anonymous_session_id,
                    before if before is not None else "",
                    after if after is not None else "",
                    change,
                ]
            )

        responses = record["sus_responses"]
        if responses:
            sus_writer.writerow(
                [
                    anonymous_participant_id,
                    anonymous_session_id,
                    f"{calculate_sus_score(responses):.1f}",
                    SUS_BENCHMARK,
                    *responses,
                ]
            )
    return confidence_buffer.getvalue(), sus_buffer.getvalue()


def _session_ids_for_export(
    user_id: int,
    records: list[dict],
) -> tuple[str, dict[int, str]]:
    participant_key = f"research-participant-id-{user_id}"
    participant_id = st.session_state.get(participant_key)
    if participant_id is None:
        participant_id = f"P-{uuid4().hex[:12]}"
        st.session_state[participant_key] = participant_id

    sessions_key = f"research-session-ids-{user_id}"
    session_ids = st.session_state.get(sessions_key)
    if not isinstance(session_ids, dict):
        session_ids = {}
    for record in records:
        session_id = int(record["session_id"])
        if session_id not in session_ids:
            session_ids[session_id] = f"S-{uuid4().hex[:12]}"
    st.session_state[sessions_key] = session_ids
    return participant_id, {
        int(record["session_id"]): session_ids[int(record["session_id"])]
        for record in records
    }


def _render_header() -> None:
    st.markdown(
        """
        <header class="topbar app-topbar">
          <a class="brand" href="?page=landing#top" target="_self"><span class="brand-mark">✦</span><span>interview<span class="brand-iq">iq</span></span></a>
          <nav class="topnav" aria-label="Main navigation">
            <a href="?page=dashboard" target="_self">Dashboard</a>
            <a href="?page=history" target="_self">History</a>
            <a href="?page=settings" target="_self" class="nav-current">Settings &amp; export</a>
          </nav>
          <a class="nav-cta" href="?page=roles" target="_self">Practice <span aria-hidden="true">↗</span></a>
        </header>
        """,
        unsafe_allow_html=True,
    )


def render_settings_export_page(
    profile: dict | None,
    settings: Settings,
) -> None:
    """Render configuration status and downloadable anonymized research data."""
    _render_header()
    st.markdown(
        """
        <div class="page-intro dashboard-intro">
          <div class="eyebrow">LOCAL APP &amp; RESEARCH DATA</div>
          <h1>Settings &amp; export.</h1>
          <p>Review the active configuration and export completed-session confidence and usability records.</p>
        </div>
        """,
        unsafe_allow_html=True,
    )
    if profile is None:
        st.info("Create a profile before exporting research records.")
        return

    left, right = st.columns(2)
    left.metric("Groq model", settings.groq_model)
    right.metric(
        "API key",
        "Configured" if settings.groq_api_key else "Not configured",
    )
    st.caption(
        f"SQLite data is stored locally in `{settings.database_path.name}`. "
        "The API key is never displayed or included in exports."
    )
    st.markdown("### Anonymous research export")
    st.write(
        "Exports include completed real sessions only. Demo Mode records, profile names, "
        "database user IDs, and numeric session IDs are excluded."
    )
    st.caption(
        "Random participant and session IDs are shared across both CSV downloads for this Streamlit session, so rows can be matched without exporting database IDs."
    )
    try:
        records = get_research_export_data(profile["id"], db_path=settings.database_path)
    except ValueError as exc:
        st.error(f"Couldn’t prepare research export: {exc}")
        return
    participant_id, anonymous_session_ids = _session_ids_for_export(
        profile["id"], records
    )
    confidence_csv, sus_csv = build_research_csvs(
        records,
        participant_id,
        anonymous_session_ids,
    )
    confidence_rows = sum(
        record["confidence_before"] is not None
        or record["confidence_after"] is not None
        for record in records
    )
    sus_rows = sum(bool(record["sus_responses"]) for record in records)
    confidence_column, sus_column = st.columns(2)
    confidence_column.metric("Sessions with confidence data", confidence_rows)
    sus_column.metric("Sessions with SUS responses", sus_rows)
    download_columns = st.columns(2)
    download_columns[0].download_button(
        "Download confidence CSV",
        data=confidence_csv,
        file_name="interviewiq-confidence.csv",
        mime="text/csv",
        disabled=confidence_rows == 0,
    )
    download_columns[1].download_button(
        "Download SUS CSV",
        data=sus_csv,
        file_name="interviewiq-sus.csv",
        mime="text/csv",
        disabled=sus_rows == 0,
    )
    if not records:
        st.info("Completed real-session survey records will appear here when available.")
    st.caption(
        "SUS item wording in the app is paraphrased; the exported score uses the standard scoring formula and includes the 68 reference benchmark."
    )
