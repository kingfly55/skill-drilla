import tracemalloc
from pathlib import Path

from skill_drilla.parse.jsonl_stream import stream_jsonl_records


def test_streaming_parser_stays_within_bounded_peak_memory(tmp_path: Path):
    transcript = tmp_path / "large.jsonl"
    line = '{"type":"user","message":{"role":"user","content":"x"}}\n'
    transcript.write_text(line * 50000, encoding="utf-8")

    tracemalloc.start()
    count = 0
    for record in stream_jsonl_records(transcript):
        assert record.status == "parsed"
        count += 1
    current, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()

    assert count == 50000
    assert peak < 2_000_000, f"peak memory too high: {peak}"
