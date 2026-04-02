import json
from pathlib import Path

from skill_drilla.config import dump_effective_config, load_config


def test_load_config_normalizes_expected_defaults():
    cfg = load_config(Path("configs/chat-analysis.default.yaml"))
    assert cfg.data["project"]["name"] == "chat-analysis"
    assert cfg.data["scope"]["include_subagents"] is False
    assert cfg.input_scope["label"] == "default-local"
    assert len(cfg.fingerprint) == 64


def test_dump_effective_config_emits_json_object():
    cfg = load_config(Path("configs/chat-analysis.default.yaml"))
    payload = json.loads(dump_effective_config(cfg))
    assert payload["meta"]["config_fingerprint"] == cfg.fingerprint
    assert payload["paths"]["artifact_root"] == "artifacts/chat-analysis"
