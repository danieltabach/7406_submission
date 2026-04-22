"""
Classifier Analysis: Can a model distinguish control vs treatment
documents using extracted features alone (without reading the text)?

Uses SMOTE to oversample inside each CV fold, then repeated
stratified 5-fold cross-validation.

ISyE 7406 - Daniel Tabach
"""

import csv
import os
import numpy as np
from sklearn.preprocessing import StandardScaler
from sklearn.model_selection import RepeatedStratifiedKFold
from sklearn.linear_model import LogisticRegression
from sklearn.neighbors import KNeighborsClassifier
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import accuracy_score, f1_score
from imblearn.over_sampling import SMOTE
from imblearn.pipeline import Pipeline as ImbPipeline

# ============================================================
# Load feature matrix
# ============================================================

# Set up paths relative to this script
DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")

# Load document-level NLP features (one row per document)
with open(os.path.join(DATA_DIR, "nlp_features.csv")) as f:
    rows = list(csv.DictReader(f))

# Load writer session data for process features (turns, tokens, duration)
# Keyed by doc_id so we can join with the NLP features
with open(os.path.join(DATA_DIR, "writer_sessions.csv")) as f:
    sessions = {r["doc_id"]: r for r in csv.DictReader(f)}


# ============================================================
# Define feature columns
# ============================================================

# 7 stylometric features extracted from the submission text
STYLOMETRIC = [
    "type_token_ratio",        # unique words / total words — vocabulary diversity
    "avg_sentence_length",     # words per sentence — structural complexity
    "sentence_length_stddev",  # standard deviation of sentence lengths — "burstiness"
    "first_person_rate_per1k", # I/me/my/we/our per 1000 words — personal voice
    "hedging_rate_per1k",      # perhaps/might/possibly per 1000 words — tentative language
    "contraction_rate_per1k",  # don't/can't/it's per 1000 words — casual tone
    "overlap_score",           # max similarity between submission and any AI response
]

# 3 process features from the writer's chatbot interaction
PROCESS = [
    "n_turns",     # number of messages the writer sent to the chatbot
    "n_tokens",    # total words in all chatbot responses
    "duration_s",  # seconds the writer spent on the task
]

# Combined list of all 10 features
ALL_FEATURES = STYLOMETRIC + PROCESS


# ============================================================
# Build X (feature matrix) and y (labels)
# ============================================================

X_rows = []  # will become a numpy array of shape (n_docs, 10)
y_rows = []  # will become a numpy array of 0s and 1s

for r in rows:
    # Skip 2 documents flagged for data-collection anomalies
    if r.get("exclude_from_classifier", "").lower() == "true":
        continue

    doc_id = r["doc_id"]

    # Pull the 7 stylometric features from nlp_features.csv
    feat = [float(r[c]) for c in STYLOMETRIC]

    # Pull the 3 process features from writer_sessions.csv (joined by doc_id)
    sess = sessions.get(doc_id, {})
    feat += [float(sess.get(c, 0)) for c in PROCESS]

    X_rows.append(feat)

    # Label: 0 = control (no warning), 1 = treatment (AI detection warning)
    y_rows.append(0 if r["condition"] == "control" else 1)

# Convert to numpy arrays for sklearn
X = np.array(X_rows, dtype=float)  # shape: (39, 10)
y = np.array(y_rows)                # shape: (39,)

print(f"Dataset: {X.shape[0]} documents, {X.shape[1]} features")
print(f"  Control: {(y == 0).sum()}, Treatment: {(y == 1).sum()}")
print(f"  Features: {ALL_FEATURES}")


# ============================================================
# SMOTE + Repeated Stratified 5-Fold CV
# ============================================================

# Define the four classifiers to evaluate (all from course material)
classifiers = {
    "Logistic Regression": LogisticRegression(max_iter=1000, random_state=42),
    "KNN (k=3)": KNeighborsClassifier(n_neighbors=3),   # 3 nearest neighbors
    "KNN (k=5)": KNeighborsClassifier(n_neighbors=5),   # 5 nearest neighbors
    "Random Forest": RandomForestClassifier(
        n_estimators=100,  # 100 trees
        max_depth=3,       # shallow trees to reduce overfitting
        random_state=42,
    ),
}

# Repeated stratified 5-fold CV: 5 folds x 20 repeats = 100 total fits
cv = RepeatedStratifiedKFold(n_splits=5, n_repeats=20, random_state=42)

print(f"\n{'Classifier':<25} {'Accuracy':>10} {'F1':>10}")

for name, clf in classifiers.items():
    # Build a pipeline that runs inside each CV fold:
    #   1. StandardScaler: normalize features to zero mean, unit variance
    #   2. SMOTE: generate synthetic training examples (k_neighbors=3)
    #   3. Classifier: fit on the oversampled training data
    #
    # SMOTE is applied INSIDE each fold so the test set stays untouched.
    # This prevents data leakage from synthetic examples.
    pipe = ImbPipeline([
        ("scaler", StandardScaler()),                          # step 1: normalize
        ("smote", SMOTE(random_state=42, k_neighbors=3)),      # step 2: oversample
        ("clf", clf),                                          # step 3: classify
    ])

    # Collect accuracy and F1 for each of the 100 folds
    accs = []
    f1s = []

    for train_idx, test_idx in cv.split(X, y):
        # Fit on training fold (after scaling + SMOTE)
        pipe.fit(X[train_idx], y[train_idx])

        # Predict on the held-out test fold
        preds = pipe.predict(X[test_idx])

        # Record metrics for this fold
        accs.append(accuracy_score(y[test_idx], preds))
        f1s.append(f1_score(y[test_idx], preds, zero_division=0))

    # Print mean and standard deviation across all 100 folds
    print(f"  {name:<23} {np.mean(accs):.3f} +/- {np.std(accs):.3f}  "
          f"{np.mean(f1s):.3f} +/- {np.std(f1s):.3f}")


# ============================================================
# Feature importance (Random Forest on full dataset)
# ============================================================

# Fit a Random Forest on ALL data (after SMOTE) to extract
# Gini importance — which features does the model rely on most?
print("\nRandom Forest feature importances (full-data fit after SMOTE):")

full_pipe = ImbPipeline([
    ("scaler", StandardScaler()),
    ("smote", SMOTE(random_state=42, k_neighbors=3)),
    ("clf", RandomForestClassifier(n_estimators=100, max_depth=3, random_state=42)),
])

# Fit on all data
full_pipe.fit(X, y)

# Extract Gini importance from the fitted RF
importances = full_pipe.named_steps["clf"].feature_importances_

# Print sorted by importance (highest first)
for fname, imp in sorted(zip(ALL_FEATURES, importances), key=lambda x: -x[1]):
    print(f"  {fname:<30} {imp:.4f}")

print("\nDone.")
