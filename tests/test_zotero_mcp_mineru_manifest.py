from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

SOURCE = Path(__file__).resolve().parents[1] / "files/system/usr/share/turquoise/zotero-mcp-mineru.py"
spec = importlib.util.spec_from_file_location("managed_mineru_under_test", SOURCE)
mineru = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(mineru)


class MineruManifestTests(unittest.TestCase):
    def test_atomic_manifest_is_valid_json_with_real_newline(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "manifest.json"
            mineru._write_json_atomic(path, {"item_key": "TESTITEM", "pdf_sha256": "abcd"})
            self.assertEqual(json.loads(path.read_text())["item_key"], "TESTITEM")
            self.assertTrue(path.read_bytes().endswith(b"\n"))
            self.assertFalse(path.read_bytes().endswith(b"\\n"))


if __name__ == "__main__":
    unittest.main()
