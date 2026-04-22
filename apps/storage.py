# storage.py — Supabase session persistence

import logging
import streamlit as st
from supabase import create_client

from config import determine_condition, determine_writing_order

logger = logging.getLogger(__name__)


def get_supabase_client():
    """Initialize Supabase client from Streamlit secrets."""
    return create_client(
        st.secrets["SUPABASE_URL"],
        st.secrets["SUPABASE_KEY"],
    )


def create_participant() -> dict:
    """
    INSERT a new session row and return assignment info.

    Returns:
        {"pid": int, "condition": str, "writing_order": list[str]}
    """
    client = get_supabase_client()

    # Insert minimal row to get auto-increment ID
    row = (
        client.table("sessions")
        .insert({"condition": "control", "writing_order": ["FOR", "AGAINST"]})
        .execute()
    )
    pid = row.data[0]["id"]

    # Compute real assignment from PID
    condition = determine_condition(pid)
    writing_order = determine_writing_order(pid)

    # Update with real assignment
    (
        client.table("sessions")
        .update({"condition": condition, "writing_order": writing_order})
        .eq("id", pid)
        .execute()
    )

    return {"pid": pid, "condition": condition, "writing_order": writing_order}


def save_session(pid: int, updates: dict) -> None:
    """
    UPDATE a session row with partial data.

    Args:
        pid: The session row ID (participant ID).
        updates: Dict of column values to update.
    """
    client = get_supabase_client()
    client.table("sessions").update(updates).eq("id", pid).execute()


def load_all_sessions() -> list[dict]:
    """Load all completed sessions for analysis."""
    client = get_supabase_client()
    result = (
        client.table("sessions")
        .select("*")
        .not_.is_("session_complete", "null")
        .execute()
    )
    return result.data
