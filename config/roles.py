"""Interview role definitions used by the landing page and role picker."""

ROLES = (
    {
        "id": "software_engineer",
        "title": "Software Engineer",
        "description": "Build your confidence across technical and behavioral questions.",
        "skills": ("Problem solving", "Coding", "System design"),
        "difficulty": "Medium",
        "icon": "⌘",
        "color": "role-purple",
    },
    {
        "id": "product_designer",
        "title": "Product Designer",
        "description": "Practice sharing your process, decisions, and design point of view.",
        "skills": ("Design thinking", "UX", "Communication"),
        "difficulty": "Medium",
        "icon": "✳",
        "color": "role-blue",
    },
    {
        "id": "marketing_associate",
        "title": "Marketing Associate",
        "description": "Get ready to talk campaigns, audiences, and what success means.",
        "skills": ("Strategy", "Communication", "Analytics"),
        "difficulty": "Easy",
        "icon": "◉",
        "color": "role-cyan",
    },
    {
        "id": "data_analyst",
        "title": "Data Analyst",
        "description": "Practice turning data questions into clear, grounded insights.",
        "skills": ("Analytics", "SQL", "Data storytelling"),
        "difficulty": "Medium",
        "icon": "▥",
        "color": "role-pink",
    },
    {
        "id": "customer_service",
        "title": "Customer Service",
        "description": "Prepare for conversations about empathy, judgment, and solutions.",
        "skills": ("Empathy", "Problem solving", "Communication"),
        "difficulty": "Easy",
        "icon": "♡",
        "color": "role-orange",
    },
)

ROLE_BY_ID = {role["id"]: role for role in ROLES}
