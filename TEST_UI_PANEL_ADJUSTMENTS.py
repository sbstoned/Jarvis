from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parent
APP = (ROOT / "ui" / "app.js").read_text(encoding="utf-8")
STYLES = (ROOT / "ui" / "styles.css").read_text(encoding="utf-8")


class AdjustablePanelUiTests(unittest.TestCase):
    def test_all_panel_shells_are_initialized(self):
        self.assertIn("querySelectorAll('.panel, .widget-shell')", APP)
        self.assertIn("initializeAdjustablePanels();", APP)

    def test_move_resize_and_reset_interactions_exist(self):
        self.assertIn("addEventListener('pointerdown'", APP)
        self.assertIn("addEventListener('pointermove'", APP)
        self.assertIn("style.setProperty('width'", APP)
        self.assertIn("style.setProperty('height'", APP)
        self.assertIn("addEventListener('dblclick'", APP)

    def test_layout_is_persisted_without_visible_controls(self):
        function_body = APP.split("function initializeAdjustablePanels(){", 1)[1].split(
            "function tickClock()", 1
        )[0]
        self.assertIn("localStorage.setItem(PANEL_LAYOUT_KEY", function_body)
        self.assertNotIn("createElement", function_body)
        self.assertIn('.panel[data-adjustable="true"]', STYLES)
        self.assertIn('.widget-shell[data-adjustable="true"]', STYLES)


if __name__ == "__main__":
    unittest.main()
