"""
Phase 1 EDA: Descriptive statistics and box plots for writer behavior
and stylometric features by condition (control vs treatment).

ISyE 7406 - Daniel Tabach
"""

import csv
import matplotlib.pyplot as plt
import numpy as np
import os

# ============================================================
# Load data
# ============================================================

# Set up paths relative to this script's location
DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
FIG_DIR = os.path.join(os.path.dirname(__file__), "figures")
os.makedirs(FIG_DIR, exist_ok=True)  # create figures/ if it doesn't exist

# Writer session-level data: one row per participant per task
# Columns: pid, condition, task_number, stance, doc_id, n_turns, n_tokens, duration_s, word_count, overlap_score
with open(os.path.join(DATA_DIR, "writer_sessions.csv")) as f:
    sessions = list(csv.DictReader(f))

# Document-level NLP features: one row per validated submission
# Columns include type_token_ratio, avg_sentence_length, contraction_rate_per1k, etc.
with open(os.path.join(DATA_DIR, "nlp_features.csv")) as f:
    features = list(csv.DictReader(f))

print(f"Loaded {len(sessions)} writer-task rows, {len(features)} document feature rows")


# ============================================================
# Behavioral summary by condition
# ============================================================

print("\nBEHAVIORAL SUMMARY BY CONDITION")

# These metrics capture how each group interacted with the AI chatbot
behavioral_metrics = [
    ("n_turns", "Conversation turns"),    # how many messages the writer sent
    ("n_tokens", "Assistant tokens"),      # how many words the AI produced
    ("duration_s", "Duration (seconds)"),  # total time spent on the task
]

for metric, label in behavioral_metrics:
    # Split by condition, skip rows with empty values
    ctrl = [float(s[metric]) for s in sessions if s["condition"] == "control" and s[metric]]
    test = [float(s[metric]) for s in sessions if s["condition"] == "test" and s[metric]]

    # Print median and mean for each group
    print(f"\n  {label}:")
    print(f"    Control (n={len(ctrl)}): median={np.median(ctrl):.1f}, mean={np.mean(ctrl):.1f}")
    print(f"    Test    (n={len(test)}): median={np.median(test):.1f}, mean={np.mean(test):.1f}")


# ============================================================
# Stylometric feature summary by condition
# ============================================================

print("\nSTYLOMETRIC FEATURES BY CONDITION")

# Each feature is extracted from the submission text itself
style_features = [
    ("type_token_ratio", "Type-Token Ratio"),          # vocabulary diversity: unique words / total words
    ("avg_sentence_length", "Avg sentence length"),    # mean words per sentence
    ("sentence_length_stddev", "Sentence-length SD"),  # variation in sentence length ("burstiness")
    ("first_person_rate_per1k", "First-person rate"),   # frequency of I, me, my, we, our per 1000 words
    ("hedging_rate_per1k", "Hedging rate"),             # frequency of perhaps, might, possibly per 1000 words
    ("contraction_rate_per1k", "Contraction rate"),     # frequency of don't, can't, it's per 1000 words
    ("overlap_score", "AI overlap score"),              # max similarity between submission and any AI response
]

for col, label in style_features:
    # Split feature values by condition
    ctrl = [float(r[col]) for r in features if r["condition"] == "control"]
    test = [float(r[col]) for r in features if r["condition"] == "test"]

    # Print median for each group
    print(f"\n  {label}:")
    print(f"    Control (n={len(ctrl)}): median={np.median(ctrl):.3f}")
    print(f"    Test    (n={len(test)}): median={np.median(test):.3f}")


# ============================================================
# Box plots: process features by condition (2x2 grid)
# ============================================================

# Create a 2x2 figure showing how each condition interacted with the chatbot
fig, axes = plt.subplots(2, 2, figsize=(9, 7))

# Four process-level metrics to compare
process_features = [
    ("n_turns", "Conversation turns"),
    ("n_tokens", "Assistant tokens"),
    ("duration_s", "Duration (seconds)"),
    ("word_count", "Word count"),
]

for ax, (col, title) in zip(axes.flatten(), process_features):
    # Gather values for each condition, filtering out empty strings
    ctrl = [float(s[col]) for s in sessions if s["condition"] == "control" and s[col]]
    test = [float(s[col]) for s in sessions if s["condition"] == "test" and s[col]]

    # Draw box plot with colored fills
    bp = ax.boxplot(
        [ctrl, test],                     # data: two groups
        tick_labels=["Control", "Test"],   # x-axis labels
        widths=0.5,                        # box width
        patch_artist=True,                 # enable fill color
    )

    # Color control blue, treatment orange
    bp["boxes"][0].set_facecolor("#a8c8e8")  # light blue for control
    bp["boxes"][1].set_facecolor("#f5b7a3")  # light orange for treatment

    # Format the subplot
    ax.set_title(title, fontsize=11)
    ax.grid(True, axis="y", alpha=0.3, linestyle="--")

# Add overall title and save
fig.suptitle("Process features by condition", fontsize=13, y=1.00)
fig.tight_layout()
fig.savefig(os.path.join(FIG_DIR, "process_features.pdf"), bbox_inches="tight")
fig.savefig(os.path.join(FIG_DIR, "process_features.png"), dpi=150, bbox_inches="tight")
print("\nSaved: process_features.pdf/png")


# ============================================================
# Box plots: lexical and structural features (1x2)
# ============================================================

# Two features that capture vocabulary diversity and sentence rhythm
fig_a, axes_a = plt.subplots(1, 2, figsize=(8, 4))

lexical_features = [
    ("type_token_ratio", "Type-Token Ratio"),       # higher = more diverse vocabulary
    ("sentence_length_stddev", "Sentence-length SD"),  # higher = more varied sentence lengths
]

for ax, (col, title) in zip(axes_a, lexical_features):
    # Split by condition
    ctrl = [float(r[col]) for r in features if r["condition"] == "control"]
    test = [float(r[col]) for r in features if r["condition"] == "test"]

    # Draw colored box plot
    bp = ax.boxplot([ctrl, test], tick_labels=["Control", "Test"],
                    widths=0.5, patch_artist=True)
    bp["boxes"][0].set_facecolor("#a8c8e8")
    bp["boxes"][1].set_facecolor("#f5b7a3")
    ax.set_title(title, fontsize=11)
    ax.grid(True, axis="y", alpha=0.3, linestyle="--")

fig_a.suptitle("Lexical and structural variation by condition", fontsize=13, y=1.00)
fig_a.tight_layout()
fig_a.savefig(os.path.join(FIG_DIR, "features_lexical.pdf"), bbox_inches="tight")
fig_a.savefig(os.path.join(FIG_DIR, "features_lexical.png"), dpi=150, bbox_inches="tight")


# ============================================================
# Box plots: voice and register features (1x2)
# ============================================================

# Two features that capture personal voice and casual tone
fig_b, axes_b = plt.subplots(1, 2, figsize=(8, 4))

voice_features = [
    ("first_person_rate_per1k", "First-person rate (per 1k)"),  # I, me, my frequency
    ("contraction_rate_per1k", "Contraction rate (per 1k)"),    # don't, can't frequency
]

for ax, (col, title) in zip(axes_b, voice_features):
    # Split by condition
    ctrl = [float(r[col]) for r in features if r["condition"] == "control"]
    test = [float(r[col]) for r in features if r["condition"] == "test"]

    # Draw colored box plot
    bp = ax.boxplot([ctrl, test], tick_labels=["Control", "Test"],
                    widths=0.5, patch_artist=True)
    bp["boxes"][0].set_facecolor("#a8c8e8")
    bp["boxes"][1].set_facecolor("#f5b7a3")
    ax.set_title(title, fontsize=11)
    ax.grid(True, axis="y", alpha=0.3, linestyle="--")

fig_b.suptitle("Voice and register features by condition", fontsize=13, y=1.00)
fig_b.tight_layout()
fig_b.savefig(os.path.join(FIG_DIR, "features_voice.pdf"), bbox_inches="tight")
fig_b.savefig(os.path.join(FIG_DIR, "features_voice.png"), dpi=150, bbox_inches="tight")

print("Saved: features_lexical.pdf/png, features_voice.pdf/png")


# ============================================================
# AI overlap score distribution (histogram)
# ============================================================

# Create histogram showing how much each submission reused chatbot text
fig, ax = plt.subplots(figsize=(6, 3.5))

# Collect all overlap scores across both conditions
scores = [float(r["overlap_score"]) for r in features]

# Draw histogram with 20 bins spanning [0, 1]
ax.hist(scores, bins=20, color="#555", edgecolor="white", alpha=0.8)
ax.set_xlabel("AI overlap score")   # 0 = no AI reuse, 1 = full paste
ax.set_ylabel("Count")              # number of documents in each bin
ax.set_title("Distribution of AI overlap scores (all 41 documents)")

fig.tight_layout()
fig.savefig(os.path.join(FIG_DIR, "overlap_distribution.pdf"), bbox_inches="tight")
fig.savefig(os.path.join(FIG_DIR, "overlap_distribution.png"), dpi=150, bbox_inches="tight")
print("Saved: overlap_distribution.pdf/png")

print("\nDone.")
