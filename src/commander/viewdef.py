"""Pure ViewDef validation and command argument generation (no Qt needed)."""
import json
import re
from pathlib import Path, PureWindowsPath

SCHEMA_VERSION = "frb_commander_viewdef_v0.1"
_SUPPORTED_SCRIPT_SUFFIXES = frozenset({".ps1"})
_PLACEHOLDER = re.compile(r"^\$\{([a-z][a-z0-9_]*)\}$")
_KNOWN_INPUTS = {"single_choice", "text", "file_path"}


def companion_viewdef(script):
    """The paired definition is independent of Launch's filename conventions."""
    path = Path(script)
    if path.suffix.casefold() not in _SUPPORTED_SCRIPT_SUFFIXES or not path.is_file():
        return None
    candidate = path.with_suffix('.viewdef')
    return candidate if candidate.is_file() else None


def read_viewdef(script):
    script = Path(script).resolve()
    definition = companion_viewdef(script)
    if definition is None:
        raise ValueError('対応する .viewdef が見つかりません')
    try:
        obj = json.loads(definition.read_text(encoding='utf-8-sig'))
    except (ValueError, OSError) as exc:
        raise ValueError('.viewdef の読込に失敗しました: ' + str(exc)) from exc
    validate_viewdef(obj, script)
    return obj


def validate_viewdef(obj, script):
    if not isinstance(obj, dict) or obj.get('schema_version') != SCHEMA_VERSION:
        raise ValueError(f'schema_version は {SCHEMA_VERSION} にしてください')
    if obj.get('view_type') != 'frb_commander':
        raise ValueError('view_type は frb_commander が必要です')
    target = obj.get('script')
    if not isinstance(target, dict) or not isinstance(target.get('file'), str):
        raise ValueError('script.file は必須です')
    # No directory traversal: only the explicitly right-clicked file is runnable.
    if (Path(target['file']).name != target['file'] or
            PureWindowsPath(target['file']).name != target['file'] or
            target['file'].casefold() != Path(script).name.casefold()):
        raise ValueError('ViewDefのscript.fileが選択スクリプトと一致しません')
    if not isinstance(obj.get('title'), str) or not obj['title'].strip():
        raise ValueError('titleが必要です')
    steps = obj.get('steps')
    if (not isinstance(steps, list) or not steps or
            not isinstance(steps[0], dict) or steps[0].get('id') != 'source' or
            steps[0].get('input') != 'single_choice'):
        raise ValueError('stepsの最初にsource選択が必要です')
    ids = set()
    for step in steps:
        if not isinstance(step, dict):
            raise ValueError('stepsの各要素はオブジェクトです')
        name = step.get('id')
        if not isinstance(name, str) or not re.fullmatch(r'[a-z][a-z0-9_]*', name) or name in ids:
            raise ValueError('step.id は一意の英小文字識別子が必要です')
        ids.add(name)
        if step.get('input') not in _KNOWN_INPUTS or not isinstance(step.get('label'), str):
            raise ValueError(f'{name}: inputまたはlabelが不正です')
        if step['input'] == 'single_choice':
            options = step.get('choices')
            if not isinstance(options, list) or not options:
                raise ValueError(f'{name}: choicesが必要です')
            seen = set()
            for choice in options:
                if (not isinstance(choice, dict) or
                        not isinstance(choice.get('value'), str) or
                        not isinstance(choice.get('label'), str) or
                        choice['value'] in seen):
                    raise ValueError(f'{name}: choiceが不正です')
                seen.add(choice['value'])
                if name == 'source':
                    args = choice.get('args')
                    if not isinstance(args, list) or any(not isinstance(a, str) for a in args):
                        raise ValueError('sourceの各choiceにはargs配列が必要です')
        if step['input'] == 'file_path':
            selector = step.get('selector')
            if not isinstance(selector, dict) or selector.get('type') != 'keyboard_ex.file':
                raise ValueError(f'{name}: keyboard_ex.fileが必要です')
            start = selector.get('initial_location')
            if not isinstance(start, dict) or start.get('type') not in ('workspace_root', 'parent_of', 'script_dir'):
                raise ValueError(f'{name}: initial_location.typeが未対応です')
            if start['type'] == 'parent_of' and start.get('selection') not in ids:
                raise ValueError(f'{name}: parent_ofは先行する選択項目を参照してください')
        when = step.get('visible_when')
        if when is not None and (not isinstance(when, dict) or len(when) != 1 or
                                 not all(isinstance(k, str) and isinstance(v, str) for k,v in when.items())):
            raise ValueError(f'{name}: visible_whenが不正です')
    for step in steps:
        for key in (step.get('visible_when') or {}):
            if key not in ids:
                raise ValueError(f'{step["id"]}: 未定義の依存先 {key}')
    for choice in steps[0]['choices']:
        for arg in choice['args']:
            if '${' in arg:
                match = _PLACEHOLDER.fullmatch(arg)
                if match is None or match.group(1) not in ids:
                    raise ValueError(f'引数テンプレートが不正です: {arg}')
    return True


def visible_steps(definition, values):
    result = []
    for step in definition['steps']:
        conditions = step.get('visible_when') or {}
        if all(values.get(key) == expected for key, expected in conditions.items()):
            result.append(step)
    return result


def build_argv(definition, values, script):
    """Return a separate argv token per argument; never use shell interpolation."""
    script = Path(script).resolve()
    validate_viewdef(definition, script)
    if not script.is_file():
        raise ValueError('スクリプトが見つかりません')
    visible = visible_steps(definition, values)
    for step in visible:
        value = values.get(step['id'])
        if step.get('required', True) and (not isinstance(value, str) or not value.strip()):
            raise ValueError(f'{step["label"]}を選択してください')
        if value is None:
            continue
        if step['input'] == 'single_choice':
            if value not in [choice['value'] for choice in step['choices']]:
                raise ValueError(f'{step["label"]}は定義された候補から選んでください')
        if step['input'] == 'file_path' and not Path(value).is_file():
            raise ValueError(f'{step["label"]}のファイルが見つかりません: {value}')
    selected = next(choice for choice in definition['steps'][0]['choices']
                    if choice['value'] == values['source'])
    extra = []
    for token in selected['args']:
        match = _PLACEHOLDER.fullmatch(token)
        extra.append(values[match.group(1)] if match else token)
    return ['-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', str(script), *extra]


def resolve_initial_directory(step, values, *, script, workspace_root=None):
    config = step['selector']['initial_location']
    kind = config['type']
    if kind == 'parent_of':
        selected = values.get(config['selection'])
        if not selected or not Path(selected).is_file():
            raise ValueError('初期フォルダーに必要な先行ファイルが未選択です')
        return Path(selected).resolve().parent
    if kind == 'script_dir':
        return Path(script).resolve().parent
    if kind == 'workspace_root':
        root = Path(workspace_root) if workspace_root else None
        return root.resolve() if root and root.is_dir() else Path(script).resolve().parent
    raise ValueError('未対応の初期フォルダー方式: ' + kind)
