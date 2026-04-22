"""
Phase 2 — Judge Session Storage (Supabase)

Each judge session is a row in the `judge_sessions` table.
Responses are saved incrementally — every pair choice triggers an UPDATE
so data is never lost even if the judge closes the tab.

Schema:
    id               SERIAL PRIMARY KEY
    alias            TEXT
    raffle_contact   TEXT              -- optional
    pairs            JSONB             -- the pairs generated for this session
    responses        JSONB DEFAULT '[]'-- array of response objects
    pairs_completed  INT DEFAULT 0
    total_pairs      INT
    session_start    TIMESTAMPTZ DEFAULT now()
    session_complete TIMESTAMPTZ       -- set when all pairs done or judge exits
    user_agent       TEXT
"""

import streamlit as st
from supabase import create_client

TABLE = "judge_sessions"


def get_supabase_client():
    return create_client(
        st.secrets["SUPABASE_URL"],
        st.secrets["SUPABASE_KEY"],
    )


def create_judge_session(
    alias: str,
    raffle_contact: str | None,
    pairs: list[dict],
    user_agent: str = "",
) -> int:
    """Insert a new judge session and return its ID."""
    db = get_supabase_client()

    # Strip text fields from pairs before storing (save space, keep only IDs/metadata)
    pairs_meta = []
    for p in pairs:
        pairs_meta.append({
            "pair_id": p.get("pair_id", ""),
            "control_doc_id": p["control_doc_id"],
            "test_doc_id": p["test_doc_id"],
            "stance": p["stance"],
            "control_side": p["control_side"],
            "control_word_count": p["control_word_count"],
            "test_word_count": p["test_word_count"],
        })

    row = {
        "alias": alias,
        "raffle_contact": raffle_contact or None,
        "pairs": pairs_meta,
        "responses": [],
        "pairs_completed": 0,
        "total_pairs": len(pairs),
        "user_agent": user_agent,
    }

    result = db.table(TABLE).insert(row).execute()
    return result.data[0]["id"]


def save_judge_response(session_id: int, responses: list[dict], pairs_completed: int):
    """Overwrite the responses array and update pairs_completed.

    Called after every single pair choice so data is always current.
    """
    db = get_supabase_client()
    db.table(TABLE).update({
        "responses": responses,
        "pairs_completed": pairs_completed,
    }).eq("id", session_id).execute()


def complete_judge_session(session_id: int, responses: list[dict], pairs_completed: int):
    """Mark session as complete (all pairs evaluated or judge finished)."""
    from datetime import datetime, timezone

    db = get_supabase_client()
    db.table(TABLE).update({
        "responses": responses,
        "pairs_completed": pairs_completed,
        "session_complete": datetime.now(timezone.utc).isoformat(),
    }).eq("id", session_id).execute()


def load_all_judge_sessions() -> list[dict]:
    """Load all judge sessions (for analysis)."""
    db = get_supabase_client()
    result = db.table(TABLE).select("*").execute()
    return result.data
