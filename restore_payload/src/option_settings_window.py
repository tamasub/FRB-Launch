"""FRB Studio Family Generic Editor host: navigation is Launch-owned.

The editor HTML/CSS/JS are ALL in the Studio family; no second Qt editor is
implemented here.  A private loopback Node process handles Composition/Save.
"""
from __future__ import annotations
import json
import sys
from pathlib import Path

from PySide6.QtCore import QProcess, Qt, QUrl
from PySide6.QtWebEngineCore import QWebEnginePage, QWebEngineProfile
from PySide6.QtWidgets import QDialog, QVBoxLayout, QLabel, QDialogButtonBox
from PySide6.QtWebEngineWidgets import QWebEngineView

from launch_option_runtime import find_node, find_studio_root


class OptionSettingsWindow(QDialog):
    def __init__(self, launch_home, state_dir, studio_root=None, parent=None, theme="light"):
        super().__init__(parent)
        self.setWindowTitle('FRB Launch — オプション設定')
        self.setWindowFlag(Qt.WindowType.WindowContextHelpButtonHint, False)
        self.setMinimumSize(510, 405)
        self.resize(660, 530)
        self._theme = 'dark' if str(theme).lower() == 'dark' else 'light' 
        self._stdout = ''
        self._root = find_studio_root(launch_home, studio_root)
        if self._root is None:
            raise RuntimeError('FRB Studio FamilyのOption Settingsが見つかりません。Studioを配置してください。')
        self._node = find_node(launch_home, self._root)
        if self._node is None:
            raise RuntimeError('Node.js実行環境がありません。runtime/node/node.exe またはPATHのNodeが必要です。')
        # A dedicated off-the-record browser profile prevents the short-lived
        # localhost token from being persisted in normal Launch browser history.
        self._profile=QWebEngineProfile(self)
        self.view=QWebEngineView(self)
        self._page=QWebEnginePage(self._profile, self.view)
        self.view.setPage(self._page)
        self.label=QLabel('Generic Editorを起動しています…')
        layout=QVBoxLayout(self)
        layout.setContentsMargins(2,2,2,2)
        layout.addWidget(self.view,1)
        self.label.setStyleSheet('font-size:10px;padding:0 3px;')
        self.label.setMaximumHeight(18)
        layout.addWidget(self.label)
        self._process=QProcess(self)
        self._process.setProgram(str(self._node))
        self._process.setArguments([
            str(self._root/'tools'/'option_settings'/'server.mjs'),
            '--studio-root', str(self._root),
            '--system-root', str(Path(launch_home)/'config'),
            '--user-root', str(Path(state_dir)/'UserConfig')
        ])
        self._process.readyReadStandardOutput.connect(self._on_output)
        self._process.readyReadStandardError.connect(self._on_error)
        self._process.errorOccurred.connect(lambda e: self.label.setText('起動エラー: '+self._process.errorString()))
        self._process.start()

    def _apply_native_titlebar_theme(self):
        """Match the Windows DWM caption to Launch's light/dark theme.

        The WebEngine CSS cannot style a native QDialog title bar.
        On older Windows builds, unsupported DWM attributes fail harmlessly.
        """
        if sys.platform != 'win32':
            return
        try:
            import ctypes
            hwnd = ctypes.c_void_p(int(self.winId()))
            set_attribute = ctypes.windll.dwmapi.DwmSetWindowAttribute
            dark = ctypes.c_int(1 if self._theme == 'dark' else 0)
            for attribute in (20, 19):  # DWMWA_USE_IMMERSIVE_DARK_MODE
                if set_attribute(hwnd, attribute, ctypes.byref(dark), ctypes.sizeof(dark)) == 0:
                    break
            # Windows 11: match the Launch dark green titlebar instead of black.
            # COLORREF is 0x00BBGGRR; 0xFFFFFFFF restores OS defaults in light mode.
            caption = ctypes.c_uint32(0x00272b20 if self._theme == 'dark' else 0xFFFFFFFF)
            foreground = ctypes.c_uint32(0x00ebf0e6 if self._theme == 'dark' else 0xFFFFFFFF)
            set_attribute(hwnd, 35, ctypes.byref(caption), ctypes.sizeof(caption))
            set_attribute(hwnd, 36, ctypes.byref(foreground), ctypes.sizeof(foreground))
        except (OSError, AttributeError, ValueError):
            # Native caption theming is cosmetic.  Never block option editing.
            pass

    def showEvent(self, event):
        super().showEvent(event)
        self._apply_native_titlebar_theme()

    def set_theme(self, theme):
        self._theme = 'dark' if str(theme).lower() == 'dark' else 'light'
        if self.isVisible():
            self._apply_native_titlebar_theme()
        if self.view.url().isValid():
            self.view.page().runJavaScript(
                "document.documentElement.dataset.theme = " + json.dumps(self._theme))

    def _on_output(self):
        self._stdout+=bytes(self._process.readAllStandardOutput()).decode('utf-8','replace')
        while '\n' in self._stdout:
            line,self._stdout=self._stdout.split('\n',1)
            try:
                ready=json.loads(line)
                port,token=int(ready['port']),ready['token']
            except (ValueError,KeyError,TypeError):
                continue
            if not 1 <= port <= 65535 or not isinstance(token,str):
                continue
            self.view.load(QUrl(f'http://127.0.0.1:{port}/?token={token}&theme={self._theme}'))
            self.label.setText('User設定は保存後に反映されます。Launchの再起動が必要な項目があります。')

    def _on_error(self):
        message=bytes(self._process.readAllStandardError()).decode('utf-8','replace').strip()
        if message:
            self.label.setText('Generic Editor: '+message[:400])

    def closeEvent(self,event):
        # Release the local server when its owning window closes.
        if self._process.state()!=QProcess.ProcessState.NotRunning:
            self._process.terminate()
            if not self._process.waitForFinished(1500):
                self._process.kill()
                self._process.waitForFinished(1000)
        super().closeEvent(event)
