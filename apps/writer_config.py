# config.py — Constants, prompts, survey options, consent text

import streamlit as st

# --- Model Configuration ---
MODEL_NAME = "claude-sonnet-4-20250514"
MAX_RESPONSE_TOKENS = 1024
MAX_TURNS_PER_TASK = 25

# --- Input Limits ---
MAX_MESSAGE_LENGTH = 3000       # ~750 words per chat turn
MAX_ALIAS_LENGTH = 50
MAX_SUBMISSION_LENGTH = 5000    # bumped to accommodate 400-word pieces comfortably

# --- Word Count Limits ---
MIN_SUBMISSION_WORDS = 200
MAX_SUBMISSION_WORDS = 400

# --- Cost Protection ---
MAX_TOKENS_PER_SESSION = 50000  # input+output combined; caps at ~$0.50/session

# --- System Prompt (identical for both groups) ---
SYSTEM_PROMPT = "You are a helpful writing assistant."

# --- Writing Task Prompts ---
TASK_PROMPT_FOR = (
    "**Your task:** Write a 200–400 word opinion piece arguing **in favor of** remote work.\n\n"
    "An AI writing assistant is available in the left panel to help with brainstorming, "
    "drafting, editing, or anything else. "
    "Draft in the notepad, then paste your final version into the submission box."
)

TASK_PROMPT_AGAINST = (
    "**Your task:** Write a 200–400 word opinion piece arguing **against** remote work.\n\n"
    "An AI writing assistant is available in the left panel to help with brainstorming, "
    "drafting, editing, or anything else. "
    "Draft in the notepad, then paste your final version into the submission box."
)

# --- AI Detection Warning (test group only) ---
AI_WARNING_BRIEFING_TEXT = (
    "Your final submission will be analyzed by an **AI detection tool**. "
    "Your **AI detection score** will be recorded and included alongside "
    "your submission in our **research dataset**."
)

AI_WARNING_TASK_BANNER = (
    "**Reminder:** Your submission will be analyzed by an AI detection tool. "
    "Your AI detection score will be recorded and included in our research dataset."
)

# --- Task Timer ---
TASK_TIMER_MINUTES = 15

# --- Editor Configuration ---
EDITOR_HEIGHT = 400
EDITOR_DEBOUNCE_MS = 500
CHAT_CONTAINER_HEIGHT = 400

# --- Post-Survey ---
POST_SURVEY_CHAR_LIMIT = 500

AI_RELIANCE_OPTIONS = [
    "I wrote it entirely myself",
    "I mostly wrote it, AI helped with ideas/edits",
    "About equal collaboration",
    "I mostly used AI's text with my own edits",
    "AI wrote almost all of it, I made minor edits",
]

# --- Tryout Chat ---
MAX_TRYOUT_TURNS = 3
TRYOUT_PROMPT = (
    "Before we start the timer, try out the AI assistant below. "
    "Send it any message to see how it works."
)

# --- Typo Correction ---
TYPO_CORRECTION_PROMPT = (
    "You are a typo-correction tool. Fix ONLY obvious spelling errors and typos. "
    "Do NOT change: word choice, sentence structure, grammar, punctuation style, "
    "capitalization style, tone, phrasing, or meaning. Return the corrected text "
    "with no commentary. If there are no typos, return the text unchanged."
)

# --- Briefing Page Text ---
BRIEFING_TASK_EXPLANATION_FOR = (
    "In this task, you will write a **200–400 word opinion piece arguing IN FAVOR OF remote work.**\n\n"
    "You will have **15 minutes** to complete this task."
)

BRIEFING_TASK_EXPLANATION_AGAINST = (
    "In this task, you will write a **200–400 word opinion piece arguing AGAINST remote work.**\n\n"
    "You will have **15 minutes** to complete this task."
)

BRIEFING_UI_EXPLANATION = (
    "**How this works:**\n\n"
    "- **Left panel:** An AI writing assistant is available. You can use it for brainstorming, drafts, edits, or feedback.\n"
    "- **Middle panel:** Your notepad. Use it to draft and refine your piece.\n"
    "- **Right panel:** Submission. Paste your final version here and submit.\n\n"
    "The timer will start when you click **I'm Ready** below."
)

# --- Transition Screen ---
TRANSITION_TEXT = (
    "For the next task, you'll be arguing the **opposite** position."
)

# --- Pre-Survey Options ---
STANCE_OPTIONS = ["Slightly Favor", "Favor", "Slightly Oppose", "Oppose"]
LLM_USAGE_BEHAVIORS = [
    "I use AI tools (ChatGPT, Claude, etc.) like a search engine — quick lookups and questions",
    "I use AI tools to help with writing (drafts, editing, brainstorming)",
    "I use AI tools for work or school assignments",
    "I use AI tools for coding or technical tasks",
    "I've tried AI tools but don't use them regularly",
    "I don't use AI tools",
]
EDUCATION_OPTIONS = [
    "High School (or in progress)",
    "Bachelor's (or in progress)",
    "Master's (or in progress)",
    "Doctorate (or in progress)",
]

# --- Assignment Helpers ---
def determine_condition(participant_id: int) -> str:
    """Alternating: odd = control, even = test."""
    return "control" if participant_id % 2 == 1 else "test"


def determine_writing_order(participant_id: int) -> list[str]:
    """
    Counterbalance FOR/AGAINST order within each condition.
    P1: control FOR-first  | P2: test FOR-first
    P3: control AGAINST-first | P4: test AGAINST-first
    P5: control FOR-first  | P6: test FOR-first  ... (cycle)
    """
    condition_count = (participant_id + 1) // 2  # 1,1,2,2,3,3,...
    if condition_count % 2 == 1:
        return ["FOR", "AGAINST"]
    return ["AGAINST", "FOR"]


# --- Consent Text ---
CONSENT_TEXT = """\
**Welcome to this writing study!**

You're being asked to participate in a short writing exercise as part of a
Georgia Tech course project studying how people use AI writing tools.

**What you'll do:** Complete a brief survey (3 questions), then use an AI chat
assistant to write two short opinion pieces (~200–400 words each) about remote work,
and answer a couple wrap-up questions.

**Time commitment:** About 20–30 minutes.

**Data & Privacy:** Your conversation logs and writing will be reviewed by the
researcher (Danny Tabach). The final course report will only contain aggregated
metrics and results — no individual submissions or personally identifiable content
will be published.

**Participation is voluntary.** You can stop at any time.
"""

# --- Dev Mode ---
DEV_ACCESS_CODE = st.secrets.get("DEV_ACCESS_CODE", "ADMIN_DEV")
