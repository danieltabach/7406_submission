"""
Phase 2 — Judge App Configuration
Constants, prompts, and UI text for the human judge evaluation platform.
"""

# ---------------------------------------------------------------------------
# Session limits
# ---------------------------------------------------------------------------
PAIRS_PER_SESSION = 18  # max unique pairs without document repetition
MIN_SECONDS_PER_PAIR = 10  # minimum time a judge must spend before choosing
MAX_ALIAS_LENGTH = 50
MAX_RAFFLE_CONTACT_LENGTH = 100
TRUNCATED_WORD_COUNT = 150  # words shown before "Show more"

# ---------------------------------------------------------------------------
# Framing
# ---------------------------------------------------------------------------
# Blind framing: no mention of detection tools, scrutiny, or conditions.
# Research basis: Jakesch et al. 2023 (PNAS), Fröhling & Zubiaga 2024 (PLOS ONE),
# medical essay detection study 2024 (JMIR). See plans/phase2_research.md.

WELCOME_TITLE = "Can You Spot the AI?"

WELCOME_TEXT = (
    "You'll be shown pairs of short opinion pieces on remote work. "
    "In each pair, one was written by AI and the other by a human. "
    "Your job: pick which one was written by a human."
)

WELCOME_SUBTEXT = (
    "There are up to 18 pairs. You can stop anytime — your answers are saved "
    "as you go, even if you close the tab. However, refreshing the page will "
    "start a new session."
)

PAIR_QUESTION = "Which one was written by a human?"

STANCE_LABEL_FOR = "Both writers argued FOR remote work"
STANCE_LABEL_AGAINST = "Both writers argued AGAINST remote work"

SHOW_MORE_LABEL = "Show full text"
SHOW_LESS_LABEL = "Show less"

# ---------------------------------------------------------------------------
# Thank you
# ---------------------------------------------------------------------------
THANK_YOU_TITLE = "Thanks for participating!"
THANK_YOU_TEXT = "Your responses have been saved. Every pair you evaluated helps our research."
THANK_YOU_RAFFLE = "If you entered the raffle, we'll reach out if you win."

# ---------------------------------------------------------------------------
# Button labels
# ---------------------------------------------------------------------------
DOC_A_LABEL = "Document A"
DOC_B_LABEL = "Document B"
DOC_A_CHOICE_LABEL = "Document A was written by a human"
DOC_B_CHOICE_LABEL = "Document B was written by a human"
START_BUTTON_LABEL = "Start"

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def truncate_text(text: str, max_words: int = TRUNCATED_WORD_COUNT) -> tuple[str, bool]:
    """Return (truncated_text, was_truncated).

    If the text has more than max_words words, truncate at the last complete
    sentence boundary within the limit. Falls back to word boundary if no
    sentence boundary is found.
    """
    words = text.split()
    if len(words) <= max_words:
        return text, False

    truncated = " ".join(words[:max_words])

    # Try to end at a sentence boundary
    for sep in (". ", "! ", "? "):
        last = truncated.rfind(sep)
        if last != -1:
            return truncated[: last + 1], True

    return truncated + "...", True


def stance_label(stance: str) -> str:
    if stance == "FOR":
        return STANCE_LABEL_FOR
    return STANCE_LABEL_AGAINST
