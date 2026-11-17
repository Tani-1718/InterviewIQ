"""Generate a portable PDF from a saved INTERVIEWIQ session report."""

import unicodedata

from fpdf import FPDF


def _pdf_text(value: object) -> str:
    text = str(value) if value is not None else ""
    normalized = unicodedata.normalize("NFKD", text)
    return normalized.encode("ascii", "ignore").decode("ascii").strip()


def _write_text(
    pdf: FPDF,
    text: object,
    *,
    size: int = 10,
    bold: bool = False,
    color: tuple[int, int, int] = (220, 224, 235),
) -> None:
    pdf.set_font("Helvetica", style="B" if bold else "", size=size)
    pdf.set_text_color(*color)
    cleaned = _pdf_text(text)
    pdf.multi_cell(w=0, h=5.5, text=cleaned or "Not available")
    pdf.ln(1.5)


def _write_section(pdf: FPDF, title: str) -> None:
    pdf.ln(3)
    pdf.set_draw_color(110, 82, 205)
    pdf.set_line_width(0.7)
    pdf.line(12, pdf.get_y(), 198, pdf.get_y())
    pdf.ln(3)
    _write_text(pdf, title, size=14, bold=True, color=(192, 170, 255))


def _write_list(pdf: FPDF, values: object) -> None:
    if not isinstance(values, list) or not values:
        _write_text(pdf, "No items recorded.")
        return
    for value in values:
        _write_text(pdf, f"- {value}")


def generate_report_pdf(report: dict) -> bytes:
    """Return a PDF containing persisted metrics, feedback, and any generated plan."""
    session = report["session"]
    metrics = report["metrics"]
    is_demo = bool(session["is_demo"])
    pdf = FPDF()
    pdf.set_margins(14, 14, 14)
    pdf.set_auto_page_break(auto=True, margin=16)
    pdf.add_page()

    _write_text(pdf, "INTERVIEWIQ", size=11, bold=True, color=(157, 125, 255))
    _write_text(pdf, "Interview practice report", size=22, bold=True)
    _write_text(
        pdf,
        f"{session['role']} | {session['experience_level']} | "
        f"{session['difficulty']} | {session['interview_type']}",
        size=10,
        color=(165, 174, 193),
    )
    if is_demo:
        _write_section(pdf, "DEMO MODE - SAMPLE PRACTICE")
        _write_text(
            pdf,
            "This report contains sample-session data and practice answers only. "
            "It is not an AI evaluation and is excluded from real statistics.",
            bold=True,
            color=(255, 202, 129),
        )

    _write_section(pdf, "Session summary")
    overall_score = metrics["overall_score"]
    average_score = metrics["average_score"]
    _write_text(
        pdf,
        f"Overall score: {overall_score}/100"
        if overall_score is not None
        else "Overall score: Not available",
    )
    _write_text(
        pdf,
        f"Average answer score: {average_score:.1f}/100"
        if average_score is not None
        else "Average answer score: Not available",
    )
    _write_text(pdf, f"Questions answered: {metrics['questions_answered']}")
    _write_text(pdf, f"Questions skipped: {metrics['questions_skipped']}")
    response_time = metrics["average_response_seconds"]
    _write_text(
        pdf,
        f"Average response time: {response_time:.1f} seconds"
        if response_time is not None
        else "Average response time: Not available",
    )
    for key, label in (
        ("technical_performance", "Technical performance"),
        ("communication_performance", "Communication performance"),
    ):
        score = metrics[key]
        _write_text(
            pdf,
            f"{label}: {score:.1f}/100" if score is not None else f"{label}: Not available",
        )

    analysis = report.get("final_analysis")
    if analysis:
        _write_section(pdf, "Session analysis")
        _write_text(pdf, analysis["overall_summary"])
        _write_text(pdf, "Strengths", bold=True)
        _write_list(pdf, analysis["strengths"])
        _write_text(pdf, "Improvement areas", bold=True)
        _write_list(pdf, analysis["improvement_areas"])
        _write_text(pdf, "Next steps", bold=True)
        _write_list(pdf, analysis["next_steps"])

    learning_plan = report.get("learning_plan")
    if learning_plan:
        _write_section(pdf, "Personalized learning plan")
        for key, label in (
            ("topics", "Topics"),
            ("concepts", "Concepts to revisit"),
            ("sample_questions", "Practice questions"),
        ):
            _write_text(pdf, label, bold=True)
            _write_list(pdf, learning_plan[key])
        _write_text(pdf, "Next practice session", bold=True)
        _write_text(pdf, learning_plan["next_practice_session"])

    dimensions = metrics["dimension_averages"]
    if dimensions:
        _write_section(pdf, "Average answer dimensions")
        for name, score in dimensions.items():
            label = name.replace("_", " ").title()
            _write_text(pdf, f"{label}: {score:.1f}/100")

    _write_section(pdf, "Questions and answers")
    for question in report["questions"]:
        _write_text(
            pdf,
            f"Question {question['sequence_number']}: {question['question_text']}",
            size=12,
            bold=True,
        )
        if question["was_skipped"]:
            _write_text(pdf, "Skipped")
            continue
        _write_text(pdf, f"Your answer: {question['answer_text']}")
        if question["overall_score"] is not None:
            _write_text(pdf, f"Answer score: {question['overall_score']}/100", bold=True)
        feedback = question["feedback_json"]
        if feedback:
            for key, label in (
                ("what_went_well", "What went well"),
                ("what_was_missing", "What was missing"),
                ("mistakes_or_inaccuracies", "Mistakes or inaccuracies"),
                ("suggestions", "Suggestions"),
                ("concepts_to_revise", "Concepts to revise"),
            ):
                values = feedback.get(key)
                if values:
                    _write_text(pdf, label, bold=True)
                    _write_list(pdf, values)

    return bytes(pdf.output())
