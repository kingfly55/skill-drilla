import json
from pathlib import Path

from skill_drilla.report import generate_report


REPEATED_RUN = Path(__file__).resolve().parents[2] / "artifacts/chat-analysis/detectors/repeated_instructions/detector_run.json"
CHANGE_RUN = Path(__file__).resolve().parents[2] / "artifacts/chat-analysis/detectors/change_requests/detector_run.json"



def test_generate_report_writes_markdown_and_metadata(tmp_path: Path):
    artifacts = generate_report([REPEATED_RUN], output_dir=tmp_path)

    assert artifacts.report_path.exists()
    assert artifacts.metadata_path.exists()

    text = artifacts.report_path.read_text(encoding="utf-8")
    metadata = json.loads(artifacts.metadata_path.read_text(encoding="utf-8"))

    assert "## Scope" in text
    assert "## Findings" in text
    assert "## Caveats" in text
    assert "#### Direct user-centered evidence" in text
    assert "#### Supporting context" in text
    assert metadata["source_detector_runs"][0]["detector"] == "repeated_instructions"
    assert metadata["sections"]
    assert all("evidence_ids" in section for section in metadata["sections"])



def test_generate_report_supports_scoped_detector_selection(tmp_path: Path):
    artifacts = generate_report(
        [REPEATED_RUN, CHANGE_RUN],
        output_dir=tmp_path,
        detectors=["change_requests"],
    )
    metadata = json.loads(artifacts.metadata_path.read_text(encoding="utf-8"))

    assert metadata["report_scope"]["scoped"] is True
    assert metadata["report_scope"]["requested_detectors"] == ["change_requests"]
    assert metadata["report_scope"]["detectors"] == ["change_requests"]
    assert all(section["detector"] == "change_requests" for section in metadata["sections"])
