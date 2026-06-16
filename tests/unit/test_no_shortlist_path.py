"""Guard against re-introducing the dead `lakebase.shortlists` path.

The shortlists table was scaffolded but never wired to UI/services. We
removed it cleanly in the cleanup pass; this test fails loudly if it
sneaks back in via a future paste.
"""

from __future__ import annotations

from pathlib import Path

REPO = Path(__file__).resolve().parents[2]


def test_no_shortlist_table_in_lakebase_schema():
    schema_sql = (REPO / "sql" / "lakebase" / "schema.sql").read_text()
    assert "shortlists" not in schema_sql.lower(), (
        "lakebase.shortlists DDL has come back; if reintroduced, also wire "
        "service methods + a UI surface, or update this test."
    )


def test_no_shortlist_method_in_lakebase_service():
    svc = (REPO / "app" / "services" / "lakebase.py").read_text()
    assert "shortlist" not in svc.lower(), (
        "Found a 'shortlist' reference in app/services/lakebase.py — wire "
        "the corresponding UI or remove the dead path."
    )


def test_setup_uc_script_does_not_create_shortlists():
    setup = (REPO / "scripts" / "setup_uc.sh").read_text()
    assert "shortlists" not in setup, (
        "scripts/setup_uc.sh still creates lakebase.shortlists. If you're "
        "re-introducing it, also wire service methods and a UI surface."
    )
