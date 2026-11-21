"""Compare how Windows/Qt exposes Explorer versus FRB Launch file drags.

Standalone diagnostic: does not change FRB Launch or read dropped file data.
"""
from __future__ import annotations

import os
import sys
import tempfile
from datetime import datetime
from pathlib import Path
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QApplication, QFrame, QLabel, QMainWindow,
                               QPushButton, QVBoxLayout, QWidget)

LOG = Path(os.environ.get('TEMP') or tempfile.gettempdir()) / 'FRBLaunch' / 'file_drop_formats.log'
LOG.parent.mkdir(parents=True, exist_ok=True)


def record(label, stage, event):
    mime = event.mimeData()
    formats = list(mime.formats())
    try:
        urls = list(mime.urls())
        file_count = sum(1 for url in urls if url.isLocalFile())
        remote_count = len(urls) - file_count
    except Exception:
        file_count, remote_count = -1, -1
    lines = [
        f'{datetime.now().astimezone().isoformat(timespec="seconds")} [{label}] {stage}',
        f'  formats={formats}',
        f'  hasUrls={mime.hasUrls()} hasText={mime.hasText()} '
        f'hasFormat(text/uri-list)={mime.hasFormat("text/uri-list")} '
        f'hasFormat(text/plain)={mime.hasFormat("text/plain")}',
        f'  local_file_count={file_count} other_url_count={remote_count}',
        f'  possibleActions={event.possibleActions()} proposedAction={event.proposedAction()}',
    ]
    with LOG.open('a', encoding='utf-8') as handle:
        handle.write('\n'.join(lines) + '\n')
    return '\n'.join(lines)


class DropZone(QFrame):
    def __init__(self, label, parent=None):
        super().__init__(parent)
        self.label = label
        self.setAcceptDrops(True)
        self.setMinimumHeight(115)
        self.setStyleSheet('QFrame { background: #f2f7fc; border: 2px dashed #6096b9; border-radius: 12px; }'
                           ' QLabel { color: #234e70; background: transparent; border: none; font-size: 15px; }')
        layout = QVBoxLayout(self)
        text = QLabel(f'{label}\nここにファイルをドロップ')
        text.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(text)
        self.status = text

    def dragEnterEvent(self, event):
        record(self.label, 'DragEnter', event)
        # Test drop target accepts file drag; no file is read or opened.
        event.acceptProposedAction()

    def dragMoveEvent(self, event):
        event.acceptProposedAction()

    def dropEvent(self, event):
        record(self.label, 'Drop', event)
        event.acceptProposedAction()
        self.status.setText(f'{self.label}\n記録したで！ 次へ進もう')


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle('FRB Launch - ファイルD&D形式 比較診断')
        self.resize(620, 480)
        central = QWidget()
        layout = QVBoxLayout(central)
        title = QLabel('Explorer と FRB Launch のドラッグ形式を比較')
        title.setStyleSheet('font-size: 17px; font-weight: bold; padding: 6px;')
        layout.addWidget(title)
        info = QLabel('同じファイルを、①Explorer → ②Launch の順にドラッグしてね。\n'
                      'ファイル名・パス・中身は記録しません。Launchの「本文D&D」はOFFで。')
        info.setWordWrap(True)
        info.setStyleSheet('padding: 4px; color: #555;')
        layout.addWidget(info)
        layout.addWidget(DropZone('① Explorer'))
        layout.addWidget(DropZone('② FRB Launch'))
        button = QPushButton('ログをメモ帳で開く')
        button.clicked.connect(self.open_log)
        layout.addWidget(button)
        note = QLabel(f'ログ: {LOG}')
        note.setWordWrap(True)
        layout.addWidget(note)
        self.setCentralWidget(central)

    def open_log(self):
        if LOG.is_file():
            import subprocess
            subprocess.Popen(['notepad.exe', str(LOG)])


def main():
    LOG.write_text('FRB Launch file drag diagnostic; formats only, filenames redacted\n',
                   encoding='utf-8')
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == '__main__':
    main()
