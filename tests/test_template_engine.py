"""Tests for template_engine module."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import template_engine


def test_render_template_basic():
    tmpl = "{company} {name}様 件名テスト\n\n{name}様\n本文テスト"
    contact = {"name": "田中太郎", "company": "テスト株式会社", "title": "部長"}
    subject, body = template_engine.render_template(tmpl, contact)
    assert subject == "テスト株式会社 田中太郎様 件名テスト"
    assert "田中太郎様" in body


def test_render_template_missing_field():
    tmpl = "{company} {name}様\n\n{name}様\n{unknown_field}です"
    contact = {"name": "田中", "company": "テスト社"}
    subject, body = template_engine.render_template(tmpl, contact)
    assert subject == "テスト社 田中様"
    assert "です" in body


def test_render_template_empty_body():
    tmpl = "件名のみ"
    contact = {"name": "テスト"}
    subject, body = template_engine.render_template(tmpl, contact)
    assert subject == "件名のみ"
    assert body == ""
