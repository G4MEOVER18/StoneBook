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
        f"Aliase (Merges):       {st.aliase_total} "
        f"(in {st.objekte_mit_alias} Kanon-Objekten)",
        f"KI-Analysen:           {st.ki_analysen_total} "
        f"(in {st.objekte_mit_ki_analyse} Objekten, "
        f"{st.ki_analysen_uebernommen} uebernommen "
        f"in {st.objekte_mit_ki_analyse_uebernommen} Objekten)",
        f"Mineral-Arten:         {st.mineral_arten_total}",
        f"Fundorte:              {st.fundorte_total}",
        # Kategorien-Arten: Diversitaets-Zaehler parallel zu Mineral-Arten
        # und Fundorten - Anzahl distinct dokumentierter Objekt-Kategorien
        # (Handstueck/Kristall/Duennschliff/...). Steht direkt unter Fundorten,
        # weil Kategorie die vorgelagerte Inventar-Klassifizierungs-Achse ist
        # ("wie viele Objekt-Typen sammle ich?") - komplementaer zu Mineral-Arten
        # (mineralogisch) und Fundorten (geografisch): die drei zentralen
        # Diversitaets-Achsen der Sammlung. Bei leerer DB / ohne jegliche
        # Kategorie-Pflege bleibt 0 (spiegelt Mineral-Arten / Fundorten-
        # Konvention: Zeile immer ausgeben, damit der Header-Block deterministisch
        # bleibt und das Kennzahlen-Trio in jedem Bericht an derselben Stelle steht).
        f"Kategorien-Arten:      {st.kategorien_total}",
        # Varietaeten: Diversitaets-Zaehler auf der mineralogischen Sub-
        # Klassifizierungs-Achse (Bergkristall/Amethyst/Rauchquarz innerhalb
        # Quarz; Malachit-Stalaktit als Habitus-Auspraegung innerhalb Malachit).
        # Steht direkt unter Kategorien-Arten, weil Varietaet die feinere
        # Auspraegung innerhalb der Mineral-Familie ist - Mineral-Arten zaehlt
        # "welche Familie?", Varietaeten "welche Auspraegung in der Familie?".
        # Vervollstaendigt das Diversitaets-Quartett Mineral-Arten / Fundorte /
        # Kategorien-Arten / Varietaeten. Bei leerer DB / ohne jegliche
        # Varietaet-Pflege bleibt 0 (spiegelt die uebrigen Diversitaets-Zaehler:
        # Zeile immer ausgeben, damit der Header-Block deterministisch bleibt).
        f"Varietaeten:           {st.varietaeten_total}",
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
        lines.append(f"  Minimaler Einzelwert:{st.wert_min_chf:,.0f}")
        # sigma Wert: Dispersions-Achse zur zentralen-Tendenz-Achse.
        # Spiegelt sigma Gewicht auf die monetaere Wert-Achse - waehrend
        # Durchschnitt und Median den typischen Objekt-Wert beziffern,
        # beziffert die Standardabweichung die versicherungsrelevante
        # Streuung um den Durchschnitt. Am Ende des Wert-Blocks (nach Ø/
        # Median/Min), spiegelt die Gewicht-Reihenfolge.
        lines.append(
            f"  σ Wert (CHF):        {st.wert_standardabweichung_chf:,.0f}")
        # CV Wert (%): dimensionsloser Variationskoeffizient (sigma/mean *
        # 100). Ergaenzt sigma um die skalen-unabhaengige Streuungs-Sicht -
        # eine 500-CHF-Sammlung mit sigma 50 und eine 5000-CHF-Sammlung mit
        # sigma 500 haben identische relative Streuung (beide CV 10%),
        # obwohl die Absolutwerte weit auseinanderliegen. Beantwortet damit
        # "wie homogen ist meine Sammlung wertlich, unabhaengig vom Preis-
        # Niveau?" - Feldspat-Klasse ~10%, gemischte Sammlung mit
        # Investment-Bergkristallen mehrere hundert Prozent. Direkt unter
        # der sigma-Zeile, damit der Dispersions-Block (sigma + CV) als
        # geschlossene Einheit sichtbar bleibt. Guard is not None: bei
        # objekte_mit_wert > 0 immer definiert (wert_sql > 0 sichert
        # mean > 0), aber die None-Pruefung entkoppelt die CLI von der
        # Compute-Guard und laesst sich auch auf leere Sammlungen (Default
        # None) sauber uebertragen, falls das Bericht-Rendering spaeter
        # ausserhalb des objekte_mit_wert-Zweigs aufgerufen wird.
        if st.wert_variationskoeffizient_prozent is not None:
            lines.append(
                f"  CV Wert (%):         "
                f"{st.wert_variationskoeffizient_prozent:,.1f}")
    if st.objekte_mit_gewicht:
        lines.append(f"  Ø Gewicht (g):       {st.gewicht_durchschnitt_g:,.1f}")
        lines.append(f"  Median Gewicht (g):  {st.gewicht_median_g:,.1f}")
        lines.append(f"  Minimales Gewicht:   {st.gewicht_min_g:,.1f}")
        lines.append(f"  Maximales Gewicht:   {st.gewicht_max_g:,.1f}")
        # sigma Gewicht: Dispersions-Achse zur zentralen-Tendenz-Achse.
        # Waehrend Durchschnitt und Median das typische Stueck beziffern,
        # beziffert die Standardabweichung die Streuung der Massen um den
        # Durchschnitt - spiegelt sigma Mohs / sigma Dichte auf die Massen-Achse.
        # Am Ende des Gewicht-Blocks (nach Extrema), damit der Extrema-Block
        # zusammen bleibt und die Dispersions-Zeile abschliesst.
        lines.append(
            f"  σ Gewicht (g):       {st.gewicht_standardabweichung_g:,.1f}")
        # CV Gewicht (%): dimensionsloser Variationskoeffizient (sigma/mean *
        # 100) auf der Massen-Achse. Spiegelt CV Wert (%) auf die Gewicht-
        # Achse - waehrend sigma die Streuung in Original-Einheiten g
        # beziffert, normiert der CV sigma auf den Durchschnitt und macht
        # die Massen-Streuung skalen-unabhaengig vergleichbar. Mineralkorn-
        # Sammlung mit Ø 5 g und sigma 0.5 vs. Handstueck-Sammlung mit Ø
        # 500 g und sigma 50 haben identische relative Streuung (beide CV
        # 10%), obwohl die Absolutwerte um Faktor 100 auseinanderliegen.
        # Direkt unter der sigma-Zeile, damit der Dispersions-Block
        # (sigma + CV) als geschlossene Einheit am Ende des Gewicht-
        # Blocks sichtbar bleibt (spiegelt die CV Wert (%)-Position im
        # Wert-Block).
        if st.gewicht_variationskoeffizient_prozent is not None:
            lines.append(
                f"  CV Gewicht (%):      "
                f"{st.gewicht_variationskoeffizient_prozent:,.1f}")
    if st.funddatum_frueheste or st.funddatum_spaeteste:
        # Spanne nur anzeigen, wenn ueberhaupt ein gueltiges Funddatum vorliegt.
        # Beide Grenzen werden gemeinsam ausgewiesen; identische Werte
        # erscheinen als "X .. X" (transparent fuer den Leser).
        lines.append(
            f"Funddatum-Spanne:      {st.funddatum_frueheste or '?'} "
            f".. {st.funddatum_spaeteste or '?'}")
    if st.erstellt_am_frueheste or st.erstellt_am_spaeteste:
        # Erfassungs-Spanne: spiegelt Funddatum-Spanne auf die erstellt_am-Achse.
        # Beantwortet "seit wann digitalisiere ich diese Sammlung?" und macht die
        # Sammler-typischen zwei Zeit-Achsen sichtbar (Fund-Zeit vs. Erfassungs-Zeit).
        # Voller Zeitstempel inkl. HH:MM:SS bleibt erhalten (erstellt_am hat
        # Sekunden-Aufloesung, anders als Funddatum mit reiner Tag-Aufloesung).
        lines.append(
            f"Erfassungs-Spanne:     {st.erstellt_am_frueheste or '?'} "
            f".. {st.erstellt_am_spaeteste or '?'}")
    if st.geaendert_am_frueheste or st.geaendert_am_spaeteste:
        # Aenderungs-Spanne: vervollstaendigt das Zeit-Spannen-Trio (Fund /
        # Erfassung / Aenderung). Minimum verraet nie-aktualisierte Alt-Eintraege,
        # Maximum nennt die letzte Datenpflege-Aktivitaet im gesamten Bestand
        # ("Wann war meine letzte Pflege-Sitzung?"). Voller Zeitstempel wie
        # bei der Erfassungs-Spanne (Sekunden-Aufloesung im _now()-Format).
        lines.append(
            f"Aenderungs-Spanne:     {st.geaendert_am_frueheste or '?'} "
            f".. {st.geaendert_am_spaeteste or '?'}")
    if st.koordinaten_bbox is not None:
        # Koordinaten-Spanne: minimal-umschliessende geografische Bounding-Box
        # ueber alle per parse_coordinates erkannten Fundort-Eintraege - die
        # natuerliche Aggregations-Achse zur punktuellen list_objects_in_bbox-
        # Suche (waehrend list_objects_in_bbox eine vom Caller vorgegebene Box
        # abfragt, liefert die Aggregation die Sammlungs-Extent). Beziffert
        # 'wie weit reicht meine Sammlung geografisch?' tagesgenau in Lat/Lon
        # statt im Fundort-Freitext. Direkt unter dem Aenderungs-/Erfassungs-/
        # Funddatum-Spannen-Trio einsortiert, weil alle vier Spannen aeussere
        # Grenzwerte des Bestands beziffern (drei Zeit-Achsen, eine geografische
        # Achse). Format: 'lat A..B, lon C..D' mit 4 Nachkomma-Stellen (~11 m
        # geodaetische Aufloesung am Aequator, ausreichend fuer Fundort-Genauigkeit
        # und konsistent mit der ueblichen Sammler-Notation). Bei genau einem
        # geocoded-Stueck kollabiert die Box zur Punkt-Box (lat A..A, lon C..C);
        # bei null geocoded-Stuecken bleibt der Block aus (Bedingung is not None).
        lat_min, lat_max, lon_min, lon_max = st.koordinaten_bbox
        lines.append(
            f"Koordinaten-Spanne:    "
            f"lat {lat_min:.4f}..{lat_max:.4f}, "
            f"lon {lon_min:.4f}..{lon_max:.4f}")
    if st.koordinaten_zentrum is not None:
        # Koordinaten-Zentrum: arithmetischer Schwerpunkt aller geocoded
        # Fundort-Eintraege - geometrische Schwerpunkts-Achse zur Extent-
        # Achse Koordinaten-Spanne. Beantwortet "wo liegt der Schwerpunkt
        # meiner Sammlung?" und ist die natuerliche Default-Wahl fuer den
        # Mittelpunkt der list_objects_nearest-Sicht ("welche N Stuecke
        # liegen meinem Sammlungs-Schwerpunkt am naechsten?"). Steht direkt
        # unter der Koordinaten-Spanne, weil beide Achsen die gleiche
        # geografische Aggregations-Sicht bedienen (Extent + Centroid =
        # vollstaendige geografische Beschreibung). 4 Nachkomma-Stellen
        # spiegeln die Box-Notation (~11 m Aufloesung, ausreichend fuer
        # Fundort-Genauigkeit).
        lat_c, lon_c = st.koordinaten_zentrum
        lines.append(
            f"Koordinaten-Zentrum:   "
            f"lat {lat_c:.4f}, lon {lon_c:.4f}")
    if st.koordinaten_radius_max_km is not None:
        # Koordinaten-Radius: maximale geodaetische Distanz vom Zentrum zu
        # einem geocoded Stueck - Streuungs-Achse zum Extent (Koordinaten-
        # Spanne) und Centroid (Koordinaten-Zentrum). Beziffert die
        # geodaetische Reichweite der Sammlung vom Schwerpunkt aus und ist
        # der natuerliche Default-Radius fuer list_objects_in_radius mit
        # Zentrum als Mittelpunkt (kleinste Disk um den Schwerpunkt, die
        # alle geocoded Stuecke umfasst). Steht direkt unter dem Koordinaten-
        # Zentrum, weil Extent/Centroid/Spread konzeptionell zusammen die
        # vollstaendige geografische Beschreibung der Sammlung bilden.
        # 1 Nachkommastelle (~100 m Aufloesung) reicht fuer die Sammler-
        # Sicht aus und vermeidet Schein-Genauigkeit jenseits der
        # parse_coordinates-Eingabe-Genauigkeit.
        lines.append(
            f"Koordinaten-Radius:    "
            f"{st.koordinaten_radius_max_km:.1f} km")
    if st.koordinaten_radius_durchschnitt_km is not None:
        # Koordinaten-Radius Ø: arithmetisches Mittel der Haversine-Distanzen
        # vom Zentrum zu jedem geocoded Stueck - robuste "typische Streuung"-
        # Achse zur ausreisser-dominierten Max-Achse (Koordinaten-Radius).
        # Waehrend Max die aeusserste Reichweite beziffert (ein einziger
        # Ausreisser-Fund zieht die Max-Achse hoch), gibt der Durchschnitt
        # die typische Distanz pro Stueck zum Schwerpunkt an. Die Differenz
        # beider beziffert die Ausreisser-Schiefe: symmetrisch verteilte
        # Sammlungen liegen mit Mittel nahe Max/2, stark ausreisser-dominierte
        # Sammlungen liegen mit Mittel deutlich unter Max/2. Steht direkt
        # unter dem Koordinaten-Radius (Max), weil Max und Durchschnitt das
        # paarweise Aggregations-Paar (extrem vs. typisch) ueber dieselbe
        # Streuungs-Verteilung bilden - spiegelt das Wert-/Gewicht-Max+Mittel-
        # Paar in der CLI-Reihenfolge. 1 Nachkommastelle (~100 m Aufloesung)
        # spiegelt die Max-Achsen-Notation.
        lines.append(
            f"Koordinaten-Radius Ø:  "
            f"{st.koordinaten_radius_durchschnitt_km:.1f} km")
    if st.koordinaten_radius_median_km is not None:
        # Koordinaten-Radius Median: ausreisser-robusteste der drei Streuungs-
        # Achsen (Max + Mittel + Median). Waehrend Mittel anteilig dem Aus-
        # reisser folgt, liegt der Median schlicht in der Mitte der sortierten
        # Distanzen - bei 9 Bern-Stuecken plus 1 Oslo-Stueck ist der Median
        # ein Bern-Distanz-Wert, der Mittel-Wert haengt jedoch direkt an
        # Oslo. Steht direkt unter dem Durchschnitt, weil Mittel + Median
        # das paarweise Aggregations-Paar (anfaellig vs. robust) ueber
        # dieselbe Streuungs-Verteilung bilden - spiegelt das Wert-/Gewicht-
        # Median-Layout in der CLI-Reihenfolge (Mittel direkt vor Median).
        # 1 Nachkommastelle (~100 m Aufloesung) spiegelt Max- und Mittel-
        # Achsen-Notation.
        lines.append(
            f"Median Koord.-Radius:  "
            f"{st.koordinaten_radius_median_km:.1f} km")
    if st.koordinaten_diameter_km is not None:
        # Koordinaten-Durchmesser: maximaler paarweise geodaetischer Abstand
        # zwischen je zwei geocoded Fundort-Eintraegen - die geografische
        # Sammlungs-Spannweite als Punkt-Paar-Achse zum Schwerpunkt-Radius
        # (Koordinaten-Radius). Waehrend Radius den entferntesten Punkt vom
        # Zentroid misst (Schwerpunkts-Sicht), gibt der Durchmesser den
        # echten Spannungs-Abstand zwischen den zwei aeussersten Stuecken
        # an (Punkt-Paar-Sicht). Geometrisch gilt radius_max <= diameter
        # <= 2*radius_max; die Differenz zu 2*Radius beziffert die
        # Schwerpunkts-Schiefe (bei symmetrischer Verteilung diameter ~
        # 2*radius_max, bei einseitig geclusterten Sammlungen deutlich
        # weniger). Steht direkt unter dem Median-Radius, weil Radius und
        # Durchmesser zusammen die zwei orthogonalen Auspraegungen der
        # Sammlungs-Ausdehnung bilden (vom Zentroid aus vs. zwischen
        # zwei Stuecken). 1 Nachkommastelle (~100 m Aufloesung) spiegelt
        # die Radius-Achsen-Notation.
        lines.append(
            f"Koord.-Durchmesser:    "
            f"{st.koordinaten_diameter_km:.1f} km")
    if st.mohs_kollektion_min is not None and st.mohs_kollektion_max is not None:
        # Mohs-Spanne ueber die ganze Sammlung: kleinste/groesste Mohs-Haerte
        # im dokumentierten Bestand. Spiegelt das Funddatum-/Erfassungs-/
        # Aenderungs-Spannen-Trio (drei Zeit-Achsen) und die Koordinaten-
        # Spanne (eine geografische Achse) auf die physikalische Haerte-Achse;
        # ergaenzt die Mohs-Coverage-Quote (Pflege-Sicht) um die Bandbreite-
        # Sicht ueber den gepflegten Anteil ("vom weichsten Talk-Stueck zum
        # haertesten Korund-Stueck"). Steht direkt unter dem Koordinaten-
        # Spannen-Block, weil alle "Spannen"-Zeilen aeussere Grenzwerte des
        # Bestands beziffern (Fund/Erfassung/Aenderung als Zeit, Koordinaten
        # als geografisch, Mohs als physikalische Haerte). 1 Nachkommastelle
        # reicht fuer Mohs aus (Skala 1..10 mit ueblichen 0.5-Schritten);
        # identische Werte erscheinen als "X.X .. X.X" (transparent fuer
        # den Leser, spiegelt die Funddatum-Spanne-Konvention). Block nur
        # ausgeben, wenn ueberhaupt eine Mohs-Pflege vorliegt - sonst
        # belastet die Zeile den Bericht mit nichtssagenden Nullen.
        lines.append(
            f"Mohs-Spanne:           "
            f"{st.mohs_kollektion_min:.1f} .. {st.mohs_kollektion_max:.1f}")
    if st.mohs_kollektion_durchschnitt is not None:
        # Mohs-Durchschnitt: zentrale-Tendenz-Achse zur Mohs-Spannen-Achse.
        # Waehrend die Spanne die Bandbreite beziffert ("weichstes bis
        # haertestes Stueck"), beziffert der Durchschnitt die typische Haerte
        # der Sammlung - spiegelt gewicht_durchschnitt_g/wert_durchschnitt_chf
        # auf die physikalische Haerte-Achse. Steht direkt unter der Mohs-
        # Spanne (Extent -> Zentrum), spiegelt die Werte-/Gewicht-Reihenfolge
        # (Summe/Ø/Median). Nur ausgeben, wenn ueberhaupt Mohs-Pflege
        # vorliegt - sonst nichtssagende 0.0-Zeile.
        lines.append(
            f"Ø Mohs:                {st.mohs_kollektion_durchschnitt:.1f}")
    if st.mohs_kollektion_median is not None:
        # Mohs-Median: ausreisser-robuste zentrale Tendenz zum Durchschnitt.
        # Waehrend der Durchschnitt sensibel auf einzelne Ausreisser reagiert
        # (Diamant-Splitter mit Mohs 10 in einer Calcit-lastigen Sammlung zieht
        # den Durchschnitt), bleibt der Median unempfindlich - das "typische"
        # Stueck als 50%-Quantil der Verteilung. Steht direkt unter Ø Mohs
        # (Zentrum -> robustes Zentrum), spiegelt die Werte-/Gewicht-Reihen-
        # folge (Ø + Median als paarweise zentrale Tendenz).
        lines.append(
            f"Median Mohs:           {st.mohs_kollektion_median:.1f}")
    if st.mohs_kollektion_standardabweichung is not None:
        # Mohs-Standardabweichung: Dispersions-Achse zur zentralen-Tendenz-
        # Achse (Durchschnitt/Median). Waehrend Durchschnitt und Median das
        # "typische" Stueck beziffern, beziffert die Standardabweichung die
        # Streuung der Sammlung um den Durchschnitt - eine reine Quarz-Familie
        # 5.5..6.5 zeigt hier ~0.3, eine gemischte Talk+Diamant-Sammlung
        # ~4.5. Steht direkt unter Median Mohs (Zentrum -> Streuung),
        # spiegelt das Kennzahlen-Layout Extent -> Zentrum -> Dispersion.
        # 2 Nachkommastellen, weil bei enger Streuung die erste Stelle
        # (0.3, 0.5) auf Rundungsfehler-Niveau der Populations-Formel liegen
        # kann und die zweite den Verteilungs-Kontrast lesbar macht.
        lines.append(
            f"σ Mohs:                "
            f"{st.mohs_kollektion_standardabweichung:.2f}")
    if st.mohs_kollektion_variationskoeffizient_prozent is not None:
        # CV Mohs (%): dimensionsloser Variationskoeffizient (sigma/mean *
        # 100) auf der Haerte-Achse. Spiegelt CV Wert (%) / CV Gewicht (%)
        # auf die Mohs-Achse - waehrend sigma die Streuung in Original-
        # Einheiten (Mohs-Punkte) beziffert, normiert der CV sigma auf
        # den Durchschnitt und macht die Haerte-Streuung skalen-
        # unabhaengig vergleichbar. Eine reine Quarz-Familie (Ø 6.0,
        # sigma 0.5) zeigt hier ~8%, eine Talk+Diamant-Sammlung dagegen
        # 40..70%, direkt vergleichbar mit CV Wert und CV Gewicht.
        # Direkt unter der sigma-Zeile, damit der Dispersions-Block
        # (sigma + CV) als geschlossene Einheit am Ende des Mohs-Blocks
        # sichtbar bleibt (spiegelt die CV Wert (%) / CV Gewicht (%)-
        # Position in den Wert-/Gewicht-Bloecken).
        lines.append(
            f"CV Mohs (%):           "
            f"{st.mohs_kollektion_variationskoeffizient_prozent:.1f}")
    if st.dichte_kollektion_min is not None and st.dichte_kollektion_max is not None:
        # Dichte-Spanne ueber die ganze Sammlung: kleinste/groesste Dichte
        # in g/cm3 im dokumentierten Bestand. Spiegelt die Mohs-Spanne auf
        # die zweite zentrale physikalische Pruef-Achse: waehrend Mohs die
        # Haerte-Bandbreite (1..10) beziffert, beziffert Dichte die Masse-
        # pro-Volumen-Bandbreite ("vom leichtesten Bims-/Opal-Stueck (~1.0)
        # zum schwersten Pyrit-/Galenit-Stueck (~7.5)"). Steht direkt unter
        # der Mohs-Spanne, weil Mohs und Dichte zusammen die zwei
        # quantitativen Pruef-Methoden der mineralogischen Diagnose bilden
        # (Quarz/Calcit/Fluorit-Klassen-Trennung). 2 Nachkommastellen
        # spiegeln die ueblichen Tabellenwerte aus Mineraldatenbanken
        # (Quarz 2.65, Calcit 2.71, Fluorit 3.18); identische Werte
        # erscheinen als "X.XX .. X.XX" (transparent fuer den Leser,
        # spiegelt die Mohs-Spanne-Konvention). Block nur ausgeben, wenn
        # ueberhaupt eine Dichte-Pflege vorliegt - sonst belastet die Zeile
        # den Bericht mit nichtssagenden Nullen.
        lines.append(
            f"Dichte-Spanne:         "
            f"{st.dichte_kollektion_min:.2f} .. {st.dichte_kollektion_max:.2f} g/cm3")
    if st.dichte_kollektion_durchschnitt is not None:
        # Dichte-Durchschnitt: zentrale-Tendenz-Achse zur Dichte-Spannen-Achse.
        # Waehrend die Spanne die Bandbreite beziffert ("leichtestes bis
        # schwerstes Stueck"), beziffert der Durchschnitt die typische Dichte
        # der Sammlung - spiegelt Ø Mohs auf die Massendichte-Achse. Steht
        # direkt unter der Dichte-Spanne (Extent -> Zentrum), spiegelt die
        # Mohs-Reihenfolge (Spanne + Ø). Nur ausgeben, wenn ueberhaupt
        # Dichte-Pflege vorliegt.
        lines.append(
            f"Ø Dichte:              "
            f"{st.dichte_kollektion_durchschnitt:.2f} g/cm3")
    if st.dichte_kollektion_median is not None:
        # Dichte-Median: ausreisser-robuste zentrale Tendenz zur Durchschnitts-
        # Achse. Waehrend der Durchschnitt sensibel auf einzelne Ausreisser
        # reagiert (Galenit-Stueck mit 7.5 g/cm3 in einer Quarz-lastigen
        # Sammlung zieht den Durchschnitt hoch), bleibt der Median unempfindlich
        # - das "typische" Stueck als 50%-Quantil der Verteilung. Steht direkt
        # unter Ø Dichte (Zentrum -> robustes Zentrum), spiegelt die Mohs-Reihen-
        # folge (Ø + Median als paarweise zentrale Tendenz).
        lines.append(
            f"Median Dichte:         "
            f"{st.dichte_kollektion_median:.2f} g/cm3")
    if st.dichte_kollektion_standardabweichung is not None:
        # Dichte-Standardabweichung: Dispersions-Achse zur zentralen-Tendenz-
        # Achse (Durchschnitt/Median). Spiegelt sigma Mohs auf die Dichte-Achse:
        # waehrend Durchschnitt und Median das "typische" Stueck beziffern,
        # beziffert die Standardabweichung die Streuung um den Durchschnitt -
        # eine reine Quarz-Familie (2.65..2.67) zeigt hier ~0.01, eine
        # gemischte Sammlung mit Bims bis Galenit ~2.0. Steht direkt unter
        # Median Dichte (Zentrum -> Streuung), spiegelt die Mohs-Reihenfolge
        # (Extent -> Zentrum -> Dispersion). 3 Nachkommastellen (~1 mg/cm3
        # Aufloesung), weil bei enger Streuung (0.010..0.100) die zweite
        # Stelle bereits Verteilungs-Kontrast lesbar macht, spiegelt die
        # Radius-Serialisierung auf 3 dp.
        lines.append(
            f"σ Dichte:              "
            f"{st.dichte_kollektion_standardabweichung:.3f} g/cm3")
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
        lines.append(f"  Gewicht:             {st.quote_mit_gewicht_prozent:.1f} %")
        # Dimensionen (Laenge/Breite/Hoehe) direkt unter Gewicht, weil sie
        # die geometrische Mess-Achse spiegelt - parallel zur Masse-Achse
        # auf der physikalischen Bestands-Kennzahl. Die Differenz beider Quoten
        # beziffert die Vermessungs-Luecke (gewogen aber nicht vermessen).
        lines.append(
            f"  Dimensionen:         {st.quote_mit_dimensionen_prozent:.1f} %")
        # Mohs-Haerte (physikalische Haerte-Achse) direkt unter Dimensionen,
        # weil sie die naechste physikalische Mess-Achse abdeckt: Masse ->
        # Geometrie -> Haerte. Mohs (1=Talk ... 10=Diamant) ist die zentrale
        # quantitative Haertegrad-Skala fuer Mineralien und neben Dichte einer
        # der wichtigsten Pruef-Parameter. Eine Achse genuegt (min ODER max
        # gesetzt) - spiegelt die has_mohs-Konvention. Niedriger Wert ist
        # normal, weil Mohs typisch erst nach Mineral-Bestimmung gepflegt wird.
        lines.append(
            f"  Mohs-Haerte:         {st.quote_mit_mohs_prozent:.1f} %")
        # Dichte (physikalische Dichte-Achse) direkt unter Mohs, weil sie die
        # naechste physikalische Mess-Achse nach Haerte abdeckt: Masse ->
        # Geometrie -> Haerte -> Dichte. Eine Achse genuegt (min ODER max
        # gesetzt) - spiegelt die has_dichte/has_mohs-Konvention. Niedriger
        # Wert ist typisch, weil die Dichte-Messung nicht so trivial ist wie
        # der Mohs-Kratztest (Wasserverdraengung oder pyknometrische Bestimmung).
        lines.append(
            f"  Dichte:              {st.quote_mit_dichte_prozent:.1f} %")
        lines.append(f"  KI-Analyse:          {st.quote_mit_ki_analyse_prozent:.1f} %")
        lines.append(
            f"  KI-Analyse (ueb.):   "
            f"{st.quote_mit_ki_analyse_uebernommen_prozent:.1f} %")
        # Confidence (Bestimmungs-Sicherheitsgrad) direkt unter den KI-Analyse-
        # Quoten, weil sie konzeptionell verwandt sind (Bestimmungs-Qualitaet),
        # aber auf einer separaten Achse: KI-Analyse misst die Anwendungs-/
        # Akzeptanz-Durchdringung, Confidence den quantitativen Score je
        # Stueck (handgepflegt oder uebernommen). Ohne Confidence-Score ist
        # ein Stueck zwischen "sicher" (>=75) und "unsicher" (<25) nicht
        # einzuordnen - die naechste typische Pflege-Achse nach KI-Analyse.
        lines.append(
            f"  Confidence:          {st.quote_mit_confidence_prozent:.1f} %")
        # Seltenheit_global_1_10 (globale Rarity-Skala, 1=haeufig .. 10=sehr
        # selten global) direkt unter Confidence, weil beide quantitative
        # Bestimmungs-Skalen mit definiertem Wertebereich sind (Confidence
        # 0..100, Seltenheit 1..10) und beide out-of-range-Werte in der
        # Integrity separat gemeldet bekommen. Komplementaer zu den existierenden
        # Rarity-Sichten (by_seltenheit_global / wert_pro / gewicht_pro): hier
        # die Coverage-Sicht ueber den Gesamtbestand. Niedriger Wert ist typisch,
        # weil die globale Rarity-Einschaetzung Marktwissen oder mineralogische
        # Recherche erfordert (anders als die objektiv am Stueck beobachtbaren
        # Pruefparameter). Steht vor Kategorie, weil sie zur Bestimmungs-Qualitaets-
        # Achse (zusammen mit Confidence) gehoert und nicht zur Inventar-Achse.
        lines.append(
            f"  Seltenheit global:   "
            f"{st.quote_mit_seltenheit_global_prozent:.1f} %")
        # Seltenheit_Fundort_1_10 (Standort-Rarity-Skala) direkt unter
        # Seltenheit global, weil beide 1..10-Skalen aus dem Feldwoerterbuch
        # sind und beide den gleichen out-of-range-Ausschluss teilen. Die
        # Differenz beider Coverage-Quoten beziffert die Pflege-Asymmetrie
        # zwischen globaler Markt-Sicht und lokalem Fundgebiets-Wissen - die
        # globale Skala ist haeufiger gepflegt (Mineraldatenbank-/Tucson-
        # Wissen), die Fundort-Skala setzt eigene Touren oder Vereins-
        # Berichte voraus. Zusammen mit Confidence/Seltenheit global gehoert
        # sie zur Bestimmungs-/Bewertungs-Qualitaets-Achse, bevor die
        # Inventar-Klassifizierung (Kategorie) drankommt.
        lines.append(
            f"  Seltenheit Fundort:  "
            f"{st.quote_mit_seltenheit_fundort_prozent:.1f} %")
        # Nachfrage_1_10 (Marktnachfrage-Skala) direkt unter Seltenheit Fundort,
        # schliesst die Coverage-Trias der drei 1..10-Markt-/Bewertungs-Skalen
        # aus dem Feldwoerterbuch ab. Waehrend die beiden Rarity-Skalen die
        # Knappheit messen (global vs. lokal), misst Nachfrage den
        # Marktdruck der Kaeufer - unabhaengig orthogonal zur Knappheit (ein
        # global haeufiger Quarz kann in Schmuckqualitaet hoch nachgefragt
        # sein). Typisch niedrigste Quote der drei Skalen in privaten Sammler-
        # Bestaenden, weil die Marktnachfrage aktives Marktbeobachtungs-Wissen
        # erfordert (Auktions-Ergebnisse, Boersenpreise) und viele Sammlungen
        # nicht zum Verkauf gedacht sind. Steht vor Kategorie, weil sie zur
        # Bestimmungs-/Bewertungs-Qualitaets-Achse gehoert und nicht zur
        # Inventar-Klassifizierungs-Achse.
        lines.append(
            f"  Nachfrage:           "
            f"{st.quote_mit_nachfrage_prozent:.1f} %")
        # Inventar-Klassifizierung: was ist das Stueck physisch (Handstueck/
        # Kristall/Duennschliff/...)? Vor Mineral/Fundort, weil Kategorie die
        # vorgelagerte ID-Achse ist - ohne sie macht die mineralogische /
        # geografische Spezifizierung wenig Sinn fuer Inventar-Sortierung.
        lines.append(f"  Kategorie:           {st.quote_mit_kategorie_prozent:.1f} %")
        lines.append(f"  Mineral_Primaer:     {st.quote_mit_mineral_prozent:.1f} %")
        # Varietaet (mineralogische Sub-Klassifizierung) direkt unter
        # Mineral_Primaer, weil sie die feinere Sub-Achse abdeckt - die Differenz
        # beider Quoten beziffert die Sub-Klassifizierungs-Luecke (Stuecke mit
        # Familie, aber ohne Auspraegung).
        lines.append(f"  Varietaet:           {st.quote_mit_varietaet_prozent:.1f} %")
        # Gesteinsart (petrologische Einordnung) direkt unter Varietaet, weil sie
        # die petrologische Achse spiegelt - parallel zur mineralogischen Sub-
        # Achse, bevor die geografische Provenienz-Achse (Fundort) drankommt.
        lines.append(
            f"  Gesteinsart:         {st.quote_mit_gesteinsart_prozent:.1f} %")
        # Kristallsystem (kristallographische Symmetrie-Einordnung) direkt unter
        # Gesteinsart, weil sie die strukturelle Achse spiegelt - parallel zur
        # petrologischen Achse: Gesteinsart sagt etwas ueber den Bildungs-Kontext,
        # Kristallsystem ueber den inneren Aufbau. Beide gemeinsam mit Mineral_
        # Primaer / Varietaet ergeben die vier mineralogisch-strukturellen
        # Bestimmungs-Achsen (Familie / Sub / Einbettung / Symmetrie), bevor die
        # geografische Provenienz-Achse (Fundort) drankommt.
        lines.append(
            f"  Kristallsystem:      {st.quote_mit_kristallsystem_prozent:.1f} %")
        # Magnetismus (qualitative magnetische Reaktion) direkt unter
        # Kristallsystem, weil sie die physikalisch-magnetische Pruef-Achse
        # spiegelt - parallel zur kristallographischen Symmetrie-Achse, beide
        # sind kurze Enum-Skalen aus dem Feldwoerterbuch (nein/schwach/ja vs.
        # kubisch/tetragonal/...). Die Coverage-Quote misst die Pflege-Tiefe
        # auf der qualitativen Pruefparameter-Achse (neben HCl-Reaktion und
        # Strichfarbe, die als freie str-Felder keine vergleichbare Enum-
        # Coverage haben). Niedriger Wert ist normal - Sammler dokumentieren
        # haeufig nur positive Magnetismus-Treffer (Magnetit, Pyrrhotin) und
        # lassen offensichtlich-negative Mineralen (Quarz, Calcit, Pyrit) ohne
        # expliziten "nein"-Eintrag, bevor die geografische Provenienz-Achse
        # (Fundort) drankommt.
        lines.append(
            f"  Magnetismus:         {st.quote_mit_magnetismus_prozent:.1f} %")
        # Glanz (optische Oberflaechen-Reflexion) direkt unter Magnetismus, weil
        # er die optische Diagnose-Achse spiegelt - parallel zur magnetischen
        # Reaktions-Achse, beide sind kurze Enum-Skalen aus dem Feldwoerterbuch
        # (glasig/wachsig/matt/metallisch/fettig/seidig/perlmutt vs. nein/schwach/
        # ja). Die Coverage-Quote misst die Pflege-Tiefe auf der optischen Achse;
        # niedriger Wert ist normal, weil gerade offensichtliche Glanz-Auspraegungen
        # ("natuerlich ist Quarz glasig") haeufig undokumentiert bleiben. Reihen-
        # folge spiegelt die semantische Sortierung Symmetrie -> Magnetismus ->
        # Glanz, bevor die geografische Provenienz-Achse (Fundort) drankommt.
        lines.append(
            f"  Glanz:               {st.quote_mit_glanz_prozent:.1f} %")
        # Transparenz (qualitative Lichtdurchlaessigkeit) direkt unter Glanz,
        # weil sie die zweite optische Diagnose-Achse spiegelt - parallel zur
        # Oberflaechen-Reflexions-Achse, beide sind kurze Enum-Skalen aus dem
        # Feldwoerterbuch (durchsichtig/durchscheinend/opak vs. glasig/wachsig/
        # matt/...). Beide gemeinsam ergeben die zwei optischen Pruef-Achsen
        # (Auflicht-Reflexion / Durchlicht-Durchlaessigkeit), bevor die
        # geografische Provenienz-Achse (Fundort) drankommt. Reihenfolge
        # spiegelt die semantische Sortierung Symmetrie -> Magnetismus -> Glanz
        # -> Transparenz, schliesst die optische Diagnose-Reihe ab.
        lines.append(
            f"  Transparenz:         {st.quote_mit_transparenz_prozent:.1f} %")
        # Spaltbarkeit (mechanisches Bruchverhalten) direkt unter Transparenz,
        # weil sie die mechanisch-strukturelle Achse spiegelt - nach der
        # optischen Diagnose-Doppel-Achse (Glanz/Transparenz) folgt die
        # mechanische Achse. Spaltbarkeit (vollkommen/gut/deutlich/undeutlich/
        # keine - die fuenf Enum-Werte) sagt, ob das Mineral entlang
        # kristallographisch bevorzugter Ebenen spaltet (Glimmer/Calcit) oder
        # unregelmaessig bricht (Quarz). Niedriger Wert ist typisch, weil der
        # Hammertest invasiv ist und nicht routinemaessig durchgefuehrt wird.
        # Reihenfolge spiegelt die semantische Sortierung Symmetrie ->
        # Magnetismus -> Glanz -> Transparenz -> Spaltbarkeit, bevor die
        # geografische Provenienz-Achse (Fundort) drankommt.
        lines.append(
            f"  Spaltbarkeit:        {st.quote_mit_spaltbarkeit_prozent:.1f} %")
        # Bruch (ungeordnetes mechanisches Versagen ausserhalb der Spaltebenen)
        # direkt unter Spaltbarkeit, weil Bruch die paarweise mechanische
        # Diagnose-Achse spiegelt - Spaltbarkeit klassifiziert das geordnete
        # Bruchverhalten entlang bevorzugter Kristallebenen (vollkommen/gut/
        # deutlich/undeutlich/keine), Bruch das ungeordnete Versagensmuster
        # ausserhalb der Spaltebenen (muschelig/uneben/splittrig/faserig/erdig/
        # glatt - die sechs Enum-Werte). Beide gemeinsam ergeben das vollstaendige
        # mechanische Versagensbild eines Stuecks: Glimmer/Calcit/Galenit zeigen
        # die Spaltbarkeit am deutlichsten, Quarz/Opal/Obsidian/Chalcedon den
        # Bruch (kein Spaltsystem, daher muscheliger Bruch als Haupt-Kennzeichen).
        # Niedriger Wert ist typisch wie bei Spaltbarkeit, weil der Hammertest
        # invasiv ist und bei Vitrinen-/Tausch-Stuecken vermieden wird. Schliesst
        # die mechanisch-strukturelle Diagnose-Doppel-Achse, bevor die
        # geografische Provenienz-Achse (Fundort) drankommt. Reihenfolge spiegelt
        # die semantische Sortierung Symmetrie -> Magnetismus -> Glanz ->
        # Transparenz -> Spaltbarkeit -> Bruch.
        lines.append(
            f"  Bruch:               {st.quote_mit_bruch_prozent:.1f} %")
        # Beste_Verwendung (empfohlene Verwendungs-Kategorie) direkt unter Bruch,
        # weil sie die letzte fehlende Coverage-Quote der strukturierten Enum-
        # Felder aus dem Feldwoerterbuch abdeckt: nach der Diagnose-Reihe
        # (Magnetismus/Glanz/Transparenz/Spaltbarkeit/Bruch - objektive
        # Beobachtungen am Stueck) folgt die Verwendungs-/Empfehlungs-Achse
        # (Schmuck/Sammlung/Forschung/Industrie/Talisman/Dekoration - subjektive
        # Sammler-Entscheidung ueber den weiteren Lebensweg des Stuecks).
        # Aussenkontext-bedingt orthogonal zu allen anderen Enum-Coverage-Quoten,
        # weil Beste_Verwendung keine Eigenschaft am Stueck beziffert, sondern
        # die Pflege-/Planungs-Entscheidung darueber - ein Stueck kann mineralogisch
        # vollstaendig charakterisiert sein und trotzdem ohne Verwendungs-
        # Empfehlung bleiben (in Wissenschafts-Sammlungen sogar regelmaessig).
        # Schliesst die Coverage-Reihe der strukturierten Enum-Felder ab, vor
        # den freien Achsen (Fundort/Notizen) und der Merge-Quote.
        lines.append(
            f"  Beste Verwendung:    {st.quote_mit_beste_verwendung_prozent:.1f} %")
        lines.append(f"  Fundort:             {st.quote_mit_fundort_prozent:.1f} %")
        # Koordinaten direkt unter Fundort, weil sie das geocoded-Subset von
        # Fundort beziffern: Anteil der Objekte, deren freitext-Fundort ein
        # per parse_coordinates erkennbares Lat/Lon-Paar enthaelt. Die
        # Differenz Fundort - Koordinaten beziffert den freitext-only-Anteil
        # ("Berner Oberland", "alte Halde bei X") und damit den verbleibenden
        # Geocoding-Pflege-Aufwand ohne neue Fundort-Akquise. Spiegelt die
        # repository-Bounding-Box-Achse list_objects_in_bbox auf das CLI-
        # Dashboard ("wie viel meiner Sammlung ist fuer geografische Filter
        # erreichbar?"). Niedriger Wert ist typisch bei historisch gewachsenen
        # Sammlungen mit Ortsnamen-only-Eintraegen aus Vor-GPS-Zeit.
        lines.append(
            f"  Koordinaten:         {st.quote_mit_koordinaten_prozent:.1f} %")
        # Farbe_beobachtet (tatsaechlich gesehene Mineral-Farbe) direkt nach
        # Fundort und vor Strichfarbe, weil sie die paarweise Farb-Achse zur
        # diagnostisch invarianten Strichfarbe darstellt - waehrend Strichfarbe
        # bei einer gegebenen Mineral-Art konstant ist (Pyrit immer gruenlich-
        # schwarz), variiert die beobachtete Farbe innerhalb der Mineral-Art
        # stark (Quarz von farblos bis rauchgrau, Calcit von weiss bis schwarz).
        # Niederschwelligste visuelle Diagnose-Achse - keine Werkzeuge noetig,
        # am Tageslicht beobachtbar - daher typisch hoechste Coverage-Quote
        # unter den freien str-Pruefparametern (eine niedrige Quote weist auf
        # einen unvollstaendig erfassten Bestand hin, in dem selbst der erste
        # Blick auf das Stueck fehlt).
        lines.append(
            f"  Farbe (beobachtet):  {st.quote_mit_farbe_prozent:.1f} %")
        # Strichfarbe (Farbe des Pulvers auf Porzellan-Strichplaette) direkt
        # nach Fundort, weil sie die letzte fehlende Coverage-Quote der
        # qualitativen Bestimmungs-Pruefparameter aus dem Feldwoerterbuch
        # abdeckt: nach der Enum-validierten Magnetismus-Achse (oben unter
        # Kristallsystem einsortiert) folgt die freie str-Pruef-Achse als
        # zweiter zentraler diagnostischer Eintragspunkt. Der Strichtest ist
        # bei visuell aehnlichen Mineralien (Pyrit-Gold, Haematit-Magnetit,
        # Calcit-Aragonit) oft der eindeutige Trenner, wenn andere Pruef-
        # Achsen versagen; die Coverage-Quote misst die Bestaetigungs-Tiefe
        # der mineralogischen Bestimmung. Niedriger Wert ist typisch, weil
        # der Strichtest invasiv ist (das Mineral wird abgerieben) und eine
        # Porzellan-Strichplaette erfordert - er wird erst nach erster
        # Mineral-Hypothese durchgefuehrt, nicht routinemaessig. Steht vor
        # Notizen, weil Strichfarbe ein strukturierter Pruef-Eintrag ist
        # (eine konkrete Farbangabe), waehrend Notizen die freie
        # "Sonstiges"-Achse jenseits der 43 strukturierten Felder beziffert.
        lines.append(
            f"  Strichfarbe:         {st.quote_mit_strichfarbe_prozent:.1f} %")
        # HCl-Reaktion (Salzsaeure-Test) schliesst die Coverage-Trias der drei
        # klassischen qualitativen Bestimmungs-Pruefparameter (Magnetismus,
        # Strichfarbe, HCl-Reaktion) aus dem Feldwoerterbuch ab. Steht direkt
        # nach Strichfarbe und vor Notizen, weil sie als strukturierter
        # Pruef-Eintrag (keine/schwach/stark) konzeptionell naeher an Strichfarbe
        # ist als an der freien Sonstiges-Achse notizen.
        lines.append(
            f"  HCl-Reaktion:        {st.quote_mit_hcl_reaktion_prozent:.1f} %")
        # UV-365nm (Fluoreszenz-Reaktion bei Langwellen-UV) spiegelt die
        # qualitativen Pruefparameter-Trias (Magnetismus/Strichfarbe/HCl-
        # Reaktion) auf die optisch-UV-Diagnose-Achse. Steht direkt nach
        # HCl-Reaktion und vor Notizen, weil UV-365nm konzeptionell eine
        # vierte qualitative Pruef-Achse ist - die Reihenfolge bildet damit
        # die Coverage-Sequenz Magnetismus -> Strichfarbe -> HCl-Reaktion ->
        # UV-365nm der vier zentralen Pruefparameter aus dem Feldwoerterbuch
        # ab, bevor mit Notizen die freie Sonstiges-Achse beginnt.
        lines.append(
            f"  UV 365 nm:           {st.quote_mit_uv_365nm_prozent:.1f} %")
        # UV-254nm (Fluoreszenz-Reaktion bei Kurzwellen-UV) als paarweise
        # Komplement-Achse zu UV-365nm. Steht direkt nach UV-365nm und vor
        # Notizen, damit die Doppel-Wellenlaengen-Achse als gemeinsamer
        # Block lesbar ist - die Differenz beider Quoten beziffert die
        # Kurzwellen-Mess-Luecke (Langwelle dokumentiert, Kurzwelle nicht).
        lines.append(
            f"  UV 254 nm:           {st.quote_mit_uv_254nm_prozent:.1f} %")
        # Reaktionshinweis (erklaerende Begleit-Notiz zu UV/HCl/Magnetismus-
        # Reaktionen) direkt nach UV 254 nm und vor Notizen, weil sie thematisch
        # fest auf die Reaktions-Interpretation fokussiert ist - die vier
        # umliegenden Reaktions-Pruef-Achsen (Magnetismus oben unter
        # Kristallsystem, HCl-Reaktion / UV-365 / UV-254 direkt davor)
        # dokumentieren die Roh-Beobachtung, Reaktionshinweis die erklaerende
        # Tiefe (warum reagiert das Stueck so?). Die Differenz
        # quote_mit_hcl_reaktion_prozent - quote_mit_reaktionshinweis_prozent
        # beziffert die typische Interpretations-Luecke (Reaktion beobachtet,
        # aber nicht erklaert). Steht vor Notizen, weil Reaktionshinweis ein
        # thematisch fokussierter Freitext-Eintrag ist (zu den Reaktions-
        # Spalten), waehrend Notizen die allgemeine "Sonstiges"-Achse jenseits
        # der 43 strukturierten Felder beziffert.
        lines.append(
            f"  Reaktionshinweis:    {st.quote_mit_reaktionshinweis_prozent:.1f} %")
        # Pruefempfehlungen (empfohlene Bestaetigungstests aus der
        # Sonstiges-Gruppe des Feldwoerterbuchs) direkt nach Reaktionshinweis
        # und vor Notizen, weil sie konzeptionell die naechste-Schritt-Achse
        # zur rueckblickenden Erklaer-Achse Reaktionshinweis ist - die drei
        # Freitext-Achsen decken zusammen den vollstaendigen Bestimmungs-
        # Workflow ab: Reaktionshinweis interpretiert die Vergangenheit
        # (warum hat das Stueck so reagiert?), Pruefempfehlungen plant die
        # Zukunft (welche Pruefung folgt als naechstes?), Notizen begleitet
        # die Gegenwart (allgemeine Beobachtungen). Die Differenz
        # quote_mit_confidence_prozent (quantitative Sicherheits-Achse) - quote
        # _mit_pruefempfehlungen_prozent beziffert die Disziplin-Luecke bei
        # der Markierung offener Pruef-Pfade fuer noch nicht endgueltig
        # bestimmte Stuecke.
        lines.append(
            f"  Pruefempfehlungen:   {st.quote_mit_pruefempfehlungen_prozent:.1f} %")
        # Notizen (freie Beobachtungs-Spalte) am Ende der Feld-Coverage-Block-
        # Sektion, weil sie konzeptionell die "Sonstiges"-Achse ist - jenseits
        # der 43 strukturierten Standardfelder. Der Sammler pflegt Notizen nur
        # bei Beobachtungs-Anlass; eine niedrige Quote ist normal, weil
        # routinemaessige Pflege auf die strukturierten Felder zielt. Die
        # Differenz zwischen einer hohen Strukturfeld-Coverage und einer
        # niedrigen Notizen-Quote charakterisiert eine rein katalogisierende
        # Sammlungs-Linie; das umgekehrte Profil eine beobachtungs-orientierte
        # Linie. Steht vor der Merge-Quote, weil Notizen pro Objekt eine
        # inhaltliche Eigenschaft ist, waehrend die Merge-Quote eine
        # Provenienz-/Konsolidierungs-Eigenschaft ueber Objekt-Gruppen hinweg
        # beziffert.
        lines.append(f"  Notizen:             {st.quote_mit_notizen_prozent:.1f} %")
        # Merge-Quote: Anteil der Kanon-Objekte, die aus Duplikat-Merges
        # hervorgegangen sind (Provenienz-Coverage). aliase_total oben zeigt
        # das Roh-Volumen, hier die Quote als Sammler-typische "wie konsolidiert
        # ist mein Bestand?"-Sicht.
        lines.append(f"  Merge (Aliase):      {st.quote_mit_alias_prozent:.1f} %")
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
    if st.by_beste_verwendung:
        # Verwendungs-Anzahl-Sicht: wieviele Stuecke pro Beste_Verwendung
        # (Schmuck/Sammlung/Forschung/Industrie/Talisman/Dekoration)?
        # Komplementaer zu wert_/gewicht_pro_beste_verwendung (CLI weiter
        # unten): zeigt die Bestand-Verteilung der Sammler-Empfehlungen -
        # praktisch fuer Boersen-Vorbereitung ("wieviele Stuecke habe ich als
        # Schmuck-Kandidaten markiert?") oder Aufraeum-Entscheidungen
        # ("Talisman-Stuecke ueberwiegen Sammlungsstuecke, sollten in eine
        # eigene Lade"). Reihenfolge aus _count_by: absteigend nach Anzahl,
        # dann alphabetisch.
        lines += ["", "Objekte pro Beste-Verwendung:"]
        for name, n in list(st.by_beste_verwendung.items())[:top]:
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
    if st.by_erstellt_am_jahr:
        # Sammlungswachstum-Histogramm pro Erfassungs-Jahr: spiegelt "Funde pro
        # Jahr" um die Achse, wann das Objekt digitalisiert wurde (statt wann
        # gefunden). Macht Migrations-Wellen sichtbar (z.B. eine grosse Erfassungs-
        # session in 2026), die in der Funddatum-Sicht untergehen. Reihenfolge
        # bleibt chronologisch aus _count_erstellt_am_jahr (aelteste zuerst).
        lines += ["", "Sammlung erfasst pro Jahr:"]
        for jahr, n in st.by_erstellt_am_jahr.items():
            lines.append(f"  {jahr:40s} {n}")
    if st.by_erstellt_am_jahrzehnt:
        # Erfassungs-Dekaden-Histogramm: spiegelt "Funde pro Jahrzehnt" auf die
        # Erfassungs-Achse. Grobe Sicht ohne Einzeljahres-Rauschen, macht
        # uebergreifende Migrations-Wellen sichtbar (Excel-Welle 2020+ vs.
        # handgepflegte 2010er-Phase). Reihenfolge bleibt chronologisch aus
        # _count_erstellt_am_jahrzehnt (aelteste zuerst).
        lines += ["", "Sammlung erfasst pro Jahrzehnt:"]
        for dekade, n in st.by_erstellt_am_jahrzehnt.items():
            lines.append(f"  {dekade:40s} {n}")
    if st.by_erstellt_am_monat:
        # Erfassungs-Saisonalitaet (01..12, ueber alle Jahre): direkt unter dem
        # Erfassungs-Jahres-Block, spiegelt "Funde pro Monat". Zeigt typische
        # Indoor-Wellen (Winter/Boersenvorbereitung Januar-Maerz) vs. Aussen-
        # Pausen waehrend der Feld-Saison. Reihenfolge bleibt 01..12.
        lines += ["", "Sammlung erfasst pro Monat:"]
        for monat, n in st.by_erstellt_am_monat.items():
            lines.append(f"  {monat:40s} {n}")
    if st.by_geaendert_am_jahr:
        # Pflege-Aktivitaet pro Aenderungs-Jahr: spiegelt "Sammlung erfasst
        # pro Jahr" auf die Aenderungs-Achse. Macht nachtraegliche Pflege-
        # Wellen sichtbar (KI-Analyse uebernommen, Foto nachgereicht, Mineral-
        # Bestimmung korrigiert), die im Erfassungs-Wachstums-Histogramm
        # untergehen, weil dort ein nie wieder beruehrtes Stueck dieselbe
        # Stempel-Position haelt wie ein nachgepflegtes. Reihenfolge bleibt
        # chronologisch aus _count_geaendert_am_jahr (aelteste zuerst).
        lines += ["", "Pflege-Aktivitaet pro Jahr:"]
        for jahr, n in st.by_geaendert_am_jahr.items():
            lines.append(f"  {jahr:40s} {n}")
    if st.by_geaendert_am_jahrzehnt:
        # Pflege-Aktivitaet pro Dekade: spiegelt "Sammlung erfasst pro
        # Jahrzehnt" auf die Aenderungs-Achse. Grobe Sicht ohne Einzeljahres-
        # Rauschen, macht uebergreifende Pflege-Wellen sichtbar (KI-Welle 2024+
        # vs. handgepflegte 2010er-Phase). Reihenfolge bleibt chronologisch
        # aus _count_geaendert_am_jahrzehnt (aelteste zuerst).
        lines += ["", "Pflege-Aktivitaet pro Jahrzehnt:"]
        for dekade, n in st.by_geaendert_am_jahrzehnt.items():
            lines.append(f"  {dekade:40s} {n}")
    if st.by_geaendert_am_monat:
        # Pflege-Saisonalitaet (01..12, ueber alle Jahre): direkt unter dem
        # Pflege-Dekaden-Block, spiegelt "Sammlung erfasst pro Monat" auf die
        # Aenderungs-Achse und schliesst die Histogramm-Trias auf der Aenderungs-
        # Achse ab (Jahr / Jahrzehnt / Monat). Zeigt typische Winter-Indoor-
        # Pflegephasen (Januar-Februar) und Pflege-Wellen-Monate (KI-Analyse),
        # waehrend die Sommer-Feldsaison pflegearm bleibt. Reihenfolge bleibt
        # 01..12.
        lines += ["", "Pflege-Aktivitaet pro Monat:"]
        for monat, n in st.by_geaendert_am_monat.items():
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
    if st.wert_pro_glanz:
        # Optische Wert-Sicht: welcher Glanztyp traegt den Sammlungswert?
        # Glasige Quarz-Sammlungen vs. metallische Sulfide vs. matte Sediment-
        # stuecke laufen wertlich oft weit auseinander. Komplementaer zu
        # by_glanz (Anzahl): die Anzahl-Sicht wuerde glasige Quarze als
        # dominierend zeigen, der Wert kann aber bei wenigen metallischen
        # Pyrit-/Galenit-Stuecken liegen - der Block trennt die beiden Effekte.
        lines += ["", "Wert pro Glanz (CHF):"]
        for glz, wert in st.wert_pro_glanz[:top]:
            lines.append(f"  {glz:40s} {wert:>12,.0f}")
    if st.wert_pro_transparenz:
        # Lichtdurchlaessigkeits-Wert-Sicht: welcher Transparenz-Typ traegt den
        # Sammlungswert (durchsichtig/durchscheinend/opak)? Komplementaer zu
        # by_transparenz (Anzahl) und wert_pro_glanz (Oberflaechen-Reflexion):
        # durchsichtiger Bergkristall vs. durchscheinender Achat vs. opaker
        # Pyrit liegen wertlich oft auf ganz unterschiedlichen Niveaus.
        lines += ["", "Wert pro Transparenz (CHF):"]
        for t, wert in st.wert_pro_transparenz[:top]:
            lines.append(f"  {t:40s} {wert:>12,.0f}")
    if st.wert_pro_magnetismus:
        # Magnetismus-Wert-Sicht: welcher Eisengehalts-Typ traegt den Sammlungs-
        # wert (ja/schwach/nein)? Magnetit/Pyrrhotin (ja) liegen wertlich oft auf
        # einem anderen Niveau als inerte Quarz-/Calcit-Stuecke (nein) oder
        # schwach magnetische Haematit-Stuecke (schwach). Komplementaer zu
        # by_magnetismus (Anzahl) und wert_pro_glanz/wert_pro_transparenz
        # (optische Achsen): hier die physikalische Eisengehalt-Achse.
        lines += ["", "Wert pro Magnetismus (CHF):"]
        for m, wert in st.wert_pro_magnetismus[:top]:
            lines.append(f"  {m:40s} {wert:>12,.0f}")
    if st.wert_pro_spaltbarkeit:
        # Spaltbarkeits-Wert-Sicht: welche Spaltflaechen-Klasse traegt den
        # Sammlungswert (vollkommen/gut/deutlich/undeutlich/keine)? Komplementaer
        # zu by_spaltbarkeit (Anzahl): Calcit/Fluorit (vollkommen) ergeben oft
        # viele kleine wertvolle Stuecke, Quarz (keine) traegt ueber wenige
        # grosse Stuecke. Praeparier-relevant: gut spaltbare Stuecke lassen sich
        # sauber schneiden, was die Polier-Empfehlung und damit Wert_CHF_poliert
        # beeinflusst.
        lines += ["", "Wert pro Spaltbarkeit (CHF):"]
        for sp, wert in st.wert_pro_spaltbarkeit[:top]:
            lines.append(f"  {sp:40s} {wert:>12,.0f}")
    if st.wert_pro_bruch:
        # Bruch-Wert-Sicht: welche Bruchverhalten-Klasse traegt den Sammlungs-
        # wert (muschelig/uneben/splittrig/faserig/erdig/glatt)? Komplementaer
        # zu by_bruch (Anzahl) und wert_pro_spaltbarkeit (Spaltflaechen):
        # muschelig brechende Quarz-/Obsidian-Stuecke liegen wertlich oft auf
        # einem anderen Niveau als fasrige Asbest-/Aktinolith-Stuecke oder
        # hakig-unebene Kupfer-/Silber-Plaettchen.
        lines += ["", "Wert pro Bruch (CHF):"]
        for b, wert in st.wert_pro_bruch[:top]:
            lines.append(f"  {b:40s} {wert:>12,.0f}")
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
    if st.gewicht_pro_glanz:
        # Spiegelbild zu wert_pro_glanz: welcher Glanztyp dominiert gewichts-
        # maessig? Matte Geroellstuecke (Sediment) tragen oft die Sammlungsmasse,
        # glasige Kristalle den Wert - die Wert/Gewicht-Entkopplung wird auf der
        # optischen Achse sichtbar.
        lines += ["", "Gewicht pro Glanz (g):"]
        for glz, gewicht in st.gewicht_pro_glanz[:top]:
            lines.append(f"  {glz:40s} {gewicht:>12,.1f}")
    if st.gewicht_pro_transparenz:
        # Spiegelbild zu wert_pro_transparenz: welcher Transparenz-Typ traegt
        # die meiste Masse? Opake Geroellstuecke (Sediment/Pyrit) dominieren
        # oft die Sammlungsmasse, durchsichtige Kristalle den Wert - die
        # Wert/Gewicht-Entkopplung wird auch auf der Lichtdurchlaessigkeits-
        # Achse sichtbar.
        lines += ["", "Gewicht pro Transparenz (g):"]
        for t, gewicht in st.gewicht_pro_transparenz[:top]:
            lines.append(f"  {t:40s} {gewicht:>12,.1f}")
    if st.gewicht_pro_magnetismus:
        # Spiegelbild zu wert_pro_magnetismus: welcher Eisengehalts-Typ traegt
        # die meiste Masse? Schwere Magnetit-Brocken (ja) heben das Gewicht in
        # einer Kategorie, die wertlich oft hinter klassischen Quarz-Stuecken
        # zurueckbleibt. Die Wert/Gewicht-Entkopplung wird auch auf der
        # Magnetismus-Achse sichtbar.
        lines += ["", "Gewicht pro Magnetismus (g):"]
        for m, gewicht in st.gewicht_pro_magnetismus[:top]:
            lines.append(f"  {m:40s} {gewicht:>12,.1f}")
    if st.gewicht_pro_spaltbarkeit:
        # Spiegelbild zu wert_pro_spaltbarkeit: welche Spaltflaechen-Klasse
        # traegt die meiste Masse? Glimmer-Plaettchen (vollkommen) sind oft
        # leicht und zahlreich, dichte Quarz-Brocken (keine) tragen den
        # Schwerteil. Die Wert/Gewicht-Entkopplung wird auch auf der
        # Spaltflaechen-Achse sichtbar.
        lines += ["", "Gewicht pro Spaltbarkeit (g):"]
        for sp, gewicht in st.gewicht_pro_spaltbarkeit[:top]:
            lines.append(f"  {sp:40s} {gewicht:>12,.1f}")
    if st.gewicht_pro_bruch:
        # Spiegelbild zu wert_pro_bruch: welche Bruchverhalten-Klasse traegt die
        # meiste Masse? Dichte muschelig brechende Obsidian-Brocken tragen oft
        # den Schwerteil, fasrige Aktinolith-Buendel bleiben leicht. Die Wert/
        # Gewicht-Entkopplung wird auch auf der Bruchverhalten-Achse sichtbar.
        lines += ["", "Gewicht pro Bruch (g):"]
        for b, gewicht in st.gewicht_pro_bruch[:top]:
            lines.append(f"  {b:40s} {gewicht:>12,.1f}")
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
    if st.wert_pro_erstellt_am_jahr:
        # Erfassungs-Achse: welcher Erfassungs-Jahrgang hat wertlich am meisten
        # in die Sammlung eingespielt? Komplementaer zu wert_pro_funddatum_jahr
        # (Fund-Achse, wann gefunden) und zu by_erstellt_am_jahr (Anzahl):
        # macht Migrations-Wellen wertlich sichtbar - typisch eine Erfassungs-
        # Session, die viele wertvolle Altbestaende auf einmal in die DB schiebt.
        lines += ["", "Wert pro Erfassungs-Jahr (CHF):"]
        for jahr, wert in st.wert_pro_erstellt_am_jahr[:top]:
            lines.append(f"  {jahr:40s} {wert:>12,.0f}")
    if st.gewicht_pro_erstellt_am_jahr:
        # Spiegelbild: schwerste Erfassungs-Welle. Wert und Gewicht entkoppeln
        # sich oft (eine Erfassungs-Session vieler leichter Top-Kristalle vs.
        # eine Geroell-Migrations-Welle), deshalb beide Sichten anbieten.
        lines += ["", "Gewicht pro Erfassungs-Jahr (g):"]
        for jahr, gewicht in st.gewicht_pro_erstellt_am_jahr[:top]:
            lines.append(f"  {jahr:40s} {gewicht:>12,.1f}")
    if st.wert_pro_geaendert_am_jahr:
        # Aenderungs-Achse: welcher Pflege-Jahrgang traegt wertlich am meisten
        # zur letzten Datenpflege bei? Vervollstaendigt das Zeit-Trio neben
        # Fund- (wert_pro_funddatum_jahr) und Erfassungs-Achse
        # (wert_pro_erstellt_am_jahr) auf die dritte Zeit-Achse aus dem
        # Spannen-Trio. Bei nie-aktualisierten Alt-Eintraegen konvergiert
        # die Spitze auf den Erfassungs-Jahrgang; bei aktiv gepflegten
        # Stuecken driftet sie in das aktuelle Pflege-Jahr.
        lines += ["", "Wert pro Aenderungs-Jahr (CHF):"]
        for jahr, wert in st.wert_pro_geaendert_am_jahr[:top]:
            lines.append(f"  {jahr:40s} {wert:>12,.0f}")
    if st.gewicht_pro_geaendert_am_jahr:
        # Spiegelbild Gewicht: in welchem Pflege-Jahr liegt die schwerste
        # zuletzt redaktionell beruehrte Masse? Komplementaer zu
        # wert_pro_geaendert_am_jahr, um die Wert/Gewicht-Entkopplung auch
        # auf der Aenderungs-Achse sichtbar zu machen.
        lines += ["", "Gewicht pro Aenderungs-Jahr (g):"]
        for jahr, gewicht in st.gewicht_pro_geaendert_am_jahr[:top]:
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
    if st.wert_pro_erstellt_am_jahrzehnt:
        # Erfassungs-Dekaden-Sicht des Sammlungswerts: spiegelt wert_pro_
        # funddatum_jahrzehnt auf die Erfassungs-Achse - in welcher Dekade
        # ist wertlich am meisten in die DB eingespielt worden? Komplementaer
        # zu by_erstellt_am_jahrzehnt (Anzahl) und wert_pro_erstellt_am_jahr
        # (Einzeljahres-Aufloesung): aggregiert auf 10er-Schritte und macht
        # Migrations-Wellen (Excel-Altbestand 2020+) wertlich sichtbar, die
        # im Einzeljahr-Histogramm durch Rauschen verdeckt sind.
        lines += ["", "Wert pro Erfassungs-Jahrzehnt (CHF):"]
        for dekade, wert in st.wert_pro_erstellt_am_jahrzehnt:
            lines.append(f"  {dekade:40s} {wert:>12,.0f}")
    if st.gewicht_pro_erstellt_am_jahrzehnt:
        # Spiegelbild Gewicht: welche Erfassungs-Dekade brachte die meiste
        # Masse? Migrations-Wellen mit Geroell-Altbestaenden tauchen hier
        # nach Gewicht sortiert auf, waehrend wert_pro_erstellt_am_jahrzehnt
        # die hochpreisigen Erfassungs-Spitzen zeigt - Wert/Gewicht-Entkopplung
        # auch auf der Erfassungs-Dekaden-Achse.
        lines += ["", "Gewicht pro Erfassungs-Jahrzehnt (g):"]
        for dekade, gewicht in st.gewicht_pro_erstellt_am_jahrzehnt:
            lines.append(f"  {dekade:40s} {gewicht:>12,.1f}")
    if st.wert_pro_geaendert_am_jahrzehnt:
        # Aenderungs-Dekaden-Wertsicht: in welcher Pflege-Dekade ist wertlich am
        # meisten redaktionell beruehrt worden? Vervollstaendigt das Dekaden-Trio
        # neben Fund (wert_pro_funddatum_jahrzehnt) und Erfassung (wert_pro_
        # erstellt_am_jahrzehnt) auf die dritte Zeit-Achse. Bei nie-aktualisierten
        # Alt-Eintraegen konvergiert die Spitze auf die Erfassungs-Dekade; bei
        # aktiv gepflegten Stuecken driftet sie in die aktuelle Pflege-Dekade -
        # typisch sichtbar bei Neu-Klassifizierungs-Wellen ueber mehrere Jahre.
        lines += ["", "Wert pro Aenderungs-Jahrzehnt (CHF):"]
        for dekade, wert in st.wert_pro_geaendert_am_jahrzehnt:
            lines.append(f"  {dekade:40s} {wert:>12,.0f}")
    if st.gewicht_pro_geaendert_am_jahrzehnt:
        # Spiegelbild Gewicht: welche Pflege-Dekade traegt die schwerste Masse?
        # Komplementaer zu wert_pro_geaendert_am_jahrzehnt, um die Wert/Gewicht-
        # Entkopplung auch auf der Aenderungs-Dekaden-Achse sichtbar zu machen.
        lines += ["", "Gewicht pro Aenderungs-Jahrzehnt (g):"]
        for dekade, gewicht in st.gewicht_pro_geaendert_am_jahrzehnt:
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
    if st.wert_pro_erstellt_am_monat:
        # Saison-Sicht des Erfassungs-Werts: welcher Monat des Jahres bringt
        # ueber alle Jahre den hoechsten Erfassungs-Wert? Komplementaer zu
        # by_erstellt_am_monat (Anzahl) und wert_pro_funddatum_monat (Fund-
        # Saison): Indoor-Erfassungs-Spitzen (Winter, Boersen-Vorbereitung
        # Januar-Maerz) entkoppeln sich oft vom Fund-Saison-Profil.
        # Sortierung: absteigend nach Summe (top zuerst).
        lines += ["", "Wert pro Erfassungs-Monat (CHF):"]
        for monat, wert in st.wert_pro_erstellt_am_monat:
            lines.append(f"  {monat:40s} {wert:>12,.0f}")
    if st.gewicht_pro_erstellt_am_monat:
        # Spiegelbild Gewicht: welcher Erfassungs-Monat bringt die meiste Masse?
        # Migrations-Wellen (schwere Altbestaende auf einmal eingespielt) tauchen
        # hier nach Gewicht sortiert auf, waehrend wert_pro_erstellt_am_monat
        # die hochpreisigen Erfassungs-Spitzen zeigt.
        lines += ["", "Gewicht pro Erfassungs-Monat (g):"]
        for monat, gewicht in st.gewicht_pro_erstellt_am_monat:
            lines.append(f"  {monat:40s} {gewicht:>12,.1f}")
    if st.wert_pro_geaendert_am_monat:
        # Aenderungs-Saison-Wertsicht: welcher Monat des Jahres bringt ueber
        # alle Jahre den hoechsten Pflege-Wert? Vervollstaendigt das Monats-
        # Trio neben Fund (wert_pro_funddatum_monat) und Erfassung
        # (wert_pro_erstellt_am_monat) auf die dritte Zeit-Achse. Bei nie-
        # aktualisierten Alt-Eintraegen konvergiert die Saison auf die
        # Erfassungs-Saison; bei aktiv gepflegten Stuecken driftet sie in
        # die aktuellen Pflege-Monate ab - typisch sichtbar bei einer
        # Boersen-Nachpflege-Welle, die einen Wert-Spitzen-Monat fern von
        # der urspruenglichen Erfassungs-Saison erzeugt.
        lines += ["", "Wert pro Aenderungs-Monat (CHF):"]
        for monat, wert in st.wert_pro_geaendert_am_monat:
            lines.append(f"  {monat:40s} {wert:>12,.0f}")
    if st.gewicht_pro_geaendert_am_monat:
        # Spiegelbild Gewicht: welcher Pflege-Monat traegt die schwerste
        # Masse? Komplementaer zu wert_pro_geaendert_am_monat, um die Wert/
        # Gewicht-Entkopplung auch auf der Aenderungs-Monats-Achse sichtbar
        # zu machen.
        lines += ["", "Gewicht pro Aenderungs-Monat (g):"]
        for monat, gewicht in st.gewicht_pro_geaendert_am_monat:
            lines.append(f"  {monat:40s} {gewicht:>12,.1f}")
    if st.wert_pro_seltenheit_global:
        # Rarity-Wert-Sicht: wo steckt der Sammlungswert in der globalen
        # Seltenheits-Verteilung (1..10)? Komplementaer zu by_seltenheit_global
        # (Anzahl): die Anzahl-Sicht zeigt den Bestand-Schwerpunkt, der Wert-
        # Block zeigt das Konzentrat - Sammler-typisch liegen die hochpreisigen
        # Stuecke auf den oberen Skalen-Stufen (>=8), waehrend die Masse der
        # haeufigen Stuecke (<=3) nur einen kleinen Wertanteil traegt. Reihen-
        # folge: absteigend nach Summe (top zuerst); Limit nicht noetig, max 10
        # Buckets ueber die Skala. Beantwortet Sammler-Frage "lohnt sich der
        # Versicherungs-Aufwand fuer die Rarit?ten?".
        lines += ["", "Wert pro Seltenheit global (CHF):"]
        for stufe, wert in st.wert_pro_seltenheit_global:
            lines.append(f"  {stufe:>40s} {wert:>12,.0f}")
    if st.gewicht_pro_seltenheit_global:
        # Spiegelbild zu wert_pro_seltenheit_global: typisch liegt die Masse in
        # den haeufigen Stufen (<=3), waehrend die wertvollen Rarit?ten (>=8)
        # leichter sind - die Wert/Gewicht-Entkopplung wird auch auf der
        # Rarity-Achse sichtbar. Sammler-typisch: ein paar Kilo "Haldenquarz"
        # (Stufe 1-2) gegen wenige Gramm Top-Rarit?ten (Stufe 8-10).
        lines += ["", "Gewicht pro Seltenheit global (g):"]
        for stufe, gewicht in st.gewicht_pro_seltenheit_global:
            lines.append(f"  {stufe:>40s} {gewicht:>12,.1f}")
    if st.wert_pro_seltenheit_fundort:
        # Standort-Rarity-Wert-Sicht: spiegelt wert_pro_seltenheit_global, hier
        # auf der lokalen Skala. Lokale Spitze (>=8) und globale Spitze fallen
        # nicht immer zusammen - eine lokale Rarit?t aus einem ausgeschoepften
        # Stollen kann global haeufig (=> wertlich niedriger) bleiben. Beide
        # Bloecke nebeneinander zeigen, ob die Sammlungs-Wertschwerpunkte
        # lokal oder global liegen. Reihenfolge wie wert_pro_seltenheit_global:
        # absteigend nach Summe, max 10 Buckets.
        lines += ["", "Wert pro Seltenheit Fundort (CHF):"]
        for stufe, wert in st.wert_pro_seltenheit_fundort:
            lines.append(f"  {stufe:>40s} {wert:>12,.0f}")
    if st.gewicht_pro_seltenheit_fundort:
        # Spiegelbild zu wert_pro_seltenheit_fundort: Standort-Rarity-Masse-Sicht.
        # Komplementaer zu gewicht_pro_seltenheit_global: zeigt, ob die Sammlungs-
        # masse auf lokal haeufigen Stuecken (Halden-Material) sitzt, auch wenn
        # global eine andere Verteilung herrscht.
        lines += ["", "Gewicht pro Seltenheit Fundort (g):"]
        for stufe, gewicht in st.gewicht_pro_seltenheit_fundort:
            lines.append(f"  {stufe:>40s} {gewicht:>12,.1f}")
    if st.wert_pro_nachfrage:
        # Marktnachfrage-Wert-Sicht: wo liegt der Sammlungswert auf der Demand-
        # Skala? Sammler-typisch vor Boersenbesuch oder Versicherungs-Update:
        # konzentriert sich der Wert auf hochbegehrte Stuecke (>=7, kurzfristig
        # liquidierbar) oder ist er in Tauschmaterial (<=3, schwer absetzbar)
        # gebunden? Reihenfolge analog zu Seltenheit: absteigend nach Summe,
        # max 10 Buckets ueber die Skala.
        lines += ["", "Wert pro Nachfrage (CHF):"]
        for stufe, wert in st.wert_pro_nachfrage:
            lines.append(f"  {stufe:>40s} {wert:>12,.0f}")
    if st.gewicht_pro_nachfrage:
        # Spiegelbild zu wert_pro_nachfrage: wo liegt die Sammlungsmasse auf der
        # Demand-Skala? Typisch sitzt die Masse in der wenig begehrten Mitte/
        # Unteren Skala (Halden-Material, schwer absetzbar), waehrend die
        # Verkaufs-Spitze ueber wenige hochpreisige Stuecke kommt - die Wert/
        # Gewicht-Entkopplung wird auch auf der Marktnachfrage-Achse sichtbar.
        lines += ["", "Gewicht pro Nachfrage (g):"]
        for stufe, gewicht in st.gewicht_pro_nachfrage:
            lines.append(f"  {stufe:>40s} {gewicht:>12,.1f}")
    if st.wert_pro_confidence_bucket:
        # Confidence-Wert-Sicht: spiegelt confidence_buckets (Anzahl) auf die
        # Wert-Achse. Beantwortet "konzentriert sich der Sammlungswert auf
        # sicher identifizierte Stuecke (75-100), oder steckt er gerade in
        # noch unbestimmten / niedrig-confidence-Stuecken (<50/'ohne')?".
        # Sammler-typisch vor Pruefempfehlungs-Abarbeitung: Stuecke im
        # 'ohne'/0-24-Bucket mit hohem Wert sind die wichtigsten naechsten
        # Pruefkandidaten. Reihenfolge: absteigend nach Summe, max 5 Buckets.
        lines += ["", "Wert pro Confidence (CHF):"]
        for bucket, wert in st.wert_pro_confidence_bucket:
            lines.append(f"  {bucket:>40s} {wert:>12,.0f}")
    if st.gewicht_pro_confidence_bucket:
        # Spiegelbild zu wert_pro_confidence_bucket: wo liegt die Sammlungs-
        # masse auf der KI-Bestimmungs-Achse? Typisch sitzt die Masse im
        # 'ohne'-Bucket (schwere Geroellstuecke ohne KI-Analyse), waehrend
        # sicher bestimmte Kristalle (75-100) leicht aber wertvoll sind -
        # die Wert/Gewicht-Entkopplung wird auch auf der Confidence-Achse
        # sichtbar.
        lines += ["", "Gewicht pro Confidence (g):"]
        for bucket, gewicht in st.gewicht_pro_confidence_bucket:
            lines.append(f"  {bucket:>40s} {gewicht:>12,.1f}")
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
            top_gewicht_funddatum_jahr=args.top,
            top_wert_erstellt_am_jahr=args.top,
            top_gewicht_erstellt_am_jahr=args.top,
            top_wert_geaendert_am_jahr=args.top,
            top_gewicht_geaendert_am_jahr=args.top)
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
