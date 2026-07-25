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
    # DE-Objekt-Nummer-Kompositum: ``Objekt-Nr. 43`` / ``Objekt Nr. 43`` /
    # ``ObjektNr 43`` / ``Objekt-Nr 43`` / ``Objektnummer 43`` /
    # ``Objekt. Nr. 43`` / ``Objekt Nummer 43``. Direktes Kompositum der bereits
    # abgedeckten Achsen ``Objekt`` (Zeile 19 in dieser Datei, ``^Objekt\s+(\d+)$``
    # fuer bare ``Objekt 43``) und ``Nr.`` (Zeile 27, ``^N(?:umme)?r\.?\s*(\d+)$``
    # fuer bare ``Nr. 43``); in DE-sprachigen Sammler-Datenbanken sehr verbreitet
    # als Spalten-Bezeichnung (Excel-Sammlungsverzeichnisse mit Spalten-Header
    # ``Objekt-Nr.`` als laufende ID-Nummer der Sammlung, Karteikarten mit
    # handschriftlichem Feld-Etikett ``Objekt-Nr.:``, Vereinszeitschriften-
    # Referenzen im Aufschluss / Der Aufschluss / Lapis / Mineralien-Welt mit
    # ``Objekt-Nr.``-Notation zur Abgrenzung von der Museums-``Inv.-Nr.``-Achse),
    # in Kaufbelegen (Auktions-Rechnungen von Neumeister / Karl & Faber /
    # Ketterer Kunst mit ``Objekt-Nr. 43`` als Los-Referenz auf dem Rechnungs-
    # Beleg) und in geerbten Sammler-Notizen aus DE-sprachigen Bestaenden
    # (der Vorbesitzer notierte in seinem privaten Katalog ``Objekt-Nr.``
    # neben der Museums-``Inv.-Nr.`` und der eigenen ``Slg.-Nr.``). Bisher
    # fielen alle Objekt-Nr.-/Objektnummer-Kompositum-Formen still auf None,
    # weil die bestehende ``^Objekt\s+(\d+)$``-Regex nur bare ``Objekt`` +
    # Whitespace + Ziffer matched und die bestehende ``^N(?:umme)?r\.?``-
    # Regex nur bare ``Nr.``/``Nummer`` + Ziffer matched - der Kompositum-
    # Praefix ``Objekt-Nr.`` blieb ungedeckt, obwohl semantisch identisch
    # zur Summe beider Komponenten.
    #
    # Regex ``^Objekt\.?[-.\s]*N(?:umme)?r\.?\s*(\d+)$`` (case-insensitive)
    # spiegelt strukturell die Inv-/Kat-/Fund-/Slg-Kompositum-Konvention
    # (``^Inv(?:entar)?\.?[-.\s]*N(?:umme)?r\.?\s*(\d+)$`` fuer ``Inv.-Nr.``
    # und ``^Kat(?:alog)?\.?[-.\s]*N(?:umme)?r\.?\s*(\d+)$`` fuer ``Kat.-Nr.``),
    # was Konsistenz der Trenner-Semantik ueber alle DE-Kompositum-Achsen
    # sicherstellt: ``Objekt`` (Vollform, keine Kurzform wie ``Inv``/``Kat``/
    # ``Slg`` - ``Obj`` waere mehrdeutig zu OBJ-Praefix-Kurzform), optionaler
    # Punkt (``Objekt.`` selten aber tolerant analog zu ``Inv.``), beliebige
    # Trenner-Kombination [-.\s]* zwischen Objekt- und Nr-Teil (``Objekt-Nr``,
    # ``Objekt.Nr``, ``Objekt Nr``, ``ObjektNr``, ``Objekt-Nr.``), obligatorischer
    # ``N(?:umme)?r``-Marker (deckt ``Nr``/``Nummer`` ab, symmetrisch zur bare
    # ``Nr.``-Regex), optionaler Punkt nach Nr (``Nr.`` vs. ``Nr``), optionaler
    # Whitespace vor Ziffer (``Nr43`` vs. ``Nr 43``).
    #
    # Der obligatorische ``N(?:umme)?r``-Marker verhindert falsche Positives
    # fuer bare ``Objekt 43`` (bereits durch ``^Objekt\s+(\d+)$`` gedeckt,
    # kollisions-frei weil dieser Praefix kein N-Suffix hat) und fuer
    # Objekt-startende Kompositum-Woerter (``Objektiv`` als Foto-Objektiv-
    # Kurzform in Fotograf-Notizen wie ``Objektiv 43mm``, ``Objektivitaet``
    # in wissenschaftlichen Bewertungs-Prosa-Kontexten wie ``Objektivitaet
    # 43%``, ``Objektion`` in rhetorischen Diskurs-Notizen) - der Marker
    # ist die Disambiguierungs-Klammer analog zum Inv-vs-Invasion- und
    # Kat-vs-Kategorie-Schutz.
    #
    # Positionierung direkt nach ``^Object\s+(\d+)$`` (Zeile 21) haelt alle
    # Objekt/Object-Praefixe zusammen (Reihenfolge: bare DE-Vollform,
    # bare EN-Vollform, DE-Kompositum). Kollisionsfrei zur bestehenden
    # ``^Objekt\s+(\d+)$``-Regex (die matched bare ``Objekt 43`` ohne
    # Nr-Marker, der neue Praefix verlangt Nr-Marker), zur bare
    # ``^N(?:umme)?r\.?``-Regex (die matched bare ``Nr. 43`` ohne
    # Objekt-Vorlauf, der neue Praefix verlangt Objekt-Vorlauf), zu Inv/
    # Kat/Slg/Fund/Cat/Acc/Reg/Field/Coll/Spec (disjunkte Anfangs-
    # Buchstaben) und zur OBJ[-_.\s]+-Regex (die matched OBJ-Kurzform,
    # nicht Objekt-Vollform - lexikalisch disjunkt weil OBJ mit drei
    # Grossbuchstaben endet, ``Objekt`` ist ein Wort mit acht Buchstaben).
    # Der $-Anker verhindert Suffix-Ballast (``Objekt-Nr. 43X``,
    # ``Objekt-Nr 43 44`` bleiben None).
    re.compile(r"^Objekt\.?[-.\s]*N(?:umme)?r\.?\s*(\d+)$", re.IGNORECASE),
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
    # Private Sammlungsnummer: ``Slg.-Nr. 43`` / ``Slg. Nr. 43`` / ``SlgNr 43`` /
    # ``Slg-Nr. 43`` / ``Sammlungsnummer 43`` / ``Sammlung-Nr. 43`` / ``Sammlungs-Nr. 43``.
    # Standard-Praefix privater Sammler-Kataloge (Excel-Sammlungsverzeichnisse, Karteikarten,
    # Vereinszeitschriften-Referenzen): ``Slg.`` ist die etablierte Kurzform von ``Sammlung`` in
    # DE-sprachigen Sammler-Notizen (analog ``Inv.`` = Inventar, ``Kat.`` = Katalog). Waehrend
    # ``Inv.-Nr.`` (323cfff) die Museums-physische Inventar-Position, ``Kat.-Nr.`` (be56257) den
    # logischen Katalog-Eintrag und ``Fund-Nr.`` (aa5372d) das Sammel-Ereignis referenziert,
    # identifiziert ``Slg.-Nr.`` den laufenden Zaehler im privaten Sammlungs-Katalog - die vier
    # Achsen koexistieren auf Objekten, die ueber Museums-/Sammler-Grenzen wandern (Museums-
    # Erwerbungen aus Privatsammlungen tragen alle vier Nummern parallel). Regex spiegelt die
    # Inv-/Kat-/Fund-Regex strukturell: ``(?:Slg|Sammlungs?)`` mit optionalem Punkt (``Slg.``
    # vs. ``Slg``), beliebige Trenner-Kombination [-.\s]*, obligatorischer ``N(?:umme)?r``-
    # Marker (verhindert falsche Positives fuer bare ``Slg 43`` oder Sammlungs-startende
    # Kompositum-Woerter wie ``Sammlungsstueck``, ``Sammlungsgegenstand``, ``Sammlungsobjekt``,
    # ``Sammlungsband``, sowie fuer ``Sammler``/``Sammelband``/``Sammelklage``). Die optionale
    # Genitiv-s-Erweiterung ``Sammlungs?`` deckt sowohl die grammatikalisch korrekte Kompositum-
    # Form ``Sammlungsnummer`` (Fugen-s bei Feminina) als auch die verkuerzte Bindestrich-Form
    # ``Sammlung-Nr.`` (ohne Fugen-s, verbreitet in handschriftlichen Karteikarten) ab.
    re.compile(r"^(?:Slg|Sammlungs?)\.?[-.\s]*N(?:umme)?r\.?\s*(\d+)$", re.IGNORECASE),
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
    # Englische Katalog-Nummer: ``Cat. No. 43`` / ``Cat No 43`` / ``CatNo43`` /
    # ``Cat-No. 43`` / ``Catalog Number 43`` / ``Catalogue No. 43``. Englisches Pendant
    # zur DE-``Kat.-Nr.``-Regex (be56257): Standard-Praefix auf EN-sprachigen Museums-
    # Etiketten und Sammlungs-Datenbanken der grossen anglo-amerikanischen Naturkunde-
    # Museen (Smithsonian National Museum of Natural History NMNH mit "Cat. No."-
    # Standard in ihrer Mineralien-Datenbank, American Museum of Natural History NYC,
    # Natural History Museum London mit BM-Kuerzel "Cat.No.", Yale Peabody Museum,
    # Harvard Mineralogical & Geological Museum) sowie in publizierten EN-sprachigen
    # Sammlungs-Katalogen (Rocks & Minerals, Mineralogical Record, The Canadian
    # Mineralogist mit "Cat. No."-Referenz-Notation in Type-Locality-Reports und in
    # Type-Specimen-Publikationen). Sammler-Notizen aus Museums-Besuchen im anglo-
    # amerikanischen Raum ("Case 12, Cat. No. 12345, Baryt from Cornwall") und
    # Publikations-Referenzen ("cf. Cat. No. 8721 in Rocks & Minerals 94:3") uebernehmen
    # die Notation woertlich; ohne diese Praefix-Erkennung faellt der ``--ids-from-file``-
    # Import solcher Listen still auf None. Regex spiegelt die Kat.-Nr.-Regex
    # strukturell mit EN-Vokabular: ``Cat(?:alog(?:ue)?)?`` deckt Kurz- (``Cat``),
    # US-Vollform (``Catalog``) und UK-Vollform (``Catalogue``) ab, optionaler Punkt
    # (``Cat.`` vs. ``Cat``), beliebige Trenner-Kombination [-.\s]*, obligatorischer
    # ``N(?:o|umber)`` -Marker (deckt Kurzform ``No`` und Vollform ``Number`` ab),
    # optionaler Punkt nach No, optionaler Whitespace vor Ziffer. Der obligatorische
    # No/Number-Marker verhindert falsche Positives fuer bare ``Cat 43`` (mehrdeutig zu
    # englischer Prosa "Cat named 43") und fuer andere ``Cat``-startende Woerter im
    # EN-Vokabular (``Category``, ``Cathedral``, ``Catholic``, ``Catnap``, ``Catch``,
    # ``Cattle``). Kollisionsfrei zur bestehenden Kat.-Nr.-Regex (``Cat`` != ``Kat``
    # lexikalisch), zu OBJ/Objekt/Object (``Cat`` startet nicht mit ``O``) und zur
    # ``No.``-Prefix-Regex (``No. 43`` matched dort, ``Cat No. 43`` matched hier -
    # spezifischerer Praefix schlaegt generischer, gleichwertige Semantik).
    re.compile(r"^Cat(?:alog(?:ue)?)?\.?[-.\s]*N(?:o|umber)\.?\s*(\d+)$", re.IGNORECASE),
    # Englische Accession-/Erwerbungs-Nummer: ``Acc. No. 43`` / ``Acc No. 43`` /
    # ``AccNo 43`` / ``Acc-No. 43`` / ``Accession No. 43`` / ``Accession Number 43``.
    # Zweiter grosser EN-Museums-Standard neben ``Cat. No.`` (Katalog-Eintrag) - waehrend
    # die Katalog-Nummer den Datensatz-Eintrag im Sammlungs-Katalog identifiziert
    # ("welcher Zeile im publizierten Bestand-Katalog"), referenziert die Accession-
    # Nummer das Erwerbungs-Ereignis der Sammlung ("wann/wie in die Sammlung gekommen":
    # Kauf, Schenkung, Tausch, Feld-Expedition, Auktion, Nachlass). Beide Achsen
    # koexistieren als eigenstaendige Nummerierungs-Systeme auf denselben Objekten
    # in den Sammlungs-Datenbanken der anglo-amerikanischen Naturkunde-Museen
    # (Smithsonian National Museum of Natural History NMNH mit ``Acc.``-Standard
    # fuer alle Erwerbungs-Chargen parallel zur Cat.-No.-Position, American Museum
    # of Natural History NYC, Natural History Museum London, Yale Peabody Museum,
    # Harvard Mineralogical & Geological Museum) und in publizierten EN-Type-
    # Specimen-Reports (Rocks & Minerals, Mineralogical Record, The Canadian
    # Mineralogist mit Accession-Referenzen in Provenienz-Zitaten wie "Type
    # specimen, Acc. No. 12345, NMNH" oder "acquired via Sotheby's Auktion 1998,
    # Acc. No. 8721"). Sammler-Notizen aus Museums-Besuchen ("Case 12, Acc. No.
    # 12345, Baryt from Cornwall") und Provenienz-Recherchen ("previously in
    # Roebling Collection, Acc. No. 4302 at NMNH") uebernehmen die Notation
    # woertlich; ohne diese Praefix-Erkennung faellt der ``--ids-from-file``-
    # Import solcher Listen still auf None und der Aufrufer beendete mit
    # ``Ungueltige Objekt-ID: 'Acc. No. 43'``, obwohl die Absicht semantisch
    # identisch zur Cat.-No.-Form (``Praefix + Ziffer``) ist. Regex spiegelt die
    # Cat.-No.-Regex strukturell mit Accession-Vokabular: ``Acc(?:ession)?`` deckt
    # Kurzform (``Acc``) und ausgeschriebene Vollform (``Accession``) ab, optionaler
    # Punkt (``Acc.`` vs. ``Acc``), beliebige Trenner-Kombination [-.\s]*,
    # obligatorischer ``N(?:o|umber)``-Marker (spiegelt Cat.-No.-Marker: deckt
    # Kurzform ``No`` und Vollform ``Number`` ab), optionaler Punkt nach No,
    # optionaler Whitespace vor Ziffer. Der obligatorische No/Number-Marker
    # verhindert falsche Positives fuer bare ``Acc 43`` (mehrdeutig zu englischer
    # Prosa) und - kritisch fuer ``Acc``-Praefix - fuer die grosse Familie
    # ``Acc``-startender EN-Woerter (``Access``, ``Accept``, ``Account``,
    # ``Accord``, ``Accurate``, ``Accompany``, ``Accomplish``, ``Accuse``); der
    # Marker ist die Disambiguierungs-Klammer analog zum ``Cat``-vs-``Category``-
    # Schutz. Kollisionsfrei zur bestehenden Cat.-No.-Regex (``Acc`` lexikalisch
    # disjunkt zu ``Cat``), zu OBJ/Objekt/Object (``Acc`` startet mit ``A``,
    # nicht ``O``), zu Inv/Kat/Fund/Slg (disjunkte Anfangs-Buchstaben) und zur
    # ``No.``-Prefix-Regex (``No. 43`` matched dort, ``Acc No. 43`` matched
    # hier - spezifischerer Praefix schlaegt generischer, gleichwertige Semantik).
    re.compile(r"^Acc(?:ession)?\.?[-.\s]*N(?:o|umber)\.?\s*(\d+)$", re.IGNORECASE),
    # Englische Registrierungs-Nummer: ``Reg. No. 43`` / ``Reg No. 43`` /
    # ``RegNo 43`` / ``Reg-No. 43`` / ``Registration No. 43`` / ``Registration
    # Number 43``. Dritter grosser EN-Museums-Standard neben ``Cat. No.``
    # (Katalog-Eintrag, 4018fc3) und ``Acc. No.`` (Erwerbungs-Ereignis, 70cd155):
    # die Registration Number ist der laufende Zaehler im offiziellen Bestands-
    # Register und wird besonders im britischen Museums-Umfeld gefuehrt (Natural
    # History Museum London mit ``BM.<jahr>,<nr>``-Notation im Sammlungs-Katalog,
    # National Museum of Wales, Sedgwick Museum Cambridge, National Museums
    # Scotland). In publizierten EN-Type-Specimen-Reports und Provenienz-
    # Zitaten wie "Reg. No. 1976.123, NHM London" oder "registered as Reg
    # No 4302" verbreitet. Bisher fielen alle Reg.-No.-Formen still auf None,
    # weil das Regex-Set keinen ``Reg``-startenden Praefix kannte. Regex
    # spiegelt die Cat.-/Acc.-No.-Regex strukturell mit Registration-Vokabular:
    # ``Reg(?:istration)?`` deckt Kurzform und Vollform ab, obligatorischer
    # ``N(?:o|umber)``-Marker deckt No/Number ab, beliebige Trenner-Kombination
    # [-.\s]*. Der obligatorische No/Number-Marker verhindert falsche Positives
    # fuer bare ``Reg 43`` (mehrdeutig zu englischer Prosa) und fuer die
    # ``Reg``-startenden Woerter (``Region``, ``Regular``, ``Regard``,
    # ``Register``, ``Regret``, ``Regime``) - der Marker ist die Disambiguierungs-
    # Klammer analog zum Cat-vs-Category- und Acc-vs-Access-Schutz. Kollisions-
    # frei zu Cat/Acc (lexikalisch disjunkte Anfangs-Buchstaben) und zu allen
    # DE-Praefixen (Inv/Kat/Fund/Slg/Nr).
    re.compile(r"^Reg(?:istration)?\.?[-.\s]*N(?:o|umber)\.?\s*(\d+)$", re.IGNORECASE),
    # Englische Feld-Nummer: ``Field No. 43`` / ``Field-No. 43`` / ``FieldNo 43`` /
    # ``Field Number 43``. Englisches Pendant zur DE-``Fund-Nr.``-Regex (aa5372d):
    # waehrend ``Cat. No.`` (4018fc3) den Katalog-Eintrag im publizierten Sammlungs-
    # Katalog identifiziert und ``Acc. No.`` (70cd155) das Erwerbungs-Ereignis der
    # Museums-Sammlung referenziert, bezeichnet die ``Field No.`` die im Feld
    # vergebene Sammler-Nummer beim tatsaechlichen Sammel-Event - direkter EN-
    # Pendant zum DE-``Fund-Nr.``-Konzept. Standard-Praefix bei USGS-Feld-
    # Kampagnen (United States Geological Survey mit ``Field No.``-Notation auf
    # Feld-Notizbuecher, Sample-Tuten und Foto-Captions), Smithsonian National
    # Museum of Natural History NMNH (``Field No.``-Spalte parallel zur Cat.-No.
    # in der Mineralien-/Petrologie-Datenbank fuer Feld-Provenienz), Harvard
    # Mineralogical & Geological Museum, University of Arizona RRUFF Project
    # sowie in publizierten EN-Type-Locality-Reports und Feld-Kampagnen-
    # Publikationen (Rocks & Minerals, Mineralogical Record, Economic Geology
    # mit ``Field No. 78-4-31``-Referenz-Notation in Provenienz-Zitaten wie
    # "collected 1978, Field No. 78-4-31, deposited NMNH as Cat. No. 156789").
    # Sammler-Notizen aus EN-sprachigen Feld-Kampagnen ("Val d'Anniviers
    # 2024-07-14, Field No. 43, Baryt Cluster") und Museums-Uebernahmen
    # (Museums-Etiketten mit paralleler Field-No.-/Cat.-No.-/Acc.-No.-Notation)
    # uebernehmen die Notation woertlich; ohne diese Praefix-Erkennung faellt
    # der ``--ids-from-file``-Import solcher Listen still auf None. Regex
    # spiegelt die Fund-Nr.-/Cat.-No.-Regex strukturell mit Field-Vokabular:
    # ``Field\.?`` mit optionalem Punkt, beliebige Trenner-Kombination [-.\s]*
    # zwischen Field- und No-Teil, obligatorischer ``N(?:o|umber)``-Marker
    # (spiegelt Cat.-No.-/Acc.-No.-/Reg.-No.-Marker: deckt Kurzform ``No`` und
    # Vollform ``Number`` ab), optionaler Punkt nach No, optionaler Whitespace
    # vor Ziffer. Der obligatorische No/Number-Marker verhindert falsche
    # Positives fuer bare ``Field 43`` (mehrdeutig zu englischer Prosa, "the
    # field is 43 acres") und - kritisch fuer ``Field``-Praefix - fuer die
    # grosse Familie ``Field``-startender EN-Kompositum-Woerter (``Fieldwork``,
    # ``Fieldworker``, ``Fieldnote``, ``Fieldnotes``, ``Fieldstone``,
    # ``Fielding``, ``Fieldtrip``) sowie fuer den EN-Nachname ``Field`` in
    # historischen Provenienz-Zitaten ("previously in the Field Collection").
    # Der Marker ist die Disambiguierungs-Klammer analog zum Cat-vs-Category-,
    # Acc-vs-Access- und Fund-vs-Fundort-Schutz. Kollisionsfrei zur bestehenden
    # Fund-Nr.-Regex (``Field`` lexikalisch disjunkt zu ``Fund``), zu Cat/Acc/
    # Reg (disjunkte Anfangs-Buchstaben ``F`` vs. ``C``/``A``/``R``), zu OBJ/
    # Objekt/Object (``Field`` startet mit ``F``, nicht ``O``), zu Inv/Kat/Slg/
    # Nr (disjunkte Anfangs-Buchstaben) und zur ``No.``-Prefix-Regex
    # (``No. 43`` matched dort, ``Field No. 43`` matched hier - spezifischerer
    # Praefix schlaegt generischer, gleichwertige Semantik).
    re.compile(r"^Field\.?[-.\s]*N(?:o|umber)\.?\s*(\d+)$", re.IGNORECASE),
    # Englische Collection-/Sammlungs-Nummer: ``Coll. No. 43`` / ``Coll-No. 43`` /
    # ``CollNo 43`` / ``Collection No. 43`` / ``Collection Number 43``. Englisches
    # Pendant zur DE-``Slg.-Nr.``-Regex (4ea1bce): waehrend ``Cat. No.`` (4018fc3)
    # den Katalog-Eintrag im publizierten Museums-Sammlungs-Katalog identifiziert,
    # ``Acc. No.`` (70cd155) das Erwerbungs-Ereignis der Museums-Sammlung
    # referenziert, ``Reg. No.`` (542ccc7) den offiziellen Bestands-Register-
    # Eintrag bezeichnet und ``Field No.`` (6657881) die im Feld vergebene
    # Sammler-Nummer markiert, identifiziert die ``Coll. No.`` den laufenden
    # Zaehler im privaten Sammlungs-Katalog des EN-sprachigen Sammlers -
    # direkter EN-Pendant zum DE-``Slg.-Nr.``-Konzept. Standard-Praefix in
    # privaten Sammler-Katalogen (Excel-Sammlungsverzeichnisse, Karteikarten),
    # in publizierten EN-Provenienz-Zitaten wie "Coll. No. 4302 (Roebling
    # Collection)" oder "Ex. Miguel Romero Collection, Coll. No. 156" (in
    # Rocks & Minerals, Mineralogical Record, The Canadian Mineralogist mit
    # Coll.-No.-Referenz-Notation zur Abgrenzung von der Museums-Cat.-/Acc.-No.
    # nach Uebernahme aus Privatsammlungen). Sammler-Notizen aus EN-sprachigen
    # Sammler-Kreisen (US-/UK-/AU-Mineralien-Sammler-Vereine wie Mineralogical
    # Society of America, Mineralogical Association of Canada) uebernehmen die
    # Notation woertlich; ohne diese Praefix-Erkennung faellt der ``--ids-from-
    # file``-Import solcher Listen still auf None. Regex spiegelt die Cat.-/Acc.-
    # /Reg.-/Field-No.-Regex strukturell mit Collection-Vokabular:
    # ``Coll(?:ection)?`` deckt Kurzform (``Coll``) und ausgeschriebene Vollform
    # (``Collection``) ab, optionaler Punkt (``Coll.`` vs. ``Coll``), beliebige
    # Trenner-Kombination [-.\s]*, obligatorischer ``N(?:o|umber)``-Marker
    # (spiegelt Cat.-/Acc.-/Reg.-/Field-No.-Marker: deckt Kurzform ``No`` und
    # Vollform ``Number`` ab), optionaler Punkt nach No, optionaler Whitespace
    # vor Ziffer. Der obligatorische No/Number-Marker verhindert falsche
    # Positives fuer bare ``Coll 43`` (mehrdeutig zu englischer Prosa) und -
    # kritisch fuer ``Coll``-Praefix - fuer die grosse Familie ``Coll``-
    # startender EN-Woerter (``College``, ``Collect``, ``Collar``, ``Collide``,
    # ``Colleague``, ``Collapse``, ``Collision``, ``Collector``, ``Colloquial``).
    # Der Marker ist die Disambiguierungs-Klammer analog zum Cat-vs-Category-,
    # Acc-vs-Access-, Reg-vs-Region- und Field-vs-Fieldwork-Schutz. Kollisions-
    # frei zur bestehenden Slg.-Nr.-Regex (``Coll`` lexikalisch disjunkt zu
    # ``Slg``/``Sammlung``), zu Cat/Acc/Reg/Field (disjunkte Anfangs-Buchstaben
    # ``C``-``o`` vs. ``C``-``a`` bzw. ``A``/``R``/``F``), zu OBJ/Objekt/Object
    # (``Coll`` startet mit ``C``, nicht ``O``), zu Inv/Kat/Slg/Fund/Nr
    # (disjunkte Anfangs-Buchstaben) und zur ``No.``-Prefix-Regex (``No. 43``
    # matched dort, ``Coll No. 43`` matched hier - spezifischerer Praefix
    # schlaegt generischer, gleichwertige Semantik). Kollisionsfrei zur
    # Cat(?:alog(?:ue)?)?-Regex: bei Eingabe ``Coll. No. 43`` scheitert der
    # Cat-Praefix bereits am zweiten Buchstaben (``a`` != ``o``), sodass die
    # Coll-Alternative uebernimmt.
    re.compile(r"^Coll(?:ection)?\.?[-.\s]*N(?:o|umber)\.?\s*(\d+)$", re.IGNORECASE),
    # Englische Specimen-Nummer: ``Spec. No. 43`` / ``Spec-No. 43`` / ``SpecNo 43`` /
    # ``Specimen No. 43`` / ``Specimen Number 43``. Sechster grosser EN-Museums-
    # Standard neben Cat/Acc/Reg/Field/Coll: die Specimen Number identifiziert das
    # physische Forschungs-Exemplar (Type-Specimen, Voucher, Holotype/Paratype) und
    # ist der Standard-Praefix in mineralogisch-/palaeontologischen Type-Specimen-
    # Publikationen (NMNH, Museum of Comparative Zoology Harvard, Field Museum,
    # USGS Type Collection). In Provenienz-Zitaten wie "Holotype, Spec. No. 156789,
    # NMNH" oder "voucher Specimen No. 4302". Der obligatorische ``N(?:o|umber)``-
    # Marker verhindert falsche Positives fuer bare ``Spec 43`` und fuer die
    # ``Spec``-startenden EN-Woerter (``Special``, ``Species``, ``Specific``,
    # ``Spectrum``, ``Speculate``, ``Speech``). Kollisionsfrei zu Cat/Acc/Reg/Field/
    # Coll (disjunkte Anfangs-Buchstaben) und zu allen DE-Praefixen.
    re.compile(r"^Spec(?:imen)?\.?[-.\s]*N(?:o|umber)\.?\s*(\d+)$", re.IGNORECASE),
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
