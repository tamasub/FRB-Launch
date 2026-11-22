"""The *one* Ctrl+Menu popup: anti-aliased, uniformly rounded on Windows.

Do not apply the translucent-window recipe to other QMenus. Those menus have
separate keyboard, window-activation and pointer interactions.
"""

from PySide6.QtCore import Qt, QRectF
from PySide6.QtGui import QColor, QPainter, QPen
from PySide6.QtWidgets import QMenu

from launch_appearance import launch_action_menu_qss, theme_family


class LaunchActionMenu(QMenu):
    """Preserve native QAction navigation with a custom, transparent shell."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName('frbLaunchActionMenu')
        # QSS border-radius alone leaves native square corners (and an odd
        # gray bottom-right shadow) on Windows. Keep QMenu's Popup semantics.
        self.setWindowFlag(Qt.WindowType.FramelessWindowHint, True)
        no_shadow = getattr(Qt.WindowType, 'NoDropShadowWindowHint', None)
        if no_shadow is not None:
            self.setWindowFlag(no_shadow, True)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self._surface_bg = '#ffffff'
        self._surface_border = '#b6cebe'

    def set_launch_theme(self, theme):
        light = theme_family(theme) == 'light'
        self._surface_bg = '#ffffff' if light else '#202b39'
        self._surface_border = '#b6cebe' if light else '#435369'
        self.setStyleSheet(launch_action_menu_qss(theme))
        self.update()

    def paintEvent(self, event):
        # Paint the entire surface with antialiased corners. With a genuinely
        # translucent top-level window these same four corners are transparent
        # outside the path; no QRegion pixel mask (jagged edges) is required.
        if self.width() >= 4 and self.height() >= 4:
            painter = QPainter(self)
            painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
            painter.setBrush(QColor(self._surface_bg))
            painter.setPen(QPen(QColor(self._surface_border), 1.0))
            margin = 0.8
            painter.drawRoundedRect(
                QRectF(margin, margin,
                       self.width() - 2 * margin, self.height() - 2 * margin),
                10.0, 10.0)
            painter.end()
        # Leave selection, text, mouse hit-testing and keyboard navigation
        # entirely to Qt's existing QMenu / QAction rendering.
        super().paintEvent(event)
