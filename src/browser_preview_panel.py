"""Opt-in third Files column for previewing a Browser bookmark URL.

This is NOT the Browser workspace: a preview keeps the current Files Exp,
Files List, selection and breadcrumb intact.  Qt WebEngine is imported only
when a user explicitly double-clicks a bookmarked URL.
"""
from PySide6.QtCore import Qt, QUrl, Signal
from PySide6.QtWidgets import QFrame, QVBoxLayout, QHBoxLayout, QLabel, QToolButton, QSizePolicy
from PySide6.QtWebEngineCore import QWebEnginePage
from PySide6.QtWebEngineWidgets import QWebEngineView

from browser_nav_icons import browser_navigation_icon
from launch_appearance import theme_family, theme_palette
from webview_settings import valid_http_url


class BrowserPreviewPanel(QFrame):
    close_requested = Signal()

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
        header.setObjectName('filesBrowserPreviewHeader')
        bar = QHBoxLayout(header)
        bar.setContentsMargins(10, 4, 6, 4)
        bar.setSpacing(6)
        self.title_label = QLabel('Browser Preview', header)
        self.title_label.setObjectName('filesBrowserPreviewTitle')
        bar.addWidget(self.title_label, 1)
        self.close_button = QToolButton(header)
        self.close_button.setObjectName('filesBrowserPreviewClose')
        self.close_button.setFixedSize(29, 29)
        self.close_button.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.close_button.setToolTip('Browser Previewを閉じる（Files Listはそのまま）')
        self.close_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.close_button.clicked.connect(self.close_requested.emit)
        bar.addWidget(self.close_button)
        layout.addWidget(header)
        self.view = QWebEngineView(self)
        self.view.setObjectName('filesBrowserPreviewWeb')
        # Where available, share the existing Launch Browser WebEngine profile
        # (not the system Chrome/Edge profile). Otherwise Qt's default profile
        # gives an isolated preview without creating a Browser tab.
        if profile is not None:
            self.view.setPage(QWebEnginePage(profile, self.view))
        self.view.setZoomFactor(float((settings or {}).get('default_zoom_percent', 90)) / 100)
        self.view.loadFinished.connect(self._loaded)
        self.view.titleChanged.connect(self._set_page_title)
        layout.addWidget(self.view, 1)
        self.apply_theme('light')

    def navigate(self, url):
        if not valid_http_url(url):
            return False
        self._url = url
        self.title_label.setText('Browser Preview')
        self.title_label.setToolTip(url)
        self.view.setUrl(QUrl(url))
        return True

    def stop_preview(self):
        """Closing must not destroy or navigate the normal Browser tabs."""
        self.view.stop()
        self.view.setUrl(QUrl('about:blank'))
        self._url = ''
        self.title_label.setText('Browser Preview')
        self.title_label.setToolTip('')

    def _loaded(self, success):
        if self._url and not success:
            self.title_label.setText('Browser Preview — 読み込み失敗')
            self.title_label.setToolTip(self._url)

    def _set_page_title(self, title):
        if self._url and title:
            self.title_label.setToolTip(f'{title}\n{self._url}')

    def apply_theme(self, theme):
        self._theme = theme
        colors = theme_palette(theme)
        family = theme_family(theme)
        self.close_button.setIcon(browser_navigation_icon('close', family))
        panel = colors['panel']
        header = colors['panel_header']
        border = colors['panel_border']
        text = colors['text']
        hover = colors['hover']
        self.setStyleSheet(f'''
            QFrame#filesBrowserPreviewPanel {{background:{panel};border:0;}}
            QFrame#filesBrowserPreviewHeader {{background:{header};border-bottom:1px solid {border};}}
            QLabel#filesBrowserPreviewTitle {{color:{text};font-size:13px;font-weight:600;border:0;background:transparent;}}
            QToolButton#filesBrowserPreviewClose {{background:transparent;border:0;border-radius:5px;}}
            QToolButton#filesBrowserPreviewClose:hover {{background:{hover};}}
        ''')
