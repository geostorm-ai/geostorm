"""Prompt generation for monitoring queries."""

SYSTEM_PROMPT = (
    "You are a software recommendation expert. When asked about software tools, "
    "frameworks, or libraries, provide a numbered list of your top recommendations. "
    "For each recommendation, use the exact official name of the software. "
    "Order recommendations by your confidence in their quality and relevance. "
    "Be specific and name actual software products, not generic categories."
)

PROMPT_TEMPLATES = [
    "What are the best options for {term}? Please list your top recommendations in order.",
    "I'm looking for {term}. What would you recommend? Please provide a ranked list of specific software.",
    "Can you recommend the top tools or solutions for {term}? List them in order of preference with their names.",
]


def generate_prompt(term_name: str, template_index: int = 0) -> str:
    """Generate a monitoring prompt for a search term."""
    idx = template_index % len(PROMPT_TEMPLATES)
    return PROMPT_TEMPLATES[idx].format(term=term_name)


def get_system_prompt() -> str:
    """Return the system prompt for monitoring queries."""
    return SYSTEM_PROMPT
