"""ぐりぐりレールのカレント●の描画契約テスト (Qt不要)。"""
import ast
from pathlib import Path
import unittest

SOURCE = (Path(__file__).resolve().parents[1] / 'src' / 'launch_remote.py').read_text(encoding='utf-8')


class CurrentDotOverlayTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        tree = ast.parse(SOURCE)
        pad = next(n for n in tree.body if isinstance(n, ast.ClassDef)
                   and n.name == 'RoundRailWheelPad')
        paint = next(n for n in pad.body if isinstance(n, ast.FunctionDef)
                     and n.name == 'paintEvent')
        cls.paint = ast.get_source_segment(SOURCE, paint)

    def test_semitransparent_dot_larger_than_previous_3px(self):
        self.assertIn('marker.setAlpha(100)', self.paint)
        self.assertIn('painter.drawEllipse(QPointF(marker_x, 44.0), 7.0, 7.0)', self.paint)
        self.assertNotIn('QPointF(x, 54.0), 1.6, 1.6', self.paint)

    def test_marker_is_behind_labels_and_uses_the_existing_side(self):
        marker_pos = self.paint.index('painter.drawEllipse(QPointF(marker_x, 44.0)')
        exp_pos = self.paint.index("Qt.AlignmentFlag.AlignCenter, 'Exp'")
        list_pos = self.paint.index("Qt.AlignmentFlag.AlignCenter, 'List'")
        self.assertLess(marker_pos, exp_pos)
        self.assertLess(marker_pos, list_pos)
        self.assertIn("self._hover_side == 'files_exp'", self.paint)
        self.assertIn('marker_x = 18.0 if', self.paint)
        self.assertIn('else 42.0', self.paint)

    def test_exp_list_text_shifted_towards_center(self):
        self.assertIn('QRectF(8.0, 37.0, 20.0, 14.0)', self.paint)
        self.assertIn('QRectF(32.0, 37.0, 20.0, 14.0)', self.paint)
        self.assertIn('font.setPixelSize(10)', self.paint)

    def test_outer_circle_center_glyph_and_painter_cleanup_unchanged(self):
        self.assertIn('painter.drawEllipse(bounds)', self.paint)
        self.assertIn('painter.end()', self.paint)
        self.assertIn("self._center_glyph = QLabel('🔘', self)", SOURCE)
        self.assertIn('glyph_font.setPixelSize(16)', SOURCE)


if __name__ == '__main__':
    unittest.main()
