"""Shared labels and adapted wording for participant self-report surveys."""

CONFIDENCE_LABELS = {
    1: "Not at all",
    2: "A little",
    3: "Somewhat",
    4: "Very",
    5: "Extremely",
}

SUS_BENCHMARK = 68
SUS_SCALE_OPTIONS = (
    "Strongly disagree",
    "Disagree",
    "Neither agree nor disagree",
    "Agree",
    "Strongly agree",
)

# Paraphrased prompts preserve SUS item polarity without reproducing the instrument verbatim.
SUS_ITEMS = (
    "I expect to use this platform for interview practice regularly.",
    "I found this platform more complex than it needed to be.",
    "I thought this platform was straightforward to use.",
    "I would need technical help to use this platform.",
    "I found the platform's features worked together well.",
    "I noticed too much inconsistency across the platform.",
    "I think most people would learn to use this platform quickly.",
    "I found the platform awkward to use.",
    "I felt confident while using this platform.",
    "I had to learn a lot before I could use this platform.",
)
