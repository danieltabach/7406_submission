# app.py — Main Streamlit application for the writing experiment

import json
import logging
import streamlit as st
from streamlit.components.v1 import html as st_html
from streamlit_lexical import streamlit_lexical
from datetime import datetime

from config import (
    CONSENT_TEXT,
    STANCE_OPTIONS,
    LLM_USAGE_BEHAVIORS,
    EDUCATION_OPTIONS,
    TASK_PROMPT_FOR,
    TASK_PROMPT_AGAINST,
    AI_WARNING_BRIEFING_TEXT,
    AI_WARNING_TASK_BANNER,
    MAX_TURNS_PER_TASK,
    MAX_MESSAGE_LENGTH,
    MAX_ALIAS_LENGTH,
    MAX_SUBMISSION_LENGTH,
    MAX_TOKENS_PER_SESSION,
    TASK_TIMER_MINUTES,
    BRIEFING_TASK_EXPLANATION_FOR,
    BRIEFING_TASK_EXPLANATION_AGAINST,
    BRIEFING_UI_EXPLANATION,
    EDITOR_HEIGHT,
    EDITOR_DEBOUNCE_MS,
    CHAT_CONTAINER_HEIGHT,
    MIN_SUBMISSION_WORDS,
    MAX_SUBMISSION_WORDS,
    POST_SURVEY_CHAR_LIMIT,
    TRANSITION_TEXT,
    AI_RELIANCE_OPTIONS,
    MAX_TRYOUT_TURNS,
    TRYOUT_PROMPT,
    DEV_ACCESS_CODE,
    determine_condition,
    determine_writing_order,
)
from llm import call_claude, correct_typos
from storage import create_participant, save_session

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Page config
# ---------------------------------------------------------------------------
st.set_page_config(page_title="Writing Study", page_icon="📝", layout="wide")


# ---------------------------------------------------------------------------
# Layout helpers
# ---------------------------------------------------------------------------
def centered_content():
    """Return a centered column for non-task pages."""
    _, center, _ = st.columns([1, 2, 1])
    return center


# ---------------------------------------------------------------------------
# Session state initialization
# ---------------------------------------------------------------------------
def init_session_state():
    """Set up all session-state keys on first load."""
    if "initialized" in st.session_state:
        return

    # Save point #1: INSERT row in Supabase, get atomic PID
    result = create_participant()
    pid = result["pid"]

    st.session_state.update(
        {
            "initialized": True,
            "stage": "welcome",
            "participant_id": pid,
            "condition": result["condition"],
            "writing_order": result["writing_order"],
            "session_start": datetime.now().isoformat(),
            # Pre-survey
            "pre_survey": {},
            # Conversation logs (one list per task)
            "conversation_1": [],
            "conversation_2": [],
            # Tryout conversation (briefing 1 only, not saved)
            "tryout_conversation": [],
            # Task timing
            "task_1_start": None,
            "task_1_end": None,
            "task_2_start": None,
            "task_2_end": None,
            # Submissions
            "submission_1": {},
            "submission_2": {},
            # Post-survey
            "post_survey": {},
            # Token budget tracking
            "total_tokens": 0,
            # Duplicate session guard
            "session_complete": False,
            # Editor content persistence (notepad scratchpad)
            "editor_1": "",
            "editor_2": "",
        }
    )


def init_dev_session():
    """Initialize session state for dev mode (no Supabase)."""
    st.session_state.update(
        {
            "initialized": True,
            "dev_mode": True,
            "stage": "pre_survey",
            "participant_id": 9999,
            "condition": "control",
            "writing_order": ["FOR", "AGAINST"],
            "session_start": datetime.now().isoformat(),
            "pre_survey": {},
            "conversation_1": [],
            "conversation_2": [],
            "tryout_conversation": [],
            "task_1_start": None,
            "task_1_end": None,
            "task_2_start": None,
            "task_2_end": None,
            "submission_1": {},
            "submission_2": {},
            "post_survey": {},
            "total_tokens": 0,
            "session_complete": False,
            "editor_1": "",
            "editor_2": "",
        }
    )


def advance(stage: str):
    """Move to the next stage and rerun."""
    st.session_state["stage"] = stage
    st.rerun()


def auto_save(updates: dict):
    """Save partial session data to Supabase. Failures are logged, never crash the app."""
    if st.session_state.get("dev_mode"):
        return
    try:
        pid = st.session_state.get("participant_id")
        if pid is None:
            return
        updates["current_stage"] = st.session_state.get("stage", "unknown")
        save_session(pid, updates)
    except Exception:
        logger.exception("auto_save failed (pid=%s)", st.session_state.get("participant_id"))


def _build_task_snapshot(task_number: int) -> dict:
    """Build the task JSONB dict from current session state."""
    ss = st.session_state
    conv_key = f"conversation_{task_number}"
    return {
        "stance": ss["writing_order"][task_number - 1],
        "start_time": ss.get(f"task_{task_number}_start"),
        "end_time": ss.get(f"task_{task_number}_end"),
        "conversation": ss[conv_key],
        "submission": ss.get(f"submission_{task_number}", {}),
    }


# ---------------------------------------------------------------------------
# Stage renderers
# ---------------------------------------------------------------------------
def render_welcome():
    with centered_content():
        st.title("Writing Study")

        # Access code gate
        code = st.text_input("Enter access code to continue:", type="password")
        if not code:
            return

        # Dev mode check
        if code == DEV_ACCESS_CODE:
            init_dev_session()
            st.rerun()
            return

        if code != st.secrets.get("STUDY_ACCESS_CODE", ""):
            st.error("Incorrect access code.")
            return

        st.markdown(CONSENT_TEXT)
        consent = st.checkbox("I have read the above and agree to participate.")
        if st.button("Begin", disabled=not consent):
            # Only now create the Supabase participant row
            init_session_state()
            advance("pre_survey")


# ---------------------------------------------------------------------------
def render_pre_survey():
    with centered_content():
        st.header("Quick Survey")
        st.caption("Just a few questions before we start.")

        alias = st.text_input("Name or alias (for tracking purposes)")
        stance = st.radio(
            "What is your stance on remote work?",
            STANCE_OPTIONS,
            index=None,
        )
        llm_usage = st.multiselect(
            "How do you use AI tools? (select all that apply)",
            LLM_USAGE_BEHAVIORS,
        )

        # Mutual exclusion: "I don't use AI tools" conflicts with other options
        no_ai_option = "I don't use AI tools"
        if no_ai_option in llm_usage and len(llm_usage) > 1:
            st.warning(
                "\"I don't use AI tools\" can't be combined with other options. "
                "Please select one or the other."
            )
        education = st.radio(
            "What is your highest level of education?",
            EDUCATION_OPTIONS,
            index=None,
        )

        if st.button("Continue"):
            # Validation
            if not alias or not alias.strip():
                st.warning("Please enter a name or alias.")
                return
            if len(alias.strip()) > MAX_ALIAS_LENGTH:
                st.warning(f"Alias must be {MAX_ALIAS_LENGTH} characters or fewer.")
                return
            if stance is None or education is None:
                st.warning("Please answer all questions.")
                return
            if not llm_usage:
                st.warning("Please select at least one AI usage option.")
                return
            if no_ai_option in llm_usage and len(llm_usage) > 1:
                st.warning(
                    "\"I don't use AI tools\" can't be combined with other options."
                )
                return

            st.session_state["pre_survey"] = {
                "name_alias": alias.strip(),
                "remote_work_stance": stance,
                "llm_usage_behaviors": llm_usage,
                "education_level": education,
            }
            # Save point #2: pre-survey submitted
            auto_save({"pre_survey": st.session_state["pre_survey"]})
            advance("briefing_1")


# ---------------------------------------------------------------------------
def render_briefing(task_number: int):
    """Show task briefing page with instructions. Timer starts on 'I'm Ready' click."""
    with centered_content():
        stance = st.session_state["writing_order"][task_number - 1]
        explanation = (
            BRIEFING_TASK_EXPLANATION_FOR
            if stance == "FOR"
            else BRIEFING_TASK_EXPLANATION_AGAINST
        )

        st.header(f"Task {task_number} of 2 — Briefing")

        # Task explanation
        st.markdown(explanation)

        # UI explanation
        st.markdown(BRIEFING_UI_EXPLANATION)

        # AI detection warning (test group only) — yellow st.warning
        if st.session_state["condition"] == "test":
            st.warning(AI_WARNING_BRIEFING_TEXT)

        st.divider()

        # --- Tryout chat (Briefing 1 only) ---
        tryout_user_turns = 0
        if task_number == 1:
            st.markdown(TRYOUT_PROMPT)

            tryout_conv = st.session_state["tryout_conversation"]
            tryout_user_turns = sum(1 for m in tryout_conv if m["role"] == "user")

            # Chat display
            chat_container = st.container(height=250)
            with chat_container:
                for msg in tryout_conv:
                    with st.chat_message(msg["role"]):
                        st.markdown(msg["content"])

            # Chat input (capped at MAX_TRYOUT_TURNS) — form auto-clears on submit
            if tryout_user_turns < MAX_TRYOUT_TURNS:
                with st.form(key="tryout_form", clear_on_submit=True):
                    tryout_msg = st.text_input(
                        "Try sending a message...",
                        placeholder="Type anything and press Enter",
                    )
                    sent = st.form_submit_button("Send")
                if sent and tryout_msg:
                    tryout_conv.append(
                        {"role": "user", "content": tryout_msg}
                    )
                    with st.spinner("AI is thinking..."):
                        try:
                            response = call_claude(tryout_conv)
                            tryout_conv.append(
                                {"role": "assistant", "content": response["content"]}
                            )
                            st.session_state["total_tokens"] += (
                                response["input_tokens"] + response["output_tokens"]
                            )
                        except RuntimeError:
                            tryout_conv.append(
                                {"role": "assistant", "content": "Sorry, something went wrong. Try again!"}
                            )
                    st.rerun()
            else:
                st.caption(f"Tryout complete ({MAX_TRYOUT_TURNS}/{MAX_TRYOUT_TURNS} messages used).")

            st.divider()

        # --- Acknowledgement checkbox ---
        ack = st.checkbox("I have read and understand the instructions above")

        # Determine if button should be enabled
        button_disabled = not ack
        if task_number == 1 and tryout_user_turns < 1:
            button_disabled = True

        # "I'm Ready" button starts the timer and advances
        if st.button(
            "I'm Ready — Start Writing",
            type="primary",
            use_container_width=True,
            disabled=button_disabled,
        ):
            st.session_state[f"task_{task_number}_start"] = (
                datetime.now().isoformat()
            )
            # Save point #3/#7: task started
            snapshot = _build_task_snapshot(task_number)
            auto_save({f"task_{task_number}": snapshot})
            advance(f"task_{task_number}")


# ---------------------------------------------------------------------------
def render_transition():
    """Breather screen between task 1 and task 2."""
    with centered_content():
        st.header("Nice work!")
        st.markdown("Take a moment before your next task.")

        next_stance = st.session_state["writing_order"][1]
        st.markdown(
            f"{TRANSITION_TEXT}\n\n"
            f"Next up: arguing **{next_stance}** remote work."
        )

        st.divider()

        if st.button(
            "Continue to Task 2",
            type="primary",
            use_container_width=True,
        ):
            advance("briefing_2")


# ---------------------------------------------------------------------------
def render_js_timer(task_number: int):
    """Inject a live JavaScript countdown timer."""
    start_key = f"task_{task_number}_start"
    start_iso = st.session_state.get(start_key)
    if not start_iso:
        return

    # Calculate remaining time server-side to avoid timezone mismatches
    elapsed_s = (datetime.now() - datetime.fromisoformat(start_iso)).total_seconds()
    remaining_ms = max(0, (TASK_TIMER_MINUTES * 60 - elapsed_s) * 1000)

    timer_html = f"""
    <div id="timer-display" style="font-size: 1.5em; font-weight: bold; text-align: center;
         padding: 10px; background-color: #f0f2f6; border-radius: 8px; margin-bottom: 10px;">
        Loading timer...
    </div>
    <script>
        var remainingAtLoad = {remaining_ms};
        var loadTime = Date.now();
        var display = document.getElementById('timer-display');

        function updateTimer() {{
            var elapsed = Date.now() - loadTime;
            var remaining = remainingAtLoad - elapsed;

            if (remaining <= 0) {{
                display.textContent = "Time's up \\u2014 please wrap up and submit.";
                display.style.backgroundColor = "#ffd6d6";
                display.style.color = "#cc0000";
                return;
            }}

            var minutes = Math.floor(remaining / 60000);
            var seconds = Math.floor((remaining % 60000) / 1000);
            display.textContent = "\\u23F1 Time remaining: " +
                String(minutes).padStart(2, '0') + ":" +
                String(seconds).padStart(2, '0');

            if (remaining < 120000) {{
                display.style.backgroundColor = "#fff3cd";
                display.style.color = "#856404";
            }}
        }}

        updateTimer();
        setInterval(updateTimer, 1000);
    </script>
    """
    st_html(timer_html, height=60)


# ---------------------------------------------------------------------------
def render_writing_task(task_number: int):
    """Three-column layout: chat | notepad | submission."""
    conv_key = f"conversation_{task_number}"
    editor_key = f"editor_{task_number}"
    stance = st.session_state["writing_order"][task_number - 1]
    prompt = TASK_PROMPT_FOR if stance == "FOR" else TASK_PROMPT_AGAINST
    skip_validation = st.session_state.get("dev_skip_validation", False)

    # --- Header row ---
    st.header(f"Writing Task {task_number} of 2")
    st.info(prompt)

    # Live JS timer (above columns)
    render_js_timer(task_number)

    # --- Three-column layout ---
    left_col, mid_col, right_col = st.columns([1, 1, 1])

    # ========================
    # LEFT COLUMN: AI Chat
    # ========================
    with left_col:
        st.subheader("AI Assistant")

        # Chat history in a scrollable container
        chat_container = st.container(height=CHAT_CONTAINER_HEIGHT)
        with chat_container:
            for msg in st.session_state[conv_key]:
                if msg["role"] == "system":
                    st.caption(f"⚠ {msg['content']}")
                else:
                    with st.chat_message(msg["role"]):
                        st.markdown(msg["content"])

        # Turn counter
        user_turns = sum(
            1 for m in st.session_state[conv_key] if m["role"] == "user"
        )
        st.caption(f"Turns used: {user_turns} / {MAX_TURNS_PER_TASK}")

        # Token budget check
        budget_exceeded = (
            st.session_state["total_tokens"] >= MAX_TOKENS_PER_SESSION
        )
        if budget_exceeded:
            st.warning(
                "You've used a lot of tokens — please finalize your submission."
            )

        # Chat input
        if user_turns < MAX_TURNS_PER_TASK and not budget_exceeded:
            user_input = st.chat_input(
                "Type your message...", key=f"chat_input_{task_number}"
            )
            if user_input:
                # Input length check
                if len(user_input) > MAX_MESSAGE_LENGTH:
                    st.warning(
                        f"Message too long ({len(user_input)} chars). "
                        f"Please keep it under {MAX_MESSAGE_LENGTH} characters."
                    )
                    return

                # Add user message
                st.session_state[conv_key].append(
                    {
                        "role": "user",
                        "content": user_input,
                        "timestamp": datetime.now().isoformat(),
                    }
                )

                # Show user message immediately
                with chat_container:
                    with st.chat_message("user"):
                        st.markdown(user_input)

                # Call Claude with loading indicator
                with st.spinner("AI is thinking..."):
                    try:
                        response = call_claude(st.session_state[conv_key])
                    except RuntimeError as e:
                        st.error(f"Something went wrong: {e}")
                        st.session_state[conv_key].pop()
                        return

                # Handle content filter
                if response.get("error") == "content_filter":
                    st.session_state[conv_key].append(
                        {
                            "role": "system",
                            "content": "Content filter blocked response",
                            "timestamp": datetime.now().isoformat(),
                        }
                    )
                    # Save point #5/#9: content filter hit
                    snapshot = _build_task_snapshot(task_number)
                    auto_save({f"task_{task_number}": snapshot})
                    st.warning(
                        "The AI couldn't respond to that message. "
                        "Try rephrasing your request."
                    )
                    st.rerun()
                    return

                # Add assistant message
                st.session_state[conv_key].append(
                    {
                        "role": "assistant",
                        "content": response["content"],
                        "timestamp": datetime.now().isoformat(),
                        "input_tokens": response["input_tokens"],
                        "output_tokens": response["output_tokens"],
                    }
                )

                # Update token budget
                st.session_state["total_tokens"] += (
                    response["input_tokens"] + response["output_tokens"]
                )

                # Save point #4/#8: chat exchange complete
                snapshot = _build_task_snapshot(task_number)
                auto_save({
                    f"task_{task_number}": snapshot,
                    "total_tokens": st.session_state["total_tokens"],
                    f"editor_{task_number}": st.session_state.get(editor_key, ""),
                })

                st.rerun()
        elif not budget_exceeded:
            st.warning(
                "You've reached the maximum number of turns for this task."
            )

    # ========================
    # MIDDLE COLUMN: Notepad (drafting)
    # ========================
    with mid_col:
        st.subheader("Notepad")
        st.caption("Draft and refine your piece here.")

        editor_content = streamlit_lexical(
            value=st.session_state.get(editor_key, ""),
            placeholder="Start drafting here...",
            height=EDITOR_HEIGHT,
            debounce=EDITOR_DEBOUNCE_MS,
            key=f"lexical_editor_{task_number}",
        )

        # Persist editor content
        if editor_content is not None:
            st.session_state[editor_key] = editor_content

    # ========================
    # RIGHT COLUMN: Submission
    # ========================
    with right_col:
        st.subheader("Final Submission")
        st.caption("Paste your final version here when ready.")

        submission_text = st.text_area(
            "Your final piece",
            height=EDITOR_HEIGHT,
            key=f"submission_text_{task_number}",
            placeholder="Paste or write your final opinion piece here...",
        )

        # Word count
        word_count = (
            len(submission_text.split()) if submission_text.strip() else 0
        )
        st.caption(f"Word count: {word_count}")

        # Submit gate: checkbox + warning for test group
        st.divider()

        # AI detection reminder for test group — right at point of submission
        if st.session_state["condition"] == "test":
            st.warning(AI_WARNING_TASK_BANNER)

        ready_to_submit = st.checkbox(
            "I am ready to submit",
            key=f"ready_submit_{task_number}",
        )

        if not ready_to_submit:
            return

        if st.button(
            "Submit Document",
            type="primary",
            key=f"submit_{task_number}",
            use_container_width=True,
        ):
            # Word count validation (skippable in dev mode)
            if not skip_validation:
                if word_count < MIN_SUBMISSION_WORDS:
                    st.warning(
                        f"Your submission needs at least {MIN_SUBMISSION_WORDS} words."
                    )
                    return
                if word_count > MAX_SUBMISSION_WORDS:
                    st.warning(
                        f"Your submission exceeds the {MAX_SUBMISSION_WORDS}-word limit. "
                        "Please trim it down."
                    )
                    return
            if len(submission_text) > MAX_SUBMISSION_LENGTH:
                st.warning(
                    f"Submission too long ({len(submission_text)} chars). "
                    f"Please keep it under {MAX_SUBMISSION_LENGTH} characters."
                )
                return

            # Store raw submission
            st.session_state[f"submission_{task_number}"] = {
                "text": submission_text,
                "word_count": word_count,
                "submitted_at": datetime.now().isoformat(),
            }

            # Silent typo correction
            typo_result = correct_typos(submission_text)
            st.session_state[f"submission_{task_number}"]["text_corrected"] = (
                typo_result["corrected_text"]
            )
            st.session_state["total_tokens"] += (
                typo_result["input_tokens"] + typo_result["output_tokens"]
            )

            st.session_state[f"task_{task_number}_end"] = (
                datetime.now().isoformat()
            )

            # Save point #6/#10: task submitted
            snapshot = _build_task_snapshot(task_number)
            auto_save({
                f"task_{task_number}": snapshot,
                f"editor_{task_number}": st.session_state.get(editor_key, ""),
            })

            next_stage = "transition" if task_number == 1 else "post_survey"
            advance(next_stage)


# ---------------------------------------------------------------------------
def render_post_survey():
    with centered_content():
        st.header("Wrap-Up Questions")

        # --- Optional open-ended questions ---
        st.caption("These are optional — share as much or as little as you'd like.")

        ai_usage_feedback = st.text_area(
            "How did you use the AI assistant?",
            max_chars=POST_SURVEY_CHAR_LIMIT,
            height=120,
            key="feedback_ai_usage",
            placeholder="e.g., I asked it to write a draft, then edited it myself...",
        )

        general_feedback = st.text_area(
            "Any other thoughts on the experience?",
            max_chars=POST_SURVEY_CHAR_LIMIT,
            height=120,
            key="feedback_general",
            placeholder="Anything you'd like to share about the study...",
        )

        st.divider()

        # --- Required: AI reliance radios ---
        st.subheader("AI Reliance")

        ai_reliance_task_1 = st.radio(
            "Task 1 — Which best describes how you wrote your first piece?",
            AI_RELIANCE_OPTIONS,
            index=None,
            key="reliance_task_1",
        )

        ai_reliance_task_2 = st.radio(
            "Task 2 — Which best describes how you wrote your second piece?",
            AI_RELIANCE_OPTIONS,
            index=None,
            key="reliance_task_2",
        )

        st.divider()

        # --- Required: Hypothesis probe ---
        st.subheader("One Last Question")
        hypothesis_guess = st.text_input(
            "In a sentence or two, what do you think this study was about?",
            key="hypothesis_guess",
            placeholder="What were we trying to learn?",
        )

        if st.button("Finish"):
            # Validation: reliance radios + hypothesis probe required
            if ai_reliance_task_1 is None or ai_reliance_task_2 is None:
                st.warning("Please answer both AI reliance questions.")
                return
            if not hypothesis_guess or not hypothesis_guess.strip():
                st.warning("Please share your guess about what this study was about.")
                return

            st.session_state["post_survey"] = {
                "ai_usage_feedback": ai_usage_feedback.strip() if ai_usage_feedback else "",
                "general_feedback": general_feedback.strip() if general_feedback else "",
                "ai_reliance_task_1": ai_reliance_task_1,
                "ai_reliance_task_2": ai_reliance_task_2,
                "hypothesis_guess": hypothesis_guess.strip(),
            }
            # Save point #11: post-survey submitted
            auto_save({"post_survey": st.session_state["post_survey"]})
            advance("thank_you")


# ---------------------------------------------------------------------------
def render_thank_you():
    with centered_content():
        ss = st.session_state

        def _calc_duration(start_key, end_key):
            start = ss.get(start_key)
            end = ss.get(end_key)
            if start and end:
                s = datetime.fromisoformat(start)
                e = datetime.fromisoformat(end)
                return round((e - s).total_seconds())
            return None

        def _count_user_turns(conv_key):
            return sum(1 for m in ss[conv_key] if m["role"] == "user")

        # Build final task snapshots with computed fields
        task_1_final = _build_task_snapshot(1)
        task_1_final["duration_seconds"] = _calc_duration("task_1_start", "task_1_end")
        task_1_final["total_turns"] = _count_user_turns("conversation_1")

        task_2_final = _build_task_snapshot(2)
        task_2_final["duration_seconds"] = _calc_duration("task_2_start", "task_2_end")
        task_2_final["total_turns"] = _count_user_turns("conversation_2")

        # Save point #12: session complete (skip in dev mode)
        if not ss.get("dev_mode"):
            try:
                save_session(ss["participant_id"], {
                    "session_complete": datetime.now().isoformat(),
                    "current_stage": "thank_you",
                    "task_1": task_1_final,
                    "task_2": task_2_final,
                    "post_survey": ss["post_survey"],
                    "total_tokens": ss["total_tokens"],
                    "editor_1": ss.get("editor_1", ""),
                    "editor_2": ss.get("editor_2", ""),
                })
            except Exception:
                logger.exception("Final save failed (pid=%s)", ss.get("participant_id"))
                st.error(
                    "There was an error saving your data. "
                    "Please screenshot this page as a backup."
                )
                # Show raw JSON so participant can recover data
                fallback = {
                    "participant_id": ss["participant_id"],
                    "condition": ss["condition"],
                    "pre_survey": ss["pre_survey"],
                    "task_1": task_1_final,
                    "task_2": task_2_final,
                    "post_survey": ss["post_survey"],
                }
                st.code(json.dumps(fallback, indent=2, default=str), language="json")

        # Mark session as complete for duplicate guard
        st.session_state["session_complete"] = True

        st.balloons()
        st.header("Thank you!")
        st.markdown(
            "Your responses have been recorded. "
            "We really appreciate you taking the time to participate."
        )
        st.caption(f"Session ID: P{ss['participant_id']:03d}")


# ---------------------------------------------------------------------------
# Dev mode sidebar
# ---------------------------------------------------------------------------
ALL_STAGES = [
    "welcome", "pre_survey", "briefing_1", "task_1",
    "transition", "briefing_2", "task_2", "post_survey", "thank_you",
]


def render_dev_sidebar():
    """Dev mode controls in the sidebar."""
    st.sidebar.error("DEV MODE — No data saved")

    # Stage jumper — sync display to actual stage, only jump on user interaction
    current = st.session_state.get("stage", "welcome")
    st.session_state["dev_stage_select"] = current  # keep selectbox in sync

    def _on_stage_jump():
        st.session_state["stage"] = st.session_state["dev_stage_select"]

    st.sidebar.selectbox(
        "Jump to stage", ALL_STAGES, key="dev_stage_select",
        on_change=_on_stage_jump,
    )

    # Condition toggle
    current_condition = st.session_state.get("condition", "control")
    new_condition = st.sidebar.radio(
        "Condition", ["control", "test"],
        index=0 if current_condition == "control" else 1,
        key="dev_condition",
    )
    if new_condition != current_condition:
        st.session_state["condition"] = new_condition
        st.rerun()

    # Writing order toggle
    current_order = st.session_state.get("writing_order", ["FOR", "AGAINST"])
    first_stance = current_order[0]
    new_first = st.sidebar.radio(
        "First stance", ["FOR", "AGAINST"],
        index=0 if first_stance == "FOR" else 1,
        key="dev_order",
    )
    expected_order = (
        ["FOR", "AGAINST"] if new_first == "FOR" else ["AGAINST", "FOR"]
    )
    if current_order != expected_order:
        st.session_state["writing_order"] = expected_order
        st.rerun()

    # Skip validation toggle
    skip_val = st.sidebar.checkbox(
        "Skip word count validation",
        value=st.session_state.get("dev_skip_validation", False),
        key="dev_skip_val",
    )
    st.session_state["dev_skip_validation"] = skip_val


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
_BEFOREUNLOAD_JS = """
<script>
window.top.addEventListener('beforeunload', function (e) {
    e.preventDefault();
    e.returnValue = '';
});
</script>
"""


def main():
    # Welcome page doesn't need session init (no Supabase yet)
    if not st.session_state.get("initialized"):
        render_welcome()
        return

    # Warn users before they accidentally refresh or close the tab
    st_html(_BEFOREUNLOAD_JS, height=0)

    # Duplicate session guard: if already completed, block re-entry
    if (
        st.session_state.get("session_complete")
        and st.session_state["stage"] != "thank_you"
    ):
        st.warning(
            "You've already completed this study in this browser session. "
            "Thank you for participating!"
        )
        return

    # Dev mode sidebar
    if st.session_state.get("dev_mode"):
        render_dev_sidebar()

    stage = st.session_state["stage"]

    if stage == "welcome":
        render_welcome()
    elif stage == "pre_survey":
        render_pre_survey()
    elif stage == "briefing_1":
        render_briefing(1)
    elif stage == "task_1":
        render_writing_task(1)
    elif stage == "transition":
        render_transition()
    elif stage == "briefing_2":
        render_briefing(2)
    elif stage == "task_2":
        render_writing_task(2)
    elif stage == "post_survey":
        render_post_survey()
    elif stage == "thank_you":
        render_thank_you()


if __name__ == "__main__":
    main()
