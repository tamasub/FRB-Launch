"""Compact FRB Update status UI. No update is initiated without a user click."""
import json
import os
import sys
import time
from uuid import uuid4
from pathlib import Path
from PySide6.QtCore import Qt, QThread, Signal, QTimer
from PySide6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
                               QFrame)
from frb_update.contracts import UpdateError, read_sources, version_tuple
from frb_update.bootstrap import check_feeds, ensure_updater, prepare_request, start_updater
from frb_update.updater_core import pending_recovery
from frb_update.progress_gate import activate

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
                ready_file=Path(ctx['work_dir']) / ('updater_ui_' + uuid4().hex + '.json')
                process=start_updater(binary,request=request,install_root=ctx['install_root'],
                                      host_pid=os.getpid(),allow_local=ctx['allow_local'],
                                      ready_file=ready_file)
                result={'pid':process.pid,'process':process,'ready_file':str(ready_file)}
            else:raise UpdateError('不明な処理です')
            self.succeeded.emit(result)
        except Exception as exc:
            self.failed.emit(str(exc))

class UpdateInformationDialog(QDialog):
    checked_newer = Signal(bool)
    def __init__(self,launch_home:Path,install_root:Path,launch_version:str,theme:str,parent=None):
        super().__init__(parent)
        self.setWindowTitle('FRB Launch — バージョン情報')
        self.setWindowFlag(Qt.WindowType.WindowContextHelpButtonHint, False)
        self.setModal(False)
        self.setMinimumWidth(380)
        self.resize(435,290)
        self.install_root=Path(install_root).resolve()
        self.launch_home=Path(launch_home).resolve()
        self.sources_path=self.launch_home/'defs'/'update'/'update_sources.json'
        self.user_sources_path=self.install_root/'UserConfig'/'update_sources.json'
        self.worker=None
        self.updater_feed=None
        self.product_feed=None
        self.config=None
        self.busy=False
        self._active_mode=None
        self._auto_checked=False
        self._waiting_for_ui=False
        self._updater_process=None
        self._updater_ready_file=None
        self._ready_started=0.0
        self._ready_timer=QTimer(self)
        self._ready_timer.setInterval(150)
        self._ready_timer.timeout.connect(self._check_updater_ui_ready)
        self.current=None
        state_file=self.install_root/'installed_release.json'
        if state_file.is_file():
            try:
                self.current=json.loads(state_file.read_text('utf-8-sig'))
            except (OSError,ValueError):pass
        lay=QVBoxLayout(self);lay.setSpacing(8);lay.setContentsMargins(13,12,13,12)
        heading=QLabel('FRB Launch  バージョン情報')
        heading.setObjectName('updateHeading')
        lay.addWidget(heading)
        self.installed=QLabel('統合版: '+(self.current['version'] if self.current else '未登録（開発版）'))
        self.launch_component=QLabel('Launch: '+launch_version)
        self.studio_component=QLabel('Studio: '+str((self.current or {}).get('components',{}).get('studio','未登録')))
        for widget in (self.installed,self.launch_component,self.studio_component):
            widget.setObjectName('updateVersionValue')
            lay.addWidget(widget)
        line=QFrame();line.setFrameShape(QFrame.Shape.HLine);lay.addWidget(line)
        self.latest=QLabel('最新版: 未確認')
        self.latest.setObjectName('updateVersionValue')
        lay.addWidget(self.latest)
        self.latest_components=QLabel('最新版コンポーネント: 未確認')
        self.latest_components.setObjectName('updateVersionValue')
        lay.addWidget(self.latest_components)
        self.notes=QLabel('更新はユーザーの指示でのみ開始します。')
        self.notes.setObjectName('updateVersionNotes')
        self.notes.setWordWrap(True);lay.addWidget(self.notes)
        self.message=QLabel('更新情報を確認しています...')
        self.message.setWordWrap(True);self.message.setObjectName('updateStatus')
        lay.addWidget(self.message)
        self.last_result=QLabel('前回の更新結果: まだありません。')
        self.last_result.setObjectName('lastUpdateResult')
        self.last_result.setWordWrap(True)
        lay.addWidget(self.last_result)
        last=Path(os.environ.get('LOCALAPPDATA',str(Path.home()))) / 'FRBLaunch' / 'UpdateLogs' / 'last_update_status.json' 
        if last.is_file():
            try:
                status=json.loads(last.read_text('utf-8-sig'))
                recorded_root=status.get('install_root')
                if not recorded_root or Path(recorded_root).resolve()==self.install_root:
                    self.last_result.setText(('前回: 成功 — ' if status.get('success') else '前回: 失敗 — ')
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
        fg='#e6e7e7' if dark else '#22362d'
        bg='#172126' if dark else '#f8fafb'
        border='#52666a' if dark else '#cbd2d7'
        field='#26373c' if dark else '#edf4ee'
        self.setStyleSheet(f'''QDialog {{background:{bg};color:{fg};font-family:"Yu Gothic UI";font-size:13px;}}
            QLabel {{color:{fg};}}
            QLabel#updateHeading {{color:{'#edf4f0' if dark else '#203c2d'};font-weight:600;font-size:15px;}}
            QLabel#updateVersionValue {{color:{'#edf3ed' if dark else '#234231'};background:{'#273c36' if dark else '#e3f0e7'};font-weight:500;padding:2px 4px;}}
            QLabel#updateVersionNotes {{color:{'#e2ebe5' if dark else '#345443'};}}
            QLabel#updateStatus {{color:{'#c0d0d1' if dark else '#243d30'};font-weight:600;}}
            QLabel#lastUpdateResult {{color:{'#dfb199' if dark else '#8d4e26'};}}
            QPushButton {{color:{fg};background:{field};border:1px solid {border};
               border-radius:4px;min-height:24px;padding:2px 9px;}}
            QPushButton:disabled {{color:{'#798c86' if dark else '#6c8178'};}}
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
        # Opening the information window is itself a request to read the latest
        # release metadata. It never authorizes installing an update.
        if not self._auto_checked:
            self._auto_checked=True
            QTimer.singleShot(0, self.check_latest)

    def _context(self):
        sources=read_sources(self.sources_path, user_path=self.user_sources_path)
        allow_local=bool(sources.get('allow_local_for_test',False))
        return {'sources':sources,'allow_local':allow_local,'install_root':self.install_root}

    def _run(self,mode,context):
        if self.busy or self._waiting_for_ui:
            return
        self._active_mode=mode
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
        self.checked_newer.emit(bool(newer))
        recovery_required = pending_recovery(self.install_root)
        self.apply.setEnabled(bool(newer and self._can_apply() and not recovery_required))
        if recovery_required:
            self.message.setText('復旧未完了の更新があります。新しい更新を開始せず、Launchを終了して復旧してください。')
        elif newer and not self._can_apply():
            self.message.setText('開発用起動では更新できません。製品配布フォルダーで起動してください。')

    def _can_apply(self):
        # Updater must never overwrite a linked developer source tree.
        return (self.install_root/'FRBLaunch.exe').is_file() and not (self.install_root/'launch_home.json').exists()

    def start_update(self):
        if not self.product_feed or not self.updater_feed or not self._can_apply():return
        if pending_recovery(self.install_root):
            self.message.setText('復旧未完了の更新があります。先に復旧が必要です。')
            self.apply.setEnabled(False)
            return
        context=self._context()
        context.update({'updater_feed':self.updater_feed,'product_feed':self.product_feed,
                        'work_dir':Path(os.environ.get('LOCALAPPDATA',str(Path.home()))) / 'FRBLaunch' / 'UpdateWork'})
        self._run('prepare',context)
        self.message.setText('Updaterの検証・準備中...')

    def _prepared(self,result):
        # Do not close Launch until native Updater UI is actually created.
        # The independent Updater remains gated until we acknowledge it.
        self._updater_process=result['process']
        self._updater_ready_file=Path(result['ready_file'])
        self._waiting_for_ui=True
        self._ready_started=time.monotonic()
        self.message.setText('Updater進捗画面の表示を確認しています...')
        self._ready_timer.start()

    def _check_updater_ui_ready(self):
        if not self._waiting_for_ui:
            return
        try:
            ready=self._updater_ready_file
            if ready.is_file():
                info=json.loads(ready.read_text(encoding='utf-8'))
                # PyInstaller --onefile may have a supervisor and a worker
                # process with DIFFERENT PIDs. The UUID-named marker is the
                # binding, not Popen.pid.
                if info.get('status') == 'error':
                    raise RuntimeError('Updater進捗画面の起動失敗: ' + str(info.get('message','')))
                if info.get('status') != 'ready':
                    raise RuntimeError('Updater進捗画面の状態が不正です')
                # This is the single authorization to start the update.
                activate(ready)
                self._ready_timer.stop()
                self._waiting_for_ui=False
                self.busy=False  # QDialog.closeEvent must allow a normal exit.
                ready.unlink(missing_ok=True)
                self.message.setText('Updater進捗画面を確認しました。Launchを終了します。')
                from PySide6.QtWidgets import QApplication
                launcher=self.parent()
                self.accept()
                if callable(getattr(launcher,'quit',None)):
                    launcher.quit()
                else:
                    QApplication.instance().quit()
                return
            if self._updater_process.poll() is not None:
                raise RuntimeError('Updaterが進捗画面を表示する前に終了しました')
            if time.monotonic() - self._ready_started > 40:
                raise TimeoutError('Updater進捗画面を確認できませんでした（40秒）。更新は開始しません。')
        except (OSError, ValueError, RuntimeError, TimeoutError) as exc:
            self._ready_timer.stop()
            self._waiting_for_ui=False
            self._updater_process=None
            self._updater_ready_file=None
            self._failed(str(exc))
            self._finish_ui_wait()

    def _finish_ui_wait(self):
        self.busy=False
        self.check.setEnabled(True)
        self.close_btn.setEnabled(True)
        if self.product_feed and self.updater_feed:
            try:
                newer=not self.current or version_tuple(self.product_feed['version'])>version_tuple(self.current['version'])
                self.apply.setEnabled(bool(newer and self._can_apply() and not pending_recovery(self.install_root)))
            except (ValueError, KeyError, UpdateError):
                self.apply.setEnabled(False)

    def _failed(self,message):
        lead = ('更新情報を取得できません: ' if self._active_mode == 'check'
                else '更新処理を開始できません: ')
        self.message.setText(lead + message)

    def _finished(self):
        if self._waiting_for_ui:
            return  # The separate native progress window has not confirmed startup.
        self.busy=False
        self.check.setEnabled(True)
        self.close_btn.setEnabled(True)
        if self.product_feed and self.updater_feed:
            newer=not self.current or version_tuple(self.product_feed['version'])>version_tuple(self.current['version'])
            self.apply.setEnabled(bool(newer and self._can_apply() and not pending_recovery(self.install_root)))

    def closeEvent(self,event):
        if self.busy or self._waiting_for_ui:event.ignore()
        else:super().closeEvent(event)
