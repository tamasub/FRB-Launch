"""Regression tests: Node installer without LICENSE, offline cache, existing license.

Tests do not make network connections and do not require Node.js on this host.
"""
from __future__ import annotations

import importlib.util
import io
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parent.parent
SCRIPT = ROOT / 'scripts/build_portable_distribution.py'

# Module's imports depend on a Launch checkout, so stub its imported leaf modules.
# This test covers the resolver itself; end-to-end ZIP generation is tested separately.
import types
m_contracts = types.ModuleType('frb_update.contracts')
m_contracts.sha256_file = lambda *_: None
m_contracts.version_tuple = lambda *_: None
m_core = types.ModuleType('frb_update.updater_core')
m_core.validate_zip = lambda *_: None
sys.modules['frb_update'] = types.ModuleType('frb_update')
sys.modules['frb_update.contracts'] = m_contracts
sys.modules['frb_update.updater_core'] = m_core
sys.modules['build_release_package'] = types.ModuleType('build_release_package')
sys.modules['build_release_package'].build = lambda *_: None
spec = importlib.util.spec_from_file_location('portable_dist_license_test', SCRIPT)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)

class FakeResponse:
    def __init__(self, data):
        self.stream = io.BytesIO(data)
    def __enter__(self): return self
    def __exit__(self, *_): return False
    def read(self, size): return self.stream.read(size)

with tempfile.TemporaryDirectory(prefix='frb_node_license_') as temp:
    base = Path(temp)
    node = base / 'node' / 'node.exe'
    node.parent.mkdir()
    node.write_text('#!/usr/bin/env python3\nprint("24.20.0")\n')
    node.chmod(0o755)
    dist, studio, output = base / 'dist', base / 'studio', base / 'release'
    dist.mkdir(); studio.mkdir()

    actual = ('Node.js is licensed for use as follows:\n' + 'X' * 200).encode()
    fetch_calls = []
    def fake_urlopen(req, timeout):
        fetch_calls.append(req.full_url)
        return FakeResponse(actual)
    with patch.object(module.urllib.request, 'urlopen', side_effect=fake_urlopen):
        resolved = module.ensure_node_license(node, None, dist, studio, output)
    assert resolved.read_bytes() == actual
    assert fetch_calls == ['https://raw.githubusercontent.com/nodejs/node/v24.20.0/LICENSE']
    print('PASS: automatically retrieves matching tagged Node.js LICENSE')

    with patch.object(module.urllib.request, 'urlopen', side_effect=AssertionError('Must use cache')):
        assert module.ensure_node_license(node, None, dist, studio, output) == resolved
    print('PASS: cached license reused offline')

    explicit = base / 'manual_license'
    explicit.write_text('Manual official Node.js LICENSE')
    with patch.object(module.urllib.request, 'urlopen', side_effect=AssertionError('Must use supplied LICENSE')):
        assert module.ensure_node_license(node, explicit, dist, studio, output) == explicit.resolve()
    print('PASS: explicitly supplied license takes priority')

    explicit.unlink()
    try:
        module.ensure_node_license(node, explicit, dist, studio, output)
        raise AssertionError('Missing explicit license should fail')
    except FileNotFoundError as error:
        assert '--node-license' in str(error)
    print('PASS: missing explicit LICENSE is reported, not silently ignored')

    # Cached file absent + network failure must never silently skip license packaging.
    resolved.unlink()
    with patch.object(module.urllib.request, 'urlopen', side_effect=OSError('offline')):
        try:
            module.ensure_node_license(node, None, dist, studio, output)
            raise AssertionError('Missing license should fail')
        except FileNotFoundError as error:
            assert 'https://nodejs.org/dist/v24.20.0/' in str(error)
    print('PASS: offline failure explains official manual fallback')
