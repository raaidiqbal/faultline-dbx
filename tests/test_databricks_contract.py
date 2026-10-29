from __future__ import annotations

import ast
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
PIPELINE = ROOT / "databricks" / "pipelines" / "faultline_pipeline.py"


class DatabricksPipelineContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.source = PIPELINE.read_text(encoding="utf-8")
        cls.tree = ast.parse(cls.source)

    def test_uses_current_lakeflow_api(self) -> None:
        self.assertIn("from pyspark import pipelines as dp", self.source)
        self.assertIn("dp.create_auto_cdc_flow", self.source)
        self.assertNotIn("import dlt", self.source)
        self.assertNotIn("apply_changes", self.source)

    def test_builds_current_and_history_projections(self) -> None:
        calls = [
            node
            for node in ast.walk(self.tree)
            if isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr == "create_auto_cdc_flow"
        ]
        self.assertEqual(2, len(calls))

        targets = {
            keyword.value.value
            for call in calls
            for keyword in call.keywords
            if keyword.arg == "target" and isinstance(keyword.value, ast.Constant)
        }
        self.assertEqual({"orders_current", "orders_history"}, targets)

    def test_orders_by_lakebase_monotonic_sequence_and_handles_deletes(self) -> None:
        self.assertIn('F.struct("_sort_by", "_pg_xid")', self.source)
        self.assertIn("_pg_change_type = 'delete'", self.source)
        self.assertIn('"update_postimage"', self.source)
        self.assertIn('"update_preimage"', self.source)

    def test_bundle_does_not_embed_credentials_or_workspace_host(self) -> None:
        bundle = (ROOT / "databricks.yml").read_text(encoding="utf-8")
        self.assertNotIn("token:", bundle.lower())
        self.assertNotIn("client_secret", bundle.lower())
        self.assertNotIn("https://", bundle.lower())


if __name__ == "__main__":
    unittest.main()

