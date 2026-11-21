"""Make physical Keyboard Ex children match the Files List sort for that folder.

Records are (directory?, pathname, title, original_object); no Qt imports and
no separate popup preference. The pinned '(current folder)' action is excluded.
"""
from middle_folder_filter import filter_sort_folder_rows


def sort_physical_popup_records(records, mode):
    # Name sorts need no disk metadata lookup, even for thousands of files.
    if mode in ('name', 'name_desc'):
        ordered = sorted(records, key=lambda r: str(r[2]).casefold(),
                         reverse=mode == 'name_desc')
        ordered.sort(key=lambda r: not r[0])  # folders before files
        return [record[3] for record in ordered]
    rows = []
    for i, (is_directory, path, title, _item) in enumerate(records):
        rows.append({'item_kind': 'directory' if is_directory else 'command',
                     'title': str(title), '_browse_file': str(path),
                     '_popup_index': i})
    sorted_rows = filter_sort_folder_rows(rows, '', mode)
    return [records[row['_popup_index']][3] for row in sorted_rows]
