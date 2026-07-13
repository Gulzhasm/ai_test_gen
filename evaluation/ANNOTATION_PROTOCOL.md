# Study 2 — AC-Coverage Annotation Protocol

**Purpose.** Rules for authoring the ground-truth labels in `baselines/*.ac.yaml`.
Written down so that (a) labels are applied consistently across all 8 stories,
(b) a second annotator can replicate the procedure for inter-rater agreement, and
(c) the dissertation can describe the method precisely.

## 1. AC list construction

- The AC unit is a **top-level bullet** of the story's Acceptance Criteria field in ADO.
- Nested sub-bullets are **folded into their parent's text** (e.g. "Shape Tools available
  from both: Left Toolbar; Top Menu → Draw" is one AC).
- Exception: where the source formatting placed genuine standalone requirements at
  top level after a nested list (Mirror Tool: "result appears instantly", "proportions
  unchanged", "flipped in place"; Properties Panel: the "Rotation:" block), each such
  requirement is its own AC. The June seeding dropped these; they are restored, and the
  per-story AC counts updated accordingly.
- "Out of scope for Phase 1" statements inside the AC field (hotkeys, tooltips,
  templates, Landscape) are **not** ACs; they bound the scope of sibling ACs.

## 2. `in_scope` rules

An AC is marked `in_scope: false` (excluded from recall's denominator) only when:

- **Meta/process statement**, not verifiable application behaviour — e.g. 270457 AC10
  "This story is independent and assigned separately".
- **Platform excluded from the test plan**: the host organisation tests Windows 11,
  iPad, and Android tablet only; macOS is not a supported test platform. The three
  Mac-shortcut ACs in 270457 are therefore out of scope *for this test plan* — an
  environment constraint, not a generator success. This exclusion is reported openly
  in the writeup (§ threats), with metrics also reported with Mac ACs in scope.

Everything else — including constraints like "no additional UI components" — stays in
scope.

## 3. `covers` rules (per test case)

1. Read **all steps** (action + expected result), not just the title.
2. A test **covers AC-X** iff at least one step *verifies* (has an expected result
   asserting) the behaviour/property AC-X specifies. Merely touching the feature in a
   setup step does not count. Coverage is judged by the test's **verification
   target(s)** — the behaviours the test is designed to check (title + its central
   assertions). Shared navigation assertions that recur identically across the suite
   (e.g. "the dialog opens" en route in every test) count only for the test(s) whose
   target is that behaviour, not for every test that passes through it.
3. Pre-requisite / launch / close steps never count toward coverage.
4. A test may cover **multiple ACs** — list every AC genuinely verified.
5. **Edge/boundary tests** derived from an AC's stated behaviour (limits, invalid input
   on a specified field, repeated application of a specified operation) cover that AC.
6. **State-variation tests** (same verified property after resize / minimise / reopen /
   platform variant) cover the AC whose property they verify.
7. **Accessibility platform variants** (keyboard navigation, screen reader, contrast)
   cover the story's accessibility AC; if they additionally verify a functional AC's
   behaviour, list that too.
8. `covers: []` (spurious) iff the test's verification target is a property found in
   **no** AC of the story — e.g. performance timing where no AC mentions performance,
   or behaviour invented for a different feature. Redundant duplicates of a covered AC
   are NOT spurious (they still map to a real AC; redundancy shows up in the
   redundancy metric instead).
9. Confidence: each label gets `confidence: high|medium|low`. Low/medium items are the
   review queue for the human annotator of record and the second annotator.

## 4. Difficulty rubric (story level)

Marked as `difficulty:` in each baseline (ignored by the scorer; used for stratified
reporting). Criteria are properties of the *story*, not of the generated tests:

- **easy** — static display/layout verification; no state machine; ACs are single
  observable properties. (269496 Model Space & Canvas; 273567 Top Menu Toolbar)
- **medium** — one interactive surface (dialog/tool) with bounded states, standard
  input validation, platform variants. (271307 New Document Dialog; 270457 Zoom
  Shortcuts; 270472 Mirror Tool)
- **hard** — composite ACs spanning multiple controls/behaviours, system-level or
  negative paths, cross-cutting couplings (unit/scale conversion, crash/logging
  internals, multi-tool modes). (270739 Properties Panel; 270479 Basic Shape Tools;
  271053 Error Handling & Logging)

## 5. Provenance

Labels are drafted by an AI annotator (Claude) applying this protocol to the full step
text fetched live from ADO (July 2026), then **reviewed and corrected by the researcher,
who is the annotator of record**. The dissertation reports the labeling as
"AI-assisted annotation with human verification"; the second-annotator κ (protocol §2
of the writeup) is computed against independent human labels.
