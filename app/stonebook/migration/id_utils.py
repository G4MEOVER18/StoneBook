"""Normalisierung der Objekt-IDs: OBJ-001 / OBJ_0001 / 'Objekt 1' / 1 → OBJ_0001."""
import re
from pathlib import Path

# Reihenfolge ist Priorität: spezifischere/strengere Muster zuerst, damit
# allgemeinere (z.B. ``^(\d+)$``) nicht ein anderes Muster ueberschatten.
_PATTERNS = [
    # Voll qualifiziert mit Separator: ``OBJ-001``, ``OBJ_0001``, ``obj-43``,
    # sowie mit Punkt-/Whitespace-Separator ``OBJ.43``, ``OBJ 43``, ``OBJ. 43``.
    # Sammler-Notizen und Dateinamen in Freitext verwenden neben Bindestrich/
    # Unterstrich haeufig Punkt und Whitespace (Windows-Explorer-Umbenennungen,
    # OCR-Scan-Ergebnisse, handschriftliche Katalog-Eintraege) - alle vier
    # semantisch identisch als "OBJ + Trenner + Nummer".
    re.compile(r"^OBJ[-_.\s]+(\d+)$", re.IGNORECASE),
    # Kompaktform ohne Separator: ``OBJ001``, ``obj43`` -- verbreitet in
    # Datei-/Ordnernamen, in denen ``-``/``_`` weggelassen wird.
    re.compile(r"^OBJ(\d+)$", re.IGNORECASE),
    # Deutsche Langform mit Whitespace: ``Objekt 7``.
    re.compile(r"^Objekt\s+(\d+)$", re.IGNORECASE),
    # Englische Langform (Foto-Captions / EN-Notizen): ``Object 43``.
    re.compile(r"^Object\s+(\d+)$", re.IGNORECASE),
    # DE-Nummerierungs-Praefix: ``Nr. 43`` / ``Nr 43`` / ``Nr.43`` (Kurzform) und
    # ``Nummer 43`` / ``Nummer43`` (ausgeschriebene Vollform, verbreitet in
    # handschriftlichen Katalog-Eintraegen und in Kaufbelegen, in denen die
    # Kurzform vermieden wird). ``N(?:umme)?r`` spiegelt strukturell die
    # Inv(?:entar)?-/Kat(?:alog)?-Konvention der Museums-Praefixe unten.
    re.compile(r"^N(?:umme)?r\.?\s*(\d+)$", re.IGNORECASE),
    # Museums-Inventar-Nummer: ``Inv.-Nr. 43`` / ``Inv. Nr. 43`` / ``InvNr 43`` /
    # ``Inv-Nr. 43`` / ``Inventarnummer 43`` / ``Inventar-Nr. 43``. Standard-Praefix
    # auf DE-sprachigen Museums-Etiketten (Naturhistorisches Museum Wien, Museum
    # fuer Naturkunde Berlin, Senckenberg Frankfurt, TU Bergakademie Freiberg)
    # und in Sammler-Notizen, die aus Museums-Katalogen abgeschrieben wurden.
    # ``Inv(?:entar)?`` mit optionalem Punkt und beliebigem Trenner (``-``/``.``
    # /Whitespace) zu ``N(?:umme)?r`` mit optionalem Punkt, dann Ziffer nach
    # optionalem Whitespace. Deckt Kurz- (``Inv``, ``Nr``) und ausgeschriebene
    # Vollform (``Inventar``, ``Nummer``) sowie alle Trenner-Kombinationen ab.
    # Der obligatorische ``N(?:umme)?r``-Marker verhindert falsche Positives fuer
    # bare ``Inv 43`` oder andere ``Inv``-startende Woerter (``Invasion``,
    # ``Invalid``).
    re.compile(r"^Inv(?:entar)?\.?[-.\s]*N(?:umme)?r\.?\s*(\d+)$", re.IGNORECASE),
    # Museums-/Sammler-Katalognummer: ``Kat.-Nr. 43`` / ``Kat. Nr. 43`` / ``KatNr 43`` /
    # ``Kat-Nr. 43`` / ``Katalognummer 43`` / ``Katalog-Nr. 43``. Parallel-Standard zur
    # Inventarnummer-Form, die den logischen Katalog-Eintrag (statt der physischen
    # Inventar-Position) identifiziert - verbreitet auf DE-sprachigen Museums-Etiketten
    # (Naturhistorisches Museum Basel/Bern, Deutsches Bergbau-Museum Bochum, Bayerische
    # Staatssammlung fuer Palaeontologie und Geologie) und in publizierten Sammlungs-
    # Katalogen (Mineralogische Zeitschriften mit Kat.-Nr.-Referenz-Notation). Sammler-
    # Notizen aus Museums-Besuchen und Publikations-Referenzen uebernehmen die Notation
    # woertlich; ohne diese Praefix-Erkennung faellt der ``--ids-from-file``-Import
    # solcher Listen still auf None. Regex spiegelt die Inventarnummer-Regex strukturell:
    # ``Kat(?:alog)?`` mit optionalem Punkt, beliebiger Trenner-Kombination (``-``/``.``
    # /Whitespace), dann obligatorischer ``N(?:umme)?r``-Marker (verhindert falsche
    # Positives fuer bare ``Kat 43`` oder andere ``Kat``-startende Woerter wie
    # ``Kategorie``, ``Katalyse``, ``Kathedrale``, ``Katze``).
    re.compile(r"^Kat(?:alog)?\.?[-.\s]*N(?:umme)?r\.?\s*(\d+)$", re.IGNORECASE),
    # Mineralogische Fundnummer: ``Fund-Nr. 43`` / ``Fund. Nr. 43`` / ``FundNr 43`` /
    # ``Fund-Nr 43`` / ``Fundnummer 43`` / ``Fund. Nummer 43``. Domaenen-spezifisches
    # Nummerierungs-Praefix fuer Mineralien-/Gesteins-Sammlungen: die Fundnummer
    # identifiziert einen Fund-Event (Datum + Ort + Sammler + Objekt) und ist in
    # DE-sprachigen Sammler-Notizen aus Feldkampagnen, in Vereinszeitschriften der
    # Mineralien-Vereine (VFMG, MVSK/Mineralien-Verein Schweiz und Kanton, Aufschluss
    # der Mineralogischen Gesellschaft), in Gel-/Bohrkern-Protokollen der
    # Bergakademien und in Foto-Captions von Fundstellen-Bildern (``Fund-Nr. 43,
    # Val Bavona, 2024-07-14``) verbreitet. Waehrend ``Inv.-Nr.`` (323cfff) die
    # Museums-physische Inventar-Position und ``Kat.-Nr.`` (be56257) den logischen
    # Katalog-Eintrag identifiziert, referenziert ``Fund-Nr.`` das Sammel-Ereignis
    # in einem privaten Sammlungs-Kontext; die drei Achsen koexistieren auf
    # denselben Objekten (Museums-Uebernahmen aus Privatsammlungen tragen alle
    # drei Nummern parallel). Bisher fielen alle Fund-Nr.-Formen still auf None,
    # weil das Regex-Set keinen ``Fund``-startenden Praefix kannte - der Sammler-
    # Workflow "Feld-Notiz-Nummer auf Foto uebertragen, mit --ids-from-file
    # importieren" scheitert mit ``Ungueltige Objekt-ID: 'Fund-Nr. 43'``.
    # Strukturell spiegelbildlich zur Inv-/Kat-Regex (``Fund\.?`` mit optionalem
    # Punkt, beliebige Trenner-Kombination [-.\s]* zwischen Fund- und Nr-Teil,
    # obligatorischer ``N(?:umme)?r``-Marker als Disambiguierungs-Klammer,
    # optionaler Punkt nach Nr, optionaler Whitespace vor Ziffer). Der Nr-Marker
    # verhindert falsche Positives fuer bare ``Fund 43`` (in Prosa mehrdeutig zu
    # "das ist der 43. Fund") und fuer die haeufigen Fund-startenden Kompositum-
    # Woerter des Sammler-Vokabulars (``Fundort``, ``Fundstelle``, ``Fundgebiet``,
    # ``Fundstaette``, ``Fundament``, ``Fundamental``, ``Fundus``).
    re.compile(r"^Fund\.?[-.\s]*N(?:umme)?r\.?\s*(\d+)$", re.IGNORECASE),
    # Internationale Nummerierungs-Praefixe (semantisch identisch zur DE-Form ``Nr.``):
    # ``No. 43`` / ``No 43`` / ``No.43`` als EN-Standard (auch in DE-sprachigen Sammler-Notizen
    # verbreitet aus EN-uebersetzten Etiketten und Auktionskatalogen), ``N° 43`` mit Grad-Zeichen
    # U+00B0 (FR-/internationale Zeitschriften-Tradition), ``Nº 43`` mit maskulinem Ordinal-
    # Zeichen U+00BA (PT-/ES-Standard), ``№ 43`` mit Unicode-Numero-Zeichen U+2116 (Norm-Zeichen
    # nach ISO 8859-5 und in russisch-/serbisch-/bulgarisch-sprachigen Etiketten verbreitet).
    re.compile(r"^No\.?\s*(\d+)$", re.IGNORECASE),
    re.compile(r"^N[°º]\s*(\d+)$", re.IGNORECASE),
    re.compile(r"^№\s*(\d+)$"),
    # Hash-Praefix (Foto-/Tagebuch-Notizen): ``#43`` / ``# 43``.
    re.compile(r"^#\s*(\d+)$"),
    # Reine Zahl: ``43``.
    re.compile(r"^(\d+)$"),
]


def normalize_id(raw) -> str | None:
    if raw is None:
        return None
    if isinstance(raw, int):
        return f"OBJ_{raw:04d}" if raw > 0 else None
    text = str(raw).strip()
    for pat in _PATTERNS:
        m = pat.match(text)
        if m:
            return f"OBJ_{int(m.group(1)):04d}"
    return None


def obj_number(obj_id: str) -> int:
    return int(obj_id.split("_")[1])


def display_name(obj_id: str) -> str:
    return f"Objekt {obj_number(obj_id)}"


def read_ids_from_file(path: Path) -> list[str] | None:
    """Liest eine ID-Liste aus einer Textdatei (eine ID pro Zeile).

    ``#``-Kommentarzeilen (auch mit fuehrendem Whitespace) und Leerzeilen
    werden uebergangen; Inline-Kommentare nach ``#`` werden gestrippt.
    Ein ``#`` am Zeilenanfang gilt als Kommentar-Marker, sodass die Hash-
    Praefix-ID-Form ``#43`` bewusst nicht erkannt wird - diese Form ist
    ein Freitext-Notation-Idiom und in einer ID-Datei mehrdeutig zum
    Kommentar-Marker; per :func:`normalize_id` gilt sie nur inline.

    Rohwerte werden NICHT normalisiert - das uebernimmt der Aufrufer
    einheitlich mit den positionalen IDs via :func:`normalize_id`, damit
    dieselbe Fehlermeldung fliesst.

    Das Encoding ``utf-8-sig`` strippt einen optionalen fuehrenden UTF-8-
    BOM (``EF BB BF``, U+FEFF) transparent, ohne die uebrige UTF-8-
    Semantik zu aendern (Dateien ohne BOM werden identisch gelesen wie
    mit reinem ``utf-8``). Notwendig, weil Windows-Notepad, VS Code mit
    Default-Encoding auf Windows und Excel-Text-Export standardmaessig
    ein BOM voranstellen - ohne den Strip wuerde das erste Zeichen der
    ersten ID zum U+FEFF-Praefix und :func:`normalize_id` liefert None,
    sodass der Sammler-Workflow "IDs in Notepad tippen, speichern,
    --ids-from-file uebergeben" mit einer kryptischen "Ungueltige
    Objekt-ID: '﻿OBJ_0001'"-Meldung crasht statt die Liste
    einzulesen. Nicht-UTF-8-Dateien (z.B. Excel-CSV-Export mit UTF-16-
    LE-BOM oder cp1252-Fallback) loesen weiterhin ``UnicodeDecodeError``
    aus, was auf ``None`` faellt - das Verhalten aendert sich nur fuer
    den BOM-only-Fall (vorher: erste ID unlesbar; nachher: erste ID
    korrekt).

    Rueckgabe:
        Liste der rohen ID-Strings (in Datei-Reihenfolge), oder ``None``
        wenn die Datei fehlt / nicht als UTF-8 lesbar ist. Der Aufrufer
        entscheidet ueber die Fehlermeldung.
    """
    try:
        raw = path.read_text(encoding="utf-8-sig")
    except (OSError, UnicodeDecodeError):
        return None
    ids: list[str] = []
    for line in raw.splitlines():
        hash_pos = line.find("#")
        if hash_pos > 0:
            line = line[:hash_pos]
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        ids.append(stripped)
    return ids
