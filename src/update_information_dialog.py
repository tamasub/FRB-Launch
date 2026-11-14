"""Compact FRB Update status UI. No update is initiated without a user click."""
import json
import os
import sys
from pathlib import Path
from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
                               QFrame)
from frb_update.contracts import UpdateError, read_sources, version_tuple
from frb_update.bootstrap import check_feeds, ensure_updater, prepare_request, start_updater

class UpdateWorker(QThread):
    succeeded = Signal(object)
    failed = Signal(str)
    def __init__(self,mode,context,parent=None):
        super().__init__(parent)
        self.mode=mode
        self.context=context
    def run(self):
        ctx=self.context
        try:
            if self.mode == 'check':
                result=check_feeds(ctx['sources']['updater_feed_url'],ctx['sources']['product_feed_url'],
                                   allow_local=ctx['allow_local'])
            elif self.mode == 'prepare':
                binary=ensure_updater(ctx['install_root'],ctx['updater_feed'],
                                       allow_local=ctx['allow_local'])
                request=prepare_request(ctx['product_feed'],ctx['work_dir'],
                                        allow_local=ctx['allow_local'])
                process=start_updater(binary,request=request,install_root=ctx['install_root'],
                                      host_pid=os.getpid(),allow_local=ctx['allow_local'])
                result={'pid':process.pid}
            else:raise UpdateError('不明な処理です')
            self.succeeded.emit(result)
        except Exception as exc:
            self.failed.emit(str(exc))

class UpdateInformationDialog(QDialog):
    def __init__(self,launch_home:Path,install_root:Path,launch_version:str,theme:str,parent=None):
        super().__init__(parent)
        self.setWindowTitle('FRB Launch — バージョンアップ情報')
        self.setWindowFlag(Qt.WindowType.WindowContextHelpButtonHint, False)
        self.setModal(False)
        self.setMinimumWidth(380)
        self.resize(435,290)
        self.install_root=Path(install_root).resolve()
        self.launch_home=Path(launch_home).resolve()
        self.sources_path=self.launch_home/'defs'/'update'/'update_sources.json'
        self.worker=None
        self.updater_feed=None
        self.product_feed=None
        self.config=None
        self.busy=False
        self.current=None
        state_file=self.install_root/'installed_release.json'
        if state_file.is_file():
            try:
                self.current=json.loads(state_file.read_text('utf-8-sig'))
            except (OSError,ValueError):pass
        lay=QVBoxLayout(self);lay.setSpacing(8);lay.setContentsMargins(13,12,13,12)
        heading=QLabel('FRB Launch  バージョンアップ情報')
        heading.setObjectName('updateHeading')
        lay.addWidget(heading)
        self.installed=QLabel('統合版: '+(self.current['version'] if self.current else '未登録（開発版）'))
        self.launch_component=QLabel('Launch: '+launch_version)
        self.studio_component=QLabel('Studio: '+str((self.current or {}).get('components',{}).get('studio','未登録')))
        for widget in (self.installed,self.launch_component,self.studio_component):lay.addWidget(widget)
        line=QFrame();line.setFrameShape(QFrame.Shape.HLine);lay.addWidget(line)
        self.latest=QLabel('最新版: 未確認')
        lay.addWidget(self.latest)
        self.latest_components=QLabel('最新版コンポーネント: 未確認')
        lay.addWidget(self.latest_components)
        self.notes=QLabel('更新はユーザーの指示でのみ開始します。')
        self.notes.setWordWrap(True);lay.addWidget(self.notes)
        self.message=QLabel('「最新版を確認」で配布情報を取得します。')
        self.message.setWordWrap(True);self.message.setObjectName('updateStatus')
        lay.addWidget(self.message)
        last=Path(os.environ.get('LOCALAPPDATA',str(Path.home()))) / 'FRBLaunch' / 'UpdateLogs' / 'last_update_status.json'
        if last.is_file():
            try:
                status=json.loads(last.read_text('utf-8-sig'))
                self.message.setText(('前回: 成功 — ' if status.get('success') else '前回: 失敗 — ')
                                     +str(status.get('message','')))
            except (OSError,ValueError):pass
        lay.addStretch(1)
        buttons=QHBoxLayout();buttons.setSpacing(6)
        self.check=QPushButton('最新版を確認');self.apply=QPushButton('更新を開始');self.close_btn=QPushButton('閉じる')
        self.apply.setEnabled(False)
        buttons.addWidget(self.check);buttons.addWidget(self.apply);buttons.addStretch(1);buttons.addWidget(self.close_btn)
        lay.addLayout(buttons)
        self.check.clicked.connect(self.check_latest)
        self.apply.clicked.connect(self.start_update)
        self.close_btn.clicked.connect(self.close)
        self._dark=str(theme).lower() not in ('light','system_light')
        dark=self._dark
        fg='#e6e7e7' if dark else '#25292b'
        bg='#172126' if dark else '#f8fafb'
        border='#52666a' if dark else '#cbd2d7'
        field='#26373c' if dark else '#eef1f3'
        self.setStyleSheet(f'''QDialog {{background:{bg};color:{fg};font-size:12px;}}
            QLabel {{color:{fg};}}
            QLabel#updateHeading {{font-weight:600;font-size:15px;}}
            QLabel#updateStatus {{color:{'#c0d0d1' if dark else '#48545b'};}}
            QPushButton {{color:{fg};background:{field};border:1px solid {border};
               border-radius:4px;min-height:24px;padding:2px 9px;}}
            QPushButton:disabled {{color:#888888;}}
            QPushButton:hover {{border-color:#83aba9;}}
            QFrame {{color:{border};}}''')

    def showEvent(self,event):
        super().showEvent(event)
        if sys.platform != 'win32':return
        try:
            import ctypes
            hwnd=ctypes.c_void_p(int(self.winId()))
            setter=ctypes.windll.dwmapi.DwmSetWindowAttribute
            dark=ctypes.c_int(int(self._dark))
            for name in (20,19):
                if setter(hwnd,name,ctypes.byref(dark),ctypes.sizeof(dark))==0:break
            caption=ctypes.c_uint32(0x00272b20 if self._dark else 0xFFFFFFFF)
            fore=ctypes.c_uint32(0x00ebf0e6 if self._dark else 0xFFFFFFFF)
            setter(hwnd,35,ctypes.byref(caption),ctypes.sizeof(caption))
            setter(hwnd,36,ctypes.byref(fore),ctypes.sizeof(fore))
        except (OSError,AttributeError,ValueError):pass

    def _context(self):
        sources=read_sources(self.sources_path)
        allow_local=bool(sources.get('allow_local_for_test',False))
        return {'sources':sources,'allow_local':allow_local,'install_root':self.install_root}

    def _run(self,mode,context):
        self.busy=True
        self.check.setEnabled(False);self.apply.setEnabled(False)
        self.close_btn.setEnabled(False)
        self.worker=UpdateWorker(mode,context,self)
        self.worker.succeeded.connect(self._checked if mode=='check' else self._prepared)
        self.worker.failed.connect(self._failed)
        self.worker.finished.connect(self._finished)
        self.worker.start()

    def check_latest(self):
        try:
            context=self._context()
            self._run('check',context)
            self.message.setText('更新情報を確認中...')
        except Exception as exc:
            self.message.setText(str(exc))

    def _checked(self,result):
        self.updater_feed,self.product_feed=result
        product=self.product_feed
        self.latest.setText('最新版: '+product['version']+'   /   Updater: '+self.updater_feed['version'])
        latest_components=product.get('components',{})
        self.latest_components.setText('Launch: '+str(latest_components.get('launch','?'))+
                                       ' / Studio: '+str(latest_components.get('studio','?')))
        self.notes.setText(str(product.get('notes') or '更新内容の説明はありません。'))
        try:
            newer=not self.current or version_tuple(product['version'])>version_tuple(self.current['version'])
        except (KeyError,ValueError,UpdateError):newer=False
        self.message.setText('更新可能です。' if newer else '最新版を使用しています。')
        self.apply.setEnabled(bool(newer and self._can_apply()))
        if newer and not self._can_apply():
            self.message.setText('開発用起動では更新できません。製品配布フォルダーで起動してください。')

    def _can_apply(self):
        # Updater must never overwrite a linked developer source tree.
        return (self.install_root/'FRBLaunch.exe').is_file() and not (self.install_root/'launch_home.json').exists()

    def start_update(self):
        if not self.product_feed or not self.updater_feed or not self._can_apply():return
        context=self._context()
        context.update({'updater_feed':self.updater_feed,'product_feed':self.product_feed,
                        'work_dir':Path(os.environ.get('LOCALAPPDATA',str(Path.home()))) / 'FRBLaunch' / 'UpdateWork'})
        self._run('prepare',context)
        self.message.setText('Updaterの検証・準備中...')

    def _prepared(self,result):
        self.message.setText('Updaterを起動しました。Launchを終了します。')
        from PySide6.QtWidgets import QApplication
        launcher=self.parent()
        self.accept()
        if callable(getattr(launcher,'quit',None)):
            launcher.quit()
        else:
            QApplication.instance().quit()

    def _failed(self,message):
        self.message.setText('更新処理を開始できません: '+message)

    def _finished(self):
        self.busy=False
        self.check.setEnabled(True)
        self.close_btn.setEnabled(True)
        if self.product_feed and self.updater_feed:
            newer=not self.current or version_tuple(self.product_feed['version'])>version_tuple(self.current['version'])
            self.apply.setEnabled(bool(newer and self._can_apply()))

    def closeEvent(self,event):
        if self.busy:event.ignore()
        else:super().closeEvent(event)
