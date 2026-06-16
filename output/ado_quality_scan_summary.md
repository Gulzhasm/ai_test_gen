# Production Quality Scan — Plan 271600 / Suite 284016

Tool-generated test cases scanned with the framework's deterministic validator (`TestCaseValidator`), project `env-quickdraw`.

- **Corpus:** 996 test cases across 55 user stories (requirement suites)
- **Strict full-contract clean:** 656/996 = **65.9%** (all rules, incl. per-test prereq/close)
- **Content-clean:** 877/996 = **88.1%** (ignoring the prereq/close suite convention)
- Flagged only for prereq/close convention: 221; flagged for a content issue: 119

## Issue breakdown (by error count)

- close_step: 238
- missing_prereq: 183
- expected_result: 59
- title_format: 54
- forbidden_language: 7
