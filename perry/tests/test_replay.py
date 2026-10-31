"""Tests: registro de ciclos (ciclos.jsonl) y su lectura para repetir escenas."""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from grasp import Cube  # noqa: E402
from replay import cube_dict, scene_cubes, read_cycles  # noqa: E402


def test_cube_roundtrip():
    c = Cube("azul", 15.25, -1.5, 12.0)
    (back,) = scene_cubes([cube_dict(c)])
    assert (back.color, back.x, back.y, back.angle) == ("azul", 15.25, -1.5, 12.0)


def test_read_cycles_merges_decision_and_result(tmp_path):
    f = tmp_path / "ciclos.jsonl"
    f.write_text("\n".join(json.dumps(r) for r in [
        {"cycle": 1, "event": "decision", "kind": "grab", "cubes": [cube_dict(Cube("azul", 15, 0, 0))]},
        {"cycle": 1, "event": "result", "ok": False, "after": []},
    ]), encoding="utf-8")
    (c1,) = read_cycles(tmp_path)
    assert c1["kind"] == "grab" and c1["ok"] is False and len(c1["cubes"]) == 1
