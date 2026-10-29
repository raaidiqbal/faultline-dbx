from __future__ import annotations

from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]


class AppContractTests(unittest.TestCase):
    def test_app_uses_managed_resources_without_embedded_credentials(self) -> None:
        source = (ROOT / "app" / "app.py").read_text(encoding="utf-8")
        config = (ROOT / "app" / "app.yaml").read_text(encoding="utf-8")
        combined = f"{source}\n{config}".lower()

        self.assertIn("credentials_provider=lambda: cfg.authenticate", source)
        self.assertIn("valueFrom: sql-warehouse", config)
        self.assertNotIn("personal access token", combined)
        self.assertNotIn("databricks_token", combined)
        self.assertNotIn("client_secret", combined)

    def test_console_is_read_only(self) -> None:
        source = (ROOT / "app" / "app.py").read_text(encoding="utf-8").upper()
        for write_keyword in ("INSERT INTO", "DELETE FROM", "MERGE INTO", "TRUNCATE TABLE"):
            self.assertNotIn(write_keyword, source)


if __name__ == "__main__":
    unittest.main()

