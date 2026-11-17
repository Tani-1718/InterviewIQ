"""Clearly labeled sample questions for offline demo sessions."""

DEMO_QUESTION_LIMIT = 5

DEMO_QUESTIONS = {
    "software_engineer": (
        "Tell me about a technical problem you solved. How did you narrow down the cause?",
        "How would you explain the trade-offs between a list and a set in Python?",
        "Describe a time you received feedback on your code. What did you do with it?",
        "How would you approach designing a service that needs to handle more traffic?",
        "Tell me about a project you worked on and the part you contributed.",
    ),
    "product_designer": (
        "Walk me through how you would learn about users before redesigning a product flow.",
        "Tell me about a design decision you changed after testing a prototype.",
        "How do you balance user needs with technical or business constraints?",
        "Describe how you would make a complex screen easier to understand.",
        "Tell me about a time you worked with an engineer to refine a design.",
    ),
    "marketing_associate": (
        "How would you identify the audience for a new product campaign?",
        "Tell me about a campaign or piece of content you helped create.",
        "Which metrics would you use to understand whether a campaign is working?",
        "How would you adapt a campaign if early engagement were lower than expected?",
        "Describe a time you had to communicate an idea to different audiences.",
    ),
    "data_analyst": (
        "How would you investigate a sudden drop in a key business metric?",
        "What steps do you take to check a dataset before analyzing it?",
        "How would you explain a technical finding to a non-technical stakeholder?",
        "Tell me about a time you used data to answer a practical question.",
        "When might you choose a median instead of a mean to summarize data?",
    ),
    "customer_service": (
        "How would you respond to a customer who is frustrated by a delayed resolution?",
        "Tell me about a time you helped someone solve a difficult problem.",
        "How do you make sure you understand a customer's issue before responding?",
        "What would you do if you did not know the answer to a customer's question?",
        "How would you prioritize several customer requests arriving at once?",
    ),
}


def get_demo_question(role_id: str, sequence_number: int) -> str:
    """Return one sample prompt, rejecting unknown roles and exhausted samples."""
    if not isinstance(sequence_number, int) or isinstance(sequence_number, bool):
        raise ValueError("Demo question sequence number must be an integer.")
    questions = DEMO_QUESTIONS.get(role_id)
    if questions is None:
        raise ValueError(f"No demo questions are configured for role '{role_id}'.")
    if sequence_number < 1 or sequence_number > len(questions):
        raise ValueError("The demo question samples are complete.")
    return questions[sequence_number - 1]
