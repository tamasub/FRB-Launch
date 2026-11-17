"""Regression for the Git action buttons and keyboard documentation (Qt-free)."""
import importlib.util
from pathlib import Path
from test_git_repo_gear_keyboard_20261116 import git_adapter
from test_list_confirmation_click_gate_20261110 import setup_question, event

ROOT=Path(__file__).resolve().parents[1]


def test_git_repeated_background_click_does_not_reset_selected_ok():
    adapter,_,buttons=git_adapter()
    ok,cancel=buttons
    adapter.background_click('dialog')
    assert adapter.selected=='Cancel'
    adapter.remote_command('RIGHT')
    assert adapter.selected=='OK'
    for origin in ('dialog','launch','dialog'):
        assert adapter.background_click(origin) is False  # Armed click executes.
        assert adapter.selected=='OK'
    ok.click.assert_not_called();cancel.click.assert_not_called()
    adapter.remote_command('CLICK')
    ok.click.assert_called_once_with();cancel.click.assert_not_called()


def test_native_dialog_buttons_allow_press_and_release_including_button_box():
    module,guard,original,_,_,viewport,_,_=setup_question()
    adapter,_,buttons=git_adapter()
    adapter.launcher=original.launcher
    adapter.launcher.remote_window.isVisible=lambda:False
    adapter.selection_combo.isAncestorOf=lambda obj:False
    guard.wheel_receiver=adapter
    adapter.background_click('dialog');adapter.remote_command('RIGHT')
    for cls in ('QAbstractButton','QDialogButtonBox'):
        obj=type(viewport)();obj._window=guard.question
        obj.inherits=lambda name,cls=cls:name==cls
        for kind in (module.QEvent.Type.MouseButtonPress,module.QEvent.Type.MouseButtonRelease):
            ev=event(kind)
            assert guard.eventFilter(obj,ev) is False
            ev.accept.assert_not_called()
            assert adapter.selected=='OK'
    buttons[0].click()
    buttons[0].click.assert_called_once_with()
    buttons[1].click.assert_not_called()


def test_mouse_over_real_ok_button_never_reverts_selection_to_cancel():
    module,guard,original,_,_,viewport,_,_=setup_question()
    adapter,_,buttons=git_adapter()
    adapter.launcher=original.launcher
    adapter.launcher.remote_window.isVisible=lambda:False
    adapter.selection_combo.isAncestorOf=lambda obj:False
    guard.wheel_receiver=adapter
    adapter.background_click('dialog');adapter.remote_command('RIGHT')
    ok,cancel=buttons
    for button,hit in ((ok,True),(cancel,False)):
        button.isVisible=lambda:True
        button.isEnabled=lambda:True
        button.mapFromGlobal=lambda pt:pt
        button.rect=lambda hit=hit:type('Rect',(),{'contains':lambda self,pt:hit})()
    obj=type(viewport)();obj._window=guard.question
    obj.inherits=lambda name:False
    for kind in (module.QEvent.Type.MouseButtonPress,module.QEvent.Type.MouseButtonRelease):
        ev=event(kind)
        assert guard.eventFilter(obj,ev) is False
        ev.accept.assert_not_called()
        assert adapter.selected=='OK'
    ok.click.assert_not_called();cancel.click.assert_not_called()


def test_about_contains_exact_github_url():
    spec=importlib.util.spec_from_file_location('tested_app_version',ROOT/'src/app_version.py')
    app=importlib.util.module_from_spec(spec);spec.loader.exec_module(app)
    assert app.APP_REPOSITORY_URL=='https://github.com/tamasub/FRB-Launch'
    assert app.APP_ABOUT_TEXT.splitlines()==[
        app.APP_NAME,'Version '+app.APP_VERSION,app.APP_PROJECT,
        'GitHub: https://github.com/tamasub/FRB-Launch']


def test_readme_explains_all_new_keys_without_claiming_published_release():
    readme=(ROOT/'README.md').read_text('utf-8')
    for token in ('キーボード操作まとめ（2026年11月16日・開発版）',
                  'Ctrl + F','Ctrl + G','Ctrl + H','Ctrl + I',
                  'Home','Tab','Shift + Tab','PageUp','PageDown','Space',
                  '手裏剣スクロール','Exp → List → フォルダー検索',
                  '実際のOK/Cancelボタンは通常のマウスクリックで直接操作可能'):
        assert token in readme,token


def test_readme_highlights_explorer_and_chromium_drag_drop():
    readme=(ROOT/'README.md').read_text('utf-8')
    assert 'ドラッグ＆ドロップでかんたん登録' in readme
    assert 'エクスプローラーから' in readme
    assert 'フォルダーやファイルをFRB Launchのメニューへドロップ' in readme
    assert 'Chrome／Edgeから' in readme
    assert 'URLをドラッグしてFRB Launchのメニューへドロップ' in readme


def test_real_event_sequence_first_click_switches_then_wheel_and_click_activates_ok():
    """The bug: first background click focused Cancel; later clicks did nothing."""
    from test_list_confirmation_click_gate_20261110 import send_click
    module, guard, original, _, _, viewport, _, _ = setup_question()
    adapter, combo, buttons = git_adapter()
    adapter.launcher = original.launcher
    adapter.launcher.remote_window.isVisible = lambda: False
    guard.wheel_receiver = adapter
    guard._opened_at -= 1

    # Any Launch surface wheel first chooses the repository.
    assert guard.eventFilter(viewport, event(module.QEvent.Type.Wheel))
    assert combo.currentIndex() == 1
    send_click(module, guard, viewport)  # First unrelated click: stage only.
    assert adapter.input_mode == 'buttons'
    assert adapter.selected == 'Cancel'
    assert adapter.remote_has_selected is False
    assert all(button.click.call_count == 0 for button in buttons)
    send_click(module, guard, viewport)  # No second-click accidental Cancel.
    assert all(button.click.call_count == 0 for button in buttons)

    # Wheel on the same background selects OK, next click must activate OK.
    assert guard.eventFilter(viewport, event(module.QEvent.Type.Wheel))
    assert adapter.selected == 'OK'
    send_click(module, guard, viewport)
    buttons[0].click.assert_called_once_with()
    buttons[1].click.assert_not_called()


def test_real_event_sequence_dialog_surface_click_executes_explicit_ok():
    from test_list_confirmation_click_gate_20261110 import send_click
    module, guard, original, _, _, viewport, _, _ = setup_question()
    adapter, combo, buttons = git_adapter()
    adapter.launcher = original.launcher
    adapter.launcher.remote_window.isVisible = lambda: False
    guard.wheel_receiver = adapter
    guard._opened_at -= 1
    dialog_surface = type(viewport)()
    dialog_surface._window = guard.question

    send_click(module, guard, dialog_surface)  # First click changes stage.
    assert adapter.input_mode == 'buttons'
    assert all(button.click.call_count == 0 for button in buttons)
    assert guard.eventFilter(dialog_surface, event(module.QEvent.Type.Wheel))
    assert adapter.selected == 'OK'
    send_click(module, guard, dialog_surface)  # Explicit choice: executes.
    buttons[0].click.assert_called_once_with()
    buttons[1].click.assert_not_called()


def test_git_native_button_click_and_safety_semantics_are_unchanged():
    adapter, _, (ok, cancel) = git_adapter()
    adapter.focus_buttons()
    assert not adapter.remote_has_selected
    # The Git Remote pad should use the actually selected (safe default)
    # button, never an implicit OK.
    adapter.remote_command('CLICK')
    cancel.click.assert_called_once_with()
    ok.click.assert_not_called()
    adapter.focus_combo()
    adapter.focus_buttons()
    adapter.remote_command('RIGHT')
    adapter.remote_command('CLICK')
    ok.click.assert_called_once_with()



def test_native_ok_click_after_unrelated_focus_switch_is_not_rewritten_as_cancel():
    """The real OK/Cancel buttons still use Qt's native click route."""
    from test_list_confirmation_click_gate_20261110 import send_click
    module, guard, original, _, _, viewport, _, _ = setup_question()
    adapter, combo, (ok, cancel) = git_adapter()
    adapter.launcher = original.launcher
    adapter.launcher.remote_window.isVisible = lambda: False
    guard.wheel_receiver = adapter
    combo.isAncestorOf = lambda obj: False  # Qt-free QComboBox double.
    guard._opened_at -= 1
    send_click(module, guard, viewport)  # Makes Cancel visually active.
    assert adapter.selected == 'Cancel'
    button = type(viewport)()
    button._window = guard.question
    button.inherits = lambda name: name == 'QAbstractButton'
    for kind in (module.QEvent.Type.MouseButtonPress, module.QEvent.Type.MouseButtonRelease):
        ev = event(kind)
        assert guard.eventFilter(button, ev) is False
        ev.accept.assert_not_called()
    # Native Qt delivers the actual OK.clicked here, not the selected Cancel.
    ok.click()
    ok.click.assert_called_once_with()
    cancel.click.assert_not_called()
