"""CLI fuer Sammlungs-Kennzahlen.

Beispiele:
    python -m stonebook.db.stats_cli                     # Default-DB, Text
    python -m stonebook.db.stats_cli --json              # JSON-Ausgabe
    python -m stonebook.db.stats_cli --db <pfad>
    python -m stonebook.db.stats_cli --top 20            # Top-Listen verlaengern
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from stonebook.db.database import connect, default_db_file
from stonebook.db.stats import Statistik, compute_statistics


DEFAULT_TOP_N = 10


def _format_text(st: Statistik, top: int = DEFAULT_TOP_N) -> str:
    lines = [
        "Sammlungs-Uebersicht",
        "====================",
        f"Objekte gesamt:        {st.objekte_total}",
        f"  aktiv:               {st.objekte_aktiv}",
        f"  platzhalter:         {st.objekte_platzhalter}",
        f"  archiviert:          {st.objekte_archiviert}",
        f"Bilder:                {st.bilder_total} "
        f"(in {st.objekte_mit_bildern} Objekten)",
        f"Aliase (Merges):       {st.aliase_total}",
        f"KI-Analysen:           {st.ki_analysen_total} "
        f"(in {st.objekte_mit_ki_analyse} Objekten, "
        f"{st.ki_analysen_uebernommen} uebernommen)",
        f"Mineral-Arten:         {st.mineral_arten_total}",
        f"Fundorte:              {st.fundorte_total}",
        "",
        f"Wert (Summe, CHF):     {st.wert_summe_chf:,.0f}",
        f"  davon Roh:           {st.wert_roh_summe_chf:,.0f}",
        f"  Objekte mit Wert:    {st.objekte_mit_wert}",
        f"  Maximaler Einzelwert:{st.wert_max_chf:,.0f}",
        f"Gewicht (Summe, g):    {st.gewicht_summe_g:,.1f}",
        f"  Objekte mit Gewicht: {st.objekte_mit_gewicht}",
    ]
    # Durchschnitt + Median fuer Wert/Gewicht direkt unter den Summenzeilen;
    # nur ausgeben, wenn ueberhaupt Werte vorliegen (sonst sind die Felder 0.0
    # und wuerden den Bericht mit nichtssagenden Nullzeilen belasten).
    if st.objekte_mit_wert:
        lines.append(f"  Ø Wert (CHF):        {st.wert_durchschnitt_chf:,.0f}")
        lines.append(f"  Median Wert (CHF):   {st.wert_median_chf:,.0f}")
    if st.objekte_mit_gewicht:
        lines.append(f"  Ø Gewicht (g):       {st.gewicht_durchschnitt_g:,.1f}")
        lines.append(f"  Median Gewicht (g):  {st.gewicht_median_g:,.1f}")
        lines.append(f"  Maximales Gewicht:   {st.gewicht_max_g:,.1f}")
    if st.funddatum_frueheste or st.funddatum_spaeteste:
        # Spanne nur anzeigen, wenn ueberhaupt ein gueltiges Funddatum vorliegt.
        # Beide Grenzen werden gemeinsam ausgewiesen; identische Werte
        # erscheinen als "X .. X" (transparent fuer den Leser).
        lines.append(
            f"Funddatum-Spanne:      {st.funddatum_frueheste or '?'} "
            f".. {st.funddatum_spaeteste or '?'}")
    if st.durchschnitt_confidence_prozent is not None:
        lines.append(
            f"Ø Confidence:          {st.durchschnitt_confidence_prozent:.1f} %")
    if st.median_confidence_prozent is not None:
        # Median liegt direkt unter Mittel; Reihenfolge spiegelt das Werte-/Gewicht-Layout.
        lines.append(
            f"Median Confidence:     {st.median_confidence_prozent:.1f} %")
    # Coverage-Quoten beantworten "Wie viel meiner Sammlung ist dokumentiert?"
    # Nur ausgeben, wenn ueberhaupt Objekte vorhanden sind (sonst sind alle
    # Quoten None und die Zeilen waeren nichtssagend).
    if st.objekte_total > 0:
        lines += ["", "Coverage:"]
        lines.append(f"  Bilder:              {st.quote_mit_bildern_prozent:.1f} %")
        lines.append(f"  Funddatum:           {st.quote_mit_funddatum_prozent:.1f} %")
        lines.append(f"  Wertschaetzung:      {st.quote_mit_wert_prozent:.1f} %")
    if st.confidence_buckets and any(st.confidence_buckets.values()):
        lines += ["", "Confidence-Verteilung:"]
        for label, n in st.confidence_buckets.items():
            lines.append(f"  {label:>6s}              {n}")
    if st.bilder_by_kategorie:
        # Foto-Coverage pro Kategorie: zeigt, ob z.B. UV-/Mikroskop-Aufnahmen
        # noch flaechig fehlen. Aufsteigende Sortierung nach Anzahl wuerde die
        # Loecher verstecken; bleibt also bei der Default-Reihenfolge der
        # Statistik (absteigend nach Anzahl).
        lines += ["", "Bilder pro Kategorie:"]
        for kat, n in st.bilder_by_kategorie.items():
            lines.append(f"  {kat:40s} {n}")
    if st.by_mineral:
        lines += ["", "Top-Minerale:"]
        for name, n in list(st.by_mineral.items())[:top]:
            lines.append(f"  {name:40s} {n}")
    if st.by_varietaet:
        # Feinere Sicht unter den Hauptmineralen: Quarz-Familie zerfaellt in
        # Bergkristall/Milchquarz/Rauchquarz, Jaspis-Familie in Roter/Bunter/
        # Brekzien-Jaspis usw. Ergaenzt by_mineral (mineralogische Hauptgruppe).
        lines += ["", "Top-Varietaeten:"]
        for name, n in list(st.by_varietaet.items())[:top]:
            lines.append(f"  {name:40s} {n}")
    if st.by_gesteinsart:
        # Petrologische Sicht: Granit/Gneis/Basalt/Sandstein. Weder Mineral-
        # noch Varietaet-Sicht zeigen das (die laufen auf mineralogischer
        # Ebene); hier die uebergeordnete Gesteins-Gruppierung.
        lines += ["", "Top-Gesteinsarten:"]
        for name, n in list(st.by_gesteinsart.items())[:top]:
            lines.append(f"  {name:40s} {n}")
    if st.by_fundort:
        lines += ["", "Top-Fundorte:"]
        for name, n in list(st.by_fundort.items())[:top]:
            lines.append(f"  {name:40s} {n}")
    if st.by_kategorie:
        # Komplementaer zu Wert-/Gewicht-pro-Kategorie: zeigt die schiere Anzahl
        # pro Objekt-Kategorie (Handstueck/Kristall/Geroell/...). Ohne Anzahl
        # erkennt der Leser nicht, ob eine Kategorie das Gewicht/den Wert ueber
        # wenige grosse Stuecke oder ueber Masse erzeugt.
        lines += ["", "Objekte pro Kategorie:"]
        for name, n in list(st.by_kategorie.items())[:top]:
            lines.append(f"  {name:40s} {n}")
    if st.by_kristallsystem:
        # Kristallographische Anzahl-Sicht: wieviele Stuecke pro Symmetrietyp?
        # Komplementaer zu wert_/gewicht_pro_kristallsystem (CLI weiter unten):
        # zeigt nicht den Wert-, sondern den Bestand-Schwerpunkt. Trigonal-Quarz
        # dominiert haeufig die Stueck-Zahl, waehrend kubisch (Pyrit/Granat)
        # ueber Einzelstuecke den Wert hebt. Reihenfolge aus _count_by:
        # absteigend nach Anzahl, dann alphabetisch.
        lines += ["", "Objekte pro Kristallsystem:"]
        for name, n in list(st.by_kristallsystem.items())[:top]:
            lines.append(f"  {name:40s} {n}")
    if st.by_glanz:
        # Optische Anzahl-Sicht: wieviele Stuecke pro Glanztyp? Komplementaer
        # zu wert_/gewicht_pro_glanz (CLI weiter unten): zeigt die rohe
        # Stueck-Zahl pro Oberflaechen-Charakteristik (glasig/metallisch/matt/...).
        # Glasige Quarze stellen oft die Masse der Stuecke, metallische Pyrit-
        # /Galenit-Stuecke das wertdominante Segment - der Block trennt die
        # beiden Effekte. Reihenfolge aus _count_by: absteigend nach Anzahl,
        # dann alphabetisch.
        lines += ["", "Objekte pro Glanz:"]
        for name, n in list(st.by_glanz.items())[:top]:
            lines.append(f"  {name:40s} {n}")
    if st.by_transparenz:
        # Lichtdurchlaessigkeits-Anzahl-Sicht: wieviele Stuecke pro Transparenz-
        # Klasse (durchsichtig/durchscheinend/opak)? Komplementaer zu
        # wert_/gewicht_pro_transparenz (CLI weiter unten) und by_glanz
        # (Oberflaechen-Reflexion vs. Volumen-Lichtgang): zwei Achsen der
        # optischen Charakteristik, die das Foto-Setup unterschiedlich
        # vorbereiten (Backlight noetig vs. Frontlight reicht). Reihenfolge
        # aus _count_by: absteigend nach Anzahl, dann alphabetisch.
        lines += ["", "Objekte pro Transparenz:"]
        for name, n in list(st.by_transparenz.items())[:top]:
            lines.append(f"  {name:40s} {n}")
    if st.by_magnetismus:
        # Magnetismus-Anzahl-Sicht: wieviele Stuecke reagieren auf den Magneten?
        # Drei Enum-Werte (ja/schwach/nein); typisches Profil ist nein-lastig
        # (Quarz/Calcit) mit kleinem ja-Anteil (Magnetit/Pyrrhotin). Komplementaer
        # zu wert_/gewicht_pro_magnetismus (CLI weiter unten): zeigt nicht den
        # Eisen-bedingten Wertbeitrag, sondern den Bestand-Anteil - praktisch
        # vor Sortier-Aktionen mit dem Hand-Magneten. Reihenfolge aus _count_by:
        # absteigend nach Anzahl, dann alphabetisch.
        lines += ["", "Objekte pro Magnetismus:"]
        for name, n in list(st.by_magnetismus.items())[:top]:
            lines.append(f"  {name:40s} {n}")
    if st.by_spaltbarkeit:
        # Spaltbarkeits-Anzahl-Sicht: wieviele Stuecke pro Spaltflaechen-Klasse
        # (vollkommen/gut/deutlich/undeutlich/keine)? Komplementaer zu
        # wert_/gewicht_pro_spaltbarkeit (CLI weiter unten): zeigt den
        # Bestand-Schwerpunkt der Spaltflaechen-Verteilung - praktisch vor
        # Praeparier-Aktionen (Calcit/Fluorit: vollkommen, lassen sich sauber
        # schneiden; Quarz: keine, nur Saegen/Polieren). Reihenfolge aus
        # _count_by: absteigend nach Anzahl, dann alphabetisch.
        lines += ["", "Objekte pro Spaltbarkeit:"]
        for name, n in list(st.by_spaltbarkeit.items())[:top]:
            lines.append(f"  {name:40s} {n}")
    if st.by_bruch:
        # Bruchverhalten-Anzahl-Sicht: wieviele Stuecke pro Bruchtyp
        # (muschelig/uneben/splittrig/faserig/erdig/glatt)? Komplementaer zu
        # wert_/gewicht_pro_bruch (CLI weiter unten) und by_spaltbarkeit
        # (Spaltflaechen vs. Bruch sind die zwei Achsen der Bearbeitungs-
        # Charakteristik): muschelig brechende Quarz-/Obsidian-Stuecke vs.
        # fasrige Aktinolith-/erdige Limonit-Brocken liegen mechanisch weit
        # auseinander. Reihenfolge aus _count_by: absteigend nach Anzahl,
        # dann alphabetisch.
        lines += ["", "Objekte pro Bruch:"]
        for name, n in list(st.by_bruch.items())[:top]:
            lines.append(f"  {name:40s} {n}")
    if st.by_funddatum_jahr:
        # Histogramm pro Fundjahr (ISO YYYY). Ergaenzt die Funddatum-Spanne oben
        # um die innere Verteilung: zeigt Sammler-Aktivitaetsphasen vs. Pausen
        # oder Schuebe bei einzelnen Exkursionen. Begrenzung erfolgt bereits in
        # _count_funddatum_jahr (top_jahre); die Anzeige bleibt chronologisch.
        lines += ["", "Funde pro Jahr:"]
        for jahr, n in st.by_funddatum_jahr.items():
            lines.append(f"  {jahr:40s} {n}")
    if st.by_funddatum_jahrzehnt:
        # Dekaden-Histogramm: grobe Sicht ohne Einzeljahres-Rauschen. Sortierung
        # bleibt chronologisch aus _count_funddatum_jahrzehnt (aelteste zuerst).
        # Ergaenzt die Jahres-Auflistung um den Blick auf Aktivitaetsphasen.
        lines += ["", "Funde pro Jahrzehnt:"]
        for dekade, n in st.by_funddatum_jahrzehnt.items():
            lines.append(f"  {dekade:40s} {n}")
    if st.by_funddatum_monat:
        # Monats-Histogramm (01..12), ueber alle Jahre aggregiert: zeigt die
        # Saison-Verteilung eines Sammler-Lebens. Komplementaer zu Jahres-/
        # Dekaden-Sicht: dort die zeitliche Achse, hier die Saisonalitaet.
        # Typische Muster sind Berg-Saison Juli/August und Boersen-Spitzen im
        # Dezember/Februar (Muenchen/Tucson). Reihenfolge bleibt 01..12.
        lines += ["", "Funde pro Monat:"]
        for monat, n in st.by_funddatum_monat.items():
            lines.append(f"  {monat:40s} {n}")
    if st.by_seltenheit_global:
        # Rarity-Histogramm 1..10: wo liegt der Bestand-Schwerpunkt der Sammlung?
        # Komplementaer zum seltenheit_global_min/max-Filter (Drill-down auf
        # einzelne Stuecke); hier die Gesamtverteilung. Reihenfolge bleibt 1..10
        # (chronologisch zur Skala), nicht nach Anzahl - sonst verzerrt die
        # Lesbarkeit des Rarity-Profils.
        lines += ["", "Seltenheit global (1..10):"]
        for stufe, n in st.by_seltenheit_global.items():
            lines.append(f"  {stufe:>40s} {n}")
    if st.by_seltenheit_fundort:
        # Fundort-Rarity-Histogramm 1..10: Standort-Seltenheit (komplementaer zur
        # globalen Sicht). Am Berner-Oberland-Hang haeufiger Quarz kann global
        # selten sein, oder umgekehrt: lokale Rarit?t aus einem ausgeschoepften
        # Stollen. Reihenfolge analog by_seltenheit_global (Skala 1..10
        # chronologisch), damit das Profil direkt vergleichbar bleibt.
        lines += ["", "Seltenheit Fundort (1..10):"]
        for stufe, n in st.by_seltenheit_fundort.items():
            lines.append(f"  {stufe:>40s} {n}")
    if st.by_nachfrage:
        # Marktnachfrage-Histogramm 1..10: wo liegt der Marktdruck-Schwerpunkt
        # der Sammlung? Komplementaer zum nachfrage_min/max-Filter (Drill-down
        # auf Verkaufs-Kandidaten); hier die Gesamtverteilung. Reihenfolge
        # bleibt 1..10 (Skala), damit das Profil direkt vergleichbar bleibt mit
        # by_seltenheit_global/by_seltenheit_fundort.
        lines += ["", "Nachfrage (1..10):"]
        for stufe, n in st.by_nachfrage.items():
            lines.append(f"  {stufe:>40s} {n}")
    if st.top_wert_objekte:
        # Sammler-typische Frage: "Was sind die hochpreisigsten Stuecke?"
        # Format: ID + Name + Wertsumme; Wert in tausenderpunktnotation.
        lines += ["", "Top-Wertobjekte (CHF):"]
        for oid, name, wert in st.top_wert_objekte[:top]:
            label = f"{oid} {name}".strip()
            lines.append(f"  {label:40s} {wert:>12,.0f}")
    if st.top_gewicht_objekte:
        lines += ["", "Top-Gewichtsobjekte (g):"]
        for oid, name, gewicht in st.top_gewicht_objekte[:top]:
            label = f"{oid} {name}".strip()
            lines.append(f"  {label:40s} {gewicht:>12,.1f}")
    if st.top_bilder_objekte:
        # Foto-Coverage pro Objekt: zeigt, welche Stuecke fotografisch am besten
        # dokumentiert sind. Komplementaer zu objekte_mit_bildern (Anzahl): nur
        # weil ein Objekt EIN Foto hat, ist es nicht gut dokumentiert; hier wird
        # die Spreizung sichtbar (5 Kategorien vs. nur Uebersicht).
        lines += ["", "Top-Foto-Objekte (Bilder):"]
        for oid, name, n in st.top_bilder_objekte[:top]:
            label = f"{oid} {name}".strip()
            lines.append(f"  {label:40s} {n:>12d}")
    if st.top_confidence_objekte:
        # Sammler-Frage: "Welche Stuecke sind am verlaesslichsten identifiziert?"
        # Komplementaer zu confidence_buckets (Verteilung): hier die konkrete
        # Spitze (mit Name/ID), nicht nur die Klassen-Histogramm-Sicht.
        lines += ["", "Top-Confidence-Objekte (%):"]
        for oid, name, c in st.top_confidence_objekte[:top]:
            label = f"{oid} {name}".strip()
            lines.append(f"  {label:40s} {c:>12d}")
    if st.wert_pro_mineral:
        # Beantwortet "Welcher Mineraltyp ist insgesamt am wertvollsten?"
        # (komplementaer zu top_wert_objekte, das das wertvollste Einzelstueck zeigt).
        # Summen aus wert_pro_objekt_sql() ueber alle CHF-Felder pro Mineral-Gruppe.
        lines += ["", "Wert pro Mineral (CHF):"]
        for mineral, wert in st.wert_pro_mineral[:top]:
            lines.append(f"  {mineral:40s} {wert:>12,.0f}")
    if st.wert_pro_varietaet:
        # Feinere Sicht unter dem Mineral: Bergkristall vs. Milchquarz innerhalb
        # der Quarz-Familie laufen wertlich oft weit auseinander. Komplementaer
        # zu wert_pro_mineral (Hauptgruppe) und by_varietaet (Anzahl).
        lines += ["", "Wert pro Varietaet (CHF):"]
        for var, wert in st.wert_pro_varietaet[:top]:
            lines.append(f"  {var:40s} {wert:>12,.0f}")
    if st.wert_pro_gesteinsart:
        # Petrologische Wert-Sicht: Granit/Gneis/Basalt/Sandstein-Klassen liegen
        # oft auf unterschiedlichen Preisniveaus (Edelgranite vs. Halden-Basalt).
        # Komplementaer zu by_gesteinsart (Anzahl).
        lines += ["", "Wert pro Gesteinsart (CHF):"]
        for ges, wert in st.wert_pro_gesteinsart[:top]:
            lines.append(f"  {ges:40s} {wert:>12,.0f}")
    if st.wert_pro_fundort:
        # Komplementaer zu by_fundort (Anzahl): zeigt den Fundort mit dem hoechsten
        # Sammlungs-Gesamtwert. Hilft bei Versicherungseinschaetzung pro Region und
        # zeigt, ob viele guenstige Stuecke einen Ort dominieren oder wenige teure.
        lines += ["", "Wert pro Fundort (CHF):"]
        for ort, wert in st.wert_pro_fundort[:top]:
            lines.append(f"  {ort:40s} {wert:>12,.0f}")
    if st.wert_pro_kategorie:
        # Drittes Schnittmuster (nach Mineral/Fundort): welche Objekt-Kategorie
        # (Handstueck, Kristall, Geroell, ...) traegt am meisten zum Sammlungswert
        # bei? Beantwortet "wo steckt das Geld in der Sammlungs-Typologie?".
        lines += ["", "Wert pro Kategorie (CHF):"]
        for kat, wert in st.wert_pro_kategorie[:top]:
            lines.append(f"  {kat:40s} {wert:>12,.0f}")
    if st.wert_pro_kristallsystem:
        # Kristallographische Sicht: welcher Symmetrietyp dominiert wertmaessig?
        # Komplementaer zu by_kristallsystem (Anzahl) - hier zaehlt der Sammlungswert
        # pro Kristallsystem (trigonal/kubisch/hexagonal/...).
        lines += ["", "Wert pro Kristallsystem (CHF):"]
        for ks, wert in st.wert_pro_kristallsystem[:top]:
            lines.append(f"  {ks:40s} {wert:>12,.0f}")
    if st.wert_pro_beste_verwendung:
        # Verwendungs-Sicht: wo steckt der Wert je Empfehlung? Sammler-Frage
        # "lohnt sich Schmuck-Verkauf, oder steckt der Wert in Sammler-/
        # Forschungs-Stuecken?" - der Block macht das transparent.
        lines += ["", "Wert pro Beste-Verwendung (CHF):"]
        for bv, wert in st.wert_pro_beste_verwendung[:top]:
            lines.append(f"  {bv:40s} {wert:>12,.0f}")
    if st.wert_pro_status:
        # Lifecycle-Sicht: wo steckt der Wert nach Pflegezustand? Beantwortet
        # Sammler-Fragen wie "wieviel Sammlungswert habe ich schon erfasst (aktiv)
        # vs. noch zu erfassen (platzhalter) vs. weggelegt (archiviert)?"
        lines += ["", "Wert pro Status (CHF):"]
        for status, wert in st.wert_pro_status:
            lines.append(f"  {status:40s} {wert:>12,.0f}")
    if st.gewicht_pro_mineral:
        # Spiegelbild zu wert_pro_mineral: welcher Mineraltyp dominiert die Sammlung
        # gewichtsmaessig? Wert und Gewicht sind oft entkoppelt (viele kleine teure
        # vs. wenige grosse guenstige Stuecke); deshalb beide Sichten anbieten.
        lines += ["", "Gewicht pro Mineral (g):"]
        for mineral, gewicht in st.gewicht_pro_mineral[:top]:
            lines.append(f"  {mineral:40s} {gewicht:>12,.1f}")
    if st.gewicht_pro_varietaet:
        # Spiegelbild zu wert_pro_varietaet: welche Varietaet dominiert
        # gewichtsmaessig? Milchquarz-Geroelle vs. wenige feine Bergkristalle
        # zeigen die Wert/Gewicht-Entkopplung auf Varietaet-Ebene.
        lines += ["", "Gewicht pro Varietaet (g):"]
        for var, gewicht in st.gewicht_pro_varietaet[:top]:
            lines.append(f"  {var:40s} {gewicht:>12,.1f}")
    if st.gewicht_pro_gesteinsart:
        # Spiegelbild zu wert_pro_gesteinsart: welche Gesteinsart bringt die
        # meiste Masse? Basalt-/Granit-Geroelle dominieren oft die Sammlung
        # gewichtsmaessig, ohne wertlich vorne zu liegen.
        lines += ["", "Gewicht pro Gesteinsart (g):"]
        for ges, gewicht in st.gewicht_pro_gesteinsart[:top]:
            lines.append(f"  {ges:40s} {gewicht:>12,.1f}")
    if st.gewicht_pro_fundort:
        # Spiegelbild zu wert_pro_fundort: welcher Fundort dominiert gewichtsmaessig?
        # Aufschluss-/Halden-Funde liefern oft viel Masse fuer geringen Wert; das
        # macht der Block sichtbar (komplementaer zur Wert-Sicht).
        lines += ["", "Gewicht pro Fundort (g):"]
        for ort, gewicht in st.gewicht_pro_fundort[:top]:
            lines.append(f"  {ort:40s} {gewicht:>12,.1f}")
    if st.gewicht_pro_kategorie:
        # Spiegelbild zu wert_pro_kategorie: welche Objekt-Kategorie dominiert
        # gewichtsmaessig? Grosse Handstuecke vs. viele kleine Kristalle werden
        # so sichtbar, auch wenn der monetaere Wert vergleichbar bleibt.
        lines += ["", "Gewicht pro Kategorie (g):"]
        for kat, gewicht in st.gewicht_pro_kategorie[:top]:
            lines.append(f"  {kat:40s} {gewicht:>12,.1f}")
    if st.gewicht_pro_kristallsystem:
        # Spiegelbild zu wert_pro_kristallsystem: welcher Symmetrietyp traegt die
        # meiste Masse? Bei Quarz-/Pyrit-Sammlungen oft entkoppelt vom Wert.
        lines += ["", "Gewicht pro Kristallsystem (g):"]
        for ks, gewicht in st.gewicht_pro_kristallsystem[:top]:
            lines.append(f"  {ks:40s} {gewicht:>12,.1f}")
    if st.gewicht_pro_beste_verwendung:
        # Spiegelbild zu wert_pro_beste_verwendung: Industrie/Dekoration oft
        # schwer, Schmuck oft leicht aber hochpreisig - die Wert/Gewicht-
        # Entkopplung wird je Verwendungs-Kategorie sichtbar.
        lines += ["", "Gewicht pro Beste-Verwendung (g):"]
        for bv, gewicht in st.gewicht_pro_beste_verwendung[:top]:
            lines.append(f"  {bv:40s} {gewicht:>12,.1f}")
    if st.gewicht_pro_status:
        # Spiegelbild zu wert_pro_status: welche Gewichts-Masse haengt noch in
        # platzhaltern? Komplementaer fuer Versicherungsabschaetzung pro Lifecycle.
        lines += ["", "Gewicht pro Status (g):"]
        for status, gewicht in st.gewicht_pro_status:
            lines.append(f"  {status:40s} {gewicht:>12,.1f}")
    if st.wert_pro_funddatum_jahr:
        # Sammler-Frage "welches war mein wertvollstes Jahr?": Wert-Summe pro
        # Funddatum-Jahr, absteigend - komplementaer zu by_funddatum_jahr
        # (Anzahl) und Top-Wertobjekten (Einzelstueck-Sicht).
        lines += ["", "Wert pro Funddatum-Jahr (CHF):"]
        for jahr, wert in st.wert_pro_funddatum_jahr[:top]:
            lines.append(f"  {jahr:40s} {wert:>12,.0f}")
    if st.gewicht_pro_funddatum_jahr:
        # Spiegelbild: schwerstes Sammeljahr. Wert und Gewicht entkoppeln sich
        # haeufig (eine Saison schwerer Geroelle vs. eine Saison kleiner
        # Kristalle), deshalb beide Sichten anbieten.
        lines += ["", "Gewicht pro Funddatum-Jahr (g):"]
        for jahr, gewicht in st.gewicht_pro_funddatum_jahr[:top]:
            lines.append(f"  {jahr:40s} {gewicht:>12,.1f}")
    if st.wert_pro_funddatum_jahrzehnt:
        # Dekaden-Sicht des Sammlungswerts: groberes Raster gegen Einzeljahr-
        # Rauschen. Komplementaer zu by_funddatum_jahrzehnt (Anzahl) und
        # wert_pro_funddatum_jahr (Einzeljahres-Aufloesung).
        lines += ["", "Wert pro Funddatum-Jahrzehnt (CHF):"]
        for dekade, wert in st.wert_pro_funddatum_jahrzehnt:
            lines.append(f"  {dekade:40s} {wert:>12,.0f}")
    if st.gewicht_pro_funddatum_jahrzehnt:
        # Spiegelbild Gewicht: welche Dekade brachte die meiste Masse?
        # Bei zeitlich konzentrierten Schwerstuecken sind die Dekaden ein
        # klareres Signal als das Einzeljahr.
        lines += ["", "Gewicht pro Funddatum-Jahrzehnt (g):"]
        for dekade, gewicht in st.gewicht_pro_funddatum_jahrzehnt:
            lines.append(f"  {dekade:40s} {gewicht:>12,.1f}")
    if st.wert_pro_funddatum_monat:
        # Saison-Ertrag in CHF: welcher Monat bringt ueber alle Jahre den meisten
        # Wert? Komplementaer zu by_funddatum_monat (Anzahl) - dort die Aktivitaet,
        # hier der Ertrag. Reihenfolge: absteigend nach Summe (top zuerst), damit
        # der "beste Monat" ohne Suchen sichtbar ist.
        lines += ["", "Wert pro Funddatum-Monat (CHF):"]
        for monat, wert in st.wert_pro_funddatum_monat:
            lines.append(f"  {monat:40s} {wert:>12,.0f}")
    if st.gewicht_pro_funddatum_monat:
        # Spiegelbild Gewicht: welcher Monat bringt die meiste Masse? Berg-Saison
        # vs. Boersen-Spitzen entkoppeln sich oft (Boerse = wenige hochpreisige
        # Kleinstuecke, Berg = schwere Handstuecke).
        lines += ["", "Gewicht pro Funddatum-Monat (g):"]
        for monat, gewicht in st.gewicht_pro_funddatum_monat:
            lines.append(f"  {monat:40s} {gewicht:>12,.1f}")
    return "\n".join(lines)


def _build_arg_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="python -m stonebook.db.stats_cli",
        description="Gibt aggregierte StoneBook-Kennzahlen aus.",
    )
    p.add_argument("--db", type=Path, default=None,
                   help="Pfad zur SQLite-DB (Default: <repo>/data/db/stonebook.sqlite3).")
    p.add_argument("--json", action="store_true",
                   help="Gibt das vollstaendige Statistik-Objekt als JSON aus.")
    p.add_argument("--top", type=int, default=DEFAULT_TOP_N,
                   help=f"Anzahl Eintraege in den Top-Listen (Default: {DEFAULT_TOP_N}).")
    return p


def main(argv: list[str] | None = None) -> int:
    args = _build_arg_parser().parse_args(argv)
    db_file = args.db if args.db else default_db_file()
    if not db_file.is_file():
        print(f"DB-Datei fehlt: {db_file}", file=sys.stderr)
        return 2
    if args.top < 1:
        print(f"--top muss >= 1 sein (war: {args.top})", file=sys.stderr)
        return 2
    conn = connect(db_file)
    try:
        # ``top`` wirkt auf alle Top-Aggregate gleichzeitig; eine feinere
        # Auspartitionierung (pro Liste) lohnt sich aus User-Sicht nicht.
        st = compute_statistics(
            conn, top_fundorte=args.top, top_wert=args.top,
            top_jahre=args.top,
            top_wert_mineral=args.top, top_gewicht_mineral=args.top,
            top_wert_varietaet=args.top, top_gewicht_varietaet=args.top,
            top_wert_gesteinsart=args.top, top_gewicht_gesteinsart=args.top,
            top_wert_fundort=args.top, top_gewicht_fundort=args.top,
            top_wert_kategorie=args.top, top_gewicht_kategorie=args.top,
            top_wert_kristallsystem=args.top,
            top_gewicht_kristallsystem=args.top,
            top_wert_beste_verwendung=args.top,
            top_gewicht_beste_verwendung=args.top,
            top_gewicht=args.top, top_bilder=args.top,
            top_confidence=args.top,
            top_wert_funddatum_jahr=args.top,
            top_gewicht_funddatum_jahr=args.top)
    finally:
        conn.close()
    if args.json:
        json.dump(st.as_dict(), sys.stdout, ensure_ascii=False, indent=1)
        sys.stdout.write("\n")
    else:
        print(_format_text(st, top=args.top))
    return 0


if __name__ == "__main__":
    sys.exit(main())
