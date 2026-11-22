"""Locations are display destinations, not necessarily filesystem paths.

A search Location has no parent directory. Each result still carries its own
real file / registered Launch identity; display metadata never grants write
or execution authority. This module has no Qt dependency.
"""
from dataclasses import dataclass

from search_result_order import display_columns


@dataclass(frozen=True)
class Location:
    kind: str  # physical | virtual | search
    identity: str
    label: str

    def __post_init__(self):
        if self.kind not in ('physical', 'virtual', 'search'):
            raise ValueError('Unknown Launch location type')
        if not self.identity:
            raise ValueError('Location identity cannot be empty')


def search_location(query):
    text = str(query).strip()
    if not text:
        raise ValueError('Empty query is a folder location, not search')
    return Location('search', text.casefold(), f'🔍 検索結果：{text}')


def search_breadcrumb(query):
    """A search has exactly one non-physical, non-parent crumb."""
    location = search_location(query)
    return [(location.label, ('search', str(query).strip()))]


def search_list_rows(pairs):
    """Project existing global-search (row, hierarchy) pairs for Files List.

    Preserve source row fields, execution steps, IDs and filesystem markers.
    The UI may add a *view-only* virtual identity for JSON menu operations;
    physical files and choice results retain their original dispatch fields.
    """
    projected = []
    for original, hierarchy in pairs:
        row = dict(original)
        _title, description = display_columns(row, hierarchy, selection=False)
        row['_main_search_result'] = True
        row['_search_hierarchy'] = hierarchy
        row['_search_description'] = description
        if row.get('_search_selection_owner'):
            row['_search_item_type'] = '選択候補'
        elif row.get('_indexed_file') or row.get('_browse_file'):
            row['_search_item_type'] = 'ファイル'
        elif row.get('item_kind') == 'directory' and row.get('_file'):
            row['_search_item_type'] = 'フォルダー'
        elif row.get('item_kind') in ('category', 'directory'):
            row['_search_item_type'] = 'フォルダー'
        else:
            row['_search_item_type'] = row.get('item_kind') or 'アイテム'
        projected.append(row)
    return projected
