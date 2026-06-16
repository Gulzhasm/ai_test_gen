# AC-Coverage Evaluation

Measures **precision / recall / F1** of AI-generated test cases against a
human-authored ground truth, at the granularity of **acceptance criteria (AC)**.

- **AC Recall (completeness)** = in-scope ACs covered by ≥1 valid test ÷ total in-scope ACs
- **Test Precision (signal quality)** = generated tests mapping to ≥1 real AC ÷ total generated tests
  (i.e. 1 − hallucination/noise rate)
- **F1** = harmonic mean

This is the lightest defensible baseline: you do **not** hand-write manual test suites — you
only label which AC(s) each *already-generated* test actually covers.

## Workflow

```bash
# 1. Seed a template (test cases pre-filled from the generated CSV in output/)
python scripts/evaluate_ac_coverage.py --make-template --story 269496
#    -> evaluation/baselines/269496.ac.yaml

# 2. Edit that file:
#    - paste the story's acceptance criteria under `acceptance_criteria`
#    - for each test, set `covers: [AC1, ...]` (the AC ids it ACTUALLY tests)
#    - leave `covers: []` for a spurious / hallucinated / out-of-scope test

# 3. Repeat for ~5–8 stories, then compute metrics across all baselines
python scripts/evaluate_ac_coverage.py
#    -> prints summary; writes output/ac_coverage_report.{md,csv}
```

## Files

- `baselines/*.ac.yaml` — your authored ground-truth labelings (one per story). These are what
  the evaluator scores.
- `example.ac.yaml` — a **synthetic** sample showing the format (NOT real data; not scored — it
  lives outside `baselines/`).

## Notes for the dissertation

- Report **both** micro (pooled across stories — weights by size) and macro (per-story average).
- `redundancy` (valid tests per covered AC) shows whether the generator over-produces.
- Threats to validity: single annotator → consider a second labeler on a subset for inter-rater
  agreement; AC-coverage measures completeness/signal, not functional bug-finding effectiveness.
