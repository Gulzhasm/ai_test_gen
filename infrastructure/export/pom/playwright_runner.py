"""
Run Playwright tests inside the generated POM project via subprocess.

Bakes in the sandbox-friendly workarounds (writable npm cache + project-local
PLAYWRIGHT_BROWSERS_PATH) and gates the install behind a node_modules check so it
isn't re-run every time.
"""
import json
import os
import subprocess
from typing import Dict, Optional, List


class PlaywrightRunner:
    def __init__(self, project_path: str):
        self.root = project_path
        self.browsers_path = os.path.join(self.root, ".pwbrowsers")
        self.npm_cache = os.path.join(self.root, ".npmcache")

    def _env(self) -> Dict[str, str]:
        env = dict(os.environ)
        # Respect an externally-provided browsers path (lets the caller reuse an
        # already-downloaded Chromium); otherwise keep browsers project-local.
        env.setdefault("PLAYWRIGHT_BROWSERS_PATH", self.browsers_path)
        return env

    def ensure_installed(self) -> None:
        """Install node deps (if node_modules missing) + chromium (unless reusing an external path)."""
        env = self._env()
        if not os.path.isdir(os.path.join(self.root, "node_modules")):
            print("  Installing POM project dependencies (npm install)...")
            subprocess.run(
                ["npm", "install", "--cache", self.npm_cache, "--no-audit", "--no-fund", "--loglevel=error"],
                cwd=self.root, env=env, check=True, capture_output=True, text=True,
            )
        # Skip the ~150MB chromium download when reusing an external browsers path.
        reused = os.environ.get("PLAYWRIGHT_BROWSERS_PATH")
        if reused and os.path.isdir(reused):
            return
        if os.path.isdir(self.browsers_path) and os.listdir(self.browsers_path):
            return
        print("  Installing Chromium for Playwright...")
        subprocess.run(
            ["npx", "playwright", "install", "chromium"],
            cwd=self.root, env=env, check=True, capture_output=True, text=True,
        )

    def run(self, base_url: Optional[str] = None, install: bool = True,
            test_files: Optional[List[str]] = None) -> Dict:
        """
        Run `npx playwright test --reporter=json`.

        Returns {returncode, passed, failed, flaky, skipped, total, ok}.
        """
        if install:
            self.ensure_installed()

        env = self._env()
        if base_url:
            env["BASE_URL"] = base_url

        cmd = ["npx", "playwright", "test", "--reporter=json"]
        if test_files:
            cmd += test_files

        proc = subprocess.run(cmd, cwd=self.root, env=env, capture_output=True, text=True)

        summary = {
            "returncode": proc.returncode,
            "passed": 0, "failed": 0, "flaky": 0, "skipped": 0, "total": 0,
            "ok": proc.returncode == 0,
        }
        try:
            data = json.loads(proc.stdout)
            stats = data.get("stats", {})
            summary["passed"] = stats.get("expected", 0)
            summary["failed"] = stats.get("unexpected", 0)
            summary["flaky"] = stats.get("flaky", 0)
            summary["skipped"] = stats.get("skipped", 0)
            summary["total"] = sum(stats.get(k, 0) for k in ("expected", "unexpected", "flaky", "skipped"))
        except (json.JSONDecodeError, ValueError):
            # Fall back to returncode; surface stderr tail for debugging.
            summary["stderr_tail"] = (proc.stderr or "")[-800:]
            summary["stdout_tail"] = (proc.stdout or "")[-800:]
        return summary
