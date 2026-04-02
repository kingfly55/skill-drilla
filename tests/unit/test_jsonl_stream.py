from pathlib import Path

from skill_drilla.parse.jsonl_stream import stream_jsonl_records


FIXTURE = Path("tests/fixtures/parse/sample_session.jsonl")


def test_stream_jsonl_records_yields_line_level_statuses():
    records = list(stream_jsonl_records(FIXTURE))

    assert [record.line_number for record in records] == [1, 2, 3, 4, 5, 6]
    assert [record.status for record in records] == [
        "parsed",
        "parsed",
        "parsed",
        "invalid_json",
        "non_object",
        "blank",
    ]
    assert records[0].record["type"] == "user"
    assert records[3].error is not None
    assert records[4].error == "expected JSON object, got list"


def test_stream_jsonl_records_consumes_custom_iterator_without_read():
    class GuardedFile:
        def __init__(self) -> None:
            self.lines = iter(['{"type":"user"}\n', '{"type":"assistant"}\n'])

        def __iter__(self):
            return self

        def __next__(self):
            return next(self.lines)

        def read(self, *args, **kwargs):  # pragma: no cover - should never be called
            raise AssertionError("stream parser must not call read()")

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

    class GuardedPath:
        def open(self, *args, **kwargs):
            return GuardedFile()

    records = list(stream_jsonl_records(GuardedPath()))
    assert [record.status for record in records] == ["parsed", "parsed"]
    assert records[1].record["type"] == "assistant"
