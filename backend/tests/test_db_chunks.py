"""Unit tests for db_manager insurance-chunk subcollection helpers."""
from unittest.mock import MagicMock

import db_manager


def _wire_subcollection(monkeypatch, subcol):
    """Patch db_manager.db so that the families/{uid}/insurance_chunks chain returns subcol."""
    fake_db = MagicMock()
    fake_db.collection.return_value.document.return_value.collection.return_value = subcol
    monkeypatch.setattr(db_manager, "db", fake_db)
    return fake_db


def test_save_policy_chunks_deletes_old_chunks_then_writes_new(monkeypatch):
    old_a = MagicMock()
    old_b = MagicMock()
    subcol = MagicMock()
    subcol.where.return_value.stream.return_value = [old_a, old_b]
    _wire_subcollection(monkeypatch, subcol)

    chunks = [
        {
            "chunk_id": "p_0",
            "text": "first",
            "anchor": "first",
            "embedding": [0.1, 0.2],
            "policy_id": "p",
            "source_doc": "policy.pdf",
        },
        {
            "chunk_id": "p_1",
            "text": "second",
            "anchor": "second",
            "embedding": [0.3, 0.4],
            "policy_id": "p",
            "source_doc": "policy.pdf",
        },
    ]

    result = db_manager.save_policy_chunks("uid_abc", "p", chunks)

    assert result is True
    # Dedup query and deletions
    subcol.where.assert_called_with("policy_id", "==", "p")
    assert old_a.reference.delete.called
    assert old_b.reference.delete.called
    # Two writes, one per chunk_id
    doc_ids = [call.args[0] for call in subcol.document.call_args_list]
    assert "p_0" in doc_ids
    assert "p_1" in doc_ids
    # The payload includes the five fields and excludes chunk_id (it's the doc id)
    set_payloads = [
        call.args[0] for call in subcol.document.return_value.set.call_args_list
    ]
    for payload in set_payloads:
        assert set(payload.keys()) == {
            "text",
            "anchor",
            "embedding",
            "policy_id",
            "source_doc",
        }


def test_save_policy_chunks_returns_false_when_db_unavailable(monkeypatch):
    monkeypatch.setattr(db_manager, "db", None)
    assert db_manager.save_policy_chunks("uid", "p", []) is False


def test_get_insurance_chunks_returns_dict_per_doc(monkeypatch):
    doc_a = MagicMock()
    doc_a.to_dict.return_value = {
        "text": "A",
        "anchor": "A",
        "embedding": [0.1],
        "policy_id": "p",
        "source_doc": "x.pdf",
    }
    doc_b = MagicMock()
    doc_b.to_dict.return_value = {
        "text": "B",
        "anchor": "B",
        "embedding": [0.2],
        "policy_id": "p",
        "source_doc": "x.pdf",
    }
    subcol = MagicMock()
    subcol.stream.return_value = [doc_a, doc_b]
    _wire_subcollection(monkeypatch, subcol)

    result = db_manager.get_insurance_chunks("uid_abc")

    assert result == [doc_a.to_dict.return_value, doc_b.to_dict.return_value]


def test_get_insurance_chunks_returns_empty_when_db_unavailable(monkeypatch):
    monkeypatch.setattr(db_manager, "db", None)
    assert db_manager.get_insurance_chunks("uid") == []
