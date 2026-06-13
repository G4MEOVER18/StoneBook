import json
from pathlib import Path

DUP = Path(__file__).resolve().parents[1] / "stonebook" / "migration" / "duplikat_gruppen.json"


def _groups():
    return json.loads(DUP.read_text(encoding="utf-8"))["gruppen"]


def test_gruppen_anzahl():
    groups = _groups()
    assert len(groups) == 30
    members = [m for g in groups for m in g["members"]]
    assert len(members) == 84
    assert len(set(members)) == 84  # keine Nummer doppelt
    aliases = len(members) - len(groups)
    assert aliases == 54


def test_kanonisch_ist_kleinste_nummer():
    for g in _groups():
        assert g["canonical"] == min(g["members"])


def test_einzeleintrag_39_nicht_gemergt():
    members = {m for g in _groups() for m in g["members"]}
    assert 39 not in members


def test_objekt_43_gruppe():
    g = next(g for g in _groups() if g["canonical"] == 43)
    assert g["members"] == [43, 44]
