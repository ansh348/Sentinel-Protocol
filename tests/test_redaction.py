"""Traces are the publishable artifact (FSE artifact evaluation): credentials
must never appear in runs/*.jsonl. The TraceWriter guard fails loud."""
from __future__ import annotations

import pytest

from trace import TraceWriter, read_trace


def test_trace_refuses_credential_material(tmp_path):
    writer = TraceWriter(tmp_path / "t.jsonl", run_id="r", seed=1, system="S5",
                         task_id="a1")
    with pytest.raises(ValueError, match="credential-like"):
        writer.emit(actor="x", event_type="error",
                    payload={"oops": "sk-ant-oat01-AAAAAAAAAAAAAAAAAAAAAAAA"})
    # nested occurrences are caught too (the serialized line is scanned)
    with pytest.raises(ValueError, match="credential-like"):
        writer.emit(actor="x", event_type="error",
                    payload={"deep": {"argv": ["--x", "sk-ant-api03-BBBBBBBBBBBBBBBBBB"]}})
    writer.close()
    assert read_trace(tmp_path / "t.jsonl") == [], "refused events must not be written"


def test_trace_allows_world_tokens(tmp_path):
    writer = TraceWriter(tmp_path / "t.jsonl", run_id="r", seed=1, system="S5",
                         task_id="a1")
    writer.emit(actor="w1", event_type="tool_call",
                payload={"headers_redacted": True, "token": "tok_268e2d8ff5dd75a1"})
    writer.close()
    assert len(read_trace(tmp_path / "t.jsonl")) == 1
