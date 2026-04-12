"""Load and render email templates with contact data."""

from __future__ import annotations

import re
from pathlib import Path
from string import Template

import config


class _SafeTemplate(Template):
    """Template that uses {name} syntax instead of $name for compatibility."""

    delimiter = "{"
    pattern = r"""
        \{(?:
            (?P<escaped>\{)       |  # {{ for literal {
            (?P<named>[a-z_]+)\}  |  # {name}
            (?P<braced>[a-z_]+)\} |  # same
            (?P<invalid>)            # anything else
        )
    """


def load_template(template_name: str) -> str:
    path = config.TEMPLATE_DIR / template_name
    return path.read_text(encoding="utf-8")


def render_template(
    template_str: str, contact: dict
) -> tuple[str, str]:
    """Render a template string with contact data.

    Template format:
        First line = subject
        (blank line)
        Remaining lines = body

    Uses safe substitution — unknown keys become empty strings,
    and attribute access (e.g. {name.__class__}) is blocked.

    Returns (subject, body).
    """
    safe_data = {k: (v if v else "") for k, v in contact.items()}
    tmpl = _SafeTemplate(template_str)
    filled = tmpl.safe_substitute(safe_data)
    filled = _clean_empty_fields(filled)
    lines = filled.split("\n", 2)
    subject = lines[0].strip()
    body = lines[2].strip() if len(lines) > 2 else ""
    return subject, body


def _clean_empty_fields(text: str) -> str:
    """Remove awkward phrasing caused by empty template fields."""
    # "でのとしての" -> "での" (empty title)
    text = text.replace("でのとしての", "での")
    # "での お取り組み" -> "のお取り組み" (empty title but company exists)
    text = text.replace("での お取り組み", "のお取り組み")
    # Remove double spaces
    text = re.sub(r"  +", " ", text)
    # Remove leading/trailing spaces on lines
    text = "\n".join(line.rstrip() for line in text.split("\n"))
    return text
