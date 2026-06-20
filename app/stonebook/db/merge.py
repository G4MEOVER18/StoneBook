"""Manuelles/programmatisches Verschmelzen zweier Objekt-Eintraege.

Die Migration nutzt ``duplikat_gruppen.json`` und die ``image_indexer``-Pipeline,
um Duplikate automatisch zusammenzufuehren. Bei spaeter erkannten Duplikaten
(im GUI oder per Skript) braucht es dieselbe Logik im laufenden Betrieb:
Bilder umhaengen, Felder mergen, Alias eintragen, Member-Objekt loeschen.
"""
from __future__ import annotations

from stonebook.db.repository import AliasRepo, AnalysisRepo, ImageRepo, ObjectRepo

# Felder, die NIE vom Member auf den Kanon uebernommen werden: Verwaltungs-Metadaten.
_MERGE_SKIP = ("obj_id", "status", "folder_path", "erstellt_am", "geaendert_am")


def merge_into_canonical(objects: ObjectRepo, images: ImageRepo, aliases: AliasRepo,
                         member_id: str, canonical_id: str,
                         quelle: str = "manuell",
                         analyses: AnalysisRepo | None = None) -> list[str]:
    """Verschmilzt ``member_id`` in ``canonical_id``.

    Schritte (in dieser Reihenfolge, eine offene Transaktion):
      1. Felder des Members in den Kanon mergen (vorhandene Kanon-Werte bleiben).
      2. Bilder des Members auf den Kanon umhaengen (``ImageRepo.reassign``).
      3. KI-Analysen des Members auf den Kanon umhaengen
         (``AnalysisRepo.reassign``), sofern ``analyses`` uebergeben wird.
         Sonst gehen sie via ON DELETE CASCADE beim Loeschen des Members
         verloren (Default-Fallback fuer Aufrufer, die noch keinen
         AnalysisRepo durchreichen; Tests und neuer GUI-Code reichen ihn durch).
      4. ``aliases``-Eintrag (alias_id=member_id → canonical_id, Quelle=``quelle``).
      5. Das Member-Objekt loeschen.

    Liefert die Liste der Feldkonflikte (Kanon hatte abweichenden Wert; der
    Kanon-Wert bleibt). Wirft ``ValueError`` bei Selbst-Merge oder unbekannter
    Member-/Kanon-ID.
    """
    if member_id == canonical_id:
        raise ValueError(f"Selbst-Merge nicht erlaubt: {member_id}")
    member = objects.get(member_id)
    if member is None:
        raise ValueError(f"Member-Objekt {member_id} existiert nicht")
    if objects.get(canonical_id) is None:
        raise ValueError(f"Kanon-Objekt {canonical_id} existiert nicht")

    fields = {k: member[k] for k in member.keys() if k not in _MERGE_SKIP}
    conflicts = objects.merge_nonempty(canonical_id, fields)
    images.reassign(member_id, canonical_id)
    if analyses is not None:
        analyses.reassign(member_id, canonical_id)
    aliases.add(member_id, canonical_id, quelle)
    objects.delete(member_id)
    return conflicts
