import json
import tempfile
from pathlib import Path
from unittest import TestCase, main
from unittest.mock import patch

from ui import dashboard


ROOT = Path(__file__).resolve().parent
APP = (ROOT / "ui" / "app.js").read_text(encoding="utf-8")
INDEX = (ROOT / "ui" / "index.html").read_text(encoding="utf-8")


class DashboardLayoutPersistenceTests(TestCase):
    def test_changed_geometry_survives_fresh_reload_from_disk(self):
        changed = {
            "version": 1,
            "panels": {
                "panel-0": {"x": 127, "y": -34, "width": 412, "height": 533},
                "detail-dock": {"x": 8, "y": 16, "width": 900, "height": 300},
            },
        }
        with tempfile.TemporaryDirectory() as temporary:
            layout_file = str(Path(temporary) / "dashboard_layout.json")
            with patch.object(dashboard, "DASHBOARD_LAYOUT_FILE", layout_file):
                dashboard.save_dashboard_layout(changed)
                # Reading the file again simulates a new dashboard process/reload.
                restored = dashboard.get_dashboard_layout()
                self.assertEqual(restored, changed)
                self.assertEqual(json.loads(Path(layout_file).read_text()), changed)

    def test_reset_removes_durable_layout(self):
        with tempfile.TemporaryDirectory() as temporary:
            layout_file = str(Path(temporary) / "dashboard_layout.json")
            with patch.object(dashboard, "DASHBOARD_LAYOUT_FILE", layout_file):
                dashboard.save_dashboard_layout({"version": 1, "panels": {"panel-1": {"x": 5}}})
                dashboard.reset_dashboard_layout()
                self.assertEqual(dashboard.get_dashboard_layout(), {})
                self.assertFalse(Path(layout_file).exists())

    def test_browser_restores_cache_and_server_layout(self):
        self.assertIn("localStorage.getItem(PANEL_LAYOUT_KEY)", APP)
        self.assertIn("fetch('/api/layout'", APP)
        self.assertIn("panels.forEach(applyGeometry)", APP)
        self.assertIn("beforeunload", APP)
        self.assertIn("Reset Dashboard Layout", INDEX)


if __name__ == "__main__":
    main()
