"""Tests for the dynamic table allow-list used by run_sql."""

from __future__ import annotations

from typing import Any

import src.action_group.tools as tools
import src.common.aws as aws


def _reset_cache() -> None:
    tools._table_names_cache = set()
    tools._table_names_fetched_at = 0.0


def _fake_glue(pages: list[list[str]]) -> Any:
    class FakeGlue:
        def __init__(self) -> None:
            self._pages = list(pages)
            self.calls = 0

        def get_tables(self, **kwargs: Any) -> dict[str, Any]:
            self.calls += 1
            page = self._pages.pop(0) if self._pages else []
            next_token = str(self.calls) if self._pages else None
            return {"TableList": [{"Name": n} for n in page], "NextToken": next_token}

    return FakeGlue()


def test_list_glue_tables_lowercases_and_paginates(monkeypatch) -> None:
    fake = _fake_glue([["AlphaTable"], ["BETA_TABLE"]])
    monkeypatch.setattr(aws, "glue", lambda: fake)

    names = tools._list_glue_tables("db")

    assert names == {"alphatable", "beta_table"}
    assert fake.calls == 2


def test_allowed_tables_caches_within_ttl(monkeypatch) -> None:
    _reset_cache()
    calls = {"n": 0}

    def fake_list(database: str) -> set[str]:
        calls["n"] += 1
        return {"credit_card_transactions"}

    monkeypatch.setattr(tools, "_list_glue_tables", fake_list)

    first = tools._allowed_tables()
    second = tools._allowed_tables()

    assert first == {"credit_card_transactions"}
    assert second == first
    assert calls["n"] == 1


def test_allowed_tables_refetches_after_ttl(monkeypatch) -> None:
    _reset_cache()
    calls = {"n": 0}

    def fake_list(database: str) -> set[str]:
        calls["n"] += 1
        return {"table_a"}

    monkeypatch.setattr(tools, "_list_glue_tables", fake_list)

    tools._allowed_tables()
    tools._table_names_fetched_at = 0.0  # force the entry to look stale
    tools._allowed_tables()

    assert calls["n"] == 2
