# Can Humans Detect AI? Mining Textual Signals of AI-Assisted Writing Under Varying Scrutiny Conditions

ISyE 7406: Data Mining & Statistical Learning - Spring 2026  
Daniel Tabach (dtabach3@gatech.edu)

## Overview

A two-phase controlled experiment testing whether the threat of AI detection changes how people write with AI, and whether human judges can tell the difference.

- **Phase 1**: 21 participants write opinion pieces with an AI chatbot. Half are warned their submission will be scanned by "AI detection software."
- **Phase 2**: 251 judges evaluate paired documents (one control, one treatment) and pick which was "written by a human."

## Live Apps

- **Writer App**: https://danieltabach-human-ai-detection-human-ai-detectionapp-7406.streamlit.app/
- **Judge App**: https://humanaidetection-judges.streamlit.app/

## Repository Structure

```
apps/                  # Streamlit app source code (writer + judge)
data/                  # Sanitized datasets (no PII, no API keys)
  documents.csv        # 41 validated submission texts
  nlp_features.csv     # Stylometric features per document
  judge_responses.csv  # 1,999 paired judge evaluations
  writer_sessions.csv  # Per-task behavioral metrics
analysis/              # Analysis scripts (run in order)
  01_eda.py            # Phase 1 descriptive EDA + plots
  02_judge_analysis.py # Phase 2 binomial test, CI, fatigue analysis
  03_classifier.py     # SMOTE + stratified CV classifiers
report/                # Final compiled report (PDF)
```

## Running the Analysis

```bash
pip install numpy scipy matplotlib scikit-learn imbalanced-learn
cd analysis
python 01_eda.py
python 02_judge_analysis.py
python 03_classifier.py
```

## Key Findings

- Judges identified the warned (treatment) document as human **54.13%** of the time vs 45.87% for control (p = 0.000243).
- No classifier (logistic regression, KNN, random forest) could distinguish the two groups from features alone (best accuracy: 47.7%).
- The warning changed the *process* (more turns, more time) but not the *product* (AI overlap scores nearly identical).
