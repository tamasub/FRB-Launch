"""Regression: v0.9.5 race between .go file creation and content flush.

These tests deliberately exercise the handshake module without Windows GUI,
network, real product files, or PyInstaller.
"""
from __future__ import annotations

import importlib.util
import os
import threading
import time
from pathlib import Path

import pytest

MODULE = Path(__file__).resolve().parents[1] / 'src/frb_update/progress_gate.py'
spec = importlib.util.spec_from_file_location('frb_update_progress_gate_hotfix', MODULE)
gate = importlib.util.module_from_spec(spec)
spec.loader.exec_module(gate)


def test_legacy_sender_empty_go_then_writes_start(tmp_path):
    """An older Launch can create .go before its buffered bytes are flushed."""
    ready = tmp_path / 'unique_ready.json'
    go = gate.activation_path(ready)
    go.touch()  # receiver observes 0-byte file; must NOT reject immediately
    result = []

    def worker():
        try:
            gate.wait_for_activation(ready, timeout=3)
            result.append('approved')
        except Exception as exc:
            result.append(type(exc).__name__)

    thread = threading.Thread(target=worker)
    thread.start()
    time.sleep(.25)
    go.write_text('start\n', encoding='ascii')
    thread.join(timeout=4)
    assert not thread.is_alive()
    assert result == ['approved']
    assert not go.exists()


def test_new_sender_publishes_valid_token_atomically(monkeypatch, tmp_path):
    ready = tmp_path / 'ready.json'
    go = gate.activation_path(ready)
    original = gate.os.replace
    saw = []

    def check_replace(source, destination):
        assert Path(destination) == go
        assert not go.exists(), 'receiver must never see an incomplete go file'
        assert Path(source).read_text(encoding='ascii') == 'start\n'
        saw.append(True)
        return original(source, destination)

    monkeypatch.setattr(gate.os, 'replace', check_replace)
    gate.activate(ready)
    assert saw == [True]
    assert go.read_text(encoding='ascii') == 'start\n'
    assert not list(tmp_path.glob('*.tmp'))
    gate.wait_for_activation(ready, timeout=1)
    assert not go.exists()


def test_corrupt_token_is_rejected_not_authorized(tmp_path):
    ready = tmp_path / 'ready.json'
    go = gate.activation_path(ready)
    go.write_text('NOT-START\n', encoding='ascii')
    began = time.monotonic()
    with pytest.raises(RuntimeError, match='不正'):
        gate.wait_for_activation(ready, timeout=3)
    assert 1.3 <= time.monotonic() - began < 3
    assert go.exists(), 'corrupted token stays as evidence; do not start updating'


def test_missing_approval_fails_closed(tmp_path):
    with pytest.raises(TimeoutError, match='許可'):
        gate.wait_for_activation(tmp_path / 'no_go.json', timeout=.2)


def test_partial_garbled_token_rejected(tmp_path):
    ready = tmp_path / 'ready.json'
    go = gate.activation_path(ready)
    go.write_bytes(b'\xff')
    with pytest.raises(RuntimeError, match='不正'):
        gate.wait_for_activation(ready, timeout=3)


def test_unique_requests_cannot_approve_each_other(tmp_path):
    first = tmp_path / 'first.json'
    second = tmp_path / 'second.json'
    gate.activate(first)
    with pytest.raises(TimeoutError):
        gate.wait_for_activation(second, timeout=.2)
    gate.wait_for_activation(first, timeout=.2)
