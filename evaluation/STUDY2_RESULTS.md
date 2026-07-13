# Study 2 — AC-Coverage Results (preliminary)

**Date:** 8 July 2026
**Status:** labels drafted by AI annotator (Claude) per `ANNOTATION_PROTOCOL.md` from
full step text fetched live from ADO; **pending review by the researcher (annotator of
record)**. 14 low-confidence and 46 medium-confidence labels are the review queue.
Until that review, treat every number here as *preliminary*.

## 1. Sample

8 stories, 216 test cases, **64 acceptance criteria (60 in scope)**. The June seeding
had flattened nested AC bullets; 4 dropped requirements were restored (Mirror Tool:
instant result, proportions, flipped-in-place; Properties Panel: the Rotation block),
so the AC count rose from 60 to 64. Out-of-scope ACs (protocol §2): three Mac-shortcut
ACs (macOS is not a test platform at the host organisation) and one meta-statement
("story is independent"), all in story 270457.

| Story | Difficulty | Tests | ACs (in scope) |
|-------|-----------|------:|---------------:|
| 269496 Model Space & Canvas | easy | 7 | 4 |
| 273567 Top Menu Toolbar | easy | 61 | 4 |
| 271307 New Document Dialog | medium | 10 | 8 |
| 270457 Zoom Shortcuts | medium | 12 | 10 (6) |
| 270472 Mirror Tool | medium | 24 | 9 |
| 271053 Error Handling & Logging | hard | 19 | 10 |
| 270739 Properties Panel – Design | hard | 32 | 10 |
| 270479 Basic Shape Tools | hard | 51 | 9 |

## 2. Headline results (lenient = as labeled)

| Story | Recall | Precision | F1 | Notes |
|-------|-------:|----------:|---:|-------|
| 269496 | 1.000 | 0.857 | 0.923 | 1 spurious: launch-time performance test (no AC) |
| 271307 | 0.875 | 1.000 | 0.933 | AC4 uncovered (unit dropdown follows app-wide setting) |
| 270457 | 1.000 | 1.000 | 1.000 | Mac ACs excluded (see §4) |
| 271053 | 1.000 | 1.000 | 1.000 | |
| 270472 | 1.000 | 1.000 | 1.000 | |
| 270739 | 1.000 | 1.000 | 1.000 | |
| 270479 | 1.000 | 1.000 | 1.000 | 9 resize tests credited leniently (see §3) |
| 273567 | 1.000 | 0.984 | 0.992 | 1 spurious: a11y scan with no a11y AC |
| **Micro (pooled)** | **0.983** | **0.991** | **0.987** | 59/60 ACs; 214/216 valid tests |
| **Macro (per-story)** | **0.984** | **0.980** | **0.982** | |

## 3. Strict variant (all 14 low-confidence credits flipped to spurious)

Low-confidence labels are cases where a test maps to an AC only under a generous
reading (e.g. resize tests credited to AC7 whose text lists select/move/delete/undo
but not resize; accessibility tests in stories that have no accessibility AC).

| Aggregate | Recall | Precision | F1 |
|-----------|-------:|----------:|---:|
| Micro | 0.983 | **0.931** | **0.956** |
| Macro | 0.984 | 0.926 | 0.955 |

Recall is unchanged (every AC covered leniently is also covered by a high-confidence
test). The precision drop is concentrated in 270479 (0.824: the 9 resize tests) and
reflects a real generator behaviour: **tests for plausible QA concerns that no AC
specifies**. The truth is between the two variants; the human review of the 14
low-confidence labels decides each case.

## 4. Platform-scope sensitivity (Mac ACs in scope)

If the three Mac-shortcut ACs of 270457 are counted in scope, story recall drops to
0.667 and pooled micro recall to 0.937 (F1 0.963). The exclusion is an environment
constraint (macOS not tested at the host organisation), not a generator success;
both numbers are reported.

## 5. By difficulty (micro, lenient / strict)

| Stratum | Stories | Recall | Precision | F1 (lenient) | F1 (strict) |
|---------|--------:|-------:|----------:|-------------:|------------:|
| easy | 2 | 1.000 | 0.971 / 0.956 | 0.985 | 0.977 |
| medium | 3 | 0.957 | 1.000 / 0.957 | 0.978 | 0.957 |
| hard | 3 | 1.000 | 1.000 / 0.902 | 1.000 | 0.948 |

Recall does not degrade with difficulty — the coverage-validation loop appears to hold
even for composite, system-level stories. The strict-precision degradation on hard
stories (0.902) comes from over-production: extra tests beyond the ACs, not missing
coverage. This contrasts with pure-LLM results (e.g. Li & Yuan 2024: accuracy 84.6%
easy → 57.9% hard).

## 6. Genuine gaps found (value of the ground truth)

Uncovered AC:
- **271307 AC4** — "Unit dropdown follows current Unit of Measure setting": no test
  exercises the app-wide setting's effect on the dialog.

Spurious tests (both confidence-independent):
- **269496-030** — launch-time performance test; no AC mentions performance.
- **273567-400** — accessibility scan; story has no accessibility AC.

Partial-coverage gaps recorded in baseline notes (count as covered, but thin):
- 270479 AC7: **delete** and **undo/redo** of drawn shapes untested (only select/move).
- 270739 AC3: decimal input and range validation untested (whole numbers only).
- 270739 AC5: fractional values untested.
- 270479 AC9: single thin accessibility test for a 51-test suite.

Content defects observed while labeling (Study 1 territory; feed to Judge analysis):
- 270739-030/-035: N-coordinate change asserts *horizontal* movement.
- 270739-100: expected value unchanged after m→in unit switch (should convert).
- 270739-076/-077: expected results misaligned with actions (undo/redo semantics).
- 271053-030/-035/-045/-090/-095: "non-fatal error" chains that expect crash dialogs.
- 273567-170: Show/Hide *Rules* asserts the drawn line hides instead of the rulers.
- 273567-150: first step's action/expected swapped.
- 270479-067: scale copy slip ("1 in = 1ft" after setting 3 ft).

## 7. Method provenance

- Fetch: `scripts/fetch_sample_stories_for_labeling.py` (titles + steps, live ADO).
- Labels: `evaluation/baselines/*.ac.yaml` (`covers` + `confidence` + `note` per test).
- Score: `python scripts/evaluate_ac_coverage.py` → `output/ac_coverage_report.{md,csv}`.
- Protocol: `evaluation/ANNOTATION_PROTOCOL.md` (AC construction, in-scope rules,
  covers rules, difficulty rubric, provenance statement).
- For the dissertation: report as "AI-assisted annotation with human verification";
  the researcher's review of the 60 non-high-confidence labels converts these
  preliminary numbers to final. Second annotator (κ) still recommended on ≥2 stories.
