# llm.py — Anthropic API wrapper

import anthropic
import streamlit as st
from config import MODEL_NAME, MAX_RESPONSE_TOKENS, SYSTEM_PROMPT, TYPO_CORRECTION_PROMPT


def get_client():
    """Initialize Anthropic client with API key from Streamlit secrets."""
    return anthropic.Anthropic(api_key=st.secrets["ANTHROPIC_API_KEY"])


def call_claude(conversation_history: list[dict]) -> dict:
    """
    Send conversation to Claude and return response with metadata.

    Args:
        conversation_history: List of {"role": "user"/"assistant", "content": "..."}

    Returns:
        {"content": str, "input_tokens": int, "output_tokens": int}
    """
    try:
        client = get_client()

        # Strip metadata fields and non-API roles — API only wants role + content
        api_messages = [
            {"role": m["role"], "content": m["content"]}
            for m in conversation_history
            if m["role"] in ("user", "assistant")
        ]

        response = client.messages.create(
            model=MODEL_NAME,
            max_tokens=MAX_RESPONSE_TOKENS,
            system=SYSTEM_PROMPT,
            messages=api_messages,
        )

        return {
            "content": response.content[0].text,
            "input_tokens": response.usage.input_tokens,
            "output_tokens": response.usage.output_tokens,
        }

    except anthropic.BadRequestError as e:
        if "content filtering" in str(e).lower():
            return {
                "content": None,
                "error": "content_filter",
                "input_tokens": 0,
                "output_tokens": 0,
            }
        raise RuntimeError(f"API Error: {e.message}") from e
    except anthropic.APIError as e:
        raise RuntimeError(f"Anthropic API error: {e.message}") from e
    except Exception as e:
        raise RuntimeError(f"Unexpected error calling Claude: {e}") from e


def correct_typos(text: str) -> dict:
    """
    Silent post-submission typo correction.
    Returns {"corrected_text": str, "input_tokens": int, "output_tokens": int}
    On any error, returns original text unchanged (fail-safe).
    """
    try:
        client = get_client()
        response = client.messages.create(
            model=MODEL_NAME,
            max_tokens=MAX_RESPONSE_TOKENS,
            system=TYPO_CORRECTION_PROMPT,
            messages=[{"role": "user", "content": text}],
        )
        return {
            "corrected_text": response.content[0].text,
            "input_tokens": response.usage.input_tokens,
            "output_tokens": response.usage.output_tokens,
        }
    except Exception:
        return {
            "corrected_text": text,
            "input_tokens": 0,
            "output_tokens": 0,
        }
