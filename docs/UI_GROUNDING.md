# Grounded Playwright Generation

Ground generated Playwright selectors in a web app's **real, observed UI elements**
instead of letting the LLM guess them (and emit `// TODO: Update selector`).

## How it works

1. **Extract (one-time per app)** — `scripts/extract_ui_inventory.py` crawls the
   running app with Playwright, mocks its backend at the network layer for
   deterministic data, walks the DOM/accessibility tree, and writes an
   `inventory.json` of selectable elements (role, accessible name, ranked Playwright
   locator, stability, layout/structure features).
2. **Generate (consumer)** — when `application.ui_extraction.inventory_path` exists,
   `PlaywrightGenerator` feeds the inventory into the LLM prompt ("use ONLY these
   selectors") and reports a **grounding-coverage %** for the generated script.

If no inventory is present, generation falls back to the original ungrounded
behavior — nothing breaks.

## Setup

```bash
pip install playwright && playwright install chromium   # Python crawler
```

The target web app must be running. For the dissertation test bed
(github.com/Gulzhasm/gap-trading-forecaster):

```bash
cd gap-trading-forecaster/web && pnpm install && pnpm dev   # serves :3000 (or :3001 if taken)
```

The backend (`:8000`) does **not** need to run — its responses are mocked from
`projects/fixtures/gap-forecaster/*.json` during the crawl.

## Run

```bash
# 1. Capture the inventory (use --base-url if the dev server moved off :3000)
python scripts/extract_ui_inventory.py --project gap-trader --base-url http://localhost:3001

# 2. Generate tests as usual — Playwright output is now grounded
#    (config: projects/configs/gap-trader.yaml, playwright_enabled: true)
```

## Configuration (`application.ui_extraction` in the project YAML)

- `inventory_path` — where `inventory.json` is written/read.
- `api_mocks` — `url_glob` → `body_file` (JSON fixture). Match the **backend**
  origin (e.g. `**/api/scan`), and remember some calls are `POST`.
- `page_states` — tabs are client-side state, so each state is reached by scripted
  steps (`goto`, `click_role`) plus a `ready_selector` to await before snapshotting.

## POM project generation (standalone Page Object Model)

Instead of a flat `.spec.ts`, the framework can generate a **separate POM project** and run it.

```bash
# 1. capture the inventory (as above)
python scripts/extract_ui_inventory.py --project gap-trader --base-url http://localhost:3001
# 2. generate the POM project (page objects deterministic; specs via LLM) and run it
python scripts/generate_ui_automation.py --project gap-trader --run --base-url http://localhost:3001
```

Configured via `application.ui_extraction.pom` (`project_path`, `run_after_generate`). Structure:
- `pages/` — `BasePage.ts` (hand-owned) + `Dashboard/Scanner/Journal/StatsPage.ts` (`@generated`,
  grounded locators copied verbatim from the inventory; `page.`→`this.page.`).
- `fixtures/test-fixtures.ts` (`@generated`) — typed `base.extend` injecting page objects + the
  `page.route` API mocks read from `fixtures/mocks/*.json`.
- `tests/*.spec.ts` (`@generated`) — LLM specs that call ONLY page-object methods. A
  `analyze_method_grounding` check fails any raw `page.getByRole`/`locator` that leaks in; when no
  method fits a step the LLM emits `// UNGROUNDED: <need>` instead of inventing a selector.

Cross-cutting elements (app title + tab buttons) are bucketed into a shared `DashboardPage`;
a column like `Ticker` that legitimately appears in two tables stays in each tab's page object.

The sandbox install workaround (writable npm cache + `PLAYWRIGHT_BROWSERS_PATH`) is baked into
`playwright_runner.py` and the project README.

## Notes

- Playwright matches `getByRole` `name` as a **substring** by default. The extractor
  emits `{ name: '...', exact: true }` when a name is a substring of another
  same-role element's name (e.g. `Scan` vs the `Scanner` tab) to avoid strict-mode
  ambiguity.
- The captured inventory (multi-modal element features) is designed to seed the
  later self-healing locator baseline store (dissertation §3.3) unchanged.
