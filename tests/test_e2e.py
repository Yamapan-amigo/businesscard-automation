"""E2E tests — full user workflow verification.

Tests the complete flow a user would go through:
1. DB initialization
2. Contact scraping → DB save
3. Template management (CRUD)
4. Template selection for drafts
5. Draft creation with Outlook (mocked)
6. Processed contact tracking
7. Streamlit page rendering
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

import db
import graph_client
import processed_tracker
import template_engine


# ============================================================
# Fixtures
# ============================================================

@pytest.fixture()
def test_db(tmp_path: Path):
    """Provide a fresh SQLite DB for each test."""
    test_db_path = tmp_path / "test.db"
    with patch.object(db, "DB_FILE", test_db_path):
        db.init_db()
        yield test_db_path


@pytest.fixture()
def sample_contacts() -> list[dict]:
    """Realistic contact data as returned by Eight scraper."""
    return [
        {
            "card_id": "40599577110",
            "name": "伊藤文一",
            "name_reading": "イトウ",
            "email": "f.ito@oplan.co.jp",
            "company": "オープラン株式会社",
            "department": "営業部",
            "title": "Chief Consultant",
            "phone": "03-5829-4906",
            "mobile": "070-4333-2100",
            "added_date": "2026-04-10T07:26:24+09:00",
        },
        {
            "card_id": "40599574658",
            "name": "山田卓",
            "name_reading": "ヤマダ",
            "email": "yamataku@init-inc.com",
            "company": "init株式会社",
            "department": "",
            "title": "代表取締役",
            "phone": "",
            "mobile": "",
            "added_date": "2026-04-10T06:50:00+09:00",
        },
        {
            "card_id": "40599574651",
            "name": "木村将人",
            "name_reading": "キムラ",
            "email": "ses-sales1@twoos.biz",
            "company": "トゥース合同会社",
            "department": "営業部",
            "title": "",
            "phone": "",
            "mobile": "",
            "added_date": "2026-04-10T06:45:00+09:00",
        },
        {
            "card_id": "40599574000",
            "name": "メールなし太郎",
            "name_reading": "",
            "email": "",
            "company": "テスト社",
            "department": "",
            "title": "",
            "phone": "",
            "mobile": "",
            "added_date": "2026-04-10T06:00:00+09:00",
        },
    ]


@pytest.fixture()
def sample_template() -> str:
    return (
        "名刺交換御礼　{company} {name}様\n"
        "\n"
        "{company}\n"
        "{name}様\n"
        "\n"
        "お世話になっております。テストです。\n"
        "何卒よろしくお願いいたします。"
    )


# ============================================================
# E2E Flow 1: Scrape → DB → Draft full pipeline
# ============================================================

class TestFullPipeline:
    """Complete user flow: scrape contacts → save → create drafts."""

    def test_scrape_save_and_retrieve(
        self, test_db: Path, sample_contacts: list[dict]
    ) -> None:
        """Contacts scraped from Eight are saved to DB and retrievable."""
        with patch.object(db, "DB_FILE", test_db):
            inserted = db.save_contacts(sample_contacts)
            assert inserted == 4

            all_contacts = db.get_contacts()
            assert len(all_contacts) == 4

            # Filter by unprocessed
            unprocessed = db.get_contacts(unprocessed_only=True)
            assert len(unprocessed) == 4

    def test_duplicate_scrape_is_idempotent(
        self, test_db: Path, sample_contacts: list[dict]
    ) -> None:
        """Re-scraping the same contacts doesn't create duplicates."""
        with patch.object(db, "DB_FILE", test_db):
            first = db.save_contacts(sample_contacts)
            second = db.save_contacts(sample_contacts)
            assert first == 4
            assert second == 0
            assert len(db.get_contacts()) == 4

    def test_full_draft_pipeline(
        self,
        test_db: Path,
        sample_contacts: list[dict],
        sample_template: str,
        tmp_path: Path,
    ) -> None:
        """Full flow: save contacts → render templates → create drafts → mark processed."""
        json_tracker = tmp_path / "processed.json"

        with (
            patch.object(db, "DB_FILE", test_db),
            patch.object(processed_tracker, "_state_path", return_value=json_tracker),
        ):
            # Step 1: Save contacts (simulating scrape result)
            db.save_contacts(sample_contacts)

            # Step 2: Get unprocessed contacts with email
            contacts = db.get_contacts(unprocessed_only=True)
            with_email = [c for c in contacts if c.get("email")]
            assert len(with_email) == 3  # 1 has no email

            # Step 3: Render templates
            drafts = []
            for contact in with_email:
                subject, body = template_engine.render_template(
                    sample_template, contact
                )
                assert contact["name"] in subject
                assert contact["name"] in body
                drafts.append({
                    "to_email": contact["email"],
                    "subject": subject,
                    "body": body,
                    "contact": contact,
                })
            assert len(drafts) == 3

            # Step 4: Mock Graph API and create drafts
            mock_response = {"id": "mock-msg-id", "isDraft": True}
            with patch.object(
                graph_client, "create_draft", return_value=mock_response
            ) as mock_create:
                for draft in drafts:
                    graph_client.create_draft(
                        token="mock-token",
                        to_email=draft["to_email"],
                        subject=draft["subject"],
                        body=draft["body"],
                    )
                assert mock_create.call_count == 3

            # Step 5: Mark as processed
            processed_ids = [
                processed_tracker.contact_id(d["contact"]) for d in drafts
            ]
            db.mark_processed(processed_ids)
            processed_tracker.mark_processed(
                [d["contact"] for d in drafts]
            )

            # Step 6: Verify processed state
            assert db.get_processed_count() == 3
            remaining = db.get_contacts(unprocessed_only=True)
            assert len(remaining) == 1  # Only the no-email contact
            assert remaining[0]["name"] == "メールなし太郎"

            # JSON tracker also updated
            assert json_tracker.exists()
            json_data = json.loads(json_tracker.read_text())
            assert len(json_data["processed_ids"]) == 3


# ============================================================
# E2E Flow 2: Template collection management
# ============================================================

class TestTemplateCollection:
    """Template CRUD operations as a user would perform them."""

    def test_create_multiple_templates(self, test_db: Path) -> None:
        with patch.object(db, "DB_FILE", test_db):
            db.save_template("レバテック交流会", "件名A\n\n本文A")
            db.save_template("展示会フォロー", "件名B\n\n本文B")
            db.save_template("一般フォローアップ", "件名C\n\n本文C")

            templates = db.list_templates()
            assert len(templates) == 3
            names = {t["name"] for t in templates}
            assert names == {"レバテック交流会", "展示会フォロー", "一般フォローアップ"}

    def test_edit_template(self, test_db: Path) -> None:
        with patch.object(db, "DB_FILE", test_db):
            db.save_template("test", "Original body")
            assert db.get_template("test") == "Original body"

            db.save_template("test", "Updated body")
            assert db.get_template("test") == "Updated body"

            # Still just 1 template
            assert len(db.list_templates()) == 1

    def test_delete_template(self, test_db: Path) -> None:
        with patch.object(db, "DB_FILE", test_db):
            db.save_template("to_delete", "body")
            assert db.get_template("to_delete") == "body"

            db.delete_template("to_delete")
            assert db.get_template("to_delete") is None
            assert len(db.list_templates()) == 0

    def test_rename_template(self, test_db: Path) -> None:
        """Rename = save new + delete old (how the UI does it)."""
        with patch.object(db, "DB_FILE", test_db):
            db.save_template("old_name", "the body")

            # Rename
            body = db.get_template("old_name")
            db.save_template("new_name", body)
            db.delete_template("old_name")

            assert db.get_template("old_name") is None
            assert db.get_template("new_name") == "the body"

    def test_template_selection_for_drafts(
        self, test_db: Path, sample_contacts: list[dict]
    ) -> None:
        """User selects different templates for different contacts."""
        with patch.object(db, "DB_FILE", test_db):
            db.save_template("formal", "御礼　{company} {name}様\n\n{name}様\nフォーマルな本文")
            db.save_template("casual", "こんにちは {name}さん\n\n{name}さん\nカジュアルな本文")

            contact = sample_contacts[0]

            # Formal template
            formal_tmpl = db.get_template("formal")
            subj_f, body_f = template_engine.render_template(formal_tmpl, contact)
            assert "御礼" in subj_f
            assert "フォーマル" in body_f

            # Casual template
            casual_tmpl = db.get_template("casual")
            subj_c, body_c = template_engine.render_template(casual_tmpl, contact)
            assert "こんにちは" in subj_c
            assert "カジュアル" in body_c


# ============================================================
# E2E Flow 3: Edge cases and error handling
# ============================================================

class TestEdgeCases:
    """Edge cases a real user might encounter."""

    def test_contact_without_email_skipped(
        self, test_db: Path, sample_contacts: list[dict], sample_template: str
    ) -> None:
        """Contacts without email are excluded from draft creation."""
        with patch.object(db, "DB_FILE", test_db):
            db.save_contacts(sample_contacts)
            contacts = db.get_contacts(unprocessed_only=True)
            with_email = [c for c in contacts if c.get("email")]
            no_email = [c for c in contacts if not c.get("email")]
            assert len(with_email) == 3
            assert len(no_email) == 1

    def test_processed_contacts_not_shown_again(
        self, test_db: Path, sample_contacts: list[dict]
    ) -> None:
        """Once processed, contacts don't appear in unprocessed list."""
        with patch.object(db, "DB_FILE", test_db):
            db.save_contacts(sample_contacts)
            assert len(db.get_contacts(unprocessed_only=True)) == 4

            db.mark_processed(["40599577110", "40599574658"])
            unprocessed = db.get_contacts(unprocessed_only=True)
            assert len(unprocessed) == 2
            names = {c["name"] for c in unprocessed}
            assert "伊藤文一" not in names
            assert "山田卓" not in names

    def test_clear_processed_resets_all(
        self, test_db: Path, sample_contacts: list[dict]
    ) -> None:
        """Resetting processed data makes all contacts available again."""
        with patch.object(db, "DB_FILE", test_db):
            db.save_contacts(sample_contacts)
            db.mark_processed(["40599577110", "40599574658", "40599574651"])
            assert len(db.get_contacts(unprocessed_only=True)) == 1

            db.clear_processed()
            assert len(db.get_contacts(unprocessed_only=True)) == 4

    def test_graph_api_partial_failure(
        self, test_db: Path, sample_contacts: list[dict], sample_template: str
    ) -> None:
        """If some drafts fail, successfully created ones are still marked processed."""
        with patch.object(db, "DB_FILE", test_db):
            db.save_contacts(sample_contacts)
            contacts = [c for c in db.get_contacts() if c.get("email")]

            # Simulate: 1st succeeds, 2nd fails, 3rd succeeds
            call_count = 0

            def mock_create_draft(**kwargs):
                nonlocal call_count
                call_count += 1
                if call_count == 2:
                    raise Exception("Graph API error")
                return {"id": f"msg-{call_count}"}

            with patch.object(
                graph_client, "create_draft", side_effect=mock_create_draft
            ):
                successful_ids = []
                for contact in contacts:
                    subject, body = template_engine.render_template(
                        sample_template, contact
                    )
                    try:
                        graph_client.create_draft(
                            token="mock",
                            to_email=contact["email"],
                            subject=subject,
                            body=body,
                        )
                        cid = processed_tracker.contact_id(contact)
                        successful_ids.append(cid)
                    except Exception:
                        continue

                db.mark_processed(successful_ids)

            # 2 out of 3 should be processed
            assert db.get_processed_count() == 2
            assert len(db.get_contacts(unprocessed_only=True)) == 2  # 1 no-email + 1 failed

    def test_template_with_missing_fields_renders_safely(self) -> None:
        """Template with fields not in contact data renders without error."""
        tmpl = "{company} {name} {nonexistent}\n\n{title} {department}"
        contact = {"name": "テスト", "company": "テスト社"}
        subject, body = template_engine.render_template(tmpl, contact)
        assert "テスト社" in subject
        assert "テスト" in subject
        # No crash, no KeyError


# ============================================================
# E2E Flow 4: Streamlit page rendering
# ============================================================

class TestStreamlitPages:
    """Verify Streamlit pages render without errors."""

    def test_dashboard_renders(self) -> None:
        """Main dashboard (app.py) renders without error."""
        from streamlit.testing.v1 import AppTest

        at = AppTest.from_file("app.py", default_timeout=10)
        at.run()
        assert not at.exception, f"Dashboard crashed: {at.exception}"
        # Verify page rendered some content (title element varies by Streamlit version)
        assert len(at.title) > 0 or len(at.markdown) > 0

    def test_settings_page_renders(self) -> None:
        """Settings page renders without error."""
        from streamlit.testing.v1 import AppTest

        at = AppTest.from_file("pages/04_設定.py", default_timeout=10)
        at.run()
        assert not at.exception, f"Settings page crashed: {at.exception}"

    def test_scraping_page_renders(self) -> None:
        """Scraping page renders (may show error for missing session, that's OK)."""
        from streamlit.testing.v1 import AppTest

        at = AppTest.from_file("pages/02_スクレイピング.py", default_timeout=10)
        at.run()
        # Page should render — it may show an error about missing Eight session
        # but it should NOT crash with an unhandled exception
        assert not at.exception, f"Scraping page crashed: {at.exception}"

    def test_draft_page_renders(self) -> None:
        """Draft creation page renders (may show warning for no contacts)."""
        from streamlit.testing.v1 import AppTest

        at = AppTest.from_file("pages/03_下書き作成.py", default_timeout=10)
        at.run()
        assert not at.exception, f"Draft page crashed: {at.exception}"
