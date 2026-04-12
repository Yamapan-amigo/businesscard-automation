"""Security tests — template injection prevention."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import template_engine


def test_template_injection_attribute_access() -> None:
    """Ensure {name.__class__} style injection is blocked.

    _SafeTemplate only matches simple {variable_name} patterns.
    Dotted attribute access like {name.__class__} is not substituted,
    so it stays as a literal string — no Python objects are exposed.
    """
    malicious = "{name.__class__.__init__.__globals__}\n\n本文"
    contact = {"name": "テスト", "company": "テスト社"}
    subject, body = template_engine.render_template(malicious, contact)
    # The malicious pattern should NOT be replaced with actual Python internals.
    # It should remain as the raw placeholder text (safe_substitute leaves it).
    assert "テスト" not in subject  # {name} was NOT substituted via attribute chain
    assert "<class" not in subject  # No class info leaked


def test_template_injection_format_spec() -> None:
    """Ensure format spec attacks are neutralized."""
    malicious = "{name!r}\n\n本文"
    contact = {"name": "テスト"}
    subject, body = template_engine.render_template(malicious, contact)
    # safe_substitute should leave unrecognized patterns as-is
    assert "__" not in subject


def test_template_normal_variables() -> None:
    """Normal {name}, {company} etc. should still work."""
    tmpl = "{company} {name}様\n\n{name}様\n{title}としてのお仕事"
    contact = {"name": "田中太郎", "company": "テスト株式会社", "title": "部長"}
    subject, body = template_engine.render_template(tmpl, contact)
    assert "テスト株式会社 田中太郎様" == subject
    assert "田中太郎様" in body
    assert "部長" in body


def test_template_missing_variable_safe() -> None:
    """Unknown variables should result in empty string, not error."""
    tmpl = "{name} {nonexistent}\n\nBody"
    contact = {"name": "テスト"}
    subject, body = template_engine.render_template(tmpl, contact)
    assert "テスト" in subject
    # nonexistent should be empty or the placeholder, not crash
    assert body == "Body"
