"""Files List .log -> Sakura: opt-in native guest stays unchanged."""
from pathlib import Path

from external_preview_route import (
    ExternalPreviewTarget, external_preview_target, external_start_command,
)


def test_log_routes_to_sakura_from_files_list(tmp_path):
    logfile = tmp_path / 'launch.log'
    logfile.write_text('trace', encoding='utf-8')
    exe = tmp_path / 'sakura.exe'
    exe.write_bytes(b'test')

    for field in ('_browse_file', '_indexed_file', '_file'):
        route = external_preview_target({field: str(logfile)},
                                        sakura_lookup=lambda: str(exe))
        assert route == ExternalPreviewTarget('sakura', str(logfile), str(exe))
        assert external_start_command(route) == [str(exe), '--', str(logfile)]


def test_case_insensitive_log_extension_and_missing_editor(tmp_path):
    logfile = tmp_path / 'SAKURA_WINDOW_TRACE.LOG'
    logfile.write_text('trace', encoding='utf-8')
    route = external_preview_target({'_browse_file': str(logfile)},
                                    sakura_lookup=lambda: 'C:/test/sakura.exe')
    assert route.app == 'sakura'
    assert external_preview_target({'_browse_file': str(logfile)},
                                   sakura_lookup=lambda: None) is None


def test_log_does_not_redirect_nonfiles_or_unrelated_extensions(tmp_path):
    logfile = tmp_path / 'launch.log'
    logfile.write_text('trace', encoding='utf-8')
    jsonfile = tmp_path / 'data.json'
    jsonfile.write_text('{}', encoding='utf-8')
    lookup = lambda: 'C:/test/sakura.exe'
    assert external_preview_target({'_browse_file': str(logfile),
                                    '_launch_virtual_node': {'kind': 'file'}},
                                   sakura_lookup=lookup) is None
    assert external_preview_target({'_browse_file': str(jsonfile)},
                                   sakura_lookup=lookup) is None
    assert external_preview_target({'_browse_file': str(tmp_path)},
                                   sakura_lookup=lookup) is None


def test_existing_txt_ini_and_md_routing_unchanged(tmp_path):
    lookup = lambda: 'C:/test/sakura.exe'
    for suffix in ('.txt', '.ini'):
        file = tmp_path / ('sample' + suffix)
        file.write_text('test', encoding='utf-8')
        assert external_preview_target({'_browse_file': str(file)},
                                       sakura_lookup=lookup).app == 'sakura'
    md = tmp_path / 'note.md'
    md.write_text('# test', encoding='utf-8')
    assert external_preview_target({'_browse_file': str(md)},
                                   sakura_lookup=lookup).app == 'obsidian'
