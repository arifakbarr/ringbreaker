import json
from pathlib import Path

from ringbreaker.hub.proof import load_proof, proof_summary

RESULTS = Path(__file__).resolve().parents[2] / "results" / "results.json"


def test_proof_copies_harness_numbers_verbatim():
    raw = json.loads(RESULTS.read_text(encoding="utf-8"))
    proof = proof_summary(raw)
    e_a = raw["experiments"]["E-A"]
    assert proof["scoreboard"]["stopped_myr"]["mean"] == e_a["stopped_myr"]["mean"]
    assert proof["scoreboard"]["time_to_detect_s"]["n"] == e_a["time_to_detect_s"]["n"]
    assert proof["config_hash"] == raw["config_hash"]
    assert proof["in_our_simulation"] is True


def test_proof_handles_missing_experiments():
    proof = proof_summary({})
    assert proof["scoreboard"]["stopped_myr"] is None
    assert proof["network_effect"] == []


def test_load_proof_missing_file(tmp_path):
    assert load_proof(tmp_path / "nope.json")["available"] is False
