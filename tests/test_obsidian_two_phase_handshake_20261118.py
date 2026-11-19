"""Two independent CLI evals: write once, read-only verify thereafter."""
from pathlib import Path
from obsidian_dock_bridge import main_open_code, main_verify_code
from test_obsidian_main_window_dock_20261118 import eval_js


def test_separate_open_and_verify_one_main_leaf_no_popout():
    open_script=main_open_code('FRB/B.md')
    verify_script=main_verify_code('FRB/B.md')
    script='(async()=>{const opened=await '+open_script+'; return {opened, verified:'+verify_script+'};})()'
    output=eval_js(script)
    assert output['result']['opened']=='FRB_MAIN_OPENED'
    assert output['result']['verified']=='FRB_MAIN_TITLE:Main%20Obsidian%20Window'
    assert output['events']==['main:FRB/B.md']
    assert output['mainFile']=='FRB/B.md' and output['popupFile']=='FRB/A.md'


def test_verify_cannot_change_documents_or_choose_popup():
    probe=main_verify_code('FRB/B.md')
    assert '.openFile(' not in probe
    assert 'newTab' not in probe and 'paneType=window' not in probe
    no_main=eval_js(probe,main=False)
    assert no_main['result']=='FRB_MAIN_NOT_READY'
    assert no_main['events']==[]
    not_open=eval_js(probe,main=True)
    assert not_open['result']=='FRB_MAIN_NOT_READY'
    assert not_open['events']==[]


def test_orchestration_keeps_one_open_request_until_startup_not_ready():
    panel=(Path(__file__).resolve().parents[1] / 'src' / 'studio_preview_panel.py').read_text(encoding='utf-8')
    method=panel.split('    def _probe_obsidian_main_window(',1)[1].split('    def _on_obsidian_main_probe_completed(',1)[0]
    assert 'request_open = not self._obsidian_main_open_issued' in method
    assert "stage='main_open'" in method
    assert "stage='main_verify'" in method
    assert 'main_verify_code(note[1])' in method
    assert 'main_open_code(note[1])' in method
    assert "'FRB_MAIN_OPEN_NOT_READY'" in method
