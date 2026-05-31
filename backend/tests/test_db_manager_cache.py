"""Unit tests for db_manager in-memory cache, profile/portfolio reads, and the
market-cache Firestore helpers. Firestore is replaced with MagicMock; the
``db is None`` safety paths are exercised explicitly."""
import datetime
from unittest.mock import MagicMock

import db_manager


# ---------------------------------------------------------------------------
# clear_cache_for_uid
# ---------------------------------------------------------------------------

def test_clear_cache_for_uid_removes_both_caches():
    db_manager._family_profile_cache["u1"] = ({"a": 1}, 999999999999)
    db_manager._processed_portfolio_cache["u1"] = ({"b": 2}, 999999999999)

    db_manager.clear_cache_for_uid("u1")

    assert "u1" not in db_manager._family_profile_cache
    assert "u1" not in db_manager._processed_portfolio_cache


def test_clear_cache_for_uid_is_noop_for_unknown_uid():
    # Should not raise even when nothing is cached
    db_manager.clear_cache_for_uid("never-seen")


# ---------------------------------------------------------------------------
# get_family_profile — cache + db None
# ---------------------------------------------------------------------------

def test_get_family_profile_returns_fresh_cache_without_hitting_db(monkeypatch):
    sentinel = {"financial_profile": {"x": 1}}
    now = db_manager.time.time()
    db_manager._family_profile_cache["cached-uid"] = (sentinel, now)

    # If the cache is honored, db is never touched — make db blow up if used.
    boom = MagicMock()
    boom.collection.side_effect = AssertionError("db must not be hit on cache HIT")
    monkeypatch.setattr(db_manager, "db", boom)

    result = db_manager.get_family_profile("cached-uid")
    assert result is sentinel


def test_get_family_profile_returns_none_when_db_unavailable(monkeypatch):
    db_manager._family_profile_cache.pop("no-db-uid", None)
    monkeypatch.setattr(db_manager, "db", None)
    assert db_manager.get_family_profile("no-db-uid") is None


def test_get_family_profile_returns_none_when_doc_missing(monkeypatch):
    db_manager._family_profile_cache.pop("missing-uid", None)
    fake_db = MagicMock()
    doc = MagicMock()
    doc.exists = False
    fake_db.collection.return_value.document.return_value.get.return_value = doc
    monkeypatch.setattr(db_manager, "db", fake_db)

    assert db_manager.get_family_profile("missing-uid") is None


# ---------------------------------------------------------------------------
# get_processed_portfolio — db None
# ---------------------------------------------------------------------------

def test_get_processed_portfolio_returns_none_when_db_unavailable(monkeypatch):
    db_manager._processed_portfolio_cache.pop("u", None)
    monkeypatch.setattr(db_manager, "db", None)
    assert db_manager.get_processed_portfolio("u") is None


# ---------------------------------------------------------------------------
# save_market_cache
# ---------------------------------------------------------------------------

def test_save_market_cache_returns_false_when_db_unavailable(monkeypatch):
    monkeypatch.setattr(db_manager, "db", None)
    assert db_manager.save_market_cache("track", [{"x": 1}]) is False


def test_save_market_cache_writes_competitors_and_timestamp(monkeypatch):
    fake_db = MagicMock()
    doc_ref = fake_db.collection.return_value.document.return_value
    monkeypatch.setattr(db_manager, "db", fake_db)

    data = [{"provider_name": "הראל"}]
    assert db_manager.save_market_cache("מסלול כללי", data) is True

    fake_db.collection.assert_called_with("market_cache")
    fake_db.collection.return_value.document.assert_called_with("מסלול כללי")
    written = doc_ref.set.call_args.args[0]
    assert written["competitors"] == data
    assert "last_updated" in written


# ---------------------------------------------------------------------------
# get_market_cache
# ---------------------------------------------------------------------------

def test_get_market_cache_returns_none_when_db_unavailable(monkeypatch):
    monkeypatch.setattr(db_manager, "db", None)
    assert db_manager.get_market_cache("track") is None


def test_get_market_cache_returns_none_on_miss(monkeypatch):
    fake_db = MagicMock()
    doc = MagicMock()
    doc.exists = False
    fake_db.collection.return_value.document.return_value.get.return_value = doc
    monkeypatch.setattr(db_manager, "db", fake_db)
    assert db_manager.get_market_cache("track") is None


def test_get_market_cache_returns_fresh_competitors(monkeypatch):
    fake_db = MagicMock()
    doc = MagicMock()
    doc.exists = True
    recent = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(days=2)
    competitors = [{"provider_name": "מיטב"}]
    doc.to_dict.return_value = {"competitors": competitors, "last_updated": recent}
    fake_db.collection.return_value.document.return_value.get.return_value = doc
    monkeypatch.setattr(db_manager, "db", fake_db)

    assert db_manager.get_market_cache("track") == competitors


def test_get_market_cache_returns_none_when_stale(monkeypatch):
    fake_db = MagicMock()
    doc = MagicMock()
    doc.exists = True
    stale = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(days=40)
    doc.to_dict.return_value = {"competitors": [{"x": 1}], "last_updated": stale}
    fake_db.collection.return_value.document.return_value.get.return_value = doc
    monkeypatch.setattr(db_manager, "db", fake_db)

    assert db_manager.get_market_cache("track") is None
