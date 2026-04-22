# judge_app.py — Phase 2: Human Judge Evaluation Platform
#
# Judges see pairs of documents (one control, one test, matched on stance)
# and pick which one was written by a human.
#
# Data tracked per pair:
#   - which side chosen
#   - whether "show more" was clicked for each doc
#   - whether each doc was expanded when the choice was made
#   - time spent on the pair (seconds)
#
# Every response is saved to Supabase immediately via a background thread,
# so tab close / timeout never loses data. The background thread means
# zero latency impact — the UI advances instantly while the write happens.

import json
import hashlib
import logging
import threading
from datetime import datetime, timezone
from pathlib import Path

import streamlit as st
from streamlit.components.v1 import html as st_html

from judge_config import (
    WELCOME_TITLE,
    WELCOME_TEXT,
    WELCOME_SUBTEXT,
    PAIR_QUESTION,
    DOC_A_LABEL,
    DOC_B_LABEL,
    DOC_A_CHOICE_LABEL,
    DOC_B_CHOICE_LABEL,
    START_BUTTON_LABEL,
    THANK_YOU_TITLE,
    THANK_YOU_TEXT,
    THANK_YOU_RAFFLE,
    MAX_ALIAS_LENGTH,
    MAX_RAFFLE_CONTACT_LENGTH,
    PAIRS_PER_SESSION,
    MIN_SECONDS_PER_PAIR,
    truncate_text,
    stance_label,
    SHOW_MORE_LABEL,
    SHOW_LESS_LABEL,
)
from judge_storage import (
    create_judge_session,
    save_judge_response,
    complete_judge_session,
)
from prepare_pairs import build_document_pool, generate_session_pairs

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Dev mode: add ?dev=1 to URL to skip Supabase and show only 3 pairs
# ---------------------------------------------------------------------------
DEV_MODE = st.query_params.get("dev") == "1"
DEV_PAIRS = 3  # number of pairs to show in dev mode

# ---------------------------------------------------------------------------
# Study lock — prevents new participants; admin password unlocks read-only access
# ---------------------------------------------------------------------------
STUDY_CLOSED = True
ADMIN_PASSWORD = "ADMIN_DEV_7406"

# ---------------------------------------------------------------------------
# Page config
# ---------------------------------------------------------------------------
st.set_page_config(page_title="Can You Spot the AI?", page_icon="🔍", layout="wide")

# ---------------------------------------------------------------------------
# Custom CSS for responsive layout + clean design
# ---------------------------------------------------------------------------
st.markdown("""
<style>
    /* Tight top padding so counter/question aren't cut off */
    .block-container { max-width: 900px; padding-top: 0.5rem; }

    /* Document card styling */
    .doc-card {
        background: #f8f9fa;
        border: 1px solid #e0e0e0;
        border-radius: 8px;
        padding: 1.25rem;
        min-height: 200px;
        font-size: 0.95rem;
        line-height: 1.6;
    }

    /* Mobile: stack documents vertically */
    @media (max-width: 768px) {
        .block-container { padding-top: 0.25rem; }
    }

    /* Hide Streamlit branding */
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    header {visibility: hidden;}

    /* Stance label — prominent pill */
    .stance-label {
        text-align: center;
        color: #444;
        font-size: 1rem;
        font-weight: 500;
        padding: 0.4rem 1rem;
        background: #f0f2f6;
        border-radius: 6px;
        display: inline-block;
    }
    .stance-label-wrapper {
        text-align: center;
        margin-bottom: 0.5rem;
    }

    /* Question styling */
    .pair-question {
        text-align: center;
        font-size: 1.25rem;
        font-weight: 600;
        margin: 0.5rem 0 0.75rem 0;
    }

    /* Pair counter */
    .pair-counter {
        text-align: center;
        color: #888;
        font-size: 0.85rem;
        margin-bottom: 0.25rem;
    }
</style>
""", unsafe_allow_html=True)


# ---------------------------------------------------------------------------
# Document pool (loaded once, cached)
# ---------------------------------------------------------------------------
@st.cache_data
def load_pool():
    pool_path = Path(__file__).resolve().parent / "document_pool.json"
    if pool_path.exists():
        with open(pool_path, encoding="utf-8") as f:
            return json.load(f)
    return build_document_pool()


def _make_pair_id(control_doc_id: str, test_doc_id: str, stance: str, control_side: str) -> str:
    """Generate a deterministic pair ID from the pair's key attributes."""
    raw = f"{control_doc_id}|{test_doc_id}|{stance}|{control_side}"
    return hashlib.sha256(raw.encode()).hexdigest()[:12]


# ---------------------------------------------------------------------------
# Session state helpers
# ---------------------------------------------------------------------------
def init_session():
    if "judge_initialized" in st.session_state:
        return
    st.session_state["judge_initialized"] = True
    st.session_state["stage"] = "welcome"
    st.session_state["alias"] = ""
    st.session_state["raffle_contact"] = ""
    st.session_state["session_id"] = None
    st.session_state["pairs"] = []
    st.session_state["responses"] = []
    st.session_state["current_pair"] = 0
    st.session_state["pair_start_time"] = None
    # Per-pair expansion tracking
    st.session_state["expanded_a"] = False
    st.session_state["expanded_b"] = False
    st.session_state["ever_expanded_a"] = False
    st.session_state["ever_expanded_b"] = False
    st.session_state["current_confidence"] = None
    st.session_state["used_goback_for_pair"] = None


def _save_in_background(sid: int, responses: list[dict], n_completed: int):
    """Fire-and-forget Supabase write in a background thread.

    Copies the responses list so the main thread can keep mutating it.
    """
    snapshot = json.loads(json.dumps(responses))  # deep copy
    def _do_save():
        try:
            save_judge_response(sid, snapshot, n_completed)
        except Exception as e:
            logger.warning(f"Background save failed: {e}")
    threading.Thread(target=_do_save, daemon=True).start()


def _complete_in_background(sid: int, responses: list[dict], n_completed: int):
    """Final Supabase write — marks session complete. Also background."""
    snapshot = json.loads(json.dumps(responses))
    def _do_complete():
        try:
            complete_judge_session(sid, snapshot, n_completed)
        except Exception as e:
            logger.warning(f"Background complete failed: {e}")
    threading.Thread(target=_do_complete, daemon=True).start()


# ---------------------------------------------------------------------------
# Welcome screen
# ---------------------------------------------------------------------------
def render_welcome():
    _, center, _ = st.columns([1, 2, 1])
    with center:
        st.title(WELCOME_TITLE)
        st.write(WELCOME_TEXT)
        st.caption(WELCOME_SUBTEXT)

        st.divider()

        alias = st.text_input(
            "Pick an alias (optional)",
            max_chars=MAX_ALIAS_LENGTH,
            placeholder="e.g., Alex",
        )
        raffle = st.text_input(
            "Enter your contact info so we can reach you if you win the raffle (optional):",
            max_chars=MAX_RAFFLE_CONTACT_LENGTH,
            placeholder="your@email.com, @your_instagram, or (555) 123-4567",
        )

        if st.button(START_BUTTON_LABEL, type="primary", use_container_width=True):
            st.session_state["alias"] = alias.strip() if alias else ""
            st.session_state["raffle_contact"] = raffle.strip() if raffle else ""

            # Generate pairs
            pool = load_pool()
            pairs = generate_session_pairs(pool)
            if DEV_MODE:
                pairs = pairs[:DEV_PAIRS]

            # Add pair IDs
            for p in pairs:
                p["pair_id"] = _make_pair_id(
                    p["control_doc_id"], p["test_doc_id"],
                    p["stance"], p["control_side"],
                )

            st.session_state["pairs"] = pairs

            # Create session in Supabase (skip in dev mode) — only DB call at start
            if DEV_MODE:
                st.session_state["session_id"] = -1
            else:
                try:
                    sid = create_judge_session(
                        alias=st.session_state["alias"],
                        raffle_contact=st.session_state["raffle_contact"] or None,
                        pairs=pairs,
                    )
                    st.session_state["session_id"] = sid
                except Exception as e:
                    logger.error(f"Failed to create judge session: {e}")
                    st.error("Something went wrong. Please try again.")
                    return

            st.session_state["pair_start_time"] = datetime.now(timezone.utc).isoformat()
            st.session_state["stage"] = "pairs"
            st.rerun()


# ---------------------------------------------------------------------------
# Pair evaluation screen
# ---------------------------------------------------------------------------
def render_pair():
    idx = st.session_state["current_pair"]
    pairs = st.session_state["pairs"]
    total = len(pairs)

    if idx >= total:
        # All pairs done — final save (background, marks session complete)
        if not DEV_MODE:
            sid = st.session_state.get("session_id")
            if sid:
                _complete_in_background(
                    sid,
                    st.session_state["responses"],
                    len(st.session_state["responses"]),
                )
        st.session_state["stage"] = "thank_you"
        st.rerun()
        return

    pair = pairs[idx]
    control_side = pair["control_side"]

    # Determine which doc is A and which is B based on control_side
    if control_side == "left":
        doc_a_text = pair["control_text"]
        doc_b_text = pair["test_text"]
        doc_a_id = pair["control_doc_id"]
        doc_b_id = pair["test_doc_id"]
    else:
        doc_a_text = pair["test_text"]
        doc_b_text = pair["control_text"]
        doc_a_id = pair["test_doc_id"]
        doc_b_id = pair["control_doc_id"]

    # Truncate
    doc_a_short, a_truncated = truncate_text(doc_a_text)
    doc_b_short, b_truncated = truncate_text(doc_b_text)

    # --- TOP SECTION: counter, stance, question, choice buttons ---

    # Pair counter
    st.markdown(
        f'<div class="pair-counter">Pair {idx + 1} of {total}</div>',
        unsafe_allow_html=True,
    )

    # Stance label
    st.markdown(
        f'<div class="stance-label-wrapper"><span class="stance-label">{stance_label(pair["stance"])}</span></div>',
        unsafe_allow_html=True,
    )

    # Question
    st.markdown(
        f'<div class="pair-question">{PAIR_QUESTION}</div>',
        unsafe_allow_html=True,
    )

    # Confidence — optional, set BEFORE making a choice
    cur_conf = st.session_state.get("current_confidence")
    st.caption("How confident are you? *(optional)*")
    conf_cols = st.columns([1, 1, 1, 1, 1, 1, 1])
    with conf_cols[0]:
        st.markdown("<small style='color:#999'>guess</small>", unsafe_allow_html=True)
    for i in range(5):
        with conf_cols[i + 1]:
            btn_type = "primary" if cur_conf == i + 1 else "secondary"
            st.button(
                str(i + 1),
                key=f"conf_{i+1}_{idx}",
                use_container_width=True,
                type=btn_type,
                on_click=_set_confidence,
                args=(i + 1,),
            )
    with conf_cols[6]:
        st.markdown("<small style='color:#999'>certain</small>", unsafe_allow_html=True)

    # Choice buttons — picking advances to next pair
    # Buttons always rendered enabled; JS handles the 10s lockout client-side.
    # Server-side guard in _record_choice rejects anything under MIN_SECONDS_PER_PAIR.

    # Countdown timer placeholder (filled by JS)
    st.markdown(
        f'<div id="pair-timer" style="text-align:center;color:#888;font-size:0.85rem;margin-bottom:0.5rem;"></div>',
        unsafe_allow_html=True,
    )

    btn_col_a, btn_col_b = st.columns(2)

    with btn_col_a:
        st.button(
            f"🅰️ {DOC_A_CHOICE_LABEL}",
            key=f"choose_a_{idx}",
            use_container_width=True,
            type="primary",
            on_click=_record_choice,
            args=("left", pair, doc_a_id, doc_b_id),
        )

    with btn_col_b:
        st.button(
            f"🅱️ {DOC_B_CHOICE_LABEL}",
            key=f"choose_b_{idx}",
            use_container_width=True,
            type="primary",
            on_click=_record_choice,
            args=("right", pair, doc_a_id, doc_b_id),
        )

    # JS: disable choice buttons for MIN_SECONDS_PER_PAIR with a live countdown.
    # Runs entirely client-side — no Streamlit rerun needed.
    pair_start = st.session_state.get("pair_start_time")
    try:
        elapsed = (datetime.now(timezone.utc) - datetime.fromisoformat(pair_start)).total_seconds()
    except (ValueError, TypeError):
        elapsed = 0
    remaining_ms = max(0, int((MIN_SECONDS_PER_PAIR - elapsed) * 1000))

    if remaining_ms > 0:
        st_html(
            f"""<script>
            (function() {{
                var remainMs = {remaining_ms};
                var parent = window.parent.document;

                // Find the two choice buttons by their text content
                function getChoiceBtns() {{
                    var btns = parent.querySelectorAll('button[kind="primary"]');
                    var result = [];
                    btns.forEach(function(b) {{
                        var txt = b.textContent || '';
                        if (txt.includes('Document A') || txt.includes('Document B')) {{
                            result.push(b);
                        }}
                    }});
                    return result;
                }}

                var choiceBtns = getChoiceBtns();
                var timerDiv = parent.querySelector('#pair-timer');

                // Disable buttons
                choiceBtns.forEach(function(b) {{
                    b.disabled = true;
                    b.style.opacity = '0.4';
                    b.style.pointerEvents = 'none';
                }});

                // Live countdown
                var startTime = Date.now();
                var interval = setInterval(function() {{
                    var left = Math.max(0, remainMs - (Date.now() - startTime));
                    var secs = Math.ceil(left / 1000);
                    if (timerDiv) {{
                        timerDiv.textContent = 'Please read both documents. You can choose in ' + secs + 's...';
                    }}
                    if (left <= 0) {{
                        clearInterval(interval);
                        if (timerDiv) timerDiv.textContent = '';
                        // Re-find buttons (Streamlit may have re-rendered)
                        getChoiceBtns().forEach(function(b) {{
                            b.disabled = false;
                            b.style.opacity = '1';
                            b.style.pointerEvents = 'auto';
                        }});
                    }}
                }}, 250);
            }})();
            </script>""",
            height=0,
        )

    # "I made a mistake" — one undo only, like Tinder swipe-back
    if idx > 0 and not st.session_state.get("used_goback_for_pair") == idx:
        st.button(
            "↩️ I made a mistake — go back",
            key=f"goback_{idx}",
            on_click=_go_back_one_pair,
        )

    st.divider()

    # --- DOCUMENTS: side by side ---
    col_a, col_b = st.columns(2)

    with col_a:
        st.markdown(f"**{DOC_A_LABEL}**")
        if a_truncated:
            if st.session_state.get("expanded_a"):
                st.markdown(f'<div class="doc-card">{doc_a_text}</div>', unsafe_allow_html=True)
                st.button(SHOW_LESS_LABEL, key=f"collapse_a_{idx}",
                          on_click=_set_expanded, args=("a", False))
            else:
                st.markdown(f'<div class="doc-card">{doc_a_short}</div>', unsafe_allow_html=True)
                st.button(SHOW_MORE_LABEL, key=f"expand_a_{idx}",
                          on_click=_set_expanded, args=("a", True))
        else:
            st.markdown(f'<div class="doc-card">{doc_a_text}</div>', unsafe_allow_html=True)

    with col_b:
        st.markdown(f"**{DOC_B_LABEL}**")
        if b_truncated:
            if st.session_state.get("expanded_b"):
                st.markdown(f'<div class="doc-card">{doc_b_text}</div>', unsafe_allow_html=True)
                st.button(SHOW_LESS_LABEL, key=f"collapse_b_{idx}",
                          on_click=_set_expanded, args=("b", False))
            else:
                st.markdown(f'<div class="doc-card">{doc_b_short}</div>', unsafe_allow_html=True)
                st.button(SHOW_MORE_LABEL, key=f"expand_b_{idx}",
                          on_click=_set_expanded, args=("b", True))
        else:
            st.markdown(f'<div class="doc-card">{doc_b_text}</div>', unsafe_allow_html=True)


def _set_confidence(value: int):
    """Store confidence via on_click — Streamlit auto-rerenders after."""
    st.session_state["current_confidence"] = value


def _set_expanded(side: str, expanded: bool):
    """Toggle doc expansion via on_click — reliable session_state update."""
    st.session_state[f"expanded_{side}"] = expanded
    if expanded:
        st.session_state[f"ever_expanded_{side}"] = True


def _record_choice(chosen_side: str, pair: dict, doc_a_id: str, doc_b_id: str):
    """Record the judge's choice for the current pair and advance.

    All data stays in session_state — NO Supabase call here.
    """
    confidence = st.session_state.get("current_confidence")
    now = datetime.now(timezone.utc).isoformat()
    pair_start = st.session_state.get("pair_start_time", now)

    # Calculate time spent on this pair
    try:
        start_dt = datetime.fromisoformat(pair_start)
        end_dt = datetime.fromisoformat(now)
        time_spent_seconds = round((end_dt - start_dt).total_seconds(), 1)
    except (ValueError, TypeError):
        time_spent_seconds = None

    # Server-side guard: reject submissions faster than the minimum
    if time_spent_seconds is not None and time_spent_seconds < MIN_SECONDS_PER_PAIR:
        return  # silently ignore — the JS countdown should prevent this anyway

    control_side = pair["control_side"]
    chose_control = (chosen_side == control_side)

    response = {
        "pair_index": st.session_state["current_pair"],
        "pair_id": pair.get("pair_id", ""),
        "control_doc_id": pair["control_doc_id"],
        "test_doc_id": pair["test_doc_id"],
        "stance": pair["stance"],
        "control_side": control_side,
        "chosen_side": chosen_side,
        "chose_control": chose_control,
        "confidence": confidence,
        "timestamp": now,
        "time_spent_seconds": time_spent_seconds,
        "doc_a_ever_expanded": st.session_state.get("ever_expanded_a", False),
        "doc_b_ever_expanded": st.session_state.get("ever_expanded_b", False),
        "doc_a_expanded_at_choice": st.session_state.get("expanded_a", False),
        "doc_b_expanded_at_choice": st.session_state.get("expanded_b", False),
    }

    st.session_state["responses"].append(response)

    # Save to Supabase in background thread — zero UI latency, zero data loss
    if not DEV_MODE:
        sid = st.session_state.get("session_id")
        if sid:
            _save_in_background(
                sid,
                st.session_state["responses"],
                len(st.session_state["responses"]),
            )

    # Reset state for next pair
    st.session_state["current_confidence"] = None
    st.session_state["expanded_a"] = False
    st.session_state["expanded_b"] = False
    st.session_state["ever_expanded_a"] = False
    st.session_state["ever_expanded_b"] = False

    # Advance
    st.session_state["current_pair"] += 1
    st.session_state["pair_start_time"] = datetime.now(timezone.utc).isoformat()


def _go_back_one_pair():
    """Undo the last response and return to that pair.

    One undo per pair only — after going back, the go-back button
    disappears for that pair (like Tinder swipe-back).
    """
    responses = st.session_state.get("responses", [])
    if not responses:
        return

    responses.pop()
    st.session_state["responses"] = responses

    new_pair_idx = max(0, st.session_state["current_pair"] - 1)
    st.session_state["current_pair"] = new_pair_idx
    st.session_state["stage"] = "pairs"
    st.session_state["pair_start_time"] = datetime.now(timezone.utc).isoformat()

    # Mark that this pair already used its one undo — button won't show again
    st.session_state["used_goback_for_pair"] = new_pair_idx

    st.session_state["current_confidence"] = None
    st.session_state["expanded_a"] = False
    st.session_state["expanded_b"] = False
    st.session_state["ever_expanded_a"] = False
    st.session_state["ever_expanded_b"] = False


# ---------------------------------------------------------------------------
# Thank you screen
# ---------------------------------------------------------------------------
def render_thank_you():
    _, center, _ = st.columns([1, 2, 1])
    with center:
        st.balloons()
        st.title(THANK_YOU_TITLE)
        n = len(st.session_state.get("responses", []))
        st.write(f"You evaluated **{n}** pair{'s' if n != 1 else ''}. {THANK_YOU_TEXT}")
        if st.session_state.get("raffle_contact"):
            st.info(THANK_YOU_RAFFLE)


# ---------------------------------------------------------------------------
# Main router
# ---------------------------------------------------------------------------
_BEFOREUNLOAD_JS = """
<script>
window.top.addEventListener('beforeunload', function (e) {
    e.preventDefault();
    e.returnValue = '';
});
</script>
"""


def render_study_closed():
    """Lock screen shown when the study is closed."""
    _, center, _ = st.columns([1, 2, 1])
    with center:
        st.markdown("---")
        st.markdown(
            "<h2 style='text-align:center;'>Hi</h2>"
            "<p style='text-align:center; font-size:1.1rem;'>"
            "This study has been closed and the raffle winner will be contacted shortly.<br><br>"
            "If you participated in this survey, thank you so much for your participation."
            "</p>",
            unsafe_allow_html=True,
        )
        st.markdown("---")

        st.markdown("")
        with st.expander("Reviewer / admin access"):
            pwd = st.text_input("Password", type="password", key="admin_pwd")
            if st.button("Unlock"):
                if pwd == ADMIN_PASSWORD:
                    st.session_state["admin_unlocked"] = True
                    st.rerun()
                else:
                    st.error("Incorrect password.")


def main():
    init_session()

    if STUDY_CLOSED and not st.session_state.get("admin_unlocked"):
        render_study_closed()
        return

    # Warn users before they accidentally refresh or close the tab
    if st.session_state.get("stage") == "pairs":
        st_html(_BEFOREUNLOAD_JS, height=0)

    if DEV_MODE:
        st.info(f"**DEV MODE** — Supabase off, {DEV_PAIRS} pairs only. Remove `?dev=1` for real mode.")

    stage = st.session_state.get("stage", "welcome")

    if stage == "welcome":
        render_welcome()
    elif stage == "pairs":
        render_pair()
    elif stage == "thank_you":
        render_thank_you()


if __name__ == "__main__":
    main()
