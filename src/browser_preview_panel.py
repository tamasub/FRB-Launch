"""The full FRB Launch Browser, hosted in the optional Files third column.

This is the *same LaunchWebView* that previously lived on the Browser tab:
Web tabs, address bar, history, downloads and URL favorites are retained.
Closing the column hides it; it never destroys the existing web tabs.
"""
from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (QFrame, QVBoxLayout, QHBoxLayout, QLabel,
                               QToolButton, QSizePolicy)

from browser_nav_icons import browser_navigation_icon
from launch_appearance import theme_family, theme_palette
from webview_settings import valid_http_url


class BrowserPreviewPanel(QFrame):
    close_requested = Signal()
    maximize_requested = Signal()

    def __init__(self, parent=None, *, settings=None, profile=None):
        super().__init__(parent)
        self.setObjectName('filesBrowserPreviewPanel')
        self.setMinimumWidth(270)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self._theme = 'light'
        self._url = ''
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        header = QFrame(self)
        self.header = header
        header.setObjectName('filesBrowserPreviewHeader')
        bar = QHBoxLayout(header)
        bar.setContentsMargins(10, 4, 6, 4)
        bar.setSpacing(6)
        self.title_label = QLabel('Browser', header)
        self.title_label.setObjectName('filesBrowserPreviewTitle')
        bar.addWidget(self.title_label, 1)
        self.maximize_button = QToolButton(header)
        self.maximize_button.setObjectName('filesBrowserPreviewMaximize')
        self.maximize_button.setFixedSize(29, 29)
        self.maximize_button.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.maximize_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.maximize_button.clicked.connect(self.maximize_requested.emit)
        bar.addWidget(self.maximize_button)
        # Match Studio / Obsidian: maximize, outside, close (rightmost).
        self.popout_button = QToolButton(header)
        self.popout_button.setObjectName('filesBrowserPreviewPopout')
        self.popout_button.setFixedSize(29, 29)
        self.popout_button.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.popout_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.popout_button.setToolTip('現在のページを既定ブラウザで外に開く（Webタブは保持）')
        self.popout_button.clicked.connect(self.open_external)
        bar.addWidget(self.popout_button)
        self.close_button = QToolButton(header)
        self.close_button.setObjectName('filesBrowserPreviewClose')
        self.close_button.setFixedSize(29, 29)
        self.close_button.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.close_button.setToolTip('第3列を非表示（Webタブは保持）')
        self.close_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.close_button.clicked.connect(self.close_requested.emit)
        bar.addWidget(self.close_button)
        layout.addWidget(header)

        # LAZY import: WebEngine is not loaded until a Browser panel is needed.
        from launch_web_view import LaunchWebView
        self.web_view = LaunchWebView(self, settings=settings)
        self.web_view.setObjectName('filesThirdColumnFullBrowser')
        # The external-open action now lives beside the third-column close X.
        # Keep LaunchWebView.open_external() and its behavior, hide only the
        # duplicate icon in the inner browser toolbar.
        self.web_view.external.hide()
        # The authored horizontal bookmark strip is intentionally hidden.
        # Bookmarks remain accessible in Files Exp/List and Exp Keyborder.
        self.web_view.bookmark_strip.hide()
        layout.addWidget(self.web_view, 1)
        self.set_maximized(False)
        self.apply_theme('light')

    def navigate(self, url, *, new_tab=None):
        if not valid_http_url(url):
            return False
        self._url = url
        self.web_view.open_launch_url(url, new_tab=new_tab)
        return True

    def open_external(self):
        """Open this URL outside Launch without destroying the web session."""
        return self.web_view.open_external()

    def stop_preview(self):
        """Hide without losing the browser's tabs, history or current URL."""
        # Do not stop active network activity / a pending form submission.
        # The web view and every tab stay alive while the third column hides.
        return None

    def set_maximized(self, maximized):
        self._third_column_maximized = bool(maximized)
        self.maximize_button.setIcon(browser_navigation_icon(
            'restore' if maximized else 'maximize', theme_family(self._theme)))
        self.maximize_button.setIconSize(self.close_button.iconSize())
        self.maximize_button.setToolTip(
            '第3列を元の幅に戻す' if maximized else 'Launch内で第3列を最大化')

    def apply_theme(self, theme):
        self._theme = theme
        colors = theme_palette(theme)
        family = theme_family(theme)
        self.close_button.setIcon(browser_navigation_icon('close', family))
        self.popout_button.setIcon(browser_navigation_icon('external', family))
        self.set_maximized(getattr(self, '_third_column_maximized', False))
        self.web_view.apply_theme(theme)
        panel, header, border, text, hover = (
            colors['panel'], colors['panel_header'], colors['panel_border'],
            colors['text'], colors['hover'])
        self.setStyleSheet(f"""
            QFrame#filesBrowserPreviewPanel {{background:{panel};border:0;}}
            QFrame#filesBrowserPreviewHeader {{background:{header};border-bottom:1px solid {border};}}
            QLabel#filesBrowserPreviewTitle {{color:{text};font-size:13px;font-weight:600;border:0;background:transparent;}}
            QToolButton#filesBrowserPreviewClose, QToolButton#filesBrowserPreviewMaximize,
            QToolButton#filesBrowserPreviewPopout
                {{background:transparent;color:{text};border:0;border-radius:5px;font-size:21px;}}
            QToolButton#filesBrowserPreviewClose:hover, QToolButton#filesBrowserPreviewMaximize:hover,
            QToolButton#filesBrowserPreviewPopout:hover
                {{background:{hover};}}
        """)
