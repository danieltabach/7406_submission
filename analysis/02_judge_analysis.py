"""
Phase 2 Judge Analysis: binomial test, confidence intervals,
by-stance breakdown, confidence/time/fatigue analysis, per-doc rates.

ISyE 7406 - Daniel Tabach
"""

import csv
import os
import numpy as np
from scipy import stats
from collections import defaultdict
import matplotlib.pyplot as plt

# ============================================================
# Load data
# ============================================================

# Set up paths relative to this script
DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
FIG_DIR = os.path.join(os.path.dirname(__file__), "figures")
os.makedirs(FIG_DIR, exist_ok=True)  # create figures/ if needed

# Load the judge response data — each row is one paired evaluation
# where a judge compared a control doc vs a test doc and chose one
with open(os.path.join(DATA_DIR, "judge_responses.csv")) as f:
    responses = list(csv.DictReader(f))

# Total number of paired evaluations
n = len(responses)
print(f"Loaded {n} judge responses")


# ============================================================
# Overall detection accuracy
# ============================================================

# Key variable: chose_control
#   True  = judge picked the CONTROL (unwarned) document as human
#   False = judge picked the TEST (warned) document as human
#
# Our hypothesis: warned writers edit to sound more human, so
# judges should pick the TEST doc as human MORE often.
# This means we expect the control-as-human rate to be BELOW 50%.

# Count how many judges picked the control doc as human
chose_ctrl = sum(1 for r in responses if r["chose_control"] == "True")
chose_test = n - chose_ctrl  # the rest picked the test doc
rate_ctrl = chose_ctrl / n   # proportion who picked control as human

# Run a two-sided exact binomial test: is the rate different from 50%?
binom_result = stats.binomtest(chose_ctrl, n, 0.5, alternative="two-sided")

# Compute 95% Wilson confidence interval (more robust than Wald for proportions)
ci = binom_result.proportion_ci(confidence_level=0.95, method="wilson")

# Print the headline result
print("\nOVERALL DETECTION ACCURACY")
print(f"  Total responses:               {n}")
print(f"  Picked control as human:       {chose_ctrl} ({rate_ctrl:.2%})")
print(f"  Picked test as human:          {chose_test} ({1 - rate_ctrl:.2%})")
print(f"  95% Wilson CI (ctrl-as-human): [{ci.low:.4f}, {ci.high:.4f}]")
print(f"  Binomial p-value vs 50%:       {binom_result.pvalue:.6f}")
print(f"  Hypothesis direction:          {'supported' if rate_ctrl < 0.5 else 'not supported'}")


# ============================================================
# By stance (FOR vs AGAINST)
# ============================================================

# Check if the effect is consistent across both writing prompts
# (FOR remote work vs AGAINST remote work)
print("\nBY STANCE")

for stance in ["FOR", "AGAINST"]:
    # Filter responses to just this stance
    subset = [r for r in responses if r["stance"] == stance]
    ns = len(subset)

    # Count control picks and compute rate
    k = sum(1 for r in subset if r["chose_control"] == "True")
    rate = k / ns

    # Run binomial test for this stance subset
    result = stats.binomtest(k, ns, 0.5, alternative="two-sided")
    ci_s = result.proportion_ci(confidence_level=0.95, method="wilson")

    print(f"  {stance:<8} n={ns}  ctrl-as-human={rate:.2%}  "
          f"CI=[{ci_s.low:.4f}, {ci_s.high:.4f}]  p={result.pvalue:.6f}")


# ============================================================
# By confidence level (1-5 scale)
# ============================================================

# After each pair, judges rated their confidence from 1 (low) to 5 (high)
# Question: do more confident judges perform differently?
print("\nBY CONFIDENCE LEVEL")

# Some responses may be missing a confidence rating — filter them out
conf_responses = [r for r in responses if r["confidence"].strip()]

# Get the unique confidence levels present in the data
conf_levels = sorted(set(r["confidence"] for r in conf_responses))

for c in conf_levels:
    # Filter to responses at this confidence level
    subset = [r for r in conf_responses if r["confidence"] == c]

    # Count how many picked control as human
    k = sum(1 for r in subset if r["chose_control"] == "True")
    rate = k / len(subset)

    print(f"  conf={c}  n={len(subset):<4}  ctrl-as-human={rate:.2%}")

# Compute Spearman rank correlation between confidence and choosing control
conf_arr = [int(r["confidence"]) for r in conf_responses]      # confidence as integer
chose_arr = [1 if r["chose_control"] == "True" else 0 for r in conf_responses]  # 1=chose control, 0=chose test
rho, p_rho = stats.spearmanr(conf_arr, chose_arr)

print(f"  Spearman(confidence, chose_control) = {rho:.4f}  p={p_rho:.4f}")


# ============================================================
# By time spent (quartiles)
# ============================================================

# Question: do judges who spend more time reading perform differently?
print("\nBY TIME SPENT (QUARTILES)")

# Extract all time-spent values as floats
times = [float(r["time_spent_seconds"]) for r in responses]

# Compute quartile boundaries
q1, q2, q3 = np.percentile(times, [25, 50, 75])
print(f"  Quartile cutoffs: Q1={q1:.1f}s  median={q2:.1f}s  Q3={q3:.1f}s")

# Label each response by its time quartile
quartile_labels = []
for r in responses:
    t = float(r["time_spent_seconds"])
    if t <= q1:
        quartile_labels.append("Q1 (fastest)")
    elif t <= q2:
        quartile_labels.append("Q2")
    elif t <= q3:
        quartile_labels.append("Q3")
    else:
        quartile_labels.append("Q4 (slowest)")

# Print accuracy for each quartile
for q_label in ["Q1 (fastest)", "Q2", "Q3", "Q4 (slowest)"]:
    # Get indices of responses in this quartile
    idx = [i for i, q in enumerate(quartile_labels) if q == q_label]
    k = sum(1 for i in idx if responses[i]["chose_control"] == "True")
    ns = len(idx)
    print(f"  {q_label:<14} n={ns}  ctrl-as-human={k/ns:.2%}")


# ============================================================
# Fatigue analysis (by tercile within each session)
# ============================================================

# Each judge's responses are split into thirds: early, middle, late
# Question: does accuracy degrade as judges review more pairs?
print("\nFATIGUE ANALYSIS (BY TERCILE)")

for tercile in ["early", "middle", "late"]:
    # Filter to responses in this tercile
    subset = [r for r in responses if r["tercile"] == tercile]

    # Count control picks
    k = sum(1 for r in subset if r["chose_control"] == "True")
    ns = len(subset)

    print(f"  {tercile:<7} n={ns}  ctrl-as-human={k/ns:.2%}")


# ============================================================
# Per-document chosen-as-human rates
# ============================================================

# Check whether the overall effect is spread across many documents
# or concentrated in a few outliers
print("\nPER-DOCUMENT CHOSEN-AS-HUMAN RATES")

doc_chosen = defaultdict(int)  # count: times this doc was chosen as human
doc_seen = defaultdict(int)    # count: times this doc appeared in a pair
ctrl_docs = set()              # track which doc_ids belong to control
test_docs = set()              # track which doc_ids belong to treatment

# Tally up selections across all responses
for r in responses:
    ctrl_id = r["control_doc_id"]  # the control doc in this pair
    test_id = r["test_doc_id"]     # the treatment doc in this pair

    # Both docs were "seen" once in this pair
    doc_seen[ctrl_id] += 1
    doc_seen[test_id] += 1

    # Track which condition each doc belongs to
    ctrl_docs.add(ctrl_id)
    test_docs.add(test_id)

    # Increment the chosen count for whichever doc the judge picked
    if r["chose_control"] == "True":
        doc_chosen[ctrl_id] += 1  # judge picked the control doc
    else:
        doc_chosen[test_id] += 1  # judge picked the test doc

# Build a list of (doc_id, condition, times_seen, times_chosen, rate)
all_docs = sorted(set(list(doc_seen.keys())))
rows = []
for doc in all_docs:
    seen = doc_seen[doc]
    chosen = doc_chosen[doc]
    rate = chosen / seen  # fraction of times this doc was picked as human
    cond = "control" if doc in ctrl_docs else "test"
    rows.append((doc, cond, seen, chosen, rate))

# Sort by rate descending to see which docs look most "human" to judges
rows.sort(key=lambda x: -x[4])

# Print the full table
print(f"\n  {'Doc ID':<18} {'Cond':<10} {'Seen':<6} {'Chosen':<8} {'Rate':<8}")
for doc, cond, seen, chosen, rate in rows:
    print(f"  {doc:<18} {cond:<10} {seen:<6} {chosen:<8} {rate:.1%}")

# Summary: how many docs in each condition are above the 50% chance line?
ctrl_rates = [r[4] for r in rows if r[1] == "control"]
test_rates = [r[4] for r in rows if r[1] == "test"]
print(f"\n  Control: mean={np.mean(ctrl_rates):.1%}, "
      f"above 50%: {sum(1 for r in ctrl_rates if r > 0.5)}/{len(ctrl_rates)}")
print(f"  Test:    mean={np.mean(test_rates):.1%}, "
      f"above 50%: {sum(1 for r in test_rates if r > 0.5)}/{len(test_rates)}")


# ============================================================
# Forest plot: confidence interval visualization
# ============================================================

# Create a horizontal forest plot showing the 95% Wilson CI
# for the control-as-human rate: overall and by stance.
# If the hypothesis holds, all intervals should sit below the 50% line.
fig, ax = plt.subplots(figsize=(6.5, 3.4))

# Build the three rows: overall, FOR stance, AGAINST stance
plot_rows = []
plot_rows.append(("Overall", rate_ctrl * 100, ci.low * 100, ci.high * 100, n))

for stance in ["FOR", "AGAINST"]:
    subset = [r for r in responses if r["stance"] == stance]
    ns = len(subset)
    k = sum(1 for r in subset if r["chose_control"] == "True")
    rate = k / ns
    result = stats.binomtest(k, ns, 0.5)
    ci_s = result.proportion_ci(confidence_level=0.95, method="wilson")
    plot_rows.append((f"{stance} stance", rate * 100, ci_s.low * 100, ci_s.high * 100, ns))

# Y positions: top to bottom
y_positions = list(range(len(plot_rows) - 1, -1, -1))

# Draw each row as a dot (point estimate) + dashed line (CI)
for y, (label, rate, ci_lo, ci_hi, count) in zip(y_positions, plot_rows):
    color = "#222" if label == "Overall" else "#555"  # darker dot for overall
    size = 9 if label == "Overall" else 7              # bigger dot for overall

    # Point estimate
    ax.plot(rate, y, "o", color=color, markersize=size, zorder=3)

    # Confidence interval as dashed horizontal line
    ax.hlines(y, ci_lo, ci_hi, color=color, linewidth=1.5, linestyle="--", zorder=2,
              label="95% Wilson CI" if y == y_positions[0] else None)

    # Label centered above the line showing rate, CI bounds, and sample size
    ax.text((ci_lo + ci_hi) / 2, y + 0.22,
            f"{rate:.1f}%  [{ci_lo:.1f}, {ci_hi:.1f}]  n={count}",
            ha="center", va="bottom", fontsize=9, color="#333")

# Draw a red dashed vertical line at 50% (the chance baseline)
ax.axvline(50, color="red", lw=1.0, ls="--", zorder=1)
ax.text(50.15, y_positions[0] + 0.45, "chance (50%)", fontsize=8, color="red", va="bottom")

# Format axes
ax.set_yticks(y_positions)
ax.set_yticklabels([r[0] for r in plot_rows], fontsize=10)
ax.set_xlabel("% picked control (unwarned) as human", fontsize=10)
ax.set_xlim(39, 54)
ax.set_ylim(-0.6, len(plot_rows) - 0.5 + 0.7)
ax.grid(True, axis="x", alpha=0.2, linestyle="--")
ax.legend(loc="lower left", fontsize=8, frameon=True)
ax.set_title("95% Wilson confidence intervals vs. chance", fontsize=11, pad=10)

fig.tight_layout()
fig.savefig(os.path.join(FIG_DIR, "judge_ci_forest.pdf"), bbox_inches="tight")
fig.savefig(os.path.join(FIG_DIR, "judge_ci_forest.png"), dpi=150, bbox_inches="tight")
print("\nSaved: judge_ci_forest.pdf/png")

print("\nDone.")
