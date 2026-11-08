"""Tests for the knowledge base loader."""

from __future__ import annotations

import json

import pytest

import kb


def _entry(**overrides) -> dict:
    base = {
        "id": "test_entry",
        "domain": "refund",
        "title": "A title",
        "rule": "A rule.",
        "plain": "A plain sentence.",
        "allowed_refs": ["Test Act, 2020"],
        "source_url": "TODO",
        "verified": False,
        "last_verified": None,
    }
    base.update(overrides)
    return base


def _write(tmp_path, payload) -> str:
    path = tmp_path / "kb.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    return str(path)


def test_project_kb_loads_and_validates():
    entries = kb.load_kb()
    assert len(entries) >= 15
    assert "cpa_limitation_2y" in kb.ids()
    assert "consumer protection act, 2019" in kb.allowlist()
    assert all(entry["verified"] is False for entry in entries)


def test_duplicate_id_fails(tmp_path):
    path = _write(tmp_path, [_entry(), _entry()])
    with pytest.raises(kb.KBError):
        kb.load_kb(path)


def test_missing_field_fails(tmp_path):
    broken = _entry()
    broken.pop("rule")
    path = _write(tmp_path, [broken])
    with pytest.raises(kb.KBError):
        kb.load_kb(path)


def test_invalid_domain_fails(tmp_path):
    path = _write(tmp_path, [_entry(domain="criminal")])
    with pytest.raises(kb.KBError):
        kb.load_kb(path)


def test_invalid_json_fails(tmp_path):
    path = tmp_path / "kb.json"
    path.write_text("{not json", encoding="utf-8")
    with pytest.raises(kb.KBError):
        kb.load_kb(str(path))


def test_render_for_prompt_filters_by_domain():
    kb.load_kb()
    refund_block = kb.render_for_prompt("refund")
    deposit_block = kb.render_for_prompt("deposit")
    everyone = kb.render_for_prompt("unknown")
    assert "cpa_limitation_2y" in refund_block
    assert "deposit_forum_civil" not in refund_block
    assert "arb_clause_basics" in refund_block
    assert "deposit_forum_civil" in deposit_block
    assert "cpa_limitation_2y" not in deposit_block
    assert "deposit_forum_civil" in everyone
    assert "cpa_limitation_2y" in everyone


def test_render_is_compact_and_omits_allowed_refs():
    block = kb.render_for_prompt("refund")
    assert "allowed_refs" not in block
    assert '"verified"' in block


def test_allowlist_contains_every_reference():
    kb.load_kb()
    allowed = kb.allowlist()
    assert "limitation act, 1963" in allowed
    assert "emaar mgf land ltd v. aftab singh" in allowed


def test_get_returns_entry_or_none():
    kb.load_kb()
    assert kb.get("cpa_limitation_2y")["domain"] == "refund"
    assert kb.get("nope") is None


def test_summary_for_ui_has_only_ui_fields():
    kb.load_kb()
    item = kb.summary_for_ui()[0]
    assert set(item) == {"id", "title", "verified"}
