"""Page Add/Update/Delete via the SAME Studio Change Core used for items.

No direct mutation of Launch configuration, no orphaned items, and no
filesystem side effects. Page unregister deliberately rejects non-empty pages.
"""
from __future__ import annotations

import hashlib
import json
import uuid
from pathlib import Path

from launch_menu_registration import (RegistrationError, VIEW_DEF, DOCUMENT_REF,
                                      launch_view_def_path,
                                      _invoke_delete_cli)

PAGE_VIEW = 'pages_view'
PAGE_SECTION = 'pages'


def page_operation_plan(config_path, action, *, page_id='', title='', icon_key='📁'):
    """Validate against canonical JSON and prepare one CAS-protected operation."""
    filename = Path(config_path).resolve()
    raw = filename.read_bytes()
    document = json.loads(raw.decode('utf-8-sig'))
    pages = document.get('pages')
    items = document.get('items')
    if not isinstance(pages, list) or not isinstance(items, list):
        raise RegistrationError('設定JSONのpages/items配列が見つかりません。')
    identifiers = [str(row.get('page_id') or '') for row in pages if isinstance(row, dict)]
    if len(set(identifiers)) != len(identifiers):
        raise RegistrationError('Page IDが重複しているため変更できません。')
    current = next((row for row in pages if isinstance(row, dict)
                    and row.get('page_id') == page_id), None)
    if action == 'add':
        if not str(title).strip():
            raise RegistrationError('Page名を入力してください。')
        if page_id:
            raise RegistrationError('Page IDはStudioが自動採番します。')
        next_sort = max((int(row.get('sort_order') or 0)
                         for row in pages if isinstance(row, dict)), default=0) + 10
        operation = {'operation': 'add', 'section_id': PAGE_SECTION,
                     'placement': {'position': 'end'},
                     'records': [{'title': str(title).strip(),
                                  'icon_key': str(icon_key or 'なし'),
                                  'enabled': True, 'sort_order': next_sort}]}
        summary = {'added': 1}
    elif action == 'update':
        if current is None:
            raise RegistrationError('簡易編集対象のPageが見つかりません。')
        if not str(title).strip():
            raise RegistrationError('Page名を入力してください。')
        changes = [{'path': k, 'value': v} for k, v in (
            ('title', str(title).strip()), ('icon_key', str(icon_key or 'なし')))
            if current.get(k) != v]
        if not changes:
            return None
        operation = {'operation': 'update', 'section_id': PAGE_SECTION,
                     'targets': [{'id': page_id, 'changes': changes}]}
        summary = {'changed_existing': 1}
    elif action == 'delete':
        if current is None:
            raise RegistrationError('登録解除対象のPageが見つかりません。')
        if page_id == 'system':
            raise RegistrationError('System Pageは内部管理対象のため登録解除できません。')
        attached = [row for row in items if isinstance(row, dict)
                    and str(row.get('page_id') or '') == page_id]
        if attached:
            raise RegistrationError(
                f'配下に設定JSONの登録が{len(attached)}件あります。'
                '孤児データを防ぐため、このPageは登録解除できません。'
                '先に配下の登録を整理してください。')
        if sum(bool(p.get('enabled', True)) for p in pages if isinstance(p, dict)) <= 1:
            raise RegistrationError('最後のPageは登録解除できません。')
        operation = {'operation': 'delete', 'section_id': PAGE_SECTION,
                     'targets': [{'id': page_id}]}
        summary = {'deleted': 1}
    else:
        raise RegistrationError('未対応のPage操作です。')
    return {'filename': filename, 'base_sha256': hashlib.sha256(raw).hexdigest(),
            'operations': [operation], 'summary': summary}


def commit_page_operation(config_path, studio_root, action, *, page_id='',
                          title='', icon_key='📁', timeout=40):
    """PREVIEW → Expected/Actual Diff → COMMIT in Studio; never write JSON here."""
    plan = page_operation_plan(config_path, action, page_id=page_id,
                               title=title, icon_key=icon_key)
    if plan is None:
        return None
    trusted = {'schema_version': 'studio_change_core_config_v0_1',
               'documents': {DOCUMENT_REF: {
                   'path': str(plan['filename']), 'view_def': VIEW_DEF,
                   'view_def_path': str(launch_view_def_path(plan['filename'])),
                   'view_id': PAGE_VIEW, 'section_ids': [PAGE_SECTION]}}}
    request = {'schema_version': 'studio_changeset_v0_1',
               'request_id': 'launch-page-' + uuid.uuid4().hex,
               'mode': 'dry_run', 'document_ref': DOCUMENT_REF,
               'base_sha256': plan['base_sha256'], 'view_def': VIEW_DEF,
               'view_id': PAGE_VIEW, 'operations': plan['operations']}
    result = None
    for mode in ('dry_run', 'commit'):
        result = _invoke_delete_cli(Path(studio_root).resolve(), trusted,
                                    request, mode, timeout)
        if any(result.get('summary', {}).get(k) != v
               for k, v in plan['summary'].items()):
            raise RegistrationError('Studio CLIのPage操作件数が期待値と一致しません。')
    return result



def page_reorder_plan(config_path, page_id, placement, *,
                      system_page_id='system',
                      bookmarks_item_id='__browser_bookmarks_root'):
    """One atomic Studio Update of visible Files Exp Page order.

    This is NOT an item Move: Page roots live in pages[], while the promoted
    bookmark root represents the System Page. All other items, including
    physical Files roots, retain their exact JSON records.
    """
    from launch_virtual_tree import virtual_exp_roots

    filename = Path(config_path).resolve()
    raw = filename.read_bytes()
    doc = json.loads(raw.decode('utf-8-sig'))
    pages, items = doc.get('pages'), doc.get('items')
    if not isinstance(pages, list) or not isinstance(items, list):
        raise RegistrationError('設定JSONのpages/items配列が見つかりません。')
    if not isinstance(placement, dict):
        raise RegistrationError('Page移動先が不正です。')
    page_id = str(page_id or '')
    position = placement.get('position')
    anchor = str(placement.get('anchor_page_id') or '')
    if position not in ('end', 'before', 'after'):
        raise RegistrationError('Page移動位置が不正です。')
    visible = [str(node['page_id']) for node in virtual_exp_roots(
        pages, items, system_page_id=system_page_id,
        bookmarks_item_id=bookmarks_item_id)]
    if len(visible) != len(set(visible)) or page_id not in visible:
        raise RegistrationError('表示中のPageの識別情報が不正です。')
    if position != 'end' and anchor not in visible:
        raise RegistrationError('移動先のPageが見つかりません。')
    new_order = [key for key in visible if key != page_id]
    if position == 'end':
        new_order.append(page_id)
    elif anchor == page_id:
        return None
    else:
        new_order.insert(new_order.index(anchor) + (position == 'after'), page_id)
    if new_order == visible:
        return None
    page_by_id = {str(p.get('page_id') or ''): p for p in pages
                  if isinstance(p, dict)}
    if len(page_by_id) != len([p for p in pages if isinstance(p, dict)]):
        raise RegistrationError('Page IDに重複があります。')
    # Give every visible Page a unique, integer, deterministic order. Hidden
    # pages (if any) are left intact, avoiding unrelated configuration edits.
    targets = []
    for index, ident in enumerate(new_order):
        order = (index + 1) * 10
        current = page_by_id[ident]
        if current.get('sort_order') != order:
            targets.append({'id': ident, 'changes': [
                {'path': 'sort_order', 'value': order}]})
    if not targets:
        return None
    request = {'schema_version': 'studio_changeset_v0_1',
               'request_id': 'launch-page-reorder-' + uuid.uuid4().hex,
               'mode': 'dry_run', 'document_ref': DOCUMENT_REF,
               'base_sha256': hashlib.sha256(raw).hexdigest(),
               'view_def': VIEW_DEF, 'view_id': PAGE_VIEW,
               'operations': [{'operation': 'update', 'section_id': PAGE_SECTION,
                               'targets': targets}]}
    trusted = {'schema_version': 'studio_change_core_config_v0_1',
               'documents': {DOCUMENT_REF: {
                   'path': str(filename), 'view_def': VIEW_DEF,
                   'view_def_path': str(launch_view_def_path(filename)),
                   'view_id': PAGE_VIEW, 'section_ids': [PAGE_SECTION]}}}
    return {'request': request, 'trusted': trusted,
            'count': len(targets), 'source': page_id,
            'ordered_pages': new_order}


def commit_page_reorder(config_path, studio_root, page_id, placement, *,
                        system_page_id='system',
                        bookmarks_item_id='__browser_bookmarks_root',
                        timeout=40):
    """PREVIEW and COMMIT through Studio Change Core; no direct JSON write."""
    plan = page_reorder_plan(config_path, page_id, placement,
                             system_page_id=system_page_id,
                             bookmarks_item_id=bookmarks_item_id)
    if plan is None:
        return None
    for mode in ('dry_run', 'commit'):
        reply = _invoke_delete_cli(Path(studio_root).resolve(), plan['trusted'],
                                   plan['request'], mode, timeout)
        if reply.get('summary', {}).get('changed_existing') != plan['count']:
            raise RegistrationError('Studio CLIのPage表示順変更件数が期待値と一致しません。')
        if mode == 'dry_run' and reply.get('saved'):
            raise RegistrationError('Page順序変更の事前検証で保存されました。')
        if mode == 'commit' and not reply.get('saved'):
            raise RegistrationError('Studio CLIのPage表示順を保存できませんでした。')
    return reply
