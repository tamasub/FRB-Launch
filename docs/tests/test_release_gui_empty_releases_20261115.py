"""Static/contract checks for the Windows PowerShell 5.1 empty Releases hotfix.

A real GUI execution on Windows is still required.
"""
from pathlib import Path
import base64
import json

ROOT = Path(__file__).resolve().parents[1]
PS1 = ROOT / "release_FRBLaunch_GUI.ps1"


def script():
    return PS1.read_text(encoding="utf-8-sig")


def test_zero_releases_does_not_dereference_a_null_object():
    s = script()
    assert 'if ($null -eq $r) { continue }' in s
    assert "$r.PSObject.Properties['isDraft']" in s
    assert "$r.PSObject.Properties['tagName']" in s
    assert 'if ($versions.Count -eq 0) {' in s
    assert "BeginJob 'DISCOVER_FEED'" in s
    assert "throw 'GitHubにバージョン付きReleaseがありません" not in s
    assert 'if ($r.isDraft)' not in s


def test_valid_releases_still_supply_the_highest_version():
    s = script()
    assert 'release list --repo ' in s
    assert '--json tagName,isDraft' in s
    assert 'Sort-Object { VersionCode $_ } -Descending | Select-Object -First 1' in s
    assert 'NextVersion $script:LatestRemote $kind' in s


def test_no_releases_uses_fixed_preview_feed_only_as_baseline():
    s = script()
    assert "'DISCOVER_FEED'" in s
    assert "'/contents/release-feed/preview/product_feed.json?ref=main'" in s
    assert "[Convert]::FromBase64String" in s
    assert "[System.Text.Encoding]::UTF8.GetString" in s
    assert "'frb-product-feed-v1'" in s
    assert "'FRBLaunchIntegrated'" in s
    assert "$script:LatestRemote = $baseline" in s
    assert "Release 0件" in s
    assert '削除済みReleaseが現存するという意味ではありません。' in s


def test_no_guessed_version_if_preview_feed_unavailable():
    s = script()
    assert 'Preview Feedも取得できないため、次版を自動決定できません。' in s
    assert '採番を中止しました。' in s
    assert '$script:RemoteReady = $false' in s
    assert '$script:prepare.Enabled = (-not $busy -and $script:RemoteReady)' in s
    assert '$script:publish.Enabled = (-not $busy -and $script:RemoteReady -and' in s


def test_release_pipeline_and_human_approval_unchanged():
    s = script()
    assert ' -PublishOnly -GuiApprovedTag ' in s
    assert 'DialogResult]::Yes' in s
    assert "BeginJob 'PREPARE'" in s
    assert "BeginJob 'PUBLISH'" in s


def test_ps51_encoding_and_crlf():
    data = PS1.read_bytes()
    assert data.startswith(b'\xef\xbb\xbf')
    assert data.count(b'\r\n') == data.count(b'\n')


def test_fixture_demonstrates_deleted_releases_but_existing_feed_v097():
    # The JSON shapes are those returned by `gh release list --json ...`
    # and GitHub's contents API, respectively; no network call in tests.
    releases = json.loads('[]')
    previous = {"schema": "frb-product-feed-v1", "product": "FRBLaunchIntegrated", "version": "0.9.7"}
    response = {"content": base64.b64encode(json.dumps(previous).encode()).decode()}
    feed = json.loads(base64.b64decode(response["content"]))
    assert len(releases) == 0 and feed['version'] == '0.9.7'
    assert '.'.join((feed['version'].split('.')[:2]) + [str(int(feed['version'].split('.')[2]) + 1)]) == '0.9.8'
