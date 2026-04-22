"""
Phase 2 — Data Preparation
Extract and clean Phase 1 submissions into a document pool for the judge app.

Usage:
    python prepare_pairs.py                    # writes document_pool.json
    python prepare_pairs.py --print-stats      # also prints pool statistics
"""

import json
import random
import sys
from pathlib import Path

SUPABASE_DUMP = Path(__file__).resolve().parent.parent / "supabase_dump.json"
OUTPUT_PATH = Path(__file__).resolve().parent / "document_pool.json"

# Exclusions decided during Phase 2 planning
EXCLUDE_TASKS = {
    (48, 1),  # James Task 1: unfinished notes, browser issues
}

# Trimming: Vijaya (PID 44) Task 2 has AI revision notes pasted at the end
VIJAYA_TRIM_MARKER = "Key improvements made:"


def load_raw_sessions() -> list[dict]:
    with open(SUPABASE_DUMP, encoding="utf-8") as f:
        return json.load(f)


def is_real_participant(session: dict) -> bool:
    return session["id"] > 15 and session.get("session_complete") is not None


def trim_vijaya_task2(text: str) -> str:
    idx = text.find(VIJAYA_TRIM_MARKER)
    if idx == -1:
        return text
    return text[:idx].rstrip()


def extract_document(session: dict, task_number: int) -> dict | None:
    pid = session["id"]

    if (pid, task_number) in EXCLUDE_TASKS:
        return None

    task_key = f"task_{task_number}"
    task = session.get(task_key)
    if not task or not task.get("submission"):
        return None

    text = task["submission"].get("text", "")
    if not text or not text.strip():
        return None

    # Trim Vijaya's AI revision notes
    if pid == 44 and task_number == 2:
        text = trim_vijaya_task2(text)

    stance = task["stance"]
    condition = session["condition"]
    word_count = len(text.split())

    return {
        "doc_id": f"P{pid}_{stance}",
        "pid": pid,
        "condition": condition,
        "stance": stance,
        "text": text,
        "word_count": word_count,
        "task_number": task_number,
    }


def build_document_pool() -> list[dict]:
    sessions = load_raw_sessions()
    real = [s for s in sessions if is_real_participant(s)]

    documents = []
    for session in real:
        for task_num in (1, 2):
            doc = extract_document(session, task_num)
            if doc:
                documents.append(doc)

    return documents


def generate_session_pairs(pool: list[dict], seed: int | None = None) -> list[dict]:
    """Generate a random set of 18 unique pairs for one judge session.

    Returns a list of pair dicts, each containing:
      - control_doc_id, test_doc_id
      - control_text, test_text
      - control_word_count, test_word_count
      - stance
      - control_side ("left" or "right") — random placement
    """
    rng = random.Random(seed)

    control_for = [d for d in pool if d["condition"] == "control" and d["stance"] == "FOR"]
    control_against = [d for d in pool if d["condition"] == "control" and d["stance"] == "AGAINST"]
    test_for = [d for d in pool if d["condition"] == "test" and d["stance"] == "FOR"]
    test_against = [d for d in pool if d["condition"] == "test" and d["stance"] == "AGAINST"]

    pairs = []

    # FOR pairs: all 9 control docs, randomly matched to 9 of N test docs
    test_for_sample = rng.sample(test_for, len(control_for))
    rng.shuffle(test_for_sample)
    for ctrl, test in zip(control_for, test_for_sample):
        side = rng.choice(["left", "right"])
        pairs.append({
            "control_doc_id": ctrl["doc_id"],
            "test_doc_id": test["doc_id"],
            "control_text": ctrl["text"],
            "test_text": test["text"],
            "control_word_count": ctrl["word_count"],
            "test_word_count": test["word_count"],
            "stance": "FOR",
            "control_side": side,
        })

    # AGAINST pairs: all 9 control docs, randomly matched to 9 of N test docs
    test_against_sample = rng.sample(test_against, len(control_against))
    rng.shuffle(test_against_sample)
    for ctrl, test in zip(control_against, test_against_sample):
        side = rng.choice(["left", "right"])
        pairs.append({
            "control_doc_id": ctrl["doc_id"],
            "test_doc_id": test["doc_id"],
            "control_text": ctrl["text"],
            "test_text": test["text"],
            "control_word_count": ctrl["word_count"],
            "test_word_count": test["word_count"],
            "stance": "AGAINST",
            "control_side": side,
        })

    rng.shuffle(pairs)
    return pairs


def print_stats(pool: list[dict]):
    control_for = [d for d in pool if d["condition"] == "control" and d["stance"] == "FOR"]
    control_against = [d for d in pool if d["condition"] == "control" and d["stance"] == "AGAINST"]
    test_for = [d for d in pool if d["condition"] == "test" and d["stance"] == "FOR"]
    test_against = [d for d in pool if d["condition"] == "test" and d["stance"] == "AGAINST"]

    print(f"Total documents: {len(pool)}")
    print(f"  Control FOR:     {len(control_for)}")
    print(f"  Control AGAINST: {len(control_against)}")
    print(f"  Test FOR:        {len(test_for)}")
    print(f"  Test AGAINST:    {len(test_against)}")
    print()
    print(f"Unique FOR pairs possible:     {len(control_for)} x {len(test_for)} = {len(control_for) * len(test_for)}")
    print(f"Unique AGAINST pairs possible: {len(control_against)} x {len(test_against)} = {len(control_against) * len(test_against)}")
    print(f"Total unique pair combinations: {len(control_for) * len(test_for) + len(control_against) * len(test_against)}")
    print()
    print(f"Pairs per judge session: {len(control_for) + len(control_against)}")
    print()

    # Verify a sample session
    pairs = generate_session_pairs(pool, seed=42)
    print(f"Sample session ({len(pairs)} pairs):")
    for i, p in enumerate(pairs):
        side_label = "ctrl=LEFT" if p["control_side"] == "left" else "ctrl=RIGHT"
        print(f"  {i+1:2d}. {p['stance']:7s} | {p['control_doc_id']:10s} vs {p['test_doc_id']:10s} | {side_label}")


def main():
    pool = build_document_pool()

    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        json.dump(pool, f, indent=2, ensure_ascii=False)

    print(f"Wrote {len(pool)} documents to {OUTPUT_PATH}")

    if "--print-stats" in sys.argv:
        print()
        print_stats(pool)


if __name__ == "__main__":
    main()
