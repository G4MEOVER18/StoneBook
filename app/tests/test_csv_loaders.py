from pathlib import Path

import pytest

from stonebook.fields import is_empty
from stonebook.migration import csv_loaders
from stonebook.migration.id_utils import (
    display_name,
    normalize_id,
    read_ids_from_file,
)

REPO = Path(__file__).resolve().parents[2]
CSV_DIR = REPO / "data" / "csv"


def test_is_empty():
    assert is_empty(None)
    assert is_empty("")
    assert is_empty("   ")
    assert not is_empty("x")
    assert not is_empty(0)        # 0 ist ein gültiger Wert
    assert not is_empty(0.0)
    assert not is_empty(False)


def test_normalize_id():
    assert normalize_id("OBJ-001") == "OBJ_0001"
    assert normalize_id("OBJ_0043") == "OBJ_0043"
    assert normalize_id("Objekt 7") == "OBJ_0007"
    assert normalize_id(43) == "OBJ_0043"
    assert normalize_id("") is None
    assert normalize_id("Quatsch") is None
    assert display_name("OBJ_0043") == "Objekt 43"


def test_normalize_id_kompaktform_und_alternative_praefixe():
    """OBJ ohne Separator, EN-Langform, Nummer-/Hash-Praefix - in Dateinamen/Captions verbreitet."""
    # Kompaktform OBJ + Ziffern ohne Separator (Datei-/Ordnernamen)
    assert normalize_id("OBJ43") == "OBJ_0043"
    assert normalize_id("OBJ001") == "OBJ_0001"
    assert normalize_id("obj43") == "OBJ_0043"
    # Englische Langform (Foto-Captions / EN-Notizen)
    assert normalize_id("Object 43") == "OBJ_0043"
    assert normalize_id("object 7") == "OBJ_0007"
    # DE Nummerierungs-Praefix
    assert normalize_id("Nr. 43") == "OBJ_0043"
    assert normalize_id("Nr 43") == "OBJ_0043"
    assert normalize_id("Nr.43") == "OBJ_0043"
    assert normalize_id("nr. 7") == "OBJ_0007"
    # Hash-Praefix (Tagebuch-/Foto-Notation)
    assert normalize_id("#43") == "OBJ_0043"
    assert normalize_id("# 43") == "OBJ_0043"
    # Bestehende Formate weiterhin gueltig (kein Regress)
    assert normalize_id("OBJ-001") == "OBJ_0001"
    assert normalize_id("OBJ_0043") == "OBJ_0043"
    assert normalize_id("Objekt 7") == "OBJ_0007"
    # Ungueltige Formen bleiben None
    assert normalize_id("OBJ X43") is None
    assert normalize_id("OBJ-43X") is None
    assert normalize_id("Objekt001") is None  # DE-Langform braucht Whitespace
    assert normalize_id("Object43") is None   # EN-Langform braucht Whitespace
    assert normalize_id("OBJEKT43") is None   # 'EKT' zwischen Buchstaben und Zahl


def test_normalize_id_punkt_und_whitespace_separator():
    """OBJ + Punkt/Whitespace als Trenner - Sammler-Notation und Datei-/Ordnernamen.

    Waehrend Bindestrich und Unterstrich als Separator bereits abgedeckt sind
    (``OBJ-43``/``OBJ_43``), verwenden Sammler-Notizen in Freitext und
    Windows-Explorer-Umbenennungen haeufig auch Punkt und Whitespace als
    natuerlichen Trenner (``OBJ.43``, ``OBJ 43``, ``OBJ. 43``); vorher fielen
    alle vier Formen silent auf None, obwohl semantisch identisch zur
    Bindestrich-/Unterstrich-Variante.
    """
    # Whitespace als Trenner
    assert normalize_id("OBJ 43") == "OBJ_0043"
    assert normalize_id("obj 7") == "OBJ_0007"
    assert normalize_id("OBJ 001") == "OBJ_0001"
    # Mehrere Whitespaces (Copy-Paste-Artefakt)
    assert normalize_id("OBJ  43") == "OBJ_0043"
    # Punkt als Trenner
    assert normalize_id("OBJ.43") == "OBJ_0043"
    assert normalize_id("OBJ.001") == "OBJ_0001"
    assert normalize_id("obj.7") == "OBJ_0007"
    # Punkt + Whitespace (Prosa-Freitext-Notation)
    assert normalize_id("OBJ. 43") == "OBJ_0043"
    assert normalize_id("OBJ .43") == "OBJ_0043"
    # Regress: existierende Trenner-Formen bleiben gueltig
    assert normalize_id("OBJ-43") == "OBJ_0043"
    assert normalize_id("OBJ_43") == "OBJ_0043"
    assert normalize_id("OBJ43") == "OBJ_0043"
    # Ungueltige Formen bleiben None (keine schwache Aufweichung)
    assert normalize_id("OBJEKT43") is None
    assert normalize_id("OBJ X43") is None
    assert normalize_id("OBJ.43X") is None
    assert normalize_id("OBJ 43 44") is None


def test_normalize_id_internationale_nummer_praefixe():
    """Internationale Nummerierungs-Praefixe (EN ``No.``, FR/PT/ES ``N°``/``Nº``, Unicode ``№``).

    Waehrend die DE-Form ``Nr. 43`` bereits abgedeckt ist, verwenden mehrsprachige
    Sammler-Notizen, EN-uebersetzte Etiketten aus Auktionskatalogen und Museums-
    Etiketten aus dem franzoesisch-/portugiesisch-/spanisch-/russisch-sprachigen
    Raum die semantisch identischen internationalen Varianten:

    * ``No.`` mit optionalem Punkt (EN-Standard, auch in DE-sprachiger Community
      aus EN-Uebersetzungen praesent),
    * ``N°`` mit Grad-Zeichen U+00B0 (FR-/internationale Zeitschriften-Tradition),
    * ``Nº`` mit maskulinem Ordinal-Zeichen U+00BA (PT-/ES-Standard),
    * ``№`` mit Unicode-Numero-Zeichen U+2116 (Norm-Zeichen, russisch-/serbisch-/
      bulgarisch-sprachige Etiketten).

    Bisher fielen alle vier Formen still auf None, obwohl semantisch identisch zur
    DE-Nummerierungs-Praefix-Form.
    """
    # EN "No." mit/ohne Punkt und Whitespace (Analog zur DE Nr.-Form)
    assert normalize_id("No. 43") == "OBJ_0043"
    assert normalize_id("No 43") == "OBJ_0043"
    assert normalize_id("No.43") == "OBJ_0043"
    assert normalize_id("no. 7") == "OBJ_0007"
    assert normalize_id("NO. 43") == "OBJ_0043"
    # FR/international mit Grad-Zeichen U+00B0
    assert normalize_id("N° 43") == "OBJ_0043"
    assert normalize_id("N°43") == "OBJ_0043"
    assert normalize_id("n° 7") == "OBJ_0007"
    # PT/ES mit maskulinem Ordinal-Zeichen U+00BA
    assert normalize_id("Nº 43") == "OBJ_0043"
    assert normalize_id("Nº43") == "OBJ_0043"
    assert normalize_id("nº 7") == "OBJ_0007"
    # Unicode-Numero-Zeichen U+2116 (standalone, ohne fuehrendes N)
    assert normalize_id("№ 43") == "OBJ_0043"
    assert normalize_id("№43") == "OBJ_0043"
    assert normalize_id("№ 7") == "OBJ_0007"
    # Regress: bestehende DE-Form bleibt gueltig
    assert normalize_id("Nr. 43") == "OBJ_0043"
    assert normalize_id("Nr 43") == "OBJ_0043"
    assert normalize_id("Nr.43") == "OBJ_0043"
    # Ungueltige Formen bleiben None
    assert normalize_id("No. 43X") is None
    assert normalize_id("N° 43 44") is None
    assert normalize_id("N 43") is None  # blosses N ohne °/º/Wortzusatz
    assert normalize_id("Nox 43") is None


def test_normalize_id_inventar_nummer_praefix():
    """Museums-Inventarnummer ``Inv.-Nr.`` und Varianten - Standard auf DE-Museums-Etiketten.

    Naturhistorisches Museum Wien, Museum fuer Naturkunde Berlin, Senckenberg
    Frankfurt, TU Bergakademie Freiberg und weitere DE-sprachige Sammlungen
    fuehren jeden Objekt-Eintrag mit ``Inv.-Nr.`` / ``Inv. Nr.`` / ``Inventar-
    Nr.`` / ``Inventarnummer``. Sammler-Notizen aus Museums-Katalogen und
    Ausstellungs-Beschriftungen uebernehmen die Notation woertlich; ohne diese
    Praefix-Erkennung faellt der ``--ids-from-file``-Import solcher Listen
    still auf None und wirft ``Ungueltige Objekt-ID: 'Inv.-Nr. 43'``.
    """
    # Standard-Formen mit unterschiedlichen Trenner-Kombinationen
    assert normalize_id("Inv.-Nr. 43") == "OBJ_0043"
    assert normalize_id("Inv. Nr. 43") == "OBJ_0043"
    assert normalize_id("Inv Nr. 43") == "OBJ_0043"
    assert normalize_id("Inv-Nr. 43") == "OBJ_0043"
    assert normalize_id("Inv-Nr 43") == "OBJ_0043"
    assert normalize_id("InvNr 43") == "OBJ_0043"
    assert normalize_id("InvNr43") == "OBJ_0043"
    assert normalize_id("Inv.Nr.43") == "OBJ_0043"
    # Ausgeschriebene Form ``Inventar`` und ``Nummer``
    assert normalize_id("Inventar-Nr. 43") == "OBJ_0043"
    assert normalize_id("Inventar Nr. 43") == "OBJ_0043"
    assert normalize_id("Inventarnummer 43") == "OBJ_0043"
    assert normalize_id("Inventarnummer43") == "OBJ_0043"
    assert normalize_id("Inv. Nummer 43") == "OBJ_0043"
    # Case-Insensitivitaet
    assert normalize_id("inv-nr 7") == "OBJ_0007"
    assert normalize_id("INV-NR. 001") == "OBJ_0001"
    assert normalize_id("inventarnummer 7") == "OBJ_0007"
    # Ungueltig: ohne Nummer-Marker, mit Suffix-Ballast, oder falsches Wort
    assert normalize_id("Inv 43") is None            # ohne Nr/Nummer nicht eindeutig
    assert normalize_id("Inventar 43") is None       # ohne Nummer-Marker
    assert normalize_id("Inv.-Nr. 43X") is None      # Suffix-Ballast
    assert normalize_id("Invasion 43") is None       # anderes Wort mit Inv-Praefix
    assert normalize_id("Invalid 43") is None
    assert normalize_id("Inv-Nr 43 44") is None      # Doppel-Zahl
    # Regressionsschutz: bestehende Formen bleiben gueltig
    assert normalize_id("OBJ-001") == "OBJ_0001"
    assert normalize_id("Nr. 43") == "OBJ_0043"
    assert normalize_id("No. 43") == "OBJ_0043"
    assert normalize_id("Objekt 7") == "OBJ_0007"
    assert normalize_id("#43") == "OBJ_0043"


def test_normalize_id_katalog_nummer_praefix():
    """Museums-Katalognummer ``Kat.-Nr.`` und Varianten - Standard-Praefix parallel zur Inventarnummer.

    Waehrend ``Inv.-Nr.`` (323cfff) die physische Inventar-Position identifiziert,
    referenziert ``Kat.-Nr.`` den logischen Katalog-Eintrag - beide Praefixe koexistieren
    auf denselben DE-sprachigen Museums-Etiketten (Naturhistorisches Museum Basel/Bern,
    Deutsches Bergbau-Museum Bochum, Bayerische Staatssammlung fuer Palaeontologie und
    Geologie) und in publizierten Sammlungs-Katalogen (mineralogische Zeitschriften
    mit ``Kat.-Nr.``-Referenz-Notation). Bisher fielen alle Kat.-Nr.-Formen still auf
    None und der ``--ids-from-file``-Import wirft ``Ungueltige Objekt-ID: 'Kat.-Nr. 43'``.
    """
    # Standard-Formen mit unterschiedlichen Trenner-Kombinationen
    assert normalize_id("Kat.-Nr. 43") == "OBJ_0043"
    assert normalize_id("Kat. Nr. 43") == "OBJ_0043"
    assert normalize_id("Kat Nr. 43") == "OBJ_0043"
    assert normalize_id("Kat-Nr. 43") == "OBJ_0043"
    assert normalize_id("Kat-Nr 43") == "OBJ_0043"
    assert normalize_id("KatNr 43") == "OBJ_0043"
    assert normalize_id("KatNr43") == "OBJ_0043"
    assert normalize_id("Kat.Nr.43") == "OBJ_0043"
    # Ausgeschriebene Form ``Katalog`` und ``Nummer``
    assert normalize_id("Katalog-Nr. 43") == "OBJ_0043"
    assert normalize_id("Katalog Nr. 43") == "OBJ_0043"
    assert normalize_id("Katalognummer 43") == "OBJ_0043"
    assert normalize_id("Katalognummer43") == "OBJ_0043"
    assert normalize_id("Kat. Nummer 43") == "OBJ_0043"
    # Case-Insensitivitaet
    assert normalize_id("kat-nr 7") == "OBJ_0007"
    assert normalize_id("KAT-NR. 001") == "OBJ_0001"
    assert normalize_id("katalognummer 7") == "OBJ_0007"
    # Ungueltig: ohne Nummer-Marker, mit Suffix-Ballast, oder falsches Wort
    assert normalize_id("Kat 43") is None            # ohne Nr/Nummer nicht eindeutig
    assert normalize_id("Katalog 43") is None        # ohne Nummer-Marker
    assert normalize_id("Kat.-Nr. 43X") is None      # Suffix-Ballast
    assert normalize_id("Kategorie 43") is None      # anderes Wort mit Kat-Praefix
    assert normalize_id("Kathedrale 43") is None
    assert normalize_id("Katalyse 43") is None
    assert normalize_id("Katze 43") is None
    assert normalize_id("Kat-Nr 43 44") is None      # Doppel-Zahl
    # Regressionsschutz: bestehende Formen (inkl. Inventarnummer-Praefix) bleiben gueltig
    assert normalize_id("OBJ-001") == "OBJ_0001"
    assert normalize_id("Nr. 43") == "OBJ_0043"
    assert normalize_id("No. 43") == "OBJ_0043"
    assert normalize_id("Inv.-Nr. 43") == "OBJ_0043"
    assert normalize_id("Inventarnummer 43") == "OBJ_0043"
    assert normalize_id("Objekt 7") == "OBJ_0007"
    assert normalize_id("#43") == "OBJ_0043"


def test_normalize_id_fund_nummer_praefix():
    """Mineralogische Fundnummer ``Fund-Nr.`` und Varianten - Sammler-/Feld-Notiz-Standard.

    Waehrend ``Inv.-Nr.`` (323cfff) die Museums-physische Inventar-Position und
    ``Kat.-Nr.`` (be56257) den logischen Katalog-Eintrag identifiziert, referenziert
    ``Fund-Nr.`` das Sammel-Ereignis in einem privaten Sammlungs-Kontext - verbreitet
    in DE-sprachigen Sammler-Notizen aus Feldkampagnen, in Vereinszeitschriften der
    Mineralien-Vereine (VFMG, MVSK, Der Aufschluss) und in Foto-Captions von
    Fundstellen-Bildern (``Fund-Nr. 43, Val Bavona, 2024-07-14``). Bisher fielen
    alle Fund-Nr.-Formen still auf None, weil das Regex-Set keinen ``Fund``-
    startenden Praefix kannte. Regex spiegelt die Inv-/Kat-Regex strukturell:
    ``Fund\\.?`` mit optionalem Punkt, beliebige Trenner-Kombination (``-``/``.``
    /Whitespace), dann obligatorischer ``N(?:umme)?r``-Marker (verhindert falsche
    Positives fuer bare ``Fund 43`` oder Fund-startende Kompositum-Woerter wie
    ``Fundort``, ``Fundstelle``, ``Fundgebiet``, ``Fundstaette``, ``Fundament``,
    ``Fundus``).
    """
    # Standard-Formen mit unterschiedlichen Trenner-Kombinationen
    assert normalize_id("Fund-Nr. 43") == "OBJ_0043"
    assert normalize_id("Fund. Nr. 43") == "OBJ_0043"
    assert normalize_id("Fund Nr. 43") == "OBJ_0043"
    assert normalize_id("Fund-Nr. 43") == "OBJ_0043"
    assert normalize_id("Fund-Nr 43") == "OBJ_0043"
    assert normalize_id("FundNr 43") == "OBJ_0043"
    assert normalize_id("FundNr43") == "OBJ_0043"
    assert normalize_id("Fund.Nr.43") == "OBJ_0043"
    # Ausgeschriebene Form ``Nummer``
    assert normalize_id("Fundnummer 43") == "OBJ_0043"
    assert normalize_id("Fundnummer43") == "OBJ_0043"
    assert normalize_id("Fund. Nummer 43") == "OBJ_0043"
    assert normalize_id("Fund Nummer 43") == "OBJ_0043"
    # Case-Insensitivitaet
    assert normalize_id("fund-nr 7") == "OBJ_0007"
    assert normalize_id("FUND-NR. 001") == "OBJ_0001"
    assert normalize_id("fundnummer 7") == "OBJ_0007"
    assert normalize_id("FUNDNUMMER 43") == "OBJ_0043"
    # Ungueltig: ohne Nummer-Marker, mit Suffix-Ballast, oder Fund-Kompositum
    assert normalize_id("Fund 43") is None            # ohne Nr/Nummer nicht eindeutig
    assert normalize_id("Fund-Nr. 43X") is None       # Suffix-Ballast
    assert normalize_id("Fundort 43") is None         # Fund-Kompositum ohne Nr-Marker
    assert normalize_id("Fundstelle 43") is None
    assert normalize_id("Fundgebiet 43") is None
    assert normalize_id("Fundstaette 43") is None
    assert normalize_id("Fundament 43") is None
    assert normalize_id("Fundamental 43") is None
    assert normalize_id("Fundus 43") is None
    assert normalize_id("Fund-Nr 43 44") is None      # Doppel-Zahl
    # Regressionsschutz: bestehende Formen (inkl. Inv/Kat-Nr-Praefix) bleiben gueltig
    assert normalize_id("OBJ-001") == "OBJ_0001"
    assert normalize_id("Nr. 43") == "OBJ_0043"
    assert normalize_id("No. 43") == "OBJ_0043"
    assert normalize_id("Inv.-Nr. 43") == "OBJ_0043"
    assert normalize_id("Inventarnummer 43") == "OBJ_0043"
    assert normalize_id("Kat.-Nr. 43") == "OBJ_0043"
    assert normalize_id("Katalognummer 43") == "OBJ_0043"
    assert normalize_id("Objekt 7") == "OBJ_0007"
    assert normalize_id("#43") == "OBJ_0043"


def test_normalize_id_ausgeschriebene_nummer_vollform():
    """Standalone ``Nummer`` als ausgeschriebene DE-Vollform, spiegelt Kurzform ``Nr.``.

    Waehrend die Kurzform ``Nr.``/``Nr`` bereits durch
    :func:`test_normalize_id_kompaktform_und_alternative_praefixe` abgedeckt ist,
    verwenden handschriftliche Katalog-Eintraege und Kaufbelege haeufig die
    ausgeschriebene Vollform ``Nummer`` ohne Abkuerzungspunkt. Bisher fielen alle
    Nummer-Formen still auf None, obwohl semantisch identisch zur Kurzform.
    Regex-Erweiterung ``N(?:umme)?r`` spiegelt strukturell die
    Inv(?:entar)?-/Kat(?:alog)?-Konvention der Museums-Praefixe.
    """
    assert normalize_id("Nummer 43") == "OBJ_0043"
    assert normalize_id("Nummer 7") == "OBJ_0007"
    assert normalize_id("Nummer43") == "OBJ_0043"
    assert normalize_id("Nummer 001") == "OBJ_0001"
    # Case-Insensitivitaet
    assert normalize_id("nummer 7") == "OBJ_0007"
    assert normalize_id("NUMMER 43") == "OBJ_0043"
    # Regressionsschutz: bestehende Kurzform bleibt gueltig
    assert normalize_id("Nr. 43") == "OBJ_0043"
    assert normalize_id("Nr 43") == "OBJ_0043"
    assert normalize_id("Nr.43") == "OBJ_0043"
    # Ungueltig: Suffix-Ballast, Doppel-Zahl, andere Woerter mit N-Praefix
    assert normalize_id("Nummer 43X") is None
    assert normalize_id("Nummer 43 44") is None
    assert normalize_id("Numerisch 43") is None
    assert normalize_id("Numeriert 43") is None


def test_normalize_id_sammlungs_nummer_praefix():
    """Private Sammlungsnummer ``Slg.-Nr.`` / ``Sammlungsnummer`` - Sammler-Katalog-Standard.

    Waehrend ``Inv.-Nr.`` (323cfff) die Museums-physische Inventar-Position,
    ``Kat.-Nr.`` (be56257) den logischen Katalog-Eintrag und ``Fund-Nr.`` (aa5372d)
    das Sammel-Ereignis identifiziert, referenziert ``Slg.-Nr.`` den laufenden
    Zaehler im privaten Sammlungs-Katalog - Standard-Praefix DE-sprachiger Sammler-
    Karteikarten, Excel-Sammlungsverzeichnisse und Vereinszeitschriften-Referenzen.
    ``Slg.`` ist die etablierte Kurzform von ``Sammlung`` (analog ``Inv.`` = Inventar,
    ``Kat.`` = Katalog). Bisher fielen alle Slg.-Nr.-Formen still auf None.
    Regex ``^(?:Slg|Sammlungs?)\\.?[-.\\s]*N(?:umme)?r\\.?\\s*(\\d+)$`` spiegelt
    strukturell die Inv-/Kat-/Fund-Regex; die optionale Genitiv-s-Erweiterung
    ``Sammlungs?`` deckt sowohl die grammatikalisch korrekte Kompositum-Form
    ``Sammlungsnummer`` (Fugen-s bei Feminina) als auch die verkuerzte Bindestrich-
    Form ``Sammlung-Nr.`` (ohne Fugen-s) ab.
    """
    # Standard-Kurzform-Trenner-Kombinationen
    assert normalize_id("Slg.-Nr. 43") == "OBJ_0043"
    assert normalize_id("Slg. Nr. 43") == "OBJ_0043"
    assert normalize_id("Slg Nr. 43") == "OBJ_0043"
    assert normalize_id("Slg-Nr. 43") == "OBJ_0043"
    assert normalize_id("Slg-Nr 43") == "OBJ_0043"
    assert normalize_id("SlgNr 43") == "OBJ_0043"
    assert normalize_id("SlgNr43") == "OBJ_0043"
    assert normalize_id("Slg.Nr.43") == "OBJ_0043"
    # Ausgeschriebene Formen (``Sammlung`` mit/ohne Fugen-s, ``Nummer`` ausgeschrieben)
    assert normalize_id("Sammlungsnummer 43") == "OBJ_0043"
    assert normalize_id("Sammlungsnummer43") == "OBJ_0043"
    assert normalize_id("Sammlungs-Nr. 43") == "OBJ_0043"
    assert normalize_id("Sammlung-Nr. 43") == "OBJ_0043"
    assert normalize_id("Sammlung Nr. 43") == "OBJ_0043"
    assert normalize_id("Slg. Nummer 43") == "OBJ_0043"
    # Case-Insensitivitaet
    assert normalize_id("slg-nr 7") == "OBJ_0007"
    assert normalize_id("SLG-NR. 001") == "OBJ_0001"
    assert normalize_id("sammlungsnummer 7") == "OBJ_0007"
    assert normalize_id("SAMMLUNGSNUMMER 43") == "OBJ_0043"
    # Ungueltig: ohne Nummer-Marker, Suffix-Ballast, Sammlungs-Kompositum,
    # oder aehnlich klingende Sammel-/Sammler-Woerter ohne semantische Naehe
    assert normalize_id("Slg 43") is None
    assert normalize_id("Sammlung 43") is None
    assert normalize_id("Slg.-Nr. 43X") is None
    assert normalize_id("Slg-Nr 43 44") is None
    assert normalize_id("Sammlungsstueck 43") is None
    assert normalize_id("Sammlungsgegenstand 43") is None
    assert normalize_id("Sammlungsobjekt 43") is None
    assert normalize_id("Sammlungsband 43") is None
    assert normalize_id("Sammler 43") is None
    assert normalize_id("Sammelband 43") is None
    assert normalize_id("Sammelklage 43") is None
    # Regressionsschutz: bestehende Formen (inkl. Inv-/Kat-/Fund-Nr-Praefix) bleiben gueltig
    assert normalize_id("OBJ-001") == "OBJ_0001"
    assert normalize_id("Nr. 43") == "OBJ_0043"
    assert normalize_id("No. 43") == "OBJ_0043"
    assert normalize_id("Inv.-Nr. 43") == "OBJ_0043"
    assert normalize_id("Inventarnummer 43") == "OBJ_0043"
    assert normalize_id("Kat.-Nr. 43") == "OBJ_0043"
    assert normalize_id("Katalognummer 43") == "OBJ_0043"
    assert normalize_id("Fund-Nr. 43") == "OBJ_0043"
    assert normalize_id("Fundnummer 43") == "OBJ_0043"
    assert normalize_id("Objekt 7") == "OBJ_0007"
    assert normalize_id("#43") == "OBJ_0043"


def test_normalize_id_englische_katalog_nummer_praefix():
    """Englische Katalog-Nummer ``Cat. No.`` / ``Catalog Number`` / ``Catalogue No.``
    - Museums-Standard des anglo-amerikanischen Raums (Smithsonian NMNH, British Museum,
    AMNH, Yale Peabody, Harvard Mineralogical). Englisches Pendant zur DE-``Kat.-Nr.``-
    Regex (be56257): waehrend die DE-Form auf DE-sprachigen Museums-Etiketten (Basel/Bern,
    Bochum, Muenchen) verbreitet ist, herrscht die EN-Form in den grossen anglo-amerikanischen
    Naturkunde-Museen und in EN-sprachigen Publikationen (Rocks & Minerals, Mineralogical
    Record). Bisher fielen alle Cat.-No.-Formen still auf None, weil die ``Kat``-Regex nur
    ``K``-startende Praefixe abdeckte - der ``--ids-from-file``-Import EN-sprachiger
    Sammlungs-/Publikations-Referenzen scheiterte.
    """
    # Standard-Kurzform-Trenner-Kombinationen
    assert normalize_id("Cat. No. 43") == "OBJ_0043"
    assert normalize_id("Cat.No. 43") == "OBJ_0043"
    assert normalize_id("Cat No. 43") == "OBJ_0043"
    assert normalize_id("Cat No 43") == "OBJ_0043"
    assert normalize_id("Cat-No. 43") == "OBJ_0043"
    assert normalize_id("Cat-No 43") == "OBJ_0043"
    assert normalize_id("CatNo 43") == "OBJ_0043"
    assert normalize_id("CatNo43") == "OBJ_0043"
    assert normalize_id("Cat.No.43") == "OBJ_0043"
    # US-Vollform ``Catalog`` und UK-Vollform ``Catalogue``, sowie ausgeschriebene ``Number``
    assert normalize_id("Catalog No. 43") == "OBJ_0043"
    assert normalize_id("Catalog Number 43") == "OBJ_0043"
    assert normalize_id("Catalog-No. 43") == "OBJ_0043"
    assert normalize_id("Catalogue No. 43") == "OBJ_0043"
    assert normalize_id("Catalogue Number 43") == "OBJ_0043"
    assert normalize_id("Cat. Number 43") == "OBJ_0043"
    assert normalize_id("CatNumber43") == "OBJ_0043"
    # Case-Insensitivitaet
    assert normalize_id("cat no 7") == "OBJ_0007"
    assert normalize_id("CAT-NO. 001") == "OBJ_0001"
    assert normalize_id("catalog number 7") == "OBJ_0007"
    assert normalize_id("CATALOGUE NO. 43") == "OBJ_0043"
    # Ungueltig: ohne No/Number-Marker, Suffix-Ballast, oder Cat-startende
    # EN-Woerter ohne semantische Naehe (Category, Cathedral, Catholic, Catch, Cattle)
    assert normalize_id("Cat 43") is None            # ohne No/Number nicht eindeutig
    assert normalize_id("Catalog 43") is None
    assert normalize_id("Catalogue 43") is None
    assert normalize_id("Cat. No. 43X") is None      # Suffix-Ballast
    assert normalize_id("Category 43") is None
    assert normalize_id("Cathedral 43") is None
    assert normalize_id("Catholic 43") is None
    assert normalize_id("Catch 43") is None
    assert normalize_id("Cattle 43") is None
    assert normalize_id("Catnap 43") is None
    assert normalize_id("Cat No 43 44") is None      # Doppel-Zahl
    # Regressionsschutz: bestehende Formen (inkl. DE-Kat-Nr) bleiben gueltig
    assert normalize_id("OBJ-001") == "OBJ_0001"
    assert normalize_id("Nr. 43") == "OBJ_0043"
    assert normalize_id("No. 43") == "OBJ_0043"
    assert normalize_id("Kat.-Nr. 43") == "OBJ_0043"
    assert normalize_id("Katalognummer 43") == "OBJ_0043"
    assert normalize_id("Inv.-Nr. 43") == "OBJ_0043"
    assert normalize_id("Fund-Nr. 43") == "OBJ_0043"
    assert normalize_id("Slg.-Nr. 43") == "OBJ_0043"
    assert normalize_id("Objekt 7") == "OBJ_0007"
    assert normalize_id("#43") == "OBJ_0043"


def test_normalize_id_englische_accession_nummer_praefix():
    """Englische Accession-/Erwerbungs-Nummer ``Acc. No.`` / ``Accession Number``
    - zweiter grosser EN-Museums-Standard neben ``Cat. No.`` (Smithsonian NMNH,
    AMNH, NHM London, Yale Peabody, Harvard Mineralogical). Distinkt von der
    Cat.-No.-Achse (Katalog-Eintrag): Accession referenziert das Erwerbungs-
    Ereignis (wann/wie erworben), Cat. No. den Katalog-Eintrag (wo im Katalog);
    beide Praefixe koexistieren als eigenstaendige Nummerierungs-Systeme auf
    denselben Objekten in den Museums-Sammlungs-Datenbanken. Bisher fielen alle
    Acc.-No.-Formen still auf None, weil das Regex-Set keinen ``Acc``-startenden
    Praefix kannte - der ``--ids-from-file``-Import EN-sprachiger Provenienz-
    Recherchen und Type-Specimen-Referenzen scheiterte.
    """
    # Standard-Kurzform-Trenner-Kombinationen
    assert normalize_id("Acc. No. 43") == "OBJ_0043"
    assert normalize_id("Acc.No. 43") == "OBJ_0043"
    assert normalize_id("Acc No. 43") == "OBJ_0043"
    assert normalize_id("Acc No 43") == "OBJ_0043"
    assert normalize_id("Acc-No. 43") == "OBJ_0043"
    assert normalize_id("Acc-No 43") == "OBJ_0043"
    assert normalize_id("AccNo 43") == "OBJ_0043"
    assert normalize_id("AccNo43") == "OBJ_0043"
    assert normalize_id("Acc.No.43") == "OBJ_0043"
    # Ausgeschriebene Vollform ``Accession`` und ``Number``
    assert normalize_id("Accession No. 43") == "OBJ_0043"
    assert normalize_id("Accession Number 43") == "OBJ_0043"
    assert normalize_id("Accession-No. 43") == "OBJ_0043"
    assert normalize_id("Accession No 43") == "OBJ_0043"
    assert normalize_id("Acc. Number 43") == "OBJ_0043"
    assert normalize_id("AccNumber43") == "OBJ_0043"
    # Case-Insensitivitaet
    assert normalize_id("acc no 7") == "OBJ_0007"
    assert normalize_id("ACC-NO. 001") == "OBJ_0001"
    assert normalize_id("accession number 7") == "OBJ_0007"
    assert normalize_id("ACCESSION NO. 43") == "OBJ_0043"
    # Ungueltig: ohne No/Number-Marker, Suffix-Ballast oder Acc-startende
    # EN-Woerter ohne semantische Naehe (Access, Accept, Account, Accord,
    # Accurate, Accompany) - Disambiguierungs-Schutz durch obligatorischen
    # No/Number-Marker.
    assert normalize_id("Acc 43") is None            # ohne No/Number nicht eindeutig
    assert normalize_id("Accession 43") is None
    assert normalize_id("Acc. No. 43X") is None      # Suffix-Ballast
    assert normalize_id("Access 43") is None
    assert normalize_id("Access No. 43") is None     # Access != Accession
    assert normalize_id("Account 43") is None
    assert normalize_id("Account No. 43") is None    # Account != Accession
    assert normalize_id("Accept 43") is None
    assert normalize_id("Accord 43") is None
    assert normalize_id("Accurate 43") is None
    assert normalize_id("Accompany 43") is None
    assert normalize_id("Acc No 43 44") is None      # Doppel-Zahl
    # Regressionsschutz: bestehende Formen (inkl. DE-/EN-Kat-Nr) bleiben gueltig
    assert normalize_id("OBJ-001") == "OBJ_0001"
    assert normalize_id("Nr. 43") == "OBJ_0043"
    assert normalize_id("No. 43") == "OBJ_0043"
    assert normalize_id("Cat. No. 43") == "OBJ_0043"
    assert normalize_id("Catalog Number 43") == "OBJ_0043"
    assert normalize_id("Kat.-Nr. 43") == "OBJ_0043"
    assert normalize_id("Katalognummer 43") == "OBJ_0043"
    assert normalize_id("Inv.-Nr. 43") == "OBJ_0043"
    assert normalize_id("Fund-Nr. 43") == "OBJ_0043"
    assert normalize_id("Slg.-Nr. 43") == "OBJ_0043"
    assert normalize_id("Objekt 7") == "OBJ_0007"
    assert normalize_id("#43") == "OBJ_0043"


def test_normalize_id_englische_registration_nummer_praefix():
    """Englische Registration-Nummer ``Reg. No.`` / ``Registration Number``
    - dritter grosser EN-Museums-Standard neben ``Cat. No.`` (Katalog-Eintrag)
    und ``Acc. No.`` (Erwerbungs-Ereignis). Standard-Praefix im britischen
    Museums-Umfeld (Natural History Museum London mit BM-Registrations-Notation,
    National Museum of Wales, Sedgwick Museum Cambridge, National Museums
    Scotland) und in publizierten EN-Type-Specimen-Reports. Bisher fielen alle
    Reg.-No.-Formen still auf None, weil das Regex-Set keinen ``Reg``-startenden
    Praefix kannte.
    """
    # Standard-Kurzform-Trenner-Kombinationen
    assert normalize_id("Reg. No. 43") == "OBJ_0043"
    assert normalize_id("Reg.No. 43") == "OBJ_0043"
    assert normalize_id("Reg No. 43") == "OBJ_0043"
    assert normalize_id("Reg No 43") == "OBJ_0043"
    assert normalize_id("Reg-No. 43") == "OBJ_0043"
    assert normalize_id("Reg-No 43") == "OBJ_0043"
    assert normalize_id("RegNo 43") == "OBJ_0043"
    assert normalize_id("RegNo43") == "OBJ_0043"
    assert normalize_id("Reg.No.43") == "OBJ_0043"
    # Ausgeschriebene Vollform ``Registration`` und ``Number``
    assert normalize_id("Registration No. 43") == "OBJ_0043"
    assert normalize_id("Registration Number 43") == "OBJ_0043"
    assert normalize_id("Registration-No. 43") == "OBJ_0043"
    assert normalize_id("Registration No 43") == "OBJ_0043"
    assert normalize_id("Reg. Number 43") == "OBJ_0043"
    assert normalize_id("RegNumber43") == "OBJ_0043"
    # Case-Insensitivitaet
    assert normalize_id("reg no 7") == "OBJ_0007"
    assert normalize_id("REG-NO. 001") == "OBJ_0001"
    assert normalize_id("registration number 7") == "OBJ_0007"
    assert normalize_id("REGISTRATION NO. 43") == "OBJ_0043"
    # Ungueltig: ohne No/Number-Marker, Suffix-Ballast oder Reg-startende
    # EN-Woerter ohne semantische Naehe (Region, Regular, Regard, Register,
    # Regret, Regime, Regel-DE) - Disambiguierungs-Schutz durch obligatorischen
    # No/Number-Marker.
    assert normalize_id("Reg 43") is None            # ohne No/Number nicht eindeutig
    assert normalize_id("Registration 43") is None
    assert normalize_id("Reg. No. 43X") is None      # Suffix-Ballast
    assert normalize_id("Region 43") is None
    assert normalize_id("Region No. 43") is None     # Region != Registration
    assert normalize_id("Regular 43") is None
    assert normalize_id("Regular No. 43") is None    # Regular != Registration
    assert normalize_id("Regard 43") is None
    assert normalize_id("Register 43") is None
    assert normalize_id("Register No. 43") is None   # Register != Registration
    assert normalize_id("Regret 43") is None
    assert normalize_id("Regime 43") is None
    assert normalize_id("Regel 43") is None          # DE-Wort ``Regel``
    assert normalize_id("Reg No 43 44") is None      # Doppel-Zahl
    # Regressionsschutz: bestehende Formen (inkl. DE-/EN-Praefixe) bleiben gueltig
    assert normalize_id("OBJ-001") == "OBJ_0001"
    assert normalize_id("Nr. 43") == "OBJ_0043"
    assert normalize_id("No. 43") == "OBJ_0043"
    assert normalize_id("Cat. No. 43") == "OBJ_0043"
    assert normalize_id("Catalog Number 43") == "OBJ_0043"
    assert normalize_id("Acc. No. 43") == "OBJ_0043"
    assert normalize_id("Accession Number 43") == "OBJ_0043"
    assert normalize_id("Kat.-Nr. 43") == "OBJ_0043"
    assert normalize_id("Katalognummer 43") == "OBJ_0043"
    assert normalize_id("Inv.-Nr. 43") == "OBJ_0043"
    assert normalize_id("Fund-Nr. 43") == "OBJ_0043"
    assert normalize_id("Slg.-Nr. 43") == "OBJ_0043"
    assert normalize_id("Objekt 7") == "OBJ_0007"
    assert normalize_id("#43") == "OBJ_0043"


def test_parse_range():
    assert csv_loaders.parse_range("6.5–7") == (6.5, 7.0)
    assert csv_loaders.parse_range("6.5-7.0") == (6.5, 7.0)
    assert csv_loaders.parse_range("ca. 2.65") == (2.65, 2.65)
    assert csv_loaders.parse_range("7") == (7.0, 7.0)
    assert csv_loaders.parse_range("2,55") == (2.55, 2.55)
    assert csv_loaders.parse_range("") == (None, None)
    assert csv_loaders.parse_range(None) == (None, None)


def test_parse_range_keine_invertierten_paare():
    """Umgedrehte Range-Eingabe '7-5' (Tippfehler) darf keinen inverted Range liefern.

    (Die IUCr-Kompaktform ``'5.5(3)'`` wird jetzt als publizierte Toleranz
    ausgelesen und lebt in :func:`test_parse_range_klammer_unsicherheit`.)
    """
    # Tippfehler "7-5" → soll nicht (7, 5) liefern
    assert csv_loaders.parse_range("7-5") == (7.0, 7.0)
    # Echter Range bleibt korrekt
    assert csv_loaders.parse_range("5-7") == (5.0, 7.0)


def test_parse_range_klammer_unsicherheit():
    """IUCr-Kompaktform ``N(M)`` liefert die publizierten Toleranz-Grenzen.

    Standard-Konvention der International Union of Crystallography und
    verbreitet in mineralogischen Referenz-Tabellen, Roentgen-Beugungs-
    Reports und NIST-CODATA-Konstanten-Tabellen. Vor dem Fix fielen alle
    Kompaktformen entweder auf inverted-Range-Kollaps ``(5.5, 5.5)``
    (Klammer-Zahl < Center) oder auf einen falsch interpretierten Range
    ``(2.65, 5.0)`` (Klammer-Zahl > Center) - beide Faelle verwarfen die
    publizierte Standard-Unsicherheit stille.
    """
    # 5.5(3) = 5.5 ± 0.3 -> Toleranz auf 1. Nachkommastelle
    assert csv_loaders.parse_range("5.5(3)") == pytest.approx((5.2, 5.8))
    # 2.65(5) = 2.65 ± 0.05 -> Toleranz auf 2. Nachkommastelle
    assert csv_loaders.parse_range("2.65(5)") == pytest.approx((2.60, 2.70))
    # 100(2) = 100 ± 2 -> Toleranz auf letzte ganze Ziffer (n_decimals = 0)
    assert csv_loaders.parse_range("100(2)") == pytest.approx((98.0, 102.0))
    # Mehrstellige Toleranz: 7.4(15) = 7.4 ± 1.5 (nicht 0.15, weil 15 ist
    # die Standardabweichung in Einheiten der letzten Ziffer und die letzte
    # Ziffer des Zentrums liegt auf 10^-1).
    assert csv_loaders.parse_range("7.4(15)") == pytest.approx((5.9, 8.9))
    # 12.345(67) = 12.345 ± 0.067 -> Toleranz auf 3. Nachkommastelle
    assert csv_loaders.parse_range("12.345(67)") == pytest.approx((12.278, 12.412))
    # Negativer Center (thermische/isotopische Werte, spiegelt die
    # ±-Langform-Konvention).
    assert csv_loaders.parse_range("-1.5(3)") == pytest.approx((-1.8, -1.2))
    # DE-Komma-Dezimal (deutschsprachige Publikationen, Excel-DE).
    assert csv_loaders.parse_range("2,65(5)") == pytest.approx((2.60, 2.70))
    # Whitespace zwischen Wert und Klammer bricht das strikte IUCr-Pattern
    # (echte Annotations-Klammern wie "1.5 (Literatur)" duerfen nicht als
    # Unsicherheit interpretiert werden); Fallback auf Zahl-Extraktion.
    assert csv_loaders.parse_range("5.5 (3)") == (5.5, 5.5)
    # Freitext-Klammer-Annotation NACH IUCr-Kompaktform (durch Whitespace
    # getrennt) wird jetzt toleriert - die Trailing-Klammer-Erweiterung des
    # Uncertainty-Patterns matcht die publizierte Wert-mit-Toleranz-mit-
    # Referenz-Notation als kanonische Publikations-Zeilenform.
    assert csv_loaders.parse_range("5.5(3) (Literatur)") == pytest.approx((5.2, 5.8))
    # Ganzzahliger Wert mit einstelliger Toleranz (haeufig in NIST-Tabellen).
    assert csv_loaders.parse_range("50(1)") == pytest.approx((49.0, 51.0))
    # Toleranz-Klammer allein (ohne Center) bleibt Standard-Fallback.
    assert csv_loaders.parse_range("(3)") == (3.0, 3.0)


def test_parse_range_en_tausendertrenner_mit_dezimal():
    """Englische Excel-Exporte: '1,000.50' (Komma=Tausender, Punkt=Dezimal)."""
    assert csv_loaders.parse_range("1,000.50") == (1000.5, 1000.5)
    assert csv_loaders.parse_range("1,000,000.50") == (1000000.5, 1000000.5)
    assert csv_loaders.parse_range("1,000.00-2,000.00") == (1000.0, 2000.0)


def test_parse_range_de_tausendertrenner_mit_dezimal():
    """Deutsche Excel-Exporte: '1.000,50' (Punkt=Tausender, Komma=Dezimal)."""
    assert csv_loaders.parse_range("1.000,50") == (1000.5, 1000.5)
    assert csv_loaders.parse_range("1.000.000,75") == (1000000.75, 1000000.75)


def test_parse_range_reine_tausendergruppen():
    """Mehrere gleichartige Trenner sind eindeutig Tausender (kein Dezimal)."""
    assert csv_loaders.parse_range("1.000.000") == (1000000.0, 1000000.0)
    assert csv_loaders.parse_range("1,000,000") == (1000000.0, 1000000.0)
    # 3 Gruppen
    assert csv_loaders.parse_range("1.000.000.000") == (1000000000.0, 1000000000.0)


def test_parse_range_ambivalente_einzeltrenner_bleiben_dezimal():
    """'1,000' und '1.000' sind ambivalent - bestehende Dezimal-Lesart beibehalten."""
    # Diese Faelle bleiben Dezimal (Regression-Test fuer bestehende Tests).
    assert csv_loaders.parse_range("1,000") == (1.0, 1.0)
    assert csv_loaders.parse_range("1.000") == (1.0, 1.0)
    # Range-Tokens mit Komma als DE-Dezimal duerfen nicht zu Tausendern werden
    assert csv_loaders.parse_range("6,5-7,0") == (6.5, 7.0)
    assert csv_loaders.parse_range("2,55") == (2.55, 2.55)


def test_parse_range_whitespace_tausender_mit_dezimal():
    """FR/SI-Konvention: Whitespace als Tausendertrenner mit Dezimalanteil.

    Franzoesische Excel-/LibreOffice-Exporte und ISO 31-0-konforme Tools
    schreiben Tausender als NBSP/schmales NBSP/ASCII-Leerzeichen. Vor dem
    Fix lieferte ``'1 000.50'`` (1.0, 0.5) statt (1000.5, 1000.5).
    """
    # ASCII-Leerzeichen (Hand-Eingabe, einige Tools)
    assert csv_loaders.parse_range("1 000.50") == (1000.5, 1000.5)
    assert csv_loaders.parse_range("1 234 567.89") == (1234567.89, 1234567.89)
    # FR-Konvention: Whitespace-Tausender + Komma-Dezimal
    assert csv_loaders.parse_range("1 000,50") == (1000.5, 1000.5)
    assert csv_loaders.parse_range("12 345 678,90") == (12345678.9, 12345678.9)
    # NBSP (U+00A0) - Default in franzoesischen Office-Suites
    assert csv_loaders.parse_range("1\xa0000.50") == (1000.5, 1000.5)
    assert csv_loaders.parse_range("1\xa0234\xa0567,89") == (1234567.89, 1234567.89)
    # Schmales NBSP (U+202F) - ISO 31-0 / SI-Empfehlung
    assert csv_loaders.parse_range("1 000.50") == (1000.5, 1000.5)
    assert csv_loaders.parse_range("1 234 567,89") == (1234567.89, 1234567.89)
    # THIN SPACE (U+2009) - das eigentlich BIPM-SI-Brochure / NIST-konforme
    # Tausender-Zeichen (NBSP ist Excel-Praxis, U+2009 ist die SI-Empfehlung
    # im SI-Brochure 8th edition, section 5.3.4). Verbreitet in wissenschaft-
    # lichen Publikationen, LaTeX-Output mit ``\,`` und ISO-31-0-konformen
    # Datensaetzen. Vor dem Fix lieferte ``"1 000.50"`` (1.0, 1.0)
    # statt (1000.5, 1000.5) - silenter Wert-Datenverlust bei der Migration
    # aus typografisch sauber gesetzten Mineralogie-Publikationen.
    assert csv_loaders.parse_range("1 000.50") == (1000.5, 1000.5)
    assert csv_loaders.parse_range("1 234 567,89") == (1234567.89, 1234567.89)
    # Kombiniert mit Punkt-Dezimal (EN-Konvention): THIN SPACE Tausender +
    # ASCII-Punkt-Dezimal aus internationalen Print-Quellen.
    assert csv_loaders.parse_range("12 345.67") == (12345.67, 12345.67)


def test_parse_range_whitespace_tausender_reine_gruppen():
    """Zwei oder mehr Whitespace-Trennergruppen sind eindeutig Tausender."""
    assert csv_loaders.parse_range("1 000 000") == (1000000.0, 1000000.0)
    assert csv_loaders.parse_range("1 234 567") == (1234567.0, 1234567.0)
    assert csv_loaders.parse_range("1 000 000 000") == (1000000000.0, 1000000000.0)
    # NBSP-Variante
    assert csv_loaders.parse_range("1\xa0000\xa0000") == (1000000.0, 1000000.0)
    # THIN SPACE (U+2009) - reine Tausendergruppen ohne Dezimalanteil,
    # spiegelt die NBSP-Variante auf das SI-spezifizierte Trennzeichen.
    assert csv_loaders.parse_range("1 000 000") == (1000000.0, 1000000.0)
    assert csv_loaders.parse_range("1 234 567") == (1234567.0, 1234567.0)
    # Range mit Whitespace-Tausendern auf beiden Seiten
    assert csv_loaders.parse_range("1 000 000-2 000 000") == (1000000.0, 2000000.0)


def test_parse_range_einzelne_whitespace_gruppe_bleibt_ambivalent():
    """``'1 234'`` (eine Gruppe, kein Dezimal) bleibt mehrdeutig wie ``'1,000'``.

    Spiegelt das EN/DE-Verhalten: ohne Dezimal und ohne zweite Trennergruppe
    ist die Whitespace-Form nicht eindeutig (koennte Range-Tippfehler "1 bis
    234" sein). Der Fall bleibt unangetastet - der bestehende Range-Parser
    liefert weiter zwei separate Zahlen.
    """
    # Wuerde sonst als 1234 missinterpretiert; existierender Range-Parser
    # zerlegt in zwei Zahlen (kein Regress fuer "5 7" o.ae.).
    assert csv_loaders.parse_range("1 234") == (1.0, 234.0)
    # Bestaetigung: gleicher Mechanismus wie "5 7"
    assert csv_loaders.parse_range("5 7") == (5.0, 7.0)


def test_parse_range_underscore_digit_grouping():
    """Underscore-Digit-Grouping (PEP 515, Java 7+, JS ES2021, Rust): ``'1_000'`` -> 1000.

    Der programmiersprachen-verbreitetste Ziffer-Gruppierungs-Trenner fuer
    numerische Literale. Vor dem Fix fielen alle Formen mit Underscore-
    Gruppierung silent auf ihre erste Ziffer-Sequenz: ``"1_000"`` -> (1.0, 1.0)
    (Groessenordnung komplett verloren), ``"10_000-20_000"`` -> (10.0, 10.0)
    (obere Range-Grenze weg, untere um Faktor 1000 geschrumpft), ``"1_000 ± 5"``
    -> (1.0, 5.0) (Uncertainty-Struktur zerbrochen, statt (995, 1005)). Der Fix
    strippt Underscore-Trenner mit Standard-3-Ziffer-Gruppierung symmetrisch
    zu den EN/DE/FR-Tausender-Trennern, damit Werte aus Python/Java/Rust-
    Snippets in Sammler-Notiz-Felder verlustfrei re-importiert werden.
    """
    # Basis-Form (1 Gruppe): eindeutig weil Underscore in Numerik keine
    # alternative Bedeutung hat (kein Dezimal-, Range-, Uncertainty-Marker).
    assert csv_loaders.parse_range("1_000") == (1000.0, 1000.0)
    assert csv_loaders.parse_range("2_500") == (2500.0, 2500.0)
    assert csv_loaders.parse_range("999_999") == (999999.0, 999999.0)
    # Mehrgruppen-Form (2+ Gruppen)
    assert csv_loaders.parse_range("1_000_000") == (1000000.0, 1000000.0)
    assert csv_loaders.parse_range("1_234_567") == (1234567.0, 1234567.0)
    assert csv_loaders.parse_range("1_000_000_000") == (1000000000.0, 1000000000.0)
    # Mit EN-Punkt-Dezimal
    assert csv_loaders.parse_range("1_000.50") == (1000.5, 1000.5)
    assert csv_loaders.parse_range("2_500.75") == (2500.75, 2500.75)
    assert csv_loaders.parse_range("1_000_000.99") == (1000000.99, 1000000.99)
    # Mit DE-Komma-Dezimal (Sammler kopiert Python/Rust-Literal, aber notiert
    # den Dezimal-Anteil in DE-Locale)
    assert csv_loaders.parse_range("1_000,50") == (1000.5, 1000.5)
    assert csv_loaders.parse_range("1_000_000,75") == (1000000.75, 1000000.75)
    # Range-Notation mit Underscore-Gruppierung auf beiden Seiten
    assert csv_loaders.parse_range("10_000-20_000") == (10000.0, 20000.0)
    assert csv_loaders.parse_range("1_000-2_000") == (1000.0, 2000.0)
    assert csv_loaders.parse_range("1_000_000-5_000_000") == (1000000.0, 5000000.0)
    # Kombination mit Uncertainty (± Langform): der Strip laeuft VOR dem
    # Uncertainty-Match und macht die grosse Center-Zahl ueberhaupt erst
    # als Uncertainty-Center erkennbar.
    assert csv_loaders.parse_range("1_000 ± 5") == (995.0, 1005.0)
    assert csv_loaders.parse_range("10_000 ± 100") == (9900.0, 10100.0)
    # Kombination mit direkt anhaengender Einheit (SI-Groesse aus einem
    # Rust-Snippet mit Suffix "g", "CHF", "kg" etc.)
    assert csv_loaders.parse_range("1_500 g") == (1500.0, 1500.0)
    assert csv_loaders.parse_range("2_500 CHF") == (2500.0, 2500.0)
    # Kombination mit Klammer-Annotation (Katalog-Nummer bleibt annotiert)
    assert csv_loaders.parse_range("1_000 (Ref-Preis)") == (1000.0, 1000.0)
    # Kombination mit Approx-Praefix ("ca. 1_000" - Sammler schreibt DE-
    # Praefix vor einen Programmier-Snippet-Wert)
    assert csv_loaders.parse_range("ca. 1_000") == (1000.0, 1000.0)


def test_parse_range_underscore_digit_grouping_kollisionsschutz():
    """Bezeichner-Kontexte, atypische Gruppen und Nicht-Standard-Formen bleiben unangetastet.

    Underscore als Ziffer-Gruppierungs-Trenner ist nur dann sicher normalisierbar,
    wenn er unzweideutig zwischen Wert-Ziffern steht - nicht innerhalb einer
    Bezeichner-Sequenz wie ``id_1_000`` oder ``Sample_1_000``. Der Lookbehind
    ``(?<![A-Za-z_\\d])`` schuetzt diese Faelle. Atypische Gruppen-Groessen
    (``1_23`` mit 2-Ziffer-Gruppe, ``1_0000`` mit 4-Ziffer-Gruppe) bleiben
    ebenfalls unangetastet - Python erlaubt sie zwar syntaktisch, aber in
    Sammler-Notizen sind sie extrem selten und das Risiko einer Fehl-
    Interpretation ist hoeher als der Nutzen.
    """
    # Bezeichner-Kontext: Bezeichner-Praefix vor der Gruppierung - Lookbehind
    # blockt, die Ziffern werden vom _NUM_RE-Fallback separat extrahiert.
    assert csv_loaders.parse_range("Sample_1_000") == (1.0, 1.0)
    assert csv_loaders.parse_range("id_1_000") == (1.0, 1.0)
    # Underscore-Leading (Kotlin-Backing-Field-Konvention _foo): keine
    # Wert-Interpretation - der Lookbehind blockt _1_000 als Bezeichner-
    # Fragment. Die trailing 1_000 nach dem ersten Underscore hat ein
    # Underscore im Lookbehind, das den Match ebenfalls blockt.
    assert csv_loaders.parse_range("_1_000") == (1.0, 1.0)
    # Atypische Gruppen (nicht die Standard-3-Ziffer-Konvention): das
    # Pattern verlangt exakt 3-Ziffer-Gruppen nach dem Underscore -
    # unklare Formen bleiben unnormalisiert.
    assert csv_loaders.parse_range("1_23") == (1.0, 23.0)
    # 4-Ziffer-Gruppe (``1_0000``): kein Standard-Match; _NUM_RE zerlegt
    # in [1, 0000] und via ``if hi < lo``-Kollaps liefert (1.0, 1.0).
    assert csv_loaders.parse_range("1_0000") == (1.0, 1.0)
    # Leading > 3 Ziffern (``1234_567``): Konvention ist 1-3 leading digits
    # vor der ersten 3er-Gruppe. Nicht-konventionelle Form bleibt ambivalent -
    # _NUM_RE zerlegt in [1234, 567], und via inverted-range-Kollaps (1234.0, 1234.0).
    assert csv_loaders.parse_range("1234_567") == (1234.0, 1234.0)
    # Range mit Bezeichner-Praefix: die Gruppierungs-Position ist zwar
    # nach dem Bindestrich, aber der Range-Kontext wird nicht verwirrt.
    assert csv_loaders.parse_range("obj_id_1_000") == (1.0, 1.0)
    # Regress-Anker fuer die EN/DE-Standard-Tausender-Trenner: die
    # Underscore-Normalisierung darf keine bestehenden Formen beeinflussen.
    assert csv_loaders.parse_range("1,000.50") == (1000.5, 1000.5)
    assert csv_loaders.parse_range("1.000,50") == (1000.5, 1000.5)
    assert csv_loaders.parse_range("1 000.50") == (1000.5, 1000.5)


def test_parse_range_plus_minus_unsicherheit():
    """Wissenschaftliche Unsicherheits-Notation ``N ± M`` liefert (N-M, N+M).

    In Mineralogie-Publikationen und -Tabellen der Standard-Weg, Messgenauigkeit
    zu notieren. Vor dem Fix lieferte ``5.5 ± 0.3`` den Center-Wert doppelt
    (Toleranz ging verloren); nach dem Fix werden die publizierten Bereichs-
    grenzen sichtbar. Komma-Dezimal (DE) und negativer Center werden unterstuetzt.
    """
    # Standard-Notation mit Whitespace um das ±-Zeichen (Publikations-Praxis).
    assert csv_loaders.parse_range("5.5 ± 0.3") == pytest.approx((5.2, 5.8))
    # Ohne Whitespace (Hand-Notation, Excel-Auto-Format).
    assert csv_loaders.parse_range("5.5±0.3") == pytest.approx((5.2, 5.8))
    # DE-Komma-Dezimal (deutschsprachige Publikationen, Excel-DE).
    assert csv_loaders.parse_range("2,65 ± 0,05") == pytest.approx((2.60, 2.70))
    # Negativer Center (thermische/isotopische Werte, seltener in Sammler-DB).
    assert csv_loaders.parse_range("-1.5 ± 0.3") == pytest.approx((-1.8, -1.2))
    # Toleranz = 0 kollabiert auf Punkt-Wert (Publikationen ohne dokumentierte
    # Unsicherheit notieren manchmal explizit ± 0 als "exakt gemessen").
    assert csv_loaders.parse_range("5.5 ± 0") == (5.5, 5.5)
    # Freitext-Klammer-Annotation nach Uncertainty wird jetzt toleriert - die
    # Trailing-Klammer-Erweiterung des Patterns matcht die publizierte
    # Wert-mit-Toleranz-mit-Referenz-Notation ("5.5 ± 0.3 (Literatur)",
    # "5.5 ± 0.3 [Ref]", "5.5 ± 0.3 {IUCr}") als kanonische Publikations-
    # Zeilenform. Vor der Erweiterung fielen alle diese Formen auf den
    # Fallback-Zahl-Extraktions-Kollaps (5.5, 5.5), obwohl die publizierte
    # Toleranz die intendierten Grenzen (5.2, 5.8) explizit setzt.
    assert csv_loaders.parse_range("5.5 ± 0.3 (Literatur)") == pytest.approx((5.2, 5.8))
    # Ohne Center (nur Toleranz) bleibt das alte Verhalten: eine Zahl.
    assert csv_loaders.parse_range("± 0.5") == (0.5, 0.5)


def test_parse_range_plus_minus_ascii_ersatzform():
    """ASCII-Ersatzformen ``+/-`` und ``+-`` loesen zu identischen Bereichs-
    grenzen auf wie die Unicode-Langform ``±``.

    In E-Mails, Terminal-Ausgaben, LaTeX-Roh-Exporten und geerbten Excel-
    Kopien mit Character-Set-Verlust ist die ASCII-Schreibweise Standard,
    weil der Autor kein Unicode ± zur Verfuegung hatte oder das Zeichen
    beim Kopieren verloren ging (z.B. beim Durchlaufen alter Sammlungs-DB-
    Formate, Foto-EXIF-Kommentaren oder 7-bit-Mail-Transports). Ohne die
    Ersatzform-Erkennung fielen alle diese Notationen weiter auf den
    inverted-Range-Kollaps ``(5.5, 5.5)`` - die Toleranz ging genauso
    verloren, wie beim reinen ``±``-Ausfall vor dem Original-Fix, obwohl
    das rohe Muster ``+/-`` semantisch identisch ist.
    """
    # +/- Standard-Notation (verbreitetste ASCII-Ersatzform)
    assert csv_loaders.parse_range("5.5 +/- 0.3") == pytest.approx((5.2, 5.8))
    # +- (kompakter, ohne Slash)
    assert csv_loaders.parse_range("5.5 +- 0.3") == pytest.approx((5.2, 5.8))
    # Ohne Whitespace um das ASCII-Symbol (Hand-Notation)
    assert csv_loaders.parse_range("5.5+/-0.3") == pytest.approx((5.2, 5.8))
    assert csv_loaders.parse_range("5.5+-0.3") == pytest.approx((5.2, 5.8))
    # Ganzzahl-Zentrum mit ganzzahliger Toleranz (100 +/- 2)
    assert csv_loaders.parse_range("100 +/- 2") == (98.0, 102.0)
    # DE-Komma-Dezimal mit ASCII-Ersatzform (DE-Excel-Roh-Exporte)
    assert csv_loaders.parse_range("2,65 +/- 0,05") == pytest.approx((2.60, 2.70))
    # Negativer Center - spiegelt die ±-Konvention
    assert csv_loaders.parse_range("-1.5 +/- 0.3") == pytest.approx((-1.8, -1.2))
    # Freitext-Klammer-Annotation nach Uncertainty wird jetzt toleriert -
    # spiegelt die ±-Erweiterung auf die ASCII-Ersatzformen (+/- und +-).
    assert csv_loaders.parse_range("5.5 +/- 0.3 (Literatur)") == pytest.approx((5.2, 5.8))


def test_parse_range_leading_ascii_pm_marker_ohne_whitespace():
    """ASCII-Ersatzformen ``+/-`` und ``+-`` am String-Anfang OHNE Whitespace
    vor dem Wert liefern denselben positiven Center-Wert wie die Unicode-Langform
    ``±`` - der Marker gilt als Praezisions-Modifier, nicht als Sign-Bindung.

    Silenter Bug ohne den Fix: Wo das Unicode-``±`` transparent via _NUM_RE-Skip
    als Vorzeichen-blockierendes Non-Digit-Zeichen behandelt wird (``±5.5``
    -> (5.5, 5.5)), enden die ASCII-Ersatzformen auf ``-`` und werden ohne
    Whitespace vor dem Wert von der Sign-Alternante als Vorzeichen an die Zahl
    gebunden:

    * ``"±5.5"``    -> (5.5, 5.5)    (Unicode-±: naturally works)
    * ``"± 5.5"``   -> (5.5, 5.5)    (Unicode-± mit Whitespace: naturally works)
    * ``"+/- 5.5"`` -> (5.5, 5.5)    (ASCII mit Whitespace: naturally works)
    * ``"+/-5.5"``  -> (-5.5, -5.5)  (ASCII OHNE Whitespace: silente Sign-Inversion)
    * ``"+-5.5"``   -> (-5.5, -5.5)  (ASCII kompakt ohne Whitespace: silente Sign-Inversion)

    Bei der Migration aus Hand-Notation (Sammler tippt ``+/-`` ohne Whitespace
    zur Kompaktheit), aus Terminal-Diagnose-Reports (``+/-``-Toleranz-Notation
    aus Mess-/Kalibrier-Tools ohne konsistente Whitespace-Pflege) und aus
    Excel-CSV-Zeilen mit Character-Set-Verlust (``±`` -> ``+/-``-ASCII-Fallback
    beim CSV-Export ohne Whitespace-Normalisierung) entstand damit silenter
    Vorzeichen-Datenverlust auf jeder Wert-Zelle mit Leading-ASCII-±-Marker.
    Im schlimmsten Fall (Wert in einer Statistik-Aggregation) verzerrte die
    Vorzeichen-Inversion Summen/Durchschnitte/Median-Werte und machte den
    Wert ununterscheidbar von einem echten negativen Messwert - die
    Migration schrieb Wert_CHF_roh=-500 statt 500, Wert_CHF_poliert=-1000
    statt 1000, oder Temperatur_min=-5 statt 5.

    Der Fix strippt den ASCII-Praefix (``+/-`` oder ``+-``) am String-Anfang
    per Regex ``^\\s*\\+/?-\\s*`` und rekursiert auf den verbleibenden Wert -
    identisches Strip-und-Rekursions-Muster zu :data:`_APPROX_VALUE_PREFIX`
    und :data:`_LEADING_CURRENCY_PREFIX`. Die Trailing-Uncertainty-Form
    (``5.5 +/- 0.3``) bleibt unveraendert (dort matcht ohnehin
    :data:`_PLUS_MINUS_UNCERTAINTY` und der Leading-Strip-Zweig blockt an
    der Center-Zahl vor dem Marker).
    """
    # Standard-ASCII-Form ``+/-`` OHNE Whitespace (der eigentliche Bug-Fall).
    # Vor dem Fix: (-5.5, -5.5) via _NUM_RE-Sign-Bindung; nach dem Fix:
    # (5.5, 5.5) via Praefix-Strip und Rekursion.
    assert csv_loaders.parse_range("+/-5.5") == (5.5, 5.5)
    # Kompakte ASCII-Form ``+-`` ohne Slash-Trenner (spiegelt +/- auf die
    # kompakte Konvention aus Hand-Notation und aus Notizen ohne Slash-
    # Konvention).
    assert csv_loaders.parse_range("+-5.5") == (5.5, 5.5)
    # Idempotenz-Anker: die bereits naturally-working Whitespace-Form bleibt
    # unveraendert (der Strip wirkt sich semantisch nicht aus, weil _NUM_RE
    # die positive Zahl ohnehin extrahiert).
    assert csv_loaders.parse_range("+/- 5.5") == (5.5, 5.5)
    assert csv_loaders.parse_range("+- 5.5") == (5.5, 5.5)
    # Ganzzahliger Center (typische Preis-Notation aus Auktions-Katalogen
    # mit ASCII-Toleranz-Marker ohne Whitespace: ``+/-500 CHF``).
    assert csv_loaders.parse_range("+/-500") == (500.0, 500.0)
    assert csv_loaders.parse_range("+-100") == (100.0, 100.0)
    # DE-Komma-Dezimal mit ASCII-Praefix (Excel-DE-Roh-Export mit Character-
    # Set-Verlust: ``±`` wurde bei der CSV-Serialisierung durch ``+/-`` ohne
    # Whitespace ersetzt).
    assert csv_loaders.parse_range("+/-2,65") == (2.65, 2.65)
    assert csv_loaders.parse_range("+-2,65") == (2.65, 2.65)
    # Leading-Dot-Dezimal ohne fuehrende Null (US-Konvention "no leading
    # zero") nach dem Praefix - das Lookahead ``(?=[.\d])`` akzeptiert
    # sowohl Digit als auch Dezimalpunkt-plus-Digit.
    assert csv_loaders.parse_range("+/-.5") == (0.5, 0.5)
    assert csv_loaders.parse_range("+-.5") == (0.5, 0.5)
    # Kombination Leading-Praefix + Trailing-Uncertainty: der Praefix-Strip
    # laeuft VOR den Uncertainty-Patterns, die publizierte Toleranz wird
    # nach dem Strip via _PLUS_MINUS_UNCERTAINTY-Match auf die korrekten
    # Bereichs-Grenzen aufgeloest.
    assert csv_loaders.parse_range("+/-5.5 ± 0.3") == pytest.approx((5.2, 5.8))
    assert csv_loaders.parse_range("+-5.5 ± 0.3") == pytest.approx((5.2, 5.8))
    # Kombination Leading-Praefix + IUCr-Kompaktform: spiegelt die Langform-
    # Kombination auf die Parenthesis-Uncertainty-Achse.
    assert csv_loaders.parse_range("+/-5.5(3)") == pytest.approx((5.2, 5.8))
    assert csv_loaders.parse_range("+-5.5(3)") == pytest.approx((5.2, 5.8))
    # Kombination Annaeherungs-Praefix + ASCII-±-Praefix: der Approx-Strip
    # laeuft zuerst, dann der ASCII-±-Strip via Rekursion, dann die
    # Fallback-Zahl-Extraktion. Zweistufige Praefix-Rekursion.
    assert csv_loaders.parse_range("ca. +/-5.5") == (5.5, 5.5)
    assert csv_loaders.parse_range("circa +/-5.5") == (5.5, 5.5)
    assert csv_loaders.parse_range("~+/-5.5") == (5.5, 5.5)
    # Kombination Leading-Waehrungs-Praefix + ASCII-±-Praefix: typische
    # Preis-Notation aus Auktions-Katalogen mit ASCII-Toleranz-Marker
    # (``CHF +/-500`` = "Preis-Schaetzung um 500 CHF mit implizite
    # Unsicherheit").
    assert csv_loaders.parse_range("CHF +/-500") == (500.0, 500.0)
    assert csv_loaders.parse_range("$+/-500") == (500.0, 500.0)
    assert csv_loaders.parse_range("EUR +-500") == (500.0, 500.0)
    # Vergleichs-Marker-Praefix + ASCII-±-Praefix: der Vergleichs-Zweig
    # konsumiert den ``<``/``>`` und rekursiert auf den verbleibenden
    # ASCII-±-Wert - die Semantik ist nicht praxisrelevant, aber verlustfrei.
    assert csv_loaders.parse_range("< +/-5.5") == (None, 5.5)
    assert csv_loaders.parse_range("> +/-5.5") == (5.5, None)
    # DE/EN-Approx-Suffix am Ende + Leading-ASCII-±-Praefix (beidseitige
    # Marker-Kombination): "+/-5.5, ca." -> Suffix-Strip -> "+/-5.5" ->
    # ASCII-±-Strip -> "5.5" -> Fallback.
    assert csv_loaders.parse_range("+/-5.5, ca.") == (5.5, 5.5)
    assert csv_loaders.parse_range("+-5.5, geschaetzt") == (5.5, 5.5)
    # Range nach ASCII-±-Praefix: der Strip konsumiert den Marker, der Rest
    # wird als normaler Range gelesen (siehe Kollisions-Kommentar in
    # _LEADING_ASCII_PM_MARKER: die Semantik "+/-5-10" ist mehrdeutig,
    # aber der Strip liefert die wahrscheinlichere Range-Interpretation).
    assert csv_loaders.parse_range("+/-5-10") == (5.0, 10.0)
    # Trailing-Einheit nach ASCII-±-Praefix-Wert: die Einheit hat keine
    # Zahlen und stoert die Extraktion nicht.
    assert csv_loaders.parse_range("+/-5.5 mm") == (5.5, 5.5)
    assert csv_loaders.parse_range("+-2.65 g/cm³") == (2.65, 2.65)
    # Case-Insensitivitaets-Regression: die ASCII-Zeichen ``+``/``-``/``/``
    # sind selbst case-invariant; der Praefix-Test ist deterministisch.
    # Regression-Anker: reine negative Werte OHNE ``+``-Praefix bleiben
    # unveraendert (der Strip blockt an ``^\s*\+``).
    assert csv_loaders.parse_range("-5.5") == (-5.5, -5.5)
    assert csv_loaders.parse_range("-100") == (-100.0, -100.0)
    # Regression-Anker: reine positive Vorzeichen ``+5.5`` bleiben
    # unveraendert (der Strip blockt an ``\+/?-`` - die Sequenz ``+5`` hat
    # weder ``/`` noch ``-`` an der Position).
    assert csv_loaders.parse_range("+5.5") == (5.5, 5.5)
    assert csv_loaders.parse_range("+100") == (100.0, 100.0)
    # Regression-Anker: Trailing-Uncertainty-Form ohne Leading-Praefix
    # bleibt unveraendert (der neue Zweig blockt am Praefix-Fehlen, die
    # etablierte _PLUS_MINUS_UNCERTAINTY-Semantik greift).
    assert csv_loaders.parse_range("5.5 +/- 0.3") == pytest.approx((5.2, 5.8))
    assert csv_loaders.parse_range("5.5 +- 0.3") == pytest.approx((5.2, 5.8))
    assert csv_loaders.parse_range("5.5+/-0.3") == pytest.approx((5.2, 5.8))
    # Regression-Anker: reine Wert-Zellen ohne Marker bleiben unveraendert.
    assert csv_loaders.parse_range("5.5") == (5.5, 5.5)
    assert csv_loaders.parse_range("5-7") == (5.0, 7.0)
    # Regression-Anker: pathologische Sequenzen ohne folgende Zahl (der
    # Lookahead ``(?=[.\d])`` blockt den Strip und die Fallback-Zahl-Suche
    # liefert None-None).
    assert csv_loaders.parse_range("+/-") == (None, None)
    assert csv_loaders.parse_range("+-") == (None, None)
    assert csv_loaders.parse_range("+/-abc") == (None, None)
    assert csv_loaders.parse_range("+-xyz") == (None, None)
    # Regression-Anker: leere Eingabe und None bleiben (None, None).
    assert csv_loaders.parse_range("") == (None, None)
    assert csv_loaders.parse_range(None) == (None, None)


def test_parse_range_uncertainty_mit_trailing_einheit():
    """Unsicherheits-Notation mit nachgestellter Einheit behaelt die publizierte Toleranz.

    In mineralogischen Referenz-Tabellen ist die Kompakt- oder Langform *mit*
    Einheit die uebliche Praxis: ``2.65 ± 0.05 g/cm³`` (Dichte-Feld mit SI-
    Einheit inkl. Superscript-3), ``5.5 ± 0.3 Mohs`` (Haerte-Feld mit Skalen-
    Name), ``100 ± 2 HV`` (Vickers-Haerte), ``-1.5 ± 0.3 °C`` (Temperatur).
    Vor dem Fix brach die trailing Einheit den ``$``-Anker der Uncertainty-
    Patterns und liess die Notation auf die generische Zahl-Extraktion
    fallen: ``2.65 ± 0.05 g/cm³`` wurde als ``[2.65, 0.05]`` gelesen und
    lieferte via ``if hi < lo``-Kollaps ``(2.65, 2.65)`` (Toleranz verloren);
    ``2.65(5) g/cm³`` wurde als ``[2.65, 5]`` gelesen und lieferte semantisch
    falsche ``(2.65, 5.0)`` (mineralogisch unsinniger Dichte-Range 2.65 bis
    5.0 g/cm³ statt Toleranz 2.60 bis 2.70); ``5.5(3) Mohs`` fiel via
    inverted-Range auf ``(5.5, 5.5)`` (Toleranz verloren). Fix relaxt das
    ``$``-Ende beider Patterns auf einen Whitespace-getrennten Wort-Token-
    Rest, plus optionale Trailing-Klammer-Annotationen (rund/eckig/geschweift,
    single-level), damit die publizierte Kombination "Wert + Toleranz +
    Einheit + Literatur-/Katalog-Referenz" als kanonische Publikations-
    Zeilenform erhalten bleibt. Komma/Semikolon-Trenner ausserhalb der
    Klammer-Annotationen sind weiter ausgeschlossen (schliesst ``, siehe
    Nr. 42``-Listen aus, damit dortige Nummern nicht als Range-Grenze
    fehlgelesen werden). Der erste Token-Buchstabe im Einheiten-Wort muss
    kein ASCII-Digit sein - damit fallen zufaellige nachgestellte Zahlen
    (``5.5 ± 0.3 42``) auf die Zahl-Extraktion durch und werden nicht in
    die Toleranz eingemischt.
    """
    # ± Langform mit SI-Einheit (Dichte-Feld). Vorher: (2.65, 2.65) via Kollaps.
    assert csv_loaders.parse_range("2.65 ± 0.05 g/cm³") == pytest.approx((2.60, 2.70))
    # ± Langform mit Skalen-Name (Haerte-Feld). Vorher: (5.5, 5.5) via Kollaps.
    assert csv_loaders.parse_range("5.5 ± 0.3 Mohs") == pytest.approx((5.2, 5.8))
    # ± Langform mit Vickers-Haerte-Kuerzel (Zwei-Buchstaben-Unit).
    assert csv_loaders.parse_range("100 ± 2 HV") == pytest.approx((98.0, 102.0))
    # ± Langform mit Temperatur-Einheit (° als Superscript).
    assert csv_loaders.parse_range("-1.5 ± 0.3 °C") == pytest.approx((-1.8, -1.2))
    # ± Langform mit Prozent-Zeichen (Anteil-Feld, seltene Wahl).
    assert csv_loaders.parse_range("50 ± 2 %") == pytest.approx((48.0, 52.0))
    # ASCII-Ersatzform mit trailing Einheit (7-bit-Mail-Transport, LaTeX-Roh).
    assert csv_loaders.parse_range("2.65 +/- 0.05 g/cm³") == pytest.approx((2.60, 2.70))
    assert csv_loaders.parse_range("5.5 +- 0.3 Mohs") == pytest.approx((5.2, 5.8))
    # IUCr-Kompaktform mit SI-Einheit (Dichte-Feld). Vorher: (2.65, 5.0) semantisch falsch.
    assert csv_loaders.parse_range("2.65(5) g/cm³") == pytest.approx((2.60, 2.70))
    # IUCr-Kompaktform mit Skalen-Name (Haerte-Feld). Vorher: (5.5, 5.5) via Kollaps.
    assert csv_loaders.parse_range("5.5(3) Mohs") == pytest.approx((5.2, 5.8))
    # IUCr-Kompaktform mit Vickers-Kuerzel.
    assert csv_loaders.parse_range("100(2) HV") == pytest.approx((98.0, 102.0))
    # IUCr-Kompaktform mit Kristall-Achsen-Einheit (Angstroem in Roentgenstruktur-Reports).
    assert csv_loaders.parse_range("12.345(67) Å") == pytest.approx((12.278, 12.412))
    # DE-Komma-Dezimal mit trailing Einheit (deutschsprachige Publikationen).
    assert csv_loaders.parse_range("2,65 ± 0,05 g/cm³") == pytest.approx((2.60, 2.70))
    assert csv_loaders.parse_range("2,65(5) g/cm³") == pytest.approx((2.60, 2.70))
    # Mehrere trailing Wort-Tokens (Einheit + Skalen-Zusatz).
    assert csv_loaders.parse_range("5.5 ± 0.3 Mohs Haerte") == pytest.approx((5.2, 5.8))
    assert csv_loaders.parse_range("5.5(3) Mohs Haerte") == pytest.approx((5.2, 5.8))
    # Klammer-Freitext-Anhang nach Uncertainty (mit oder ohne Einheit dazwischen)
    # wird jetzt toleriert - die Trailing-Klammer-Erweiterung des Patterns
    # matcht die publizierte Wert-mit-Toleranz-mit-Einheit-mit-Referenz-Notation
    # als kanonische Publikations-Zeilenform. Die publizierte Toleranz bleibt
    # erhalten, spiegelt die _PLUS_MINUS_UNCERTAINTY-/_PARENTHESIS_UNCERTAINTY-
    # Grundsemantik auf die reale IUCr-/NIST-Publikations-Praxis, in der Wert
    # + Toleranz + Einheit + Literatur-Verweis eine einzige Tabellen-Zeile
    # bilden.
    assert csv_loaders.parse_range("5.5 ± 0.3 (Literatur)") == pytest.approx((5.2, 5.8))
    assert csv_loaders.parse_range("5.5(3) (Literatur)") == pytest.approx((5.2, 5.8))
    assert csv_loaders.parse_range("2.65 ± 0.05 g/cm³ (Literatur)") == pytest.approx((2.60, 2.70))
    assert csv_loaders.parse_range("2.65(5) g/cm³ (Literatur)") == pytest.approx((2.60, 2.70))
    assert csv_loaders.parse_range("5.5 ± 0.3 Mohs [Ref]") == pytest.approx((5.2, 5.8))
    assert csv_loaders.parse_range("5.5(3) Mohs [Ref]") == pytest.approx((5.2, 5.8))
    assert csv_loaders.parse_range("12.345(67) K [NIST-CODATA-2018]") == pytest.approx((12.278, 12.412))
    # Regression-Anker: Komma-Anhang bricht das Trailing-Pattern (schliesst
    # ``, siehe Nr. 42``-Listen aus). Ohne diesen Ausschluss wuerde eine
    # nachgestellte Referenz-Nummer als Range-Grenze fehlgelesen.
    assert csv_loaders.parse_range("2.65 ± 0.05, siehe") == (2.65, 2.65)
    # Regression-Anker: Trailing-Digit-Token faellt auf Zahl-Extraktion, damit
    # zufaellige Zahlen nicht die Toleranz ueberschreiben.
    assert csv_loaders.parse_range("5.5 ± 0.3 42") == (5.5, 42.0)


def test_parse_range_uncertainty_mit_prozent_und_promille():
    """Unsicherheits-Notation mit ``%``/``‰`` direkt am Wert behaelt die Toleranz.

    In mineralogischen und geochemischen Publikationen sind Prozent-Zeichen
    (``%``, U+0025) und Promille-Zeichen (``‰``, U+2030) haeufige Wert-Suffixe,
    die konventionell OHNE Whitespace zwischen Zahl und Symbol notiert werden
    (``45.2 ± 0.3%`` in oxydischen Chemie-Analysen, ``-15.5 ± 0.5‰`` in
    Isotopen-Fraktionierungs-Werten wie δ¹³C/δ¹⁸O/δ³⁴S, ``100(2)%`` in Erz-
    Gehaltsangaben, ``2.65(5)%`` in Reinheits-/Ausbeute-Tabellen). Vor dem
    Fix brach das direkt angehaengte ``%``/``‰`` den ``$``-Anker beider
    Uncertainty-Patterns: der Trailing-Unit-Zweig verlangte obligatorisches
    ``\\s+`` VOR dem ersten Einheiten-Token, sodass ``5.5 ± 0.3%`` durch das
    fehlende Whitespace zwischen ``0.3`` und ``%`` auf die Fallback-Zahl-
    Extraktion durchfiel und via ``[5.5, 0.3]``-inverted-range auf ``(5.5,
    5.5)`` kollabierte (Toleranz verloren); ``100(2)%`` fiel via ``[100, 2]``
    -> Kollaps auf ``(100, 100)`` (Toleranz verloren); ``-15.5(5)‰`` (Standard-
    Notation der Isotopen-Referenz-Werte in Geochemie-/Kosmochemie-Publikationen)
    fiel via inverted-Range-Kollaps auf ``(-15.5, -15.5)``. In den Fachdomaenen
    (Isotopen-Geochemie: ‰ ist die einzige uebliche Einheit fuer delta-Werte
    stabiler Isotope; Oxid-Gehaltsangaben: wt% / mol% / at% ist die Standard-
    Konvention der Elektronenmikrosonden- und ICP-MS-Analysen; Erz-/Reinheits-
    Angaben: % ohne Whitespace ist die Print-/Excel-Konvention) entsteht damit
    silenter Verlust der publizierten Standard-Unsicherheit auf jeder Analyse-
    /Isotopen-Achse. Fix ergaenzt in beiden Uncertainty-Patterns eine optionale
    ``(?:\\s*[%‰])?``-Alternante hinter der Toleranz-Zahl (und, symmetrisch,
    hinter der Center-Zahl der ±-Langform), sodass das Symbol mit oder ohne
    Whitespace direkt an die Zahl gebunden werden kann, ohne den Trailing-
    Unit-Zweig oder die Trailing-Bracket-Annotations-Zweig zu blockieren.
    Center-``%``/``‰`` fuer die IUCr-Kompaktform ist bewusst NICHT ergaenzt,
    weil die IUCr-Konvention das Einheiten-Symbol strikt hinter die
    Klammer setzt (``5.5%(3)`` waere nicht IUCr-konform).
    """
    # ±-Langform mit ``%`` direkt an der Toleranz (Oxid-Gehaltsangabe).
    # Vorher: (5.5, 5.5) via ``[5.5, 0.3]``-inverted-range-Kollaps.
    assert csv_loaders.parse_range("5.5 ± 0.3%") == pytest.approx((5.2, 5.8))
    # ±-Langform mit ``%`` an Center UND Toleranz (redundante aber verbreitete
    # Publikations-Notation, "Wert-Einheit ± Toleranz-Einheit").
    assert csv_loaders.parse_range("5.5% ± 0.3%") == pytest.approx((5.2, 5.8))
    # ±-Langform ohne Whitespace zwischen ± und Zahlen, ``%`` direkt angehaengt
    # (kompakte Tabellen-Schreibweise ohne Spacing-Overhead).
    assert csv_loaders.parse_range("5.5%±0.3%") == pytest.approx((5.2, 5.8))
    # ±-Langform mit ``‰`` (Promille) fuer Isotopen-delta-Werte. Center darf
    # negativ sein - die klassische Konvention der Isotopen-Fraktionierung
    # (δ¹³C ~ -25‰ in organischer Materie, δ¹⁸O ~ -8‰ in Suesswasser).
    assert csv_loaders.parse_range("-15.5 ± 0.5‰") == pytest.approx((-16.0, -15.0))
    # ±-ASCII-Ersatzform mit ``%`` (7-bit-Mail-Transport, LaTeX-Roh).
    assert csv_loaders.parse_range("5.5 +/- 0.3%") == pytest.approx((5.2, 5.8))
    assert csv_loaders.parse_range("5.5 +- 0.3%") == pytest.approx((5.2, 5.8))
    # IUCr-Kompaktform mit ``%`` (Reinheits-/Ausbeute-Tabellen).
    # Vorher: (5.5, 5.5) via inverted-Range-Kollaps.
    assert csv_loaders.parse_range("5.5(3)%") == pytest.approx((5.2, 5.8))
    # IUCr-Kompaktform mit ``%`` (Erz-Gehaltsangabe, ganzzahliges Center).
    # Vorher: (100.0, 100.0) via inverted-Range-Kollaps.
    assert csv_loaders.parse_range("100(2)%") == pytest.approx((98.0, 102.0))
    # IUCr-Kompaktform mit ``‰`` fuer Isotopen-Referenz-Werte.
    assert csv_loaders.parse_range("-15.5(5)‰") == pytest.approx((-16.0, -15.0))
    # DE-Komma-Dezimal mit ``%``/``‰`` direkt angehaengt (deutschsprachige
    # Publikationen mit Komma-Dezimal-Konvention).
    assert csv_loaders.parse_range("5,5 ± 0,3%") == pytest.approx((5.2, 5.8))
    assert csv_loaders.parse_range("5,5(3)%") == pytest.approx((5.2, 5.8))
    # ``%``/``‰`` mit optionalem Whitespace davor (Space-getrennte Publikations-
    # Konvention) - bereits vor dem Fix ueber den Trailing-Unit-Zweig
    # unterstuetzt, hier als Regression-Anker gegen die neue Alternante.
    assert csv_loaders.parse_range("5.5 ± 0.3 %") == pytest.approx((5.2, 5.8))
    assert csv_loaders.parse_range("5.5(3) %") == pytest.approx((5.2, 5.8))
    assert csv_loaders.parse_range("-15.5 ± 0.5 ‰") == pytest.approx((-16.0, -15.0))
    # Kombination ``%`` + Trailing-Klammer-Annotation (publizierte Notation
    # "Wert%-Einheit + Referenz-Klammer").
    assert csv_loaders.parse_range("5.5 ± 0.3% (Literatur)") == pytest.approx((5.2, 5.8))
    assert csv_loaders.parse_range("5.5(3)% [Ref]") == pytest.approx((5.2, 5.8))
    # Regression-Anker: Uncertainty OHNE ``%``/``‰`` funktioniert unveraendert.
    assert csv_loaders.parse_range("5.5 ± 0.3") == pytest.approx((5.2, 5.8))
    assert csv_loaders.parse_range("5.5(3)") == pytest.approx((5.2, 5.8))
    # Regression-Anker: Uncertainty mit Whitespace-getrennter Einheit
    # unveraendert (der neue ``%``/``‰``-Optional-Zweig blockiert die
    # Trailing-Unit-Sequenz nicht).
    assert csv_loaders.parse_range("2.65 ± 0.05 g/cm³") == pytest.approx((2.60, 2.70))
    assert csv_loaders.parse_range("5.5(3) Mohs") == pytest.approx((5.2, 5.8))
    # Regression-Anker: Uncertainty mit Prozent-in-Einheit (``mol%``, ``wt%``,
    # ``at%``) unveraendert - das ``%`` ist Bestandteil eines mehrbuchstabigen
    # Einheiten-Tokens und wird via Trailing-Unit-Zweig gemischt, nicht via
    # der neuen Optional-Alternante.
    assert csv_loaders.parse_range("5.5 ± 0.3 mol%") == pytest.approx((5.2, 5.8))
    assert csv_loaders.parse_range("2.65(5) wt%") == pytest.approx((2.60, 2.70))


def test_parse_range_uncertainty_mit_direkt_anhaengender_einheit():
    """Unsicherheits-Notation mit direkt (ohne Whitespace) anhaengender Einheit
    behaelt die publizierte Toleranz.

    In Mineralogie-/Physik-Publikationen, in Excel-CSV-Exporten aus geerbten
    Sammler-Etiketten und in Foto-EXIF-Kommentaren ist die Space-lose Notation
    zwischen Zahl und Einheit sehr verbreitet: ``5.5mm`` (Kristall-Groesse),
    ``2.65g/cm³`` (Dichte), ``100HV`` (Vickers-Haerte), ``12.345K`` (Temperatur).
    Vor dem Fix brach die direkt anhaengende SI-Einheit den ``$``-Anker beider
    Uncertainty-Patterns: der Trailing-Unit-Zweig verlangte obligatorisches
    ``\\s+`` VOR dem ersten Einheiten-Token, sodass ``5.5 ± 0.3mm`` durch das
    fehlende Whitespace zwischen ``0.3`` und ``mm`` auf die Fallback-Zahl-
    Extraktion durchfiel und via ``[5.5, 0.3]``-inverted-range auf ``(5.5,
    5.5)`` kollabierte (Toleranz verloren); ``5.5mm ± 0.3mm`` fiel auf
    ``[5.5, 0.3]``-Kollaps ``(5.5, 5.5)``; ``2.65(5)g/cm³`` fiel auf
    ``[2.65, 5]`` → ``(2.65, 5.0)`` semantisch falsch. Fix ergaenzt in beiden
    Uncertainty-Patterns eine optionale direkt-anhaengende Einheiten-Token-
    Alternante ``(?:[A-Za-zÅΩµ°][A-Za-z0-9ÅΩµ°/^³²]*)?`` hinter Center und
    Toleranz-Zahl. Die Alternante muss mit einem Buchstaben (ASCII a-z / A-Z
    plus SI-Standard-Zeichen Å/Ω/µ/°) STARTEN - damit blockt sie nicht die
    ±-Alternante, die mit ``±``/``+/-``/``+-`` beginnt, und kollidiert nicht
    mit den Bracket-Klammern ``(``/``[``/``{``.
    """
    # ±-Langform mit direkt anhaengender Einheit an Toleranz.
    # Vorher: (5.5, 5.5) via ``[5.5, 0.3]``-inverted-range-Kollaps.
    assert csv_loaders.parse_range("5.5 ± 0.3mm") == pytest.approx((5.2, 5.8))
    assert csv_loaders.parse_range("5.5 ± 0.3g") == pytest.approx((5.2, 5.8))
    assert csv_loaders.parse_range("2.65 ± 0.05g/cm3") == pytest.approx((2.60, 2.70))
    assert csv_loaders.parse_range("2.65 ± 0.05g/cm³") == pytest.approx((2.60, 2.70))
    assert csv_loaders.parse_range("2.65 ± 0.05g/cm^3") == pytest.approx((2.60, 2.70))
    # ±-Langform mit direkt anhaengender Einheit an Center (Wert-Einheit + Toleranz).
    assert csv_loaders.parse_range("5.5mm ± 0.3") == pytest.approx((5.2, 5.8))
    assert csv_loaders.parse_range("5.5g ± 0.3") == pytest.approx((5.2, 5.8))
    # ±-Langform mit direkt anhaengender Einheit an Center UND Toleranz
    # (redundante aber verbreitete Publikations-Notation).
    assert csv_loaders.parse_range("5.5mm ± 0.3mm") == pytest.approx((5.2, 5.8))
    assert csv_loaders.parse_range("5.5g ± 0.3g") == pytest.approx((5.2, 5.8))
    assert csv_loaders.parse_range("2.65g/cm3 ± 0.05g/cm3") == pytest.approx((2.60, 2.70))
    assert csv_loaders.parse_range("2.65g/cm³ ± 0.05g/cm³") == pytest.approx((2.60, 2.70))
    # ±-ASCII-Ersatzform mit direkt anhaengender Einheit.
    assert csv_loaders.parse_range("5.5 +/- 0.3mm") == pytest.approx((5.2, 5.8))
    assert csv_loaders.parse_range("5.5 +- 0.3mm") == pytest.approx((5.2, 5.8))
    # ±-Langform mit SI-Standard-Sonder-Zeichen (Å, Ω, µ, °).
    assert csv_loaders.parse_range("12.345 ± 0.067K") == pytest.approx((12.278, 12.412))
    assert csv_loaders.parse_range("12.345Å ± 0.067Å") == pytest.approx((12.278, 12.412))
    # IUCr-Kompaktform mit direkt anhaengender Einheit.
    # Vorher: (5.5, 5.5) via inverted-Range-Kollaps.
    assert csv_loaders.parse_range("5.5(3)mm") == pytest.approx((5.2, 5.8))
    assert csv_loaders.parse_range("2.65(5)g") == pytest.approx((2.60, 2.70))
    # IUCr-Kompaktform mit direkt anhaengender SI-Einheit.
    # Vorher: (2.65, 5.0) semantisch falsch.
    assert csv_loaders.parse_range("2.65(5)g/cm3") == pytest.approx((2.60, 2.70))
    assert csv_loaders.parse_range("2.65(5)g/cm³") == pytest.approx((2.60, 2.70))
    assert csv_loaders.parse_range("2.65(5)g/cm^3") == pytest.approx((2.60, 2.70))
    # IUCr-Kompaktform mit Vickers-Kuerzel direkt anhaengend.
    assert csv_loaders.parse_range("100(2)HV") == pytest.approx((98.0, 102.0))
    # IUCr-Kompaktform mit Angstroem direkt anhaengend.
    assert csv_loaders.parse_range("12.345(67)Å") == pytest.approx((12.278, 12.412))
    # DE-Komma-Dezimal mit direkt anhaengender Einheit.
    assert csv_loaders.parse_range("5,5 ± 0,3mm") == pytest.approx((5.2, 5.8))
    assert csv_loaders.parse_range("2,65 ± 0,05g/cm³") == pytest.approx((2.60, 2.70))
    assert csv_loaders.parse_range("2,65(5)g/cm³") == pytest.approx((2.60, 2.70))
    # Kombination direkt-anhaengende Einheit + Trailing-Klammer-Annotation.
    assert csv_loaders.parse_range("2.65 ± 0.05g/cm³ (Literatur)") == pytest.approx((2.60, 2.70))
    assert csv_loaders.parse_range("2.65(5)g/cm³ [Ref]") == pytest.approx((2.60, 2.70))
    assert csv_loaders.parse_range("5.5(3)mm (Foto)") == pytest.approx((5.2, 5.8))
    # Regression-Anker: Uncertainty mit Whitespace-getrennter Einheit
    # unveraendert (der neue direkt-anhaengende Alternate blockiert die
    # Trailing-Unit-Sequenz nicht).
    assert csv_loaders.parse_range("2.65 ± 0.05 g/cm³") == pytest.approx((2.60, 2.70))
    assert csv_loaders.parse_range("5.5(3) Mohs") == pytest.approx((5.2, 5.8))
    assert csv_loaders.parse_range("12.345(67) Å") == pytest.approx((12.278, 12.412))
    # Regression-Anker: Uncertainty OHNE Einheit funktioniert unveraendert.
    assert csv_loaders.parse_range("5.5 ± 0.3") == pytest.approx((5.2, 5.8))
    assert csv_loaders.parse_range("5.5(3)") == pytest.approx((5.2, 5.8))
    # Regression-Anker: ``%``/``‰`` direkt anhaengend bleibt via
    # ``(?:\\s*[%‰])?``-Alternante erkannt (nicht via der neuen Buchstaben-
    # basierten Direct-Attach-Alternante).
    assert csv_loaders.parse_range("5.5 ± 0.3%") == pytest.approx((5.2, 5.8))
    assert csv_loaders.parse_range("5.5(3)%") == pytest.approx((5.2, 5.8))
    assert csv_loaders.parse_range("-15.5 ± 0.5‰") == pytest.approx((-16.0, -15.0))
    # Regression-Anker: Komma-Anhang und Trailing-Digit-Token bleiben Range-
    # Grenze (nicht in die Toleranz eingemischt).
    assert csv_loaders.parse_range("5.5 ± 0.3, siehe") == (5.5, 5.5)
    assert csv_loaders.parse_range("5.5 ± 0.3 42") == (5.5, 42.0)


def test_parse_range_uncertainty_mit_center_einheit_whitespace_getrennt():
    """Unsicherheits-Notation mit whitespace-getrennter Einheit VOR dem ± behaelt
    die publizierte Toleranz.

    In publizierten Referenz-Tabellen und Excel-CSV-Exporten aus Print-Quellen
    ist die redundante "Center-mit-Einheit ± Toleranz-mit-Einheit"-Notation
    eine sehr verbreitete Standard-Praxis (Sammler kopieren komplette Dichte-
    /Haerte-/Temperatur-Zeilen aus IUCr-/NIST-Publikationen und Print-
    Nachschlagewerken, wo die Einheit auf beiden Seiten des ±-Symbols
    redundant notiert wird). Vor dem Fix fiel jede Notation mit whitespace-
    getrennter Einheit VOR dem ±-Symbol still auf die Fallback-Zahl-
    Extraktion durch: ``2.65 g/cm³ ± 0.05 g/cm³`` wurde als ``[2.65, 0.05]``
    gelesen und via ``if hi < lo``-Kollaps auf ``(2.65, 2.65)`` reduziert
    (Toleranz verloren); ``-1.5 °C ± 0.3`` sogar semantisch falsch als
    ``[-1.5, 0.3]``-Range interpretiert und zu ``(-1.5, 0.3)`` (thermisch
    unsinnige Range-Grenzen, publizierte Standard-Unsicherheit als Range-
    Grenze fehlgedeutet). Fix ergaenzt in :data:`_PLUS_MINUS_UNCERTAINTY`
    einen ``(?:\\s+…[A-Za-z…][A-Za-z0-9…]*)*``-Zweig ZWISCHEN Center und
    ± symmetrisch zur bereits vorhandenen Trailing-Einheit-nach-Toleranz-
    Klausel.

    Der Zweig backtrackt sauber bei ± direkt hinter Center (``5.5 ± 0.3``):
    das erste-Zeichen-muss-Buchstabe-Kriterium (``[A-Za-zÅΩµ°]``) blockt die
    ±-Zeichen-Position, und das ``*``-Quantifier erlaubt Zero-Match. Regression-
    Anker gegen die vorhandenen Uncertainty-Tests: ``5.5 ± 0.3`` (kein Middle-
    Token) bleibt unveraendert, ``5.5 ± 0.3 mm`` (Trailing-Token, nicht Middle)
    bleibt unveraendert.
    """
    # SI-Einheit auf Center UND Toleranz, whitespace-getrennt (Publikations-Standard
    # aus mineralogischen Dichte-Tabellen). Vorher: (2.65, 2.65) via Kollaps.
    assert csv_loaders.parse_range(
        "2.65 g/cm³ ± 0.05 g/cm³"
    ) == pytest.approx((2.60, 2.70))
    # SI-Einheit nur auf Center-Seite, Toleranz ohne Einheit (kompaktere
    # Publikations-Notation). Vorher: (5.5, 5.5) via Kollaps.
    assert csv_loaders.parse_range("5.5 mm ± 0.3") == pytest.approx((5.2, 5.8))
    assert csv_loaders.parse_range("5.5 g ± 0.3") == pytest.approx((5.2, 5.8))
    # Zwei-Buchstaben-Einheit (Vickers-Haerte-Kuerzel) auf Center UND Toleranz.
    # Vorher: (100.0, 100.0) via Kollaps.
    assert csv_loaders.parse_range("100 HV ± 2") == (98.0, 102.0)
    assert csv_loaders.parse_range("100 HV ± 2 HV") == (98.0, 102.0)
    # Skalen-Name (Mohs-Haerte, kein SI-Symbol) auf Center-Seite.
    assert csv_loaders.parse_range("5.5 Mohs ± 0.3") == pytest.approx((5.2, 5.8))
    # Temperatur-Einheit mit SI-Standard-Sonderzeichen (° = U+00B0) auf Center
    # UND Toleranz. Negativer Center - spiegelt die _PLUS_MINUS-Konvention.
    # Vorher besonders schlimm: (-1.5, 0.3) als vermeintlicher Range across-zero.
    assert csv_loaders.parse_range("-1.5 °C ± 0.3") == pytest.approx((-1.8, -1.2))
    assert csv_loaders.parse_range(
        "-1.5 °C ± 0.3 °C"
    ) == pytest.approx((-1.8, -1.2))
    # Angstroem-Einheit (Kristall-Achsen-Laengen in Roentgen-Struktur-Reports).
    assert csv_loaders.parse_range(
        "12.345 Å ± 0.067 Å"
    ) == pytest.approx((12.278, 12.412))
    # SI-Standard-Sonderzeichen Å auf Center-Seite, ohne Einheit auf Toleranz.
    assert csv_loaders.parse_range(
        "12.345 Å ± 0.067"
    ) == pytest.approx((12.278, 12.412))
    # Ohm (Ω = U+03A9) - elektrische Leitfaehigkeit in erz-mineralogischen
    # Kontexten (Halbleiter-Mineralien, Cu-/Ag-Analytik).
    assert csv_loaders.parse_range("100 Ω ± 5") == (95.0, 105.0)
    # ASCII-Ersatzform ``+/-`` mit Center-Einheit (LaTeX-Roh-Export, 7-bit-Mail).
    assert csv_loaders.parse_range(
        "2.65 g/cm³ +/- 0.05 g/cm³"
    ) == pytest.approx((2.60, 2.70))
    assert csv_loaders.parse_range("5.5 mm +/- 0.3") == pytest.approx((5.2, 5.8))
    assert csv_loaders.parse_range("5.5 mm +- 0.3") == pytest.approx((5.2, 5.8))
    # DE-Komma-Dezimal auf Center und Toleranz mit whitespace-getrennter Einheit
    # (deutschsprachige mineralogische Publikationen und DE-Excel-Exporte).
    assert csv_loaders.parse_range(
        "2,65 g/cm³ ± 0,05 g/cm³"
    ) == pytest.approx((2.60, 2.70))
    assert csv_loaders.parse_range("5,5 mm ± 0,3") == pytest.approx((5.2, 5.8))
    # Mehrere whitespace-getrennte Einheiten-Tokens auf Center-Seite (Skalen-
    # Name + Zusatz-Marker, publizierte Praxis in mineralogischen Referenz-
    # Tabellen).
    assert csv_loaders.parse_range(
        "5.5 Mohs Haerte ± 0.3"
    ) == pytest.approx((5.2, 5.8))
    # Kombination Center-Einheit + Trailing-Klammer-Annotation (kanonische
    # Publikations-Zeilenform "Wert-Einheit + Toleranz + Referenz-Klammer").
    assert csv_loaders.parse_range(
        "2.65 g/cm³ ± 0.05 g/cm³ (Literatur)"
    ) == pytest.approx((2.60, 2.70))
    assert csv_loaders.parse_range(
        "100 HV ± 2 HV [NIST-2018]"
    ) == (98.0, 102.0)
    # Kombination Center-Einheit + Trailing-Satzzeichen (aus Satz-Fluss
    # uebernommener Wert).
    assert csv_loaders.parse_range("5.5 mm ± 0.3.") == pytest.approx((5.2, 5.8))
    assert csv_loaders.parse_range("100 HV ± 2 HV;") == (98.0, 102.0)
    # Regression-Anker: Uncertainty OHNE Center-Einheit bleibt via Zero-Match
    # der neuen ``*``-Alternante unveraendert.
    assert csv_loaders.parse_range("5.5 ± 0.3") == pytest.approx((5.2, 5.8))
    assert csv_loaders.parse_range("5.5 ± 0.3 mm") == pytest.approx((5.2, 5.8))
    assert csv_loaders.parse_range("2.65 ± 0.05 g/cm³") == pytest.approx((2.60, 2.70))
    # Regression-Anker: direkt anhaengende Einheit (ohne Whitespace) auf Center
    # bleibt via bestehende Direct-Attach-Alternante erkannt, nicht via der
    # neuen Whitespace-Middle-Unit-Alternante.
    assert csv_loaders.parse_range("5.5mm ± 0.3") == pytest.approx((5.2, 5.8))
    assert csv_loaders.parse_range("5.5mm ± 0.3mm") == pytest.approx((5.2, 5.8))
    assert csv_loaders.parse_range(
        "2.65g/cm³ ± 0.05g/cm³"
    ) == pytest.approx((2.60, 2.70))
    # Regression-Anker: gemischte Notation (Whitespace-Center, Attached-Toleranz)
    # bleibt korrekt aufgeloest.
    assert csv_loaders.parse_range("5.5 mm ± 0.3mm") == pytest.approx((5.2, 5.8))
    assert csv_loaders.parse_range("5.5mm ± 0.3 mm") == pytest.approx((5.2, 5.8))
    # Regression-Anker: Range mit "N to M"-Syntax bleibt Fallback (kein
    # Uncertainty), weil ``to`` zwar durch die Middle-Unit-Alternante
    # konsumiert wird, aber die Toleranz-Zahl nach dem naechsten Whitespace
    # kein Buchstabe ist und das Uncertainty-Pattern insgesamt nicht matcht;
    # die Fallback-Zahl-Extraktion liefert [5, 10, 0.3], via ``hi < lo``-
    # Anti-Kollaps auf (5.0, 5.0) - die publizierte Range-Grenze wird
    # verworfen, weil die Notation ohnehin mehrdeutig ist (Range oder
    # Range-mit-Toleranz?), das Center-only-Fallback ist die konservative Wahl.
    assert csv_loaders.parse_range("5 to 10 ± 0.3") == (5.0, 5.0)


def test_parse_range_prozent_promille_range_ohne_whitespace_um_bindestrich():
    """Range-Notation ``N%-M%`` / ``N‰-M‰`` ohne Whitespace um den Bindestrich
    liefert beide Bereichsgrenzen (keine Sign-Bindung an die obere Grenze).

    In Sammler-Notizen sind Prozent-/Promille-Bereichs-Angaben ohne
    Whitespace um den Bindestrich der praxis-verbreitetste Kompakt-Stil
    ("Cu-Gehalt 5%-10% (XRF)", "Fluid-Einschluss-Salinitaet 3%-8%",
    "Isotopen-Fraktionierung δ13C 0.5‰-2.5‰"). Vor dem Fix fiel der
    zu enge Sign-Lookbehind auf ``[5, -10]``, was via ``if hi < lo``-
    Kollaps stille auf ``(5.0, 5.0)`` reduzierte und die obere Grenze
    verwarf - silenter Datenverlust auf ppm-nahen Konzentrations- und
    Isotopen-Feldern. Fix erweitert die Sign-Blockierung ``(?<![\\d.])-``
    auf ``(?<![\\d.%‰])-`` und beruecksichtigt die Wert-Terminatoren
    ``%``/``‰`` als sign-blockierende Vorgaenger.
    """
    # Prozent-Range ohne Whitespace um den Bindestrich
    assert csv_loaders.parse_range("5%-10%") == (5.0, 10.0)
    assert csv_loaders.parse_range("5%-10") == (5.0, 10.0)
    assert csv_loaders.parse_range("5.5%-10.5%") == pytest.approx((5.5, 10.5))
    assert csv_loaders.parse_range("0%-100%") == (0.0, 100.0)
    # Promille-Range (Isotopen-Fraktionierung, Wasser-Chemie)
    assert csv_loaders.parse_range("0.5‰-2.5‰") == pytest.approx((0.5, 2.5))
    assert csv_loaders.parse_range("1‰-3‰") == (1.0, 3.0)
    # Whitespace-Kombinationen: bereits vor dem Fix korrekt, hier als
    # Regress-Anker (das Fix darf keine dieser Formen brechen)
    assert csv_loaders.parse_range("5% - 10%") == (5.0, 10.0)
    assert csv_loaders.parse_range("5 % - 10 %") == (5.0, 10.0)
    assert csv_loaders.parse_range("5 %-10 %") == (5.0, 10.0)
    assert csv_loaders.parse_range("5%- 10%") == (5.0, 10.0)
    assert csv_loaders.parse_range("5-10%") == (5.0, 10.0)
    # DE-Komma-Dezimal im Prozent-Range
    assert csv_loaders.parse_range("5,5%-10,5%") == pytest.approx((5.5, 10.5))
    # Range mit "bis"/"to"-Wort-Trenner (kein Sign-Konflikt, aber
    # Konsistenz-Anker fuer Prozent-Notation)
    assert csv_loaders.parse_range("5% bis 10%") == (5.0, 10.0)
    assert csv_loaders.parse_range("5% to 10%") == (5.0, 10.0)
    # Regress-Anker: Negativ-Vorzeichen bleibt aktiv an legitimen
    # Start-Positionen (String-Anfang, Whitespace, Komma, Semikolon,
    # Klammer, andere Nicht-Wert-Terminatoren) - der Fix darf die
    # Negativ-Semantik nur an %/‰-Positionen blockieren
    assert csv_loaders.parse_range("-5.5") == (-5.5, -5.5)
    assert csv_loaders.parse_range("-5-10") == (-5.0, 10.0)
    assert csv_loaders.parse_range("-10 - -5") == (-10.0, -5.0)
    assert csv_loaders.parse_range("5, -10") == (5.0, 5.0)   # inverted collapse
    assert csv_loaders.parse_range("-15.5 ± 0.5‰") == pytest.approx((-16.0, -15.0))
    # Regress-Anker: reine Prozent-/Promille-Einzelwerte unveraendert
    assert csv_loaders.parse_range("5%") == (5.0, 5.0)
    assert csv_loaders.parse_range("5‰") == (5.0, 5.0)
    assert csv_loaders.parse_range("100%") == (100.0, 100.0)
    # Regress-Anker: Uncertainty mit Prozent-Suffix unveraendert (der
    # dedizierte ±-Zweig matcht vor der Range-Zahl-Extraktion)
    assert csv_loaders.parse_range("5.5% ± 0.3%") == pytest.approx((5.2, 5.8))
    assert csv_loaders.parse_range("5.5(3)%") == pytest.approx((5.2, 5.8))
    # Regress-Anker: Basis-Range ohne Prozent unveraendert
    assert csv_loaders.parse_range("5-10") == (5.0, 10.0)
    assert csv_loaders.parse_range("5.5-10.5") == pytest.approx((5.5, 10.5))
    # Regress-Anker: mol%/wt%/at% (Prozent als Teil eines mehrbuchstabigen
    # Einheit-Tokens) bleibt Range-Grenze, nicht sign-blockierender Terminator
    assert csv_loaders.parse_range("5.5 mol% - 10.5 mol%") == pytest.approx((5.5, 10.5))
    assert csv_loaders.parse_range("5 wt% - 10 wt%") == (5.0, 10.0)


def test_parse_range_uncertainty_mit_trailing_satzzeichen():
    """Uncertainty-Notation mit Trailing-Satzzeichen (``.``, ``,``, ``;``,
    ``:``, ``!``, ``?``) behaelt die publizierte Toleranz.

    In Sammler-Notizen und Excel-CSV-Zeilen ist es sehr verbreitet, den Wert
    mit Toleranz am Ende eines Satzes oder einer Zeilen-Zelle mit einem
    Punkt/Komma/Semikolon abzuschliessen ("Dichte 2.65 ± 0.05.",
    "Haerte 5.5 ± 0.3, siehe Literatur X", "5.5(3);"). Vor dem Fix
    ankerten beide Uncertainty-Patterns strikt auf ``\\s*$`` - jedes
    Trailing-Satzzeichen blockte den End-Anker-Match und die Formen fielen
    still auf die Fallback-Zahl-Extraktion via ``[center, tol]``-inverted-
    range-Kollaps auf ``(center, center)`` durch (Toleranz verloren). Fix
    ergaenzt beide Patterns um eine optionale Trailing-Satzzeichen-Klasse
    ``[.,;:!?]?`` vor dem End-Anker.
    """
    # ±-Langform mit einzelnem Trailing-Satzzeichen
    assert csv_loaders.parse_range("5.5 ± 0.3.") == pytest.approx((5.2, 5.8))
    assert csv_loaders.parse_range("5.5 ± 0.3,") == pytest.approx((5.2, 5.8))
    assert csv_loaders.parse_range("5.5 ± 0.3;") == pytest.approx((5.2, 5.8))
    assert csv_loaders.parse_range("5.5 ± 0.3:") == pytest.approx((5.2, 5.8))
    assert csv_loaders.parse_range("5.5 ± 0.3!") == pytest.approx((5.2, 5.8))
    assert csv_loaders.parse_range("5.5 ± 0.3?") == pytest.approx((5.2, 5.8))
    # Ohne Whitespace um ±
    assert csv_loaders.parse_range("5.5±0.3.") == pytest.approx((5.2, 5.8))
    assert csv_loaders.parse_range("5.5±0.3,") == pytest.approx((5.2, 5.8))
    assert csv_loaders.parse_range("5.5±0.3;") == pytest.approx((5.2, 5.8))
    # ASCII-Ersatzform (+/-, +-) mit Trailing-Satzzeichen
    assert csv_loaders.parse_range("5.5 +/- 0.3.") == pytest.approx((5.2, 5.8))
    assert csv_loaders.parse_range("5.5 +/- 0.3,") == pytest.approx((5.2, 5.8))
    assert csv_loaders.parse_range("5.5 +- 0.3;") == pytest.approx((5.2, 5.8))
    # IUCr-Kompaktform mit Trailing-Satzzeichen
    assert csv_loaders.parse_range("5.5(3).") == pytest.approx((5.2, 5.8))
    assert csv_loaders.parse_range("5.5(3),") == pytest.approx((5.2, 5.8))
    assert csv_loaders.parse_range("5.5(3);") == pytest.approx((5.2, 5.8))
    assert csv_loaders.parse_range("5.5(3):") == pytest.approx((5.2, 5.8))
    assert csv_loaders.parse_range("2.65(5),") == pytest.approx((2.60, 2.70))
    assert csv_loaders.parse_range("100(2).") == (98.0, 102.0)
    # Mit direkt anhaengender Einheit + Trailing-Satzzeichen
    assert csv_loaders.parse_range("5.5 ± 0.3mm,") == pytest.approx((5.2, 5.8))
    assert csv_loaders.parse_range("5.5 ± 0.3mm.") == pytest.approx((5.2, 5.8))
    assert csv_loaders.parse_range("2.65 ± 0.05g/cm³,") == pytest.approx((2.60, 2.70))
    assert csv_loaders.parse_range("2.65(5)g/cm³.") == pytest.approx((2.60, 2.70))
    # Mit Whitespace-getrennter Einheit + Trailing-Satzzeichen
    assert csv_loaders.parse_range("5.5 ± 0.3 mm,") == pytest.approx((5.2, 5.8))
    assert csv_loaders.parse_range("2.65 ± 0.05 g/cm³.") == pytest.approx((2.60, 2.70))
    assert csv_loaders.parse_range("5.5(3) Mohs;") == pytest.approx((5.2, 5.8))
    # Mit Trailing-Klammer-Annotation + Trailing-Satzzeichen
    assert csv_loaders.parse_range("5.5 ± 0.3 (Literatur).") == pytest.approx((5.2, 5.8))
    assert csv_loaders.parse_range("5.5 ± 0.3 (Ref),") == pytest.approx((5.2, 5.8))
    assert csv_loaders.parse_range("5.5(3) [NIST-2018].") == pytest.approx((5.2, 5.8))
    assert csv_loaders.parse_range("100(2) {IUCr};") == (98.0, 102.0)
    # Mit Prozent-/Promille-Suffix + Trailing-Satzzeichen
    assert csv_loaders.parse_range("5.5% ± 0.3%.") == pytest.approx((5.2, 5.8))
    assert csv_loaders.parse_range("5.5(3)%,") == pytest.approx((5.2, 5.8))
    assert csv_loaders.parse_range("-15.5 ± 0.5‰.") == pytest.approx((-16.0, -15.0))
    # Trailing-Whitespace nach Satzzeichen toleriert
    assert csv_loaders.parse_range("5.5 ± 0.3, ") == pytest.approx((5.2, 5.8))
    assert csv_loaders.parse_range("5.5 ± 0.3.  ") == pytest.approx((5.2, 5.8))
    assert csv_loaders.parse_range("5.5(3);  ") == pytest.approx((5.2, 5.8))
    # Regress-Anker: ohne Trailing-Satzzeichen unveraendert
    assert csv_loaders.parse_range("5.5 ± 0.3") == pytest.approx((5.2, 5.8))
    assert csv_loaders.parse_range("5.5(3)") == pytest.approx((5.2, 5.8))
    assert csv_loaders.parse_range("5.5 ± 0.3 mm") == pytest.approx((5.2, 5.8))
    # Regress-Anker: Trailing-Freitext nach Satzzeichen fuehrt weiter zum
    # Fallback (kein Match des Uncertainty-Zweigs, kein Ausschnitt-Match durch
    # die neue optionale Satzzeichen-Klasse). Der Fallback liefert
    # ``[center, tol]`` und kollabiert via ``if hi < lo`` auf ``(center, center)``
    # - identisch zum Verhalten vor dem Fix, das Fix ist strikt additiv fuer
    # die reine Satzzeichen-Terminator-Position.
    assert csv_loaders.parse_range("5.5 ± 0.3, more text") == (5.5, 5.5)
    assert csv_loaders.parse_range("5.5 ± 0.3!!more") == (5.5, 5.5)
    # Freitext ohne Satzzeichen wird bereits vor dem Fix vom Trailing-Unit-
    # Wort-Zweig aufgesaugt (jedes Wort wird als Einheit interpretiert), so
    # dass ``"5.5(3) with note"`` als valide IUCr-Kompaktform + zwei Einheiten-
    # Tokens erkannt wird und die Toleranz behaelt - Regress-Anker fuer die
    # (ueberraschende, aber semantisch verlust-freie) alte Semantik.
    assert csv_loaders.parse_range("5.5(3) with note") == pytest.approx((5.2, 5.8))


def test_parse_range_klammer_annotation_wird_nicht_als_range_gelesen():
    """Klammer-umschlossene Freitext-Anhaenge sind Annotation, nicht Range-Grenze.

    In Sammler-Notizen sind Foto-/Katalog-/Referenz-Marker in Klammern
    strukturell separat vom Wert-Bereich: ``"5.5 (2020)"`` bedeutet "Wert 5.5,
    Referenz-Jahr 2020" - nicht "Wert-Bereich 5.5 bis 2020". Vor dem Fix
    lieferte die generische Fallback-Zahl-Extraktion alle Zahlen inkl. der
    Annotation als vermeintliche Range-Grenzen und produzierte mineralogisch/
    sammlungslogisch unsinnige Bereiche:

    * ``"5.5 (2020)"``        -> (5.5, 2020.0)   (Jahr als hi statt Annotation)
    * ``"5-7 Mohs (Nr. 42)"`` -> (5.0, 42.0)     (Katalog-Nr. als hi)
    * ``"2.65 (Ref 42)"``     -> (2.65, 42.0)    (Ref-Nr. als hi)
    * ``"5.5 [2024]"``        -> (5.5, 2024.0)   (Jahr in eckigen Klammern)

    Bei allen inverted-Range-Faellen (Annotation-Zahl < Zentrum-Zahl) griff
    der ``if hi < lo``-Fallback und kollabierte auf ``(lo, lo)`` - aber
    sobald die Annotation *groesser* als das Zentrum war (Jahres-Marker,
    hohe Katalog-Nummern), wurde die Annotation stille als hoher Range-Wert
    gelesen.

    Der Fix strippt runde/eckige/geschweifte Klammer-Annotationen inkl.
    Verschachtelung vor der Zahl-Extraktion. Kritischer Rueckfall-Schutz:
    wenn der Wert *selbst* in Klammern steht (``"(5-7)"``, ``"(2.65)"``,
    ``"[5,7]"`` als mathematisches Intervall), wird der Original-String
    beibehalten - die Klammer-Umhuellung wird dann als Wert-Traeger
    interpretiert, nicht als Annotation.
    """
    # Jahres-Annotation nach Wert (Foto-Referenz / Kauf-Jahr). Vorher: (5.5, 2020.0).
    assert csv_loaders.parse_range("5.5 (2020)") == (5.5, 5.5)
    assert csv_loaders.parse_range("5.5 [2024]") == (5.5, 5.5)
    # Katalog-/Referenz-Nummer nach Wert. Vorher: (2.65, 42.0).
    assert csv_loaders.parse_range("2.65 (Ref 42)") == (2.65, 2.65)
    assert csv_loaders.parse_range("2.65 (Nr. 42)") == (2.65, 2.65)
    # Katalog-Nummer nach Range. Vorher: (5.0, 42.0).
    assert csv_loaders.parse_range("5-7 (Nr. 42)") == (5.0, 7.0)
    assert csv_loaders.parse_range("5-7 Mohs (siehe Ref. 42)") == (5.0, 7.0)
    # Jahres-Annotation nach Range in eckigen Klammern. Vorher: (5.5, 2024.0).
    assert csv_loaders.parse_range("5.5-7.0 [Verified 2024]") == (5.5, 7.0)
    # Freitext-Annotation ohne Zahl (bleibt aus Symmetrie-Gruenden ebenfalls
    # gestrippt, damit trailing-Freitext in Klammern kein Rest-Whitespace
    # als Wert-Erweiterung anschleppt).
    assert csv_loaders.parse_range("5.5 (Foto)") == (5.5, 5.5)
    assert csv_loaders.parse_range("5.5 [verified]") == (5.5, 5.5)
    assert csv_loaders.parse_range("5.5 {geerbt}") == (5.5, 5.5)
    # Verschachtelte Klammern werden vom Innen-nach-Aussen aufgeloest.
    assert csv_loaders.parse_range("5.5 (Foto (gut))") == (5.5, 5.5)
    assert csv_loaders.parse_range("5-7 [Range (Mohs) verified]") == (5.0, 7.0)
    # Klammer-Freitext-Anhang nach Uncertainty wird jetzt vom erweiterten
    # Uncertainty-Pattern direkt matched (Trailing-Klammer-Erweiterung), sodass
    # die publizierte Toleranz erhalten bleibt. Vorher: die Klammer blockte
    # das End-Anker-Matching, und der Fallback lieferte via Strip nur den
    # Center ("5.5 ± 0.3 (Ref 42)" -> (5.5, 5.5)); mit der Erweiterung matcht
    # die Klammer-Annotation als Trailing-Zweig und die Toleranz-Grenzen
    # bleiben erhalten ((5.2, 5.8) fuer die ±-Form, (5.2, 5.8) fuer die
    # IUCr-Kompaktform).
    assert csv_loaders.parse_range("5.5 ± 0.3 (Ref 42)") == pytest.approx((5.2, 5.8))
    assert csv_loaders.parse_range("5.5(3) (Ref 42)") == pytest.approx((5.2, 5.8))
    # Regression-Anker: Wert *selbst* in Klammern bleibt unangetastet.
    # Rueckfall-Schutz greift, weil nach dem Strip keine Ziffern mehr uebrig
    # waeren - die Klammer wird als Wert-Traeger interpretiert.
    assert csv_loaders.parse_range("(5-7)") == (5.0, 7.0)
    assert csv_loaders.parse_range("(2.65)") == (2.65, 2.65)
    # ``[5-7]`` als mathematisches Intervall mit ASCII-Bindestrich - der
    # Komma-Trenner ``[5,7]`` bleibt bewusst ausgespart, weil er mit dem
    # DE-Dezimal-Komma kollidiert (``5,7`` waere gleichzeitig "5 komma 7"
    # als 5.7 und Zweier-Liste "5 und 7"); die Klammer-Umhuellung mit
    # Bindestrich ist eindeutig.
    assert csv_loaders.parse_range("[5-7]") == (5.0, 7.0)
    assert csv_loaders.parse_range("{5-7}") == (5.0, 7.0)
    # Regression-Anker: bereits vorhandene Grenzform-Tests bleiben unveraendert.
    assert csv_loaders.parse_range("5.5 (3.0)") == (5.5, 5.5)   # inverted-Kollaps


def test_parse_range_wissenschaftliche_notation():
    """Zahl-Token mit Exponent ``E±N`` wird als scientific-notation gelesen.

    In Mineralogie-/Physik-Publikationen die Standardform fuer Werte, die
    viele Groessenordnungen ueberspannen: Absorptions-Querschnitte in cm²
    (``2.5e-19``), Halbwertszeiten von Isotopen in Jahren (``4.5e9``),
    Kalibrier-Konstanten aus spektroskopischen Messungen (``1.5e-3``),
    Fluoreszenz-Lebensdauern in Sekunden (``3e-6``). Vor dem Fix wurde
    ``1e3`` als zwei Tokens ``1`` und ``3`` gelesen (inverted range,
    Fallback (1.0, 1.0)); ``1.5e-3`` lieferte ``(1.5, 3.0)`` als
    vermeintlicher Range ``1.5 bis 3`` - beide Faelle verwerfen die
    Groessenordnung stille.

    Kollisionsfreiheit zu den Uncertainty-Patterns (Langform ``N ± M``
    und IUCr-Kompaktform ``N(M)``): der Exponent-Match greift nur, wenn
    weder die ± noch die Klammer-Struktur den Freitext strukturell
    umschliesst - beide Uncertainty-Zweige fangen ihren Fall via
    ^...$-Anker vor der generischen Zahlen-Extraktion ab, sodass
    ``5.5(3)`` und ``5.5 ± 0.3`` weiterhin die publizierte Toleranz
    liefern und nicht als scientific-notation-Kollision fehlinterpretiert
    werden.
    """
    # Ganzzahl-Mantisse mit positivem Exponent: klassische Compact-Form fuer
    # Werte in wissenschaftlichen Notizen.
    assert csv_loaders.parse_range("1e3") == (1000.0, 1000.0)
    # Explizites Plus-Vorzeichen (Excel-DE-Auto-Format schreibt haeufig
    # ``1,5E+03``; NIST-CODATA-Tabellen ``1.5E+3`` mit sichtbarem Plus).
    assert csv_loaders.parse_range("1.5E+3") == (1500.0, 1500.0)
    # Negativer Exponent: der Standard-Fall fuer sub-Einheiten-Groessen
    # (Kalibrier-Konstanten, Absorptions-Querschnitte, HWZ-Bruchteile).
    assert csv_loaders.parse_range("1.5e-3") == (0.0015, 0.0015)
    # Case-insensitive: ``e`` und ``E`` beide gueltig (LaTeX-Rendering
    # schreibt ``e``, Excel-Auto-Format ``E``).
    assert csv_loaders.parse_range("2.65e0") == (2.65, 2.65)
    assert csv_loaders.parse_range("2.65E0") == (2.65, 2.65)
    # DE-Komma-Dezimal in der Mantisse (deutsche Publikationen, Excel-DE
    # schreibt ``1,5E-03`` mit Komma-Dezimal); der Exponent selbst ist
    # immer ganzzahlig ohne Locale-Problem.
    assert csv_loaders.parse_range("1,5e-3") == (0.0015, 0.0015)
    # Astronomische Groessenordnungen (Halbwertszeit U-238 in Jahren,
    # Absorptions-Querschnitt in cm²) - decken den float-Wertebereich ab.
    assert csv_loaders.parse_range("4.5e9") == (4.5e9, 4.5e9)
    assert csv_loaders.parse_range("2.5e-19") == (2.5e-19, 2.5e-19)
    # Echter Range mit scientific notation auf beiden Seiten (Kalibrier-
    # Bereich, Absorptions-Spektrum): der Range-Trenner ist der Bindestrich
    # zwischen den beiden Exponent-Zahlen, nicht der Minus-Anker des
    # rechten Exponents.
    assert csv_loaders.parse_range("1e3 - 5e3") == (1000.0, 5000.0)
    # Range mit negativem Exponent auf beiden Seiten: sicherstellen, dass
    # die Zahl-Zerlegung greedy den ganzen Exponent-Token nimmt und nicht
    # vorzeitig beim Bindestrich abbricht.
    assert csv_loaders.parse_range("1e-3 - 5e-3") == (0.001, 0.005)
    # Einzelner Exponent ohne Mantisse-Dezimalstelle (``1e0`` = 1) - lieferte
    # frueher ueber die Zwei-Zahl-Zerlegung (1.0, 0.0) → collapsed (1.0, 1.0).
    # Neues Verhalten: exponent wird ausgewertet, liefert dasselbe (1.0, 1.0)
    # aber ueber den semantisch korrekten Pfad.
    assert csv_loaders.parse_range("1e0") == (1.0, 1.0)
    # Kollisionsfreiheit mit den Uncertainty-Zweigen: die publizierte
    # Toleranz-Semantik bleibt Vorrang; ``5.5(3)`` liefert weiterhin die
    # Klammer-Unsicherheit, kein scientific-notation-Fallback, und
    # ``5.5 ± 0.3`` bleibt Langform-Uncertainty. Regression-Anker fuer
    # den Fall, dass jemand die Zweige umsortiert.
    assert csv_loaders.parse_range("5.5(3)") == pytest.approx((5.2, 5.8))
    assert csv_loaders.parse_range("5.5 ± 0.3") == pytest.approx((5.2, 5.8))


def test_parse_range_explizit_multiplikation_zehnerpotenz():
    """Explizit-Multiplikations-Form ``N · 10^M`` / ``N × 10³`` als Scientific-Notation.

    In wissenschaftlichen Publikationen und Sammler-Notizen aus PDF-/Word-/
    LaTeX-Quellen ist die Explizit-Form haeufiger als die kompakte
    E-Notation: Word- und LaTeX-Autoformat setzen das Multiplikations-
    Zeichen typografisch (``·`` U+00B7, ``×`` U+00D7) und den Exponenten
    als Unicode-Superscript (``10³`` / ``10⁻³``). Vor dem Fix las
    :data:`_NUM_RE` z.B. ``"2.5·10^3"`` als drei Tokens ``[2.5, 10, 3]``,
    liefert per ``if hi < lo``-Kollaps ``(2.5, 3.0)`` (Faktor 10^3 verloren)
    - bei der Migration aus wissenschaftlichen Quellen entstand damit
    silenter Groessenordnungs-Verlust in Absorptions-/Kalibrier-/HWZ-Werten.

    :func:`_normalize_explicit_mult_power10` schreibt beide Zweige (Caret-
    ASCII-Exponent und Unicode-Superscript-Exponent) auf die Standard-
    E-Notation ``NeM`` um, die :data:`_NUM_RE` transparent als eine Zahl liest.
    """
    # ASCII-Caret-Form mit den vier gebrauchlichen Multiplikations-Zeichen
    # (Middle-Dot U+00B7, Multiplication-Sign U+00D7, ASCII-Stern, ASCII-x).
    assert csv_loaders.parse_range("2.5·10^3") == (2500.0, 2500.0)
    assert csv_loaders.parse_range("2.5×10^3") == (2500.0, 2500.0)
    assert csv_loaders.parse_range("2.5*10^3") == (2500.0, 2500.0)
    assert csv_loaders.parse_range("2.5x10^3") == (2500.0, 2500.0)
    assert csv_loaders.parse_range("2.5X10^3") == (2500.0, 2500.0)
    # Whitespace zwischen Mantisse, Operator und ``10^`` toleriert (Print-/
    # PDF-Setz mit klassischer Space-um-Operator-Konvention).
    assert csv_loaders.parse_range("2.5 · 10^3") == (2500.0, 2500.0)
    assert csv_loaders.parse_range("2.5 × 10^3") == (2500.0, 2500.0)
    assert csv_loaders.parse_range("2.5 · 10 ^ 3") == (2500.0, 2500.0)
    # Negativer Exponent (Absorptions-/Kalibrier-/HWZ-Werte < 1).
    assert csv_loaders.parse_range("2.5·10^-3") == pytest.approx((0.0025, 0.0025))
    assert csv_loaders.parse_range("2.5 × 10^-3") == pytest.approx((0.0025, 0.0025))
    # Explizites Plus-Vorzeichen am Exponenten (Excel-DE-Auto-Format-Konvention).
    assert csv_loaders.parse_range("2.5·10^+3") == (2500.0, 2500.0)
    # Unicode-Superscript-Exponent statt Caret-ASCII: Word-/LaTeX-Autoformat
    # setzt ``10^3`` als ``10³`` (U+00B3) und ``10^-3`` als ``10⁻³``
    # (U+207B MINUS + U+00B3).
    assert csv_loaders.parse_range("2.5·10³") == (2500.0, 2500.0)
    assert csv_loaders.parse_range("2.5×10³") == (2500.0, 2500.0)
    assert csv_loaders.parse_range("2.5·10⁻³") == pytest.approx((0.0025, 0.0025))
    assert csv_loaders.parse_range("2.5×10⁻³") == pytest.approx((0.0025, 0.0025))
    assert csv_loaders.parse_range("2.5×10⁺³") == (2500.0, 2500.0)
    # Mehrstelliger Unicode-Superscript-Exponent (``10¹²`` fuer Avogadro-
    # Groessenordnungen).
    assert csv_loaders.parse_range("6.022·10²³") == pytest.approx((6.022e23, 6.022e23))
    # DE-Komma-Dezimal in der Mantisse (DE-Publikationen, DE-Excel-Export
    # schreiben ``2,5·10^3`` statt ``2.5·10^3``).
    assert csv_loaders.parse_range("2,5·10^3") == (2500.0, 2500.0)
    assert csv_loaders.parse_range("2,5·10³") == (2500.0, 2500.0)
    # Negatives Vorzeichen an der Mantisse (thermische/isotopische Werte
    # ausserhalb der klassischen Mineralogie).
    assert csv_loaders.parse_range("-2.5·10^3") == (-2500.0, -2500.0)
    assert csv_loaders.parse_range("-2.5·10³") == (-2500.0, -2500.0)
    # Leading-Dot-Dezimal in der Mantisse (US-typographische Konvention).
    assert csv_loaders.parse_range(".5·10^3") == (500.0, 500.0)
    # Range mit Explizit-Form auf beiden Seiten (Kalibrier-/Absorptions-
    # Spektrum-Grenzen, oft als ``N × 10^k – M × 10^k`` gesetzt).
    assert csv_loaders.parse_range("1×10^3 to 2×10^3") == (1000.0, 2000.0)
    assert csv_loaders.parse_range("1·10³ – 2·10³") == (1000.0, 2000.0)
    # Trailing-Einheit ohne Whitespace-Problem (die Einheiten-Suffix-Zahl-
    # Blockade aus dem ``cm3``/``m2``-Zweig bleibt unabhaengig gueltig).
    assert csv_loaders.parse_range("2.5·10^3 g/cm³") == (2500.0, 2500.0)
    assert csv_loaders.parse_range("0.5·10^-3 cm²") == pytest.approx((0.0005, 0.0005))
    # Annaeherungs-Praefix vor der Explizit-Form (Sammler-Notiz "ca.").
    assert csv_loaders.parse_range("ca. 2.5·10^3") == (2500.0, 2500.0)
    # Regression: Kompakte E-Notation bleibt unveraendert (die Normalisierung
    # macht Explizit → Kompakt, nicht umgekehrt).
    assert csv_loaders.parse_range("2.5e3") == (2500.0, 2500.0)
    # Regression: Multiplikations-Zeichen zwischen Zahlen OHNE ``10^``-Kern
    # bleibt als getrennter Zahl-Trenner unbehelligt (Dimensions-Notation
    # ``5cm × 3cm`` → ``5cm`` und ``3cm``, jede Zahl separat gelesen).
    assert csv_loaders.parse_range("5 × 3") == (5.0, 3.0) or \
        csv_loaders.parse_range("5 × 3") == (5.0, 5.0)  # inverted-collapse
    assert csv_loaders.parse_range("5cm x 3cm") == (5.0, 3.0) or \
        csv_loaders.parse_range("5cm x 3cm") == (5.0, 5.0)  # inverted-collapse
    # Regression: ``10^N`` OHNE Mantisse-vor-dem-Operator bleibt unbehelligt -
    # das Pattern verlangt strukturell die ``N × 10^M``-Signatur mit
    # explizitem Multiplikations-Zeichen.
    assert csv_loaders.parse_range("10^3") == (10.0, 10.0)
    # Regression: SI-Einheiten-Bruch ``EUR·kg^-1`` hat keinen ``10``-Kern
    # nach dem Middle-Dot, matcht das Explizit-Pattern nicht und bleibt
    # in der bestehenden Zahl-Extraktion.
    assert csv_loaders.parse_range("1 EUR·kg^-1") == (1.0, 1.0)
    # Regression: Word-artige Multiplikation zwischen zwei nicht-Zehner-
    # Werten (``5 × 3.14`` ist eine Berechnung, keine Groessenordnung).
    result = csv_loaders.parse_range("5 × 3.14")
    assert result == (5.0, 3.14) or result == (5.0, 5.0)


def test_parse_range_explizit_multiplikation_dot_operator_u22c5():
    """DOT OPERATOR ``⋅`` (U+22C5) als Multiplikations-Zeichen aequivalent zu MIDDLE DOT.

    ``⋅`` (U+22C5) und ``·`` (U+00B7) sehen visuell nahezu identisch aus, sind
    aber unicode-kategorisch getrennt: U+00B7 ist General-Punctuation (``Po``),
    U+22C5 ist Math-Operator (``Sm``). LaTeX ``\\cdot`` und MathJax rendern
    beim Kompilieren/Anzeigen zu U+22C5; wer aus MathJax-gerenderten
    Wikipedia-Info-Boxen, aus LaTeX-Quellen exportierten Referenz-Tabellen
    oder aus Publikations-Snippets (JSTOR-PDF, Wolfram Alpha) einen Wert wie
    ``5.5⋅10⁻³`` in eine Sammlungs-Notiz kopiert, bringt den Dot-Operator-
    Codepunkt mit; bisher fielen exakt diese Copy-Paste-Faelle auf den
    ``(mantisse, 10.0)``-Fehlpfad, weil die Multiplikations-Klasse in
    :data:`_EXPLICIT_MULT_POWER10_CARET` / :data:`_EXPLICIT_MULT_POWER10_SUPER`
    / :data:`_EXPLICIT_EXPONENT_RE` nur den Middle-Dot enthielt.

    Bug-Signatur vor dem Fix (unterschieden nach Publikations-Quelle):
    ``2.5⋅10^3`` (Mantisse * 10^3, gaengige Absorptions-Querschnitts-Notation
    aus MathJax-Wikipedia) lieferte ``(2.5, 10.0)`` statt ``(2500.0, 2500.0)``
    - Groessenordnung 10^3 komplett verloren; die "10" wurde als vermeintliche
    obere Range-Grenze in den CHF-/Gewicht-/Dichte-Slot gesetzt und
    korrumpierte alle nachgelagerten SUM/AVG-Aggregationen.
    ``6.022⋅10²³`` (Avogadro-Konstante aus dem CRC Handbook per LaTeX
    ``6.022 \\cdot 10^{23}``) fiel auf ``(6.022, 10.0)`` statt ``6.022e23`` -
    ein Groessenordnungs-Verlust von 22 Dekaden, mineralogisch komplett
    unsinnig.

    Der Fix erweitert alle drei Multiplikations-Char-Klassen ``[·×*xX]`` bzw.
    ``[·×*]|[xX]`` um U+22C5 zu ``[·⋅×*xX]`` bzw. ``[·⋅×*]|[xX]``. Beide
    Formen kollabieren dann auf denselben Substitutions-Pfad zu ``NeM``,
    :data:`_NUM_RE` liest die publizierte Groessenordnung als eine Zahl statt
    als Range-Grenze.

    Test spiegelt die Struktur von :func:`test_parse_range_explizit_multiplikation_zehnerpotenz`
    auf die U+22C5-Achse: ASCII-Caret-Form (positiv/negativ/Plus-Sign-Explizit),
    Unicode-Superscript-Form, Whitespace-Toleranz, DE-Komma-Dezimal, Leading-
    Dot-Dezimal, Range mit U+22C5 auf beiden Seiten, Kombination mit
    Trailing-Einheit und Approx-Praefix. Regressions-Anker stellen sicher,
    dass Middle-Dot und Multiplication-Sign weiterhin funktionieren, und dass
    U+22C5 ohne ``10^``-Kern (in SI-Einheiten-Notation wie ``EUR⋅kg⁻¹``)
    unbehelligt bleibt.
    """
    # ASCII-Caret-Form mit U+22C5 (Direct-Copy aus MathJax-Rendering).
    assert csv_loaders.parse_range("2.5⋅10^3") == (2500.0, 2500.0)
    assert csv_loaders.parse_range("2.5⋅10^-3") == pytest.approx((0.0025, 0.0025))
    assert csv_loaders.parse_range("2.5⋅10^+3") == (2500.0, 2500.0)
    # Whitespace zwischen Mantisse, Dot-Operator und ``10^``: LaTeX-Setz
    # ``\, \cdot \, `` mit Thin-Space um den Operator.
    assert csv_loaders.parse_range("2.5 ⋅ 10^3") == (2500.0, 2500.0)
    assert csv_loaders.parse_range("2.5 ⋅ 10 ^ 3") == (2500.0, 2500.0)
    # Unicode-Superscript-Form (typischer LaTeX-PDF-Export mit Math-Rendering).
    assert csv_loaders.parse_range("2.5⋅10³") == (2500.0, 2500.0)
    assert csv_loaders.parse_range("2.5⋅10⁻³") == pytest.approx((0.0025, 0.0025))
    assert csv_loaders.parse_range("2.5⋅10⁺³") == (2500.0, 2500.0)
    # Mehrstelliger Unicode-Superscript-Exponent (Avogadro-Konstante aus CRC
    # Handbook per LaTeX ``6.022 \cdot 10^{23}`` -> MathJax -> U+22C5).
    assert csv_loaders.parse_range("6.022⋅10²³") == pytest.approx((6.022e23, 6.022e23))
    # DE-Komma-Dezimal in der Mantisse (DE-Publikationen mit LaTeX-``\cdot``).
    assert csv_loaders.parse_range("2,5⋅10^3") == (2500.0, 2500.0)
    assert csv_loaders.parse_range("2,5⋅10³") == (2500.0, 2500.0)
    # Negatives Vorzeichen an der Mantisse.
    assert csv_loaders.parse_range("-2.5⋅10^3") == (-2500.0, -2500.0)
    assert csv_loaders.parse_range("-2.5⋅10³") == (-2500.0, -2500.0)
    # Leading-Dot-Dezimal in der Mantisse (US-Konvention).
    assert csv_loaders.parse_range(".5⋅10^3") == (500.0, 500.0)
    # Range mit U+22C5-Explizit-Form auf beiden Seiten (Kalibrier-/Absorptions-
    # Spektrum-Grenzen aus einer LaTeX-Tabelle kopiert).
    assert csv_loaders.parse_range("1⋅10^3 to 2⋅10^3") == (1000.0, 2000.0)
    assert csv_loaders.parse_range("1⋅10³ – 2⋅10³") == (1000.0, 2000.0)
    # Trailing-Einheit direkt nach dem Superscript-Exponent (die Einheiten-
    # Suffix-Zahl-Blockade aus dem ``cm3``/``m2``-Zweig bleibt unabhaengig).
    assert csv_loaders.parse_range("2.5⋅10^3 g/cm³") == (2500.0, 2500.0)
    assert csv_loaders.parse_range("0.5⋅10^-3 cm²") == pytest.approx((0.0005, 0.0005))
    # Annaeherungs-Praefix (Sammler-Notiz "ca." mit U+22C5).
    assert csv_loaders.parse_range("ca. 2.5⋅10^3") == (2500.0, 2500.0)
    # Gemischte Explizit-Multiplikations-Zeichen im Range - links U+22C5,
    # rechts U+00B7 (Publikations-Snippets, die aus verschiedenen Quellen
    # zusammenkopiert wurden). Beide Zweige normalisieren auf ``NeM``.
    assert csv_loaders.parse_range("1⋅10^3 – 2·10^3") == (1000.0, 2000.0)
    assert csv_loaders.parse_range("1·10^3 – 2⋅10^3") == (1000.0, 2000.0)
    # Regression: Middle-Dot U+00B7 bleibt unveraendert funktional -
    # die Erweiterung fuegt U+22C5 hinzu, ersetzt U+00B7 nicht.
    assert csv_loaders.parse_range("2.5·10^3") == (2500.0, 2500.0)
    assert csv_loaders.parse_range("2.5·10³") == (2500.0, 2500.0)
    # Regression: Multiplication-Sign U+00D7 und ASCII-Formen unveraendert.
    assert csv_loaders.parse_range("2.5×10^3") == (2500.0, 2500.0)
    assert csv_loaders.parse_range("2.5*10^3") == (2500.0, 2500.0)
    assert csv_loaders.parse_range("2.5x10^3") == (2500.0, 2500.0)
    # Regression: U+22C5 OHNE ``10``-Kern in SI-Einheiten-Notation (Preis pro
    # Kilogramm als ``EUR⋅kg^-1``, aus LaTeX-Publikations-Setz kopiert)
    # matcht das Explizit-Pattern nicht (kein ``10`` als Zweitoperand), die
    # Zahl-Extraktion bleibt bei der Mantisse-1.
    assert csv_loaders.parse_range("1 EUR⋅kg^-1") == (1.0, 1.0)
    # Regression: U+22C5 ohne Mantisse davor (etwa ``⋅10^3`` in einem Fragment)
    # matcht nicht - das Pattern verlangt strukturell die vollstaendige
    # ``N × 10^M``-Signatur. Ohne Mantisse faellt der Ausdruck auf die
    # normale Zahl-Extraktion (findet ``10`` und ``3``).
    assert csv_loaders.parse_range("⋅10^3") == (10.0, 3.0) or \
        csv_loaders.parse_range("⋅10^3") == (10.0, 10.0)
    # Regression: U+22C5 zwischen Nicht-Zehner-Werten bleibt Trenner-artig
    # (``5 ⋅ 3.14`` ist eine mathematische Multiplikation, keine Groessen-
    # ordnungs-Notation - das Pattern greift wegen fehlendem ``10`` nicht).
    result = csv_loaders.parse_range("5 ⋅ 3.14")
    assert result == (5.0, 3.14) or result == (5.0, 5.0)


def test_parse_range_scientific_notation_overflow():
    """Overflow der Exponent-Notation (``1e400`` -> ``inf``) faellt auf ``(None, None)``.

    ``float()`` konvertiert Mantissen jenseits des IEEE-754-Bereichs
    (rund ``1.7976931348623157e+308``) stille zu ``+inf``/``-inf`` und
    ``inf ± inf`` bzw. ``inf - inf`` zu ``NaN``. Ohne Filter wanderten
    diese Werte transparent als vermeintlich gueltige Bereichsgrenzen in
    die Numeric-Felder (Wert_CHF, Gewicht_g, Dichte, Haerte) und
    korrumpierten stille alle nachgelagerten Operationen: SUM/AVG in der
    Statistik lieferten ``inf``, Sortierung nach Wert setzt den
    Overflow-Datensatz endlos an die Spitze, JSON-Export via
    ``json.dumps`` mit ``allow_nan=False`` verweigert die Serialisierung
    (Backup-CLI wuerde brechen) und ``allow_nan=True`` schreibt das
    JSON-spec-widrige Literal ``Infinity``. Vor dem Fix lieferte
    ``'1e400'`` -> ``(inf, inf)``, ``'1e400 ± 0.1'`` -> ``(inf, inf)`` und
    ``'5.5 - 1e400'`` -> ``(5.5, inf)``.

    Semantisch ist ein Token, das float nicht darstellen kann, aequivalent
    zu "kein gueltiger Wert" - konsistent mit der bestehenden ``(None,
    None)``-Rueckgabe fuer leere/nicht-parsbare Eingaben. Bei gemischten
    Ranges (endlich + overflow) bleibt der endliche Teil als (n, n)
    erhalten, damit die endliche Halb-Information nicht mit-verworfen
    wird.
    """
    # Reiner Overflow: das einzige Token ueberlaeuft, keine Zahl uebrig.
    assert csv_loaders.parse_range("1e400") == (None, None)
    assert csv_loaders.parse_range("1E400") == (None, None)
    assert csv_loaders.parse_range("2.5e999") == (None, None)
    # Explizit negativer Overflow (typografisch selten, aber float()-symmetrisch).
    assert csv_loaders.parse_range("-1e400") == (None, None)
    # Beide Range-Seiten ueberlaufen -> keine endliche Grenze uebrig.
    assert csv_loaders.parse_range("1e400 - 5e400") == (None, None)
    # Gemischt: nur eine Seite ueberlaeuft; die endliche Halb-Info bleibt
    # als Punkt-Wert erhalten (via inverted-range-Fallback nach der
    # finite-Filter-Reduktion).
    assert csv_loaders.parse_range("5.5 - 1e400") == (5.5, 5.5)
    assert csv_loaders.parse_range("1e400 - 5.5") == (5.5, 5.5)
    # Uncertainty-Zweige mit Overflow-Center: arithmetische Verkettung
    # (``inf ± tol`` bzw. ``inf(2)``) liefert ``inf``/``NaN``, wird
    # via ``_finite_pair`` auf ``(None, None)`` gemappt.
    assert csv_loaders.parse_range("1e400 ± 1e400") == (None, None)
    # Regression-Anker: normale scientific notation innerhalb des
    # float-Bereichs bleibt unveraendert (die Filter greift nur bei
    # Overflow, nicht bei allen Werten mit Exponent).
    assert csv_loaders.parse_range("4.5e9") == (4.5e9, 4.5e9)
    assert csv_loaders.parse_range("2.5e-19") == (2.5e-19, 2.5e-19)
    # Underflow zu subnormal/0.0 bleibt endlich und wird NICHT gefiltert -
    # 0 ist ein legitimer Zahl-Wert (Nullpunkt), im Gegensatz zu inf.
    assert csv_loaders.parse_range("1e-400") == (0.0, 0.0)


def test_parse_range_explizit_multiplikative_zehnerpotenz():
    """``N × 10^M`` / ``N · 10^M`` / ``N × 10ᴹ`` wird als scientific notation ``NeM`` gelesen.

    Explizit-multiplikative Form der wissenschaftlichen Zehnerpotenz ist der
    typografische Standard in Print-Publikationen (Mineralogie-Handbuecher
    Hollemann-Wiberg, Ternes Bio-Chemie, CRC Handbook of Chemistry and
    Physics, IUPAC Green Book, Kluwer Handbook of Minerals) und in LaTeX-/
    PDF-Publikationen; die kompakte E-Notation ``1.5e-3`` dominiert dagegen
    in Excel-/CSV-/Terminal-Ausgaben. Typische Anwendungsfelder sind
    Absorptions-Querschnitte in cm² (``2.5 × 10⁻¹⁹``), Loeslichkeitsprodukte
    (``1.5 × 10⁻⁹``), Aktivitaeten radioaktiver Isotope (``4.5 · 10⁹ a``),
    Kalibrier-Konstanten aus spektroskopischen Messungen (``1.5 × 10⁻³``),
    Fluoreszenz-Lebensdauern (``3 · 10⁻⁶``), Bragg-Winkel-Beugungs-Faktoren
    (``5.5 · 10⁻² Å``) und thermische Ausdehnungs-Koeffizienten (``β = 5.5
    × 10⁻⁶ K⁻¹``).

    Vor dem Fix fielen alle diese Formen still auf eine strukturell falsche
    Range-Interpretation ``(mantisse, 10.0)``: die generische ``_NUM_RE``-
    Extraktion las Mantisse und ``10`` als zwei separate Zahl-Tokens und
    lieferte den unsinnigen Range mit dem Basis-Radix als vermeintlicher
    Range-Grenze. Konkret: ``5.5 × 10^-3`` lieferte (5.5, 10.0) statt
    (0.0055, 0.0055) - Groessenordnung komplett verloren, Wert mit dem
    Basis-Radix vertauscht; ``2.5 · 10⁻¹⁹`` (Superskript-Form) analog auf
    (2.5, 10.0) (der Superskript-Exponent faellt aus ``_NUM_RE`` heraus,
    weil ``⁻¹⁹`` nicht in der ASCII-Zahl-Klasse liegt); ``1.5 * 10^3`` auf
    (1.5, 10.0). Bei der Migration aus Mineralogie-/Physik-Publikationen mit
    typografischer Explizit-Multiplikations-Notation entstand damit silenter
    Groessenordnungs-Datenverlust auf jeder Wert-Achse ueber viele
    Groessenordnungen hinweg.

    Kollisionsfreiheit zur bestehenden E-Notation (``1e-3`` bleibt
    unveraendert - hat keinen ``10``-Basis-Radix), zur Range-Notation
    (``5-10`` bleibt Range - kein Multiplikations-Zeichen), zur Uncertainty-
    Notation (``5 ± 3`` bleibt Uncertainty - kein Multiplikations-Zeichen),
    zur SI-Kompakt-Einheit (``g cm^-3`` bleibt Einheit - keine Mantisse
    davor), zur Dimensions-Notation (``5x10 cm`` bleibt Range - kein
    Exponent nach ``10``).
    """
    # ASCII-Asterisk-Multiplikation (Terminal-/Log-/E-Mail-Notiz ohne Unicode).
    assert csv_loaders.parse_range("5.5*10^-3") == pytest.approx((0.0055, 0.0055))
    assert csv_loaders.parse_range("5.5 * 10^-3") == pytest.approx((0.0055, 0.0055))
    assert csv_loaders.parse_range("5.5 * 10 ^ -3") == pytest.approx((0.0055, 0.0055))
    # Unicode Middle Dot U+00B7 (DE-Print-Publikations-Standard).
    assert csv_loaders.parse_range("5.5·10^-3") == pytest.approx((0.0055, 0.0055))
    assert csv_loaders.parse_range("5.5 · 10^-3") == pytest.approx((0.0055, 0.0055))
    # Unicode Multiplication Sign U+00D7 (EN-Print-Publikations-Standard).
    assert csv_loaders.parse_range("5.5×10^-3") == pytest.approx((0.0055, 0.0055))
    assert csv_loaders.parse_range("5.5 × 10^-3") == pytest.approx((0.0055, 0.0055))
    # ASCII-Letter ``x``/``X`` (Typewriter-/Handschrift-Ersatz fuer ×).
    assert csv_loaders.parse_range("5.5 x 10^-3") == pytest.approx((0.0055, 0.0055))
    assert csv_loaders.parse_range("5.5 X 10^-3") == pytest.approx((0.0055, 0.0055))
    assert csv_loaders.parse_range("5.5x10^-3") == pytest.approx((0.0055, 0.0055))
    # Positiver Exponent ohne explizites Plus-Zeichen (Print-Standard).
    assert csv_loaders.parse_range("5.5×10^3") == pytest.approx((5500.0, 5500.0))
    assert csv_loaders.parse_range("5.5 × 10^3") == pytest.approx((5500.0, 5500.0))
    assert csv_loaders.parse_range("5.5·10^3") == pytest.approx((5500.0, 5500.0))
    # Explizites Plus-Vorzeichen (LaTeX-Roh-Export oder Excel-Auto-Format).
    assert csv_loaders.parse_range("5.5×10^+3") == pytest.approx((5500.0, 5500.0))
    # Exponent Null (Skalar ohne Groessenordnungs-Modifikation) - Regression-
    # Anker fuer den Fall, dass die Zehnerpotenz nicht faelschlich zu 10
    # (10^1) fehlgelesen wird.
    assert csv_loaders.parse_range("2.65 × 10^0") == pytest.approx((2.65, 2.65))
    # Unicode-Superskript-Exponent (typografischer Print-Publikations-
    # Standard: die Explizit-Multiplikation wird oft mit Superskript-
    # Exponent gesetzt, weil beide Elemente typografisch zusammen gehoeren).
    assert csv_loaders.parse_range("5.5×10³") == pytest.approx((5500.0, 5500.0))
    assert csv_loaders.parse_range("5.5·10³") == pytest.approx((5500.0, 5500.0))
    assert csv_loaders.parse_range("5.5×10²") == pytest.approx((550.0, 550.0))
    assert csv_loaders.parse_range("5.5×10⁻³") == pytest.approx((0.0055, 0.0055))
    assert csv_loaders.parse_range("5.5·10⁻³") == pytest.approx((0.0055, 0.0055))
    assert csv_loaders.parse_range("5.5×10⁻²") == pytest.approx((0.055, 0.055))
    # Mehrstellige Superskript-Exponenten (astronomische Groessenordnungen
    # aus Isotopen-HWZ und Absorptions-Querschnitten).
    assert csv_loaders.parse_range("5.5×10⁻¹⁹") == pytest.approx((5.5e-19, 5.5e-19))
    assert csv_loaders.parse_range("4.5×10⁹") == pytest.approx((4.5e9, 4.5e9))
    # DE-Komma-Dezimal in der Mantisse (Publikationen aus DE-Print-Quellen
    # kombinieren Komma-Dezimal mit Middle-Dot-Multiplikation).
    assert csv_loaders.parse_range("5,5·10^-3") == pytest.approx((0.0055, 0.0055))
    assert csv_loaders.parse_range("5,5 × 10⁻³") == pytest.approx((0.0055, 0.0055))
    # Leading-Dot-Dezimal-Mantisse ohne fuehrende Null (US-/LaTeX-Konvention).
    assert csv_loaders.parse_range(".5×10^-3") == pytest.approx((0.0005, 0.0005))
    # Ganzzahl-Mantisse (Publikationen mit exakten Werten ohne Nachkommastelle).
    assert csv_loaders.parse_range("2×10^3") == pytest.approx((2000.0, 2000.0))
    assert csv_loaders.parse_range("1×10⁻³") == pytest.approx((0.001, 0.001))
    # Trailing SI-Einheit nach dem Exponent (typischer Publikations-Setz
    # ``2.65 × 10^3 kg/m^3``, ``1.5 × 10⁻⁹ mol/L``) - die Einheit hat
    # eigene Ziffern, die durch ``_NUM_RE``-Lookbehind ausgeblendet werden.
    assert csv_loaders.parse_range("5.5 × 10^-3 g/cm³") == pytest.approx((0.0055, 0.0055))
    assert csv_loaders.parse_range("1.5 × 10⁻⁹ mol/L") == pytest.approx((1.5e-9, 1.5e-9))
    # Negatives Vorzeichen vor der Mantisse (Kryo-Temperatur-Koeffizienten,
    # Isotopen-Delta-Werte, δ¹³C/δ¹⁸O in extremen Fraktionierungs-Regimen).
    assert csv_loaders.parse_range("-5.5 × 10^-3") == pytest.approx((-0.0055, -0.0055))
    # Range mit explizit-multiplikativer Zehnerpotenz auf beiden Seiten
    # (Kalibrier-Bereich, spektroskopischer Absorptions-Range).
    assert csv_loaders.parse_range("1×10^-3 - 5×10^-3") == pytest.approx((0.001, 0.005))
    assert csv_loaders.parse_range("1 × 10^3 - 5 × 10^3") == pytest.approx((1000.0, 5000.0))
    assert csv_loaders.parse_range("1 × 10^3 bis 5 × 10^3") == pytest.approx((1000.0, 5000.0))
    # Regression-Anker: die bestehende kompakte E-Notation bleibt
    # unveraendert - hat keinen ``10``-Basis-Radix, matcht das neue
    # Pattern nicht.
    assert csv_loaders.parse_range("1e-3") == pytest.approx((0.001, 0.001))
    assert csv_loaders.parse_range("1.5e-3") == pytest.approx((0.0015, 0.0015))
    # Regression-Anker: die Range-Notation ``5-10`` bleibt Range - kein
    # Multiplikations-Zeichen zwischen den Zahlen, das Pattern matcht nicht.
    assert csv_loaders.parse_range("5-10") == (5.0, 10.0)
    # Dimensions-/Groessen-Notation ``5x10 cm`` (Groessen-Angabe, nicht
    # Zehnerpotenz) matcht das Mantisse-Exponent-Pattern nicht (kein Exponent
    # nach ``10``) und faellt in den Dimensions-Zweig
    # :data:`_DIMENSION_X`: ``5x10`` -> ``5 10`` als Range-Ausdehnungen.
    # Siehe :func:`test_parse_range_ascii_x_dimensions_separator`.
    assert csv_loaders.parse_range("5x10 cm") == (5.0, 10.0)
    assert csv_loaders.parse_range("5x10") == (5.0, 10.0)
    # Regression-Anker: Uncertainty-Notation ``5.5 ± 0.3`` bleibt
    # Uncertainty - kein Multiplikations-Zeichen im Struktur-Anker.
    assert csv_loaders.parse_range("5.5 ± 0.3") == pytest.approx((5.2, 5.8))
    # Regression-Anker: SI-Kompakt-Einheit ``g cm^-3`` bleibt Einheit -
    # keine Mantisse VOR dem Multiplikations-Zeichen (bzw. der ``^-3``-
    # Sequenz), das Pattern matcht nicht.
    assert csv_loaders.parse_range("2.65 g cm^-3") == pytest.approx((2.65, 2.65))
    # Namens-/Katalog-Fragment mit ``x10``-Sequenz: das Lookbehind
    # ``(?<![A-Za-z0-9])`` blockiert das Mantissa-Match nach Buchstaben,
    # der Sample-/Katalog-Name wird nicht als Wert-Traeger fehlinterpretiert -
    # ``5x10^-3`` matcht das Mantisse-Exponent-Pattern nicht. Nach dem
    # :data:`_DIMENSION_X`-Sub ``Sample5x10^-3 g`` -> ``Sample5 10^-3 g``:
    # das ``5`` bleibt via ``_NUM_RE``-Letter-Lookbehind blockiert, ``10``
    # matcht nach Leerzeichen als (10, 10), ``3`` wird durch das ``^-``-
    # SI-Kompakt-Exponent-Lookbehind blockiert. Regression-Anker fuer den
    # Fall, dass das Mantissa-Lookbehind entfernt wird - die Mantisse-
    # Exponent-Interpretation von ``5x10^-3`` (die 0.005 liefern wuerde)
    # bleibt weiterhin blockiert, unabhaengig vom Dimensions-Zweig.
    assert csv_loaders.parse_range("Sample5x10^-3 g") == (10.0, 10.0)


def test_parse_range_leading_dot_dezimal():
    """Leading-Dot-Dezimals ``.5`` / ``.05`` / ``.5e-3`` werden als Wert < 1 gelesen.

    US-typografische Konvention "no leading zero" und wissenschaftliche
    Publikationen ohne fuehrende Null (LaTeX/PDF-Roh-Export, Print-Kataloge,
    NIST-CODATA-Auszuege). Vor dem Fix fiel der Punkt aus dem Match des
    generischen Zahl-Token-Regex und die Ziffernfolge dahinter wurde als eigene
    Ganzzahl gelesen: ``.5`` lieferte (5.0, 5.0) statt (0.5, 0.5) (Faktor 10
    zu gross), ``.5-.7`` lieferte (5.0, 7.0) statt (0.5, 0.7), ``.5e-3`` (kleiner
    Absorptions-/Kalibrier-Wert in Publikationen ohne fuehrende Null) lieferte
    ueber Zwei-Zahl-Zerlegung ``[5, 3]`` und hi<lo-Fallback (5.0, 5.0) statt
    (0.0005, 0.0005) - Faktor 10.000 zu gross. Bei der Migration aus US-/
    englischsprachigen Sammlungs-Notizen und aus LaTeX-Publikationen ohne
    fuehrende Null entstand damit silenter Groessenordnungs-Verlust bei
    kleinen Werten (Mikroskopie-Messwerte, Foliendicken, Feinkorn-Groessen).
    """
    # Punktwert ohne fuehrende Null (typisch US/Print).
    assert csv_loaders.parse_range(".5") == (0.5, 0.5)
    assert csv_loaders.parse_range(".05") == (0.05, 0.05)
    assert csv_loaders.parse_range(".005") == (0.005, 0.005)
    # Range ohne fuehrende Nullen auf beiden Seiten.
    assert csv_loaders.parse_range(".5-.7") == (0.5, 0.7)
    assert csv_loaders.parse_range(".5 - .7") == (0.5, 0.7)
    # Gemischt: leading-dot links, normale Zahl rechts (und umgekehrt).
    assert csv_loaders.parse_range(".5-7") == (0.5, 7.0)
    # Scientific notation ohne fuehrende Null - Absorptions-/Kalibrier-Werte
    # in Publikationen (``.5e-3`` = 5e-4 = 0.0005).
    assert csv_loaders.parse_range(".5e-3") == (0.0005, 0.0005)
    assert csv_loaders.parse_range(".5E+3") == (500.0, 500.0)
    # Freitext-Praefix (z.B. Annaeherungs-Marker) vor leading-dot.
    assert csv_loaders.parse_range("ca. .5") == (0.5, 0.5)
    # Freitext-Suffix (Einheit) nach leading-dot - Einheit hat keine
    # Zahlen, damit die Groessenordnung erhalten bleibt.
    assert csv_loaders.parse_range(".5 mm") == (0.5, 0.5)
    assert csv_loaders.parse_range(".05 g") == (0.05, 0.05)
    # Regression-Anker: normale Werte (mit fuehrender Null) bleiben
    # unveraendert, damit die neue Alternante die bestehende Konvention
    # nicht umschreibt.
    assert csv_loaders.parse_range("0.5") == (0.5, 0.5)
    assert csv_loaders.parse_range("0.5-0.7") == (0.5, 0.7)
    # Regression-Anker: leading-Komma (``,5`` alleinstehend) wird NICHT
    # als Dezimal interpretiert - waere in DE-Locale mehrdeutig; US-
    # Konvention kennt kein leading-Komma-Dezimal, und Excel-DE schreibt
    # ``0,5`` mit fuehrender Null. Der String faellt auf die generische
    # Zahl-Suche zurueck, findet die ``5`` als eigenstaendige Ganzzahl.
    assert csv_loaders.parse_range(",5") == (5.0, 5.0)


def test_parse_range_schweizer_apostroph_tausender():
    """Schweizer Tausendertrenner ''' wird ignoriert (CHF-Betraege aus Excel)."""
    # Ohne Fix waere "1'000.00" als (1, 0) gelesen worden.
    assert csv_loaders.parse_range("1'000.00") == (1000.0, 1000.0)
    assert csv_loaders.parse_range("1'500'000.50") == (1500000.5, 1500000.5)
    # Range mit Apostroph auf beiden Seiten
    assert csv_loaders.parse_range("1'000-2'000") == (1000.0, 2000.0)
    # Typografischer Apostroph (U+2019) wird ebenso entfernt
    assert csv_loaders.parse_range("1’000") == (1000.0, 1000.0)


def test_parse_range_einheit_mit_hochgestellter_ascii_ziffer():
    """SI-Einheiten mit ASCII-Superskript-Ersatz (``cm3``/``m2``/``s2``/``cm^3``)
    duerfen die Ziffer im Einheiten-Suffix nicht als Range-Grenze anschleppen.

    In geerbten Sammlungs-Notizen sehr verbreitet, wenn Autor/Tool kein
    Unicode-Superskript zur Verfuegung hatte: Excel-CSV-Exporte ohne
    Unicode-Codepage, Terminal-/Log-Ausgaben (ASCII-only), LaTeX-Roh-Exporte
    ohne ``\\textsuperscript``, alte Sammlungs-DB-Formate mit 7-bit-ASCII
    und Foto-EXIF-Kommentare aus Kameras ohne Unicode-Support schreiben
    ``g/cm³`` als ``g/cm3`` (Ziffer statt ³ U+00B3) bzw. als ``g/cm^3`` mit
    Caret als Superskript-Marker (LaTeX-/Math-Konvention). Bisher fiel die
    Einheits-Ziffer als eigenstaendiger Zahl-Token in nums auf und produzierte
    mineralogisch unsinnige Bereiche:

    * ``"2.65 g/cm3"``  -> (2.65, 3.0)  (3 aus ``cm3`` als Range-hi statt Einheit)
    * ``"2.65 kg/m3"``  -> (2.65, 3.0)  (3 aus ``m3`` als Range-hi)
    * ``"2.65 g/cm^3"`` -> (2.65, 3.0)  (Caret-Superskript-Form, gleiche Fehl-Lese)
    * ``"5-7 g/cm3"``   -> (5.0, 5.0)   (nums=[5,7,3], hi=3<lo=5 -> Kollaps, Range verloren)
    * ``"9.81 m/s2"``   -> (9.81, 9.81) (zufaellig richtig, weil hi<lo-Kollaps)

    Bei der Migration aus ASCII-only-Mineralogie-Notizen entstand damit
    silenter Wert-/Range-Datenverlust: kleine Bereiche mit hi=Ziffer-aus-
    Einheit wurden auf den Center kollabiert (Range verloren), grosse
    Werte mit ni-Ziffer-aus-Einheit > Center wurden als semantisch falscher
    Range gelesen (unsinnige mineralogische Interpretation).

    Der Fix ergaenzt ``_NUM_RE`` um ein negatives Lookbehind ``(?<![A-Za-z^])``,
    das die generische Zahl-Extraktion an Positionen blockiert, an denen die
    Zahl direkt nach einem Buchstaben oder Caret steht - die typische
    Einheiten-Suffix-Signatur. Kollisionsfrei zu scientific notation
    (``1e3``/``1.5e-3`` matchen als Ganz-Token, das Lookbehind pruefft nur
    das fuehrende Digit, nicht das ``e`` innerhalb des Tokens) und zu
    Leading-Dot-Dezimals (``.5`` matcht ueber die ``\\.\\d+``-Alternante,
    Lookbehind gilt vor dem ``.``).

    Bezeichner-Positionen (``Sample3``/``Mineral2``/``B12``) sind eine
    natuerliche Nebenwirkung: dort ist die Zahl Teil des Namens (Sample-
    Nummer, Chargen-Marker, Katalog-Bezeichner), nicht eine Messgroesse -
    dropen ist semantisch korrekt, spiegelt die Strip-Konvention von
    :func:`_strip_bracketed_annotations` auf die Bezeichner-Achse.
    """
    # Dichte-Einheit mit ASCII-Superskript-Ersatz (die haeufigste Notation
    # in ASCII-only-Mineralogie-Kontexten). Vorher: (2.65, 3.0).
    assert csv_loaders.parse_range("2.65 g/cm3") == (2.65, 2.65)
    assert csv_loaders.parse_range("2.65 kg/m3") == (2.65, 2.65)
    # Caret-Superskript-Form (LaTeX-/Math-Konvention). Vorher: (2.65, 3.0).
    assert csv_loaders.parse_range("2.65 g/cm^3") == (2.65, 2.65)
    assert csv_loaders.parse_range("2.65 kg/m^3") == (2.65, 2.65)
    # Range mit Einheit am Ende: die Einheits-Ziffer darf den echten Range
    # weder als hi ueberschreiben noch via hi<lo-Kollaps auf den Center
    # zusammenziehen. Vorher: (5.0, 5.0) via nums=[5,7,3] und hi=3<lo=5.
    assert csv_loaders.parse_range("5-7 g/cm3") == (5.0, 7.0)
    assert csv_loaders.parse_range("5-7 g/cm^3") == (5.0, 7.0)
    # Andere physikalische Einheiten mit ASCII-Superskript (Flaeche, Zeit,
    # Beschleunigung, Volumen). Vorher: alle Faelle brachten via hi<lo-Kollaps
    # zufaellig den Center-Wert doppelt zurueck (aber semantisch: Ziffer
    # aus Einheit war als Range-Grenze gemeint - Silent-Drop der Semantik).
    assert csv_loaders.parse_range("9.81 m/s2") == (9.81, 9.81)
    assert csv_loaders.parse_range("100 mm2") == (100.0, 100.0)
    assert csv_loaders.parse_range("50 cm3") == (50.0, 50.0)
    # Bezeichner-Zahlen (Sample/Chargen-Marker vor dem Wert): die Zahl im
    # Bezeichner-Praefix wird nicht als Range-Grenze fehlgelesen. Vorher:
    # ``"Sample3 test 2.65"`` -> (3.0, 3.0) via hi<lo-Kollaps, Wert 2.65
    # ging verloren. ``"Mineral2 test 5.5"`` -> (2.0, 5.5) semantisch falscher
    # Range 2 bis 5.5.
    assert csv_loaders.parse_range("Sample3 test 2.65") == (2.65, 2.65)
    assert csv_loaders.parse_range("Mineral2 5.5") == (5.5, 5.5)
    # Unicode-Superskript-Form (bereits richtig, Regression-Anker): ``g/cm³``
    # (U+00B3) enthaelt kein ASCII-Digit und war schon vor dem Fix korrekt.
    assert csv_loaders.parse_range("2.65 g/cm³") == (2.65, 2.65)
    assert csv_loaders.parse_range("5-7 g/cm³") == (5.0, 7.0)
    # Regression-Anker: scientific notation bleibt Ganz-Token, weil das
    # Lookbehind nur die erste Ziffer prueft und ``1e3`` als eine Zahl mit
    # ``1`` am Anfang (nach ``\\s``/Start, nicht nach Buchstabe) matcht.
    assert csv_loaders.parse_range("1e3") == (1000.0, 1000.0)
    assert csv_loaders.parse_range("1.5e-3") == (0.0015, 0.0015)
    assert csv_loaders.parse_range(".5e-3") == (0.0005, 0.0005)
    # Regression-Anker: Leading-Dot-Dezimals matchen ueber die ``\\.\\d+``-
    # Alternante, das Lookbehind gilt vor dem ``.`` und laesst den Match zu.
    assert csv_loaders.parse_range(".5") == (0.5, 0.5)
    assert csv_loaders.parse_range(".5 mm") == (0.5, 0.5)
    # Regression-Anker: alle bereits geprueften Notations-Klassen bleiben
    # unveraendert - der Fix beruehrt nur die generische Fallback-Extraktion.
    assert csv_loaders.parse_range("5.5(3)") == pytest.approx((5.2, 5.8))
    assert csv_loaders.parse_range("5.5 ± 0.3") == pytest.approx((5.2, 5.8))
    assert csv_loaders.parse_range("6.5-7.0") == (6.5, 7.0)
    assert csv_loaders.parse_range("1'000.00") == (1000.0, 1000.0)


def test_parse_range_si_kompakt_negativer_exponent():
    """SI-Kompakt-Einheit mit negativer Zehnerpotenz (``g cm-3``, ``m s-1``) darf
    die Exponenten-Ziffer nicht als Range-Grenze anschleppen.

    SI-Kompakt-Notation ohne Divisions-Slash ist der internationale Publikations-
    Standard (ISO 80000, IUPAC-Gruen-Buch, IUCr-Style-Guide) fuer zusammengesetzte
    Einheiten mit negativer Zehnerpotenz - "Dichte 2.65 g cm-3", "Frequenz 100
    s-1", "Bragg-Winkel 5.5 A-1", "Konzentration 1.5 mol-1", "Diffusivitaet 1e-6
    m2 s-1". In Mineralogie-/Physik-Publikationen (Nature/Science/AmMin/GCA) und
    NIST-CODATA-Konstanten-Tabellen die kanonische Form. Bisher fiel jede dieser
    Notationen still auf Range-Fehl-Interpretation durch:

    * ``"2.65 g cm-3"`` -> (2.65, 3.0) (3 aus ``cm-3`` als Range-hi statt Exponent)
    * ``"2.65 kg m-3"`` -> (2.65, 3.0) (analog SI-Basis-Einheit)
    * ``"1.5 mol-1"``   -> (1.0, 1.5)  (1 aus ``mol-1`` als Range-lo)
    * ``"5.5 cm-3"``    -> (5.5, 5.5)  (zufaellig richtig via hi<lo-Kollaps, aber
                                        semantisch die 3 als Range-hi fehlgelesen)

    Der Fix ergaenzt ``_NUM_RE`` um ein zweites Lookbehind
    ``(?<![A-Za-z^]-)``, das die generische Zahl-Extraktion an Positionen
    blockiert, an denen die Ziffer direkt nach ``[Buchstabe|Caret][Hyphen]``
    steht - die SI-Kompakt-Exponenten-Signatur. Kollisionsfrei zu echten
    Sign-Rollen (Zeilenanfang, nach Whitespace/Punktuation/Klammer/=) und zu
    Range-Trennern (der Trenner-Hyphen sitzt zwischen zwei Ziffern, nicht
    nach einem Buchstaben).
    """
    # Dichte in SI-Kompakt-Form (mineralogische Standardnotation)
    assert csv_loaders.parse_range("2.65 g cm-3") == (2.65, 2.65)
    assert csv_loaders.parse_range("2.65 kg m-3") == (2.65, 2.65)
    assert csv_loaders.parse_range("2.65 g m-3") == (2.65, 2.65)
    # Caret-Superskript-Variante (LaTeX-/Math-Konvention)
    assert csv_loaders.parse_range("2.65 g cm^-3") == (2.65, 2.65)
    assert csv_loaders.parse_range("2.65 kg m^-3") == (2.65, 2.65)
    # Frequenz-/Zerfalls-Reziprok (s-1 = Hz)
    assert csv_loaders.parse_range("100 s-1") == (100.0, 100.0)
    assert csv_loaders.parse_range("2.65 g s-1") == (2.65, 2.65)
    # Reziproke Basis-Vektoren in Roentgen-Beugung (Å-1 / A-1)
    assert csv_loaders.parse_range("5.5 A-1") == (5.5, 5.5)
    assert csv_loaders.parse_range("5.5 Å-1") == (5.5, 5.5)
    # Loeslichkeitsprodukt / Loschmidt-Reziprok
    assert csv_loaders.parse_range("1.5 mol-1") == (1.5, 1.5)
    # Konzentration/Zerfalls-Dichte (cm-3, pm-1)
    assert csv_loaders.parse_range("5.5 cm-3") == (5.5, 5.5)
    assert csv_loaders.parse_range("5.5 pm-1") == (5.5, 5.5)
    # Longformer-Wert < SI-Exponent (der Fix beseitigt den echten Range-Fehler
    # 2.65 g cm-3 -> (2.65, 3.0), der beim inverted-Range-Fallback bisher NICHT
    # gefangen wurde). Vorher: (2.65, 3.0); jetzt: (2.65, 2.65).
    assert csv_loaders.parse_range("2.65 g m-3") == (2.65, 2.65)
    # Wissenschaftliche Notation kombiniert mit SI-Kompakt-Einheit
    assert csv_loaders.parse_range("3.14e-5 mol kg-1") == pytest.approx(
        (3.14e-5, 3.14e-5))
    # Regression-Anker: echte negative Sign-Rollen bleiben intakt
    assert csv_loaders.parse_range("-5.5") == (-5.5, -5.5)
    assert csv_loaders.parse_range("x=-3.5") == (-3.5, -3.5)
    assert csv_loaders.parse_range("value:-3.5") == (-3.5, -3.5)
    # Regression-Anker: echte Range-Trenner bleiben intakt (der Hyphen zwischen
    # zwei Ziffern hat vor der zweiten Ziffer das Muster [Ziffer][Hyphen],
    # nicht [Buchstabe][Hyphen] - Lookbehind passiert).
    assert csv_loaders.parse_range("5-7") == (5.0, 7.0)
    assert csv_loaders.parse_range("5.5-7.5") == (5.5, 7.5)
    assert csv_loaders.parse_range("5-7 g/cm3") == (5.0, 7.0)
    # Regression-Anker: bereits vorhandene SI-Positiv-Exponenten-Behandlung
    # (``cm3``/``m2``/``s2``/``cm^3``) bleibt unveraendert.
    assert csv_loaders.parse_range("2.65 g/cm3") == (2.65, 2.65)
    assert csv_loaders.parse_range("2.65 g/cm³") == (2.65, 2.65)
    assert csv_loaders.parse_range("2.65 g/cm^3") == (2.65, 2.65)
    # Regression-Anker: Uncertainty-Notation mit SI-Kompakt-Einheit bleibt
    # ueber den etablierten ±-/Klammer-Zweig aufgeloest (der neue Zweig
    # greift nur in der Fallback-Extraktion).
    assert csv_loaders.parse_range("5.5(3)") == pytest.approx((5.2, 5.8))
    assert csv_loaders.parse_range("5.5 ± 0.3") == pytest.approx((5.2, 5.8))


def test_parse_range_unicode_vulgar_fraktionen():
    """Unicode-Vulgar-Fraktionen (¼/½/¾ und U+2150-U+215E) werden als Wert
    aufgeloest statt still verworfen.

    In mineralogischen Referenz-Tabellen ist die Mohs-Halbschritt-Notation
    ``5½`` der klassische Weg, die Haerte zwischen zwei Ganzzahl-
    Referenzmineralen zu notieren (5½ = zwischen Apatit und Orthoklas,
    6½ = zwischen Orthoklas und Quarz), und ¼/¾/⅛-Notation kommt in
    Groessen-/Gewichts-Fraktionen aeltere Sammler-Karten und in
    imperialen Einheiten (``3¼ inch``) vor. Vor dieser Erweiterung fiel
    ``5½`` auf ``[5]`` und lieferte (5.0, 5.0) statt (5.5, 5.5) - der
    publizierte Halbschritt der Mohs-Skala ging silent verloren und die
    Sortier-/Vergleichs-Reihenfolge stimmte nicht mehr mit der Referenz-
    Tabelle ueberein; standalone ``¼`` lieferte (None, None) - Wert-
    Datenverlust bei jeder Migration aus Word/LibreOffice/PDF-Quellen mit
    typografisch sauber gesetzten Unicode-Fraktionen.
    """
    # Mixed-Form Mohs-Halbschritt (die haeufigste Notation in Referenz-
    # Tabellen; vor dem Fix: (5.0, 5.0), Halbschritt still verloren).
    assert csv_loaders.parse_range("5½") == (5.5, 5.5)
    assert csv_loaders.parse_range("6½") == (6.5, 6.5)
    # Mixed-Form mit Whitespace-Trenner (Print-/Katalog-Form mit typo-
    # grafisch sauberem Halbschritt-Space; auch NBSP und schmales NBSP).
    assert csv_loaders.parse_range("5 ½") == (5.5, 5.5)
    assert csv_loaders.parse_range("5\xa0½") == (5.5, 5.5)
    assert csv_loaders.parse_range("5 ½") == (5.5, 5.5)
    # Mixed-Form mit Viertel- und Dreiviertel-Fraktion (imperiale Einheiten,
    # aeltere Groessen-Notation in Sammler-Karten).
    assert csv_loaders.parse_range("3¼") == (3.25, 3.25)
    assert csv_loaders.parse_range("6¾") == (6.75, 6.75)
    # Mixed-Form mit Achtel-Fraktion (Sieb-Rueckstands-Rasterung, feinere
    # imperiale Notation).
    assert csv_loaders.parse_range("2⅛") == (2.125, 2.125)
    assert csv_loaders.parse_range("1⅜") == (1.375, 1.375)
    assert csv_loaders.parse_range("4⅝") == (4.625, 4.625)
    assert csv_loaders.parse_range("3⅞") == (3.875, 3.875)
    # Standalone-Form (Wert < 1 ohne Ganzzahl-Vorstand); vor dem Fix:
    # (None, None), Wert komplett verloren.
    assert csv_loaders.parse_range("¼") == (0.25, 0.25)
    assert csv_loaders.parse_range("½") == (0.5, 0.5)
    assert csv_loaders.parse_range("¾") == (0.75, 0.75)
    assert csv_loaders.parse_range("⅕") == (0.2, 0.2)
    assert csv_loaders.parse_range("⅖") == (0.4, 0.4)
    assert csv_loaders.parse_range("⅗") == (0.6, 0.6)
    assert csv_loaders.parse_range("⅘") == (0.8, 0.8)
    assert csv_loaders.parse_range("⅛") == (0.125, 0.125)
    assert csv_loaders.parse_range("⅜") == (0.375, 0.375)
    assert csv_loaders.parse_range("⅝") == (0.625, 0.625)
    assert csv_loaders.parse_range("⅞") == (0.875, 0.875)
    assert csv_loaders.parse_range("⅒") == (0.1, 0.1)
    # Periodische Fraktionen (⅓/⅔/⅙/⅚/⅐/⅑) - 12 signifikante Nachkomma-
    # Stellen decken den IEEE-754-double-Praezisionsbereich sauber ab.
    assert csv_loaders.parse_range("⅓") == pytest.approx((1 / 3, 1 / 3), rel=1e-11)
    assert csv_loaders.parse_range("⅔") == pytest.approx((2 / 3, 2 / 3), rel=1e-11)
    assert csv_loaders.parse_range("⅙") == pytest.approx((1 / 6, 1 / 6), rel=1e-11)
    assert csv_loaders.parse_range("⅚") == pytest.approx((5 / 6, 5 / 6), rel=1e-11)
    assert csv_loaders.parse_range("⅐") == pytest.approx((1 / 7, 1 / 7), rel=1e-11)
    assert csv_loaders.parse_range("⅑") == pytest.approx((1 / 9, 1 / 9), rel=1e-11)
    # Range-Formen mit Mixed-Fraktion auf beiden Seiten (Mohs-Bereich
    # zwischen zwei Halbschritt-Werten) - die haeufigste Referenz-Tabellen-
    # Notation fuer variabel-haertige Minerale.
    assert csv_loaders.parse_range("5½-6½") == (5.5, 6.5)
    assert csv_loaders.parse_range("5½ - 6½") == (5.5, 6.5)
    assert csv_loaders.parse_range("5 ½ – 6 ½") == (5.5, 6.5)  # En-Dash Print-Form
    # Range mit Mixed-Fraktion und Ganzzahl gemischt.
    assert csv_loaders.parse_range("5½-7") == (5.5, 7.0)
    assert csv_loaders.parse_range("5-6½") == (5.0, 6.5)
    # Kombination mit Uncertainty-Zweig: die Fraktions-Normalisierung
    # greift *vor* der Uncertainty-Erkennung, damit ``5½ ± 0.3`` als
    # ``5.5 ± 0.3`` korrekt als publizierte Toleranz auf den Halbschritt-
    # Wert auswertet (statt Center 5.0 zu (4.7, 5.3)).
    assert csv_loaders.parse_range("5½ ± 0.3") == pytest.approx((5.2, 5.8))
    assert csv_loaders.parse_range("5½(3)") == pytest.approx((5.2, 5.8))
    # Kombination mit Trailing-Einheit: die Fraktion wird zum Wert-
    # Vorstand normalisiert, die nachfolgende Einheit bleibt Whitespace-
    # getrennter Wort-Token (kein Match im Zahl-Extraktor).
    assert csv_loaders.parse_range("5½ Mohs") == (5.5, 5.5)
    assert csv_loaders.parse_range("2¾ g/cm³") == (2.75, 2.75)
    assert csv_loaders.parse_range("3¼ inch") == (3.25, 3.25)
    # Kombination mit Klammer-Annotation: die Fraktion wird normalisiert,
    # dann strippt der Klammer-Strip die Annotation vor der Zahl-
    # Extraktion (spiegelt _strip_bracketed_annotations auf die Fraktions-
    # Achse).
    assert csv_loaders.parse_range("5½ (Ref)") == (5.5, 5.5)
    assert csv_loaders.parse_range("5½ [Foto]") == (5.5, 5.5)
    # Kollisions-Schutz gegen SI-Einheiten-Position: ``cm3½`` bleibt
    # unangetastet, weil die 3 durch das _NUM_RE-Lookbehind als Teil der
    # Einheit erkannt wird und das Mixed-Fraktion-Lookbehind zusaetzlich
    # den Letter-Kontext blockiert (die Fraktion darf nicht mit einer
    # Einheiten-Ziffer als vermeintlichem Ganzzahl-Vorstand kombiniert
    # werden). Ohne diesen Schutz wuerde ``cm3½`` zu ``cm3.5`` und der
    # (unerwuenschte) Match wuerde 3.5 als Wert liefern.
    assert csv_loaders.parse_range("cm3½") == (None, None)
    assert csv_loaders.parse_range("m^3½") == (None, None)
    # Kollisions-Schutz gegen Bezeichner-Position: ``Sample½`` bleibt
    # unangetastet (kein Wert, sondern Katalog-Bezeichner mit typografischer
    # Fraktion) - spiegelt die _NUM_RE-Bezeichner-Konvention.
    assert csv_loaders.parse_range("Sample½") == (None, None)
    # Defekte Dezimal-Fraktions-Verkettung: ``5.5½`` ist semantisch
    # unklar (soll das 5.5+0.5=6.0 oder ein Tippfehler sein?), besser
    # unangetastet lassen als kuenstlich zu ``5.5.5`` zu erweitern. Das
    # Fraktions-Lookbehind blockiert nach ``.`` und ``,``, sodass nur die
    # ``5.5`` als Wert-Token extrahiert wird.
    assert csv_loaders.parse_range("5.5½") == (5.5, 5.5)
    # Locale-Konsistenz: DE-Komma-Dezimal am Vorstand ist keine gueltige
    # Mixed-Form; die Fraktion faellt auf Standalone zurueck. ``5,5½``
    # wird zu ``5,50.5`` erweitert - der Zahl-Extraktor liest ``5,5`` als
    # DE-Dezimal und ``0.5`` als zweiten Wert. Range zaehlt nach
    # Zahl-Reihenfolge; Ergebnis (5.5, 5.5) via hi<lo-Kollaps, konsistent
    # mit der Standard-DE-Konvention.
    assert csv_loaders.parse_range("5,5½") == (5.5, 5.5)


def test_parse_range_ascii_mixed_fraktionen():
    """ASCII-Mixed-Fraktion ``\\d+\\s+\\d+/\\d+`` wird als Wert aufgeloest statt still
    als Range-/Ratio-Fragmentliste zerlegt.

    Spiegelt die Unicode-Vulgar-Fraktions-Normalisierung
    (:func:`_normalize_vulgar_fractions`) auf die Plain-ASCII-Achse - typische
    Notation aus Typewriter-/Terminal-Notizen, aus geerbten Textdatei-
    Sammlungen (RTF/TXT ohne Autoformat-Konvertierung zu ½/¼) und aus
    handschriftlich abgeschriebenen Mohs-Haerte-Werten, bei denen der Autor
    den Halbschritt als ``5 1/2`` statt ``5½`` notiert. Vor dieser
    Erweiterung fiel ``5 1/2`` auf ``[5, 1, 2]`` und lieferte via inverted-
    Range-Kollaps ``(5.0, 5.0)`` - der Mohs-Halbschritt ging silent
    verloren; ``5 1/2 - 6 1/2`` lieferte via [5, 1, 2, 6, 1, 2] den
    semantisch falschen Range ``(5.0, 6.0)`` (beide Halbschritte verloren);
    ``5 3/4 Mohs`` lieferte ``(3.0, 4.0)`` (Ganzzahl-Vorstand verworfen).
    """
    # Mohs-Halbschritt (der klassische Anwendungsfall - haeufigste ASCII-
    # Notation in Typewriter-/Plain-Text-Sammler-Notizen; vor dem Fix
    # (5.0, 5.0), Halbschritt still verloren).
    assert csv_loaders.parse_range("5 1/2") == (5.5, 5.5)
    assert csv_loaders.parse_range("6 1/2") == (6.5, 6.5)
    # Viertel-/Dreiviertel-Fraktion (imperiale Groessen-/Gewicht-Angaben,
    # aeltere Sammler-Karten).
    assert csv_loaders.parse_range("3 1/4") == (3.25, 3.25)
    assert csv_loaders.parse_range("6 3/4") == (6.75, 6.75)
    # Achtel-Fraktion (Sieb-Rueckstands-Rasterung, feinere imperiale
    # Notation).
    assert csv_loaders.parse_range("2 1/8") == (2.125, 2.125)
    assert csv_loaders.parse_range("1 3/8") == (1.375, 1.375)
    assert csv_loaders.parse_range("4 5/8") == (4.625, 4.625)
    assert csv_loaders.parse_range("3 7/8") == (3.875, 3.875)
    # Sechzehntel-Fraktion (Bohrdurchmesser-Notation, feine imperiale
    # Rasterung).
    assert csv_loaders.parse_range("5 1/16") == pytest.approx((5.0625, 5.0625))
    assert csv_loaders.parse_range("5 15/16") == (5.9375, 5.9375)
    # Metrische Tenth-Fraktion.
    assert csv_loaders.parse_range("5 3/10") == (5.3, 5.3)
    # Periodische Fraktionen (⅓/⅔/⅙/⅚) - 12 signifikante Nachkomma-Stellen
    # decken den IEEE-754-double-Praezisionsbereich sauber ab (spiegelt die
    # Konvention der Unicode-Vulgar-Fraktions-Normalisierung).
    assert csv_loaders.parse_range("5 1/3") == pytest.approx(
        (5 + 1 / 3, 5 + 1 / 3), rel=1e-11
    )
    assert csv_loaders.parse_range("5 2/3") == pytest.approx(
        (5 + 2 / 3, 5 + 2 / 3), rel=1e-11
    )
    assert csv_loaders.parse_range("5 1/6") == pytest.approx(
        (5 + 1 / 6, 5 + 1 / 6), rel=1e-11
    )
    # Whitespace-Varianten: einfaches Leerzeichen, NBSP (U+00A0), schmales
    # NBSP (U+202F) - typografische Print-Formen mit sauberem Halbschritt-
    # Space.
    assert csv_loaders.parse_range("5\xa01/2") == (5.5, 5.5)
    assert csv_loaders.parse_range("5 1/2") == (5.5, 5.5)
    # Range-Formen mit Mixed-Fraktion auf beiden Seiten (Mohs-Bereich
    # zwischen zwei Halbschritt-Werten) - die haeufigste Referenz-Tabellen-
    # Notation fuer variabel-haertige Minerale in Plain-Text-Quellen.
    assert csv_loaders.parse_range("5 1/2 - 6 1/2") == (5.5, 6.5)
    assert csv_loaders.parse_range("5 1/2-6 1/2") == (5.5, 6.5)
    assert csv_loaders.parse_range("5 1/2 – 6 1/2") == (5.5, 6.5)  # En-Dash
    # Range mit Mixed-Fraktion und Ganzzahl gemischt.
    assert csv_loaders.parse_range("5 1/2 - 7") == (5.5, 7.0)
    assert csv_loaders.parse_range("5 - 6 1/2") == (5.0, 6.5)
    # Kombination mit Uncertainty-Zweig: die Fraktions-Normalisierung
    # greift *vor* der Uncertainty-Erkennung, damit ``5 1/2 ± 0.3`` als
    # ``5.5 ± 0.3`` korrekt als publizierte Toleranz auf den Halbschritt-
    # Wert auswertet (statt Center 5.0 zu (4.7, 5.3)).
    assert csv_loaders.parse_range("5 1/2 ± 0.3") == pytest.approx((5.2, 5.8))
    assert csv_loaders.parse_range("5 1/2(3)") == pytest.approx((5.2, 5.8))
    # Kombination mit Trailing-Einheit: die Fraktion wird zum Wert-
    # Vorstand normalisiert, die nachfolgende Einheit bleibt Whitespace-
    # getrennter Wort-Token (kein Match im Zahl-Extraktor).
    assert csv_loaders.parse_range("5 1/2 Mohs") == (5.5, 5.5)
    assert csv_loaders.parse_range("2 3/4 g/cm³") == (2.75, 2.75)
    assert csv_loaders.parse_range("3 1/4 inch") == (3.25, 3.25)
    # Kombination mit Klammer-Annotation: die Fraktion wird normalisiert,
    # dann strippt der Klammer-Strip die Annotation vor der Zahl-
    # Extraktion.
    assert csv_loaders.parse_range("5 1/2 (Ref)") == (5.5, 5.5)
    assert csv_loaders.parse_range("5 1/2 [Foto]") == (5.5, 5.5)


def test_parse_range_ascii_mixed_fraktionen_ungueltig():
    """Sicherheitsschranken der ASCII-Mixed-Fraktions-Normalisierung:
    Denominator-Whitelist, Proper-Fraktion-Check, Lookbehind/Lookahead-Schutz.

    ASCII-Mixed-Fraktion ist strukturell mehrdeutig - im Gegensatz zur
    Unicode-Vulgar-Fraktion ``½`` (eindeutiges Wert-Zeichen) kann
    ``1/2`` als Ratio, Datums-Fragment (6/2024) oder Katalog-Nummer
    (Nr. 3 von 42) auftreten. Die Whitelist auf mineralogische/imperiale
    Standard-Nenner {2,3,4,5,6,8,10,16,32} und der Proper-Fraktion-Check
    (Zaehler < Nenner) filtern die semantisch mehrdeutigen Kombinationen.
    """
    # Denominator ausserhalb der Whitelist: Datums-Fragment mit Nenner
    # 1985/2020/2024 (Jahr) faellt auf keine Substitution zurueck -
    # die generische Zahl-Extraktion greift und liefert die einzelnen
    # Tokens. ``5 6/2024`` (Tag/Monat/Jahr-Fragment) -> [5, 6, 2024].
    assert csv_loaders.parse_range("5 1/1985") == (5.0, 1985.0)
    assert csv_loaders.parse_range("5 6/2024") == (5.0, 2024.0)
    # Nenner 12 (Monatszahl) ist bewusst ausserhalb der Whitelist - eine
    # 12tel-Fraktion ist mineralogisch unueblich und die Kollision mit
    # Monats-Notation zu wichtig. ``5 3/12`` bleibt Range-/Fragment-
    # Interpretation [5, 3, 12].
    assert csv_loaders.parse_range("5 1/12") == (5.0, 12.0)
    assert csv_loaders.parse_range("5 3/12") == (5.0, 12.0)
    # Nenner 100 (Katalog-Nummer ``N von 100``) ist bewusst ausserhalb -
    # ``5 42/100`` bleibt Range-/Fragment-Interpretation [5, 42, 100].
    assert csv_loaders.parse_range("5 42/100") == (5.0, 100.0)
    # Improper Fraktion (Zaehler >= Nenner) faellt auf keine Substitution
    # zurueck - ``5 5/2`` waere semantisch mehrdeutig (Ratio 5:2, verkuerzte
    # Range-Notation), besser unangetastet.
    assert csv_loaders.parse_range("5 5/2") == (5.0, 5.0)
    assert csv_loaders.parse_range("5 3/3") == (5.0, 5.0)
    # Kollisions-Schutz gegen Einheiten-Position: der Ganzzahl-Vorstand
    # darf nicht mit einer Einheiten-Ziffer als vermeintlichem Wert-Anker
    # kombiniert werden. ``cm3 1/2`` (SI-Einheit ``cm³`` als ``cm3``-ASCII)
    # bleibt in der Einheiten-Semantik - der Wert-Anker ist die Einheit,
    # nicht der 3-Suffix.
    assert csv_loaders.parse_range("m^3 1/2") == (1.0, 2.0)
    # Kollisions-Schutz gegen greedy-Uebergreifen: eine anschliessende
    # ``/\d``-Sequenz (Datum-Kette ``5 3/4/2020``) blockiert den Match via
    # Lookahead - die Fraktion ist strukturell nicht abgeschlossen und
    # koennte Teil eines Datums-Fragments sein.
    assert csv_loaders.parse_range("5 3/4/2020") == (5.0, 2020.0)
    # Standalone-Fraktion ohne Ganzzahl-Vorstand (``1/2``, ``3/4``) faellt
    # bewusst *nicht* auf 0.5/0.75, sondern bleibt Range-Interpretation
    # [1, 2] / [3, 4] - die Mehrdeutigkeit zwischen Fraktion, Ratio,
    # Einheiten-Nenner und Range ist ohne Ganzzahl-Vorstand zu gross;
    # die Unicode-Standalone-Form ``½``/``¾`` bleibt hier die stabile
    # Alternative, wenn der Autor die Fraktion eindeutig meint.
    assert csv_loaders.parse_range("1/2") == (1.0, 2.0)
    assert csv_loaders.parse_range("3/4") == (3.0, 4.0)
    # Regression-Anker: die bestehende Uncertainty-/Range-Semantik ohne
    # Mixed-Fraktion bleibt unangetastet.
    assert csv_loaders.parse_range("5") == (5.0, 5.0)
    assert csv_loaders.parse_range("5-7") == (5.0, 7.0)
    assert csv_loaders.parse_range("5.5 ± 0.3") == pytest.approx((5.2, 5.8))
    assert csv_loaders.parse_range("2.65(5)") == pytest.approx((2.60, 2.70))


def test_parse_range_ascii_x_dimensions_separator():
    """ASCII ``x``/``X`` zwischen zwei Ziffern wird als Dimensions-Separator
    behandelt und liefert einen Range der Ausdehnungen statt silentem
    Datenverlust der zweiten Dimension.

    Spiegelt die bereits vorhandene Unicode-``×`` (U+00D7)-Range-Semantik auf
    die ASCII-Achse. In der Mineralogie ist die Compact-Notation ``5x10mm``
    der klassische Weg, "5 mm mal 10 mm" ohne separates Breite-Feld zu
    notieren - haeufig aus geerbten Excel-Kopien mit nur einer Groessen-
    Spalte, aus Foto-Katalog-Software mit Freitext-Groessen-Feld und aus
    handschriftlichen Sammler-Karten. Vor dem Fix blockte der ``_NUM_RE``-
    Lookbehind ``(?<![A-Za-z^])`` die zweite Zahl (``x`` als Letter),
    ``5x10`` lieferte (5.0, 5.0) statt (5.0, 10.0), ``5x10x15`` analog
    (5.0, 5.0) - silenter Range-Datenverlust auf der Groessen-Achse.
    """
    # Grundform Compact-Dimensions-Notation: zwei Dimensionen ohne Whitespace.
    assert csv_loaders.parse_range("5x10") == (5.0, 10.0)
    assert csv_loaders.parse_range("5X10") == (5.0, 10.0)
    # Mit Trailing-Einheit (SI-mm/cm/m); die Einheit bleibt Wort-Token und
    # blockiert die letzte Ziffer via ``_NUM_RE``-Lookbehind - der Wert-Anker
    # ist die vorletzte Zahl vor der Einheit.
    assert csv_loaders.parse_range("5x10mm") == (5.0, 10.0)
    assert csv_loaders.parse_range("5x10cm") == (5.0, 10.0)
    # Drei Dimensionen (Laenge x Breite x Hoehe): der Range spannt die
    # kleinste bis groesste Ausdehnung ab, sinnvoll fuer eine Sortier-/
    # Vergleichs-Groesse in einer Groessen-Spalte.
    assert csv_loaders.parse_range("5x10x15") == (5.0, 15.0)
    assert csv_loaders.parse_range("5x10x15mm") == (5.0, 15.0)
    # Dezimal-Vorstand (Millimeter-genaue Messung); ``5x3`` -> ``5 3``
    # via Digit-Anker.
    assert csv_loaders.parse_range("2.5x3.0mm") == (2.5, 3.0)
    assert csv_loaders.parse_range("2.5x3.0x4.0mm") == (2.5, 4.0)
    # DE-Komma-Dezimal-Vorstand (Excel-DE-Export); die Digit-Anker matchen
    # unabhaengig vom Locale-Dezimal-Trenner.
    assert csv_loaders.parse_range("2,5x3,0mm") == (2.5, 3.0)
    # Whitespace-Form ``5 x 10`` funktionierte schon bisher via Whitespace-
    # Separator; die neue Normalisierung greift nicht (kein digit-x-digit)
    # aber die Semantik bleibt identisch - Regression-Anker.
    assert csv_loaders.parse_range("5 x 10 mm") == (5.0, 10.0)
    assert csv_loaders.parse_range("5 x 10") == (5.0, 10.0)
    # Unicode ``×`` (U+00D7) matchte schon bisher als Range-Separator
    # (kein Letter im Lookbehind) - die neue Normalisierung greift nicht,
    # die Semantik bleibt identisch. Regression-Anker fuer die Konsistenz
    # zwischen ASCII- und Unicode-Achse.
    assert csv_loaders.parse_range("5×10") == (5.0, 10.0)
    assert csv_loaders.parse_range("5×10×15") == (5.0, 15.0)
    assert csv_loaders.parse_range("2.5×3.0mm") == (2.5, 3.0)
    # Kombination mit ± /(N)-Uncertainty: die Uncertainty-Zweige laufen
    # *vor* der Dimensions-Normalisierung und binden das Center an die erste
    # Zahl - die semantisch unklare Kombination ``5x10 ± 0.3`` wird als
    # ``5 ± 0.3`` gelesen (bestehende Semantik, Regression-Anker). Der
    # Dimensions-Sub greift nicht mehr, weil der Uncertainty-Zweig schon
    # zurueckgekehrt ist.
    assert csv_loaders.parse_range("5x10 ± 0.3") == pytest.approx((4.7, 5.3))
    # Kollisions-Schutz gegen Bezeichner-Position: Wort-Buchstaben mit ``x``
    # ohne Digit-Anker (``Excel``, ``Textur``, ``xylitol``) bleiben unangetastet
    # und liefern keine Zahl-Tokens - die Digit-Anker verhindern die
    # Substitution bei Nicht-Dimensions-Kontext.
    assert csv_loaders.parse_range("Excel") == (None, None)
    assert csv_loaders.parse_range("Textur ist grob") == (None, None)
    # Kollisions-Schutz gegen ASCII-Hochzahl-Einheiten: ``cm3``/``m^3`` ohne
    # Digit-x-Digit-Kontext bleiben unangetastet.
    assert csv_loaders.parse_range("cm3") == (None, None)
    assert csv_loaders.parse_range("m^3") == (None, None)
    # Kollisions-Schutz gegen ``Sample5x10``-Katalog-Bezeichner mit
    # angehaengter Dimensions-Notation: die Substitution greift zwar
    # (``5x1`` matcht), aber das ``5`` bleibt via ``_NUM_RE``-Letter-
    # Lookbehind (``e`` davor) blockiert - nur das ``10`` nach dem
    # Leerzeichen matcht und liefert (10, 10). Info-Gewinn gegenueber
    # (None, None) im alten Verhalten (der einzige gefundene Zahl-Wert
    # wird nicht mehr komplett verworfen).
    assert csv_loaders.parse_range("Sample5x10") == (10.0, 10.0)
    # Regression-Anker: bestehende Uncertainty-/Range-/Klammer-Semantik
    # ohne Dimensions-Notation bleibt unangetastet.
    assert csv_loaders.parse_range("5") == (5.0, 5.0)
    assert csv_loaders.parse_range("5-7") == (5.0, 7.0)
    assert csv_loaders.parse_range("5.5(3)") == pytest.approx((5.2, 5.8))
    assert csv_loaders.parse_range("5.5 ± 0.3") == pytest.approx((5.2, 5.8))
    assert csv_loaders.parse_range("5.5 (Foto)") == (5.5, 5.5)
    # Inverted-Range-Kollaps (``hi < lo``) greift bei semantisch invertierter
    # Dimensions-Notation ``4x2`` (Autor hat die groessere Dimension zuerst
    # geschrieben): ``4x2`` -> ``4 2`` -> nums=[4, 2] -> hi=2 < lo=4 -> (4, 4).
    # Konsistent mit dem bestehenden Tippfehler-Schutz aus
    # :func:`test_parse_range_keine_invertierten_paare`.
    assert csv_loaders.parse_range("4x2 cm") == (4.0, 4.0)


def test_parse_range_ascii_x_dimensions_kette_ungerade_segmente():
    """Verkettete ASCII-``x``-Dimensions-Notation mit ungeraden Segment-Laengen
    (``1x2x3``, ``5x1x2``) liefert die volle Range aller Dimensionen.

    Vor dem Lookahead-Fix konsumierte die Substitution ``(\\d)[xX](\\d)`` in
    einem Match-Schritt BEIDE Digit-Kanten, sodass der naechste Scan-Schritt
    hinter der rechten Ziffer weiterlief. Bei all-single-digit-Ketten fiel
    der zweite ``x`` damit auf ein Nicht-Digit-Zeichen (dem naechsten ``x``
    selbst, denn die vorhergehende ``x``-Position wurde konsumiert), und der
    naechste Match-Versuch scheiterte an fehlender rechter Digit-Kante fuer
    die letzte Zahl. Konkret:

    * ``1x2x3`` (5 Zeichen): erster Pass matcht ``1x2`` (pos 0-2, beide
      Ziffern konsumiert), Scan resumiert an pos 3 (dem zweiten ``x``), pos 3
      ist keine Ziffer -> kein Match. Pos 4 ``3`` steht isoliert ohne rechten
      Digit-Partner -> kein Match. Zwischenstand ``1 2x3``. Die ``3`` bleibt
      via ``_NUM_RE``-Letter-Lookbehind hinter dem ``x`` blockiert, nums=[1,
      2] -> ``(1, 2)`` statt der publizierten ``(1, 3)``. Die dritte
      Dimension ging silent verloren.
    * ``5x1x2`` (5 Zeichen): analog matcht der erste Pass ``5x1``, das zweite
      ``x`` bleibt ohne konsumiertes Zeichen zurueck, ``2`` blockiert weiter
      via Letter-Lookbehind, nums=[5, 1] -> ``(5, 5)`` via inverted-Range-
      Kollaps - die dritte Dimension komplett verloren.

    Der Lookahead-Fix ``(\\d)[xX](?=\\d)`` mit Substitution ``\\1 `` (nur die
    linke Ziffer plus Leerzeichen anstelle des ``x``, die rechte Ziffer
    bleibt fuer den naechsten Scan-Schritt stehen) macht die rechte Kante
    selbst wieder zur linken Kante der naechsten Digit-x-Digit-Sequenz.
    ``1x2x3`` -> ``1 2 3`` -> nums=[1, 2, 3] -> ``(1, 3)``; ``5x1x2`` ->
    ``5 1 2`` -> nums=[5, 1, 2] via inverted-Range-Kollaps auf ``(5, 5)``.

    Semantisch identisch zur Unicode-``×``-Behandlung: die ``×`` blockiert
    ``_NUM_RE`` ohnehin nicht (kein Letter), alle konsekutiven ``×``-
    Sequenzen wurden schon bisher transparent gelesen. Der Fix schliesst
    die letzte Asymmetrie zwischen ASCII- und Unicode-Achse.
    """
    # All-single-digit-Kette (drei Dimensionen): jede Position eine einzelne
    # Ziffer, ungerade Segment-Laenge nach dem ersten Match.
    assert csv_loaders.parse_range("1x2x3") == (1.0, 3.0)
    assert csv_loaders.parse_range("1X2X3") == (1.0, 3.0)
    # All-single-digit-Kette mit invertierter mittlerer Dimension: der Kollaps
    # greift auf die groesste linke Kante, weil hi < lo.
    assert csv_loaders.parse_range("5x1x2") == (5.0, 5.0)
    # Vier-Dimensionen-Kette (all-single-digit): jede Substitution greift
    # unabhaengig via Lookahead.
    assert csv_loaders.parse_range("1x2x3x4") == (1.0, 4.0)
    # Fuenf-Dimensionen-Kette: laengere Ketten funktionieren transparent.
    assert csv_loaders.parse_range("1x2x3x4x5") == (1.0, 5.0)
    # Trailing-Einheit an einer all-single-digit-Kette: die letzte Ziffer
    # bleibt hinter der Einheit hinter dem Buchstaben-Lookbehind blockiert,
    # aber die vorletzte Ziffer ist die max-Dimension.
    assert csv_loaders.parse_range("1x2x3mm") == (1.0, 3.0)
    assert csv_loaders.parse_range("1x2x3x4cm") == (1.0, 4.0)
    # Mixed-length-Kette (single-multi-single): der Lookahead greift an jeder
    # Position unabhaengig von der Segment-Laenge. Die parse_range-Semantik
    # ist erste-Zahl-als-lo / letzte-Zahl-als-hi (nicht min/max), spiegelt
    # die bestehende Range-Konvention "erste bis letzte Grenze".
    assert csv_loaders.parse_range("1x10x3") == (1.0, 3.0)   # letzte < mittlere -> lo/hi bleiben erste/letzte
    assert csv_loaders.parse_range("1x2x30") == (1.0, 30.0)
    assert csv_loaders.parse_range("10x2x3") == (10.0, 10.0)  # letzte < erste -> inverted-Kollaps
    # DE-Komma-Dezimal-Vorstand in einer Kette (Excel-DE-Export).
    assert csv_loaders.parse_range("1,5x2,5x3,5") == (1.5, 3.5)
    # Regress-Anker: Unicode-``×``-Kette liefert dieselben Ergebnisse
    # (Konsistenz zwischen ASCII- und Unicode-Achse).
    assert csv_loaders.parse_range("1×2×3") == (1.0, 3.0)
    assert csv_loaders.parse_range("5×1×2") == (5.0, 5.0)
    assert csv_loaders.parse_range("1×2×3×4") == (1.0, 4.0)
    # Regress-Anker: Zwei-Dimensions-Grundform (aus dem urspruenglichen Test)
    # bleibt identisch, kein Lookahead-Regress.
    assert csv_loaders.parse_range("5x10") == (5.0, 10.0)
    assert csv_loaders.parse_range("5x10mm") == (5.0, 10.0)
    assert csv_loaders.parse_range("2.5x3.0mm") == (2.5, 3.0)
    # Regress-Anker: gerade-length-Ketten (aus dem urspruenglichen Test)
    # bleiben identisch - die alten Assertionen greifen auf denselben
    # Ausdruck via Zufaellige-Position-Ausrichtung.
    assert csv_loaders.parse_range("5x10x15") == (5.0, 15.0)
    assert csv_loaders.parse_range("2.5x3.0x4.0mm") == (2.5, 4.0)


def test_parse_range_negatives_vorzeichen():
    """Fuehrendes Minus-Vorzeichen wird als negatives Signum an die folgende Zahl
    gebunden, ohne die bestehende Range-Separator-Semantik zu beruehren.

    Vor dem Fix verwarf die generische Zahl-Extraktion (siehe :data:`_NUM_RE`)
    still jedes fuehrende ASCII-Minus-Vorzeichen, weil das Regex nur den
    Ziffernteil einfing:

    * ``"-5.5"``      -> ``[5.5]``       -> (5.5, 5.5)    (Vorzeichen verloren)
    * ``"-10 - -5"``  -> ``[10, 5]``     -> (10.0, 10.0)  (beide Vorzeichen verloren + inverted-Kollaps)
    * ``"-10 - 5"``   -> ``[10, 5]``     -> (10.0, 10.0)  (linkes Vorzeichen verloren + inverted-Kollaps)
    * ``"ca. -5.5"``  -> ``[5.5]``       -> (5.5, 5.5)    (Vorzeichen verloren nach Freitext-Praefix)
    * ``"-10,5–-5,5"``-> ``[10.5, 5.5]`` -> (10.5, 10.5)  (DE-Komma + en-dash, beide Vorzeichen verloren)

    Bei der Migration aus Cryo-Mineralogie-Notizen (Frost-/Eis-Kristall-
    Sammlungen mit Temperatur-Bereichen unter 0 °C), Bergbau-/Tektonik-
    Tiefen-Berichten (negative Meereshoehe als Kristall-Fundort), Isotopen-
    Fraktionierungs-Daten (δ¹³C, δ¹⁸O in ‰ - typisch negativ fuer viele
    Karbonate/Silikate), thermischen Ausdehnungs-Koeffizienten (β < 0 bei
    einigen Kristall-Klassen wie Quarz alpha-beta-Uebergang) oder aus
    Vergleichs-Deltas (``Δn`` in Doppelbrechungs-Tabellen) entstand damit
    silenter Vorzeichen-Datenverlust auf jedem Numeric-Feld, das Nullpunkt-
    negative Werte tragen kann. Im schlimmsten Fall (symmetrischer negativer
    Range) wurden die absoluten Werte gespiegelt (10.0 statt -10.0) - eine
    Vorzeichen-Inversion, die mineralogisch/physikalisch nicht auffaellt,
    aber die publizierte Temperatur- oder Isotopen-Achse komplett verwirft.

    Der Fix erweitert ``_NUM_RE`` um eine optionale Sign-Alternante
    ``(?:(?<![\\d.])-)?`` vor dem Digit-Teil - das Minus wird nur an
    Positionen als Vorzeichen gebunden, an denen das VOR dem Minus stehende
    Zeichen weder Digit noch Dezimalpunkt ist. Dadurch bleibt die bestehende
    Range-Separator-Semantik unangetastet: in ``"5-7"`` und ``"5.5-7.0"``
    steht ein Digit unmittelbar vor dem Minus, der Sign-Match blockt via
    ``(?<![\\d.])`` und der Hyphen bleibt Range-Trenner. Nur wenn das
    Zeichen vor dem Minus ein Whitespace, Start-of-String, Klammer-Rand,
    anderer Dash-Typ (en-/em-dash) oder anderes Non-Digit-Separator-Zeichen
    (``=``, ``:``, ``/``, ``&``, ``,``) ist, wird der Minus als Vorzeichen
    interpretiert - genau die Positionen, an denen ein Minus semantisch
    kein Range-Separator sein kann.
    """
    # Einzelwert negativ - klassischer Cryo-Temperatur-Wert oder Isotopen-
    # Fraktionierung.
    assert csv_loaders.parse_range("-5.5") == (-5.5, -5.5)
    assert csv_loaders.parse_range("-10") == (-10.0, -10.0)
    assert csv_loaders.parse_range("-0.5") == (-0.5, -0.5)
    # Symmetrischer negativer Range mit ASCII-Hyphen als Range-Separator
    # zwischen zwei negativen Bounds - typisch fuer Cryo-Temperatur-Fenster
    # ("-10 - -5 °C") oder Isotopen-Delta-Bereiche.
    assert csv_loaders.parse_range("-10 - -5") == (-10.0, -5.0)
    assert csv_loaders.parse_range("-10--5") == (-10.0, -5.0)
    # En-dash (U+2013) und em-dash (U+2014) als Range-Separator zwischen zwei
    # negativen Bounds - typografisch sauber gesetzte Print-/PDF-Publikationen
    # verwenden en-dash statt ASCII-Hyphen fuer Bereichs-Notation.
    assert csv_loaders.parse_range("-10 – -5") == (-10.0, -5.0)
    assert csv_loaders.parse_range("-10 — -5") == (-10.0, -5.0)
    # Vorzeichen-gemischter Range (negativ zu positiv) - typisch fuer
    # Temperatur-Fenster ueber den Nullpunkt hinweg ("-10 bis +5 °C").
    assert csv_loaders.parse_range("-10 - 5") == (-10.0, 5.0)
    assert csv_loaders.parse_range("-10–5") == (-10.0, 5.0)
    # Freitext-Praefix (Annaeherungs-Marker) vor negativem Wert - der Wert
    # muss trotz Praefix sein Vorzeichen behalten.
    assert csv_loaders.parse_range("ca. -5.5") == (-5.5, -5.5)
    assert csv_loaders.parse_range("circa -5.5") == (-5.5, -5.5)
    # DE-Komma-Dezimal mit negativem Vorzeichen - deutsche Publikationen und
    # Excel-DE-Auto-Format schreiben ``-2,65`` mit Komma-Dezimal.
    assert csv_loaders.parse_range("-2,65") == (-2.65, -2.65)
    assert csv_loaders.parse_range("-10,5 - -5,5") == (-10.5, -5.5)
    assert csv_loaders.parse_range("-10,5–-5,5") == (-10.5, -5.5)
    # Trailing-Einheit nach negativem Wert - die Einheit hat keine Zahlen,
    # damit die Groessenordnung erhalten bleibt.
    assert csv_loaders.parse_range("-5.5 °C") == (-5.5, -5.5)
    assert csv_loaders.parse_range("-10 - -5 °C") == (-10.0, -5.0)
    # Scientific notation mit negativem Vorzeichen an der Mantisse - typisch
    # fuer sub-Einheiten-Groessen im negativen Bereich (thermische
    # Ausdehnungs-Koeffizienten, Absorptions-Deltas).
    assert csv_loaders.parse_range("-1.5e-3") == (-0.0015, -0.0015)
    assert csv_loaders.parse_range("-1e3") == (-1000.0, -1000.0)
    # Leading-Dot-Dezimal mit negativem Vorzeichen (``-.5`` = -0.5, US-
    # Konvention "no leading zero" mit Minus-Praefix).
    assert csv_loaders.parse_range("-.5") == (-0.5, -0.5)
    assert csv_loaders.parse_range("-.5-.7") == (-0.5, 0.7)
    # Negativer Wert mit Uncertainty-Langform (``-1.5 ± 0.3``) - der
    # bestehende _PLUS_MINUS_UNCERTAINTY-Zweig faengt den Fall bereits, hier
    # als Regression-Anker fuer die Prioritaets-Reihenfolge (Uncertainty vor
    # generischer Zahl-Extraktion).
    assert csv_loaders.parse_range("-1.5 ± 0.3") == pytest.approx((-1.8, -1.2))
    # Regression-Anker: die bestehende Range-Separator-Semantik bleibt
    # unveraendert - in ``"5-7"`` steht Digit vor Minus, der Sign-Match
    # blockt und der Hyphen bleibt Range-Trenner.
    assert csv_loaders.parse_range("5-7") == (5.0, 7.0)
    assert csv_loaders.parse_range("5.5-7.0") == (5.5, 7.0)
    assert csv_loaders.parse_range("5") == (5.0, 5.0)
    assert csv_loaders.parse_range("5.5") == (5.5, 5.5)
    # Regression-Anker: Leading-Dot-Dezimal ohne Vorzeichen bleibt
    # unveraendert.
    assert csv_loaders.parse_range(".5") == (0.5, 0.5)
    assert csv_loaders.parse_range(".5-.7") == (0.5, 0.7)
    # Regression-Anker: Freitext-Praefix ohne Vorzeichen bleibt unveraendert
    # (der optional-sign-Zweig blockt korrekt bei Nicht-Minus-Praefix).
    assert csv_loaders.parse_range("ca. 5.5") == (5.5, 5.5)
    assert csv_loaders.parse_range("ca. 2.65") == (2.65, 2.65)
    # Regression-Anker: scientific notation ohne Vorzeichen bleibt
    # unveraendert (der Exponent-``-`` bleibt Teil des Ganz-Tokens).
    assert csv_loaders.parse_range("1e-3") == (0.001, 0.001)
    assert csv_loaders.parse_range("1.5e-3") == (0.0015, 0.0015)
    # Regression-Anker: SI-Einheit-Suffix mit ASCII-Superskript (``cm3``,
    # ``m^3``) blockt die Ziffer im Suffix - Buchstabe/Caret vor Digit
    # trifft den bestehenden ``(?<![A-Za-z^])``-Lookbehind, das neue
    # Sign-Lookbehind ist eine unabhaengige Schicht.
    assert csv_loaders.parse_range("2.65 g/cm3") == (2.65, 2.65)
    assert csv_loaders.parse_range("-2.65 g/cm3") == (-2.65, -2.65)
    # Regression-Anker: inverted-Range-Kollaps bleibt aktiv, wenn der
    # negative hi arithmetisch kleiner als der negative lo ist
    # (Tippfehler-Robustheit spiegelt die positive Konvention).
    assert csv_loaders.parse_range("-5 - -10") == (-5.0, -5.0)
    # Regression-Anker: Klammer-Annotation nach negativem Wert wird
    # gestrippt und die Annotations-Zahl darf nicht als Range-Grenze
    # fehlgelesen werden.
    assert csv_loaders.parse_range("-5.5 (Ref 42)") == (-5.5, -5.5)
    assert csv_loaders.parse_range("-10 - -5 [Nr. 42]") == (-10.0, -5.0)


def test_parse_range_typografisches_minus_u2212():
    """Typografisches Minus-Zeichen U+2212 (MINUS SIGN) wird in der
    Vorverarbeitung auf ASCII-Hyphen normalisiert, damit die Sign-Bindung in
    :data:`_NUM_RE` greift und negative Werte aus typeset-Quellen ihr
    Vorzeichen behalten.

    Vor dem Fix fielen alle U+2212-vorangestellten Werte durch die ASCII-only-
    Sign-Alternante des :data:`_NUM_RE`-Regex (``(?<![\\d.%‰])-``) und
    lieferten silente ihren Absolut-Betrag:

    * ``"−5.5"``          -> ``[5.5]``       -> (5.5, 5.5)    (Vorzeichen verloren)
    * ``"−5.5 ± 0.3"``    -> Fallback        -> (5.5, 5.5)    (Vorzeichen UND Toleranz verloren)
    * ``"−5.5(3)"``       -> Fallback        -> (5.5, 5.5)    (dito IUCr-Kompakt)
    * ``"−1.5 ± 0.3 °C"`` -> Fallback        -> (1.5, 1.5)    (Kryo-Temperatur)
    * ``"−15.5 ± 0.5 ‰"`` -> Fallback        -> (15.5, 15.5)  (Isotopen-Delta)
    * ``"−10 − −5"``      -> ``[10, 5]``     -> (10.0, 10.0)  (Cryo-Range mit U+2212 dreifach)

    U+2212 ist der kanonische Minus-Setz aus Print-/PDF-Publikationen
    (LaTeX-Autoformat, Word/Office-Autoformat wandelt ``-`` im Zahl-Kontext
    automatisch zu U+2212), GPS-/Editor-Tools mit "smart punctuation" und
    typografisch sauber gesetzten Katalogen. Bei der Migration aus solchen
    Quellen entstand silenter Vorzeichen-Datenverlust auf allen Numeric-
    Achsen mit Nullpunkt-negativen Werten (Kryo-Temperaturen, Isotopen-
    Fraktionierungs-Deltas in ‰, thermische Ausdehnungs-Koeffizienten β < 0,
    Meereshoehe-negative Fundort-Tiefen).

    Der Fix normalisiert U+2212 in :func:`normalize_numeric_locale` per
    Single-Pass-Strip auf ASCII-Hyphen ``-``. Das ist einfacher und sicherer
    als alle Zahl-/Uncertainty-Patterns parallel um U+2212-Alternation zu
    erweitern - spiegelt den gleichen Vorverarbeitungs-Ansatz aus
    :func:`stonebook.migration.validators.parse_coordinates`.

    Kollisionsfreiheit zur Range-Separator-Rolle: U+2212 zwischen zwei
    Zahlen (``"5.5 − 7.5"`` / ``"5.5−7.5"``) faellt nach der Normalisierung
    in die bereits vorhandene ASCII-Hyphen-Range-Separator-Logik, wo der
    Sign-Lookbehind ``(?<![\\d.%‰])-`` die Sign-Bindung nach der ersten
    Digit blockiert - Range-Semantik bleibt unveraendert.
    """
    # Einzelwert mit U+2212 als Vorzeichen - klassischer Cryo-Temperatur-Wert
    # aus Print-Publikationen oder PDF-Katalog.
    assert csv_loaders.parse_range("−5.5") == (-5.5, -5.5)
    assert csv_loaders.parse_range("−10") == (-10.0, -10.0)
    assert csv_loaders.parse_range("−0.5") == (-0.5, -0.5)
    # U+2212 als Vorzeichen mit ±-Uncertainty-Langform - der Uncertainty-Zweig
    # muss die Toleranz auch mit typografischem Minus richtig auswerten.
    assert csv_loaders.parse_range("−5.5 ± 0.3") == pytest.approx((-5.8, -5.2))
    assert csv_loaders.parse_range("−1.5 ± 0.3") == pytest.approx((-1.8, -1.2))
    # U+2212 als Vorzeichen mit IUCr-Kompakt-Notation ``N(M)`` - Klammer-
    # Toleranz auf die letzten Ziffern des negativen Zentrums.
    assert csv_loaders.parse_range("−5.5(3)") == pytest.approx((-5.8, -5.2))
    assert csv_loaders.parse_range("−2.65(5)") == pytest.approx((-2.70, -2.60))
    # U+2212 als Vorzeichen mit Trailing-Einheit-Uncertainty - Kryo-Temperatur
    # in °C ist der klassische Anwendungsfall mit publizierter Toleranz.
    assert csv_loaders.parse_range("−1.5 ± 0.3 °C") == pytest.approx((-1.8, -1.2))
    assert csv_loaders.parse_range("−12 ± 2 °C") == (-14.0, -10.0)
    # U+2212 als Vorzeichen mit Promille-Einheit-Uncertainty - Isotopen-
    # Fraktionierungs-Werte δ¹³C/δ¹⁸O sind typisch negativ im ‰-Bereich.
    assert csv_loaders.parse_range("−15.5 ± 0.5 ‰") == (-16.0, -15.0)
    assert csv_loaders.parse_range("−7.2 ± 0.1 ‰") == pytest.approx((-7.3, -7.1))
    # U+2212 als Vorzeichen mit Trailing-Einheit (ohne Uncertainty).
    assert csv_loaders.parse_range("−5.5 g/cm³") == (-5.5, -5.5)
    assert csv_loaders.parse_range("−5.5 g") == (-5.5, -5.5)
    assert csv_loaders.parse_range("−273.15 °C") == (-273.15, -273.15)
    # U+2212 sowohl als Vorzeichen als auch als Range-Separator - typische
    # Print-Publikations-Notation "Cryo-Temperatur -10 bis -5 °C".
    assert csv_loaders.parse_range("−10 − −5") == (-10.0, -5.0)
    assert csv_loaders.parse_range("−10 − −5 °C") == (-10.0, -5.0)
    # Gemischt: U+2212 als Vorzeichen, ASCII-Hyphen als Range-Separator.
    assert csv_loaders.parse_range("−10 - −5") == (-10.0, -5.0)
    # U+2212 nur als Vorzeichen der ersten Bound, positive zweite Bound
    # (Temperatur-Range ueber Nullpunkt).
    assert csv_loaders.parse_range("−10 - 5") == (-10.0, 5.0)
    assert csv_loaders.parse_range("−10 − 5") == (-10.0, 5.0)
    # DE-Komma-Dezimal mit U+2212-Vorzeichen - typografisch sauber gesetzte
    # DE-Publikationen kombinieren Komma-Dezimal und U+2212-Minus.
    assert csv_loaders.parse_range("−2,65") == (-2.65, -2.65)
    assert csv_loaders.parse_range("−10,5 − −5,5") == (-10.5, -5.5)
    # Freitext-Praefix (Annaeherungs-Marker) vor U+2212-Wert - der Wert muss
    # sein Vorzeichen behalten.
    assert csv_loaders.parse_range("ca. −5.5") == (-5.5, -5.5)
    assert csv_loaders.parse_range("circa −5.5") == (-5.5, -5.5)
    # Scientific notation mit U+2212 an der Mantisse - typisch fuer
    # sub-Einheiten-Groessen im negativen Bereich.
    assert csv_loaders.parse_range("−1.5e-3") == pytest.approx((-0.0015, -0.0015))
    assert csv_loaders.parse_range("−1e3") == (-1000.0, -1000.0)
    # Leading-Dot-Dezimal mit U+2212 (``−.5`` = -0.5, typografisch sauberes
    # US-Konvention "no leading zero" mit Print-Minus).
    assert csv_loaders.parse_range("−.5") == (-0.5, -0.5)
    # Klammer-Annotation nach U+2212-Wert wird gestrippt.
    assert csv_loaders.parse_range("−5.5 (Ref 42)") == (-5.5, -5.5)
    assert csv_loaders.parse_range("−10 − −5 [Nr. 42]") == (-10.0, -5.0)
    # Regression-Anker: U+2212 zwischen zwei positiven Zahlen ohne
    # Vorzeichen-Rolle bleibt Range-Separator (die neue Normalisierung
    # laesst die bestehende Range-Semantik unveraendert).
    assert csv_loaders.parse_range("5.5 − 7.5") == (5.5, 7.5)
    assert csv_loaders.parse_range("5.5−7.5") == (5.5, 7.5)
    assert csv_loaders.parse_range("5 − 7") == (5.0, 7.0)
    # Regression-Anker: en-dash (U+2013) und em-dash (U+2014) bleiben
    # unangetastet als Range-Separatoren - nur U+2212 wird normalisiert,
    # die anderen typografischen Dash-Varianten sind semantisch immer
    # Range-Separatoren.
    assert csv_loaders.parse_range("5.5 – 7.5") == (5.5, 7.5)
    assert csv_loaders.parse_range("5.5 — 7.5") == (5.5, 7.5)
    # Regression-Anker: Werte ohne U+2212 bleiben komplett unveraendert.
    assert csv_loaders.parse_range("5.5") == (5.5, 5.5)
    assert csv_loaders.parse_range("5.5 ± 0.3") == pytest.approx((5.2, 5.8))
    assert csv_loaders.parse_range("2.65(5)") == pytest.approx((2.60, 2.70))


def test_normalize_numeric_locale_typografisches_minus_u2212():
    """:func:`normalize_numeric_locale` normalisiert U+2212 auf ASCII-Hyphen,
    damit die AI-Response-Koerzitierung in :mod:`stonebook.ai.providers`
    auch typografisch gesetzte negative Werte aus Modell-Antworten korrekt
    einliest.

    KI-Modelle geben typeset-Minus-Zeichen (U+2212) gern in wissenschaftlichen
    Kontexten aus (Kryo-Temperaturen ``−12 °C``, Isotopen-Fraktionierungen
    ``−15.5 ‰``), weil das System-Prompt-Umfeld eine typografisch saubere
    Ausgabe suggeriert. Ohne die U+2212-Normalisierung fiele die :data:`_LEADING_NUMBER`-
    Extraktion (``[-+]?\\d+``) auf den positiven Betrag zurueck - der
    Sammler-Wert wuerde als ``12 °C`` statt ``-12 °C`` in die Datenbank
    wandern, mit silenter Vorzeichen-Inversion auf jeder Numeric-Achse.
    """
    # U+2212 wird auf ASCII-Hyphen normalisiert (Vorzeichen-Rolle bleibt
    # erhalten, die Kombination mit :data:`_LEADING_NUMBER` liefert den
    # negativen Wert).
    assert csv_loaders.normalize_numeric_locale("−5.5") == "-5.5"
    assert csv_loaders.normalize_numeric_locale("−12 °C") == "-12 °C"
    assert csv_loaders.normalize_numeric_locale("−15.5 ‰") == "-15.5 ‰"
    # Kombination mit Schweizer Apostroph-Tausender (bereits vorhandene
    # Vorverarbeitung) und U+2212-Vorzeichen.
    assert csv_loaders.normalize_numeric_locale("−1'500.00") == "-1500.00"
    # Ohne U+2212 bleibt der Text unveraendert (der Strip ist idempotent
    # und veraendert Nicht-U+2212-Zeichen nicht).
    assert csv_loaders.normalize_numeric_locale("-5.5") == "-5.5"
    assert csv_loaders.normalize_numeric_locale("5.5") == "5.5"
    # En-dash und em-dash bleiben unangetastet (nur U+2212 wird normalisiert).
    assert csv_loaders.normalize_numeric_locale("5.5 – 7.5") == "5.5 – 7.5"
    assert csv_loaders.normalize_numeric_locale("5.5 — 7.5") == "5.5 — 7.5"


def test_parse_range_repetierte_einheit_wird_gestrippt():
    """Repetierte-Einheit-Range ``<Wert><Einheit>-<Wert><Einheit>`` (``3mm-5mm``,
    ``1.5g-2.5g``, ``5cm-10cm``, ``10kg-15kg``) wird als Bereich mit beiden
    Grenzen erkannt, statt still auf den ersten Wert zu kollabieren.

    In Sammler-Notizen und Fund-Etiketten ist die kompakte Repetitions-
    Schreibweise (Einheit an beiden Bereichs-Grenzen) verbreitet, weil der
    Sammler die Einheit als Teil des jeweiligen Wertes ansieht und nicht als
    trailing-suffix: "Rauchquarz-Cluster 3mm-5mm", "Chalkopyrit 10g-50g",
    "Amethyst-Druse 5cm-10cm". Ohne Fix fielen alle Formen still auf
    ``(lo, lo)`` (obere Bereichs-Grenze verloren):

    * ``"3mm-5mm"``    -> ``(3.0, 3.0)``   statt ``(3.0, 5.0)``
    * ``"1.5g-2.5g"``  -> ``(1.5, 1.5)``   statt ``(1.5, 2.5)``
    * ``"5cm-10cm"``   -> ``(5.0, 5.0)``   statt ``(5.0, 10.0)``
    * ``"10kg-15kg"``  -> ``(10.0, 10.0)`` statt ``(10.0, 15.0)``

    Ursache: der Sign-Lookbehind ``(?<![A-Za-z^]-)`` in :data:`_NUM_RE`
    blockiert den ``m-`` -> ``2`` Uebergang (Buchstabe + Hyphen ergibt Sign-
    Bindung, die verhindert dass die obere Grenze als eigenstaendige Zahl
    gelesen wird). Der ``\\d+``-Fallback matcht dann nur den Ziffern-Rest
    der oberen Grenze (``20`` -> ``0``, ``15`` -> ``5``), und der Range-
    Zahl-Extract kollabiert via ``hi < lo``-Fallback auf ``(lo, lo)``.

    Fix: :func:`_strip_repeated_unit` erkennt die Repetition per Backreference
    ``\\2`` und transformiert ``3mm-5mm`` -> ``3-5 mm`` (Trailing-Einheit-Form
    wie ``5-10 mm``, die schon vor dem Fix korrekt behandelt wurde). Die
    Transformation ist semantisch aequivalent (dieselbe Einheit gilt fuer
    beide Grenzen) und nicht-invasiv (die weiteren parse_range-Pfade bleiben
    unveraendert).
    """
    # Basis-Formen: SI-Basis-Einheiten (mm, cm, dm, m, km) mit Ganzzahl-Bereich.
    assert csv_loaders.parse_range("3mm-5mm") == (3.0, 5.0)
    assert csv_loaders.parse_range("5cm-10cm") == (5.0, 10.0)
    assert csv_loaders.parse_range("10km-20km") == (10.0, 20.0)
    assert csv_loaders.parse_range("100mm-200mm") == (100.0, 200.0)
    # Gewichts-Einheiten (g, kg, mg) - fuer Sammlungs-Ueberblick-Notation.
    assert csv_loaders.parse_range("10g-50g") == (10.0, 50.0)
    assert csv_loaders.parse_range("1kg-3kg") == (1.0, 3.0)
    assert csv_loaders.parse_range("100mg-500mg") == (100.0, 500.0)
    # Dezimal-Werte in beiden Grenzen mit US-Punkt-Konvention.
    assert csv_loaders.parse_range("1.5g-2.5g") == pytest.approx((1.5, 2.5))
    assert csv_loaders.parse_range("0.5kg-1.5kg") == pytest.approx((0.5, 1.5))
    assert csv_loaders.parse_range("3.5mm-7.5mm") == pytest.approx((3.5, 7.5))
    # Dezimal-Werte mit DE-Komma-Konvention - Excel-DE-Export-typisch.
    assert csv_loaders.parse_range("1,5g-2,5g") == pytest.approx((1.5, 2.5))
    assert csv_loaders.parse_range("0,5kg-1,5kg") == pytest.approx((0.5, 1.5))
    assert csv_loaders.parse_range("3,5mm-7,5mm") == pytest.approx((3.5, 7.5))
    # Whitespace zwischen Wert und Einheit auf beiden Seiten - vor dem Fix
    # ebenfalls fehlerhaft (``m-2`` = Buchstabe+Hyphen).
    assert csv_loaders.parse_range("3 mm-5 mm") == (3.0, 5.0)
    assert csv_loaders.parse_range("1.5 g-2.5 g") == pytest.approx((1.5, 2.5))
    assert csv_loaders.parse_range("10 kg-15 kg") == (10.0, 15.0)
    # Whitespace um den Bindestrich (mit repetierter Einheit) - der Fix
    # muss auch die "hoefliche" Notation behandeln.
    assert csv_loaders.parse_range("3mm - 5mm") == (3.0, 5.0)
    assert csv_loaders.parse_range("1.5g - 2.5g") == pytest.approx((1.5, 2.5))
    # Umschliessende Klammern - der Klammer-Strip laesst ``(3mm-5mm)`` als
    # Wert-Traeger unangetastet (Wert-selbst-in-Klammern-Ruecksetzung), aber
    # die _NUM_RE-Extraktion greift trotzdem korrekt nach der Repetitions-
    # Normalisierung.
    assert csv_loaders.parse_range("(3mm-5mm)") == (3.0, 5.0)
    assert csv_loaders.parse_range("[1.5g-2.5g]") == pytest.approx((1.5, 2.5))
    assert csv_loaders.parse_range("{10kg-15kg}") == (10.0, 15.0)
    # Freitext-Praefix vor der Range - typische Sammler-Notation mit
    # Prosa-Kontext ("Groesse: 3mm-5mm", "Gewicht 10g-50g").
    assert csv_loaders.parse_range("Groesse 3mm-5mm") == (3.0, 5.0)
    assert csv_loaders.parse_range("Gewicht 10g-50g") == (10.0, 50.0)
    assert csv_loaders.parse_range("size 3mm-5mm") == (3.0, 5.0)
    # Trenner-Varianten: en-dash und em-dash (typografisch aus Print-Quellen).
    assert csv_loaders.parse_range("3mm–5mm") == (3.0, 5.0)
    assert csv_loaders.parse_range("3mm—5mm") == (3.0, 5.0)
    # Kombinierbar mit Annaeherungs-Praefix (``ca.``, ``~``).
    assert csv_loaders.parse_range("ca. 3mm-5mm") == (3.0, 5.0)
    assert csv_loaders.parse_range("~3mm-5mm") == (3.0, 5.0)
    assert csv_loaders.parse_range("circa 1.5g-2.5g") == pytest.approx((1.5, 2.5))
    # Regress-Anker: gleiche Einheit ist Pflicht - Mixed-Unit-Formen
    # (``3mm-5cm``) bleiben unangetastet und kollabieren wie bisher.
    assert csv_loaders.parse_range("3mm-5cm") == (3.0, 3.0)
    assert csv_loaders.parse_range("10g-50kg") == (10.0, 10.0)
    # Regress-Anker: Einheit nur auf einer Seite bleibt unangetastet
    # (der Trailing-Einheit-Form ``5-10 mm`` matcht schon vor dem Fix korrekt).
    assert csv_loaders.parse_range("3-5 mm") == (3.0, 5.0)
    assert csv_loaders.parse_range("3-5mm") == (3.0, 5.0)
    # Einheit nur an der ersten Grenze (``3mm-5``): der Fix greift NICHT
    # (die Backreference ``\\2`` verlangt exakte Einheit auf beiden Seiten).
    # Die _NUM_RE-Sign-Blockierung ``(?<![A-Za-z^]-)`` blockiert die ``-5``
    # weiterhin, das Verhalten bleibt vor-Fix-identisch (kollabiert auf
    # ``(3.0, 3.0)``). Dieser Grenzfall ist ausserhalb der Fix-Scope,
    # weil die Notation ``<Wert><Einheit>-<Wert>`` ohne repetierte Einheit
    # in Sammler-Notizen praktisch nicht vorkommt.
    assert csv_loaders.parse_range("3mm-5") == (3.0, 3.0)
    # Regress-Anker: der Sicherheits-Guard verhindert False-Positives an
    # eingebetteten Positionen wie ``field-1abc-2abc`` (dort ist ``1abc-
    # 2abc`` von ``-`` und Buchstabe umgeben, nicht von Whitespace/Anfang).
    assert csv_loaders.parse_range("field-1abc-2abc") == (None, None)
    # Regress-Anker: Prozent- und Promille-Range unveraendert (die Sign-
    # Blockierung ``(?<![\\d.%‰])-`` behandelt %/‰ als eigenen Wert-
    # Terminator; die neue Repetitions-Klasse ``[A-Za-zµ°]{1,4}`` enthaelt
    # ``%``/``‰`` nicht und beruehrt diese Formen nicht).
    assert csv_loaders.parse_range("5%-10%") == (5.0, 10.0)
    assert csv_loaders.parse_range("0.5‰-2.5‰") == pytest.approx((0.5, 2.5))
    # Regress-Anker: wissenschaftliche E-Notation ``1e3-2e3`` bleibt
    # unangetastet (``e3`` matcht die Einheit-Klasse nicht als vollstaendige
    # Einheit - der Trailing-Guard scheitert am nachfolgenden ``-``).
    assert csv_loaders.parse_range("1e3-2e3") == (1000.0, 2000.0)
    # Regress-Anker: g/cm³ und aehnliche zusammengesetzte Einheiten bleiben
    # unangetastet (die Einheit-Klasse enthaelt ``/``/``³``/``²`` nicht;
    # die bestehende Trailing-Einheit-Form ``2.65 g/cm³ - 5.5 g/cm³`` greift
    # per Whitespace-um-Bindestrich-Trenner in ``_NUM_RE``).
    assert csv_loaders.parse_range("2.65 g/cm³ - 5.5 g/cm³") == pytest.approx((2.65, 5.5))
    # Regress-Anker: Einzelwert mit Einheit unveraendert (kein Range-
    # Separator - der Regex matcht nicht).
    assert csv_loaders.parse_range("5mm") == (5.0, 5.0)
    assert csv_loaders.parse_range("2.5g") == pytest.approx((2.5, 2.5))
    # Regress-Anker: plain Range ohne Einheit unveraendert.
    assert csv_loaders.parse_range("3-5") == (3.0, 5.0)
    assert csv_loaders.parse_range("1.5-2.5") == pytest.approx((1.5, 2.5))
    # Regress-Anker: Uncertainty-Notation unveraendert (der ±-Zweig matcht
    # vor der Range-Zahl-Extraktion; die Repetition-Normalisierung greift
    # nur wenn ein Bindestrich zwischen zwei Zahl+Einheit-Tupeln liegt).
    assert csv_loaders.parse_range("5.5 ± 0.3") == pytest.approx((5.2, 5.8))
    assert csv_loaders.parse_range("5.5 mm ± 0.3 mm") == pytest.approx((5.2, 5.8))
    # Grenzfall: Groessere Ganzzahlen mit repetierter Einheit.
    assert csv_loaders.parse_range("100g-500g") == (100.0, 500.0)
    assert csv_loaders.parse_range("1000mm-2000mm") == (1000.0, 2000.0)
    # Grenzfall: Repetierte Einheit mit gleichen Werten (kein echter Range,
    # aber der Regex greift trotzdem und die Extraktion liefert (n, n)).
    assert csv_loaders.parse_range("5mm-5mm") == (5.0, 5.0)


def test_parse_range_dotted_separator_wird_zu_bindestrich():
    """ASCII-Doppel-/Dreifach-Dot als Range-Separator (``3.5..5.5``, ``1..10``,
    ``3.5...5.5``, ``1e5..2e5``) wird in der Vorverarbeitung auf einen
    einfachen Bindestrich normalisiert, damit die generische Zahl-Extraktion
    beide Range-Grenzen aufloest.

    Vor dem Fix fielen alle Formen still auf einen Range-Kollaps auf den ersten
    Wert zurueck, weil :data:`_NUM_RE` den zweiten Dot als "leading-dot decimal"
    liest und die Zahl-Menge in ``[lo, teil-von-hi]`` zerfaellt:

    * ``"3.5..5.5"``  -> ``[3.5, 0.5, 0.5]``    -> (3.5, 3.5)
    * ``"3.5...5.5"`` -> ``[3.5, 0.5, 0.5]``    -> (3.5, 3.5)
    * ``"1..10"``     -> ``[1]`` (die Dots blocken die naechste Match-Position)
                                                 -> (1.0, 1.0)
    * ``"1e5..2e5"``  -> ``[1e5, 0.2e5]``       -> (1e5, 1e5)  Scientific-Kollaps
    * ``"(3..5)"``    -> nach Bracket-Strip-Fallback auf Original identisch
                                                 -> (3.0, 3.0)

    ``..``/``...`` als Range-Trenner ist in mehreren Kontexten verbreitet:
    Fortran-/Pascal-/Ruby-Sprach-Ranges (``3..5``), publizierte wissenschaft-
    liche Tabellen, in denen der Bindestrich als Sub-/Vorzeichen reserviert
    ist und ``..`` als visuell klareres Trenner-Zeichen dient, sowie Textdatei-
    Sammlungen aus RTF/TXT-Quellen ohne Autoformat-Konvertierung zu
    ``–``/``…``, in denen der Sammler die ASCII-Form verwendet. Bei der
    Migration aus solchen Quellen entstand silenter Datenverlust auf der
    oberen Range-Grenze jeder Numeric-Achse.

    Der Fix normalisiert per :data:`_DOTTED_RANGE_SEPARATOR`-Regex jede
    ``\\d..\\d``/``\\d...\\d``-Sequenz auf ``\\d-\\d`` (ohne Whitespace,
    damit die Sign-Lookbehind-Klausel ``(?<![\\d.%‰])-`` in :data:`_NUM_RE`
    den Bindestrich als Separator statt als Vorzeichen erkennt). Nach
    :func:`_normalize_ascii_mixed_fractions` und vor den Uncertainty-Zweigen
    einsortiert (kollisionsfrei: die Uncertainty-Patterns nutzen ``±``/``(M)``,
    nicht Dots). Guards ``(?<=\\d)`` links und ``(?=\\d)`` rechts verhindern
    False-Positives an trailing/leading Dot-Clustern (``3..``, ``..5``,
    ``Cluster ... aber``) und an einzelnen Dots in Nummerierungen (``1.2.3.4``).
    """
    # Ruby-/Fortran-Style Doppel-Dot-Range: die klassische Form.
    assert csv_loaders.parse_range("3.5..5.5") == (3.5, 5.5)
    assert csv_loaders.parse_range("1..10") == (1.0, 10.0)
    assert csv_loaders.parse_range("3..5") == (3.0, 5.0)
    # Publikations-Style Dreifach-Dot als Range-Trenner.
    assert csv_loaders.parse_range("3.5...5.5") == (3.5, 5.5)
    assert csv_loaders.parse_range("0.5...1.5") == (0.5, 1.5)
    # Leading-Dot-Dezimal auf einer Seite - der Fraktions-Wert wird bewahrt.
    assert csv_loaders.parse_range(".5..7.5") == (0.5, 7.5)
    assert csv_loaders.parse_range("3.5...5") == (3.5, 5.0)
    # Scientific-Notation auf beiden Seiten - Exponent bleibt intakt.
    assert csv_loaders.parse_range("1e5..2e5") == (100000.0, 200000.0)
    assert csv_loaders.parse_range("1.5e-3..2.5e-3") == pytest.approx((0.0015, 0.0025))
    # DE-Komma-Dezimal auf beiden Seiten (Publikation aus dem DACH-Raum).
    assert csv_loaders.parse_range("3,5..5,5") == (3.5, 5.5)
    # Negatives Vorzeichen auf der linken Range-Grenze - der Bindestrich in
    # der Substitution kollidiert nicht mit einem echten Sign davor.
    assert csv_loaders.parse_range("-3.5..5.5") == (-3.5, 5.5)
    # Trailing-Einheit nach der Range - die Einheit greift auf beide Grenzen.
    assert csv_loaders.parse_range("3.5..5.5 mm") == (3.5, 5.5)
    assert csv_loaders.parse_range("0.5..1.5 mm") == (0.5, 1.5)
    # Freitext-Praefix (``ca.``/``~``) vor der Range - der Praefix wird von
    # :data:`_APPROX_VALUE_PREFIX` gestrippt und die Range-Extraktion greift.
    assert csv_loaders.parse_range("ca. 3.5..5.5") == (3.5, 5.5)
    assert csv_loaders.parse_range("~3.5..5.5") == (3.5, 5.5)
    # Range in umschliessenden Klammern - nach der Dot-Normalisierung wird
    # ``(3.5-5.5)`` durch den Bracket-Strip-Fallback auf sich selbst
    # zurueckgefuehrt und die Standard-Range-Zahl-Extraktion greift.
    assert csv_loaders.parse_range("(3..5)") == (3.0, 5.0)
    assert csv_loaders.parse_range("(3.5..5.5)") == (3.5, 5.5)
    assert csv_loaders.parse_range("[3.5..5.5]") == (3.5, 5.5)
    assert csv_loaders.parse_range("{3.5..5.5}") == (3.5, 5.5)
    # Invertierte Range mit Dot-Trenner: bleibt bei der bestehenden
    # inverted-Range-Kollaps-Semantik (``7.5..3.5`` -> (7.5, 7.5)).
    assert csv_loaders.parse_range("7.5..3.5") == (7.5, 7.5)
    # Chained Range ``3..5..7`` (mehrere Dot-Cluster) wird auf ``3-5-7``
    # normalisiert; die generische Zahl-Extraktion liefert lo=3, hi=7.
    assert csv_loaders.parse_range("3..5..7") == (3.0, 7.0)
    # Regress-Anker: einzelner Dot zwischen Zahlen ist keine Range-Notation,
    # sondern ein Dezimaltrenner - Version-Nummern-artige Sequenzen bleiben
    # unangetastet und fallen wie vor dem Fix auf den existierenden
    # Kollaps-Pfad (``1.2.3.4`` -> nums ``[1.2, .3, .4]`` -> (1.2, 1.2)).
    assert csv_loaders.parse_range("1.2.3.4") == (1.2, 1.2)
    # Regress-Anker: reine trailing/leading Dot-Cluster ohne rechten/linken
    # Digit-Partner bleiben unangetastet (Guards blocken das Match).
    assert csv_loaders.parse_range("3..") == (3.0, 3.0)
    assert csv_loaders.parse_range("..5") == (0.5, 0.5)
    # Regress-Anker: Standard-Range mit Bindestrich/En-Dash/Em-Dash bleibt
    # unveraendert (kein Dot involviert).
    assert csv_loaders.parse_range("3.5-5.5") == (3.5, 5.5)
    assert csv_loaders.parse_range("3.5–5.5") == (3.5, 5.5)
    assert csv_loaders.parse_range("3.5—5.5") == (3.5, 5.5)
    # Regress-Anker: Unicode-Ellipsis ``…`` mit umgebendem Whitespace wird
    # bereits vom generischen Zahl-Extraktor korrekt behandelt - der Fix
    # laesst sie unangetastet.
    assert csv_loaders.parse_range("3.5 … 5.5") == (3.5, 5.5)
    # Regress-Anker: repetierte-Einheit-Range (``3mm-5mm``) bleibt vom
    # bestehenden :func:`_strip_repeated_unit`-Zweig behandelt, unabhaengig
    # vom Dot-Range-Fix.
    assert csv_loaders.parse_range("3mm-5mm") == (3.0, 5.0)
    # Regress-Anker: IUCr-Kompakt-Uncertainty (nutzt Klammer, keine Dots).
    assert csv_loaders.parse_range("5.5(3)") == pytest.approx((5.2, 5.8))
    # Regress-Anker: ±-Uncertainty (nutzt ±, keine Dots).
    assert csv_loaders.parse_range("5.5 ± 0.3") == pytest.approx((5.2, 5.8))
    # Regress-Anker: leere/None-Eingabe.
    assert csv_loaders.parse_range("") == (None, None)
    assert csv_loaders.parse_range(None) == (None, None)


def test_load_v1():
    data = csv_loaders.load_v1(CSV_DIR / "Stonebock__stoneboock_daten_objekte_1-42.csv")
    assert "OBJ_0001" in data
    o1 = data["OBJ_0001"]
    assert "Jaspis" in o1["Mineral_Primaer"]
    assert "Rötlich" in o1["notizen"]


def test_load_v2():
    data = csv_loaders.load_v2(CSV_DIR / "Stonebock__stoneboock_daten_v2_objekte_1-42.csv")
    o1 = data["OBJ_0001"]
    assert o1["Mohs_Haerte_min"] == 6.5
    assert o1["Mohs_Haerte_max"] == 7.0
    assert o1["Confidence_Prozent"] == 80
    assert o1["Varietaet"] == "Jaspis"


def test_load_standard_roundtrip(tmp_path):
    """export_csv → load_standard ergibt identische Werte für nichtleere Zellen."""
    from stonebook.db.database import connect
    from stonebook.export.csv_export import export_csv
    from stonebook.migration.csv_loaders import load_standard
    from stonebook.migration.migrate import migrate

    db_file = tmp_path / "stonebook.sqlite3"
    migrate(REPO, db_file, log=lambda *_: None)
    csv_path = tmp_path / "export.csv"
    export_csv(connect(db_file), csv_path)
    data = load_standard(csv_path)
    assert "OBJ_0043" in data
    o43 = data["OBJ_0043"]
    assert "Quarz" in o43["Mineral_Primaer"]
    assert o43["Gewicht_g"] == 41.0
    assert o43["Mohs_Haerte_min"] == 7.0
    assert o43.get("status") == "aktiv"


def test_load_standard_ignoriert_ungueltige_datumswerte(tmp_path):
    csv_path = tmp_path / "x.csv"
    csv_path.write_text(
        "ID,Funddatum,Mineral_Primaer\nOBJ_0001,32.13.2024,Quarz\n",
        encoding="utf-8",
    )
    from stonebook.migration.csv_loaders import load_standard
    data = load_standard(csv_path)
    o1 = data["OBJ_0001"]
    assert o1["Mineral_Primaer"] == "Quarz"
    assert "Funddatum" not in o1  # ungueltiges Datum wird verworfen


def test_load_standard_semicolon_delimiter(tmp_path):
    """Excel-DE-Export mit ; als Trennzeichen wird automatisch erkannt."""
    csv_path = tmp_path / "semi.csv"
    csv_path.write_text(
        "ID;Mineral_Primaer;Gewicht_g\nOBJ_0001;Quarz;12.5\n",
        encoding="utf-8",
    )
    from stonebook.migration.csv_loaders import load_standard
    data = load_standard(csv_path)
    assert data["OBJ_0001"]["Mineral_Primaer"] == "Quarz"
    assert data["OBJ_0001"]["Gewicht_g"] == 12.5


def test_load_standard_tab_delimiter(tmp_path):
    csv_path = tmp_path / "tab.tsv"
    csv_path.write_text(
        "ID\tMineral_Primaer\tGewicht_g\nOBJ_0001\tCalcit\t7\n",
        encoding="utf-8",
    )
    from stonebook.migration.csv_loaders import load_standard
    data = load_standard(csv_path)
    assert data["OBJ_0001"]["Mineral_Primaer"] == "Calcit"
    assert data["OBJ_0001"]["Gewicht_g"] == 7.0


def test_load_standard_header_whitespace(tmp_path):
    """Spaltennamen mit fuehrenden/abschliessenden Leerzeichen werden getrimmt."""
    csv_path = tmp_path / "ws.csv"
    csv_path.write_text(
        " ID , Mineral_Primaer ,Gewicht_g \nOBJ_0001,Quarz,5\n",
        encoding="utf-8",
    )
    from stonebook.migration.csv_loaders import load_standard
    data = load_standard(csv_path)
    assert data["OBJ_0001"]["Mineral_Primaer"] == "Quarz"
    assert data["OBJ_0001"]["Gewicht_g"] == 5.0


def test_load_standard_multiline_quoted_zelle(tmp_path):
    """Eingebettete Newlines in quoted Feldern (lange notizen) bleiben erhalten."""
    csv_path = tmp_path / "ml.csv"
    # notizen mit eingebettetem \n in Anfuehrungszeichen (z.B. Excel-Export
    # langer Freitext-Notizen mit Zeilenumbruechen)
    csv_path.write_text(
        'ID,Mineral_Primaer,notizen\n'
        'OBJ_0001,Quarz,"Erste Zeile\nZweite Zeile\nDritte Zeile"\n'
        'OBJ_0002,Calcit,"Einzelnotiz"\n',
        encoding="utf-8",
    )
    from stonebook.migration.csv_loaders import load_standard
    data = load_standard(csv_path)
    assert set(data.keys()) == {"OBJ_0001", "OBJ_0002"}
    assert data["OBJ_0001"]["Mineral_Primaer"] == "Quarz"
    # Newlines im Freitext bleiben erhalten (sonst waere die Notiz zerfallen)
    assert data["OBJ_0001"]["notizen"] == "Erste Zeile\nZweite Zeile\nDritte Zeile"
    assert data["OBJ_0002"]["notizen"] == "Einzelnotiz"


def test_load_standard_multiline_mit_semicolon_delimiter(tmp_path):
    """Multiline-Zellen bleiben auch bei ;-Delimiter (Excel-DE) erhalten."""
    csv_path = tmp_path / "ml_de.csv"
    csv_path.write_text(
        'ID;Mineral_Primaer;notizen\n'
        'OBJ_0001;Quarz;"Zeile A\nZeile B"\n',
        encoding="utf-8",
    )
    from stonebook.migration.csv_loaders import load_standard
    data = load_standard(csv_path)
    assert data["OBJ_0001"]["notizen"] == "Zeile A\nZeile B"


def test_detect_delimiter_ignoriert_quoted_kommas_in_header(tmp_path):
    """Semikolon-CSV mit komma-haltigen quoted Feldnamen wird nicht als Komma-CSV
    fehlgelesen.

    Excel-DE-Export: Semikolon-Delimiter (DE-Locale), aber Feldnamen wie
    ``"Wert, geschaetzt"`` oder ``"Feld mit, Komma, mehr, Kommas"`` enthalten
    Kommas. Die naive Zeichen-Count-Heuristik zaehlt jede Komma-Vorkommnis,
    sodass ein Header mit >=3 quoted Kommas den echten Semikolon-Trenner
    ueberstimmen wuerde - der gesamte Datensatz zerfaellt dann zu einer
    einzigen Zelle pro Zeile mit einem synthetischen Header aus Fragmenten
    des ersten Feldnamens. Der Quoted-Span-Skip stellt sicher, dass nur
    Zeichen ausserhalb ``"..."`` als Delimiter-Kandidaten zaehlen.
    """
    csv_path = tmp_path / "semi_quoted_kommas.csv"
    csv_path.write_text(
        '"ID";"Wert, geschaetzt";"Feld mit, Komma, mehr, Kommas";"Ort"\n'
        '"OBJ_0001";"12,50";"beispielwert";"Zermatt"\n',
        encoding="utf-8",
    )
    from stonebook.migration.csv_loaders import _read_csv_robust
    rows = _read_csv_robust(csv_path)
    assert len(rows) == 1
    row = rows[0]
    assert row["ID"] == "OBJ_0001"
    assert row["Wert, geschaetzt"] == "12,50"
    assert row["Feld mit, Komma, mehr, Kommas"] == "beispielwert"
    assert row["Ort"] == "Zermatt"


def test_detect_delimiter_quoted_spans_helper():
    """Direkter Ankertest fuer die Quoted-Span-Zaehl-Heuristik.

    Deckt die semantisch relevanten Faelle ab: naive Overcount bei quoted
    Kommas in Semikolon-CSV, RFC-4180-Escape-Anfuehrungszeichen (``""``
    bleibt Innen-Zeichen), unbalancierte Anfuehrungszeichen (Fallback auf
    Roh-Zaehlung, damit ein einzelnes ``"`` in einem exotischen Header nicht
    die halbe Zeile ausblendet), und Regress-Anker auf die ungequoteten
    Basis-Formen fuer Komma/Semikolon/Tab/Pipe.
    """
    from stonebook.migration.csv_loaders import _detect_delimiter

    # Quoted Kommas gegen echtes Semikolon: Semikolon gewinnt.
    assert _detect_delimiter(
        '"ID";"Feld mit, Komma, mehr, Kommas";"Ort"') == ';'
    assert _detect_delimiter('"a";"b, c, d, e, f";"g"') == ';'
    # Quoted Semikolons gegen echtes Komma: Komma gewinnt.
    assert _detect_delimiter('"a","b","c;d;e;f;g"') == ','
    # RFC-4180-Escape: "" ist ein literales " innerhalb des Feldes -
    # zaehlt nicht als Feld-Ende und blendet die inneren Zeichen aus.
    assert _detect_delimiter('"a""b";c;d') == ';'
    # Nur eine Zahl-Vorkommen: fallback auf Komma.
    assert _detect_delimiter('') == ','
    assert _detect_delimiter('ID') == ','
    # Unbalancierte Anfuehrungszeichen: konservativer Fallback auf Roh-
    # Zaehlung, damit die Delimiter-Entscheidung nicht vom Restsatz abhaengt.
    # In diesem Fall zaehlt die Roh-Zaehlung 2 Kommas und 1 Semikolon.
    assert _detect_delimiter('a,b,"c;d') == ','
    # Regress-Anker auf die Basis-Formen.
    assert _detect_delimiter('ID,Name,Fundort') == ','
    assert _detect_delimiter('ID;Name;Fundort') == ';'
    assert _detect_delimiter('ID\tName\tFundort') == '\t'
    assert _detect_delimiter('ID|Name|Fundort') == '|'
    # Gemischt: hoechster Count gewinnt, Ties gehen an Komma per Iterations-
    # Reihenfolge in ``_COMMON_DELIMS``.
    assert _detect_delimiter('a;"b, c";"d, e, f";g') == ';'


def test_load_standard_skip_blank_rows(tmp_path):
    csv_path = tmp_path / "blank.csv"
    csv_path.write_text(
        "ID,Mineral_Primaer\n"
        "OBJ_0001,Quarz\n"
        ",\n"
        "\n"
        "OBJ_0002,Calcit\n",
        encoding="utf-8",
    )
    from stonebook.migration.csv_loaders import load_standard
    data = load_standard(csv_path)
    assert set(data.keys()) == {"OBJ_0001", "OBJ_0002"}


def test_load_standard_empty_file(tmp_path):
    csv_path = tmp_path / "empty.csv"
    csv_path.write_text("", encoding="utf-8")
    from stonebook.migration.csv_loaders import load_standard
    assert load_standard(csv_path) == {}


def test_load_standard_bom_und_crlf(tmp_path):
    """BOM + Windows-Zeilenenden werden korrekt verarbeitet."""
    csv_path = tmp_path / "bom.csv"
    csv_path.write_bytes(
        b"\xef\xbb\xbfID,Mineral_Primaer\r\nOBJ_0001,Quarz\r\n"
    )
    from stonebook.migration.csv_loaders import load_standard
    data = load_standard(csv_path)
    assert data["OBJ_0001"]["Mineral_Primaer"] == "Quarz"


def test_load_standard_cp1252_fallback(tmp_path):
    """Excel-Export auf alten Windows-Systemen ist oft cp1252; muss lesbar bleiben."""
    csv_path = tmp_path / "win.csv"
    # Umlaute in Daten + Header werden als cp1252 geschrieben (kein BOM, kein UTF-8)
    csv_path.write_bytes(
        "ID,Mineral_Primaer,Fundort\nOBJ_0001,Quarz,Zürich\n".encode("cp1252")
    )
    from stonebook.migration.csv_loaders import load_standard
    data = load_standard(csv_path)
    assert data["OBJ_0001"]["Mineral_Primaer"] == "Quarz"
    assert data["OBJ_0001"]["Fundort"] == "Zürich"


def test_load_standard_latin1_fallback(tmp_path):
    csv_path = tmp_path / "latin.csv"
    csv_path.write_bytes(
        "ID,Mineral_Primaer\nOBJ_0001,Calcít\n".encode("latin-1")
    )
    from stonebook.migration.csv_loaders import load_standard
    data = load_standard(csv_path)
    assert data["OBJ_0001"]["Mineral_Primaer"] == "Calcít"


def test_load_standard_utf16_le_bom(tmp_path):
    """Excel 'Unicode Text'-Export ist UTF-16-LE mit BOM und Tab-Separator.

    Ohne BOM-Erkennung fiele die Datei aktuell durch utf-8-sig/utf-8 (beide
    scheitern an ``\\xff`` als ungueltigem Startbyte) auf cp1252 zurueck und
    wuerde als Doppelbyte-Muell dekodiert (jeder ASCII-Buchstabe als
    ``X\\x00``, ID-Header zerfaellt). Mit BOM-Pruefung wird der korrekte
    UTF-16-Decoder benutzt; Umlaute bleiben intakt.
    """
    csv_path = tmp_path / "u16le.csv"
    csv_path.write_bytes(
        ("ID\tMineral_Primaer\tFundort\n"
         "OBJ_0001\tQuarz\tZürich\n"
         "OBJ_0002\tCalcit\tDavos\n").encode("utf-16")  # encode() addiert BOM \xff\xfe
    )
    from stonebook.migration.csv_loaders import load_standard
    data = load_standard(csv_path)
    assert set(data.keys()) == {"OBJ_0001", "OBJ_0002"}
    assert data["OBJ_0001"]["Mineral_Primaer"] == "Quarz"
    assert data["OBJ_0001"]["Fundort"] == "Zürich"
    assert data["OBJ_0002"]["Mineral_Primaer"] == "Calcit"


def test_load_standard_utf16_be_bom(tmp_path):
    """UTF-16-BE mit BOM (selten, aber spec-konform) wird ebenfalls erkannt."""
    csv_path = tmp_path / "u16be.csv"
    # encode('utf-16-be') addiert KEIN BOM; BOM \xfe\xff manuell voranstellen,
    # damit die BOM-Pruefung in _read_text_any_encoding greift
    csv_path.write_bytes(
        b"\xfe\xff" + (
            "ID,Mineral_Primaer\nOBJ_0001,Quarz\n"
        ).encode("utf-16-be")
    )
    from stonebook.migration.csv_loaders import load_standard
    data = load_standard(csv_path)
    assert data["OBJ_0001"]["Mineral_Primaer"] == "Quarz"


def test_load_standard_utf16_ohne_bom_faellt_auf_cp1252_zurueck(tmp_path):
    """Ohne BOM keine stille UTF-16-Annahme: BOM-loses UTF-16 ist von ASCII-
    Daten in cp1252 nicht eindeutig unterscheidbar; bestehende Fallback-Logik
    bleibt unveraendert. Eine reine ASCII-CSV ohne BOM funktioniert weiter.
    """
    csv_path = tmp_path / "ascii.csv"
    csv_path.write_bytes(b"ID,Mineral_Primaer\nOBJ_0001,Quarz\n")
    from stonebook.migration.csv_loaders import load_standard
    data = load_standard(csv_path)
    assert data["OBJ_0001"]["Mineral_Primaer"] == "Quarz"


def test_load_standard_quoted_multiline(tmp_path):
    """Zellen mit eingebetteten Zeilenumbruechen (quoted) werden korrekt geparst."""
    csv_path = tmp_path / "multi.csv"
    csv_path.write_text(
        'ID,Mineral_Primaer,notizen\n'
        'OBJ_0001,Quarz,"Zeile 1\nZeile 2"\n'
        'OBJ_0002,Calcit,einzeilig\n',
        encoding="utf-8",
    )
    from stonebook.migration.csv_loaders import load_standard
    data = load_standard(csv_path)
    assert set(data.keys()) == {"OBJ_0001", "OBJ_0002"}
    assert "Zeile 1" in data["OBJ_0001"]["notizen"]
    assert "Zeile 2" in data["OBJ_0001"]["notizen"]
    assert data["OBJ_0002"]["notizen"] == "einzeilig"


def test_load_standard_obj_id_alias(tmp_path):
    """JSON-/DB-Konvention 'obj_id' wird als ID-Spalte akzeptiert."""
    csv_path = tmp_path / "json_like.csv"
    csv_path.write_text(
        "obj_id,Mineral_Primaer,Gewicht_g\nOBJ_0001,Quarz,12.5\n",
        encoding="utf-8",
    )
    from stonebook.migration.csv_loaders import load_standard
    data = load_standard(csv_path)
    assert data["OBJ_0001"]["Mineral_Primaer"] == "Quarz"
    assert data["OBJ_0001"]["Gewicht_g"] == 12.5


def test_find_duplicate_ids_standard(tmp_path):
    """Doppelte IDs in derselben CSV werden erkannt (spiegelt load_standard-Dict-Overwrite).

    load_standard(dict[str, dict]) ueberschreibt fruehere Zeilen kommentarlos,
    wenn dieselbe ID mehrfach als Zeile vorkommt (typischer Datenverlust-Fall
    bei nutzer-editierten CSVs). find_duplicate_ids liefert die betroffenen
    IDs zurueck, ohne die Loesch-Semantik selbst zu aendern.
    """
    from stonebook.migration.csv_loaders import find_duplicate_ids, load_standard
    csv_path = tmp_path / "duplikate.csv"
    csv_path.write_text(
        "ID,Name\n"
        "OBJ_0001,Erste Zeile\n"
        "OBJ_0002,Zwischen\n"
        "OBJ_0001,Zweite Zeile\n"
        "OBJ_0003,Andere\n"
        "OBJ_0001,Dritte Zeile\n",
        encoding="utf-8",
    )
    # find_duplicate_ids meldet OBJ_0001 genau einmal, in der Reihenfolge des
    # zweiten Vorkommens (deterministisch fuer Reporter/Log-Ausgabe).
    assert find_duplicate_ids(csv_path) == ["OBJ_0001"]
    # load_standard behaelt die letzte Zeile (dict-Overwrite-Semantik).
    data = load_standard(csv_path)
    assert data["OBJ_0001"]["Name"] == "Dritte Zeile"
    assert data["OBJ_0002"]["Name"] == "Zwischen"
    assert data["OBJ_0003"]["Name"] == "Andere"


def test_find_duplicate_ids_normalisiert_alternativ_formen(tmp_path):
    """obj_1 und OBJ_0001 werden als dieselbe ID erkannt (normalize_id-Semantik).

    Spiegelt load_standard, das ueber normalize_id gleichermassen kompaktes
    ``obj_1`` und ``OBJ_0001`` auf denselben Schluessel abbildet - ohne
    Normalisierung wuerde ein user-editierter Mix beider Formen fuer dasselbe
    Stueck nicht als Duplikat auffallen.
    """
    from stonebook.migration.csv_loaders import find_duplicate_ids
    csv_path = tmp_path / "mixid.csv"
    csv_path.write_text(
        "ID,Name\nOBJ_0001,Erste\nobj_1,Zweite\n",
        encoding="utf-8",
    )
    assert find_duplicate_ids(csv_path) == ["OBJ_0001"]


def test_find_duplicate_ids_leer_und_ohne_duplikate(tmp_path):
    """Leere CSV und CSV ohne Duplikate liefern eine leere Liste."""
    from stonebook.migration.csv_loaders import find_duplicate_ids
    leer = tmp_path / "leer.csv"
    leer.write_text("ID,Name\n", encoding="utf-8")
    assert find_duplicate_ids(leer) == []
    ohne = tmp_path / "ohne.csv"
    ohne.write_text(
        "ID,Name\nOBJ_0001,A\nOBJ_0002,B\nOBJ_0003,C\n",
        encoding="utf-8",
    )
    assert find_duplicate_ids(ohne) == []


def test_find_duplicate_ids_raises_bei_fehlender_id_spalte(tmp_path):
    """CSV mit Zeilen aber ohne ID/obj_id-Header wirft ValueError (spiegelt load_standard).

    Ohne diesen Fehler wuerde ein falsch adressierter Dateipfad (z.B. v1-CSV
    mit Header Name,Mineralart) hier stille als "keine Duplikate" durchgehen,
    obwohl load_standard denselben Input mit ValueError abbricht - beide
    Funktionen sollen zur gleichen Format-Regel stehen.
    """
    import pytest
    from stonebook.migration.csv_loaders import find_duplicate_ids
    csv_path = tmp_path / "fremd.csv"
    csv_path.write_text("Name,Mineralart\nFoo,Quarz\n", encoding="utf-8")
    with pytest.raises(ValueError, match="ID-Spalte"):
        find_duplicate_ids(csv_path)


def test_find_duplicate_ids_leere_datei_ohne_id_spalte_ist_ok(tmp_path):
    """Leere CSV (nur Header) ohne ID-Spalte loest keinen Fehler aus (spiegelt load_standard)."""
    from stonebook.migration.csv_loaders import find_duplicate_ids
    csv_path = tmp_path / "leerohne.csv"
    csv_path.write_text("Name,Mineralart\n", encoding="utf-8")
    assert find_duplicate_ids(csv_path) == []


def test_find_rows_without_id_standard(tmp_path):
    """Zeilen mit leerer oder unlesbarer ID-Spalte werden gemeldet.

    load_standard verwirft Zeilen ohne normalisierbare ID kommentarlos - ein
    user-editierter Tippfehler (leer, ``??``, ``TODO``) laesst die Zeile silent
    verschwinden, obwohl uebrige Spalten voll gepflegt sein koennen. Der Report
    liefert 1-basierte Zeilennummern ueber die Datenzeilen (Header zaehlt nicht),
    komplett leere Zeilen zaehlen nicht (die filtert der Reader).
    """
    from stonebook.migration.csv_loaders import find_rows_without_id, load_standard
    csv_path = tmp_path / "ohne_id.csv"
    csv_path.write_text(
        "ID,Name\n"
        "OBJ_0001,Erste\n"
        ",Zeile ohne ID\n"
        "OBJ_0002,Zweite\n"
        "??,Kaputte ID\n"
        "OBJ_0003,Dritte\n",
        encoding="utf-8",
    )
    assert find_rows_without_id(csv_path) == [2, 4]
    # load_standard behaelt nur die drei gueltigen IDs (dict-Semantik).
    data = load_standard(csv_path)
    assert set(data.keys()) == {"OBJ_0001", "OBJ_0002", "OBJ_0003"}


def test_find_rows_without_id_leer_und_alles_ok(tmp_path):
    """Leere CSV und CSV ohne unlesbare IDs liefern eine leere Liste."""
    from stonebook.migration.csv_loaders import find_rows_without_id
    leer = tmp_path / "leer.csv"
    leer.write_text("ID,Name\n", encoding="utf-8")
    assert find_rows_without_id(leer) == []
    ok = tmp_path / "ok.csv"
    ok.write_text(
        "ID,Name\nOBJ_0001,A\nOBJ_0002,B\n",
        encoding="utf-8",
    )
    assert find_rows_without_id(ok) == []


def test_find_rows_without_id_raises_bei_fehlender_id_spalte(tmp_path):
    """CSV mit Zeilen aber ohne ID/obj_id-Header wirft ValueError (spiegelt load_standard)."""
    import pytest
    from stonebook.migration.csv_loaders import find_rows_without_id
    csv_path = tmp_path / "fremd.csv"
    csv_path.write_text("Name,Mineralart\nFoo,Quarz\n", encoding="utf-8")
    with pytest.raises(ValueError, match="ID-Spalte"):
        find_rows_without_id(csv_path)


def test_find_rows_without_id_akzeptiert_obj_id_spalte(tmp_path):
    """JSON-/DB-Format nutzt ``obj_id`` statt ``ID`` - beide werden erkannt."""
    from stonebook.migration.csv_loaders import find_rows_without_id
    csv_path = tmp_path / "objid.csv"
    csv_path.write_text(
        "obj_id,Name\nOBJ_0001,Erste\n,Zeile ohne ID\n",
        encoding="utf-8",
    )
    assert find_rows_without_id(csv_path) == [2]


def test_find_rows_with_invalid_funddatum_standard(tmp_path):
    """Zeilen mit einem nicht parsbaren Funddatum werden gemeldet (Feld-Level-Silent-Drop).

    _convert_standard uebernimmt Funddatum nur, wenn parse_iso_date den Wert
    erfolgreich mappen kann - Tippfehler (32.13.2024, Monat 13) oder unstruk-
    turierter Freitext ("Sommer 84" ohne Vollzahl-Jahr) werden kommentarlos
    verworfen, die Zeile bleibt aber sonst intakt. Der Report liefert
    (Zeilennummer, Roh-Wert)-Paare, damit der User den konkreten Tippfehler
    ohne Zusatz-Recherche findet.
    """
    from stonebook.migration.csv_loaders import (
        find_rows_with_invalid_funddatum,
        load_standard,
    )
    csv_path = tmp_path / "funddatum.csv"
    csv_path.write_text(
        "ID,Funddatum,Mineral_Primaer\n"
        "OBJ_0001,2024-06-13,Quarz\n"
        "OBJ_0002,32.13.2024,Calcit\n"
        "OBJ_0003,1985,Amethyst\n"
        "OBJ_0004,Sommer 84,Turmalin\n"
        "OBJ_0005,,Ohne\n",
        encoding="utf-8",
    )
    assert find_rows_with_invalid_funddatum(csv_path) == [
        (2, "32.13.2024"),
        (4, "Sommer 84"),
    ]
    # load_standard behaelt die Zeilen, aber ohne das kaputte Funddatum-Feld.
    data = load_standard(csv_path)
    assert data["OBJ_0002"]["Mineral_Primaer"] == "Calcit"
    assert "Funddatum" not in data["OBJ_0002"]
    assert "Funddatum" not in data["OBJ_0004"]
    # Gueltige Datums-Werte bleiben unangetastet.
    assert data["OBJ_0001"]["Funddatum"] == "2024-06-13"
    assert data["OBJ_0003"]["Funddatum"] == "1985-01-01"


def test_find_rows_with_invalid_funddatum_ignoriert_leer_und_no_data_marker(tmp_path):
    """Leere Werte und "keine Angabe"-Marker (k.a./n/a/unbekannt/? etc.) zaehlen
    NICHT als invalid.

    parse_iso_date behandelt die Marker semantisch als "User sagt: kein Datum"
    (siehe DATE_NO_DATA_MARKERS). Da ist nichts verloren gegangen; die Zeile
    darf nicht als silent-data-loss-Fund gemeldet werden, sonst wuerde der
    Report bei ausdruecklich "no data"-Eingaben Rauschen erzeugen.
    """
    from stonebook.migration.csv_loaders import find_rows_with_invalid_funddatum
    csv_path = tmp_path / "marker.csv"
    csv_path.write_text(
        "ID,Funddatum,Mineral_Primaer\n"
        "OBJ_0001,,Leer\n"
        "OBJ_0002,   ,Whitespace\n"
        "OBJ_0003,k.a.,Marker DE\n"
        "OBJ_0004,n/a,Marker EN\n"
        "OBJ_0005,unbekannt,Wort-Marker\n"
        "OBJ_0006,?,Fragezeichen\n"
        "OBJ_0007,-,Bindestrich\n"
        "OBJ_0008,K.A.,Marker mit Grossschreibung\n",
        encoding="utf-8",
    )
    assert find_rows_with_invalid_funddatum(csv_path) == []


def test_find_rows_with_invalid_funddatum_ignoriert_erweiterte_no_data_marker(tmp_path):
    """Erweiterte "keine Angabe"-Marker (n.a., En-Dash, unknown, keine angabe, ...)
    zaehlen NICHT als invalid.

    Deckt die erweiterte DATE_NO_DATA_MARKERS-Menge (n.a./n. a./En-Dash/??/???/
    unknown/no data/no date/none/keine angabe/keine daten/kein datum) auf der
    Consumer-Seite ab: der silent-data-loss-Report darf keine dieser Formen als
    "invalid" melden, sonst waere fuer den User die explizite Marker-Absicht als
    Fehler ausgewiesen. Bereits abgedeckte Marker (k.a./n/a/?/-/—/unbekannt)
    sind im Vorgaenger-Test ``_ignoriert_leer_und_no_data_marker`` verankert.
    """
    from stonebook.migration.csv_loaders import find_rows_with_invalid_funddatum
    csv_path = tmp_path / "erweiterte_marker.csv"
    csv_path.write_text(
        "ID,Funddatum,Mineral_Primaer\n"
        "OBJ_0001,n.a.,Punkt-Form\n"
        "OBJ_0002,n. a.,Punkt-Form mit Space\n"
        "OBJ_0003,N.A.,Grossschreibung\n"
        "OBJ_0004,–,En-Dash U+2013\n"
        "OBJ_0005,??,Doppel-Fragezeichen\n"
        "OBJ_0006,???,Dreifach-Fragezeichen\n"
        "OBJ_0007,unknown,EN-Aequivalent zu unbekannt\n"
        "OBJ_0008,Unknown,EN mit Grossschreibung\n"
        "OBJ_0009,no data,EN Langform\n"
        "OBJ_0010,No Data,EN Titel-Case\n"
        "OBJ_0011,no date,EN Datums-spezifische Form\n"
        "OBJ_0012,none,EN Null-Marker\n"
        "OBJ_0013,None,EN Titel-Case\n"
        "OBJ_0014,keine angabe,DE Langform zu k.a.\n"
        "OBJ_0015,Keine Angabe,DE Titel-Case\n"
        "OBJ_0016,keine daten,DE Alt-Form\n"
        "OBJ_0017,kein datum,DE Datums-spezifische Form\n",
        encoding="utf-8",
    )
    assert find_rows_with_invalid_funddatum(csv_path) == []


def test_find_rows_with_invalid_funddatum_ohne_spalte_ist_leer(tmp_path):
    """Fehlt die Funddatum-Spalte komplett, wird [] zurueckgegeben.

    Kein Datenverlust moeglich, wenn das Feld gar nicht Teil der CSV ist -
    der Report darf nicht faelschlich "0 Zeilen" statt "gar nicht anwendbar"
    signalisieren, sondern liefert schlicht leere Liste.
    """
    from stonebook.migration.csv_loaders import find_rows_with_invalid_funddatum
    csv_path = tmp_path / "kein_funddatum.csv"
    csv_path.write_text(
        "ID,Mineral_Primaer\nOBJ_0001,Quarz\nOBJ_0002,Calcit\n",
        encoding="utf-8",
    )
    assert find_rows_with_invalid_funddatum(csv_path) == []


def test_find_rows_with_invalid_funddatum_akzeptiert_obj_id_spalte(tmp_path):
    """JSON-/DB-Format nutzt ``obj_id`` statt ``ID`` - beide werden erkannt.

    Spiegelt find_rows_without_id/find_duplicate_ids: das ID-Spalten-Aliasing
    ist eine Symmetrie-Regel ueber alle Pre-Scanner, kein Extra-Feature dieses
    einen Checks.
    """
    from stonebook.migration.csv_loaders import find_rows_with_invalid_funddatum
    csv_path = tmp_path / "objid_datum.csv"
    csv_path.write_text(
        "obj_id,Funddatum\nOBJ_0001,2024-06-13\nOBJ_0002,kaputt\n",
        encoding="utf-8",
    )
    assert find_rows_with_invalid_funddatum(csv_path) == [(2, "kaputt")]


def test_find_rows_with_invalid_funddatum_raises_bei_fehlender_id_spalte(tmp_path):
    """CSV mit Zeilen aber ohne ID/obj_id-Header wirft ValueError.

    Spiegelt find_duplicate_ids/find_rows_without_id/load_standard: alle vier
    stehen zur gleichen Format-Regel und lehnen v1/v2-Historik-CSVs sichtbar
    ab, statt stille "0 Funde" zu melden.
    """
    import pytest
    from stonebook.migration.csv_loaders import find_rows_with_invalid_funddatum
    csv_path = tmp_path / "fremd.csv"
    csv_path.write_text(
        "Name,Mineralart,Fundort\nFoo,Quarz,Davos\n", encoding="utf-8")
    with pytest.raises(ValueError, match="ID-Spalte"):
        find_rows_with_invalid_funddatum(csv_path)


def test_find_rows_with_invalid_funddatum_leere_datei_ohne_id_spalte_ist_ok(tmp_path):
    """Leere CSV (nur Header) ohne ID-Spalte loest keinen Fehler aus.

    Spiegelt find_duplicate_ids/find_rows_without_id: ohne Zeilen kann es
    keinen Datenverlust geben, unabhaengig vom Header-Format.
    """
    from stonebook.migration.csv_loaders import find_rows_with_invalid_funddatum
    csv_path = tmp_path / "leerohne.csv"
    csv_path.write_text("Name,Mineralart\n", encoding="utf-8")
    assert find_rows_with_invalid_funddatum(csv_path) == []


def test_find_rows_with_invalid_numeric_field_standard(tmp_path):
    """Feld-Level-Silent-Drop-Pendant auf der numerischen Achse.

    ``_num("sehr schwer")`` liefert None, ``_convert_standard`` uebergibt
    ``(True, None)``, ``import_csv`` filtert das Feld via ``is_empty(None)``
    aus dem Update-Dict - der Roh-Text ist verloren, ohne dass der Report
    ihn sichtbar macht. Diese Funktion pre-scannt die CSV und liefert die
    (Zeile, Roh-Wert)-Paare zur sichtbaren Meldung, damit der User den
    konkreten Tippfehler direkt findet. Spiegelt den Standard-Pfad von
    find_rows_with_invalid_funddatum auf die Gewicht-Achse.
    """
    from stonebook.migration.csv_loaders import (
        find_rows_with_invalid_numeric_field,
        load_standard,
    )
    csv_path = tmp_path / "gewicht.csv"
    csv_path.write_text(
        "ID,Gewicht_g,Mineral_Primaer\n"
        "OBJ_0001,42.5,Quarz\n"
        "OBJ_0002,sehr schwer,Calcit\n"
        "OBJ_0003,150,Amethyst\n"
        "OBJ_0004,teuer,Turmalin\n"
        "OBJ_0005,,Ohne\n",
        encoding="utf-8",
    )
    assert find_rows_with_invalid_numeric_field(csv_path, "Gewicht_g") == [
        (2, "sehr schwer"),
        (4, "teuer"),
    ]
    # load_standard behaelt die Zeilen, aber ohne das kaputte Gewicht_g-Feld
    # (_num->None, is_empty(None)->True, das Feld verschwindet aus fields dict).
    data = load_standard(csv_path)
    assert data["OBJ_0002"]["Mineral_Primaer"] == "Calcit"
    assert data["OBJ_0002"].get("Gewicht_g") is None
    assert data["OBJ_0004"].get("Gewicht_g") is None
    # Gueltige numerische Werte bleiben unangetastet.
    assert data["OBJ_0001"]["Gewicht_g"] == 42.5
    assert data["OBJ_0003"]["Gewicht_g"] == 150.0


def test_find_rows_with_invalid_numeric_field_akzeptiert_einheiten(tmp_path):
    """Werte mit Einheit (``42 g``, ``ca. 500 CHF``) sind NICHT invalid.

    ``_num`` extrahiert das Zahl-Token, ``_convert_standard`` uebernimmt den
    Wert - die Einheiten-Annotation geht verloren, ist aber semantisch
    redundant (die Spalte kodiert die Einheit im Namen: ``Gewicht_g`` ist
    immer g). Erst wenn kein Zahl-Token gefunden wird (``sehr schwer``),
    ist der Wert-Anteil verloren und die Zeile wird gemeldet. Ohne diesen
    Test wuerde eine spaetere Regex-Verschaerfung von ``_num`` (z.B. Einheit
    zwingend abschneiden vor der Zahl-Extraktion) den Report mit Rauschen
    fuellen.
    """
    from stonebook.migration.csv_loaders import find_rows_with_invalid_numeric_field
    csv_path = tmp_path / "einheiten.csv"
    csv_path.write_text(
        "ID,Gewicht_g,Wert_CHF_roh\n"
        "OBJ_0001,42 g,ca. 500 CHF\n"
        "OBJ_0002,150 gram,750.00 CHF\n"
        "OBJ_0003,ca. 42.5,1'500.00\n",  # Schweizer Tausender
        encoding="utf-8",
    )
    assert find_rows_with_invalid_numeric_field(
        csv_path, "Gewicht_g") == []
    assert find_rows_with_invalid_numeric_field(
        csv_path, "Wert_CHF_roh") == []


def test_find_rows_with_invalid_numeric_field_ignoriert_leer_und_no_data_marker(tmp_path):
    """Leere Werte und "keine Angabe"-Marker zaehlen NICHT als invalid.

    Spiegelt die Marker-Ignoranz von find_rows_with_invalid_funddatum: die
    :data:`DATE_NO_DATA_MARKERS`-Menge ist single source of truth ueber alle
    Feld-Achsen (Datum, numerisch). Wenn der User explizit ``k.a.`` in eine
    Gewicht-Zelle schreibt, ist das "kein Wert verfuegbar" - da ist nichts
    verloren gegangen, und der Report darf keine Rauschmeldung erzeugen.
    """
    from stonebook.migration.csv_loaders import find_rows_with_invalid_numeric_field
    csv_path = tmp_path / "marker_num.csv"
    csv_path.write_text(
        "ID,Gewicht_g\n"
        "OBJ_0001,\n"
        "OBJ_0002,   \n"
        "OBJ_0003,k.a.\n"
        "OBJ_0004,n/a\n"
        "OBJ_0005,unbekannt\n"
        "OBJ_0006,?\n"
        "OBJ_0007,-\n"
        "OBJ_0008,K.A.\n",  # Grossschreibung
        encoding="utf-8",
    )
    assert find_rows_with_invalid_numeric_field(csv_path, "Gewicht_g") == []


def test_find_rows_with_invalid_numeric_field_ohne_spalte_ist_leer(tmp_path):
    """Fehlt die genannte Spalte komplett im File, wird ``[]`` zurueckgegeben.

    Spiegelt find_rows_with_invalid_funddatum: kein Datenverlust moeglich,
    wenn das Feld gar nicht Teil der CSV ist - der Report darf nicht
    faelschlich "0 Zeilen" statt "gar nicht anwendbar" signalisieren.
    """
    from stonebook.migration.csv_loaders import find_rows_with_invalid_numeric_field
    csv_path = tmp_path / "kein_gewicht.csv"
    csv_path.write_text(
        "ID,Mineral_Primaer\nOBJ_0001,Quarz\nOBJ_0002,Calcit\n",
        encoding="utf-8",
    )
    assert find_rows_with_invalid_numeric_field(csv_path, "Gewicht_g") == []


def test_find_rows_with_invalid_numeric_field_akzeptiert_obj_id_spalte(tmp_path):
    """JSON-/DB-Format nutzt ``obj_id`` statt ``ID`` - beide werden erkannt.

    Spiegelt die ID-Spalten-Aliasing-Regel der uebrigen Pre-Scanner:
    das Alias gilt fuer alle Silent-Drop-Detektoren einheitlich.
    """
    from stonebook.migration.csv_loaders import find_rows_with_invalid_numeric_field
    csv_path = tmp_path / "objid_num.csv"
    csv_path.write_text(
        "obj_id,Wert_CHF_roh\nOBJ_0001,42.5\nOBJ_0002,teuer\n",
        encoding="utf-8",
    )
    assert find_rows_with_invalid_numeric_field(
        csv_path, "Wert_CHF_roh") == [(2, "teuer")]


def test_find_rows_with_invalid_numeric_field_raises_bei_fehlender_id_spalte(tmp_path):
    """CSV mit Zeilen aber ohne ID/obj_id-Header wirft ValueError.

    Spiegelt find_duplicate_ids/find_rows_without_id/find_rows_with_invalid_funddatum/
    load_standard: alle stehen zur gleichen Format-Regel und lehnen v1/v2-
    Historik-CSVs sichtbar ab, statt stille "0 Funde" zu melden.
    """
    import pytest
    from stonebook.migration.csv_loaders import find_rows_with_invalid_numeric_field
    csv_path = tmp_path / "fremd_num.csv"
    csv_path.write_text(
        "Name,Mineralart,Fundort\nFoo,Quarz,Davos\n", encoding="utf-8")
    with pytest.raises(ValueError, match="ID-Spalte"):
        find_rows_with_invalid_numeric_field(csv_path, "Gewicht_g")


def test_find_rows_with_invalid_numeric_field_raises_bei_nicht_numerischem_feld(tmp_path):
    """Nicht-numerische Felder werfen ValueError.

    ``Fundort`` (str), ``Notizen`` (text), ``Kategorie`` (enum), ``Funddatum``
    (date), ``Foto_Uebersicht`` (path) sind keine Silent-Drop-Kandidaten auf
    der Zahl-Achse und wuerden vom Detektor irrefuehrende Ergebnisse liefern
    ("jeder freitext-Wert waere invalid"). Fuer ``date`` gibt es
    :func:`find_rows_with_invalid_funddatum` als spezialisierten Pfad; fuer
    Text-Felder gilt jeder nicht-leere Wert als gueltig (kein Silent-Drop
    moeglich). Ein Aufruf mit "Fundort" waere fast sicher ein Programmier-
    Fehler und darf nicht stillschweigend leere Liste liefern.
    """
    import pytest
    from stonebook.migration.csv_loaders import find_rows_with_invalid_numeric_field
    csv_path = tmp_path / "irrelevant.csv"
    csv_path.write_text("ID,Fundort\nOBJ_0001,Davos\n", encoding="utf-8")
    for col in ("Fundort", "Funddatum", "Mineral_Primaer", "Kategorie",
                "Foto_Uebersicht"):
        with pytest.raises(ValueError, match="Kein numerisches Standard-Feld"):
            find_rows_with_invalid_numeric_field(csv_path, col)
    # Erfundenes Feld wird ebenfalls abgewiesen (kein Regress zu einem
    # "unbekanntes Feld wird toleriert"-Verhalten).
    with pytest.raises(ValueError, match="Kein numerisches Standard-Feld"):
        find_rows_with_invalid_numeric_field(csv_path, "Halluzination")


def test_find_rows_with_invalid_numeric_field_scale_und_int_felder(tmp_path):
    """Detektor deckt alle NUMERIC_TYPES ab (float, int, scale).

    ``Confidence_Prozent`` (int) und ``Seltenheit_global_1_10`` (scale) sind
    numerisch konvertiert und teilen die Silent-Drop-Semantik: ein Freitext
    wie "hoch" oder "mittel" faellt via ``_int -> _num -> None`` durch, das
    Feld wird nicht uebernommen. Ohne diesen Test koennte eine spaetere
    Verschaerfung des Domain-Filters (z.B. nur ``float`` akzeptieren) die
    Scale-/Int-Coverage still abschneiden.
    """
    from stonebook.migration.csv_loaders import find_rows_with_invalid_numeric_field
    csv_path = tmp_path / "scale_int.csv"
    csv_path.write_text(
        "ID,Confidence_Prozent,Seltenheit_global_1_10\n"
        "OBJ_0001,85,7\n"
        "OBJ_0002,hoch,mittel\n"
        "OBJ_0003,42,-\n"   # "-" ist no-data-marker, nicht invalid
        "OBJ_0004,keine Angabe verfuegbar,unbekannt\n",  # nur Text ohne Zahl
        encoding="utf-8",
    )
    assert find_rows_with_invalid_numeric_field(
        csv_path, "Confidence_Prozent") == [
        (2, "hoch"),
        (4, "keine Angabe verfuegbar"),
    ]
    assert find_rows_with_invalid_numeric_field(
        csv_path, "Seltenheit_global_1_10") == [
        (2, "mittel"),
    ]


def test_find_rows_with_invalid_numeric_fields_bulk_standard(tmp_path):
    """Bulk-Scanner buendelt alle numerischen Spalten in einem Aufruf.

    Symmetrie-Vervollstaendigung zur singularen Variante: waehrend die
    Einzel-Spalte-Version einen konkreten Feldnamen erwartet, laeuft die
    Plural-Version selbstaendig ueber alle im File vorhandenen numerischen
    Spalten und emittiert (Zeile, Spalte, Roh-Wert)-Tripel. Vorbedingung
    fuer die ImportReport-Wiring, die ohne feste Spalten-Liste auskommen
    muss. Reihenfolge = Zeile-primaer, Spalte-sekundaer in Header-Reihenfolge.
    """
    from stonebook.migration.csv_loaders import (
        find_rows_with_invalid_numeric_fields,
    )
    csv_path = tmp_path / "bulk.csv"
    csv_path.write_text(
        "ID,Gewicht_g,Wert_CHF_roh,Mineral_Primaer\n"
        "OBJ_0001,42.5,500,Quarz\n"
        "OBJ_0002,sehr schwer,teuer,Calcit\n"     # zwei Silent-Drops in Zeile 2
        "OBJ_0003,150,ca. 750,Amethyst\n"          # Zeile 3 sauber
        "OBJ_0004,,unbekannt,Turmalin\n"           # leer/Marker - kein Report
        "OBJ_0005,mittel,,Diopsid\n",              # nur Gewicht kaputt
        encoding="utf-8",
    )
    assert find_rows_with_invalid_numeric_fields(csv_path) == [
        (2, "Gewicht_g", "sehr schwer"),
        (2, "Wert_CHF_roh", "teuer"),
        (5, "Gewicht_g", "mittel"),
    ]


def test_find_rows_with_invalid_numeric_fields_ohne_numerische_spalten(tmp_path):
    """Fehlen numerische Spalten komplett -> [] statt ValueError.

    Spiegelt die Kein-Datenverlust-Regel der Einzel-Version: wenn das File
    keine numerischen Felder enthaelt, kann es dort auch keinen Silent-Drop
    geben - der Report darf nicht kuenstlich ValueError werfen.
    """
    from stonebook.migration.csv_loaders import (
        find_rows_with_invalid_numeric_fields,
    )
    csv_path = tmp_path / "kein_num.csv"
    csv_path.write_text(
        "ID,Mineral_Primaer,Fundort\nOBJ_0001,Quarz,Davos\n",
        encoding="utf-8",
    )
    assert find_rows_with_invalid_numeric_fields(csv_path) == []


def test_find_rows_with_invalid_numeric_fields_ignoriert_no_data_marker(tmp_path):
    """Explizite "keine Angabe"-Marker werden auch im Bulk-Scan uebersprungen.

    Marker-Menge muss zwischen singular und plural konsistent sein - Wenn
    der User in einer Spalte ``k.a.`` schreibt, ist das explizite
    ``kein Wert verfuegbar``, kein Silent-Drop. Ein Regress hier wuerde die
    Report-Ausgabe mit Rauschmeldungen fluten.
    """
    from stonebook.migration.csv_loaders import (
        find_rows_with_invalid_numeric_fields,
    )
    csv_path = tmp_path / "marker_bulk.csv"
    csv_path.write_text(
        "ID,Gewicht_g,Wert_CHF_roh,Confidence_Prozent\n"
        "OBJ_0001,k.a.,n/a,unbekannt\n"
        "OBJ_0002,?,-,K.A.\n"
        "OBJ_0003,,   ,\n",
        encoding="utf-8",
    )
    assert find_rows_with_invalid_numeric_fields(csv_path) == []


def test_find_rows_with_invalid_numeric_fields_scale_und_int_felder(tmp_path):
    """Bulk-Scan deckt alle NUMERIC_TYPES ab (float / int / scale).

    Analog zur singularen Variante: Confidence_Prozent (int),
    Seltenheit_global_1_10 (scale), Gewicht_g (float) sind alle numerisch
    konvertiert und teilen die Silent-Drop-Semantik. Ohne diesen Test
    koennte eine spaetere Domain-Verengung des Bulk-Scanners (nur float)
    die Scale-/Int-Coverage still abschneiden.
    """
    from stonebook.migration.csv_loaders import (
        find_rows_with_invalid_numeric_fields,
    )
    csv_path = tmp_path / "types.csv"
    csv_path.write_text(
        "ID,Confidence_Prozent,Seltenheit_global_1_10,Gewicht_g\n"
        "OBJ_0001,hoch,mittel,leicht\n",
        encoding="utf-8",
    )
    assert find_rows_with_invalid_numeric_fields(csv_path) == [
        (1, "Confidence_Prozent", "hoch"),
        (1, "Seltenheit_global_1_10", "mittel"),
        (1, "Gewicht_g", "leicht"),
    ]


def test_find_rows_with_invalid_numeric_fields_akzeptiert_obj_id_spalte(tmp_path):
    """JSON-/DB-Format nutzt ``obj_id`` statt ``ID``.

    Bulk-Scan-Konsistenz mit der ID-Alias-Regel der uebrigen Silent-Drop-
    Detektoren: ein Reexport aus dem DB-Backup-JSON (Header ``obj_id``) muss
    genauso verarbeitet werden wie ein CSV-Export (Header ``ID``).
    """
    from stonebook.migration.csv_loaders import (
        find_rows_with_invalid_numeric_fields,
    )
    csv_path = tmp_path / "objid_bulk.csv"
    csv_path.write_text(
        "obj_id,Wert_CHF_roh\nOBJ_0001,42.5\nOBJ_0002,teuer\n",
        encoding="utf-8",
    )
    assert find_rows_with_invalid_numeric_fields(csv_path) == [
        (2, "Wert_CHF_roh", "teuer"),
    ]


def test_find_rows_with_invalid_numeric_fields_raises_bei_fehlender_id_spalte(tmp_path):
    """CSV mit Zeilen aber ohne ID/obj_id-Header wirft ValueError.

    Format-Regel-Konsistenz: alle Pre-Scanner
    (find_duplicate_ids/find_rows_without_id/find_rows_with_invalid_funddatum/
    find_rows_with_invalid_numeric_field und jetzt auch die Bulk-Variante)
    lehnen v1/v2-Historik-CSVs sichtbar ab, statt stille "0 Funde" zu melden.
    """
    import pytest
    from stonebook.migration.csv_loaders import (
        find_rows_with_invalid_numeric_fields,
    )
    csv_path = tmp_path / "fremd_bulk.csv"
    csv_path.write_text(
        "Name,Mineralart,Fundort\nFoo,Quarz,Davos\n", encoding="utf-8")
    with pytest.raises(ValueError, match="ID-Spalte"):
        find_rows_with_invalid_numeric_fields(csv_path)


def test_find_rows_with_invalid_numeric_fields_leere_csv(tmp_path):
    """Leere CSV (nur Header) -> [] ohne Fehler.

    Spiegelt find_rows_with_invalid_funddatum_leere_csv: ohne Zeilen kann
    es keinen Datenverlust geben, unabhaengig vom Header-Format. Auch dann
    keine ValueError, wenn der Header keine ID-Spalte hat - konsistent mit
    dem "Zeilen == 0"-Kurzschluss der uebrigen Silent-Drop-Detektoren.
    """
    from stonebook.migration.csv_loaders import (
        find_rows_with_invalid_numeric_fields,
    )
    csv_path = tmp_path / "leer_bulk.csv"
    csv_path.write_text("Name,Mineralart\n", encoding="utf-8")
    assert find_rows_with_invalid_numeric_fields(csv_path) == []


def test_load_standard_raises_bei_fehlender_id_spalte(tmp_path):
    """CSV ohne ID/obj_id-Spalte ist kein gueltiger Standard-Import - klarer Fehler."""
    import pytest
    csv_path = tmp_path / "fremd.csv"
    csv_path.write_text(
        "Name,Mineralart,Fundort\nFoo,Quarz,Davos\n",
        encoding="utf-8",
    )
    from stonebook.migration.csv_loaders import load_standard
    with pytest.raises(ValueError, match="ID-Spalte"):
        load_standard(csv_path)


def test_load_standard_leere_csv_ohne_id_spalte_ist_ok(tmp_path):
    """Leere CSV (nur Header) loest keinen Fehler aus - return {} ist sinnvoll."""
    csv_path = tmp_path / "leer.csv"
    csv_path.write_text("Name,Mineralart\n", encoding="utf-8")
    from stonebook.migration.csv_loaders import load_standard
    assert load_standard(csv_path) == {}


def test_load_obj043():
    data = csv_loaders.load_obj043(
        CSV_DIR / "Stonebock__StoneBoock_Objekt_043_FULL__StoneBoock_Objekt_043.csv")
    o43 = data["OBJ_0043"]
    assert o43["Gewicht_g"] == 41.0
    assert "Quarz" in o43["Mineral_Primaer"]
    assert o43["Dichte_min_gcm3"] == 2.65
    assert o43["Dichte_max_gcm3"] == 2.65
    assert o43["Mohs_Haerte_min"] == 7.0


def test_load_v1_cp1252_fallback(tmp_path):
    """v1-Loader greift jetzt auf den gleichen tolerant-Reader wie load_standard zu.

    Re-editierte Historik-CSVs aus Excel/Notepad mit cp1252-Encoding (typisch beim
    "Speichern unter..."-Dialog auf aelteren Windows-Versionen) wurden bisher von
    ``_read_csv`` mit utf-8-sig-only stillschweigend zur ``UnicodeDecodeError``-
    Exception eskaliert. Nach der Konsolidierung auf ``_read_csv_robust`` greift
    der Encoding-Fallback (utf-8-sig -> utf-8 -> cp1252 -> latin-1) auch fuer die
    historischen Loader.
    """
    p = tmp_path / "v1_cp1252.csv"
    # Volle v1-Spaltenliste mit Härte/Dichte/Wert-Spalten; nur die kritischen
    # Umlaute (Härte, Rötlich) testen den Encoding-Fallback.
    header = ("ID,Name,Beschreibung,Mineralart,Fundort,UV-Reaktion,Härte,Dichte,"
              "Transparenz,Farbe,Wert_CHF_roh,Wert_CHF_poliert,Wert_CHF_Schmuck,"
              "Wert_USD_Talisman,Marktwert,Wissenschaftlicher_Wert,"
              "Seltenheit_global,Seltenheit_Fundort,Nachfrage,Inhaltsstoffe,"
              "Beste_Verwendung\n")
    row = ("OBJ_0001,Jaspis,Rötlicher Stein,Jaspis,Schweiz,keine,6.5-7,2.65,"
           "opak,rot,100,200,300,50,150,80,7,5,6,SiO2,Sammlung\n")
    p.write_bytes((header + row).encode("cp1252"))
    data = csv_loaders.load_v1(p)
    assert "OBJ_0001" in data
    o = data["OBJ_0001"]
    assert o["Mineral_Primaer"] == "Jaspis"
    assert o["Mohs_Haerte_min"] == 6.5
    assert o["Mohs_Haerte_max"] == 7.0
    assert "Rötlich" in o["notizen"]


def test_load_v2_semicolon_delimiter(tmp_path):
    """v2-Loader erkennt jetzt ``;`` als Delimiter (DE-Excel-Default).

    DE-/CH-Excel speichert beim CSV-Export per Default mit Semikolon, weil das
    Komma als Dezimal-Trenner reserviert ist. Vor der Konsolidierung scheiterte
    ``load_v2`` auf solchen Re-Exports stille mit leerem Dict (Header als
    Einzelspalte ``ID;Name;...`` interpretiert, keine ID-Spalte gefunden).
    Der tolerant-Reader detektiert jetzt den haeufigsten Trenner aus der
    Header-Zeile.
    """
    p = tmp_path / "v2_semicolon.csv"
    header = "ID;Name;Mineral_Primaer;Mohs_Haerte_min;Mohs_Haerte_max\n"
    row = "OBJ_0007;Bergkristall;Quarz;7;7\n"
    p.write_text(header + row, encoding="utf-8")
    data = csv_loaders.load_v2(p)
    assert "OBJ_0007" in data
    o = data["OBJ_0007"]
    assert o["Mineral_Primaer"] == "Quarz"
    assert o["Mohs_Haerte_min"] == 7.0
    assert o["Mohs_Haerte_max"] == 7.0


def test_parse_range_annaeherungs_praefix_mit_uncertainty():
    """Annaeherungs-Praefix am Wert-Anfang ("ca.", "circa", "about", "approx.",
    "estimated", "um", "etwa", "vermutlich", "geschaetzt", "wahrscheinlich",
    "~", "≈" ...) wird gestrippt, damit die nachfolgende Uncertainty-Notation
    (``±``-Langform oder ``N(M)``-Kompaktform) die publizierte Toleranz als
    Bereichsgrenzen behaelt.

    Vor dem Fix fielen alle Kombinationen "Approximations-Praefix +
    Uncertainty" still auf die Fallback-Zahl-Extraktion durch, weil sowohl
    :data:`_PLUS_MINUS_UNCERTAINTY` als auch :data:`_PARENTHESIS_UNCERTAINTY`
    per ``^...$``-Anker eine reine Zahl am String-Anfang verlangen:

    * ``"ca. 5.5 ± 0.3"``    -> ``[5.5, 0.3]`` -> (5.5, 5.5)  (Toleranz verloren)
    * ``"circa 5.5(3)"``      -> ``[5.5, 3.0]`` -> (5.5, 5.5)  (dito IUCr-Kompakt)
    * ``"~2.65 ± 0.05"``      -> ``[2.65, 0.05]`` -> (2.65, 2.65) (Toleranz verloren)
    * ``"approx 100(2)"``     -> ``[100, 2]`` -> (100, 100)  (dito IUCr-Kompakt)
    * ``"≈-1.5 ± 0.3 °C"``    -> ``[-1.5, 0.3]`` -> (-1.5, 0.3) (semantisch falsch)

    In Publikationen, Auktions-Katalogen (Preis-Schaetzungen mit publizierter
    Streuung "ca. 500 CHF ± 50") und Sammler-Notizen ist die Kombination
    verbreitet, weil der Approximations-Marker die Praezision des Zentrums
    beziffert waehrend die Uncertainty-Notation die Streuung um dieses
    (approximative) Zentrum publiziert - beide Marker sind komplementaer,
    nicht redundant.

    Vokabel-Liste und Zweig-Layout spiegeln
    :data:`stonebook.migration.validators._APPROX_PREFIX`: DE- und EN-
    Vollformen und Abkuerzungen (``ca.``/``circa``/``approx.``/``about``/
    ``roughly``/``estimated``/``est.``/``um``/``gegen``/``etwa``/
    ``vermutlich``, ``sch[äa]tzungsweise``, ``ungef[äa]hr``, ``gesch[äa]tzt``,
    ``wahrscheinlich``, ``m[öo]glicherweise``, ``evtl.``/``eventuell``,
    ``perhaps``/``possibly``/``maybe``), sowie symbolische Marker
    (Tilde ``~`` U+007E, Almost-Equal ``≈`` U+2248). Umlaut- und
    Transliterations-Varianten parallel wie bei den Datums-Praefixen, damit
    Windows-CP1252/Excel-DE nativ (``ungefähr``) und 7-bit-ASCII-Notizen
    (``ungefaehr``) identisch behandelt werden.
    """
    # Wort-Praefix + ±-Langform-Uncertainty. Der Praefix wird gestrippt,
    # die publizierte Toleranz laeuft in den _PLUS_MINUS_UNCERTAINTY-Zweig.
    assert csv_loaders.parse_range("ca. 5.5 ± 0.3") == pytest.approx((5.2, 5.8))
    assert csv_loaders.parse_range("ca 5.5 ± 0.3") == pytest.approx((5.2, 5.8))
    assert csv_loaders.parse_range("circa 5.5 ± 0.3") == pytest.approx((5.2, 5.8))
    assert csv_loaders.parse_range("etwa 5.5 ± 0.3") == pytest.approx((5.2, 5.8))
    assert csv_loaders.parse_range("about 5.5 ± 0.3") == pytest.approx((5.2, 5.8))
    assert csv_loaders.parse_range("approx 5.5 ± 0.3") == pytest.approx((5.2, 5.8))
    assert csv_loaders.parse_range("approx. 5.5 ± 0.3") == pytest.approx((5.2, 5.8))
    assert csv_loaders.parse_range("approximately 5.5 ± 0.3") == pytest.approx((5.2, 5.8))
    assert csv_loaders.parse_range("around 5.5 ± 0.3") == pytest.approx((5.2, 5.8))
    assert csv_loaders.parse_range("roughly 5.5 ± 0.3") == pytest.approx((5.2, 5.8))
    assert csv_loaders.parse_range("estimated 5.5 ± 0.3") == pytest.approx((5.2, 5.8))
    assert csv_loaders.parse_range("est. 5.5 ± 0.3") == pytest.approx((5.2, 5.8))
    assert csv_loaders.parse_range("um 5.5 ± 0.3") == pytest.approx((5.2, 5.8))
    assert csv_loaders.parse_range("gegen 5.5 ± 0.3") == pytest.approx((5.2, 5.8))
    assert csv_loaders.parse_range("vermutlich 5.5 ± 0.3") == pytest.approx((5.2, 5.8))
    # DE-Vollform mit Umlaut und ASCII-Transliteration parallel.
    assert csv_loaders.parse_range("ungefähr 5.5 ± 0.3") == pytest.approx((5.2, 5.8))
    assert csv_loaders.parse_range("ungefaehr 5.5 ± 0.3") == pytest.approx((5.2, 5.8))
    assert csv_loaders.parse_range("geschätzt 5.5 ± 0.3") == pytest.approx((5.2, 5.8))
    assert csv_loaders.parse_range("geschaetzt 5.5 ± 0.3") == pytest.approx((5.2, 5.8))
    assert csv_loaders.parse_range("schätzungsweise 5.5 ± 0.3") == pytest.approx((5.2, 5.8))
    assert csv_loaders.parse_range("schaetzungsweise 5.5 ± 0.3") == pytest.approx((5.2, 5.8))
    # Wahrscheinlichkeits-/Vermutungs-Marker.
    assert csv_loaders.parse_range("wahrscheinlich 5.5 ± 0.3") == pytest.approx((5.2, 5.8))
    assert csv_loaders.parse_range("möglicherweise 5.5 ± 0.3") == pytest.approx((5.2, 5.8))
    assert csv_loaders.parse_range("moeglicherweise 5.5 ± 0.3") == pytest.approx((5.2, 5.8))
    assert csv_loaders.parse_range("evtl. 5.5 ± 0.3") == pytest.approx((5.2, 5.8))
    assert csv_loaders.parse_range("eventuell 5.5 ± 0.3") == pytest.approx((5.2, 5.8))
    assert csv_loaders.parse_range("perhaps 5.5 ± 0.3") == pytest.approx((5.2, 5.8))
    assert csv_loaders.parse_range("possibly 5.5 ± 0.3") == pytest.approx((5.2, 5.8))
    assert csv_loaders.parse_range("maybe 5.5 ± 0.3") == pytest.approx((5.2, 5.8))
    # Case-Insensitivitaet ist in :data:`_APPROX_VALUE_PREFIX` per re.IGNORECASE
    # gesetzt, damit Sammler-Notizen mit uppercase Anfang ("Ca. 5.5") oder
    # gemischtem Kanon ("CIRCA 5.5") identisch behandelt werden.
    assert csv_loaders.parse_range("Ca. 5.5 ± 0.3") == pytest.approx((5.2, 5.8))
    assert csv_loaders.parse_range("CIRCA 5.5 ± 0.3") == pytest.approx((5.2, 5.8))
    assert csv_loaders.parse_range("ESTIMATED 5.5 ± 0.3") == pytest.approx((5.2, 5.8))
    # Symbolische Marker ``~`` und ``≈`` - null Leerzeichen erlaubt (spiegelt
    # die Symbolic-Marker-Konvention aus _APPROX_PREFIX in validators.py).
    assert csv_loaders.parse_range("~5.5 ± 0.3") == pytest.approx((5.2, 5.8))
    assert csv_loaders.parse_range("~ 5.5 ± 0.3") == pytest.approx((5.2, 5.8))
    assert csv_loaders.parse_range("≈5.5 ± 0.3") == pytest.approx((5.2, 5.8))
    assert csv_loaders.parse_range("≈ 5.5 ± 0.3") == pytest.approx((5.2, 5.8))
    # ASCII-Ersatzformen der Uncertainty-Struktur bleiben mit Praefix erhalten.
    assert csv_loaders.parse_range("ca. 5.5 +/- 0.3") == pytest.approx((5.2, 5.8))
    assert csv_loaders.parse_range("ca. 5.5+/-0.3") == pytest.approx((5.2, 5.8))
    assert csv_loaders.parse_range("~5.5+-0.3") == pytest.approx((5.2, 5.8))
    # DE-Komma-Dezimal in der Uncertainty-Notation bleibt mit Praefix erhalten.
    assert csv_loaders.parse_range("ca. 2,65 ± 0,05") == pytest.approx((2.60, 2.70))
    assert csv_loaders.parse_range("~2,65 ± 0,05") == pytest.approx((2.60, 2.70))
    # Wort-Praefix + IUCr-Kompakt-Uncertainty ``N(M)`` - der Praefix wird
    # gestrippt, die publizierte Toleranz laeuft in den _PARENTHESIS_UNCERTAINTY-
    # Zweig.
    assert csv_loaders.parse_range("ca. 5.5(3)") == pytest.approx((5.2, 5.8))
    assert csv_loaders.parse_range("circa 2.65(5)") == pytest.approx((2.60, 2.70))
    assert csv_loaders.parse_range("approx 100(2)") == pytest.approx((98.0, 102.0))
    assert csv_loaders.parse_range("~5.5(3)") == pytest.approx((5.2, 5.8))
    assert csv_loaders.parse_range("≈2.65(5)") == pytest.approx((2.60, 2.70))
    assert csv_loaders.parse_range("estimated 12.345(67)") == pytest.approx((12.278, 12.412))
    # Negatives Zentrum mit Praefix (Kryo-/Isotopen-Werte in Publikationen
    # oft mit Approximations-Marker).
    assert csv_loaders.parse_range("ca. -1.5 ± 0.3") == pytest.approx((-1.8, -1.2))
    assert csv_loaders.parse_range("~-1.5 ± 0.3") == pytest.approx((-1.8, -1.2))
    assert csv_loaders.parse_range("circa -2.65(5)") == pytest.approx((-2.70, -2.60))
    # Praefix + Uncertainty + Trailing-Einheit - die Einheit bleibt symmetrisch
    # zur reinen Uncertainty-Notation erhalten.
    assert csv_loaders.parse_range("ca. 2.65 ± 0.05 g/cm³") == pytest.approx((2.60, 2.70))
    assert csv_loaders.parse_range("~5.5 ± 0.3 mm") == pytest.approx((5.2, 5.8))
    assert csv_loaders.parse_range("about 100 ± 2 HV") == pytest.approx((98.0, 102.0))
    assert csv_loaders.parse_range("estimated -1.5 ± 0.3 °C") == pytest.approx((-1.8, -1.2))
    assert csv_loaders.parse_range("ca. 5.5(3) Mohs") == pytest.approx((5.2, 5.8))
    # Praefix + Uncertainty + Trailing-Klammer-Annotation ((Literatur), [Ref]).
    assert csv_loaders.parse_range("ca. 5.5 ± 0.3 (Literatur)") == pytest.approx((5.2, 5.8))
    assert csv_loaders.parse_range("~2.65(5) [Ref 42]") == pytest.approx((2.60, 2.70))
    # Praefix + Uncertainty + Trailing-Satzzeichen (Excel-CSV-Zeilen-Ende-
    # Punkt/Komma aus Editor-Autocomplete).
    assert csv_loaders.parse_range("ca. 5.5 ± 0.3.") == pytest.approx((5.2, 5.8))
    assert csv_loaders.parse_range("~2.65(5),") == pytest.approx((2.60, 2.70))
    # Kollisionsschutz gegen fehlendes Trennungs-Whitespace bei Wort-Praefixen:
    # ``ca5.5`` (ohne Space) ist kein Approximations-Marker - der Wort-Zweig
    # verlangt mindestens ein Space, damit "ca" nicht in Bezeichner-Namen
    # ("Sample-ca17", "Catalog-ca42") als Praefix fehlgelesen wird.
    # Existierende Semantik (Fallback-Zahl-Extraktion findet ``.5`` als 0.5)
    # bleibt unveraendert.
    assert csv_loaders.parse_range("ca5.5") == (0.5, 0.5)
    # Symbolische Marker OHNE nachfolgende Zahl fallen still auf None -
    # ohne Zahl gibt es keinen Wert.
    assert csv_loaders.parse_range("ca.") == (None, None)
    assert csv_loaders.parse_range("circa") == (None, None)
    assert csv_loaders.parse_range("~") == (None, None)
    assert csv_loaders.parse_range("≈") == (None, None)
    # Regress-Anker: Praefix vor reiner Zahl (ohne Uncertainty) bleibt
    # rueckwaerts-kompatibel - der Praefix wird gestrippt und die reine
    # Zahl-Extraktion laeuft weiter.
    assert csv_loaders.parse_range("ca. 5.5") == (5.5, 5.5)
    assert csv_loaders.parse_range("~5.5") == (5.5, 5.5)
    assert csv_loaders.parse_range("estimated 5.5") == (5.5, 5.5)
    # Regress-Anker: Praefix vor Range-Notation (ohne Uncertainty) bleibt
    # rueckwaerts-kompatibel - die Range-Grenzen laufen in die Fallback-
    # Zahl-Extraktion nach dem Praefix-Strip.
    assert csv_loaders.parse_range("ca. 5.5-7.5") == (5.5, 7.5)
    assert csv_loaders.parse_range("ca. 5.5 - 7.5") == (5.5, 7.5)
    assert csv_loaders.parse_range("~5.5-7.5") == (5.5, 7.5)
    assert csv_loaders.parse_range("estimated 5.5 to 7.5") == (5.5, 7.5)
    # Regress-Anker: Werte OHNE Approximations-Praefix bleiben unveraendert.
    assert csv_loaders.parse_range("5.5") == (5.5, 5.5)
    assert csv_loaders.parse_range("5.5 ± 0.3") == pytest.approx((5.2, 5.8))
    assert csv_loaders.parse_range("2.65(5)") == pytest.approx((2.60, 2.70))
    assert csv_loaders.parse_range("100(2)") == pytest.approx((98.0, 102.0))
    assert csv_loaders.parse_range("5.5-7.5") == (5.5, 7.5)


def test_parse_range_annaeherungs_praefix_unicode_cong_simeq():
    """Unicode-Naeherungs-Marker ``≅`` (U+2245, LaTeX \\cong) und ``≃`` (U+2243,
    LaTeX \\simeq) als Leading-Approximations-Praefix.

    Spiegelt strukturell die bereits vorhandene Symbolic-Marker-Klasse
    ``[~≈]`` auf zwei weitere, in Print-/LaTeX-Publikationen und in aus
    LaTeX-exportierten Datenbank-CSVs gebraeuchliche Unicode-Symbole. In
    Physik-/Engineering-/Mineralogie-Referenz-Tabellen (IUCr, NIST, RRUFF-
    Datenbank, Handbook of Mineralogy) rendert der LaTeX-Befehl ``\\cong``
    zu ``≅`` und ``\\simeq`` zu ``≃`` - beide semantisch identisch zu
    ``≈``/``~`` (Naeherungs-Marker vor dem Wert).

    Bisher fielen alle Formen mit diesen zwei Marker-Varianten still auf die
    Fallback-Zahl-Extraktion durch; bei Uncertainty-Kombinationen ("≅ 5.5 ±
    0.3", "≃ 2.65(5)") fiel ausserdem die publizierte Toleranz ueber den
    ``[center, tol]``-inverted-Range-Kollaps auf ``(center, center)`` still
    verloren - identischer Bug-Effekt wie bei ``~``/``≈`` vor Einfuehrung der
    Symbolic-Marker-Klasse.
    """
    # ≅ (U+2245, APPROXIMATELY EQUAL TO, LaTeX \cong) - null Leerzeichen
    # erlaubt (spiegelt die Symbolic-Marker-Konvention ohne Wort-Trennung).
    assert csv_loaders.parse_range("≅5.5 ± 0.3") == pytest.approx((5.2, 5.8))
    assert csv_loaders.parse_range("≅ 5.5 ± 0.3") == pytest.approx((5.2, 5.8))
    assert csv_loaders.parse_range("≅5.5") == (5.5, 5.5)
    assert csv_loaders.parse_range("≅ 5.5") == (5.5, 5.5)
    # ≃ (U+2243, ASYMPTOTICALLY EQUAL TO, LaTeX \simeq).
    assert csv_loaders.parse_range("≃5.5 ± 0.3") == pytest.approx((5.2, 5.8))
    assert csv_loaders.parse_range("≃ 5.5 ± 0.3") == pytest.approx((5.2, 5.8))
    assert csv_loaders.parse_range("≃5.5") == (5.5, 5.5)
    assert csv_loaders.parse_range("≃ 5.5") == (5.5, 5.5)
    # IUCr-Kompakt-Uncertainty ``N(M)`` mit beiden Markern - der Praefix wird
    # gestrippt, die publizierte Toleranz laeuft in den _PARENTHESIS_UNCERTAINTY-
    # Zweig.
    assert csv_loaders.parse_range("≅2.65(5)") == pytest.approx((2.60, 2.70))
    assert csv_loaders.parse_range("≃2.65(5)") == pytest.approx((2.60, 2.70))
    assert csv_loaders.parse_range("≅100(2)") == pytest.approx((98.0, 102.0))
    assert csv_loaders.parse_range("≃100(2)") == pytest.approx((98.0, 102.0))
    # ASCII-Ersatzformen der Uncertainty-Struktur bleiben mit Praefix erhalten.
    assert csv_loaders.parse_range("≅5.5 +/- 0.3") == pytest.approx((5.2, 5.8))
    assert csv_loaders.parse_range("≃5.5+-0.3") == pytest.approx((5.2, 5.8))
    # DE-Komma-Dezimal in der Uncertainty-Notation bleibt mit Praefix erhalten
    # (Suisse romande CSV-Excel-Konvention).
    assert csv_loaders.parse_range("≅2,65 ± 0,05") == pytest.approx((2.60, 2.70))
    assert csv_loaders.parse_range("≃2,65 ± 0,05") == pytest.approx((2.60, 2.70))
    # Negatives Zentrum mit Praefix (Kryo-/Isotopen-Werte in Publikationen oft
    # mit Approximations-Marker).
    assert csv_loaders.parse_range("≅-1.5 ± 0.3") == pytest.approx((-1.8, -1.2))
    assert csv_loaders.parse_range("≃-1.5 ± 0.3") == pytest.approx((-1.8, -1.2))
    assert csv_loaders.parse_range("≅-2.65(5)") == pytest.approx((-2.70, -2.60))
    # Praefix + Uncertainty + Trailing-Einheit - die Einheit bleibt symmetrisch
    # zur reinen Uncertainty-Notation erhalten.
    assert csv_loaders.parse_range("≅2.65 ± 0.05 g/cm³") == pytest.approx((2.60, 2.70))
    assert csv_loaders.parse_range("≃5.5 ± 0.3 mm") == pytest.approx((5.2, 5.8))
    assert csv_loaders.parse_range("≅100 ± 2 HV") == pytest.approx((98.0, 102.0))
    assert csv_loaders.parse_range("≃-1.5 ± 0.3 °C") == pytest.approx((-1.8, -1.2))
    # Praefix + Uncertainty + Trailing-Klammer-Annotation ((Literatur), [Ref]).
    assert csv_loaders.parse_range("≅5.5 ± 0.3 (Literatur)") == pytest.approx((5.2, 5.8))
    assert csv_loaders.parse_range("≃2.65(5) [Ref 42]") == pytest.approx((2.60, 2.70))
    # Kombination mit Waehrungs-Praefix via Rekursion (spiegelt die identische
    # Verkettungs-Semantik der uebrigen Symbolic-/Wort-Praefixe).
    assert csv_loaders.parse_range("≅ CHF 500 ± 50") == pytest.approx((450.0, 550.0))
    assert csv_loaders.parse_range("≃ EUR 2.65 ± 0.05") == pytest.approx((2.60, 2.70))
    # Kombination mit Vergleichs-Praefix via Rekursion (spiegelt die identische
    # Verkettungs-Semantik).
    assert csv_loaders.parse_range("≅ > 500") == (500.0, None)
    assert csv_loaders.parse_range("≃ < 100") == (None, 100.0)
    # Symbolische Marker OHNE nachfolgende Zahl fallen still auf None - ohne
    # Zahl gibt es keinen Wert (spiegelt ``~`` / ``≈`` Regress-Verhalten).
    assert csv_loaders.parse_range("≅") == (None, None)
    assert csv_loaders.parse_range("≃") == (None, None)
    # Regress-Anker: die bereits vorher unterstuetzten Symbole bleiben unveraendert.
    assert csv_loaders.parse_range("~5.5 ± 0.3") == pytest.approx((5.2, 5.8))
    assert csv_loaders.parse_range("≈5.5 ± 0.3") == pytest.approx((5.2, 5.8))
    # Regress-Anker: Werte OHNE Approximations-Praefix bleiben unveraendert.
    assert csv_loaders.parse_range("5.5") == (5.5, 5.5)
    assert csv_loaders.parse_range("5.5 ± 0.3") == pytest.approx((5.2, 5.8))
    assert csv_loaders.parse_range("2.65(5)") == pytest.approx((2.60, 2.70))


def test_parse_range_annaeherungs_praefix_unicode_sim():
    """Unicode-Naeherungs-Marker ``∼`` (U+223C, TILDE OPERATOR, LaTeX \\sim) als
    Leading-Approximations-Praefix.

    Spiegelt strukturell die bereits vorhandene Symbolic-Marker-Klasse
    ``[~≈≅≃]`` auf den mathematischen Tilde-Operator U+223C. LaTeX rendert
    im Math-Mode den Befehl ``\\sim`` zu U+223C (waehrend der ASCII-Tilde
    U+007E dem Text-Mode-Befehl ``\\textasciitilde`` entspricht) - PDF-
    Text-Extraktion aus LaTeX-gesetzten Publikationen (IUCr, NIST, RRUFF,
    Mindat.org, Handbook of Mineralogy) exportiert den Math-Mode-Tilde als
    U+223C und nicht als ASCII-``~``, sodass Sammler-Notizen beim Copy&
    Paste aus solchen Quellen den Unicode-Punkt uebernehmen. Schliesst die
    letzte Luecke der Math-Mode-Naeherungs-Symbol-Achse (``≈``=``\\approx``,
    ``≅``=``\\cong``, ``≃``=``\\simeq``, ``∼``=``\\sim``).

    Bisher fielen alle Formen mit ``∼``-Praefix still auf die Fallback-
    Zahl-Extraktion durch; bei Uncertainty-Kombinationen ("∼5.5 ± 0.3",
    "∼2.65(5)") fiel ausserdem die publizierte Toleranz ueber den
    ``[center, tol]``-inverted-Range-Kollaps auf ``(center, center)`` still
    verloren - identischer Bug-Effekt wie bei ``≅``/``≃`` vor Einfuehrung
    dieser Marker in c6ce6ac.
    """
    # ∼ (U+223C, TILDE OPERATOR, LaTeX \sim) - null Leerzeichen erlaubt
    # (spiegelt die Symbolic-Marker-Konvention ohne Wort-Trennung).
    assert csv_loaders.parse_range("∼5.5 ± 0.3") == pytest.approx((5.2, 5.8))
    assert csv_loaders.parse_range("∼ 5.5 ± 0.3") == pytest.approx((5.2, 5.8))
    assert csv_loaders.parse_range("∼5.5") == (5.5, 5.5)
    assert csv_loaders.parse_range("∼ 5.5") == (5.5, 5.5)
    # IUCr-Kompakt-Uncertainty ``N(M)`` - Praefix strippen, Toleranz erhalten.
    assert csv_loaders.parse_range("∼2.65(5)") == pytest.approx((2.60, 2.70))
    assert csv_loaders.parse_range("∼100(2)") == pytest.approx((98.0, 102.0))
    # ASCII-Ersatzformen der Uncertainty-Struktur.
    assert csv_loaders.parse_range("∼5.5 +/- 0.3") == pytest.approx((5.2, 5.8))
    assert csv_loaders.parse_range("∼5.5+-0.3") == pytest.approx((5.2, 5.8))
    # DE-Komma-Dezimal in der Uncertainty-Notation (Suisse romande CSV/Excel).
    assert csv_loaders.parse_range("∼2,65 ± 0,05") == pytest.approx((2.60, 2.70))
    # Negatives Zentrum (Kryo-/Isotopen-Werte in Publikationen).
    assert csv_loaders.parse_range("∼-1.5 ± 0.3") == pytest.approx((-1.8, -1.2))
    assert csv_loaders.parse_range("∼-2.65(5)") == pytest.approx((-2.70, -2.60))
    # Praefix + Uncertainty + Trailing-Einheit - Einheit bleibt erhalten.
    assert csv_loaders.parse_range("∼2.65 ± 0.05 g/cm³") == pytest.approx((2.60, 2.70))
    assert csv_loaders.parse_range("∼5.5 ± 0.3 mm") == pytest.approx((5.2, 5.8))
    assert csv_loaders.parse_range("∼100 ± 2 HV") == pytest.approx((98.0, 102.0))
    # Praefix + Uncertainty + Trailing-Klammer-Annotation.
    assert csv_loaders.parse_range("∼5.5 ± 0.3 (Literatur)") == pytest.approx((5.2, 5.8))
    assert csv_loaders.parse_range("∼2.65(5) [Ref 42]") == pytest.approx((2.60, 2.70))
    # Kombination mit Waehrungs-Praefix via Rekursion.
    assert csv_loaders.parse_range("∼ CHF 500 ± 50") == pytest.approx((450.0, 550.0))
    assert csv_loaders.parse_range("∼ EUR 2.65 ± 0.05") == pytest.approx((2.60, 2.70))
    # Kombination mit Vergleichs-Praefix via Rekursion.
    assert csv_loaders.parse_range("∼ > 500") == (500.0, None)
    assert csv_loaders.parse_range("∼ < 100") == (None, 100.0)
    # Verkettet mit anderen Symbolic-Markern (verschiedene Marker-Kombinationen).
    assert csv_loaders.parse_range("∼~5.5 ± 0.3") == pytest.approx((5.2, 5.8))
    assert csv_loaders.parse_range("∼≈5.5") == (5.5, 5.5)
    assert csv_loaders.parse_range("≅∼5.5 ± 0.3") == pytest.approx((5.2, 5.8))
    assert csv_loaders.parse_range("~∼2.65(5)") == pytest.approx((2.60, 2.70))
    # Verkettet mit Wort-Praefix (rekursiv).
    assert csv_loaders.parse_range("∼ ca. 5.5 ± 0.3") == pytest.approx((5.2, 5.8))
    # Symbolischer Marker OHNE nachfolgende Zahl faellt still auf None.
    assert csv_loaders.parse_range("∼") == (None, None)
    # Regress-Anker: bereits unterstuetzte Symbole bleiben unveraendert.
    assert csv_loaders.parse_range("~5.5 ± 0.3") == pytest.approx((5.2, 5.8))
    assert csv_loaders.parse_range("≈5.5 ± 0.3") == pytest.approx((5.2, 5.8))
    assert csv_loaders.parse_range("≅5.5 ± 0.3") == pytest.approx((5.2, 5.8))
    assert csv_loaders.parse_range("≃5.5 ± 0.3") == pytest.approx((5.2, 5.8))
    # Regress-Anker: Werte OHNE Approximations-Praefix bleiben unveraendert.
    assert csv_loaders.parse_range("5.5") == (5.5, 5.5)
    assert csv_loaders.parse_range("5.5 ± 0.3") == pytest.approx((5.2, 5.8))
    assert csv_loaders.parse_range("2.65(5)") == pytest.approx((2.60, 2.70))


def test_parse_range_annaeherungs_praefix_fr_it():
    """FR-/IT-Annaeherungs-Marker (Suisse romande / Ticino / Val d'Aosta).

    ``vers`` (FR) und ``verso`` (IT) sind die Standard-Vokabeln fuer "gegen"/
    "um" einen Wert herum; ``environ`` (FR) fuer "ungefaehr"; ``attorno`` (IT)
    fuer "rund um". Semantisch identisch zu ``ca.``/``circa``/``etwa`` -
    Praefix wird gestrippt, die verbleibende Wert-Struktur laeuft in die
    normale Pipeline (Uncertainty-Match oder Fallback-Zahl-Suche). Spiegelt
    :func:`test_parse_iso_date_annaeherungs_praefix_fr_it` auf die Wert-Achse:
    ``_APPROX_VALUE_PREFIX`` in :mod:`stonebook.migration.csv_loaders` und
    ``_APPROX_PREFIX`` in :mod:`stonebook.migration.validators` teilen dieselbe
    FR/IT-Vokabel-Auswahl, damit ein FR-/IT-Sammler die Marker konsistent auf
    Datums- und Wert-Feldern einsetzen kann.
    """
    # FR: vers (= gegen/um) - Praefix vor reiner Zahl.
    assert csv_loaders.parse_range("vers 5.5") == (5.5, 5.5)
    assert csv_loaders.parse_range("vers 500") == (500.0, 500.0)
    # FR: environ (= ungefaehr) - Praefix vor reiner Zahl.
    assert csv_loaders.parse_range("environ 5.5") == (5.5, 5.5)
    assert csv_loaders.parse_range("environ 2.65") == (2.65, 2.65)
    # IT: verso (= gegen/um).
    assert csv_loaders.parse_range("verso 5.5") == (5.5, 5.5)
    assert csv_loaders.parse_range("verso 100") == (100.0, 100.0)
    # IT: attorno (= rund um) - bare Praefix-Form ohne Artikel.
    assert csv_loaders.parse_range("attorno 5.5") == (5.5, 5.5)
    assert csv_loaders.parse_range("attorno 2.65") == (2.65, 2.65)
    # Case-Insensitivitaet (spiegelt DE/EN-Praefixe).
    assert csv_loaders.parse_range("VERS 5.5") == (5.5, 5.5)
    assert csv_loaders.parse_range("Vers 5.5") == (5.5, 5.5)
    assert csv_loaders.parse_range("VERSO 5.5") == (5.5, 5.5)
    assert csv_loaders.parse_range("ENVIRON 5.5") == (5.5, 5.5)
    # FR/IT-Praefix + ±-Langform-Uncertainty (die publizierte Toleranz bleibt
    # nach dem Praefix-Strip als Bereichs-Grenzen erhalten - das ist der
    # eigentliche Nutzen des Praefix-Zweigs gegenueber der Fallback-Zahl-
    # Extraktion, die bei kombiniertem Praefix + Uncertainty die Toleranz
    # via inverted-Range-Kollaps stille verlieren wuerde).
    assert csv_loaders.parse_range("vers 5.5 ± 0.3") == pytest.approx((5.2, 5.8))
    assert csv_loaders.parse_range("environ 2.65 ± 0.05") == pytest.approx((2.60, 2.70))
    assert csv_loaders.parse_range("verso 5.5 ± 0.3") == pytest.approx((5.2, 5.8))
    assert csv_loaders.parse_range("attorno 100 ± 2") == pytest.approx((98.0, 102.0))
    # FR/IT-Praefix + IUCr-Kompakt-Uncertainty ``N(M)``.
    assert csv_loaders.parse_range("vers 5.5(3)") == pytest.approx((5.2, 5.8))
    assert csv_loaders.parse_range("environ 2.65(5)") == pytest.approx((2.60, 2.70))
    assert csv_loaders.parse_range("verso 100(2)") == pytest.approx((98.0, 102.0))
    # FR/IT-Praefix + Range-Notation (die Range-Grenzen laufen in die Fallback-
    # Zahl-Extraktion nach dem Praefix-Strip).
    assert csv_loaders.parse_range("vers 5.5-7.5") == (5.5, 7.5)
    assert csv_loaders.parse_range("environ 5.5 - 7.5") == (5.5, 7.5)
    assert csv_loaders.parse_range("verso 100-200") == (100.0, 200.0)
    # FR/IT-Praefix + DE-Komma-Dezimal-Locale (FR/IT-Sammler-Notizen aus einem
    # DE-/FR-/IT-Excel-Export nutzen ohnehin den Komma-Dezimal, weil sowohl
    # Suisse romande als auch Ticino/Val d'Aosta die Komma-Konvention teilen).
    assert csv_loaders.parse_range("environ 2,65") == (2.65, 2.65)
    assert csv_loaders.parse_range("vers 5,5 ± 0,3") == pytest.approx((5.2, 5.8))
    # Verkettung mit DE/EN-Praefix (die Rekursion loest die Praefixe
    # sequentiell auf - ein FR-/IT-Sammler in einer gemischten Notiz kann
    # beide Sprachen kombinieren, ohne dass die Praezisions-Angabe stille
    # auf die Fallback-Extraktion durchfaellt).
    assert csv_loaders.parse_range("vers ca. 5.5") == (5.5, 5.5)
    assert csv_loaders.parse_range("ca. vers 5.5") == (5.5, 5.5)
    assert csv_loaders.parse_range("environ approx 2.65 ± 0.05") == pytest.approx((2.60, 2.70))
    # Kein False-Positive fuer aehnlich beginnende Woerter - der Praefix muss
    # durch ``\s+`` vom Rest getrennt sein (spiegelt den identischen
    # Kollisions-Schutz aus :data:`stonebook.migration.validators._APPROX_PREFIX`
    # fuer die Wort-Fortsetzungen versichert/versa/environment/versoehnung/version).
    # Ohne den Whitespace-Anker wuerde die FR/IT-Vokabel in Freitext-Ausdruecken
    # als Praefix fehlgelesen und die eingebettete Zahl als Wert extrahiert.
    assert csv_loaders.parse_range("versichert 5.5") == (5.5, 5.5)
    assert csv_loaders.parse_range("versa 5.5") == (5.5, 5.5)
    assert csv_loaders.parse_range("versoehnung 5.5") == (5.5, 5.5)
    assert csv_loaders.parse_range("version 5.5") == (5.5, 5.5)
    assert csv_loaders.parse_range("environment 5.5") == (5.5, 5.5)
    assert csv_loaders.parse_range("environments 5.5") == (5.5, 5.5)
    # Ohne Wert-Rest fallen die reinen Marker still auf (None, None) - ohne
    # Zahl gibt es keinen Wert (spiegelt die "ca."/"circa"/"~"-Regress-Anker
    # aus :func:`test_parse_range_annaeherungs_praefix_mit_uncertainty`).
    assert csv_loaders.parse_range("vers") == (None, None)
    assert csv_loaders.parse_range("verso") == (None, None)
    assert csv_loaders.parse_range("environ") == (None, None)
    assert csv_loaders.parse_range("attorno") == (None, None)
    # Regress-Anker: bestehende DE/EN-Praefixe bleiben unveraendert.
    assert csv_loaders.parse_range("ca. 5.5") == (5.5, 5.5)
    assert csv_loaders.parse_range("circa 5.5") == (5.5, 5.5)
    assert csv_loaders.parse_range("etwa 5.5") == (5.5, 5.5)
    assert csv_loaders.parse_range("about 5.5") == (5.5, 5.5)


def test_parse_range_annaeherungs_praefix_hearsay():
    """Hearsay-/Zuschreibungs-Marker (DE ``angeblich`` sowie EN ``allegedly``/
    ``supposedly``/``reportedly``/``purportedly``) plus EN ``presumably`` als
    Leading-Annaeherungs-Praefix auf der Wert-Achse.

    Spiegelt strukturell die bereits in
    :data:`stonebook.migration.validators._APPROX_PREFIX` gepflegte Hearsay-
    Marker-Menge auf die Wert-Achse. In geerbten Sammlungs-Notizen, Museums-
    Etiketten und Auktions-Katalog-Provenienz-Eintraegen setzt der Vorbesitzer/
    Kurator/Auktionator den Hearsay-Marker vor die Wert-Angabe, wenn die
    Preis-/Gewichts-/Dichte-/Haerte-Aussage aus zweiter Hand kommt: "angeblich
    500 CHF Marktwert laut Vorbesitzer", "allegedly 500 CHF from the seller's
    estimate", "supposedly Mohs 7 per the old label", "reportedly 5.5 g weight
    from an unverified source", "purportedly a Mohs 8 hardness per the auction
    catalogue", "presumably 500 CHF Nachlassschaetzung".

    Vor dem Fix fielen alle Hearsay-Praefix-Formen still auf die Fallback-
    Zahl-Extraktion durch, weil sowohl :data:`_PLUS_MINUS_UNCERTAINTY` als auch
    :data:`_PARENTHESIS_UNCERTAINTY` per ``^\\s*(-?\\d ...)``-Anker eine reine
    Zahl am String-Anfang verlangen. Die publizierte Standard-Unsicherheit
    ging via ``[center, tol]``-inverted-Range-Kollaps ``(center, center)``
    still verloren - identischer Bug-Effekt wie bei ``"ca. 5.5 ± 0.3"`` vor
    Einfuehrung der uebrigen Approx-Marker in :data:`_APPROX_VALUE_PREFIX`.
    """
    # DE-Hearsay-Praefix + ±-Langform-Uncertainty. Der Praefix wird gestrippt,
    # die publizierte Toleranz laeuft in den _PLUS_MINUS_UNCERTAINTY-Zweig.
    assert csv_loaders.parse_range("angeblich 5.5 ± 0.3") == pytest.approx((5.2, 5.8))
    assert csv_loaders.parse_range("angeblich 500 ± 50") == pytest.approx((450.0, 550.0))
    assert csv_loaders.parse_range("angeblich 2.65 ± 0.05") == pytest.approx((2.60, 2.70))
    # EN-Hearsay-Praefix + ±-Langform-Uncertainty.
    assert csv_loaders.parse_range("allegedly 5.5 ± 0.3") == pytest.approx((5.2, 5.8))
    assert csv_loaders.parse_range("supposedly 5.5 ± 0.3") == pytest.approx((5.2, 5.8))
    assert csv_loaders.parse_range("reportedly 2.65 ± 0.05") == pytest.approx((2.60, 2.70))
    assert csv_loaders.parse_range("purportedly 100 ± 2") == pytest.approx((98.0, 102.0))
    # EN-Vermutungs-Marker ``presumably`` (bereits in
    # stonebook.migration.validators._APPROX_PREFIX gepflegt, jetzt symmetrisch
    # auf die Wert-Achse).
    assert csv_loaders.parse_range("presumably 5.5 ± 0.3") == pytest.approx((5.2, 5.8))
    assert csv_loaders.parse_range("presumably 500 ± 50") == pytest.approx((450.0, 550.0))
    # Case-Insensitivitaet (Excel-Autocorrect uppercase Anfang, gemischtes
    # Kanon, Caps-Lock aus Katalog-Import).
    assert csv_loaders.parse_range("Angeblich 5.5 ± 0.3") == pytest.approx((5.2, 5.8))
    assert csv_loaders.parse_range("ANGEBLICH 5.5 ± 0.3") == pytest.approx((5.2, 5.8))
    assert csv_loaders.parse_range("Allegedly 5.5 ± 0.3") == pytest.approx((5.2, 5.8))
    assert csv_loaders.parse_range("SUPPOSEDLY 5.5 ± 0.3") == pytest.approx((5.2, 5.8))
    assert csv_loaders.parse_range("Reportedly 2.65(5)") == pytest.approx((2.60, 2.70))
    # Hearsay-Praefix + IUCr-Kompakt-Uncertainty ``N(M)`` - der Praefix wird
    # gestrippt, die publizierte Toleranz laeuft in den
    # _PARENTHESIS_UNCERTAINTY-Zweig.
    assert csv_loaders.parse_range("angeblich 5.5(3)") == pytest.approx((5.2, 5.8))
    assert csv_loaders.parse_range("allegedly 2.65(5)") == pytest.approx((2.60, 2.70))
    assert csv_loaders.parse_range("reportedly 5.5(3)") == pytest.approx((5.2, 5.8))
    assert csv_loaders.parse_range("purportedly 100(2)") == pytest.approx((98.0, 102.0))
    assert csv_loaders.parse_range("supposedly 12.345(67)") == pytest.approx((12.278, 12.412))
    assert csv_loaders.parse_range("presumably 100(2)") == pytest.approx((98.0, 102.0))
    # Hearsay-Praefix + ASCII-Ersatzformen der Uncertainty-Struktur.
    assert csv_loaders.parse_range("angeblich 5.5 +/- 0.3") == pytest.approx((5.2, 5.8))
    assert csv_loaders.parse_range("allegedly 5.5+/-0.3") == pytest.approx((5.2, 5.8))
    assert csv_loaders.parse_range("supposedly 5.5+-0.3") == pytest.approx((5.2, 5.8))
    # Hearsay-Praefix + Uncertainty + Trailing-Einheit.
    assert csv_loaders.parse_range("angeblich 500 ± 50 CHF") == pytest.approx((450.0, 550.0))
    assert csv_loaders.parse_range("allegedly 500 ± 50 EUR") == pytest.approx((450.0, 550.0))
    assert csv_loaders.parse_range("reportedly 2.65 ± 0.05 g/cm³") == pytest.approx((2.60, 2.70))
    assert csv_loaders.parse_range("supposedly 5.5 ± 0.3 mm") == pytest.approx((5.2, 5.8))
    assert csv_loaders.parse_range("purportedly 5.5(3) Mohs") == pytest.approx((5.2, 5.8))
    # Hearsay-Praefix + DE-Komma-Dezimal-Locale.
    assert csv_loaders.parse_range("angeblich 2,65 ± 0,05") == pytest.approx((2.60, 2.70))
    assert csv_loaders.parse_range("allegedly 5,5 ± 0,3") == pytest.approx((5.2, 5.8))
    # Verkettung mit Leading-Waehrungs-Marker (die Rekursion loest die Praefixe
    # sequentiell auf - Hearsay-Marker + Waehrungs-Marker + Uncertainty).
    assert csv_loaders.parse_range("angeblich CHF 500 ± 50") == pytest.approx((450.0, 550.0))
    assert csv_loaders.parse_range("allegedly USD 500 ± 50") == pytest.approx((450.0, 550.0))
    assert csv_loaders.parse_range("reportedly EUR 500 ± 50") == pytest.approx((450.0, 550.0))
    # Verkettung mit Trailing-Approx-Suffix (die beidseitige Marker-Kombination
    # loest via Leading-Strip gefolgt vom Trailing-Strip in einer Rekursion auf).
    assert csv_loaders.parse_range("angeblich 500 ± 50, ca.") == pytest.approx((450.0, 550.0))
    assert csv_loaders.parse_range("allegedly 5.5 ± 0.3, ca.") == pytest.approx((5.2, 5.8))
    # Verkettung mit anderem Approx-Praefix (Rekursion loest beide sequentiell auf).
    assert csv_loaders.parse_range("angeblich ca. 5.5 ± 0.3") == pytest.approx((5.2, 5.8))
    assert csv_loaders.parse_range("allegedly circa 5.5 ± 0.3") == pytest.approx((5.2, 5.8))
    # Negatives Zentrum mit Hearsay-Praefix (Kryo-/Isotopen-Werte in
    # zweitrangigen Provenienz-Notizen).
    assert csv_loaders.parse_range("angeblich -1.5 ± 0.3") == pytest.approx((-1.8, -1.2))
    assert csv_loaders.parse_range("reportedly -2.65(5)") == pytest.approx((-2.70, -2.60))
    # Hearsay-Praefix + Range-Notation (die Range-Grenzen laufen in die
    # Fallback-Zahl-Extraktion nach dem Praefix-Strip).
    assert csv_loaders.parse_range("angeblich 5.5-7.5") == (5.5, 7.5)
    assert csv_loaders.parse_range("allegedly 5.5 - 7.5") == (5.5, 7.5)
    assert csv_loaders.parse_range("reportedly 100-200") == (100.0, 200.0)
    # Hearsay-Praefix vor reiner Zahl (ohne Uncertainty) - Praefix gestrippt,
    # reine Zahl-Extraktion laeuft weiter (Regress-Anker der Grund-Funktion).
    assert csv_loaders.parse_range("angeblich 500") == (500.0, 500.0)
    assert csv_loaders.parse_range("allegedly 500") == (500.0, 500.0)
    assert csv_loaders.parse_range("supposedly 500 CHF") == (500.0, 500.0)
    assert csv_loaders.parse_range("reportedly Mohs 7") == (7.0, 7.0)
    assert csv_loaders.parse_range("presumably 500 CHF") == (500.0, 500.0)
    # Ohne Wert-Rest fallen die reinen Marker still auf (None, None) - ohne
    # Zahl gibt es keinen Wert (spiegelt die "ca."/"circa"/"~"-Regress-Anker).
    assert csv_loaders.parse_range("angeblich") == (None, None)
    assert csv_loaders.parse_range("allegedly") == (None, None)
    assert csv_loaders.parse_range("supposedly") == (None, None)
    assert csv_loaders.parse_range("reportedly") == (None, None)
    assert csv_loaders.parse_range("purportedly") == (None, None)
    assert csv_loaders.parse_range("presumably") == (None, None)
    # Regress-Anker: bestehende DE/EN-/FR-/IT-Praefixe bleiben unveraendert.
    assert csv_loaders.parse_range("ca. 5.5 ± 0.3") == pytest.approx((5.2, 5.8))
    assert csv_loaders.parse_range("vermutlich 5.5 ± 0.3") == pytest.approx((5.2, 5.8))
    assert csv_loaders.parse_range("vers 5.5 ± 0.3") == pytest.approx((5.2, 5.8))
    assert csv_loaders.parse_range("verso 5.5 ± 0.3") == pytest.approx((5.2, 5.8))


def test_parse_range_trailing_annaeherungs_suffix():
    """Trailing Annaeherungs-Suffix auf der Wert-Achse (spiegelt Leading-Praefix).

    Deckt die in Sammler-Notizen sehr verbreitete Reihenfolge "Wert zuerst,
    Praezisions-Marker nachgeschoben" ab: ``5.5 ± 0.3, ca.`` / ``2.65(5) circa``
    / ``500 CHF geschaetzt``. Bei reinen Wert-Zellen ohne Uncertainty-Struktur
    ist der Suffix verlustfrei via Fallback (die Punkt-Range bleibt Punkt-Range,
    die Approximations-Semantik gehoert in die notizen-Spalte); kritisch ist
    die Kombination mit Uncertainty-Notation UND einem Komma-Trenner zwischen
    Wert-Ausdruck und Marker - die Uncertainty-Patterns absorbieren Trailing-
    Tokens ohne Komma als einheiten-aehnliche Fortsetzung, aber ein ``,`` bricht
    die Token-Kette und das End-Anker-Matching schlaegt fehl. Ohne Suffix-Strip
    fielen genau diese in Sammler-Notizen verbreiteten Formen (``"5.5 ± 0.3,
    ca."``, ``"2.65(5), circa"``) still auf ``(center, center)``-Kollaps und
    verloren die publizierte Toleranz - identischer Bug-Effekt wie in der
    Leading-Form vor Einfuehrung von :data:`_APPROX_VALUE_PREFIX`. Spiegelt
    strukturell :func:`test_parse_iso_date_trailing_annaeherungs_suffix` aus
    :mod:`stonebook.migration.validators` auf die Wert-Achse.
    """
    # Reine Wert-Zelle + Trailing-Marker: Suffix wird gestrippt, Fallback-Zahl-
    # Extraktion liefert die Punkt-Range (verlustfrei ohne Uncertainty).
    assert csv_loaders.parse_range("5.5 ca.") == (5.5, 5.5)
    assert csv_loaders.parse_range("5.5 circa") == (5.5, 5.5)
    assert csv_loaders.parse_range("500 approximately") == (500.0, 500.0)
    assert csv_loaders.parse_range("500 vermutlich") == (500.0, 500.0)
    assert csv_loaders.parse_range("500 geschaetzt") == (500.0, 500.0)
    assert csv_loaders.parse_range("500 ungefaehr") == (500.0, 500.0)
    assert csv_loaders.parse_range("500 estimated") == (500.0, 500.0)
    assert csv_loaders.parse_range("500 est.") == (500.0, 500.0)
    # Uncertainty + Trailing-Marker OHNE Komma-Trenner: die Uncertainty-Patterns
    # absorbieren "ca."/"circa"/etc. bereits ueber ihren Einheit-aehnlichen
    # Trailing-Token-Loop. Regress-Anker: die Toleranz bleibt erhalten.
    assert csv_loaders.parse_range("5.5 ± 0.3 ca.") == pytest.approx((5.2, 5.8))
    assert csv_loaders.parse_range("2.65(5) circa") == pytest.approx((2.60, 2.70))
    # Uncertainty + Komma-Trenner + Trailing-Marker: KRITISCHER Fix-Fall.
    # Ohne Suffix-Strip faellt der Komma-Trenner auf ``(center, center)``-
    # Kollaps zurueck und die Toleranz geht verloren.
    assert csv_loaders.parse_range("5.5 ± 0.3, ca.") == pytest.approx((5.2, 5.8))
    assert csv_loaders.parse_range("5.5(3), ca.") == pytest.approx((5.2, 5.8))
    assert csv_loaders.parse_range("2.65(5), circa") == pytest.approx((2.60, 2.70))
    assert csv_loaders.parse_range("100 ± 2, ungefaehr") == pytest.approx((98.0, 102.0))
    # Uncertainty + Einheit + Komma-Trenner + Trailing-Marker: haeufigste
    # Sammler-Notation aus mineralogischen Etiketten mit Nachtrag-Marker.
    assert csv_loaders.parse_range("2.65 ± 0.05 g/cm³, ca.") == pytest.approx((2.60, 2.70))
    assert csv_loaders.parse_range("2.65(5) g/cm³, circa") == pytest.approx((2.60, 2.70))
    assert csv_loaders.parse_range("5.5 ± 0.3 Mohs, geschaetzt") == pytest.approx((5.2, 5.8))
    # Case-Insensitivitaet (spiegelt _APPROX_VALUE_PREFIX-Konvention).
    assert csv_loaders.parse_range("5.5 CA.") == (5.5, 5.5)
    assert csv_loaders.parse_range("5.5 Circa") == (5.5, 5.5)
    assert csv_loaders.parse_range("500 GESCHAETZT") == (500.0, 500.0)
    assert csv_loaders.parse_range("500 Vermutlich") == (500.0, 500.0)
    # Leading + Trailing Marker in einer Rekursion: die beiden Strip-Zweige
    # verkettet, damit "ca. 5.5 ± 0.3, ca." (beidseitige Kombination) die
    # Toleranz behaelt.
    assert csv_loaders.parse_range("ca. 5.5 ± 0.3, ca.") == pytest.approx((5.2, 5.8))
    assert csv_loaders.parse_range("etwa 2.65(5), circa") == pytest.approx((2.60, 2.70))
    # DE-Komma-Dezimal-Locale mit Trailing-Marker (Excel-DE-Konvention).
    assert csv_loaders.parse_range("5,5 ± 0,3, ca.") == pytest.approx((5.2, 5.8))
    assert csv_loaders.parse_range("2,65 vermutlich") == (2.65, 2.65)
    # Range + Trailing-Marker (die Range-Grenzen bleiben nach dem Strip).
    assert csv_loaders.parse_range("3-5 vermutlich") == (3.0, 5.0)
    assert csv_loaders.parse_range("3.5-5.5 ca.") == (3.5, 5.5)
    assert csv_loaders.parse_range("100-200 geschaetzt") == (100.0, 200.0)
    # Kollisions-Schutz: aehnlich beginnende Woerter am Ende duerfen NICHT
    # als Marker gelesen werden - der Vollwort-Anker via ``[.,;:!?]?\s*$``
    # und die exakte Marker-Liste schuetzen vor Fehlmatches.
    assert csv_loaders.parse_range("5.5 estimator") == (5.5, 5.5)
    assert csv_loaders.parse_range("5.5 schaetzung") == (5.5, 5.5)
    assert csv_loaders.parse_range("5.5 essentially") == (5.5, 5.5)
    assert csv_loaders.parse_range("5.5 abouts") == (5.5, 5.5)
    # Marker MUSS am String-Ende stehen (nicht mitten im Freitext) - eine
    # Wort-Fortsetzung nach dem Marker verhindert den Suffix-Match, der
    # Wert bleibt via Fallback-Extraktion Punkt-Range.
    assert csv_loaders.parse_range("5 estimated Ref X") == (5.0, 5.0)
    assert csv_loaders.parse_range("5.5 ca. Ref Y") == (5.5, 5.5)
    # FR/IT-Praepositions-Marker (vers/environ/verso/attorno) sind absichtlich
    # NICHT im Trailing-Suffix - sie sind FR/IT-Praepositionen mit strikter
    # Position-vor-Wert-Semantik (spiegelt die _TRAILING_APPROX_SUFFIX-
    # Konvention aus validators.py, die dieselben Praepositions-Marker
    # ebenfalls ausschliesst). Regress-Anker: die Formen bleiben Punkt-Range
    # via Fallback.
    assert csv_loaders.parse_range("5.5 vers") == (5.5, 5.5)
    assert csv_loaders.parse_range("5.5 verso") == (5.5, 5.5)
    assert csv_loaders.parse_range("5.5 environ") == (5.5, 5.5)
    assert csv_loaders.parse_range("5.5 attorno") == (5.5, 5.5)
    # Regress-Anker: die bestehenden Leading-Praefix-Formen bleiben unveraendert.
    assert csv_loaders.parse_range("ca. 5.5") == (5.5, 5.5)
    assert csv_loaders.parse_range("circa 5.5") == (5.5, 5.5)
    assert csv_loaders.parse_range("etwa 5.5 ± 0.3") == pytest.approx((5.2, 5.8))
    # Regress-Anker: reine Wert-Zellen ohne Marker bleiben Punkt-Range.
    assert csv_loaders.parse_range("5.5") == (5.5, 5.5)
    assert csv_loaders.parse_range("500") == (500.0, 500.0)


def test_parse_range_trailing_annaeherungs_suffix_presumably():
    """Trailing ``presumably``-Suffix (EN-Wahrscheinlichkeits-/Vermutungs-Marker).

    Deckt die letzte Symmetrie-Luecke in :data:`_APPROX_VALUE_SUFFIX`: der
    Marker ``presumably`` war bereits in :data:`_APPROX_VALUE_PREFIX` (Leading-
    Achse), :data:`stonebook.migration.validators._APPROX_PREFIX` (Datums-
    Leading) und :data:`stonebook.migration.validators._TRAILING_APPROX_SUFFIX`
    (Datums-Trailing) gepflegt, fehlte aber in der Wert-Trailing-Achse -
    Sammler-Notation "Wert zuerst, EN-Vermutungs-Marker nachgeschoben" mit
    Komma-Trenner (``"5.5 ± 0.3, presumably"``) fiel still auf den
    ``(center, center)``-Kollaps und verlor die publizierte Toleranz.
    Semantisch identisch zu ``possibly``/``perhaps``/``maybe`` (bereits in der
    Menge) und zu den DE-Aequivalenten ``vermutlich``/``wahrscheinlich``. Der
    Fix schliesst die letzte Achse, damit die vier Marker-Mengen
    (Datums-Leading/-Trailing, Wert-Leading/-Trailing) lexikalisch identisch
    sind.
    """
    # Uncertainty + Komma-Trenner + Trailing ``presumably``: der Fix-Fall.
    assert csv_loaders.parse_range("5.5 ± 0.3, presumably") == pytest.approx((5.2, 5.8))
    assert csv_loaders.parse_range("5.5(3), presumably") == pytest.approx((5.2, 5.8))
    assert csv_loaders.parse_range("2.65(5), presumably") == pytest.approx((2.60, 2.70))
    assert csv_loaders.parse_range("100 ± 2, presumably") == pytest.approx((98.0, 102.0))
    # Uncertainty + Einheit + Komma-Trenner + Trailing ``presumably``.
    assert csv_loaders.parse_range("2.65 ± 0.05 g/cm³, presumably") == pytest.approx((2.60, 2.70))
    assert csv_loaders.parse_range("5.5 ± 0.3 Mohs, presumably") == pytest.approx((5.2, 5.8))
    assert csv_loaders.parse_range("500 ± 50 CHF, presumably") == pytest.approx((450.0, 550.0))
    # Reine Wert-Zelle + Trailing ``presumably`` (verlustfrei via Fallback).
    assert csv_loaders.parse_range("500 presumably") == (500.0, 500.0)
    assert csv_loaders.parse_range("500 presumably.") == (500.0, 500.0)
    assert csv_loaders.parse_range("5.5 presumably") == (5.5, 5.5)
    # Case-Insensitivitaet (spiegelt die restliche Marker-Menge).
    assert csv_loaders.parse_range("5.5 ± 0.3, PRESUMABLY") == pytest.approx((5.2, 5.8))
    assert csv_loaders.parse_range("5.5 ± 0.3, Presumably") == pytest.approx((5.2, 5.8))
    # Leading + Trailing ``presumably`` in einer Rekursion.
    assert csv_loaders.parse_range("ca. 5.5 ± 0.3, presumably") == pytest.approx((5.2, 5.8))
    assert csv_loaders.parse_range("presumably 5.5 ± 0.3, presumably") == pytest.approx((5.2, 5.8))
    assert csv_loaders.parse_range("etwa 2.65(5), presumably") == pytest.approx((2.60, 2.70))
    # DE-Komma-Dezimal-Locale + Trailing ``presumably``.
    assert csv_loaders.parse_range("5,5 ± 0,3, presumably") == pytest.approx((5.2, 5.8))
    # Range + Trailing ``presumably`` (die Range-Grenzen bleiben nach dem Strip).
    assert csv_loaders.parse_range("3-5 presumably") == (3.0, 5.0)
    assert csv_loaders.parse_range("100-200 presumably") == (100.0, 200.0)
    # Kollisions-Schutz: aehnlich beginnende Woerter am Ende sind KEINE
    # Marker (Vollwort-Anker via ``[.,;:!?]?\s*$``).
    assert csv_loaders.parse_range("5.5 presuming") == (5.5, 5.5)
    assert csv_loaders.parse_range("5.5 presume") == (5.5, 5.5)
    assert csv_loaders.parse_range("5.5 presumptuous") == (5.5, 5.5)
    # Regress-Anker: bereits gepflegte Trailing-Marker bleiben unveraendert
    # (der Fix ist rein additiv).
    assert csv_loaders.parse_range("5.5 ± 0.3, possibly") == pytest.approx((5.2, 5.8))
    assert csv_loaders.parse_range("5.5 ± 0.3, vermutlich") == pytest.approx((5.2, 5.8))
    assert csv_loaders.parse_range("5.5 ± 0.3, ca.") == pytest.approx((5.2, 5.8))
    # Regress-Anker: die bereits gepflegte Leading-``presumably``-Form
    # (aus :data:`_APPROX_VALUE_PREFIX`) bleibt unveraendert.
    assert csv_loaders.parse_range("presumably 5.5") == (5.5, 5.5)
    assert csv_loaders.parse_range("presumably 5.5 ± 0.3") == pytest.approx((5.2, 5.8))


def test_read_ids_from_file_basisformen(tmp_path):
    """Regress-Anker: Kommentare/Leerzeilen/Inline-Kommentare/Trim.

    Deckt die bisher nur implizit ueber die csv_cli-/docx_cli-End-to-End-
    Tests abgedeckte Verzweigungslogik des Helpers auf der Direkt-Ebene
    ab, damit ein Regress in :func:`read_ids_from_file` sofort dort
    sichtbar wird und nicht erst als CLI-Fehlermeldung ("Ungueltige
    Objekt-ID") auftaucht - die eigentliche Ursache (Datei-Parsing)
    wuerde sonst in der Fehlerkette versteckt bleiben.
    """
    p = tmp_path / "ids.txt"
    p.write_text(
        "# Erste Charge - Kommentar am Zeilenanfang wird uebersprungen\n"
        "OBJ_0001\n"
        "\n"                                # Leerzeile
        "  OBJ-43   # inline-Kommentar\n"   # inline-Kommentar wird gestrippt
        "Objekt 3\n"
        "   \n"                             # nur Whitespace = leer
        "  # eingerueckter Kommentar\n"
        "3\n",
        encoding="utf-8",
    )
    # Rohwerte in Datei-Reihenfolge, keine Normalisierung (obliegt Caller).
    assert read_ids_from_file(p) == ["OBJ_0001", "OBJ-43", "Objekt 3", "3"]


def test_read_ids_from_file_utf8_bom_wird_gestrippt(tmp_path):
    """Windows-Notepad-Default-Encoding UTF-8-BOM darf die erste ID nicht kaputt machen.

    Notepad und VS Code auf Windows schreiben bei "Save As" mit UTF-8-
    Default ein fuehrendes BOM (``EF BB BF``, U+FEFF). Ohne den Strip
    wuerde das erste Zeichen der ersten ID zum U+FEFF-Praefix und
    :func:`normalize_id` liefert None fuer ``﻿OBJ_0001``, sodass
    der Sammler-Workflow "IDs in Notepad tippen -> Speichern ->
    ``--ids-from-file`` uebergeben" mit einer kryptischen
    "Ungueltige Objekt-ID"-Meldung crasht statt die Liste einzulesen.
    Fix: ``encoding='utf-8-sig'`` strippt das BOM transparent (ohne
    Effekt auf Dateien ohne BOM).
    """
    p = tmp_path / "ids_bom.txt"
    p.write_bytes(b"\xef\xbb\xbfOBJ_0001\nOBJ_0002\n")
    # Vor dem Fix wuerde die erste ID mit U+FEFF beginnen - siehe die
    # Regress-Assertion darunter.
    result = read_ids_from_file(p)
    assert result == ["OBJ_0001", "OBJ_0002"]
    assert not result[0].startswith("﻿")


def test_read_ids_from_file_ohne_bom_bleibt_unveraendert(tmp_path):
    """Regress-Anker: Dateien ohne BOM werden identisch zu vorher gelesen.

    ``utf-8-sig`` verhaelt sich fuer Dateien ohne fuehrendes BOM exakt
    wie ``utf-8``; dieser Test verankert das Verhalten, damit ein
    Regress im Encoding-Handling (versehentliches Strip von Byte-
    Sequenzen, die zufaellig aussehen wie ein BOM) sichtbar wird.
    """
    p = tmp_path / "ids_plain.txt"
    p.write_bytes(b"OBJ_0001\nOBJ_0002\n")
    assert read_ids_from_file(p) == ["OBJ_0001", "OBJ_0002"]


def test_read_ids_from_file_fehlend_liefert_none(tmp_path):
    """Nicht vorhandene Datei -> None (Aufrufer entscheidet ueber Meldung)."""
    assert read_ids_from_file(tmp_path / "fehlt.txt") is None


def test_read_ids_from_file_nicht_utf8_liefert_none(tmp_path):
    """UTF-16-/latin1-/binary-Dateien fallen auf None statt zu crashen.

    Excel-CSV-Export mit UTF-16-LE-Encoding oder ein cp1252-Fallback aus
    einem alten Editor sind reale Sammler-Faelle; ohne den
    UnicodeDecodeError-Fang wuerde die CLI abstuerzen statt eine
    verstaendliche "ID-Datei nicht lesbar"-Meldung auszugeben (der
    Aufrufer bildet den None-Rueckgabewert auf die Nutzer-Meldung ab).
    """
    p = tmp_path / "utf16.txt"
    p.write_text("OBJ_0001\nOBJ_0002\n", encoding="utf-16")
    assert read_ids_from_file(p) is None


def test_parse_range_einseitige_vergleichs_grenze():
    """Einseitige Vergleichs-Grenze (``<``/``>``/``<=``/``>=``/``≤``/``≥``)
    am Wert-Anfang wird als offene Range-Grenze geparst.

    Sammler-Notizen und publizierte Referenz-Tabellen nutzen die Ein-Seiten-
    Vergleichs-Notation regelmaessig fuer unsicher bestimmte Bereichsgrenzen:

    * ``"Mohs > 7"`` bei einem Stueck, das Quarz ritzt (aber die exakte
      Haerte nicht bestimmt wurde) -> Mohs_Haerte_min=7, Mohs_Haerte_max=NULL
    * ``"Dichte < 3"`` fuer ein leichteres Mineral ohne exakte Massendichte
      -> Dichte_min_gcm3=NULL, Dichte_max_gcm3=3
    * ``"Wert >= 500 CHF"`` fuer eine Mindest-Schaetzung ohne feste Obergrenze
      -> nur untere Wert-Grenze gesetzt

    Vor dem Fix fielen alle diese Formen still auf die Fallback-Zahl-Extraktion
    durch, die den Vergleichs-Marker ignorierte und den nackten Wert als
    Punkt-Range ``(5.0, 5.0)`` lieferte - die publizierte Ein-Seiten-Semantik
    ging stille verloren und die Migration schrieb Mohs_Haerte_min=5 UND
    Mohs_Haerte_max=5 statt der korrekten Ein-Seiten-Setzung mit NULL an der
    gegenueberliegenden Grenze (spiegelt die NULL-an-Ende-Konvention der
    _min/_max-Sortier-/Filter-Achsen aus dem Repository).

    Marker-Menge deckt beide ASCII-Formen (``<``/``>``, ``<=``/``>=``) und
    beide Unicode-Aequivalente (``≤`` U+2264 "less-than or equal to", ``≥``
    U+2265 "greater-than or equal to") ab. ASCII-Formen sind der Standard aus
    Terminal-/E-Mail-/LaTeX-Roh-Notizen und aus 7-bit-CSV-Exporten; Unicode-
    Formen sind der Standard aus DOCX-/PDF-/Print-Publikationen mit
    Autoformat-Konvertierung und aus mathematischen Referenz-Tabellen. Die
    Gleich-Varianten (``<=``/``≤``/``>=``/``≥``) liefern semantisch denselben
    Range wie ``<``/``>`` (die Bereichs-Grenzen sind in dieser Anwendung
    ohnehin inklusiv gemeint, weil DB-Filter ``Mohs_Haerte_max >= X`` und
    ``Mohs_Haerte_max <= X`` als geschlossene Intervalle geschrieben sind).
    """
    # Nur-``<``-Marker: obere Grenze, untere bleibt None.
    assert csv_loaders.parse_range("< 5") == (None, 5.0)
    assert csv_loaders.parse_range("<5") == (None, 5.0)
    assert csv_loaders.parse_range("< 5.5") == (None, 5.5)
    assert csv_loaders.parse_range("< 100") == (None, 100.0)
    # Nur-``>``-Marker: untere Grenze, obere bleibt None.
    assert csv_loaders.parse_range("> 5") == (5.0, None)
    assert csv_loaders.parse_range(">5") == (5.0, None)
    assert csv_loaders.parse_range("> 7.0") == (7.0, None)
    assert csv_loaders.parse_range("> 500") == (500.0, None)
    # ``<=`` / ``>=``: identische Semantik wie ``<`` / ``>``.
    assert csv_loaders.parse_range("<= 5") == (None, 5.0)
    assert csv_loaders.parse_range("<=5") == (None, 5.0)
    assert csv_loaders.parse_range(">= 5") == (5.0, None)
    assert csv_loaders.parse_range(">=5") == (5.0, None)
    # Unicode-Vergleichs-Zeichen ``≤`` (U+2264) und ``≥`` (U+2265).
    assert csv_loaders.parse_range("≤ 5") == (None, 5.0)
    assert csv_loaders.parse_range("≤5") == (None, 5.0)
    assert csv_loaders.parse_range("≥ 5") == (5.0, None)
    assert csv_loaders.parse_range("≥5") == (5.0, None)
    # Komma-Dezimal-Locale (DE/EU-CSV-Excel-Export) wird durch die
    # bestehende ``normalize_numeric_locale``-Preprocessing-Stufe abgedeckt;
    # der Vergleichs-Marker greift auf die bereits normalisierte Dezimal-Form.
    assert csv_loaders.parse_range("< 5,5") == (None, 5.5)
    assert csv_loaders.parse_range(">= 2,65") == (2.65, None)
    # Vergleichs-Marker vor negativer Zahl: der Marker konsumiert den Praefix,
    # die Rekursion parst die negative Zahl korrekt.
    assert csv_loaders.parse_range("> -5") == (-5.0, None)
    assert csv_loaders.parse_range("< -1.5") == (None, -1.5)
    # Kombination mit dem Approximations-Praefix: ``< ca. 5`` wird als
    # "obere Grenze 5, ungefaehr" gelesen. Der Vergleichs-Zweig ist NACH dem
    # _APPROX_VALUE_PREFIX-Strip einsortiert, damit "obere Grenze ca 5"
    # transparent auf (None, 5.0) rekursiert.
    assert csv_loaders.parse_range("< ca. 5") == (None, 5.0)
    assert csv_loaders.parse_range(">= etwa 500") == (500.0, None)
    # Kombination mit wissenschaftlicher Notation: der Vergleichs-Marker
    # konsumiert den Praefix, die Rekursion parst die Zehnerpotenz.
    assert csv_loaders.parse_range("< 1e3") == (None, 1000.0)
    assert csv_loaders.parse_range(">= 2.5e-3") == (0.0025, None)
    # Bestandsverhalten unveraendert: reine Zahlen liefern Punkt-Range
    # (5.0, 5.0), Bereiche (5.0, 7.0), leere Eingaben (None, None).
    assert csv_loaders.parse_range("5") == (5.0, 5.0)
    assert csv_loaders.parse_range("5-7") == (5.0, 7.0)
    assert csv_loaders.parse_range("") == (None, None)


def test_parse_range_einseitige_wort_vergleichs_grenze():
    """Wort-basierte einseitige Vergleichs-Grenze am Wert-Anfang wird als
    offene Range-Grenze geparst - Naturssprachige Kurzform der ``<``/``>``/
    ``<=``/``>=``-Marker aus :func:`test_parse_range_einseitige_vergleichs_grenze`.

    Sammler-Notizen und Auktions-/Katalog-Texte nutzen die natur-sprachige
    Kurzform der Vergleichs-Marker ebenso verbreitet wie die mathematische
    Notation - eine Wert-Zelle "mindestens 500 CHF" oder "bis 500 CHF" ist
    in der deutsch-sprachigen Katalog-Praxis (Auktions-Angebote, Boersen-
    Preise, Erbschafts-Schaetzungen) weit haeufiger als die Kompakt-Form
    "> 500" bzw. "< 500". Vor dem Fix fielen alle diese Formen still auf
    die Fallback-Zahl-Extraktion durch: der Wort-Marker wurde als Freitext
    gelesen und der nackte Wert als Punkt-Range (5.0, 5.0) geliefert - die
    publizierte Ein-Seiten-Semantik ging stille verloren und die Migration
    schrieb Mohs_Haerte_min=5 UND Mohs_Haerte_max=5 statt der korrekten
    Ein-Seiten-Setzung mit NULL an der gegenueberliegenden Grenze.

    Marker-Menge (Anspruch: die in Sammler-Notizen und Katalog-Texten
    praxisrelevanten Formen, keine kreativen Freitext-Varianten):

    Untere Grenze (>=): DE mindestens / mind. / min. / wenigstens /
    zumindest / ab; EN at least / from.

    Obere Grenze (<=): DE hoechstens / höchstens / maximal / max. /
    bis zu / bis; EN at most / up to.
    """
    # Untere Grenze (>=): alle DE-/EN-Formen mappen auf (Wert, None).
    assert csv_loaders.parse_range("mindestens 5") == (5.0, None)
    assert csv_loaders.parse_range("mind. 5") == (5.0, None)
    assert csv_loaders.parse_range("min. 5") == (5.0, None)
    assert csv_loaders.parse_range("wenigstens 5") == (5.0, None)
    assert csv_loaders.parse_range("zumindest 5") == (5.0, None)
    assert csv_loaders.parse_range("ab 5") == (5.0, None)
    assert csv_loaders.parse_range("at least 5") == (5.0, None)
    assert csv_loaders.parse_range("from 5") == (5.0, None)
    # Obere Grenze (<=): alle DE-/EN-Formen mappen auf (None, Wert).
    assert csv_loaders.parse_range("hoechstens 5") == (None, 5.0)
    assert csv_loaders.parse_range("höchstens 5") == (None, 5.0)
    assert csv_loaders.parse_range("maximal 5") == (None, 5.0)
    assert csv_loaders.parse_range("max. 5") == (None, 5.0)
    assert csv_loaders.parse_range("bis 5") == (None, 5.0)
    assert csv_loaders.parse_range("bis zu 5") == (None, 5.0)
    assert csv_loaders.parse_range("at most 5") == (None, 5.0)
    assert csv_loaders.parse_range("up to 5") == (None, 5.0)
    # Case-Insensitivitaet: die :data:`_COMPARISON_WORD_LOWER` /
    # :data:`_COMPARISON_WORD_UPPER` Patterns sind mit ``re.IGNORECASE``
    # kompiliert, damit Excel-Autocorrect ("Mindestens") oder Fliesstext-
    # Notation ("MINDESTENS", "At Least") transparent gelesen wird.
    assert csv_loaders.parse_range("MINDESTENS 5") == (5.0, None)
    assert csv_loaders.parse_range("Mindestens 5") == (5.0, None)
    assert csv_loaders.parse_range("At Least 5") == (5.0, None)
    assert csv_loaders.parse_range("UP TO 5") == (None, 5.0)
    # Dezimal-Zahlen und DE-Komma-Dezimal-Locale nach Praefix-Strip.
    assert csv_loaders.parse_range("mindestens 5.5") == (5.5, None)
    assert csv_loaders.parse_range("mindestens 5,5") == (5.5, None)
    assert csv_loaders.parse_range("ab 2,65") == (2.65, None)
    assert csv_loaders.parse_range("bis 100 mg") == (None, 100.0)
    # Wert-Feld-Praxis (Wert_min/_max-Grenze aus Auktions-/Boersen-Texten):
    # DE-Tausendertrenner werden durch die bestehende
    # ``normalize_numeric_locale``-Preprocessing-Stufe abgedeckt.
    assert csv_loaders.parse_range("ab 500 CHF") == (500.0, None)
    assert csv_loaders.parse_range("bis 500 CHF") == (None, 500.0)
    assert csv_loaders.parse_range("ab 1.500,00 CHF") == (1500.0, None)
    # Kombination mit dem Approximations-Praefix (``ca.``/``etwa``): der
    # Wort-Marker konsumiert den Praefix, die Rekursion konsumiert die
    # Approximation, das Endresultat behaelt die Ein-Seiten-Semantik.
    assert csv_loaders.parse_range("mindestens ca. 5") == (5.0, None)
    assert csv_loaders.parse_range("bis etwa 500") == (None, 500.0)
    # Kombination mit dem Zeichen-Vergleichs-Marker: ``mindestens > 5``
    # (redundante Notation aus Sammler-Notizen) wird verlustfrei geparst -
    # der Wort-Marker konsumiert das Wort, die Rekursion konsumiert das
    # ``>`` und liefert (5.0, None); die Wort-Interpretation "untere Grenze"
    # ist identisch zur ``>``-Interpretation, sodass beide Marker konsistent
    # dieselbe Grenze setzen.
    assert csv_loaders.parse_range("mindestens > 5") == (5.0, None)
    assert csv_loaders.parse_range("hoechstens < 5") == (None, 5.0)
    # Kombination mit Uncertainty-Notation: der Wort-Marker konsumiert das
    # Wort, die Rekursion parst die Toleranz-Struktur. "mindestens 5.5 ±
    # 0.3" liefert (5.2, None): die untere Toleranz-Grenze wird als
    # konservative Untergrenze uebernommen (spiegelt _COMPARISON_PREFIX's
    # Uncertainty-Kompatibilitaet).
    assert csv_loaders.parse_range("mindestens 5.5 ± 0.3") == pytest.approx((5.2, None))
    # Negative Werte (thermodynamische Kontexte): ``ab -5`` liefert
    # (-5.0, None), ``bis -5`` liefert (None, -5.0). Der Wort-Marker
    # konsumiert das Wort, die Rekursion parst die negative Zahl.
    assert csv_loaders.parse_range("ab -5") == (-5.0, None)
    assert csv_loaders.parse_range("bis -5") == (None, -5.0)
    assert csv_loaders.parse_range("mindestens -1.5") == (-1.5, None)
    # Kollisions-Schutz: der Wort-Marker greift NUR am String-Anfang mit
    # obligatorischem Whitespace nach dem Marker. Wort-Fortsetzungen
    # (``abmessungen``, ``bislang``, ``maximaler``) haben KEIN Whitespace
    # nach dem Marker-Anfangs-Prefix und fallen auf die Standard-Zahl-
    # Extraktion durch (Punkt-Range).
    assert csv_loaders.parse_range("abmessungen 5") == (5.0, 5.0)
    assert csv_loaders.parse_range("bislang 5") == (5.0, 5.0)
    assert csv_loaders.parse_range("maximaler 5") == (5.0, 5.0)
    # Kollisions-Schutz: ``bis`` zwischen zwei Zahlen bleibt als Range-
    # Separator erhalten, weil der Praefix-Anker den Wort-Marker NUR am
    # String-Anfang akzeptiert - ``3 bis 5`` matcht NICHT (die ``3`` steht
    # vorne). Spiegelt die etablierte Range-Separator-Behandlung.
    assert csv_loaders.parse_range("3 bis 5") == (3.0, 5.0)
    assert csv_loaders.parse_range("3 to 5") == (3.0, 5.0)
    # Leere Fortsetzung: nur der Wort-Marker ohne Zahl faellt zurueck auf
    # (None, None) - der Wort-Match verlangt ``\s+`` nach dem Marker,
    # sodass ohne Zahl der Match nicht greift und die generische Zahl-
    # Extraktion auf leere Eingabe (None, None) liefert.
    assert csv_loaders.parse_range("mindestens") == (None, None)
    assert csv_loaders.parse_range("bis") == (None, None)
    # Bestandsverhalten unveraendert: reine Zahlen, Bereiche, leere Eingabe.
    assert csv_loaders.parse_range("5") == (5.0, 5.0)
    assert csv_loaders.parse_range("5-7") == (5.0, 7.0)
    assert csv_loaders.parse_range("") == (None, None)


def test_parse_range_einseitige_wort_vergleichs_grenze_strikt():
    """Strikte Vergleichs-Wort-Marker (``ueber``/``über``/``mehr als``/``over``/
    ``above``/``more than``/``greater than`` fuer die untere Grenze, ``unter``/
    ``unterhalb``/``weniger als``/``under``/``below``/``less than`` fuer die
    obere Grenze) werden als offene Range-Grenze geparst - Ergaenzung zu den
    nicht-strikten Formen aus :func:`test_parse_range_einseitige_wort_vergleichs_grenze`.

    Sammler-Notizen aus Auktions-/Boersen-Katalogen (Christie's, Bonhams,
    "Rocks & Minerals") und geerbten Erbschafts-Schaetzungen verwenden die
    strikte Notation (``ueber 500 CHF``, ``mehr als 500 EUR``, ``over $500``)
    in Fluchtklauseln ("Mindestwert nicht bekannt, aber ueber 500") und
    in Preis-Erwartungen ("erwartet ueber 500"). Die untere-strikte Form
    kommt in geerbten Sammlungen aus dem D-A-CH-Raum sehr haeufig vor;
    die obere-strikte Form ("unter 500", ``below $500``) taucht in
    Angebot-Grenzen ("bevorzugt unter 500") und in Fund-Etiketten mit
    Wertschaetzungen der Vorbesitzer auf.

    Die strikte (>) vs. nicht-strikte (>=) Unterscheidung wird nicht in den
    Range-Grenzen erhalten - der interne Container kennt nur offene/
    geschlossene Grenzen, und die praxisrelevante Frage ist "welche Seite
    ist unbekannt?", nicht "ist der Grenzwert selbst enthalten?". Spiegelt
    die identische Vereinfachung in :data:`_COMPARISON_PREFIX`, wo ``<`` und
    ``<=`` bereits identisch auf die obere-Grenze-offen abgebildet werden.
    """
    # Untere Grenze (>): DE-Formen mappen auf (Wert, None).
    assert csv_loaders.parse_range("ueber 500") == (500.0, None)
    assert csv_loaders.parse_range("über 500") == (500.0, None)
    assert csv_loaders.parse_range("mehr als 500") == (500.0, None)
    assert csv_loaders.parse_range("oberhalb 500") == (500.0, None)
    # Untere Grenze (>): EN-Formen mappen auf (Wert, None).
    assert csv_loaders.parse_range("over 500") == (500.0, None)
    assert csv_loaders.parse_range("above 500") == (500.0, None)
    assert csv_loaders.parse_range("more than 500") == (500.0, None)
    assert csv_loaders.parse_range("greater than 500") == (500.0, None)
    # Obere Grenze (<): DE-Formen mappen auf (None, Wert).
    assert csv_loaders.parse_range("unter 500") == (None, 500.0)
    assert csv_loaders.parse_range("unterhalb 500") == (None, 500.0)
    assert csv_loaders.parse_range("weniger als 500") == (None, 500.0)
    # Obere Grenze (<): EN-Formen mappen auf (None, Wert).
    assert csv_loaders.parse_range("under 500") == (None, 500.0)
    assert csv_loaders.parse_range("below 500") == (None, 500.0)
    assert csv_loaders.parse_range("less than 500") == (None, 500.0)
    # Case-Insensitivitaet (Excel-Autocorrect, Fliesstext-Titel):
    assert csv_loaders.parse_range("UEBER 500") == (500.0, None)
    assert csv_loaders.parse_range("Mehr Als 500") == (500.0, None)
    assert csv_loaders.parse_range("OVER 500") == (500.0, None)
    assert csv_loaders.parse_range("Less Than 500") == (None, 500.0)
    # Kombination mit Waehrungs-Praefix (Auktions-Katalog-Notation):
    assert csv_loaders.parse_range("ueber CHF 500") == (500.0, None)
    assert csv_loaders.parse_range("mehr als 500 CHF") == (500.0, None)
    assert csv_loaders.parse_range("over $500") == (500.0, None)
    assert csv_loaders.parse_range("under 500 EUR") == (None, 500.0)
    # Dezimal-Zahlen mit DE-Komma-Locale:
    assert csv_loaders.parse_range("ueber 2,65") == (2.65, None)
    assert csv_loaders.parse_range("under 2.5") == (None, 2.5)
    # Negative Werte (thermodynamische Kontexte):
    assert csv_loaders.parse_range("ueber -5") == (-5.0, None)
    assert csv_loaders.parse_range("unter -5") == (None, -5.0)
    # Kollisions-Schutz: Wort-Fortsetzungen ohne Whitespace nach dem Marker-
    # Anfang fallen auf die Standard-Zahl-Extraktion durch (Punkt-Range).
    # ``overall``/``override``/``underneath``/``understanding``/``unterschiedlich``/
    # ``ueberall``/``oberflaeche`` haben KEIN Whitespace nach dem Marker-Prefix
    # und werden korrekt NICHT als Vergleichs-Marker interpretiert.
    assert csv_loaders.parse_range("overall 500") == (500.0, 500.0)
    assert csv_loaders.parse_range("override 500") == (500.0, 500.0)
    assert csv_loaders.parse_range("underneath 500") == (500.0, 500.0)
    assert csv_loaders.parse_range("understanding 500") == (500.0, 500.0)
    assert csv_loaders.parse_range("unterschiedlich 500") == (500.0, 500.0)
    assert csv_loaders.parse_range("ueberall 500") == (500.0, 500.0)
    assert csv_loaders.parse_range("oberflaeche 500") == (500.0, 500.0)
    # Kollisions-Schutz: die Marker greifen NUR am String-Anfang. Zwischen
    # zwei Zahlen bleiben "ueber"/"unter"/"over"/"under" als Freitext, die
    # Fallback-Zahl-Extraktion nimmt die erste/letzte Zahl.
    assert csv_loaders.parse_range("3 ueber 5") == (3.0, 5.0)
    assert csv_loaders.parse_range("3 under 5") == (3.0, 5.0)
    # Leere Fortsetzung: nur Marker ohne Zahl faellt zurueck auf (None, None).
    assert csv_loaders.parse_range("ueber") == (None, None)
    assert csv_loaders.parse_range("under") == (None, None)


def test_parse_range_range_starter_wort_dual_use():
    """``from``/``ab`` sind in natuerlicher Sprache doppelt genutzt: entweder
    als "at least"-Ein-Seiten-Marker (``from 5`` / ``ab 500 CHF``) oder als
    Range-Start-Wort in Kombination mit einem folgenden Range-Separator
    (``from 5 to 7`` / ``ab 5 bis 7`` / ``ab 5-7`` / ``from 500 to 700 CHF``).
    Die Auswertung unterscheidet die beiden Faelle rein syntaktisch anhand
    des Range-Separators im Rest-Segment: bei ``to``/``bis`` bzw. Ziffern-
    Bindestrich (ASCII-``-`` oder Unicode-``–``/``—``/``−`` zwischen Zahlen)
    im ``rest`` wird die Range-Semantik uebernommen; ohne Separator die
    etablierte Ein-Seiten-Semantik.

    Vor dem Fix kollabierten alle Range-Formen still auf die Ein-Seiten-
    Interpretation - der Wort-Marker konsumierte die erste Zahl als
    "at least"-Wert, die Rekursion parste den Rest (``to 7`` / ``bis 7``)
    und die auf ``(lo, None)`` mappende Ein-Seiten-Setzung verwarf die
    obere Bereichsgrenze silent:

    * ``"from 5 to 7"``       -> (5, None)  (obere Grenze 7 verloren)
    * ``"ab 5 bis 7"``        -> (5, None)  (dito, DE-Konvention)
    * ``"ab 5-7"``            -> (5, None)  (Ziffern-Bindestrich verloren)
    * ``"from 500 to 700 CHF"`` -> (500, None)  (Wert-Range zerbrochen)

    Sammler-Notation aus Auktions-/Boersen-Katalogen und Erbschafts-
    Schaetzungen verwendet die ``von X bis Y``/``from X to Y``-Range-
    Konvention regelmaessig fuer Preis-Erwartungen ("erwartet from 500
    to 700 CHF"), fuer Wert-Bereichs-Angaben ("Nachlassschaetzung ab
    500 bis 700 EUR") und fuer physikalische Bereichs-Grenzen ("Haerte
    from 5 to 7 Mohs", "Dichte ab 2.6 bis 2.8 g/cm³") - beide Grenzen
    sind publiziert, die Range-Erhaltung ist fuer die Sortier-/Filter-
    Ebene der Range-Felder (Mohs_min/_max, Dichte_min/_max_gcm3,
    Wert_CHF_*) essenziell.

    Die Auswertung ist auf :data:`_RANGE_STARTER_WORDS` (``from``, ``ab``)
    beschraenkt und laesst alle uebrigen Wort-Marker (``mindestens``,
    ``at least``, ``ueber``, ``mehr als``, ``greater than``, ``over``,
    ``above``, ``oberhalb``, ``wenigstens``, ``zumindest``, ``min.``,
    ``mind.``) bei ihrer strikten Ein-Seiten-Semantik - diese Marker sind
    in natuerlicher Sprache eindeutig "at least"-Marker (``at least
    5-7`` = "der Wert liegt mindestens im Range 5-7, also mindestens 5",
    NICHT "der Wert liegt im Range 5-7") und teilen die Range-Starter-
    Semantik nicht.
    """
    # Range-Starter mit Wort-Separator ``to``/``bis``: die publizierte
    # Range-Zuordnung wird uebernommen.
    assert csv_loaders.parse_range("from 5 to 7") == (5.0, 7.0)
    assert csv_loaders.parse_range("from 500 to 700") == (500.0, 700.0)
    assert csv_loaders.parse_range("ab 5 bis 7") == (5.0, 7.0)
    assert csv_loaders.parse_range("ab 500 bis 700") == (500.0, 700.0)
    # Range-Starter mit Ziffern-Bindestrich (ASCII + Unicode-Dashes):
    assert csv_loaders.parse_range("from 5-7") == (5.0, 7.0)
    assert csv_loaders.parse_range("ab 5-7") == (5.0, 7.0)
    assert csv_loaders.parse_range("from 5 - 7") == (5.0, 7.0)
    assert csv_loaders.parse_range("ab 5 - 7") == (5.0, 7.0)
    assert csv_loaders.parse_range("from 5–7") == (5.0, 7.0)   # en-dash
    assert csv_loaders.parse_range("ab 5—7") == (5.0, 7.0)     # em-dash
    assert csv_loaders.parse_range("from 5−7") == (5.0, 7.0)   # U+2212 minus
    # Range-Starter mit Einheit auf beiden Grenzen (Standard-Katalog-
    # Notation).
    assert csv_loaders.parse_range("from 5 mm to 7 mm") == (5.0, 7.0)
    assert csv_loaders.parse_range("ab 2.6 g/cm³ bis 2.8 g/cm³") == (2.6, 2.8)
    assert csv_loaders.parse_range("from 500 to 700 CHF") == (500.0, 700.0)
    assert csv_loaders.parse_range("ab 500 bis 700 EUR") == (500.0, 700.0)
    # DE-Komma-Dezimal auf beiden Grenzen (Suisse romande CSV-Excel-
    # Konvention):
    assert csv_loaders.parse_range("ab 2,6 bis 2,8") == (2.6, 2.8)
    assert csv_loaders.parse_range("from 5,5 to 7,5") == (5.5, 7.5)
    # Case-Insensitivitaet (spiegelt die etablierte re.IGNORECASE-
    # Konvention der Comparison-Word-Regexes):
    assert csv_loaders.parse_range("FROM 5 TO 7") == (5.0, 7.0)
    assert csv_loaders.parse_range("From 5 To 7") == (5.0, 7.0)
    assert csv_loaders.parse_range("AB 5 BIS 7") == (5.0, 7.0)
    # Ein-Seiten-Semantik OHNE Range-Separator bleibt unveraendert
    # (die Regress-Anker aus dem Bestand-Test verbleiben verlustfrei):
    assert csv_loaders.parse_range("from 5") == (5.0, None)
    assert csv_loaders.parse_range("ab 500 CHF") == (500.0, None)
    assert csv_loaders.parse_range("ab 1.500,00 CHF") == (1500.0, None)
    # Ein-Seiten-Semantik mit negativen Werten - der Ziffern-Bindestrich-
    # Detektor verlangt eine Ziffer VOR dem ``-`` (Lookbehind ``(?<=\\d)``),
    # sodass die Sign-Bindung ``-5`` nicht faelschlich als Range-Separator
    # gelesen wird.
    assert csv_loaders.parse_range("ab -5") == (-5.0, None)
    assert csv_loaders.parse_range("from -5") == (-5.0, None)
    # Andere Wort-Marker sind KEINE Range-Starter und behalten die
    # strikte Ein-Seiten-Semantik auch bei folgendem Range-Ausdruck:
    assert csv_loaders.parse_range("at least 5-7") == (5.0, None)
    assert csv_loaders.parse_range("at least 5 to 7") == (5.0, None)
    assert csv_loaders.parse_range("mindestens 5-7") == (5.0, None)
    assert csv_loaders.parse_range("mindestens 5 bis 7") == (5.0, None)
    assert csv_loaders.parse_range("ueber 5 bis 7") == (5.0, None)
    assert csv_loaders.parse_range("over 5 to 7") == (5.0, None)
    assert csv_loaders.parse_range("greater than 5 to 7") == (5.0, None)
    assert csv_loaders.parse_range("more than 5-7") == (5.0, None)
    assert csv_loaders.parse_range("wenigstens 5-7") == (5.0, None)
    assert csv_loaders.parse_range("oberhalb 5-7") == (5.0, None)
    # Bestandsverhalten der Zwischen-Zahl-Separator-Semantik unveraendert:
    # ``to``/``bis`` als reine Range-Separator zwischen zwei Zahlen (ohne
    # vorangestellten Range-Starter) bleiben verlustfrei.
    assert csv_loaders.parse_range("3 bis 5") == (3.0, 5.0)
    assert csv_loaders.parse_range("3 to 5") == (3.0, 5.0)
    assert csv_loaders.parse_range("5-7") == (5.0, 7.0)
    # Bestandsverhalten der oberen-Wort-Marker unveraendert:
    assert csv_loaders.parse_range("bis 5") == (None, 5.0)
    assert csv_loaders.parse_range("bis zu 500") == (None, 500.0)
    assert csv_loaders.parse_range("up to 5") == (None, 5.0)
    assert csv_loaders.parse_range("at most 5") == (None, 5.0)


def test_parse_range_leading_currency_prefix_mit_uncertainty():
    """Leading-Waehrungs-Prefix am Wert-Anfang (ISO-4217-Codes CHF/USD/EUR/GBP/JPY/...
    und Waehrungs-Symbole ``$``/``€``/``£``/``¥``/... plus Compound-``$``-Prefixe
    HK$/US$/NZ$/AU$/CA$/SG$/NT$) wird gestrippt, damit die nachfolgende
    Uncertainty-Notation (``±``-Langform oder ``N(M)``-Kompaktform) die
    publizierte Toleranz als Bereichsgrenzen behaelt.

    Vor dem Fix fielen alle Kombinationen "Leading-Waehrungs-Marker +
    Uncertainty" still auf die Fallback-Zahl-Extraktion durch, weil sowohl
    :data:`_PLUS_MINUS_UNCERTAINTY` als auch :data:`_PARENTHESIS_UNCERTAINTY`
    per ``^\\s*(-?\\d ...)``-Anker eine Zahl (oder Vorzeichen) am String-Anfang
    verlangen:

    * ``"CHF 500 ± 50"``   -> ``[500, 50]`` -> (500, 500)   (Toleranz verloren)
    * ``"$500 ± 50"``      -> ``[500, 50]`` -> (500, 500)   (dito)
    * ``"€2.65(5)"``       -> ``[2.65, 5]`` -> (2.65, 5.0)  (semantisch falscher Range)
    * ``"USD 5.5 ± 0.3"``  -> ``[5.5, 0.3]`` -> (5.5, 5.5)  (Toleranz verloren)
    * ``"HK$100 ± 5"``     -> ``[100, 5]`` -> (100, 100)    (Toleranz verloren)

    In Auktions-Katalogen (Christie's, Bonhams, Sotheby's Fine Mineral,
    Rocks & Minerals-Zeitschrift) und in Erbschafts-/Boersen-Schaetzungen
    ist die Leading-Waehrungs-Konvention der Standard - der Waehrungs-Marker
    identifiziert die Wert-Achse, waehrend die Uncertainty-Notation die
    Streuung um den Schaetz-Wert publiziert. Beide Marker sind komplementaer:
    ohne Waehrung ist die Zahl semantisch mehrdeutig (CHF/EUR/USD als
    Wert-CHF-roh-Kandidat), ohne Uncertainty geht die Praezision verloren.

    Vokabel-Liste und Zweig-Layout spiegeln die Symmetrie-Konvention von
    :data:`_APPROX_VALUE_PREFIX`: identische Strip-und-Rekursion-Semantik,
    identische Kombination-mit-Approximations-Marker-Auflösung ("ca. CHF
    500 ± 50" und "CHF ca. 500 ± 50" liefern identische Ergebnisse via
    Rekursion). Case-Insensitiv (Excel-Autocorrect "Chf"/"Usd" und
    lowercase-Notation aus Konsolen-Tools ohne Caps-Lock).
    """
    # ISO-4217-Code + ±-Langform-Uncertainty. Der Praefix wird gestrippt,
    # die publizierte Toleranz laeuft in den _PLUS_MINUS_UNCERTAINTY-Zweig.
    assert csv_loaders.parse_range("CHF 500 ± 50") == pytest.approx((450.0, 550.0))
    assert csv_loaders.parse_range("EUR 500 ± 50") == pytest.approx((450.0, 550.0))
    assert csv_loaders.parse_range("USD 500 ± 50") == pytest.approx((450.0, 550.0))
    assert csv_loaders.parse_range("GBP 500 ± 50") == pytest.approx((450.0, 550.0))
    assert csv_loaders.parse_range("JPY 500 ± 50") == pytest.approx((450.0, 550.0))
    assert csv_loaders.parse_range("CAD 500 ± 50") == pytest.approx((450.0, 550.0))
    assert csv_loaders.parse_range("AUD 500 ± 50") == pytest.approx((450.0, 550.0))
    assert csv_loaders.parse_range("SEK 500 ± 50") == pytest.approx((450.0, 550.0))
    assert csv_loaders.parse_range("NOK 500 ± 50") == pytest.approx((450.0, 550.0))
    assert csv_loaders.parse_range("DKK 500 ± 50") == pytest.approx((450.0, 550.0))
    assert csv_loaders.parse_range("NZD 500 ± 50") == pytest.approx((450.0, 550.0))
    assert csv_loaders.parse_range("PLN 500 ± 50") == pytest.approx((450.0, 550.0))
    assert csv_loaders.parse_range("CZK 500 ± 50") == pytest.approx((450.0, 550.0))
    assert csv_loaders.parse_range("HUF 500 ± 50") == pytest.approx((450.0, 550.0))
    assert csv_loaders.parse_range("RUB 500 ± 50") == pytest.approx((450.0, 550.0))
    assert csv_loaders.parse_range("CNY 500 ± 50") == pytest.approx((450.0, 550.0))
    assert csv_loaders.parse_range("HKD 500 ± 50") == pytest.approx((450.0, 550.0))
    assert csv_loaders.parse_range("SGD 500 ± 50") == pytest.approx((450.0, 550.0))
    assert csv_loaders.parse_range("INR 500 ± 50") == pytest.approx((450.0, 550.0))
    assert csv_loaders.parse_range("AED 500 ± 50") == pytest.approx((450.0, 550.0))
    assert csv_loaders.parse_range("ILS 500 ± 50") == pytest.approx((450.0, 550.0))
    assert csv_loaders.parse_range("ZAR 500 ± 50") == pytest.approx((450.0, 550.0))
    assert csv_loaders.parse_range("BRL 500 ± 50") == pytest.approx((450.0, 550.0))
    assert csv_loaders.parse_range("MXN 500 ± 50") == pytest.approx((450.0, 550.0))
    assert csv_loaders.parse_range("TRY 500 ± 50") == pytest.approx((450.0, 550.0))
    assert csv_loaders.parse_range("THB 500 ± 50") == pytest.approx((450.0, 550.0))
    assert csv_loaders.parse_range("KRW 500 ± 50") == pytest.approx((450.0, 550.0))
    # Waehrungs-Symbole (Ein-Zeichen-Marker am String-Anfang, ohne Whitespace-
    # Trennung typisch) + ±-Langform-Uncertainty.
    assert csv_loaders.parse_range("$500 ± 50") == pytest.approx((450.0, 550.0))
    assert csv_loaders.parse_range("€500 ± 50") == pytest.approx((450.0, 550.0))
    assert csv_loaders.parse_range("£500 ± 50") == pytest.approx((450.0, 550.0))
    assert csv_loaders.parse_range("¥500 ± 50") == pytest.approx((450.0, 550.0))
    assert csv_loaders.parse_range("¢500 ± 50") == pytest.approx((450.0, 550.0))
    assert csv_loaders.parse_range("₹500 ± 50") == pytest.approx((450.0, 550.0))
    assert csv_loaders.parse_range("₩500 ± 50") == pytest.approx((450.0, 550.0))
    assert csv_loaders.parse_range("₽500 ± 50") == pytest.approx((450.0, 550.0))
    assert csv_loaders.parse_range("₺500 ± 50") == pytest.approx((450.0, 550.0))
    assert csv_loaders.parse_range("₪500 ± 50") == pytest.approx((450.0, 550.0))
    assert csv_loaders.parse_range("₣500 ± 50") == pytest.approx((450.0, 550.0))
    # Symbol + optionales Whitespace vor der Zahl (``$ 500`` und ``$500``
    # sind beide typisch, Zeichen-Setz-Konvention variiert je nach Quelle).
    assert csv_loaders.parse_range("$ 500 ± 50") == pytest.approx((450.0, 550.0))
    assert csv_loaders.parse_range("€ 500 ± 50") == pytest.approx((450.0, 550.0))
    # Compound-$-Prefixe (HK$, US$, NZ$, AU$, CA$, SG$, NT$) fuer die
    # dominanten Nicht-USD-$-Waehrungen aus internationalen Auktions-
    # Katalogen.
    assert csv_loaders.parse_range("HK$500 ± 50") == pytest.approx((450.0, 550.0))
    assert csv_loaders.parse_range("US$500 ± 50") == pytest.approx((450.0, 550.0))
    assert csv_loaders.parse_range("NZ$500 ± 50") == pytest.approx((450.0, 550.0))
    assert csv_loaders.parse_range("AU$500 ± 50") == pytest.approx((450.0, 550.0))
    assert csv_loaders.parse_range("CA$500 ± 50") == pytest.approx((450.0, 550.0))
    assert csv_loaders.parse_range("SG$500 ± 50") == pytest.approx((450.0, 550.0))
    assert csv_loaders.parse_range("NT$500 ± 50") == pytest.approx((450.0, 550.0))
    # IUCr-Kompakt-Uncertainty ``N(M)`` mit Leading-Waehrungs-Marker.
    assert csv_loaders.parse_range("CHF 5.5(3)") == pytest.approx((5.2, 5.8))
    assert csv_loaders.parse_range("USD 2.65(5)") == pytest.approx((2.60, 2.70))
    assert csv_loaders.parse_range("EUR 100(2)") == pytest.approx((98.0, 102.0))
    assert csv_loaders.parse_range("$5.5(3)") == pytest.approx((5.2, 5.8))
    assert csv_loaders.parse_range("€2.65(5)") == pytest.approx((2.60, 2.70))
    assert csv_loaders.parse_range("£100(2)") == pytest.approx((98.0, 102.0))
    # Kombination Approx-Praefix + Waehrungs-Praefix + Uncertainty in beiden
    # Reihenfolgen (Rekursion loest die Verkettung transparent auf).
    assert csv_loaders.parse_range("ca. CHF 500 ± 50") == pytest.approx((450.0, 550.0))
    assert csv_loaders.parse_range("CHF ca. 500 ± 50") == pytest.approx((450.0, 550.0))
    assert csv_loaders.parse_range("~$500 ± 50") == pytest.approx((450.0, 550.0))
    assert csv_loaders.parse_range("$~500 ± 50") == pytest.approx((450.0, 550.0))
    assert csv_loaders.parse_range("circa €5.5(3)") == pytest.approx((5.2, 5.8))
    assert csv_loaders.parse_range("€ circa 5.5(3)") == pytest.approx((5.2, 5.8))
    assert csv_loaders.parse_range("approx. USD 100(2)") == pytest.approx((98.0, 102.0))
    # Kombination Leading-Waehrung + Uncertainty + Trailing-Approx-Marker
    # (via _APPROX_VALUE_SUFFIX-Strip in der Rekursion): "CHF 500 ± 50, ca."
    # -> Waehrungs-Strip -> "500 ± 50, ca." -> Trailing-Suffix-Strip ->
    # "500 ± 50" -> Uncertainty-Match.
    assert csv_loaders.parse_range("CHF 500 ± 50, ca.") == pytest.approx((450.0, 550.0))
    assert csv_loaders.parse_range("$500 ± 50 geschaetzt") == pytest.approx((450.0, 550.0))
    assert csv_loaders.parse_range("€2.65(5), circa") == pytest.approx((2.60, 2.70))
    # Case-Insensitivitaet: Excel-Autocorrect "Chf"/"Usd" und lowercase-
    # Notation aus Konsolen-Tools ohne Caps-Lock.
    assert csv_loaders.parse_range("chf 500 ± 50") == pytest.approx((450.0, 550.0))
    assert csv_loaders.parse_range("Chf 500 ± 50") == pytest.approx((450.0, 550.0))
    assert csv_loaders.parse_range("usd 500 ± 50") == pytest.approx((450.0, 550.0))
    assert csv_loaders.parse_range("Eur 500 ± 50") == pytest.approx((450.0, 550.0))
    # DE-Komma-Dezimal-Locale (Suisse romande CSV-Excel-Konvention) mit
    # Leading-Waehrungs-Marker.
    assert csv_loaders.parse_range("CHF 5,5 ± 0,3") == pytest.approx((5.2, 5.8))
    assert csv_loaders.parse_range("EUR 2,65(5)") == pytest.approx((2.60, 2.70))
    # Praefix + Uncertainty + Trailing-Einheit (die Einheit bleibt symmetrisch
    # zur reinen Uncertainty-Notation erhalten).
    assert csv_loaders.parse_range("CHF 5.5 ± 0.3 Mohs") == pytest.approx((5.2, 5.8))
    assert csv_loaders.parse_range("$100 ± 2 HV") == pytest.approx((98.0, 102.0))
    # Praefix + Uncertainty + Trailing-Klammer-Annotation.
    assert csv_loaders.parse_range("CHF 500 ± 50 (Schaetzung)") == pytest.approx((450.0, 550.0))
    assert csv_loaders.parse_range("€2.65(5) [Ref 42]") == pytest.approx((2.60, 2.70))
    # Praefix + Uncertainty + Trailing-Satzzeichen (Excel-CSV-Zeilen-Ende-
    # Punkt/Komma aus Editor-Autocomplete).
    assert csv_loaders.parse_range("CHF 500 ± 50.") == pytest.approx((450.0, 550.0))
    assert csv_loaders.parse_range("$500 ± 50,") == pytest.approx((450.0, 550.0))
    # Interaktion mit _COMPARISON_PREFIX (Zeichen-Vergleich) und
    # _COMPARISON_WORD_LOWER / _COMPARISON_WORD_UPPER (Wort-Vergleich):
    # Leading-Waehrung + Vergleichs-Marker liefert die offene Range-Grenze
    # nach dem Waehrungs-Strip; die Kombination in beiden Reihenfolgen
    # loest ueber Rekursion auf.
    assert csv_loaders.parse_range("CHF > 500") == (500.0, None)
    assert csv_loaders.parse_range("CHF < 500") == (None, 500.0)
    assert csv_loaders.parse_range(">= CHF 500") == (500.0, None)
    assert csv_loaders.parse_range("<= EUR 500") == (None, 500.0)
    assert csv_loaders.parse_range("mindestens CHF 500") == (500.0, None)
    assert csv_loaders.parse_range("CHF mindestens 500") == (500.0, None)
    assert csv_loaders.parse_range("hoechstens $500") == (None, 500.0)
    assert csv_loaders.parse_range("$ maximal 500") == (None, 500.0)
    # Kollisionsschutz: Fremdwoerter, die zufaellig mit den gleichen Buchstaben
    # beginnen wie ISO-4217-Codes (``USDA`` = US-Landwirtschafts-Ministerium,
    # ``SEKtoren``, ``AUDio``, ``NOKia``, ``PLNe``, ``CNYanide``), duerfen
    # den Wert nicht vor der Uncertainty-Notation strippen - der ``\\b``-
    # Wortgrenze hinter dem Code blockt Kollision, weil zwischen Code-Endung
    # und Fremdwort-Fortsetzung keine Wortgrenze liegt. Ohne Uncertainty
    # bleibt das Verhalten unveraendert (Fallback-Zahl-Extraktion findet den
    # Wert weiterhin, aber die Waehrungs-Semantik geht verloren - was
    # semantisch korrekt ist, weil "usda 500" keine Waehrungs-Zeile ist).
    assert csv_loaders.parse_range("usda 500") == (500.0, 500.0)
    assert csv_loaders.parse_range("USDA 500") == (500.0, 500.0)
    assert csv_loaders.parse_range("chief 500") == (500.0, 500.0)
    assert csv_loaders.parse_range("SEKtoren 500") == (500.0, 500.0)
    assert csv_loaders.parse_range("AUDio 500") == (500.0, 500.0)
    assert csv_loaders.parse_range("NOKia 500") == (500.0, 500.0)
    # Kollisionsschutz gegen SI-Einheiten am Anfang (nicht-Waehrungs-
    # Buchstaben-Sequenzen): ``kg``/``g``/``mm`` sind keine Waehrungen und
    # duerfen keinen Praefix-Strip ausloesen.
    assert csv_loaders.parse_range("kg 500") == (500.0, 500.0)
    assert csv_loaders.parse_range("g 500") == (500.0, 500.0)
    # Waehrungs-Marker OHNE nachfolgende Zahl fallen still auf None -
    # ohne Zahl gibt es keinen Wert. Spiegelt die Konvention aus
    # test_parse_range_annaeherungs_praefix_mit_uncertainty.
    assert csv_loaders.parse_range("CHF") == (None, None)
    assert csv_loaders.parse_range("CHF ") == (None, None)
    assert csv_loaders.parse_range("$") == (None, None)
    assert csv_loaders.parse_range("€") == (None, None)
    # Regress-Anker: Waehrungs-Praefix vor reiner Zahl (ohne Uncertainty)
    # bleibt rueckwaerts-kompatibel - der Praefix wird gestrippt und die
    # reine Zahl-Extraktion laeuft weiter mit identischem Ergebnis.
    assert csv_loaders.parse_range("CHF 500") == (500.0, 500.0)
    assert csv_loaders.parse_range("$500") == (500.0, 500.0)
    assert csv_loaders.parse_range("EUR 5.5") == (5.5, 5.5)
    # Regress-Anker: Waehrungs-Praefix vor Range-Notation (ohne Uncertainty)
    # bleibt rueckwaerts-kompatibel - die Range-Grenzen laufen in die
    # Fallback-Zahl-Extraktion nach dem Praefix-Strip.
    assert csv_loaders.parse_range("CHF 500-1000") == (500.0, 1000.0)
    assert csv_loaders.parse_range("CHF 500 - 1000") == (500.0, 1000.0)
    assert csv_loaders.parse_range("$500-$1000") == (500.0, 1000.0)
    assert csv_loaders.parse_range("EUR 5.5 to 7.5") == (5.5, 7.5)
    # Regress-Anker: Trailing-Waehrungs-Form (bereits ueber die Trailing-
    # Einheit-Alternate in _PLUS_MINUS_UNCERTAINTY abgedeckt) bleibt
    # unveraendert - der Leading-Strip greift nicht.
    assert csv_loaders.parse_range("500 CHF ± 50") == pytest.approx((450.0, 550.0))
    assert csv_loaders.parse_range("500 ± 50 CHF") == pytest.approx((450.0, 550.0))
    # Regress-Anker: Werte OHNE Waehrungs-Praefix bleiben unveraendert.
    assert csv_loaders.parse_range("500 ± 50") == pytest.approx((450.0, 550.0))
    assert csv_loaders.parse_range("2.65(5)") == pytest.approx((2.60, 2.70))
    assert csv_loaders.parse_range("100(2)") == pytest.approx((98.0, 102.0))
    assert csv_loaders.parse_range("500-1000") == (500.0, 1000.0)


def test_read_ids_from_file_leerdatei_und_nur_kommentare_liefern_leere_liste(tmp_path):
    """Leere Datei / nur Kommentare -> [] (kein Fehler, aber auch keine IDs).

    Der Aufrufer (csv_cli/docx_cli) unterscheidet dann zwischen
    ``None`` (Datei-Fehler) und ``[]`` (Datei gelesen, aber keine
    verwertbare Zeile) - beides wird von den CLIs als "keine gueltige
    Selektion" behandelt (aus verschiedenen Gruenden), aber die
    Trennung erlaubt spezifischere Fehlermeldungen im Aufrufer.
    """
    p_empty = tmp_path / "leer.txt"
    p_empty.write_text("", encoding="utf-8")
    assert read_ids_from_file(p_empty) == []

    p_comments = tmp_path / "nur_kommentare.txt"
    p_comments.write_text(
        "# Kopfzeile\n"
        "\n"
        "   # eingerueckter Kommentar\n"
        "   \n",
        encoding="utf-8",
    )
    assert read_ids_from_file(p_comments) == []
