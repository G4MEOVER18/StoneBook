"""Aggregierte Kennzahlen über die Objekt-DB (Grundlage für Dashboard/Berichte)."""
from __future__ import annotations

import sqlite3
from dataclasses import dataclass, field

# Felder, die in WERTSUMME einfliessen
WERT_FELDER = (
    "Wert_CHF_roh",
    "Wert_CHF_poliert",
    "Wert_CHF_Schmuck",
    "Marktwert_Industrie",
    "Wissenschaftlicher_Wert_CHF",
)


@dataclass
class Statistik:
    objekte_total: int = 0
    objekte_aktiv: int = 0
    objekte_platzhalter: int = 0
    objekte_archiviert: int = 0
    objekte_mit_bildern: int = 0
    objekte_mit_funddatum: int = 0
    objekte_mit_kategorie: int = 0
    objekte_mit_mineral: int = 0
    objekte_mit_varietaet: int = 0
    objekte_mit_gesteinsart: int = 0
    objekte_mit_kristallsystem: int = 0
    objekte_mit_magnetismus: int = 0
    objekte_mit_glanz: int = 0
    objekte_mit_transparenz: int = 0
    objekte_mit_spaltbarkeit: int = 0
    objekte_mit_bruch: int = 0
    objekte_mit_beste_verwendung: int = 0
    objekte_mit_fundort: int = 0
    objekte_mit_koordinaten: int = 0
    objekte_mit_farbe: int = 0
    objekte_mit_strichfarbe: int = 0
    objekte_mit_hcl_reaktion: int = 0
    objekte_mit_uv_365nm: int = 0
    objekte_mit_uv_254nm: int = 0
    objekte_mit_reaktionshinweis: int = 0
    objekte_mit_pruefempfehlungen: int = 0
    objekte_mit_notizen: int = 0
    bilder_total: int = 0
    aliase_total: int = 0
    objekte_mit_alias: int = 0
    ki_analysen_total: int = 0
    ki_analysen_uebernommen: int = 0
    objekte_mit_ki_analyse: int = 0
    objekte_mit_ki_analyse_uebernommen: int = 0
    mineral_arten_total: int = 0
    fundorte_total: int = 0
    kategorien_total: int = 0
    varietaeten_total: int = 0
    gesteinsarten_total: int = 0
    by_status: dict[str, int] = field(default_factory=dict)
    by_mineral: dict[str, int] = field(default_factory=dict)
    by_varietaet: dict[str, int] = field(default_factory=dict)
    by_gesteinsart: dict[str, int] = field(default_factory=dict)
    by_kategorie: dict[str, int] = field(default_factory=dict)
    by_kristallsystem: dict[str, int] = field(default_factory=dict)
    by_glanz: dict[str, int] = field(default_factory=dict)
    by_transparenz: dict[str, int] = field(default_factory=dict)
    by_magnetismus: dict[str, int] = field(default_factory=dict)
    by_spaltbarkeit: dict[str, int] = field(default_factory=dict)
    by_bruch: dict[str, int] = field(default_factory=dict)
    by_beste_verwendung: dict[str, int] = field(default_factory=dict)
    by_fundort: dict[str, int] = field(default_factory=dict)
    by_funddatum_jahr: dict[str, int] = field(default_factory=dict)
    by_funddatum_jahrzehnt: dict[str, int] = field(default_factory=dict)
    by_funddatum_monat: dict[str, int] = field(default_factory=dict)
    by_erstellt_am_jahr: dict[str, int] = field(default_factory=dict)
    by_erstellt_am_jahrzehnt: dict[str, int] = field(default_factory=dict)
    by_erstellt_am_monat: dict[str, int] = field(default_factory=dict)
    by_geaendert_am_jahr: dict[str, int] = field(default_factory=dict)
    by_geaendert_am_jahrzehnt: dict[str, int] = field(default_factory=dict)
    by_geaendert_am_monat: dict[str, int] = field(default_factory=dict)
    by_seltenheit_global: dict[str, int] = field(default_factory=dict)
    by_seltenheit_fundort: dict[str, int] = field(default_factory=dict)
    by_nachfrage: dict[str, int] = field(default_factory=dict)
    bilder_by_kategorie: dict[str, int] = field(default_factory=dict)
    funddatum_frueheste: str | None = None
    funddatum_spaeteste: str | None = None
    erstellt_am_frueheste: str | None = None
    erstellt_am_spaeteste: str | None = None
    geaendert_am_frueheste: str | None = None
    geaendert_am_spaeteste: str | None = None
    koordinaten_bbox: tuple[float, float, float, float] | None = None
    koordinaten_zentrum: tuple[float, float] | None = None
    koordinaten_radius_max_km: float | None = None
    koordinaten_radius_durchschnitt_km: float | None = None
    koordinaten_radius_median_km: float | None = None
    koordinaten_diameter_km: float | None = None
    mohs_kollektion_min: float | None = None
    mohs_kollektion_max: float | None = None
    mohs_kollektion_durchschnitt: float | None = None
    mohs_kollektion_median: float | None = None
    mohs_kollektion_standardabweichung: float | None = None
    mohs_kollektion_variationskoeffizient_prozent: float | None = None
    mohs_kollektion_spanweite: float | None = None
    dichte_kollektion_min: float | None = None
    dichte_kollektion_max: float | None = None
    dichte_kollektion_durchschnitt: float | None = None
    dichte_kollektion_median: float | None = None
    dichte_kollektion_standardabweichung: float | None = None
    dichte_kollektion_variationskoeffizient_prozent: float | None = None
    dichte_kollektion_spanweite: float | None = None
    wert_summe_chf: float = 0.0
    wert_roh_summe_chf: float = 0.0
    wert_min_chf: float = 0.0
    wert_max_chf: float = 0.0
    wert_durchschnitt_chf: float = 0.0
    wert_median_chf: float = 0.0
    wert_standardabweichung_chf: float = 0.0
    wert_variationskoeffizient_prozent: float | None = None
    wert_spanweite_chf: float = 0.0
    objekte_mit_wert: int = 0
    top_wert_objekte: list[tuple[str, str, float]] = field(default_factory=list)
    top_gewicht_objekte: list[tuple[str, str, float]] = field(default_factory=list)
    top_bilder_objekte: list[tuple[str, str, int]] = field(default_factory=list)
    top_confidence_objekte: list[tuple[str, str, int]] = field(default_factory=list)
    wert_pro_mineral: list[tuple[str, float]] = field(default_factory=list)
    wert_pro_varietaet: list[tuple[str, float]] = field(default_factory=list)
    wert_pro_gesteinsart: list[tuple[str, float]] = field(default_factory=list)
    wert_pro_fundort: list[tuple[str, float]] = field(default_factory=list)
    wert_pro_kategorie: list[tuple[str, float]] = field(default_factory=list)
    wert_pro_kristallsystem: list[tuple[str, float]] = field(default_factory=list)
    wert_pro_glanz: list[tuple[str, float]] = field(default_factory=list)
    wert_pro_transparenz: list[tuple[str, float]] = field(default_factory=list)
    wert_pro_magnetismus: list[tuple[str, float]] = field(default_factory=list)
    wert_pro_spaltbarkeit: list[tuple[str, float]] = field(default_factory=list)
    wert_pro_bruch: list[tuple[str, float]] = field(default_factory=list)
    wert_pro_beste_verwendung: list[tuple[str, float]] = field(default_factory=list)
    wert_pro_status: list[tuple[str, float]] = field(default_factory=list)
    wert_pro_funddatum_jahr: list[tuple[str, float]] = field(default_factory=list)
    wert_pro_funddatum_jahrzehnt: list[tuple[str, float]] = field(default_factory=list)
    wert_pro_funddatum_monat: list[tuple[str, float]] = field(default_factory=list)
    wert_pro_erstellt_am_jahr: list[tuple[str, float]] = field(default_factory=list)
    wert_pro_erstellt_am_jahrzehnt: list[tuple[str, float]] = field(default_factory=list)
    wert_pro_erstellt_am_monat: list[tuple[str, float]] = field(default_factory=list)
    wert_pro_geaendert_am_jahr: list[tuple[str, float]] = field(default_factory=list)
    wert_pro_geaendert_am_jahrzehnt: list[tuple[str, float]] = field(default_factory=list)
    wert_pro_geaendert_am_monat: list[tuple[str, float]] = field(default_factory=list)
    wert_pro_seltenheit_global: list[tuple[str, float]] = field(default_factory=list)
    wert_pro_seltenheit_fundort: list[tuple[str, float]] = field(default_factory=list)
    wert_pro_nachfrage: list[tuple[str, float]] = field(default_factory=list)
    wert_pro_confidence_bucket: list[tuple[str, float]] = field(default_factory=list)
    gewicht_pro_mineral: list[tuple[str, float]] = field(default_factory=list)
    gewicht_pro_varietaet: list[tuple[str, float]] = field(default_factory=list)
    gewicht_pro_gesteinsart: list[tuple[str, float]] = field(default_factory=list)
    gewicht_pro_fundort: list[tuple[str, float]] = field(default_factory=list)
    gewicht_pro_kategorie: list[tuple[str, float]] = field(default_factory=list)
    gewicht_pro_kristallsystem: list[tuple[str, float]] = field(default_factory=list)
    gewicht_pro_glanz: list[tuple[str, float]] = field(default_factory=list)
    gewicht_pro_transparenz: list[tuple[str, float]] = field(default_factory=list)
    gewicht_pro_magnetismus: list[tuple[str, float]] = field(default_factory=list)
    gewicht_pro_spaltbarkeit: list[tuple[str, float]] = field(default_factory=list)
    gewicht_pro_bruch: list[tuple[str, float]] = field(default_factory=list)
    gewicht_pro_beste_verwendung: list[tuple[str, float]] = field(default_factory=list)
    gewicht_pro_status: list[tuple[str, float]] = field(default_factory=list)
    gewicht_pro_funddatum_jahr: list[tuple[str, float]] = field(default_factory=list)
    gewicht_pro_funddatum_jahrzehnt: list[tuple[str, float]] = field(default_factory=list)
    gewicht_pro_funddatum_monat: list[tuple[str, float]] = field(default_factory=list)
    gewicht_pro_erstellt_am_jahr: list[tuple[str, float]] = field(default_factory=list)
    gewicht_pro_erstellt_am_jahrzehnt: list[tuple[str, float]] = field(default_factory=list)
    gewicht_pro_erstellt_am_monat: list[tuple[str, float]] = field(default_factory=list)
    gewicht_pro_geaendert_am_jahr: list[tuple[str, float]] = field(default_factory=list)
    gewicht_pro_geaendert_am_jahrzehnt: list[tuple[str, float]] = field(default_factory=list)
    gewicht_pro_geaendert_am_monat: list[tuple[str, float]] = field(default_factory=list)
    gewicht_pro_seltenheit_global: list[tuple[str, float]] = field(default_factory=list)
    gewicht_pro_seltenheit_fundort: list[tuple[str, float]] = field(default_factory=list)
    gewicht_pro_nachfrage: list[tuple[str, float]] = field(default_factory=list)
    gewicht_pro_confidence_bucket: list[tuple[str, float]] = field(default_factory=list)
    gewicht_summe_g: float = 0.0
    gewicht_durchschnitt_g: float = 0.0
    gewicht_median_g: float = 0.0
    gewicht_min_g: float = 0.0
    gewicht_max_g: float = 0.0
    gewicht_standardabweichung_g: float = 0.0
    gewicht_variationskoeffizient_prozent: float | None = None
    gewicht_spanweite_g: float = 0.0
    objekte_mit_gewicht: int = 0
    objekte_mit_dimensionen: int = 0
    objekte_mit_mohs: int = 0
    objekte_mit_dichte: int = 0
    objekte_mit_seltenheit_global: int = 0
    objekte_mit_seltenheit_fundort: int = 0
    objekte_mit_nachfrage: int = 0
    objekte_mit_confidence: int = 0
    durchschnitt_confidence_prozent: float | None = None
    median_confidence_prozent: float | None = None
    confidence_min_prozent: int | None = None
    confidence_max_prozent: int | None = None
    confidence_standardabweichung_prozent: float | None = None
    confidence_variationskoeffizient_prozent: float | None = None
    confidence_spanweite_prozent: int | None = None
    confidence_buckets: dict[str, int] = field(default_factory=dict)

    def _quote(self, n: int) -> float | None:
        if self.objekte_total <= 0:
            return None
        return n / self.objekte_total * 100.0

    @property
    def quote_mit_bildern_prozent(self) -> float | None:
        return self._quote(self.objekte_mit_bildern)

    @property
    def quote_mit_funddatum_prozent(self) -> float | None:
        return self._quote(self.objekte_mit_funddatum)

    @property
    def quote_mit_wert_prozent(self) -> float | None:
        return self._quote(self.objekte_mit_wert)

    @property
    def quote_mit_gewicht_prozent(self) -> float | None:
        return self._quote(self.objekte_mit_gewicht)

    @property
    def quote_mit_dimensionen_prozent(self) -> float | None:
        # Coverage-Quote fuer geometrische Dimensionen (Laenge_mm / Breite_mm /
        # Hoehe_mm) symmetrisch zu quote_mit_gewicht_prozent auf die geometrische
        # Mess-Achse. Spiegelt die has_dimensionen-Filter-Konvention: ein Objekt
        # zaehlt als dimensioniert, sobald mindestens eine der drei Achsen
        # gemessen ist - in der Praxis wird oft nur die laengste Achse erfasst
        # und die anderen nachgereicht, oder es liegt nur eine Schiebelehre-
        # Messung als Pseudo-Volumen-Achse vor. Eine konjunktive Definition
        # (alle drei gesetzt) waere strenger, wuerde aber den Pflege-Workflow
        # missrepraesentieren - Sammler messen typisch zuerst die laengste
        # Achse als Vitrinen-/Schubladen-Index und ergaenzen Breite/Hoehe
        # spaeter, wenn das Stueck praepariert wird. Komplementaer zu
        # quote_mit_gewicht_prozent (Masse als physikalische Mess-Achse): hier
        # die geometrische Achse. Niedriger Wert ist normal - nicht jedes
        # Stueck wird vermessen (besonders kleine Mineral-Koerner und lose
        # Geroell-Sammlungen), waehrend Gewicht haeufiger erfasst wird (eine
        # Waage liegt eher griffbereit als eine kalibrierte Schiebelehre).
        # Die Differenz quote_mit_gewicht_prozent - quote_mit_dimensionen_prozent
        # beziffert die Vermessungs-Luecke (gewogen, aber nicht vermessen).
        return self._quote(self.objekte_mit_dimensionen)

    @property
    def quote_mit_dichte_prozent(self) -> float | None:
        # Coverage-Quote fuer Dichte (Dichte_min_gcm3 / Dichte_max_gcm3)
        # symmetrisch zu quote_mit_mohs_prozent / quote_mit_dimensionen_prozent /
        # quote_mit_gewicht_prozent auf die physikalische Dichte-Achse. Spiegelt
        # die Mohs-Haerte-Achse exakt: beide sind Bereichsfelder (min/max), beide
        # zaehlen Mineralien als geprueft, sobald eines der beiden Bereichsfelder
        # gesetzt ist - die obere und untere Grenze werden nicht immer zusammen
        # gepflegt, oft steht nur ein Punkt-Wert (Reinmineral) oder eine
        # Roh-Skala ("2.6-2.7" als min=2.6/max=2.7) als Standard-Tabellenwert
        # aus der Mineraldatenbank uebernommen. Vervollstaendigt die physikalische
        # Mess-Reihe: Masse (Gewicht) -> Geometrie (Dimensionen) -> Haerte (Mohs)
        # -> Dichte. Dichte (g/cm3) ist die zweite zentrale quantitative Pruef-
        # Methode neben Mohs: Quarz (~2.65) vs. Calcit (~2.71) sind ueber Mohs
        # (7 vs. 3) sicher trennbar, aber Pyrit (~5.0) vs. Markasit (~4.9) nur
        # ueber Dichte distinkt - beide Mineralien haben Mohs 6-6.5 und
        # metallischen Glanz. Die Messung ist allerdings nicht so trivial wie
        # der Mohs-Kratztest (Wasserverdraengung mit Waage, oder pyknometrische
        # Bestimmung), daher in Sammler-Bestaenden seltener gepflegt als Mohs.
        # Komplementaer zu has_dichte (Listen-Filter) und zum dichte_min/max-
        # Bereichsfilter (konkrete Schwellen): hier die Anteil-Sicht auf den
        # Gesamtbestand. Bisher gab es nur has_dichte und Filter, aber keine
        # Coverage-Kennzahl - waehrend die verwandte physikalische Haerte-Achse
        # mit quote_mit_mohs_prozent bereits abgedeckt war. Aus Datenpflege-Sicht
        # ein direkter naechster Pflege-Indikator nach Mohs: die Differenz
        # quote_mit_mohs_prozent - quote_mit_dichte_prozent beziffert die
        # Dichte-Mess-Luecke (Haerte geprueft, aber Dichte nicht). Whitespace
        # nicht relevant (REAL-Feld, NULL = nicht erfasst), spiegelt das
        # has_dichte-/has_mohs-Verhalten.
        return self._quote(self.objekte_mit_dichte)

    @property
    def quote_mit_mohs_prozent(self) -> float | None:
        # Coverage-Quote fuer Mohs-Haerte (Mohs_Haerte_min / Mohs_Haerte_max)
        # symmetrisch zu quote_mit_dimensionen_prozent / quote_mit_gewicht_prozent
        # auf die physikalische Diagnose-Achse. Mohs ist die zentrale quantitative
        # Haertegrad-Skala fuer Mineralien (1=Talk ... 10=Diamant) und neben
        # Dichte einer der wichtigsten Pruef-Parameter, mit dem Quarz (7) von
        # Calcit (3) oder Fluorit (4) unterscheidbar wird. Spiegelt die
        # has_mohs-Filter-Konvention exakt: ein Objekt zaehlt als geprueft,
        # sobald eines der beiden Bereichsfelder (min ODER max) gesetzt ist -
        # die obere und untere Grenze werden nicht immer zusammen gepflegt,
        # oft steht nur "5-6" als Roh-Skala mit min=5, max=NULL oder umgekehrt.
        # Niedriger Wert ist normal - Mohs wird typisch erst nach Mineral-
        # Bestimmung gepflegt (deterministisch aus der Mineralart ableitbar),
        # viele mineralogisch klare Stuecke bleiben ohne explizite Haerte-
        # Pruefung. Aus Datenpflege-Sicht ein direkter naechster Pflege-
        # Indikator: Stuecke ohne dokumentierte Mohs-Haerte sind die ueblichen
        # Pruefkandidaten fuer den Kratztest (Glas/Stahl/Kupfer-/Fingernagel-
        # Skala). Komplementaer zu has_mohs (Listen-Filter) und zum
        # mohs_min/max-Bereichsfilter (konkrete Schwellen): hier die Anteil-
        # Sicht auf den Gesamtbestand. Whitespace nicht relevant (REAL-Feld,
        # NULL = nicht erfasst).
        return self._quote(self.objekte_mit_mohs)

    @property
    def quote_mit_seltenheit_global_prozent(self) -> float | None:
        # Coverage-Quote fuer Seltenheit_global_1_10 (globale Rarity-Skala 1..10,
        # 1=haeufig .. 10=sehr selten global - die zentrale Markt-/Versicherungs-
        # Achse aus dem Feldwoerterbuch) symmetrisch zu quote_mit_confidence_prozent
        # auf die scale-Skala-Achse. Spiegelt das Coverage-Vokabular der
        # quantitativen Bestimmungs-Achse (Confidence_Prozent, 0..100, mit
        # BETWEEN-Filter und Out-of-Range-Ausschluss) auf die ordinale Rarity-
        # Skala (1..10) - beide sind integer-/scale-Felder mit definiertem
        # Wertebereich, beide haben out-of-range-Werte, die in der Integrity
        # separat gemeldet und in den zentralen Aggregaten ausgeschlossen werden.
        # Komplementaer zu den existierenden Rarity-Sichten: by_seltenheit_global
        # (Verteilungs-Sicht ueber die 10 Skalen-Buckets), wert_pro_seltenheit_global
        # (Wert-Aufteilung je Bucket), gewicht_pro_seltenheit_global (Massen-
        # Aufteilung je Bucket) - hier die Anteil-Sicht auf den Gesamtbestand
        # ("welcher Anteil der Sammlung traegt ueberhaupt einen globalen Rarity-
        # Score?"), waehrend die anderen die innere Verteilung der gepflegten
        # Stuecke beziffern. Aussenkontext-bedingt typisch niedrig in Sammler-
        # Bestaenden, weil die globale Seltenheit-Einschaetzung Marktwissen oder
        # mineralogische Recherche erfordert (Mineraldatenbanken, Tucson-/
        # Mineralientage-Erfahrung, Auktions-Vergleichswerte) - anders als die
        # objektiv am Stueck beobachtbaren Pruefparameter (Glanz/Transparenz/
        # Strichfarbe), die der Sammler ohne Aussenwissen pflegen kann. Aus
        # Datenpflege-Sicht ein direkter Indikator fuer die Bewertungs-Tiefe der
        # Sammlung: Stuecke ohne Rarity-Score sind die ueblichen Pruefkandidaten
        # fuer eine Marktwert-/Versicherungs-Einschaetzung. Out-of-Range-Werte
        # (<1 / >10) zaehlen nicht (sie werden in der Integrity separat gemeldet,
        # spiegelt das objekte_mit_confidence-Verhalten); NULL = nicht erfasst.
        # Whitespace nicht relevant (Integer-Feld). Komplementaer zu
        # by_seltenheit_global/wert_pro_seltenheit_global/gewicht_pro_seltenheit_
        # global (innere Verteilung der gepflegten Stuecke) - hier die Coverage-
        # Sicht ueber den Gesamtbestand.
        return self._quote(self.objekte_mit_seltenheit_global)

    @property
    def quote_mit_seltenheit_fundort_prozent(self) -> float | None:
        # Coverage-Quote fuer Seltenheit_Fundort_1_10 (Standort-Rarity-Skala
        # 1..10, 1=haeufig am Fundort .. 10=sehr selten am Fundort) symmetrisch
        # zu quote_mit_seltenheit_global_prozent auf die zweite ordinale Rarity-
        # Achse aus dem Feldwoerterbuch. Beide sind 1..10-Skalen mit definiertem
        # Wertebereich und teilen denselben out-of-range-Ausschluss (Werte <1
        # oder >10 werden in der Integrity separat gemeldet und in der Coverage-/
        # Verteilungs-Sicht ignoriert) - der Reuse-Pfad ueber
        # sum(by_seltenheit_fundort.values()) garantiert, dass Coverage und
        # by_seltenheit_fundort-Histogramm auf demselben Wertegrund stehen.
        # Komplementaer zur globalen Rarity-Achse: ein Stueck kann am Standort
        # haeufig sein (Quarz aus dem Berner Oberland) und global selten (oder
        # umgekehrt: lokale Rarit?t aus einem ausgeschoepften Stollen, global
        # haeufig). Die Differenz quote_mit_seltenheit_global_prozent -
        # quote_mit_seltenheit_fundort_prozent beziffert die typische Pflege-
        # Asymmetrie zwischen den beiden Rarity-Achsen: die globale Skala ist
        # haeufiger gepflegt, weil sie aus Mineraldatenbanken/Tucson-Erfahrung
        # ableitbar ist, waehrend die Fundort-Skala lokales Fundgebiets-Wissen
        # voraussetzt (welche Mineralen sind in genau diesem Aufschluss/Tagebau/
        # Hoehlen-System haeufig?), das nur Sammler mit eigenen Touren oder
        # Vereins-Berichten haben. Aus Datenpflege-Sicht ein Indikator fuer
        # die Fundgebiets-Erfahrung der Sammlung: Stuecke ohne Fundort-Rarity
        # sind typisch jene aus fremden Bezugsquellen (Boerse/Tausch/Erbe), bei
        # denen das lokale Haeufigkeits-Wissen fehlt. Out-of-Range-Werte (<1 /
        # >10) zaehlen nicht (Integrity meldet separat), NULL = nicht erfasst,
        # Whitespace nicht relevant (Integer-Feld).
        return self._quote(self.objekte_mit_seltenheit_fundort)

    @property
    def quote_mit_nachfrage_prozent(self) -> float | None:
        # Coverage-Quote fuer Nachfrage_1_10 (Marktnachfrage-Skala 1..10,
        # 1=keine Nachfrage .. 10=hoechste Marktnachfrage) symmetrisch zu
        # quote_mit_seltenheit_global_prozent / quote_mit_seltenheit_fundort_
        # prozent auf die dritte ordinale 1..10-Skala aus dem Feldwoerterbuch.
        # Schliesst die Coverage-Reihe der drei Markt-/Bewertungs-Skalen aus
        # dem Feldwoerterbuch ab: Seltenheit_global (Knappheit weltweit),
        # Seltenheit_Fundort (Knappheit am Standort), Nachfrage (Marktdruck der
        # Kaeufer). Reuse-Pfad ueber sum(by_nachfrage.values()) spiegelt das
        # objekte_mit_seltenheit_global-/objekte_mit_seltenheit_fundort-Muster
        # exakt - Out-of-Range-Werte (<1 / >10) sind in beiden ausgeschlossen
        # (Integrity meldet separat), NULL bleibt in keinem Bucket. Aussenkontext-
        # bedingt orthogonal zu den beiden Seltenheits-Achsen: ein Stueck kann
        # global haeufig (Quarz: Rarity-Score 1), am Fundort selten (Bergkristall
        # aus einer ausgeschoepften Kluft: Fundort-Rarity 8) und hoch nachgefragt
        # (Schmuckqualitaet/Polierfaehigkeit: Nachfrage 9) sein - drei verschiedene
        # Kennzahlen, die unabhaengig zur Versicherungs-/Verkaufs-Einschaetzung
        # beitragen. Aus Datenpflege-Sicht ein direkter Indikator fuer die
        # Verkaufsbereitschaft der Sammlung: Stuecke ohne Nachfrage-Score sind
        # die ueblichen Pruefkandidaten vor Boersenbesuch ("welche Stuecke
        # lassen sich tatsaechlich absetzen, welche bleiben Tauschmaterial?").
        # Typisch niedrig in privaten Sammler-Bestaenden, weil die Marktnachfrage
        # ein aktives Marktbeobachtungs-Signal erfordert (Auktions-Ergebnisse,
        # Boersenpreise, Schmuck-Trends) - viele Sammler pflegen ueberhaupt
        # keine Verkaufs-Achse, weil ihre Sammlung nicht zum Verkauf gedacht
        # ist. Komplementaer zu by_nachfrage (Verteilungs-Sicht ueber die 10
        # Skalen-Buckets), wert_pro_nachfrage und gewicht_pro_nachfrage (Wert-/
        # Gewicht-Aufteilung je Bucket): hier die Anteil-Sicht auf den
        # Gesamtbestand. Out-of-Range-Werte (<1 / >10) zaehlen nicht, NULL =
        # nicht erfasst, Whitespace nicht relevant (Integer-Feld).
        return self._quote(self.objekte_mit_nachfrage)

    @property
    def quote_mit_ki_analyse_prozent(self) -> float | None:
        return self._quote(self.objekte_mit_ki_analyse)

    @property
    def quote_mit_confidence_prozent(self) -> float | None:
        # Coverage-Quote fuer Confidence_Prozent (Bestimmungs-Sicherheitsgrad)
        # symmetrisch zu quote_mit_ki_analyse_prozent / quote_mit_ki_analyse_
        # uebernommen_prozent. Spiegelt die KI-Analyse-Quoten auf die separate
        # Confidence-Achse: KI-Analyse misst, ob ueberhaupt eine Bestimmung
        # mit KI-Unterstuetzung gelaufen ist (Anwendungs-Durchdringung),
        # uebernommen misst die Akzeptanz der Vorschlaege (Pflege-Akzeptanz),
        # und Confidence misst, ob das Stueck einen quantitativen Sicherheits-
        # Score (0-100) traegt - unabhaengig davon, ob er vom Sammler oder
        # von der KI gesetzt wurde. Aussenkontext-bedingt orthogonal zur KI-
        # Analyse-Achse: ein Stueck kann eine handgepflegte Confidence von
        # 90 % tragen, ohne dass jemals eine KI-Analyse lief; umgekehrt
        # koennen KI-Analysen ohne Confidence-Uebertragung bleiben.
        # Komplementaer zu durchschnitt_/median_confidence_prozent (zentrale
        # Tendenz unter den vorhandenen Werten) und confidence_buckets
        # (Verteilung unter den vorhandenen Werten): hier die Coverage-Sicht
        # ueber den Gesamtbestand ("welcher Anteil der Sammlung traegt
        # ueberhaupt einen Sicherheits-Score?"), waehrend die anderen die
        # innere Verteilung beziffern. Aus Datenpflege-Sicht ein wichtiger
        # naechster Pflege-Indikator: Stuecke ohne Confidence sind die
        # ueblichen Pruefkandidaten, weil sie weder als sicher (>=75) noch
        # als unsicher (<25) markiert sind. Out-of-Range-Werte (<0 / >100)
        # zaehlen nicht (sie werden in der Integrity separat gemeldet,
        # spiegelt das median_confidence-Verhalten); Whitespace nicht
        # relevant (Integer-Feld, NULL = nicht erfasst).
        return self._quote(self.objekte_mit_confidence)

    @property
    def quote_mit_kategorie_prozent(self) -> float | None:
        # Coverage-Quote fuer Objekt-Kategorie (Inventar-Klassifizierung)
        # symmetrisch zu Bildern/Funddatum/Wert/Gewicht/KI-Analyse/Mineral/Fundort.
        # Kategorie (Mineral-Korn/Handstueck/Duennschliff/Kristall/Geroell/Sonstiges)
        # ist die erste Inventar-Achse - sie sagt, was das Stueck physisch ueberhaupt
        # ist, bevor mineralogische Bestimmung (Mineral_Primaer) oder Provenienz
        # (Fundort) sinnvoll werden. Vervollstaendigt die ID-Gruppe der Coverage-
        # Quoten neben quote_mit_mineral_prozent (Was ist das Mineral?) und
        # quote_mit_fundort_prozent (Wo wurde es gefunden?). Niedriger Wert
        # deutet auf einen frisch importierten Bestand vor Inventar-Vorklassifizierung
        # oder Migrations-Restbestaende ohne Kategorie-Spalte in den alten v1/
        # obj043-CSVs (die haben keine Kategorie). Whitespace zaehlt wie leer
        # (spiegelt has_kategorie-Filter-Konvention).
        return self._quote(self.objekte_mit_kategorie)

    @property
    def quote_mit_mineral_prozent(self) -> float | None:
        return self._quote(self.objekte_mit_mineral)

    @property
    def quote_mit_varietaet_prozent(self) -> float | None:
        # Coverage-Quote fuer Varietaet (mineralogische Sub-Klassifizierung)
        # symmetrisch zu quote_mit_mineral_prozent. Varietaet ist die feinere
        # Sub-Achse unter Mineral_Primaer (Bergkristall/Milchquarz/Rauchquarz
        # innerhalb der Quarz-Familie); Mineral_Primaer beantwortet "welche
        # Mineral-Familie", Varietaet "welche Auspraegung in der Familie".
        # Komplementaer zu by_varietaet (Streuung-Sicht ueber die Varietaeten)
        # und has_varietaet (Listen-Filter): hier die Coverage-Sicht
        # ("welcher Anteil der Sammlung ist auf der feineren Sub-Achse
        # bestimmt?"). Niedriger Wert ist normal - Varietaet wird typisch erst
        # nach Mineral_Primaer-Bestimmung gepflegt, viele Stuecke bleiben auf
        # der Mineral-Familie stehen ohne weitere Sub-Klassifizierung. Die
        # Differenz quote_mit_mineral_prozent - quote_mit_varietaet_prozent
        # beziffert die Sub-Klassifizierungs-Luecke (Stuecke mit Familie, aber
        # ohne Auspraegung). Whitespace zaehlt wie leer (spiegelt
        # has_varietaet-Filter-Konvention).
        return self._quote(self.objekte_mit_varietaet)

    @property
    def quote_mit_gesteinsart_prozent(self) -> float | None:
        # Coverage-Quote fuer Gesteinsart (petrologische Gesteins-Einordnung)
        # symmetrisch zu quote_mit_mineral_prozent / quote_mit_varietaet_prozent.
        # Mineral_Primaer beantwortet "welche Mineral-Familie?" (mineralogische
        # Achse), Varietaet "welche Auspraegung in der Familie?" (mineralogische
        # Sub-Achse) - Gesteinsart "in welcher Gesteins-Einbettung?" (petrologische
        # Achse). Granit/Gneis/Basalt/Sandstein gruppieren Stuecke nach
        # geologischem Zusammenhang, der weder durch Mineral_Primaer (mineralogisch)
        # noch durch Kategorie (Form/Aufbewahrung) abgedeckt ist - ein Quarz-Stueck
        # kann aus Pegmatit oder Hydrothermal-Ader stammen, der mineralogische
        # Befund bleibt gleich aber die Gesteinsart sagt etwas anderes ueber den
        # geologischen Bildungs-Kontext aus. Komplementaer zu by_gesteinsart
        # (Streuung-Sicht ueber die Gesteinsarten) und has_gesteinsart/
        # gesteinsart_in (Listen-Filter): hier die Coverage-Sicht
        # ("welcher Anteil der Sammlung ist petrologisch eingeordnet?").
        # Niedriger Wert ist normal - Gesteinsart wird typisch erst nach
        # Mineral_Primaer-Bestimmung gepflegt (wenn ueberhaupt), viele
        # mineralogisch klare Stuecke bleiben ohne petrologische Einordnung
        # stehen (besonders bei Einzel-Kristallen, fuer die die Gesteins-
        # Einbettung beim Sammeln nicht dokumentiert wurde). Whitespace zaehlt
        # wie leer (spiegelt has_gesteinsart-Filter-Konvention).
        return self._quote(self.objekte_mit_gesteinsart)

    @property
    def quote_mit_kristallsystem_prozent(self) -> float | None:
        # Coverage-Quote fuer Kristallsystem (kristallographische Symmetrie-
        # Klassifizierung) symmetrisch zu quote_mit_mineral_prozent /
        # quote_mit_varietaet_prozent / quote_mit_gesteinsart_prozent. Spiegelt
        # die mineralogischen / petrologischen Achsen auf die kristallographische:
        # Mineral_Primaer beantwortet "welche Mineral-Familie?" (Quarz/Calcit/
        # Pyrit), Varietaet "welche Auspraegung in der Familie?" (Bergkristall/
        # Milchquarz), Gesteinsart "in welcher Gesteins-Einbettung?" (Granit/
        # Basalt), Kristallsystem "welcher Symmetrietyp?" (kubisch/tetragonal/
        # hexagonal/trigonal/orthorhombisch/monoklin/triklin/amorph - 7+1 Enum-
        # Werte aus dem Feldwoerterbuch). Niedriger Wert ist normal - Kristall-
        # system wird typisch erst nach Mineral_Primaer-Bestimmung gepflegt
        # (deterministisch aus der Mineralart ableitbar, aber haendisch zu
        # uebernehmen), viele mineralogisch klare Stuecke bleiben ohne
        # Symmetrietyp-Einordnung. Komplementaer zu by_kristallsystem
        # (Streuung-Sicht ueber die Symmetrietypen) und has_kristallsystem
        # (Listen-Filter): hier die Coverage-Sicht ("welcher Anteil der
        # Sammlung ist kristallographisch eingeordnet?"). Whitespace zaehlt
        # wie leer (spiegelt has_kristallsystem-Filter-Konvention).
        return self._quote(self.objekte_mit_kristallsystem)

    @property
    def quote_mit_magnetismus_prozent(self) -> float | None:
        # Coverage-Quote fuer Magnetismus (qualitative magnetische Reaktion)
        # symmetrisch zu quote_mit_kristallsystem_prozent auf die magnetisch-
        # physikalische Pruef-Achse. Spiegelt die kristallographische Symmetrie-
        # Achse auf die magnetische Reaktions-Achse: Kristallsystem klassifiziert
        # den inneren Symmetrie-Aufbau (kubisch/tetragonal/...), Magnetismus die
        # qualitative Eisengehalts-Reaktion (nein/schwach/ja - die drei Enum-
        # Werte aus dem Feldwoerterbuch). Aussenkontext-bedingt orthogonal zur
        # mineralogischen Identifikations-Achse (Mineral_Primaer): Magnetismus
        # ist ein billig zu testender Pruefparameter (Hand-/Neodym-Magnet),
        # der bei vielen typischen Sammler-Mineralen (Quarz, Calcit, Pyrit) das
        # offensichtlich-negative Ergebnis liefert, aber dort ueberhaupt nicht
        # dokumentiert wird, weil die Reaktion erwartet-negativ war - das
        # entspricht der typischen Pflege-Luecke bei objekte_mit_magnetismus.
        # Komplementaer zu by_magnetismus (distinkte Werte, Streuung-Sicht)
        # und wert_/gewicht_pro_magnetismus (Wert-/Gewicht-Aufteilung pro
        # Reaktions-Stufe): hier die Coverage-Sicht ueber den Gesamtbestand
        # ("welcher Anteil der Sammlung ist auf der magnetischen Achse
        # geprueft?"). Niedriger Wert ist normal - Sammler dokumentieren
        # haeufig nur die positiven Magnetismus-Treffer (Magnetit, Pyrrhotin)
        # und lassen die offensichtlich-negativen Mineralen ohne expliziten
        # "nein"-Eintrag stehen. Aus Datenpflege-Sicht ist die Quote ein
        # direkter Indikator fuer die Vollstaendigkeit der qualitativen
        # Pruefparameter-Achse (neben HCl-Reaktion und Strichfarbe, die als
        # freie str-Felder keine vergleichbare Enum-Coverage haben). Whitespace
        # zaehlt wie leer (spiegelt has_magnetismus-Filter-Konvention).
        return self._quote(self.objekte_mit_magnetismus)

    @property
    def quote_mit_glanz_prozent(self) -> float | None:
        # Coverage-Quote fuer Glanz (optische Oberflaechen-Reflexion: glasig/
        # wachsig/matt/metallisch/fettig/seidig/perlmutt - die sieben Enum-Werte
        # aus dem Feldwoerterbuch) symmetrisch zu quote_mit_kristallsystem_prozent
        # / quote_mit_magnetismus_prozent auf die optisch-physikalische Diagnose-
        # Achse. Spiegelt die magnetische Reaktions-Achse auf die optische
        # Reflexions-Achse: Magnetismus klassifiziert die qualitative Eisengehalts-
        # Reaktion (mit Hand-/Neodym-Magnet pruefbar), Glanz die qualitative
        # Oberflaechen-Reflexion (visuell pruefbar unter Standard-Beleuchtung) -
        # beide sind kurze Enum-Skalen aus dem Feldwoerterbuch und beide spiegeln
        # qualitative Pruef-Schritte ohne instrumentelle Mess-Mittel. Bisher gab
        # es nur by_glanz (Streuung-Sicht), has_glanz (Listen-Filter) und wert_/
        # gewicht_pro_glanz (Wert-/Gewicht-Aufteilung), aber keine Coverage-
        # Kennzahl (Anteil-Sicht auf den Gesamtbestand) - waehrend die verwandte
        # qualitative Pruef-Achse mit quote_mit_magnetismus_prozent bereits
        # abgedeckt war. Aussenkontext-bedingt orthogonal zur mineralogischen
        # Identifikations-Achse (Mineral_Primaer): Glanz ist ein billig zu
        # beobachtender Pruefparameter (das blosse Auge unter normaler Beleuchtung
        # reicht), aber gerade weil er so offensichtlich ist, vergessen Sammler
        # haeufig, ihn explizit zu dokumentieren - "natuerlich ist Quarz glasig,
        # wozu soll ich das aufschreiben?" entspricht der typischen Pflege-
        # Luecke bei objekte_mit_glanz. Komplementaer zu by_glanz (distinkte
        # Werte, Streuung-Sicht) und wert_/gewicht_pro_glanz (Wert-/Gewicht-
        # Aufteilung pro Reflexions-Typ): hier die Coverage-Sicht ueber den
        # Gesamtbestand ("welcher Anteil der Sammlung ist auf der optischen
        # Achse charakterisiert?"). Whitespace zaehlt wie leer (spiegelt
        # has_glanz-Filter-Konvention).
        return self._quote(self.objekte_mit_glanz)

    @property
    def quote_mit_transparenz_prozent(self) -> float | None:
        # Coverage-Quote fuer Transparenz (Lichtdurchlaessigkeit: durchsichtig/
        # durchscheinend/opak - die drei Enum-Werte aus dem Feldwoerterbuch)
        # symmetrisch zu quote_mit_glanz_prozent / quote_mit_magnetismus_prozent
        # auf die optisch-physikalische Diagnose-Achse. Spiegelt die
        # Oberflaechen-Reflexions-Achse auf die Lichtdurchlaessigkeits-Achse:
        # Glanz klassifiziert die qualitative Oberflaechen-Reflexion (visuell
        # pruefbar in Auflicht/Front-Beleuchtung), Transparenz die qualitative
        # Lichtdurchlaessigkeit (visuell pruefbar in Durchlicht/Gegenlicht) -
        # beide sind kurze Enum-Skalen aus dem Feldwoerterbuch, beide spiegeln
        # qualitative Pruef-Schritte ohne instrumentelle Mess-Mittel, beide
        # zielen auf den optischen Eindruck unter Standard-Beleuchtung.
        # Bisher gab es nur by_transparenz (Streuung-Sicht) und has_transparenz
        # (Listen-Filter) plus wert_/gewicht_pro_transparenz (Wert-/Gewicht-
        # Aufteilung), aber keine Coverage-Kennzahl (Anteil-Sicht auf den
        # Gesamtbestand) - waehrend die verwandte optische Achse mit
        # quote_mit_glanz_prozent bereits abgedeckt war. Schliesst die Coverage-
        # Reihe der optischen Diagnose-Achsen: Glanz (Auflicht/Reflexion) ->
        # Transparenz (Durchlicht/Durchlaessigkeit). Aussenkontext-bedingt
        # orthogonal zur mineralogischen Identifikations-Achse (Mineral_Primaer):
        # Transparenz ist ein billig zu beobachtender Pruefparameter (eine
        # Lichtquelle reicht), aber gerade weil er so offensichtlich ist,
        # vergessen Sammler haeufig, ihn explizit zu dokumentieren ("natuerlich
        # ist Quarz durchsichtig, wozu soll ich das aufschreiben?") - das
        # entspricht der typischen Pflege-Luecke bei objekte_mit_transparenz,
        # spiegelt die Glanz-Luecke. Aus Datenpflege-Sicht ein direkter
        # Indikator fuer die Vollstaendigkeit der qualitativen optischen
        # Diagnose-Achse (Transparenz ist neben Glanz die zweite optische
        # Charakteristik im Feldwoerterbuch und der einzige der beiden mit
        # einer 3-Stufen-Skala - Glanz hat sieben Stufen). Komplementaer zu
        # by_transparenz (distinkte Werte, Streuung-Sicht) und has_transparenz
        # (Listen-Filter); beide gemeinsam geben Auskunft ueber Vollstaendigkeit
        # vs. Streuung der optischen Pruefung. Whitespace zaehlt wie leer
        # (spiegelt has_transparenz-Filter-Konvention).
        return self._quote(self.objekte_mit_transparenz)

    @property
    def quote_mit_spaltbarkeit_prozent(self) -> float | None:
        # Coverage-Quote fuer Spaltbarkeit (mechanisch-strukturelles Bruchverhalten
        # entlang kristallographisch bevorzugter Ebenen: vollkommen/gut/deutlich/
        # undeutlich/keine - die fuenf Enum-Werte aus dem Feldwoerterbuch)
        # symmetrisch zu quote_mit_glanz_prozent / quote_mit_transparenz_prozent /
        # quote_mit_magnetismus_prozent auf die mechanisch-strukturelle Diagnose-
        # Achse. Spiegelt die optische Diagnose-Doppel-Achse (Glanz/Transparenz)
        # und die magnetische Reaktions-Achse auf die mechanische Achse: waehrend
        # Glanz und Transparenz die optische Eigenschaft beschreiben und
        # Magnetismus die qualitative Eisengehalts-Reaktion, beschreibt
        # Spaltbarkeit das mechanische Bruchverhalten - ob das Mineral entlang
        # bevorzugter Kristallebenen spaltet (Glimmer: vollkommen blaettrig;
        # Calcit/Halit: gut wuerfelig/rhomboedrisch) oder unregelmaessig bricht
        # (Quarz: keine Spaltbarkeit, nur Bruch). Bisher gab es nur by_spaltbarkeit
        # (Streuung-Sicht), has_spaltbarkeit (Listen-Filter) und wert_pro_
        # spaltbarkeit (Wert-Aufteilung), aber keine Coverage-Kennzahl (Anteil-
        # Sicht auf den Gesamtbestand) - waehrend die verwandten qualitativen
        # Pruef-Achsen (optisch, magnetisch) bereits Coverage-Quoten haben.
        # Aussenkontext-bedingt komplementaer zu quote_mit_bruch_prozent (wenn
        # vorhanden): Spaltbarkeit beschreibt die geordnete Bruchrichtung
        # (kristallographisch determiniert), Bruch das ungeordnete Versagen
        # ausserhalb der Spaltebenen (muschelig/uneben/...) - beide sind
        # paarweise Eintragspunkte einer Hammertest-/Pruefnotiz. Aus Datenpflege-
        # Sicht ist Spaltbarkeit ein zentraler Diagnose-Parameter, weil die
        # Kombination Spaltbarkeit-vollkommen + Mohs-niedrig (Glimmer, Calcit,
        # Galenit) eine eindeutige Mineral-Klasse markiert; die Quote zeigt, wie
        # gross der Pflege-Restbestand auf dieser Bestimmungs-Achse ist. Niedriger
        # Wert ist typisch in Sammler-Bestaenden, weil der Hammertest invasiv ist
        # (man muss ein Stueck schlagen, um die Spaltflaechen zu sehen) und
        # daher seltener routinemaessig durchgefuehrt wird als optische oder
        # magnetische Pruefungen - viele Stuecke bleiben ohne dokumentierte
        # Spaltbarkeit stehen. Aus Datenpflege-Sicht ein direkter Indikator
        # fuer die Vollstaendigkeit der mechanischen Diagnose-Achse. Komplementaer
        # zu by_spaltbarkeit (distinkte Werte, Streuung-Sicht) und has_spaltbarkeit
        # (Listen-Filter); beide gemeinsam geben Auskunft ueber Vollstaendigkeit
        # vs. Streuung der mechanischen Pruefung. Whitespace zaehlt wie leer
        # (spiegelt has_spaltbarkeit-Filter-Konvention).
        return self._quote(self.objekte_mit_spaltbarkeit)

    @property
    def quote_mit_bruch_prozent(self) -> float | None:
        # Coverage-Quote fuer Bruch (ungeordnetes mechanisches Versagen ausserhalb
        # der Spaltebenen: muschelig/uneben/splittrig/faserig/erdig/glatt - die
        # sechs Enum-Werte aus dem Feldwoerterbuch) symmetrisch zu
        # quote_mit_spaltbarkeit_prozent auf die mechanisch-strukturelle
        # Diagnose-Achse. Spiegelt die Spaltbarkeits-Achse (geordnete Bruch-
        # richtung entlang kristallographisch bevorzugter Ebenen) exakt:
        # waehrend Spaltbarkeit beschreibt, ob das Mineral entlang bevorzugter
        # Ebenen spaltet (Glimmer: vollkommen blaettrig, Calcit: gut rhomboedrisch),
        # beschreibt Bruch das Versagensmuster ausserhalb der Spaltebenen
        # (Quarz: muschelig wie Glasbruch, Pyrit: uneben-hakig, Asbest: faserig,
        # Limonit: erdig, Obsidian: glatt-muschelig). Beide sind paarweise
        # Eintragspunkte einer Hammertest-/Pruefnotiz, gemeinsam ergeben sie das
        # vollstaendige mechanische Versagensbild eines Stuecks. Bisher gab es
        # nur by_bruch (Streuung-Sicht), has_bruch (Listen-Filter) und
        # wert_pro_bruch / gewicht_pro_bruch (Wert-/Gewicht-Aufteilung), aber
        # keine Coverage-Kennzahl (Anteil-Sicht auf den Gesamtbestand) - waehrend
        # die paarweise Spaltbarkeits-Achse mit quote_mit_spaltbarkeit_prozent
        # bereits abgedeckt war. Schliesst die Coverage-Reihe der mechanisch-
        # strukturellen Diagnose-Doppel-Achse: Spaltbarkeit (geordnete
        # Bruchrichtung) -> Bruch (ungeordnetes Versagen). Aussenkontext-bedingt
        # komplementaer zu quote_mit_spaltbarkeit_prozent: Stuecke mit
        # vollkommener Spaltbarkeit (Glimmer/Calcit/Galenit) brauchen oft keinen
        # separaten Bruch-Eintrag (das Versagen folgt den Spaltebenen), waehrend
        # Stuecke ohne Spaltbarkeit (Quarz: keine) ihren Bruch am deutlichsten
        # zeigen - die Differenz beider Quoten beziffert die mechanische
        # Pflege-Luecke (Spaltbarkeit geprueft, aber Bruch nicht oder umgekehrt).
        # Aus Datenpflege-Sicht ist Bruch der wichtigere Diagnose-Parameter bei
        # spaltbarkeits-armen Mineralen (Quarz, Opal, Obsidian, Chalcedon - alle
        # mit muscheligem Bruch als Haupt-Kennzeichen), waehrend Spaltbarkeit
        # bei spaltungs-reichen Mineralen (Glimmer, Calcit, Galenit) dominiert.
        # Niedriger Wert ist typisch in Sammler-Bestaenden, weil der Hammertest
        # invasiv ist (man muss ein Stueck schlagen, um die Bruchflaeche zu
        # sehen - bei Vitrinen-/Tausch-Stuecken vermeidet man das) und daher
        # seltener routinemaessig durchgefuehrt wird als optische oder
        # magnetische Pruefungen; spiegelt das Pflege-Verhalten bei
        # Spaltbarkeit. Komplementaer zu by_bruch (distinkte Werte, Streuung-
        # Sicht) und has_bruch (Listen-Filter); beide gemeinsam geben Auskunft
        # ueber Vollstaendigkeit vs. Streuung der mechanischen Pruefung.
        # Whitespace zaehlt wie leer (spiegelt has_bruch-Filter-Konvention).
        return self._quote(self.objekte_mit_bruch)

    @property
    def quote_mit_beste_verwendung_prozent(self) -> float | None:
        # Coverage-Quote fuer Beste_Verwendung (empfohlene Verwendungs-Kategorie:
        # Schmuck/Sammlung/Forschung/Industrie/Talisman/Dekoration - die sechs
        # Enum-Werte aus dem Feldwoerterbuch) symmetrisch zu den Coverage-Quoten
        # der uebrigen Enum-Felder (Kategorie/Kristallsystem/Magnetismus/Glanz/
        # Transparenz/Spaltbarkeit/Bruch). Spiegelt die Coverage-Reihe der
        # strukturierten Enum-Achsen aus dem Feldwoerterbuch auf die letzte
        # bisher fehlende Enum-Achse: waehrend Kategorie die Inventar-Achse
        # ("was ist das Stueck physisch?"), die mineralogisch-strukturellen
        # Achsen (Mineral/Varietaet/Gesteinsart/Kristallsystem) die Bestimmungs-
        # Achse, und die physikalisch-qualitativen Achsen (Magnetismus/Glanz/
        # Transparenz/Spaltbarkeit/Bruch) die Diagnose-Achse abdecken, zielt
        # Beste_Verwendung auf die Verwendungs-/Empfehlungs-Achse: was sollte
        # mit dem Stueck geschehen? Aussenkontext-bedingt orthogonal zu den
        # uebrigen Coverage-Quoten - die Verwendungs-Empfehlung ist keine
        # Beobachtung am Stueck (wie Glanz/Magnetismus), sondern eine subjektive
        # Sammler-Entscheidung ueber den weiteren Lebensweg ("dieser Achat
        # gehoert poliert in den Schmuck"; "dieses Kristall-Stueck bleibt in
        # der Vitrine"; "dieser Lapislazuli geht in den Verkauf").
        # Komplementaer zu by_beste_verwendung (Streuung-Sicht ueber die
        # Verwendungs-Kategorien), has_beste_verwendung (Listen-Filter) und
        # wert_pro_beste_verwendung / gewicht_pro_beste_verwendung (Wert-/
        # Gewicht-Aufteilung pro Verwendungs-Kategorie): hier die Coverage-
        # Sicht ueber den Gesamtbestand ("welcher Anteil der Sammlung hat
        # ueberhaupt eine Verwendungs-Empfehlung?"). Bisher gab es alle drei
        # umliegenden Sichten, aber keine Anteil-Sicht auf den Gesamtbestand -
        # die letzte fehlende Coverage-Quote der strukturierten Enum-Felder.
        # Aus Datenpflege-Sicht ein direkter Indikator fuer die Verkaufs-/
        # Pflege-Planung: Stuecke ohne dokumentierte Verwendung sind die
        # ueblichen Pruefkandidaten fuer eine Sammler-Entscheidung ("was tue
        # ich mit diesem Stueck?"). Niedriger Wert ist typisch in unsortierten
        # Bestaenden (frisch importiert, noch nicht durchgesehen) oder bei
        # reinen Wissenschafts-Sammlungen, in denen die Verwendung gar nicht
        # zur Debatte steht (alle Stuecke fuer Forschung). Whitespace zaehlt
        # wie leer (spiegelt has_beste_verwendung-Filter-Konvention).
        return self._quote(self.objekte_mit_beste_verwendung)

    @property
    def quote_mit_fundort_prozent(self) -> float | None:
        # Coverage-Quote fuer Fundort (Fundort-Dokumentation) symmetrisch zu
        # Bildern/Funddatum/Wert/Gewicht/KI-Analyse/Mineral. Fundort ist die
        # geografische Provenienz-Achse - ohne ihn fehlt der Sammlungs-Kontext
        # ("Quarz aus dem Berner Oberland" vs. "Quarz, unbekannte Herkunft"
        # haben fuer Sammler/Forscher/Versicherung unterschiedlichen Aussage-
        # gehalt). Spiegelt die mineralogische Identifikations-Achse
        # (quote_mit_mineral) auf die geografische Provenienz-Achse - beide
        # zusammen liefern die Kern-Identitaet eines Sammlungsstuecks.
        # Whitespace zaehlt wie leer (spiegelt has_fundort-Filter-Konvention).
        return self._quote(self.objekte_mit_fundort)

    @property
    def quote_mit_koordinaten_prozent(self) -> float | None:
        # Geocoded-Subset-Coverage: Anteil der Objekte, deren Fundort-Eintrag
        # ein per parse_coordinates erkennbares Lat/Lon-Paar enthaelt. Bezugs-
        # menge bleibt objekte_total (nicht objekte_mit_fundort), damit die
        # Quote direkt mit den uebrigen quote_mit_X_prozent vergleichbar ist
        # ("welcher Anteil der gesamten Sammlung ist geografisch geocoded?"
        # statt "welcher Anteil der bereits dokumentierten Fundorte..."). Die
        # zwei-stufige Differenz (quote_mit_fundort - quote_mit_koordinaten)
        # beziffert den freitext-only-Anteil ("Berner Oberland", "alte Halde
        # bei X"), also den Pflege-Aufwand fuer eine vollstaendige Geocoding-
        # Ergaenzung ohne neue Fundort-Akquise. Komplementaer zu der
        # repository-Bounding-Box-Achse (list_objects_in_bbox): waehrend die
        # Box-Abfrage punktuell auf ein Suchgebiet zugreift, beziffert die
        # Coverage-Quote die Voraussetzung der Box-Abfrage selbst ("wie viel
        # meiner Sammlung ist ueberhaupt fuer geografische Filter erreichbar?").
        # Niedriger Wert ist typisch bei historisch gewachsenen Sammlungen mit
        # Ortsnamen-only-Eintraegen aus Vor-GPS-Zeit; ein steigender Trend
        # zeigt nachtraegliche Geocoding-Pflege oder neuere Touren mit GPS-
        # protokollierten Fundpunkten. Whitespace und nicht-parsebare Frei-
        # text-Eintraege zaehlen wie nicht-geocoded (spiegelt das None-
        # Verhalten von parse_coordinates).
        return self._quote(self.objekte_mit_koordinaten)

    @property
    def quote_mit_farbe_prozent(self) -> float | None:
        # Coverage-Quote fuer Farbe_beobachtet (tatsaechlich gesehene Farbe(n)
        # eines Stuecks - die niederschwelligste visuelle Diagnose-Achse aus
        # dem Feldwoerterbuch). Spiegelt die Enum-Coverage-Quoten der optischen
        # Achsen (quote_mit_glanz_prozent / quote_mit_transparenz_prozent) auf
        # die freie str-Farb-Achse: waehrend Glanz die Oberflaechen-Reflexion
        # (glasig/matt/metallisch/...) und Transparenz die Lichtdurchlaessigkeit
        # (durchsichtig/durchscheinend/opak) auf Enum-Skalen beziffert, beziffert
        # Farbe_beobachtet die wahrgenommene Mineral-Farbe selbst (rot/gruen/
        # blau/braun/schwarz/...). Komplementaer zu quote_mit_strichfarbe_prozent
        # (Farbe des abgeriebenen Pulvers): waehrend Strichfarbe diagnostisch
        # invariant ist (Pyrit immer gruenlich-schwarz, Hematit immer ziegelrot),
        # variiert die beobachtete Farbe innerhalb einer Mineral-Art stark
        # (Quarz von farblos ueber gelb/rosa/rauchgrau/violett bis schwarz; Calcit
        # von weiss ueber gelb/orange/blaeulich bis schwarz). Beide Farb-Achsen
        # zusammen ergeben das vollstaendige Farb-Profil eines Stuecks. Bisher
        # gab es nur den has_farbe-Filter (Listen-Filter, Anwesenheits-Pruefung)
        # und das wahlfreie repository.filter_objects-Argument, aber keine
        # Coverage-Kennzahl (Anteil-Sicht auf den Gesamtbestand) - waehrend die
        # umliegenden visuellen Pruef-Achsen (Glanz/Transparenz) und die
        # paarweise Strichfarbe bereits Coverage-Quoten haben. Aussenkontext-
        # bedingt typisch hoch im Vergleich zu den anderen Pruef-Achsen, weil
        # Farb-Beobachtung die niederschwelligste Diagnose-Achse ueberhaupt ist
        # (keine Werkzeuge noetig, kein invasiver Eingriff, am Tageslicht
        # beobachtbar - spiegelt das Pflege-Verhalten der ebenfalls non-
        # invasiven Glanz-/Transparenz-Pruefungen). Eine niedrige Quote weist
        # auf einen unvollstaendig erfassten Bestand hin (selbst der erste
        # Blick auf das Stueck fehlt im Datensatz) - der direkte Indikator
        # fuer die Basis-Erfassungs-Tiefe. Whitespace zaehlt wie leer, spiegelt
        # die has_X-Filter-Konvention der umliegenden freien str-Spalten
        # (Fundort/Notizen/Strichfarbe).
        return self._quote(self.objekte_mit_farbe)

    @property
    def quote_mit_strichfarbe_prozent(self) -> float | None:
        # Coverage-Quote fuer Strichfarbe (Farbe des Pulvers auf
        # Porzellan-Strichplaettchen, eines der drei klassischen qualitativen
        # Bestimmungs-Pruefparameter neben HCl-Reaktion und Magnetismus).
        # Spiegelt die Enum-Coverage-Quoten der qualitativen Pruef-Achsen
        # (quote_mit_magnetismus_prozent als Enum-validierte Reaktions-Achse)
        # auf die zwei verbleibenden freien str-Pruefparameter aus dem
        # Feldwoerterbuch. Strichfarbe ist eine der zuverlaessigsten
        # Diagnose-Achsen ueberhaupt - bei vielen visuell aehnlichen
        # Mineralien (Pyrit gelb-metallisch, Goldspecimen gelb-metallisch)
        # ist der Strich der eindeutige Trenner (Pyrit: gruenlich-schwarz,
        # Gold: gelb-metallisch), waehrend andere Pruef-Achsen versagen.
        # Bisher gab es weder eine Anwesenheits-Pruefung (has_strichfarbe-
        # Filter fehlt ebenfalls) noch eine Coverage-Kennzahl, waehrend alle
        # umliegenden Pruef-Achsen (Magnetismus, Glanz, Transparenz,
        # Spaltbarkeit, Bruch) bereits eine Coverage-Quote tragen.
        # Aussenkontext-bedingt niedrig - der Strichtest erfordert eine
        # Porzellan-Strichplaette (10 EUR Material), ist invasiv (das
        # Mineral wird abgerieben) und wird daher seltener routinemaessig
        # durchgefuehrt als die non-invasiven optischen Pruefungen (Glanz/
        # Transparenz, beobachtbar ohne Werkzeug). Aus Datenpflege-Sicht
        # ein direkter Indikator fuer die Tiefe der mineralogischen
        # Bestimmungs-Pflege: ein Stueck mit dokumentierter Strichfarbe
        # ist mit hoher Wahrscheinlichkeit auch korrekt mineralogisch
        # bestimmt (der Strichtest wird typisch erst nach erster Mineral-
        # Hypothese als Bestaetigung durchgefuehrt), waehrend ein Stueck
        # ohne Strichfarbe die Bestaetigungs-Achse noch offen hat. Die
        # Differenz quote_mit_mineral_prozent - quote_mit_strichfarbe_
        # prozent beziffert daher die Bestaetigungs-Luecke (mineralogisch
        # eingeordnet, aber Strich noch ungeprueft) - der naechste typische
        # Pflege-Schritt nach der Mineral-Familien-Bestimmung fuer
        # diagnostisch schwierige Mineralen. Whitespace zaehlt wie leer,
        # spiegelt die has_X-Filter-Konvention der umliegenden Felder
        # (Fundort/Notizen/Mineral); freie str-Spalte wie notizen, daher
        # gleichartige Whitespace-Behandlung.
        return self._quote(self.objekte_mit_strichfarbe)

    @property
    def quote_mit_hcl_reaktion_prozent(self) -> float | None:
        # Coverage-Quote fuer HCl-Reaktion (Salzsaeure-Test, einer der drei
        # klassischen qualitativen Bestimmungs-Pruefparameter aus dem
        # Feldwoerterbuch neben Magnetismus und Strichfarbe). Schliesst die
        # Pruefparameter-Coverage-Trias ab. Freie str-Spalte mit Konvention
        # "keine/schwach/stark; kalt/warm"; Whitespace zaehlt wie leer.
        return self._quote(self.objekte_mit_hcl_reaktion)

    @property
    def quote_mit_uv_254nm_prozent(self) -> float | None:
        # Coverage-Quote fuer UV-Reaktion bei 254 nm (kurzwelliges UV) -
        # paarweise zur Langwellen-Achse quote_mit_uv_365nm_prozent und
        # vervollstaendigt das UV-Doppel-Wellenlaengen-Coverage (365 nm
        # Langwelle / 254 nm Kurzwelle, die zwei Standard-Wellenlaengen
        # mineralogischer UV-Lampen). Spiegelt das Schwester-Property in
        # Struktur und Konvention: freie str-Spalte, Whitespace zaehlt wie
        # leer. Kurzwelliges UV ist die zweite UV-Achse, deren Reaktion
        # mineralogisch unabhaengig von der 365-nm-Antwort ist - viele
        # Mineralien (Scheelit-stark blauweiss, Hyalit-gruen, Calcit-rot)
        # fluoreszieren nur unter Kurzwelle, andere (Fluorit-blauviolett)
        # nur unter Langwelle, wieder andere (Manganhaltige Calcit) unter
        # beiden. Aussenkontext-bedingt typisch deutlich niedrigere Quote
        # als UV_365nm: die 254-nm-Lampen sind teurer (kalte Kathode statt
        # LED), gesundheitlich riskanter (UV-Schutzbrille erforderlich
        # wegen Augen-/Hautschaeden) und in der Sammler-Praxis seltener
        # verfuegbar; viele Sammler haben nur eine Langwellen-LED-Taschen-
        # lampe. Die Differenz quote_mit_uv_365nm_prozent -
        # quote_mit_uv_254nm_prozent beziffert die Kurzwellen-Mess-Luecke
        # (Langwelle dokumentiert, aber Kurzwelle nicht geprueft) - der
        # naechste typische Pflege-Schritt fuer Sammler mit erweiterter
        # UV-Ausruestung. Komplementaer zu quote_mit_uv_365nm_prozent
        # (Langwellen-Coverage) und zu den anderen Pruefparameter-Quoten
        # (Magnetismus/Strichfarbe/HCl-Reaktion); zusammen mit UV_365nm
        # ergibt sich das Doppel-Wellenlaengen-Coverage der UV-Diagnose-
        # Achse symmetrisch zur Doppel-Achse Spaltbarkeit/Bruch der
        # mechanischen Diagnose.
        return self._quote(self.objekte_mit_uv_254nm)

    @property
    def quote_mit_uv_365nm_prozent(self) -> float | None:
        # Coverage-Quote fuer UV-Reaktion bei 365 nm (langwelliges UV - die
        # Standard-Wellenlaenge fuer Fluoreszenz-Sammler, deutlich verbreiteter
        # als UV-254nm/kurzwellig). Spiegelt die Coverage-Quoten der qualitativen
        # Pruefparameter-Trias (Magnetismus/Strichfarbe/HCl-Reaktion) auf die
        # optische UV-Diagnose-Achse: waehrend Magnetismus die magnetische
        # Reaktion (Magnetit/Pyrrhotin), Strichfarbe die Pulverfarbe und
        # HCl-Reaktion die Carbonat-Brausreaktion misst, beziffert UV_365nm die
        # Fluoreszenz unter langwelligem UV-Licht (Fluorit, Calcit-Manganhaltig,
        # Willemit, Hyalit). Freie str-Spalte mit Konvention "keine/schwach/
        # stark + Farbe" (z.B. "stark gruen", "schwach orange", "keine"),
        # Whitespace zaehlt wie leer (spiegelt die has_X-Filter-Konvention der
        # umliegenden Pruef-Spalten). Bisher gab es zwar Foto_UV365/Foto_UV395
        # als separate Pfad-Felder und UV365 als Bild-Kategorie, aber keine
        # Coverage-Quote fuer die UV-Reaktions-Spalte selbst - die Foto-Felder
        # zaehlen Stuecke mit dokumentiertem UV-Bild, die Reaktions-Spalte
        # dagegen Stuecke mit dokumentierter Beobachtung der Fluoreszenz-
        # Antwort (textuell beschrieben, ohne Foto-Verweis). Aussenkontext-
        # bedingt orthogonal zur Mineral-Identifikation: UV-Fluoreszenz ist
        # bei vielen typischen Sammler-Mineralen das offensichtlich-negative
        # Ergebnis (Quarz/Pyrit/Magnetit reagieren typisch nicht), und auch
        # diese negativen Befunde wuerden in einem konsequent gepflegten
        # Bestand als "keine" eingetragen werden - die Quote ist daher ein
        # direkter Indikator fuer die Tiefe der UV-Pflege jenseits der
        # auffaelligen positiven Treffer. Niedriger Wert ist typisch in
        # Sammler-Bestaenden ohne dedizierte UV-Box (UV-Lampe + Dunkelkammer
        # erfordert separate Ausruestung), spiegelt die Pflege-Luecke bei
        # Magnetismus/Strichfarbe (alle drei sind invasive bzw. ausruestungs-
        # abhaengige Pruef-Achsen, anders als die visuellen Glanz/Transparenz/
        # Farbe, die ohne Werkzeug am Tageslicht beobachtbar sind).
        return self._quote(self.objekte_mit_uv_365nm)

    @property
    def quote_mit_reaktionshinweis_prozent(self) -> float | None:
        # Coverage-Quote fuer Reaktionshinweis (erklaerende Begleit-Notiz zu
        # UV/HCl/Magnetismus-Reaktionen). Spiegelt die Coverage-Quoten der
        # qualitativen Reaktions-Pruef-Achsen (Magnetismus/HCl-Reaktion/
        # UV_365nm/UV_254nm) auf die zugehoerige Begleit-Notiz-Achse - waehrend
        # die vier strukturierten Reaktions-Spalten die Roh-Beobachtung
        # festhalten (Magnetismus ja/nein/schwach, HCl keine/schwach/stark,
        # UV-Reaktion textuell beschrieben), beziffert Reaktionshinweis die
        # erklaerende Tiefe daneben (warum reagiert das Stueck so? welche
        # Begleit-Phase ist dafuer verantwortlich? unter welchen Bedingungen
        # tritt die Reaktion auf?). Mehrzeilige text-Spalte (Feldwoerterbuch-
        # Typ "text"), Whitespace zaehlt wie leer - spiegelt die
        # has_reaktionshinweis-Filter-Konvention aus stonebook.db.repository.
        # Bisher gab es zwar den has_reaktionshinweis-Filter (Listen-Filter,
        # Anwesenheits-Pruefung) als wahlfreies repository.filter_objects-
        # Argument, aber keine Coverage-Kennzahl (Anteil-Sicht auf den Gesamt-
        # bestand) - waehrend alle vier umliegenden Reaktions-Spalten
        # (Magnetismus/HCl/UV-365/UV-254) bereits Coverage-Quoten tragen.
        # Aussenkontext-bedingt typisch sehr niedrig in Sammler-Bestaenden,
        # weil Reaktionshinweis erst bei nicht-trivialer Reaktions-Erklaerung
        # gepflegt wird (warum braust dieses Stueck schwaecher als erwartet?
        # weil es ein Mischcarbonat mit Magnesium-Anteil ist - solche Mineral-
        # /Petrologie-Interpretationen sind die Ausnahme, nicht die Regel).
        # Aus Datenpflege-Sicht ein Indikator fuer die Interpretations-Tiefe
        # der Reaktions-Pflege: ein Stueck mit dokumentiertem
        # Reaktionshinweis ist nicht nur gepruft (Roh-Beobachtung steht in
        # einer der vier Reaktions-Spalten), sondern auch interpretiert
        # (warum hat es so reagiert?) - der Unterschied zwischen
        # Katalogisierung und mineralogischem Verstaendnis. Komplementaer
        # zu quote_mit_notizen_prozent (allgemeine freie Beobachtungs-
        # Achse jenseits der 43 strukturierten Felder): waehrend Notizen
        # die "Sonstiges"-Spalte fuer beliebige Beobachtungen ist,
        # ist Reaktionshinweis thematisch fest auf die Reaktions-Interpretation
        # fokussiert - beide sind Freitext, aber mit unterschiedlichem
        # Geltungsbereich. Die Differenz quote_mit_hcl_reaktion_prozent -
        # quote_mit_reaktionshinweis_prozent beziffert die typische
        # Interpretations-Luecke (Reaktion beobachtet, aber nicht erklaert) -
        # der naechste Pflege-Schritt fuer Sammler mit petrologischem
        # Hintergrund.
        return self._quote(self.objekte_mit_reaktionshinweis)

    @property
    def quote_mit_pruefempfehlungen_prozent(self) -> float | None:
        # Coverage-Quote fuer Pruefempfehlungen (empfohlene Bestaetigungstests
        # neben den schon durchgefuehrten Pruef-Achsen aus der
        # Sonstiges-Gruppe des Feldwoerterbuchs). Spiegelt die Coverage-Quote
        # quote_mit_reaktionshinweis_prozent (erklaerende Begleit-Notiz zu den
        # Roh-Beobachtungen) auf die naechste-Schritt-Achse: waehrend
        # Reaktionshinweis die Interpretation der bereits beobachteten
        # Reaktionen festhaelt (warum reagiert das Stueck so?), zielt
        # Pruefempfehlungen auf die noch offene Pruef-Liste (welche Tests
        # bestaetigen die aktuelle Hypothese am zuverlaessigsten?). Mehrzeilige
        # text-Spalte (Feldwoerterbuch-Typ "text"), Whitespace zaehlt wie leer -
        # spiegelt die has_pruefempfehlungen-Filter-Konvention aus
        # stonebook.db.repository. Bisher gab es zwar den
        # has_pruefempfehlungen-Filter (Listen-Filter, Anwesenheits-Pruefung)
        # als wahlfreies repository.filter_objects-Argument, aber keine
        # Coverage-Kennzahl (Anteil-Sicht auf den Gesamtbestand) - waehrend
        # die paarweise Sonstiges-Achse Reaktionshinweis und die freie
        # Notizen-Achse bereits Coverage-Quoten tragen. Aussenkontext-bedingt
        # typisch sehr niedrig in Sammler-Bestaenden, weil Pruefempfehlungen
        # erst gepflegt werden, wenn die Bestimmung bewusst als vorlaeufig
        # markiert ist und ein konkreter naechster Pruefschritt notiert wird
        # (Dichtebestimmung mit Pyknometer, EDX-Analyse bei der Volkshochschule,
        # XRD im Universitaetslabor, Spaltbarkeitsprobe an einer abgebrochenen
        # Ecke) - die ueblicheren Faelle sind entweder vollstaendig bestimmt
        # (keine offenen Pruefungen mehr) oder grob eingeordnet ohne expliziten
        # Pflege-Plan. Aus Datenpflege-Sicht ein direkter Indikator fuer die
        # Pflege-Disziplin: Stuecke mit dokumentierten Pruefempfehlungen sind
        # bewusst als "Bestimmung im Gang" markiert (der Sammler hat einen
        # konkreten Plan, wie er die Hypothese bestaetigt), waehrend Stuecke
        # ohne Pruefempfehlungen entweder fertig sind oder ohne Pflege-Plan
        # vorlaeufig - der Unterschied zwischen "ich habe einen Pruefplan" und
        # "ich akzeptiere die aktuelle Bestimmung". Komplementaer zu
        # quote_mit_confidence_prozent (quantitative Sicherheits-Achse): ein
        # Stueck mit Confidence_Prozent unter dem Bestimmungs-Schwellwert
        # sollte typisch auch Pruefempfehlungen tragen (welche Pruefung wuerde
        # die Sicherheit erhoehen?), waehrend ein hoch-confidentes Stueck ohne
        # Pruefempfehlungen die normale Endstation der Bestimmung ist; die
        # Differenz beider Quoten beziffert die Disziplin-Luecke bei der
        # Markierung offener Pruef-Pfade. Komplementaer zu
        # quote_mit_reaktionshinweis_prozent (Interpretations-Tiefe der
        # bereits beobachteten Reaktionen) und quote_mit_notizen_prozent
        # (allgemeine Freitext-Beobachtungen): waehrend Reaktionshinweis
        # rueckblickend erklaert und Notizen seitwaerts beobachtet, blickt
        # Pruefempfehlungen vorwaerts auf den naechsten Pflege-Schritt - die
        # drei Freitext-Achsen decken zusammen den vollstaendigen
        # Bestimmungs-Workflow ab (Vergangenheit/Gegenwart/Zukunft).
        return self._quote(self.objekte_mit_pruefempfehlungen)

    @property
    def quote_mit_notizen_prozent(self) -> float | None:
        # Coverage-Quote fuer freie Notizen (notizen-Spalte). Spiegelt die
        # Feld-Coverage-Quoten (Bildern/Funddatum/Wert/Gewicht/Mineral/Fundort)
        # auf die unstrukturierte Freitext-Achse - "wie viel Anteil der
        # Sammlung traegt ueberhaupt eine handgepflegte Beobachtung neben den
        # 43 Standardfeldern?". Komplementaer zu den enum-/typ-validierten
        # Feld-Coverage-Quoten: dort geht es um die Vollstaendigkeit der
        # strukturierten Erfassungs-Achsen (Mineral/Fundort/Glanz/...), hier
        # um die Tiefe der freien Beobachtung (Habitus-Beschreibung, Pflege-
        # Hinweise, Provenienz-Geschichte, Mess-Notizen, Vermutungen, die
        # nicht in eines der 43 Standardfelder passen). Aussenkontext-bedingt
        # niedriger Wert ist typisch - notizen ist die "Sonstiges"-Spalte, die
        # erst gepflegt wird, wenn der Sammler einen Beobachtungs-Anlass hat
        # (auffaelliger Habitus, ungewoehnliche Pflege-Anforderung, Sammler-
        # Erinnerung an Fund-Umstand, Hinweis auf zukuenftige Pruefung), nicht
        # routinemaessig fuer jedes Stueck. Aus Datenpflege-Sicht ein Indikator
        # fuer die Erfassungs-Tiefe jenseits der strukturierten Pflicht-Achsen:
        # eine Sammlung mit hoher Strukturfeld-Coverage und niedriger Notizen-
        # Quote ist katalogisiert (alle Felder gefuellt), aber nicht
        # interpretiert; umgekehrt deutet eine niedrige Strukturfeld-Coverage
        # mit hoher Notizen-Quote auf eine Beobachtungs-orientierte
        # Sammlungs-Linie (alles steht im Freitext, nichts in den strukturierten
        # Feldern) - beide Profile sind legitim, aber sie sagen Unter-
        # schiedliches ueber den Pflege-Stil. Whitespace zaehlt wie leer
        # (spiegelt has_notizen-Filter-Konvention).
        return self._quote(self.objekte_mit_notizen)

    @property
    def quote_mit_ki_analyse_uebernommen_prozent(self) -> float | None:
        # Coverage-Quote fuer tatsaechlich uebernommene KI-Analysen. Spiegelt
        # quote_mit_ki_analyse auf die feinere Granularitaet "wieviel Anteil
        # der Sammlung wurde durch die KI tatsaechlich verbessert?" - die
        # Differenz beider Quoten beziffert die Akzeptanz-/Pflege-Luecke:
        # Objekte, fuer die zwar KI-Vorschlaege erzeugt wurden, deren
        # uebernommen_json aber leer/NULL geblieben ist (Sammler hat die
        # Vorschlaege noch nicht gepflegt/geprueft, oder bewusst verworfen).
        # quote_mit_ki_analyse misst Anwendungs-Durchdringung (wo lief die KI
        # schon?), quote_mit_ki_analyse_uebernommen misst Nutzungs-Tiefe (wo
        # wurde der Output integriert?). Aus Datenpflege-Sicht ist die
        # zweite Achse die aussagekraeftigere - sie spiegelt die operative
        # Wirkung der KI auf das tatsaechliche Datenbild, waehrend die erste
        # nur die Reichweite des KI-Laufs misst. Whitespace zaehlt wie leer
        # (spiegelt has_ki_analyse_uebernommen-Filter-Konvention).
        return self._quote(self.objekte_mit_ki_analyse_uebernommen)

    @property
    def quote_mit_alias_prozent(self) -> float | None:
        # Coverage-Quote fuer Kanon-Objekte mit mindestens einem Alias (Merge-
        # Quote). Spiegelt das Coverage-Vokabular auf die Provenienz-Achse:
        # "wie viel Anteil der Sammlung ist tatsaechlich aus Duplikat-Merges
        # hervorgegangen?" - eine sehr aussagekraeftige Dokumentations-Qualitaets-
        # Kennzahl, weil sie zeigt, wie stark das Migrations-/Pflege-Verfahren
        # die rohen historischen Eintraege konsolidiert hat. aliase_total ist die
        # Summe aller Alias-Eintraege (ein Kanon-Objekt kann mehrere alte IDs
        # auf sich vereinigen), objekte_mit_alias die Anzahl der verschmolzenen
        # Kanon-Objekte (unabhaengig von der Merge-Tiefe), quote_mit_alias_prozent
        # rechnet das auf den Anteil der Gesamtsammlung um. Hoher Wert deutet auf
        # Sammler-Bestand mit vielen historischen Doppelungen (z.B. aus zwei
        # parallelen Erfassungs-Systemen zusammengefuehrt), niedriger Wert auf
        # eine sauber verwaltete Erfassungs-Linie. Komplementaer zu aliase_total
        # (Roh-Volumen) und objekte_mit_alias (Anzahl-Sicht); orthogonal zu den
        # Feld-Coverage-Quoten (Bildern/Funddatum/Mineral/...), die die
        # inhaltliche Pflege je Stueck messen.
        return self._quote(self.objekte_mit_alias)

    def as_dict(self) -> dict:
        return {
            "objekte_total": self.objekte_total,
            "objekte_aktiv": self.objekte_aktiv,
            "objekte_platzhalter": self.objekte_platzhalter,
            "objekte_archiviert": self.objekte_archiviert,
            "objekte_mit_bildern": self.objekte_mit_bildern,
            "objekte_mit_funddatum": self.objekte_mit_funddatum,
            "objekte_mit_kategorie": self.objekte_mit_kategorie,
            "objekte_mit_mineral": self.objekte_mit_mineral,
            "objekte_mit_varietaet": self.objekte_mit_varietaet,
            "objekte_mit_gesteinsart": self.objekte_mit_gesteinsart,
            "objekte_mit_kristallsystem": self.objekte_mit_kristallsystem,
            "objekte_mit_magnetismus": self.objekte_mit_magnetismus,
            "objekte_mit_glanz": self.objekte_mit_glanz,
            "objekte_mit_spaltbarkeit": self.objekte_mit_spaltbarkeit,
            "objekte_mit_bruch": self.objekte_mit_bruch,
            "objekte_mit_beste_verwendung": self.objekte_mit_beste_verwendung,
            "objekte_mit_transparenz": self.objekte_mit_transparenz,
            "objekte_mit_fundort": self.objekte_mit_fundort,
            "objekte_mit_koordinaten": self.objekte_mit_koordinaten,
            "objekte_mit_farbe": self.objekte_mit_farbe,
            "objekte_mit_strichfarbe": self.objekte_mit_strichfarbe,
            "objekte_mit_hcl_reaktion": self.objekte_mit_hcl_reaktion,
            "objekte_mit_uv_365nm": self.objekte_mit_uv_365nm,
            "objekte_mit_uv_254nm": self.objekte_mit_uv_254nm,
            "objekte_mit_reaktionshinweis": self.objekte_mit_reaktionshinweis,
            "objekte_mit_pruefempfehlungen": self.objekte_mit_pruefempfehlungen,
            "objekte_mit_notizen": self.objekte_mit_notizen,
            "objekte_mit_seltenheit_global": self.objekte_mit_seltenheit_global,
            "objekte_mit_seltenheit_fundort": self.objekte_mit_seltenheit_fundort,
            "objekte_mit_nachfrage": self.objekte_mit_nachfrage,
            "bilder_total": self.bilder_total,
            "aliase_total": self.aliase_total,
            "objekte_mit_alias": self.objekte_mit_alias,
            "ki_analysen_total": self.ki_analysen_total,
            "ki_analysen_uebernommen": self.ki_analysen_uebernommen,
            "objekte_mit_ki_analyse": self.objekte_mit_ki_analyse,
            "objekte_mit_ki_analyse_uebernommen": self.objekte_mit_ki_analyse_uebernommen,
            "mineral_arten_total": self.mineral_arten_total,
            "fundorte_total": self.fundorte_total,
            "kategorien_total": self.kategorien_total,
            "varietaeten_total": self.varietaeten_total,
            "gesteinsarten_total": self.gesteinsarten_total,
            "by_status": dict(self.by_status),
            "by_mineral": dict(self.by_mineral),
            "by_varietaet": dict(self.by_varietaet),
            "by_gesteinsart": dict(self.by_gesteinsart),
            "by_kategorie": dict(self.by_kategorie),
            "by_kristallsystem": dict(self.by_kristallsystem),
            "by_glanz": dict(self.by_glanz),
            "by_transparenz": dict(self.by_transparenz),
            "by_magnetismus": dict(self.by_magnetismus),
            "by_spaltbarkeit": dict(self.by_spaltbarkeit),
            "by_bruch": dict(self.by_bruch),
            "by_beste_verwendung": dict(self.by_beste_verwendung),
            "by_fundort": dict(self.by_fundort),
            "by_funddatum_jahr": dict(self.by_funddatum_jahr),
            "by_funddatum_jahrzehnt": dict(self.by_funddatum_jahrzehnt),
            "by_funddatum_monat": dict(self.by_funddatum_monat),
            "by_erstellt_am_jahr": dict(self.by_erstellt_am_jahr),
            "by_erstellt_am_jahrzehnt": dict(self.by_erstellt_am_jahrzehnt),
            "by_erstellt_am_monat": dict(self.by_erstellt_am_monat),
            "by_geaendert_am_jahr": dict(self.by_geaendert_am_jahr),
            "by_geaendert_am_jahrzehnt": dict(self.by_geaendert_am_jahrzehnt),
            "by_geaendert_am_monat": dict(self.by_geaendert_am_monat),
            "by_seltenheit_global": dict(self.by_seltenheit_global),
            "by_seltenheit_fundort": dict(self.by_seltenheit_fundort),
            "by_nachfrage": dict(self.by_nachfrage),
            "bilder_by_kategorie": dict(self.bilder_by_kategorie),
            "funddatum_frueheste": self.funddatum_frueheste,
            "funddatum_spaeteste": self.funddatum_spaeteste,
            "erstellt_am_frueheste": self.erstellt_am_frueheste,
            "erstellt_am_spaeteste": self.erstellt_am_spaeteste,
            "geaendert_am_frueheste": self.geaendert_am_frueheste,
            "geaendert_am_spaeteste": self.geaendert_am_spaeteste,
            "koordinaten_bbox": (
                list(self.koordinaten_bbox)
                if self.koordinaten_bbox is not None else None
            ),
            "koordinaten_zentrum": (
                list(self.koordinaten_zentrum)
                if self.koordinaten_zentrum is not None else None
            ),
            "koordinaten_radius_max_km": (
                round(self.koordinaten_radius_max_km, 3)
                if self.koordinaten_radius_max_km is not None else None
            ),
            "koordinaten_radius_durchschnitt_km": (
                round(self.koordinaten_radius_durchschnitt_km, 3)
                if self.koordinaten_radius_durchschnitt_km is not None else None
            ),
            "koordinaten_radius_median_km": (
                round(self.koordinaten_radius_median_km, 3)
                if self.koordinaten_radius_median_km is not None else None
            ),
            "koordinaten_diameter_km": (
                round(self.koordinaten_diameter_km, 3)
                if self.koordinaten_diameter_km is not None else None
            ),
            "mohs_kollektion_min": (
                round(self.mohs_kollektion_min, 1)
                if self.mohs_kollektion_min is not None else None
            ),
            "mohs_kollektion_max": (
                round(self.mohs_kollektion_max, 1)
                if self.mohs_kollektion_max is not None else None
            ),
            "mohs_kollektion_median": (
                round(self.mohs_kollektion_median, 1)
                if self.mohs_kollektion_median is not None else None
            ),
            "mohs_kollektion_standardabweichung": (
                round(self.mohs_kollektion_standardabweichung, 2)
                if self.mohs_kollektion_standardabweichung is not None else None
            ),
            "mohs_kollektion_variationskoeffizient_prozent": (
                round(self.mohs_kollektion_variationskoeffizient_prozent, 2)
                if self.mohs_kollektion_variationskoeffizient_prozent is not None
                else None
            ),
            "mohs_kollektion_spanweite": (
                round(self.mohs_kollektion_spanweite, 1)
                if self.mohs_kollektion_spanweite is not None else None
            ),
            "mohs_kollektion_durchschnitt": (
                round(self.mohs_kollektion_durchschnitt, 1)
                if self.mohs_kollektion_durchschnitt is not None else None
            ),
            "dichte_kollektion_min": (
                round(self.dichte_kollektion_min, 2)
                if self.dichte_kollektion_min is not None else None
            ),
            "dichte_kollektion_max": (
                round(self.dichte_kollektion_max, 2)
                if self.dichte_kollektion_max is not None else None
            ),
            "dichte_kollektion_durchschnitt": (
                round(self.dichte_kollektion_durchschnitt, 2)
                if self.dichte_kollektion_durchschnitt is not None else None
            ),
            "dichte_kollektion_median": (
                round(self.dichte_kollektion_median, 2)
                if self.dichte_kollektion_median is not None else None
            ),
            "dichte_kollektion_standardabweichung": (
                round(self.dichte_kollektion_standardabweichung, 3)
                if self.dichte_kollektion_standardabweichung is not None else None
            ),
            "dichte_kollektion_variationskoeffizient_prozent": (
                round(
                    self.dichte_kollektion_variationskoeffizient_prozent, 2)
                if self.dichte_kollektion_variationskoeffizient_prozent
                is not None else None
            ),
            "dichte_kollektion_spanweite": (
                round(self.dichte_kollektion_spanweite, 2)
                if self.dichte_kollektion_spanweite is not None else None
            ),
            "wert_summe_chf": round(self.wert_summe_chf, 2),
            "wert_roh_summe_chf": round(self.wert_roh_summe_chf, 2),
            "wert_min_chf": round(self.wert_min_chf, 2),
            "wert_max_chf": round(self.wert_max_chf, 2),
            "wert_durchschnitt_chf": round(self.wert_durchschnitt_chf, 2),
            "wert_median_chf": round(self.wert_median_chf, 2),
            "wert_standardabweichung_chf": round(
                self.wert_standardabweichung_chf, 2),
            "wert_variationskoeffizient_prozent": (
                round(self.wert_variationskoeffizient_prozent, 2)
                if self.wert_variationskoeffizient_prozent is not None else None
            ),
            "wert_spanweite_chf": round(self.wert_spanweite_chf, 2),
            "objekte_mit_wert": self.objekte_mit_wert,
            "top_wert_objekte": [
                (oid, name, round(w, 2)) for oid, name, w in self.top_wert_objekte
            ],
            "top_gewicht_objekte": [
                (oid, name, round(g, 2)) for oid, name, g in self.top_gewicht_objekte
            ],
            "top_bilder_objekte": [
                (oid, name, int(n)) for oid, name, n in self.top_bilder_objekte
            ],
            "top_confidence_objekte": [
                (oid, name, int(c)) for oid, name, c in self.top_confidence_objekte
            ],
            "wert_pro_mineral": [
                (mineral, round(w, 2)) for mineral, w in self.wert_pro_mineral
            ],
            "wert_pro_varietaet": [
                (var, round(w, 2)) for var, w in self.wert_pro_varietaet
            ],
            "wert_pro_gesteinsart": [
                (ges, round(w, 2)) for ges, w in self.wert_pro_gesteinsart
            ],
            "wert_pro_fundort": [
                (ort, round(w, 2)) for ort, w in self.wert_pro_fundort
            ],
            "wert_pro_kategorie": [
                (kat, round(w, 2)) for kat, w in self.wert_pro_kategorie
            ],
            "wert_pro_kristallsystem": [
                (ks, round(w, 2)) for ks, w in self.wert_pro_kristallsystem
            ],
            "wert_pro_glanz": [
                (g, round(w, 2)) for g, w in self.wert_pro_glanz
            ],
            "wert_pro_transparenz": [
                (t, round(w, 2)) for t, w in self.wert_pro_transparenz
            ],
            "wert_pro_magnetismus": [
                (m, round(w, 2)) for m, w in self.wert_pro_magnetismus
            ],
            "wert_pro_spaltbarkeit": [
                (sp, round(w, 2)) for sp, w in self.wert_pro_spaltbarkeit
            ],
            "wert_pro_bruch": [
                (b, round(w, 2)) for b, w in self.wert_pro_bruch
            ],
            "wert_pro_beste_verwendung": [
                (bv, round(w, 2)) for bv, w in self.wert_pro_beste_verwendung
            ],
            "wert_pro_status": [
                (s, round(w, 2)) for s, w in self.wert_pro_status
            ],
            "wert_pro_funddatum_jahr": [
                (j, round(w, 2)) for j, w in self.wert_pro_funddatum_jahr
            ],
            "wert_pro_funddatum_jahrzehnt": [
                (d, round(w, 2)) for d, w in self.wert_pro_funddatum_jahrzehnt
            ],
            "wert_pro_funddatum_monat": [
                (m, round(w, 2)) for m, w in self.wert_pro_funddatum_monat
            ],
            "wert_pro_erstellt_am_jahr": [
                (j, round(w, 2)) for j, w in self.wert_pro_erstellt_am_jahr
            ],
            "wert_pro_erstellt_am_jahrzehnt": [
                (d, round(w, 2)) for d, w in self.wert_pro_erstellt_am_jahrzehnt
            ],
            "wert_pro_erstellt_am_monat": [
                (m, round(w, 2)) for m, w in self.wert_pro_erstellt_am_monat
            ],
            "wert_pro_geaendert_am_jahr": [
                (j, round(w, 2)) for j, w in self.wert_pro_geaendert_am_jahr
            ],
            "wert_pro_geaendert_am_jahrzehnt": [
                (d, round(w, 2)) for d, w in self.wert_pro_geaendert_am_jahrzehnt
            ],
            "wert_pro_geaendert_am_monat": [
                (m, round(w, 2)) for m, w in self.wert_pro_geaendert_am_monat
            ],
            "wert_pro_seltenheit_global": [
                (s, round(w, 2)) for s, w in self.wert_pro_seltenheit_global
            ],
            "wert_pro_seltenheit_fundort": [
                (s, round(w, 2)) for s, w in self.wert_pro_seltenheit_fundort
            ],
            "wert_pro_nachfrage": [
                (s, round(w, 2)) for s, w in self.wert_pro_nachfrage
            ],
            "wert_pro_confidence_bucket": [
                (b, round(w, 2)) for b, w in self.wert_pro_confidence_bucket
            ],
            "gewicht_pro_mineral": [
                (mineral, round(g, 2)) for mineral, g in self.gewicht_pro_mineral
            ],
            "gewicht_pro_varietaet": [
                (var, round(g, 2)) for var, g in self.gewicht_pro_varietaet
            ],
            "gewicht_pro_gesteinsart": [
                (ges, round(g, 2)) for ges, g in self.gewicht_pro_gesteinsart
            ],
            "gewicht_pro_fundort": [
                (ort, round(g, 2)) for ort, g in self.gewicht_pro_fundort
            ],
            "gewicht_pro_kategorie": [
                (kat, round(g, 2)) for kat, g in self.gewicht_pro_kategorie
            ],
            "gewicht_pro_kristallsystem": [
                (ks, round(g, 2)) for ks, g in self.gewicht_pro_kristallsystem
            ],
            "gewicht_pro_glanz": [
                (glz, round(g, 2)) for glz, g in self.gewicht_pro_glanz
            ],
            "gewicht_pro_transparenz": [
                (t, round(g, 2)) for t, g in self.gewicht_pro_transparenz
            ],
            "gewicht_pro_magnetismus": [
                (m, round(g, 2)) for m, g in self.gewicht_pro_magnetismus
            ],
            "gewicht_pro_spaltbarkeit": [
                (sp, round(g, 2)) for sp, g in self.gewicht_pro_spaltbarkeit
            ],
            "gewicht_pro_bruch": [
                (b, round(g, 2)) for b, g in self.gewicht_pro_bruch
            ],
            "gewicht_pro_beste_verwendung": [
                (bv, round(g, 2)) for bv, g in self.gewicht_pro_beste_verwendung
            ],
            "gewicht_pro_status": [
                (s, round(g, 2)) for s, g in self.gewicht_pro_status
            ],
            "gewicht_pro_funddatum_jahr": [
                (j, round(g, 2)) for j, g in self.gewicht_pro_funddatum_jahr
            ],
            "gewicht_pro_funddatum_jahrzehnt": [
                (d, round(g, 2)) for d, g in self.gewicht_pro_funddatum_jahrzehnt
            ],
            "gewicht_pro_funddatum_monat": [
                (m, round(g, 2)) for m, g in self.gewicht_pro_funddatum_monat
            ],
            "gewicht_pro_erstellt_am_jahr": [
                (j, round(g, 2)) for j, g in self.gewicht_pro_erstellt_am_jahr
            ],
            "gewicht_pro_erstellt_am_jahrzehnt": [
                (d, round(g, 2)) for d, g in self.gewicht_pro_erstellt_am_jahrzehnt
            ],
            "gewicht_pro_erstellt_am_monat": [
                (m, round(g, 2)) for m, g in self.gewicht_pro_erstellt_am_monat
            ],
            "gewicht_pro_geaendert_am_jahr": [
                (j, round(g, 2)) for j, g in self.gewicht_pro_geaendert_am_jahr
            ],
            "gewicht_pro_geaendert_am_jahrzehnt": [
                (d, round(g, 2)) for d, g in self.gewicht_pro_geaendert_am_jahrzehnt
            ],
            "gewicht_pro_geaendert_am_monat": [
                (m, round(g, 2)) for m, g in self.gewicht_pro_geaendert_am_monat
            ],
            "gewicht_pro_seltenheit_global": [
                (s, round(g, 2)) for s, g in self.gewicht_pro_seltenheit_global
            ],
            "gewicht_pro_seltenheit_fundort": [
                (s, round(g, 2)) for s, g in self.gewicht_pro_seltenheit_fundort
            ],
            "gewicht_pro_nachfrage": [
                (s, round(g, 2)) for s, g in self.gewicht_pro_nachfrage
            ],
            "gewicht_pro_confidence_bucket": [
                (b, round(g, 2)) for b, g in self.gewicht_pro_confidence_bucket
            ],
            "gewicht_summe_g": round(self.gewicht_summe_g, 2),
            "gewicht_durchschnitt_g": round(self.gewicht_durchschnitt_g, 2),
            "gewicht_median_g": round(self.gewicht_median_g, 2),
            "gewicht_min_g": round(self.gewicht_min_g, 2),
            "gewicht_max_g": round(self.gewicht_max_g, 2),
            "gewicht_standardabweichung_g": round(
                self.gewicht_standardabweichung_g, 2),
            "gewicht_variationskoeffizient_prozent": (
                round(self.gewicht_variationskoeffizient_prozent, 2)
                if self.gewicht_variationskoeffizient_prozent is not None
                else None
            ),
            "gewicht_spanweite_g": round(self.gewicht_spanweite_g, 2),
            "objekte_mit_gewicht": self.objekte_mit_gewicht,
            "objekte_mit_dimensionen": self.objekte_mit_dimensionen,
            "objekte_mit_mohs": self.objekte_mit_mohs,
            "objekte_mit_dichte": self.objekte_mit_dichte,
            "objekte_mit_confidence": self.objekte_mit_confidence,
            "durchschnitt_confidence_prozent": (
                round(self.durchschnitt_confidence_prozent, 1)
                if self.durchschnitt_confidence_prozent is not None else None
            ),
            "median_confidence_prozent": (
                round(self.median_confidence_prozent, 1)
                if self.median_confidence_prozent is not None else None
            ),
            "confidence_min_prozent": self.confidence_min_prozent,
            "confidence_max_prozent": self.confidence_max_prozent,
            "confidence_standardabweichung_prozent": (
                round(self.confidence_standardabweichung_prozent, 2)
                if self.confidence_standardabweichung_prozent is not None else None
            ),
            "confidence_variationskoeffizient_prozent": (
                round(self.confidence_variationskoeffizient_prozent, 2)
                if self.confidence_variationskoeffizient_prozent is not None
                else None
            ),
            "confidence_spanweite_prozent": self.confidence_spanweite_prozent,
            "confidence_buckets": dict(self.confidence_buckets),
            "quote_mit_bildern_prozent": _round_or_none(self.quote_mit_bildern_prozent),
            "quote_mit_funddatum_prozent": _round_or_none(self.quote_mit_funddatum_prozent),
            "quote_mit_wert_prozent": _round_or_none(self.quote_mit_wert_prozent),
            "quote_mit_gewicht_prozent": _round_or_none(self.quote_mit_gewicht_prozent),
            "quote_mit_dimensionen_prozent": _round_or_none(self.quote_mit_dimensionen_prozent),
            "quote_mit_mohs_prozent": _round_or_none(self.quote_mit_mohs_prozent),
            "quote_mit_dichte_prozent": _round_or_none(self.quote_mit_dichte_prozent),
            "quote_mit_ki_analyse_prozent": _round_or_none(self.quote_mit_ki_analyse_prozent),
            "quote_mit_confidence_prozent": _round_or_none(self.quote_mit_confidence_prozent),
            "quote_mit_seltenheit_global_prozent": _round_or_none(
                self.quote_mit_seltenheit_global_prozent),
            "quote_mit_seltenheit_fundort_prozent": _round_or_none(
                self.quote_mit_seltenheit_fundort_prozent),
            "quote_mit_nachfrage_prozent": _round_or_none(
                self.quote_mit_nachfrage_prozent),
            "quote_mit_kategorie_prozent": _round_or_none(self.quote_mit_kategorie_prozent),
            "quote_mit_mineral_prozent": _round_or_none(self.quote_mit_mineral_prozent),
            "quote_mit_varietaet_prozent": _round_or_none(self.quote_mit_varietaet_prozent),
            "quote_mit_gesteinsart_prozent": _round_or_none(self.quote_mit_gesteinsart_prozent),
            "quote_mit_kristallsystem_prozent": _round_or_none(
                self.quote_mit_kristallsystem_prozent),
            "quote_mit_magnetismus_prozent": _round_or_none(
                self.quote_mit_magnetismus_prozent),
            "quote_mit_glanz_prozent": _round_or_none(self.quote_mit_glanz_prozent),
            "quote_mit_transparenz_prozent": _round_or_none(self.quote_mit_transparenz_prozent),
            "quote_mit_spaltbarkeit_prozent": _round_or_none(
                self.quote_mit_spaltbarkeit_prozent),
            "quote_mit_bruch_prozent": _round_or_none(
                self.quote_mit_bruch_prozent),
            "quote_mit_beste_verwendung_prozent": _round_or_none(
                self.quote_mit_beste_verwendung_prozent),
            "quote_mit_fundort_prozent": _round_or_none(self.quote_mit_fundort_prozent),
            "quote_mit_koordinaten_prozent": _round_or_none(
                self.quote_mit_koordinaten_prozent),
            "quote_mit_farbe_prozent": _round_or_none(self.quote_mit_farbe_prozent),
            "quote_mit_strichfarbe_prozent": _round_or_none(
                self.quote_mit_strichfarbe_prozent),
            "quote_mit_hcl_reaktion_prozent": _round_or_none(
                self.quote_mit_hcl_reaktion_prozent),
            "quote_mit_uv_365nm_prozent": _round_or_none(
                self.quote_mit_uv_365nm_prozent),
            "quote_mit_uv_254nm_prozent": _round_or_none(
                self.quote_mit_uv_254nm_prozent),
            "quote_mit_reaktionshinweis_prozent": _round_or_none(
                self.quote_mit_reaktionshinweis_prozent),
            "quote_mit_pruefempfehlungen_prozent": _round_or_none(
                self.quote_mit_pruefempfehlungen_prozent),
            "quote_mit_notizen_prozent": _round_or_none(self.quote_mit_notizen_prozent),
            "quote_mit_ki_analyse_uebernommen_prozent": _round_or_none(
                self.quote_mit_ki_analyse_uebernommen_prozent
            ),
            "quote_mit_alias_prozent": _round_or_none(self.quote_mit_alias_prozent),
        }


def _round_or_none(value: float | None, digits: int = 1) -> float | None:
    return round(value, digits) if value is not None else None


def _count_distinct(conn: sqlite3.Connection, column: str) -> int:
    """Anzahl der verschiedenen Werte in ``column`` (NULL/leer ignoriert)."""
    return conn.execute(
        f"SELECT COUNT(DISTINCT {column}) FROM objects "
        f"WHERE {column} IS NOT NULL AND TRIM({column}) != ''"
    ).fetchone()[0]


def _count_by(conn: sqlite3.Connection, column: str, limit: int | None = None) -> dict[str, int]:
    sql = (
        f"SELECT {column} AS k, COUNT(*) AS n FROM objects "
        f"WHERE {column} IS NOT NULL AND TRIM({column}) != '' "
        f"GROUP BY {column} ORDER BY n DESC, {column} ASC"
    )
    if limit is not None:
        sql += f" LIMIT {int(limit)}"
    return {r["k"]: r["n"] for r in conn.execute(sql).fetchall()}


def _count_funddatum_jahr(conn: sqlite3.Connection, limit: int | None = None) -> dict[str, int]:
    """Zaehlt Objekte pro Funddatum-Jahr (Substring 1..4 von ISO YYYY-MM-DD).

    Nur Werte mit vier Ziffern am Anfang werden beruecksichtigt; ungueltige
    Funddaten werden ignoriert (siehe check_integrity).
    """
    sql = (
        "SELECT substr(Funddatum, 1, 4) AS jahr, COUNT(*) AS n FROM objects "
        "WHERE Funddatum IS NOT NULL AND TRIM(Funddatum) != '' "
        "AND substr(Funddatum, 1, 4) GLOB '[0-9][0-9][0-9][0-9]' "
        "GROUP BY jahr ORDER BY jahr ASC"
    )
    rows = conn.execute(sql).fetchall()
    pairs = [(r["jahr"], r["n"]) for r in rows]
    if limit is not None:
        pairs.sort(key=lambda p: (-p[1], p[0]))
        pairs = pairs[:int(limit)]
        pairs.sort(key=lambda p: p[0])
    return {j: n for j, n in pairs}


def _count_funddatum_monat(conn: sqlite3.Connection) -> dict[str, int]:
    """Zaehlt Objekte pro Funddatum-Monat (01..12), ueber alle Jahre aggregiert.

    Komplementaer zu :func:`_count_funddatum_jahr` (chronologisch) und
    :func:`_count_funddatum_jahrzehnt` (Dekaden): zeigt die Saison-Verteilung
    eines Sammler-Lebens - typisch sind Spitzen in Juli/August (Berg-Saison)
    und Dezember (Mineralienboerse Tucson/Muenchen). Label sind die Monats-
    Ziffern (``"01"`` .. ``"12"``); Monate ohne Treffer fehlen im Dict.

    Akzeptiert nur Funddaten in ISO-Form ``YYYY-MM-DD``/``YYYY-MM`` mit
    gueltigem Monatsteil 01-12; reine Jahresangaben (``"2024"``) haben keinen
    Monatsteil und werden ignoriert (sonst wuerden sie als "Monat 00" auf
    einen Default-Bucket fallen und die Saison-Statistik verzerren).
    """
    sql = (
        "SELECT substr(Funddatum, 6, 2) AS monat, COUNT(*) AS n FROM objects "
        "WHERE Funddatum IS NOT NULL AND TRIM(Funddatum) != '' "
        "AND substr(Funddatum, 1, 4) GLOB '[0-9][0-9][0-9][0-9]' "
        "AND substr(Funddatum, 6, 2) GLOB '[0-1][0-9]' "
        "AND CAST(substr(Funddatum, 6, 2) AS INTEGER) BETWEEN 1 AND 12 "
        "GROUP BY monat ORDER BY monat ASC"
    )
    return {r["monat"]: r["n"] for r in conn.execute(sql).fetchall()}


def _count_funddatum_jahrzehnt(conn: sqlite3.Connection) -> dict[str, int]:
    """Zaehlt Objekte pro Funddatum-Jahrzehnt (Dekade), Label ``1980er``, ``1990er`` ...

    Aggregiert die Jahres-Verteilung auf 10er-Schritte; das Label ist die
    Dekaden-Startzahl mit Suffix ``er`` (Sammler-Konvention: "Funde aus den
    1990ern"). Ohne Limit, weil die Zahl der Dekaden ueberschaubar bleibt
    (~10-15 ueber ein Sammlerleben).

    Komplementaer zu :func:`_count_funddatum_jahr`: zeigt grobe
    Aktivitaetsphasen ohne Einzeljahres-Rauschen. Sortierung: chronologisch
    aufsteigend (aelteste Dekade zuerst), damit das Histogramm zeitlich
    lesbar bleibt.
    """
    sql = (
        "SELECT (CAST(substr(Funddatum, 1, 4) AS INTEGER) / 10) * 10 AS dekade, "
        "       COUNT(*) AS n FROM objects "
        "WHERE Funddatum IS NOT NULL AND TRIM(Funddatum) != '' "
        "AND substr(Funddatum, 1, 4) GLOB '[0-9][0-9][0-9][0-9]' "
        "GROUP BY dekade ORDER BY dekade ASC"
    )
    return {f"{r['dekade']}er": r["n"] for r in conn.execute(sql).fetchall()}


def _count_erstellt_am_jahr(conn: sqlite3.Connection) -> dict[str, int]:
    """Zaehlt Objekte pro ``erstellt_am``-Jahr (Sammlungswachstum).

    Antwort auf die Sammler-Frage "wie ist meine Sammlung gewachsen?". Im
    Gegensatz zu :func:`_count_funddatum_jahr` (wann wurde gefunden) zaehlt
    dieser Block, wann das Objekt erfasst wurde - also wie aktiv pro Jahr
    erfasst/digitalisiert wurde, unabhaengig vom Fundzeitpunkt.

    ``erstellt_am`` wird beim Insert in repository.py auf
    ``YYYY-MM-DD HH:MM:SS`` gesetzt; der Substring-Trick auf den ersten vier
    Ziffern reicht und ist analog zu :func:`_count_funddatum_jahr`. NULL/
    Whitespace und Eintraege ohne vierstelligen Jahres-Praefix bleiben aus
    der Statistik (historische Imports koennten leere Stempel haben).

    Sortierung: chronologisch aufsteigend (aelteste Jahre zuerst), damit das
    Wachstums-Histogramm zeitlich lesbar bleibt. Ohne Limit, weil die Zahl der
    Jahre ueberschaubar bleibt (~10-30 ueber eine Sammler-Karriere).
    """
    sql = (
        "SELECT substr(erstellt_am, 1, 4) AS jahr, COUNT(*) AS n FROM objects "
        "WHERE erstellt_am IS NOT NULL AND TRIM(erstellt_am) != '' "
        "AND substr(erstellt_am, 1, 4) GLOB '[0-9][0-9][0-9][0-9]' "
        "GROUP BY jahr ORDER BY jahr ASC"
    )
    return {r["jahr"]: r["n"] for r in conn.execute(sql).fetchall()}


def _count_erstellt_am_jahrzehnt(conn: sqlite3.Connection) -> dict[str, int]:
    """Zaehlt Objekte pro ``erstellt_am``-Jahrzehnt (Erfassungs-Dekade), Label ``2010er``, ``2020er`` ...

    Spiegelt :func:`_count_funddatum_jahrzehnt` um die Erfassungs-Achse:
    aggregiert die Erfassungs-Jahres-Verteilung auf 10er-Schritte. Sammler-
    typische Antwort auf "in welcher Dekade ist mein Bestand entstanden?";
    macht uebergreifende Erfassungs-Wellen sichtbar, die im Jahres-Histogramm
    durch Einzeljahr-Rauschen verdeckt werden (z.B. Migration einer alten
    Excel-Sammlung in 2020+ konzentriert auf wenige Jahre, alles davor in
    Papier-Tagebuechern).

    ``erstellt_am`` hat im Insert-Pfad das Format ``YYYY-MM-DD HH:MM:SS``;
    Substring 1..4 reicht als Jahres-Praefix. Ohne gueltigen Jahres-Praefix
    werden Eintraege ausgeschlossen (kaputte Stempel historischer Imports).
    Sortierung: chronologisch aufsteigend (aelteste Dekade zuerst), damit
    das Histogramm zeitlich lesbar bleibt. Ohne Limit, weil die Zahl der
    Dekaden ueberschaubar bleibt (~3-5 ueber eine Sammler-Karriere).
    """
    sql = (
        "SELECT (CAST(substr(erstellt_am, 1, 4) AS INTEGER) / 10) * 10 AS dekade, "
        "       COUNT(*) AS n FROM objects "
        "WHERE erstellt_am IS NOT NULL AND TRIM(erstellt_am) != '' "
        "AND substr(erstellt_am, 1, 4) GLOB '[0-9][0-9][0-9][0-9]' "
        "GROUP BY dekade ORDER BY dekade ASC"
    )
    return {f"{r['dekade']}er": r["n"] for r in conn.execute(sql).fetchall()}


def _count_erstellt_am_monat(conn: sqlite3.Connection) -> dict[str, int]:
    """Zaehlt Objekte pro ``erstellt_am``-Monat (Erfassungs-Saisonalitaet).

    Spiegelt :func:`_count_funddatum_monat` um die Erfassungs-Achse: zeigt,
    in welchen Monaten typischerweise digitalisiert wird (Winter-Indoor-Phasen
    vs. Sommer-Pausen waehrend Feld-Aktivitaeten). Aggregiert ueber alle Jahre,
    Labels ``"01"`` .. ``"12"``; Monate ohne Treffer fehlen im Dict.

    ``erstellt_am`` hat im Insert-Pfad das Format ``YYYY-MM-DD HH:MM:SS``;
    Monatsteil sitzt deterministisch in Substring 6..7. Eintraege ohne
    gueltigen Jahres-Praefix oder mit Monatsteil ausserhalb 01..12 werden
    ausgeschlossen (defensive Behandlung historischer Imports mit kaputten
    Stempeln), damit die Saison-Statistik nicht verzerrt wird.
    """
    sql = (
        "SELECT substr(erstellt_am, 6, 2) AS monat, COUNT(*) AS n FROM objects "
        "WHERE erstellt_am IS NOT NULL AND TRIM(erstellt_am) != '' "
        "AND substr(erstellt_am, 1, 4) GLOB '[0-9][0-9][0-9][0-9]' "
        "AND substr(erstellt_am, 6, 2) GLOB '[0-1][0-9]' "
        "AND CAST(substr(erstellt_am, 6, 2) AS INTEGER) BETWEEN 1 AND 12 "
        "GROUP BY monat ORDER BY monat ASC"
    )
    return {r["monat"]: r["n"] for r in conn.execute(sql).fetchall()}


def _count_geaendert_am_jahr(conn: sqlite3.Connection) -> dict[str, int]:
    """Zaehlt Objekte pro ``geaendert_am``-Jahr (Pflege-Aktivitaet pro Jahr).

    Spiegelt :func:`_count_erstellt_am_jahr` um die Aenderungs-Achse: waehrend
    ``by_erstellt_am_jahr`` das Sammlungswachstum beziffert (wann erfasst), zeigt
    ``by_geaendert_am_jahr`` die Pflege-Aktivitaet (wann zuletzt redaktionell
    beruehrt). Aussenkontext-bedingt sehr ungleichmaessig: ein Stueck, das nach
    der Erst-Erfassung nie wieder angefasst wurde, traegt ``geaendert_am ==
    erstellt_am`` (Insert-Pfad setzt beide synchron in repository._now()), und
    landet daher im Sammlungswachstums-Histogramm. Stuecke, die spaeter nach-
    gepflegt wurden (z.B. KI-Analyse uebernommen, Foto nachgereicht, Mineral-
    Bestimmung korrigiert), erscheinen hier in einem spaeteren Jahr - die
    Differenz beider Histogramme zeigt die nachtraegliche Pflege-Aktivitaet pro
    Jahr.

    ``geaendert_am`` hat im repository._now()-Pfad das Format
    ``YYYY-MM-DD HH:MM:SS``; Substring 1..4 reicht als Jahres-Praefix und ist
    analog zu :func:`_count_erstellt_am_jahr`. NULL/Whitespace und Eintraege
    ohne vierstelligen Jahres-Praefix bleiben aus der Statistik (kaputte
    Stempel historischer Imports). Sortierung chronologisch aufsteigend
    (aelteste Jahre zuerst), damit das Pflege-Histogramm zeitlich lesbar
    bleibt. Ohne Limit, weil die Zahl der Jahre ueberschaubar bleibt
    (~10-30 ueber eine Sammler-Karriere).
    """
    sql = (
        "SELECT substr(geaendert_am, 1, 4) AS jahr, COUNT(*) AS n FROM objects "
        "WHERE geaendert_am IS NOT NULL AND TRIM(geaendert_am) != '' "
        "AND substr(geaendert_am, 1, 4) GLOB '[0-9][0-9][0-9][0-9]' "
        "GROUP BY jahr ORDER BY jahr ASC"
    )
    return {r["jahr"]: r["n"] for r in conn.execute(sql).fetchall()}


def _count_geaendert_am_jahrzehnt(conn: sqlite3.Connection) -> dict[str, int]:
    """Zaehlt Objekte pro ``geaendert_am``-Jahrzehnt (Pflege-Dekade), Label ``2010er``, ``2020er`` ...

    Spiegelt :func:`_count_erstellt_am_jahrzehnt` um die Aenderungs-Achse:
    aggregiert das Pflege-Jahres-Histogramm auf 10er-Schritte und macht so
    uebergreifende Pflege-Wellen sichtbar, die im reinen Jahres-Histogramm
    durch Einzeljahr-Rauschen verdeckt werden. Beantwortet "in welcher Dekade
    bin ich besonders aktiv im redaktionellen Pflegen gewesen?" - z.B. die
    KI-Welle 2024+ konzentriert auf wenige Jahre, davor handgepflegte 2010er-
    Phase. Komplementaer zu :func:`_count_geaendert_am_jahr` (Einzel-Jahres-
    Aufloesung): hier die grobe Dekaden-Sicht. Komplementaer zu
    :func:`_count_erstellt_am_jahrzehnt` (Erfassungs-Achse, wann erfasst):
    hier die Aenderungs-Achse (wann zuletzt redaktionell beruehrt). Die
    Differenz beider Dekaden-Histogramme zeigt die nachtraegliche Pflege-
    Verschiebung pro Dekade.

    ``geaendert_am`` hat im repository._now()-Pfad das Format
    ``YYYY-MM-DD HH:MM:SS``; Substring 1..4 reicht als Jahres-Praefix. Ohne
    gueltigen Jahres-Praefix werden Eintraege ausgeschlossen (kaputte Stempel
    historischer Imports). Sortierung chronologisch aufsteigend (aelteste
    Dekade zuerst), damit das Histogramm zeitlich lesbar bleibt. Ohne Limit,
    weil die Zahl der Dekaden ueberschaubar bleibt (~3-5 ueber eine Sammler-
    Karriere).
    """
    sql = (
        "SELECT (CAST(substr(geaendert_am, 1, 4) AS INTEGER) / 10) * 10 AS dekade, "
        "       COUNT(*) AS n FROM objects "
        "WHERE geaendert_am IS NOT NULL AND TRIM(geaendert_am) != '' "
        "AND substr(geaendert_am, 1, 4) GLOB '[0-9][0-9][0-9][0-9]' "
        "GROUP BY dekade ORDER BY dekade ASC"
    )
    return {f"{r['dekade']}er": r["n"] for r in conn.execute(sql).fetchall()}


def _count_geaendert_am_monat(conn: sqlite3.Connection) -> dict[str, int]:
    """Zaehlt Objekte pro ``geaendert_am``-Monat (Pflege-Saisonalitaet).

    Spiegelt :func:`_count_erstellt_am_monat` um die Aenderungs-Achse und
    schliesst die Histogramm-Trias auf der Aenderungs-Achse ab (Jahr / Jahrzehnt
    / Monat) - parallel zur Funddatums- und Erfassungs-Achse, die alle drei
    Aggregationsstufen tragen. Beantwortet "in welchen Monaten ueber alle Jahre
    bin ich besonders aktiv im Pflegen gewesen?", aggregiert ueber alle Jahre,
    Labels ``"01"`` .. ``"12"``; Monate ohne Treffer fehlen im Dict.

    Aussenkontext-bedingt typisch konzentriert auf Winter-Indoor-Phasen
    (Sammlungsdurchsicht waehrend der kalten Monate, Boersen-Vorbereitung
    Januar-Februar) und auf Pflege-Wellen-Monate (z.B. ein Sommer-Monat mit
    intensiver KI-Analyse-Welle), waehrend die Sommer-Feldsaison typisch
    pflegearm bleibt - die Differenz zur Erfassungs-Saisonalitaet zeigt die
    nachtraegliche Pflege-Verschiebung pro Saison, die im reinen Erfassungs-
    Saison-Bild untergeht.

    ``geaendert_am`` hat im repository._now()-Pfad das Format
    ``YYYY-MM-DD HH:MM:SS``; Monatsteil sitzt deterministisch in Substring 6..7.
    Eintraege ohne gueltigen Jahres-Praefix oder mit Monatsteil ausserhalb
    01..12 werden ausgeschlossen (defensive Behandlung historischer Imports
    mit kaputten Stempeln), damit die Saison-Statistik nicht verzerrt wird -
    spiegelt :func:`_count_erstellt_am_monat` exakt.
    """
    sql = (
        "SELECT substr(geaendert_am, 6, 2) AS monat, COUNT(*) AS n FROM objects "
        "WHERE geaendert_am IS NOT NULL AND TRIM(geaendert_am) != '' "
        "AND substr(geaendert_am, 1, 4) GLOB '[0-9][0-9][0-9][0-9]' "
        "AND substr(geaendert_am, 6, 2) GLOB '[0-1][0-9]' "
        "AND CAST(substr(geaendert_am, 6, 2) AS INTEGER) BETWEEN 1 AND 12 "
        "GROUP BY monat ORDER BY monat ASC"
    )
    return {r["monat"]: r["n"] for r in conn.execute(sql).fetchall()}


def _funddatum_spanne(conn: sqlite3.Connection) -> tuple[str | None, str | None]:
    """Liefert (fruehestes, spaetestes) Funddatum als ISO-String.

    Beruecksichtigt nur Werte, die mit vier Ziffern beginnen (siehe
    :func:`_count_funddatum_jahr`); ISO YYYY-MM-DD ist lexikographisch
    sortierbar. Reine Jahresangaben (``"2024"``) werden mit einbezogen
    und tauchen so als Grenze auf, sofern keine spezifischere Angabe da ist.
    Leere DB → ``(None, None)``.
    """
    row = conn.execute(
        "SELECT MIN(Funddatum) AS lo, MAX(Funddatum) AS hi FROM objects "
        "WHERE Funddatum IS NOT NULL AND TRIM(Funddatum) != '' "
        "AND substr(Funddatum, 1, 4) GLOB '[0-9][0-9][0-9][0-9]'"
    ).fetchone()
    return (row["lo"], row["hi"])


def _erstellt_am_spanne(conn: sqlite3.Connection) -> tuple[str | None, str | None]:
    """Liefert (fruehestes, spaetestes) ``erstellt_am`` als Zeitstempel-String.

    Spiegelt :func:`_funddatum_spanne` auf die Erfassungs-Achse: waehrend die
    Funddatum-Spanne den Sammlungs-Zeitraum auf der Fund-Achse beziffert
    ("seit wann sammle ich Stuecke aus dem Aaregebiet?"), beziffert die
    erstellt_am-Spanne den Erfassungs-Zeitraum ("seit wann digitalisiere ich
    diese Sammlung?"). Beide gemeinsam machen die zwei Zeit-Achsen einer
    Sammlung sichtbar - Fund-Zeit (oft Jahrzehnte rueckwirkend, geerbt) vs.
    Erfassungs-Zeit (typisch wenige Jahre, beginnt mit der Anschaffung der
    Verwaltungs-App). Komplementaer zu by_erstellt_am_jahr/jahrzehnt/monat
    (Erfassungs-Histogramm: Verteilung ueber die Zeit) - hier die zwei
    aeusseren Grenzen, dort die innere Verteilung.

    ``erstellt_am`` hat im Insert-Pfad das Format ``YYYY-MM-DD HH:MM:SS``;
    MIN/MAX arbeitet lexikographisch und liefert die vollstaendigen Zeitstempel
    (inkl. Sekunden-Aufloesung) zurueck - feiner als bei Funddatum, das nur
    Tag-Aufloesung hat. Substring-Filter auf vierstelligen Jahres-Praefix
    spiegelt _funddatum_spanne; Eintraege mit leerem/NULL/kaputtem Stempel
    (historische Imports) bleiben aus der Spanne, damit ein einzelner
    fehlerhafter Eintrag die Grenze nicht verzerrt. Leere DB → ``(None, None)``.
    """
    row = conn.execute(
        "SELECT MIN(erstellt_am) AS lo, MAX(erstellt_am) AS hi FROM objects "
        "WHERE erstellt_am IS NOT NULL AND TRIM(erstellt_am) != '' "
        "AND substr(erstellt_am, 1, 4) GLOB '[0-9][0-9][0-9][0-9]'"
    ).fetchone()
    return (row["lo"], row["hi"])


def _geaendert_am_spanne(conn: sqlite3.Connection) -> tuple[str | None, str | None]:
    """Liefert (fruehestes, spaetestes) ``geaendert_am`` als Zeitstempel-String.

    Vervollstaendigt das Trio der Sammler-Zeit-Spannen: Fund (was wurde wann
    gefunden), Erfassung (wann digitalisiert), Aenderung (wann zuletzt
    angefasst). Beantwortet zwei Pflege-typische Fragen, die weder Funddatum-
    noch Erfassungs-Spanne klar zeigt: das Minimum verraet, ob es noch nie-
    aktualisierte Alt-Eintraege gibt (deren geaendert_am identisch zum
    erstellt_am bleibt - oder, in der Bestaends-Sicht, das aelteste Eintrag-
    Datum ueberhaupt). Das Maximum nennt die letzte Pflege-Aktivitaet ueber
    den gesamten Bestand - "Wann war meine letzte Datenpflege-Sitzung?",
    nuetzlich vor Backup-/Export-Sitzungen oder zur Diagnose einer
    eingeschlafenen Sammlungspflege ("nichts mehr seit 6 Monaten geaendert -
    ist die Sammlung still oder die App nicht mehr im Einsatz?").

    Spiegelt _erstellt_am_spanne strukturell: MIN/MAX ueber objects.geaendert_am
    mit dem identischen Praefix-Filter (substr 1..4 GLOB Ziffern), weil
    geaendert_am wie erstellt_am im Insert-/Update-Pfad von repository._now()
    im sortierbaren Format YYYY-MM-DD HH:MM:SS gesetzt wird. Voller Zeitstempel
    inkl. HH:MM:SS bleibt erhalten. Komplementaer zu geaendert_vor_erstellt
    und future_geaendert_am in integrity.py (Konsistenz-Checks): hier die
    aeusseren Grenzen, dort die semantische Validitaet pro Eintrag. Leere
    DB → (None, None), spiegelt das _funddatum_spanne-/_erstellt_am_spanne-
    Verhalten.
    """
    row = conn.execute(
        "SELECT MIN(geaendert_am) AS lo, MAX(geaendert_am) AS hi FROM objects "
        "WHERE geaendert_am IS NOT NULL AND TRIM(geaendert_am) != '' "
        "AND substr(geaendert_am, 1, 4) GLOB '[0-9][0-9][0-9][0-9]'"
    ).fetchone()
    return (row["lo"], row["hi"])


def _mohs_spanne(conn: sqlite3.Connection) -> tuple[float | None, float | None]:
    """Liefert (kleinste, groesste) Mohs-Haerte als Kollektion-Spanne.

    Spiegelt :func:`_funddatum_spanne` auf die Mohs-Haerte-Achse: waehrend die
    Funddatum-Spanne den Sammlungs-Zeitraum auf der Fund-Achse beziffert,
    beziffert die Mohs-Spanne die Haerte-Bandbreite der Sammlung ("vom
    weichsten Talk-Stueck zum haertesten Korund-Stueck") und ergaenzt damit
    die Coverage-Quote ``quote_mit_mohs_prozent`` (Pflege-Sicht) um die
    physikalische Extent-Sicht ueber den dokumentierten Bestand.

    Mohs-Haerte liegt pro Objekt als Bereich vor (``Mohs_Haerte_min``/
    ``Mohs_Haerte_max``), z.B. "5-6" fuer Apatit-typische Stuecke; in der
    Praxis ist oft nur eine Achse gepflegt (Punkt-Wert wie "7" fuer Quarz
    wird als ``min=7`` ohne max gespeichert, oder als ``min=max=7``).
    COALESCE(min, max)/COALESCE(max, min) faengt die Single-Point-Faelle ab
    und behandelt sie als beidseitige Grenze - spiegelt die has_mohs-/
    objekte_mit_mohs-Konvention exakt: ein Objekt zaehlt, sobald eines der
    beiden Bereichsfelder gesetzt ist. WHERE filtert Eintraege ohne jegliche
    Haerte-Angabe (beide NULL) heraus, damit nicht-gepflegte Stuecke die
    Spanne nicht auf ``(NULL, NULL)`` verfaelschen. Leere DB → (None, None),
    spiegelt das _funddatum_spanne-/_erstellt_am_spanne-Verhalten.
    """
    row = conn.execute(
        "SELECT MIN(COALESCE(Mohs_Haerte_min, Mohs_Haerte_max)) AS lo, "
        "MAX(COALESCE(Mohs_Haerte_max, Mohs_Haerte_min)) AS hi "
        "FROM objects "
        "WHERE Mohs_Haerte_min IS NOT NULL OR Mohs_Haerte_max IS NOT NULL"
    ).fetchone()
    lo = float(row["lo"]) if row["lo"] is not None else None
    hi = float(row["hi"]) if row["hi"] is not None else None
    return (lo, hi)


def _mohs_durchschnitt(conn: sqlite3.Connection) -> float | None:
    """Liefert den arithmetischen Mittelwert der Mohs-Haerte-Mittelpunkte.

    Spiegelt :func:`_mohs_spanne` (Extent-Sicht: kleinster/groesster Wert) auf
    die zentrale-Tendenz-Sicht: waehrend die Spanne die Bandbreite der Sammlung
    beziffert ("vom weichsten Talk-Stueck zum haertesten Korund-Stueck"),
    beziffert der Durchschnitt die "typische" Haerte des dokumentierten
    Bestands. Ergaenzt damit die Mohs-Kennzahlen-Achse (min/max) um die
    zentrale-Tendenz-Achse, spiegelt das gewicht_min_g/gewicht_max_g/
    gewicht_durchschnitt_g-Trio auf die Mohs-Haerte.

    Pro Objekt wird der Mittelpunkt des dokumentierten Bereichs verwendet:
    bei zwei Werten (min UND max) der arithmetische Mittelwert, bei
    Single-Point-Pflege (nur min ODER nur max) der eine Wert. Reuse der
    has_mohs-/objekte_mit_mohs-Konvention (ein Objekt zaehlt, sobald eines
    der beiden Bereichsfelder gesetzt ist); Eintraege ohne jegliche Haerte-
    Pflege bleiben aus dem Durchschnitt. Bei leerer DB / ohne jegliche
    Mohs-Pflege bleibt der Durchschnitt None - spiegelt das _mohs_spanne-
    Verhalten und macht die CLI-Zeile bei nicht-gepflegter Sammlung
    optional (analog zur Spanne-Zeile).
    """
    row = conn.execute(
        "SELECT AVG((COALESCE(Mohs_Haerte_min, Mohs_Haerte_max) + "
        "COALESCE(Mohs_Haerte_max, Mohs_Haerte_min)) / 2.0) AS avg "
        "FROM objects "
        "WHERE Mohs_Haerte_min IS NOT NULL OR Mohs_Haerte_max IS NOT NULL"
    ).fetchone()
    return float(row["avg"]) if row["avg"] is not None else None


def _mohs_median(conn: sqlite3.Connection) -> float | None:
    """Liefert den Median der Mohs-Haerte-Mittelpunkte ueber die Sammlung.

    Spiegelt :func:`_mohs_durchschnitt` (arithmetisches Mittel als zentrale
    Tendenz) auf die ausreisser-robuste zentrale Tendenz: waehrend der
    Durchschnitt sensibel auf einzelne sehr weiche/harte Ausreisser reagiert
    (ein Diamant-Splitter mit Mohs 10 in einer sonst Calcit-lastigen Sammlung
    zieht den Durchschnitt nach oben), bleibt der Median unempfindlich - er
    beziffert das "typische" Stueck als 50%-Quantil der Haerte-Verteilung.
    Vervollstaendigt damit das Mohs-Kennzahlen-Trio (min/max/durchschnitt) um
    die Median-Achse, spiegelt das gewicht_max_g/gewicht_durchschnitt_g/
    gewicht_median_g- und wert_max_chf/wert_durchschnitt_chf/wert_median_chf-
    Quartett auf die physikalische Haerte-Achse.

    Pro Objekt wird der Mittelpunkt des dokumentierten Bereichs verwendet
    (bei zwei Werten: (min+max)/2; bei Single-Point-Pflege: der eine Wert -
    spiegelt die _mohs_durchschnitt-Konvention via COALESCE). Reuse der
    has_mohs-/objekte_mit_mohs-Konvention (ein Objekt zaehlt, sobald eines
    der beiden Bereichsfelder gesetzt ist). Median berechnet sich klassisch:
    bei ungerader Anzahl das mittlere Element der sortierten Liste, bei
    gerader Anzahl der Mittelwert der beiden mittleren Elemente - spiegelt
    das gewicht_median_g-/wert_median_chf-Verhalten exakt. Bei leerer DB /
    ohne jegliche Mohs-Pflege bleibt der Median None (spiegelt das
    _mohs_durchschnitt-/_mohs_spanne-Verhalten und macht die CLI-Zeile bei
    nicht-gepflegter Sammlung optional).
    """
    mittelpunkte = [float(r["mid"]) for r in conn.execute(
        "SELECT (COALESCE(Mohs_Haerte_min, Mohs_Haerte_max) + "
        "COALESCE(Mohs_Haerte_max, Mohs_Haerte_min)) / 2.0 AS mid "
        "FROM objects "
        "WHERE Mohs_Haerte_min IS NOT NULL OR Mohs_Haerte_max IS NOT NULL "
        "ORDER BY mid"
    ).fetchall()]
    if not mittelpunkte:
        return None
    n = len(mittelpunkte)
    return (mittelpunkte[n // 2] if n % 2
            else (mittelpunkte[n // 2 - 1] + mittelpunkte[n // 2]) / 2)


def _mohs_standardabweichung(conn: sqlite3.Connection) -> float | None:
    """Liefert die Populations-Standardabweichung der Mohs-Haerte-Mittelpunkte.

    Spiegelt :func:`_mohs_durchschnitt` (zentrale Tendenz) und :func:`_mohs_median`
    (robuste zentrale Tendenz) auf die Dispersions-Achse: waehrend Durchschnitt
    und Median das "typische" Stueck beziffern, beziffert die Standardabweichung
    die "Streuung" der Sammlung um den Durchschnitt - eine Sammlung mit Mohs-
    Durchschnitt 6.0 und Standardabweichung 0.5 (reine Quarz-Familie 5.5..6.5)
    ist mineralogisch anders zusammengesetzt als eine mit demselben Durchschnitt
    6.0 und Standardabweichung 3.0 (Talk + Diamant gemischt 1..10). Ergaenzt
    damit das Mohs-Kennzahlen-Quartett (min/max/durchschnitt/median) um die
    Dispersions-Achse und macht die Verteilungs-Form ueber die Bandbreite
    hinaus sichtbar - die Spanne allein sagt nichts ueber die Konzentration
    der Stuecke innerhalb der Grenzen (Mohs 1..10 mit gleichmaessig verteilten
    Zwischenwerten vs. Mohs 1..10 mit polarisierten Extremen sehen in der
    Spanne identisch aus, in der Standardabweichung erst nicht).

    Pro Objekt wird der Mittelpunkt des dokumentierten Bereichs verwendet
    (bei zwei Werten: (min+max)/2; bei Single-Point-Pflege: der eine Wert -
    spiegelt die _mohs_durchschnitt-/_mohs_median-Konvention via COALESCE).
    Reuse der has_mohs-/objekte_mit_mohs-Konvention (ein Objekt zaehlt,
    sobald eines der beiden Bereichsfelder gesetzt ist). Berechnung nach der
    Populations-Formel sqrt(E[X^2] - E[X]^2) mit AVG-basiertem E[X] und
    AVG(mid*mid)-basiertem E[X^2] in einer einzigen SQL-Round-Trip; bewusst
    die Populations-Variante (Divisor n statt n-1), weil die Sammlung als
    vollstaendige Grundgesamtheit betrachtet wird (nicht als Stichprobe einer
    groesseren mineralogischen Population). Bei einem einzelnen Mohs-Eintrag
    kollabiert die Streuung auf 0.0 (keine Dispersion moeglich); bei
    identischen Mittelpunkten ebenfalls 0.0 (E[X^2] = E[X]^2). Bei leerer DB
    / ohne jegliche Mohs-Pflege bleibt None (spiegelt das _mohs_durchschnitt-/
    _mohs_median-Verhalten und macht die CLI-Zeile bei nicht-gepflegter
    Sammlung optional). Der max(...,0.0)-Guard faengt negative Floating-
    Point-Artefakte ab (E[X^2] - E[X]^2 kann bei identischen Werten durch
    Rundungsfehler auf -1e-16 fallen, sqrt wuerde NaN liefern).
    """
    row = conn.execute(
        "SELECT AVG(mid) AS mean, AVG(mid * mid) AS mean_sq "
        "FROM (SELECT (COALESCE(Mohs_Haerte_min, Mohs_Haerte_max) + "
        "COALESCE(Mohs_Haerte_max, Mohs_Haerte_min)) / 2.0 AS mid "
        "FROM objects "
        "WHERE Mohs_Haerte_min IS NOT NULL OR Mohs_Haerte_max IS NOT NULL)"
    ).fetchone()
    if row["mean"] is None:
        return None
    var = float(row["mean_sq"]) - float(row["mean"]) ** 2
    return (max(var, 0.0)) ** 0.5


def _dichte_durchschnitt(conn: sqlite3.Connection) -> float | None:
    """Liefert den arithmetischen Mittelwert der Dichte-Mittelpunkte in g/cm3.

    Spiegelt :func:`_mohs_durchschnitt` (zentrale-Tendenz-Achse zur Mohs-
    Spannen-Achse) auf die physikalische Dichte-Achse: waehrend die Dichte-
    Spanne die Massendichte-Bandbreite beziffert ("vom leichtesten Bims-/
    Opal-Stueck zum schwersten Pyrit-/Galenit-Stueck"), beziffert der
    Durchschnitt die "typische" Dichte des dokumentierten Bestands.
    Vervollstaendigt damit die Dichte-Kennzahlen-Achse (min/max/durchschnitt)
    und macht sie strukturidentisch zur Mohs-Kennzahlen-Achse.

    Pro Objekt wird der Mittelpunkt des dokumentierten Bereichs verwendet:
    bei zwei Werten (min UND max) der arithmetische Mittelwert (min+max)/2,
    bei Single-Point-Pflege (nur min ODER nur max gesetzt) der eine Wert -
    spiegelt die _dichte_spanne-Konvention via COALESCE. Reuse der has_dichte-/
    objekte_mit_dichte-Konvention (ein Objekt zaehlt, sobald eines der beiden
    Bereichsfelder gesetzt ist); Eintraege ohne jegliche Dichte-Pflege
    bleiben aus dem Durchschnitt. Bei leerer DB / ohne jegliche Dichte-Pflege
    liefert AVG NULL, das wird auf None gemappt und macht die CLI-Zeile
    optional (spiegelt das _mohs_durchschnitt-/_dichte_spanne-Verhalten).
    """
    row = conn.execute(
        "SELECT AVG((COALESCE(Dichte_min_gcm3, Dichte_max_gcm3) + "
        "COALESCE(Dichte_max_gcm3, Dichte_min_gcm3)) / 2.0) AS avg "
        "FROM objects "
        "WHERE Dichte_min_gcm3 IS NOT NULL OR Dichte_max_gcm3 IS NOT NULL"
    ).fetchone()
    return float(row["avg"]) if row["avg"] is not None else None


def _dichte_standardabweichung(conn: sqlite3.Connection) -> float | None:
    """Liefert die Populations-Standardabweichung der Dichte-Mittelpunkte in g/cm3.

    Spiegelt :func:`_mohs_standardabweichung` (Dispersions-Achse zur zentralen-
    Tendenz-Achse) auf die physikalische Dichte-Achse: waehrend Durchschnitt
    und Median das "typische" Stueck beziffern, beziffert die Standardabweichung
    die Streuung der Sammlung um den Durchschnitt - eine reine Quarz-Familie
    (Dichte 2.65..2.67) zeigt hier ~0.01, eine gemischte Sammlung mit Bims
    (~1.0) bis Galenit (~7.5) dagegen ~2.0. Vervollstaendigt damit das Dichte-
    Kennzahlen-Quartett (min/max/durchschnitt/median) um die Dispersions-Achse
    und stellt es strukturell parallel zum Mohs-Kennzahlen-Quintett auf
    (Extent + Zentrum + robustes Zentrum + Streuung).

    Pro Objekt wird der Mittelpunkt des dokumentierten Bereichs verwendet
    (bei zwei Werten: (min+max)/2; bei Single-Point-Pflege: der eine Wert -
    spiegelt die _dichte_durchschnitt-/_dichte_median-Konvention via COALESCE).
    Reuse der has_dichte-/objekte_mit_dichte-Konvention (ein Objekt zaehlt,
    sobald eines der beiden Bereichsfelder gesetzt ist). Berechnung nach der
    Populations-Formel sqrt(E[X^2] - E[X]^2) mit AVG-basiertem E[X] und
    AVG(mid*mid)-basiertem E[X^2] in einer einzigen SQL-Round-Trip; bewusst
    die Populations-Variante (Divisor n statt n-1), spiegelt die
    _mohs_standardabweichung-Konvention (Sammlung als vollstaendige Grund-
    gesamtheit, nicht Stichprobe). Bei einem einzelnen Dichte-Eintrag
    kollabiert die Streuung auf 0.0, bei identischen Mittelpunkten ebenfalls
    0.0. Bei leerer DB / ohne jegliche Dichte-Pflege bleibt None. Der
    max(...,0.0)-Guard faengt negative Floating-Point-Artefakte ab (bei
    identischen Werten kann E[X^2] - E[X]^2 durch Rundung auf -1e-16 fallen,
    sqrt wuerde NaN liefern) - spiegelt _mohs_standardabweichung exakt.
    """
    row = conn.execute(
        "SELECT AVG(mid) AS mean, AVG(mid * mid) AS mean_sq "
        "FROM (SELECT (COALESCE(Dichte_min_gcm3, Dichte_max_gcm3) + "
        "COALESCE(Dichte_max_gcm3, Dichte_min_gcm3)) / 2.0 AS mid "
        "FROM objects "
        "WHERE Dichte_min_gcm3 IS NOT NULL OR Dichte_max_gcm3 IS NOT NULL)"
    ).fetchone()
    if row["mean"] is None:
        return None
    var = float(row["mean_sq"]) - float(row["mean"]) ** 2
    return (max(var, 0.0)) ** 0.5


def _dichte_median(conn: sqlite3.Connection) -> float | None:
    """Liefert den Median der Dichte-Mittelpunkte in g/cm3 ueber die Sammlung.

    Spiegelt :func:`_mohs_median` (ausreisser-robuste zentrale Tendenz zur
    Durchschnitts-Achse) auf die physikalische Dichte-Achse: waehrend der
    Durchschnitt sensibel auf einzelne sehr leichte/schwere Ausreisser
    reagiert (ein Galenit-Stueck mit ~7.5 g/cm3 in einer sonst Quarz-lastigen
    Sammlung zieht den Durchschnitt hoch), bleibt der Median unempfindlich -
    er beziffert das "typische" Stueck als 50%-Quantil der Dichte-Verteilung
    und bleibt auch bei extremen Ausreissern beim Cluster-Wert. Vervollstaendigt
    damit das Dichte-Kennzahlen-Trio (min/max/durchschnitt) um die Median-
    Achse und stellt es strukturidentisch neben das Mohs-Kennzahlen-Quartett
    (min/max/durchschnitt/median).

    Pro Objekt wird der Mittelpunkt des dokumentierten Bereichs verwendet
    (bei zwei Werten: (min+max)/2; bei Single-Point-Pflege: der eine Wert -
    spiegelt die _dichte_durchschnitt-Konvention via COALESCE). Reuse der
    has_dichte-/objekte_mit_dichte-Konvention (ein Objekt zaehlt, sobald
    eines der beiden Bereichsfelder gesetzt ist). Median berechnet sich
    klassisch: bei ungerader Anzahl das mittlere Element der sortierten
    Liste, bei gerader Anzahl der Mittelwert der beiden mittleren Elemente -
    spiegelt das _mohs_median-Verhalten exakt. SQL sortiert deterministisch
    ueber ORDER BY mid. Bei leerer DB / ohne jegliche Dichte-Pflege bleibt
    der Median None (spiegelt das _mohs_median-/_dichte_spanne-Verhalten).
    """
    mittelpunkte = [float(r["mid"]) for r in conn.execute(
        "SELECT (COALESCE(Dichte_min_gcm3, Dichte_max_gcm3) + "
        "COALESCE(Dichte_max_gcm3, Dichte_min_gcm3)) / 2.0 AS mid "
        "FROM objects "
        "WHERE Dichte_min_gcm3 IS NOT NULL OR Dichte_max_gcm3 IS NOT NULL "
        "ORDER BY mid"
    ).fetchall()]
    if not mittelpunkte:
        return None
    n = len(mittelpunkte)
    return (mittelpunkte[n // 2] if n % 2
            else (mittelpunkte[n // 2 - 1] + mittelpunkte[n // 2]) / 2)


def _dichte_spanne(conn: sqlite3.Connection) -> tuple[float | None, float | None]:
    """Liefert (kleinste, groesste) Dichte als Kollektion-Spanne in g/cm3.

    Spiegelt :func:`_mohs_spanne` auf die physikalische Dichte-Achse:
    waehrend die Mohs-Spanne die Haerte-Bandbreite ueber den dokumentierten
    Bestand beziffert ("vom weichsten Talk-Stueck zum haertesten Korund-
    Stueck"), beziffert die Dichte-Spanne die Massendichte-Bandbreite ("vom
    leichtesten Bims-/Opal-Stueck zum schwersten Pyrit-/Galenit-Stueck") und
    ergaenzt damit die Coverage-Quote ``quote_mit_dichte_prozent`` (Pflege-
    Sicht) um die physikalische Extent-Sicht ueber den dokumentierten Anteil.
    Vervollstaendigt das Spannen-Trio der physikalischen Mess-Achsen
    (Mohs/Dichte) auf der Bestands-Extent-Sicht symmetrisch zur Coverage-
    Achse - bisher gab es nur die Mohs-Spanne als physikalische Bandbreite-
    Kennzahl, waehrend Dichte als die zweite zentrale quantitative Pruef-
    Methode ohne Bandbreite-Sicht blieb.

    Dichte liegt pro Objekt als Bereich vor (``Dichte_min_gcm3``/
    ``Dichte_max_gcm3``), z.B. "2.6-2.7" fuer Quarz-typische Stuecke; in der
    Praxis ist oft nur eine Achse gepflegt (Punkt-Wert als Tabellen-
    Uebernahme aus einer Mineraldatenbank wird als ``min=max`` oder nur
    ``min`` gespeichert, oder eine Roh-Skala "2.6-2.7" als ``min=2.6/max=2.7``).
    COALESCE(min, max)/COALESCE(max, min) faengt die Single-Point-Faelle ab
    und behandelt sie als beidseitige Grenze - spiegelt die has_dichte-/
    objekte_mit_dichte-Konvention exakt: ein Objekt zaehlt, sobald eines der
    beiden Bereichsfelder gesetzt ist. WHERE filtert Eintraege ohne jegliche
    Dichte-Angabe (beide NULL) heraus, damit nicht-gepflegte Stuecke die
    Spanne nicht auf ``(NULL, NULL)`` verfaelschen. Leere DB → (None, None),
    spiegelt das _mohs_spanne-/_funddatum_spanne-Verhalten.
    """
    row = conn.execute(
        "SELECT MIN(COALESCE(Dichte_min_gcm3, Dichte_max_gcm3)) AS lo, "
        "MAX(COALESCE(Dichte_max_gcm3, Dichte_min_gcm3)) AS hi "
        "FROM objects "
        "WHERE Dichte_min_gcm3 IS NOT NULL OR Dichte_max_gcm3 IS NOT NULL"
    ).fetchone()
    lo = float(row["lo"]) if row["lo"] is not None else None
    hi = float(row["hi"]) if row["hi"] is not None else None
    return (lo, hi)


SCALE_1_10_COLUMNS: frozenset[str] = frozenset({
    "Seltenheit_global_1_10", "Seltenheit_Fundort_1_10", "Nachfrage_1_10",
})


def _count_scale_1_10(conn: sqlite3.Connection, column: str) -> dict[str, int]:
    """Zaehlt Objekte pro 1..10-Skalenwert (Seltenheit/Nachfrage).

    Ignoriert NULL und out-of-range-Werte (die werden separat in
    :func:`check_integrity` gemeldet und wuerden die Bucket-Sicht verzerren).
    Liefert ein Dict in chronologischer Skalen-Reihenfolge (1..10 aufsteigend);
    Skalenwerte ohne Treffer fehlen, damit der Dashboard-Bar-Chart nicht von
    leeren Buckets dominiert wird. Komplementaer zu :func:`_confidence_buckets`
    (0..100 in 5 Bucketts), hier feiner aufgeloest weil die Skala kleiner ist.

    ``column`` wird gegen :data:`SCALE_1_10_COLUMNS` validiert, um SQL-Injection
    ueber freie Spaltennamen auszuschliessen.
    """
    if column not in SCALE_1_10_COLUMNS:
        raise ValueError(f"Unzulaessige Skalen-Spalte: {column}")
    rows = conn.execute(
        f"SELECT {column} AS k, COUNT(*) AS n FROM objects "
        f"WHERE {column} IS NOT NULL AND {column} BETWEEN 1 AND 10 "
        f"GROUP BY k ORDER BY k ASC"
    ).fetchall()
    return {str(r["k"]): r["n"] for r in rows}


def _sum_by_scale_1_10(conn: sqlite3.Connection, column: str, value_sql: str,
                       extra_where: str = "") -> list[tuple[str, float]]:
    """Aggregiert ``SUM(value_sql)`` gruppiert nach 1..10-Skalenwert.

    Pendant zu :func:`_count_scale_1_10` (Anzahl), aber summiert Wert/Gewicht
    je Skalen-Bucket. Komplementaer zum ``seltenheit_global_min/max``-Filter
    (Drill-down auf einzelne Stuecke); hier die Wert-/Massen-Verteilung ueber
    die Rarity-/Nachfrage-Achse - macht "wo steckt der Wert in der seltenen
    Spitze (>=8) vs. in der Masse (<=3)?" sichtbar.

    Sortierung: absteigend nach Summe, Tie-Break aufsteigend nach Skalenwert
    (analog zu :func:`_sum_by`). Ohne Limit, weil maximal 10 Buckets vorkommen
    koennen - die Ausgabe wird nie laenger. Out-of-Range-Werte (<1 / >10)
    bleiben ausgeschlossen, damit die Aggregate nicht durch kaputte Skalen-
    Eintraege verzerrt werden (Integrity meldet die separat).

    ``column`` wird gegen :data:`SCALE_1_10_COLUMNS` validiert, um SQL-Injection
    ueber freie Spaltennamen auszuschliessen.
    """
    if column not in SCALE_1_10_COLUMNS:
        raise ValueError(f"Unzulaessige Skalen-Spalte: {column}")
    where = f"{column} IS NOT NULL AND {column} BETWEEN 1 AND 10"
    if extra_where:
        where = f"{where} AND {extra_where}"
    sql = (
        f"SELECT {column} AS k, SUM({value_sql}) AS w "
        f"FROM objects WHERE {where} "
        f"GROUP BY k HAVING w > 0 "
        f"ORDER BY w DESC, k ASC"
    )
    return [(str(r["k"]), float(r["w"])) for r in conn.execute(sql).fetchall()]


CONFIDENCE_BUCKET_ORDER: tuple[str, ...] = ("ohne", "0-24", "25-49", "50-74", "75-100")


def _confidence_bucket_case_sql(column: str = "Confidence_Prozent") -> str:
    """SQL-CASE-Ausdruck, der einen Confidence-Wert auf den Bucket-Namen abbildet.

    Geteilt von :func:`_confidence_buckets` (Anzahl) und
    :func:`_sum_by_confidence_bucket` (Wert/Gewicht), damit die Bucket-Grenzen
    nur an einer Stelle definiert sind und die beiden Aggregate garantiert
    deckungsgleich klassifizieren.
    """
    return (
        "CASE "
        f"  WHEN {column} IS NULL THEN 'ohne' "
        f"  WHEN {column} BETWEEN 0 AND 24 THEN '0-24' "
        f"  WHEN {column} BETWEEN 25 AND 49 THEN '25-49' "
        f"  WHEN {column} BETWEEN 50 AND 74 THEN '50-74' "
        f"  WHEN {column} BETWEEN 75 AND 100 THEN '75-100' "
        "  ELSE NULL END"
    )


def _sum_by_confidence_bucket(conn: sqlite3.Connection, value_sql: str,
                              extra_where: str = "") -> list[tuple[str, float]]:
    """Aggregiert ``SUM(value_sql)`` gruppiert nach Confidence-Bucket.

    Pendant zu :func:`_confidence_buckets` (Anzahl): summiert Wert/Gewicht je
    25-Prozent-Klasse plus 'ohne' (NULL Confidence). Beantwortet die
    Sammler-Frage "wieviel Wert/Masse haengt an Stuecken, denen die KI nicht
    vertraut (<50) vs. an sicheren Bestimmungen (75-100)?".

    Sortierung: absteigend nach Summe, Tiebreak nach
    :data:`CONFIDENCE_BUCKET_ORDER` (also 'ohne' vor '0-24' vor ...).
    Out-of-Range-Werte (<0 oder >100) zaehlen nicht; sie werden in
    :func:`check_integrity` separat gemeldet und wuerden hier nur Rauschen
    produzieren.
    """
    where = "1=1"
    if extra_where:
        where = extra_where
    bucket_sql = _confidence_bucket_case_sql()
    sql = (
        f"SELECT {bucket_sql} AS bucket, SUM({value_sql}) AS w "
        f"FROM objects WHERE {where} "
        f"GROUP BY bucket HAVING bucket IS NOT NULL AND w > 0"
    )
    rows = [(str(r["bucket"]), float(r["w"]))
            for r in conn.execute(sql).fetchall()]
    order_index = {b: i for i, b in enumerate(CONFIDENCE_BUCKET_ORDER)}
    rows.sort(key=lambda r: (-r[1], order_index.get(r[0], len(CONFIDENCE_BUCKET_ORDER))))
    return rows


def _confidence_buckets(conn: sqlite3.Connection) -> dict[str, int]:
    """Verteilung der Confidence-Werte auf 25-Prozent-Klassen + 'ohne' (NULL).

    Liefert ein Dict in fester Reihenfolge ``CONFIDENCE_BUCKET_ORDER``; Klassen
    ohne Treffer bleiben mit 0 enthalten, damit das Dashboard eine stabile
    Bar-Reihenfolge zeichnen kann. Out-of-Range-Werte (<0 oder >100) zaehlen
    nicht mit; sie werden separat in :func:`check_integrity` gemeldet.
    """
    counts = dict.fromkeys(CONFIDENCE_BUCKET_ORDER, 0)
    rows = conn.execute(
        f"SELECT {_confidence_bucket_case_sql()} AS bucket, COUNT(*) AS n "
        "FROM objects GROUP BY bucket"
    ).fetchall()
    for r in rows:
        b = r["bucket"]
        if b in counts:
            counts[b] = r["n"]
    return counts


def wert_pro_objekt_sql() -> str:
    """Per-Row-Summe der CHF-Wertfelder (für Sortierung/Aggregation/Filter)."""
    return "(" + " + ".join(f"COALESCE({c}, 0)" for c in WERT_FELDER) + ")"


def _sum_by(conn: sqlite3.Connection, group_col: str, value_sql: str,
            limit: int, extra_where: str = "") -> list[tuple[str, float]]:
    """Aggregiert ``SUM(value_sql)`` gruppiert nach ``group_col`` und liefert die
    Top-N absteigend nach Summe (Tiebreaker: Gruppenname aufsteigend).

    ``group_col`` darf nur ein Spaltenname sein (Whitelist-Validierung beim
    Aufrufer). ``extra_where`` ist optional und wird per AND angefuegt.
    """
    where = (f"{group_col} IS NOT NULL AND TRIM({group_col}) != ''")
    if extra_where:
        where = f"{where} AND {extra_where}"
    sql = (
        f"SELECT {group_col} AS k, SUM({value_sql}) AS w FROM objects "
        f"WHERE {where} "
        f"GROUP BY {group_col} HAVING w > 0 "
        f"ORDER BY w DESC, {group_col} ASC LIMIT ?"
    )
    return [(r["k"], float(r["w"])) for r in conn.execute(sql, (int(limit),)).fetchall()]


# Backwards-Kompatibilitaet: vorheriger Privatname.
_wert_pro_objekt_sql = wert_pro_objekt_sql


def _sum_by_funddatum_monat(conn: sqlite3.Connection, value_sql: str,
                            extra_where: str = "") -> list[tuple[str, float]]:
    """Aggregiert ``SUM(value_sql)`` gruppiert nach Funddatum-Monat (01..12).

    Pendant zu :func:`_sum_by_funddatum_jahr`, aggregiert ueber alle Jahre.
    Selektiert nur Eintraege mit gueltigem Monatsteil 01..12; reine Jahres-
    angaben ohne Monat fallen weg (siehe :func:`_count_funddatum_monat`).

    Top-N absteigend nach Summe; Tie-Break aufsteigend nach Monat. Ohne Limit,
    weil maximal 12 Monate vorkommen koennen - die Ausgabe wird nie laenger.
    """
    where = ("Funddatum IS NOT NULL AND TRIM(Funddatum) != '' "
             "AND substr(Funddatum, 1, 4) GLOB '[0-9][0-9][0-9][0-9]' "
             "AND substr(Funddatum, 6, 2) GLOB '[0-1][0-9]' "
             "AND CAST(substr(Funddatum, 6, 2) AS INTEGER) BETWEEN 1 AND 12")
    if extra_where:
        where = f"{where} AND {extra_where}"
    sql = (
        f"SELECT substr(Funddatum, 6, 2) AS k, SUM({value_sql}) AS w "
        f"FROM objects WHERE {where} "
        f"GROUP BY k HAVING w > 0 "
        f"ORDER BY w DESC, k ASC"
    )
    return [(r["k"], float(r["w"])) for r in conn.execute(sql).fetchall()]


def _sum_by_funddatum_jahrzehnt(conn: sqlite3.Connection, value_sql: str,
                                extra_where: str = "") -> list[tuple[str, float]]:
    """Aggregiert ``SUM(value_sql)`` gruppiert nach Funddatum-Jahrzehnt (Dekade).

    Pendant zu :func:`_count_funddatum_jahrzehnt` (Anzahl), aber summiert
    Wert/Gewicht je Dekaden-Bucket. Label folgt der Sammler-Konvention
    (``1980er``, ``1990er``, ...). Sortierung absteigend nach Summe; bei
    Gleichstand chronologisch aufsteigend. Ohne Limit, weil die Zahl der
    Dekaden (~10-15 ueber ein Sammlerleben) klein bleibt.
    """
    where = ("Funddatum IS NOT NULL AND TRIM(Funddatum) != '' "
             "AND substr(Funddatum, 1, 4) GLOB '[0-9][0-9][0-9][0-9]'")
    if extra_where:
        where = f"{where} AND {extra_where}"
    sql = (
        f"SELECT (CAST(substr(Funddatum, 1, 4) AS INTEGER) / 10) * 10 AS dekade, "
        f"       SUM({value_sql}) AS w FROM objects WHERE {where} "
        f"GROUP BY dekade HAVING w > 0 "
        f"ORDER BY w DESC, dekade ASC"
    )
    return [(f"{r['dekade']}er", float(r["w"])) for r in conn.execute(sql).fetchall()]


def _sum_by_erstellt_am_jahrzehnt(conn: sqlite3.Connection, value_sql: str,
                                  extra_where: str = "") -> list[tuple[str, float]]:
    """Aggregiert ``SUM(value_sql)`` gruppiert nach ``erstellt_am``-Jahrzehnt (Dekade).

    Spiegelt :func:`_sum_by_funddatum_jahrzehnt` auf die Erfassungs-Achse:
    nicht "in welcher Dekade habe ich am meisten gefunden", sondern "in welcher
    Dekade habe ich am meisten erfasst/digitalisiert". Komplementaer zu
    :func:`_count_erstellt_am_jahrzehnt` (Anzahl) und zu
    :func:`_sum_by_erstellt_am_jahr` (Einzeljahres-Aufloesung) - aggregiert das
    Erfassungs-Jahres-Histogramm wertlich/gewichtsmaessig auf 10er-Schritte
    und macht uebergreifende Erfassungs-Wellen (z.B. Excel-Migration in 2020+)
    sichtbar, die im Jahres-Histogramm durch Einzeljahr-Rauschen verdeckt
    werden. Label folgt der Sammler-Konvention (``2010er``, ``2020er`` ...).

    Wie bei :func:`_count_erstellt_am_jahrzehnt` zaehlen nur Eintraege mit
    vierstelligem Jahres-Praefix; kaputte Stempel und NULL/leer bleiben aussen
    vor. Sortierung absteigend nach Summe, Tie-Break chronologisch aufsteigend.
    Ohne Limit, weil die Zahl der Dekaden klein bleibt (~3-5 ueber eine
    Sammler-Karriere, analog zu :func:`_sum_by_funddatum_jahrzehnt`).
    """
    where = ("erstellt_am IS NOT NULL AND TRIM(erstellt_am) != '' "
             "AND substr(erstellt_am, 1, 4) GLOB '[0-9][0-9][0-9][0-9]'")
    if extra_where:
        where = f"{where} AND {extra_where}"
    sql = (
        f"SELECT (CAST(substr(erstellt_am, 1, 4) AS INTEGER) / 10) * 10 AS dekade, "
        f"       SUM({value_sql}) AS w FROM objects WHERE {where} "
        f"GROUP BY dekade HAVING w > 0 "
        f"ORDER BY w DESC, dekade ASC"
    )
    return [(f"{r['dekade']}er", float(r["w"])) for r in conn.execute(sql).fetchall()]


def _sum_by_geaendert_am_jahrzehnt(conn: sqlite3.Connection, value_sql: str,
                                   extra_where: str = "") -> list[tuple[str, float]]:
    """Aggregiert ``SUM(value_sql)`` gruppiert nach ``geaendert_am``-Jahrzehnt.

    Spiegelt :func:`_sum_by_erstellt_am_jahrzehnt` auf die Aenderungs-Achse:
    aggregiert das Pflege-Jahres-Histogramm
    (:func:`_sum_by_geaendert_am_jahr`) wertlich/gewichtsmaessig auf 10er-
    Schritte. Komplementaer zu :func:`_count_geaendert_am_jahrzehnt` (Anzahl):
    die Dekaden-Sicht macht uebergreifende Pflege-Wellen sichtbar, die im
    Einzeljahr-Histogramm durch Rauschen verdeckt sind - typisch eine
    Neu-Klassifizierungs-Welle ueber mehrere Jahre, in der Sammler nach
    einem groesseren mineralogischen Lehrgang die Altbestaende wert-
    technisch re-klassifizieren. Bei nie-aktualisierten Alt-Eintraegen
    konvergiert die Dekaden-Spitze auf die Erfassungs-Dekade; bei aktiv
    gepflegten Stuecken driftet sie in die aktuelle Pflege-Dekade.

    Wie bei :func:`_sum_by_erstellt_am_jahrzehnt` zaehlen nur Eintraege mit
    vierstelligem Jahres-Praefix; kaputte Stempel und NULL/leer bleiben
    aussen vor. Label folgt der Sammler-Konvention (``2020er``). Sortierung
    absteigend nach Summe, Tie-Break chronologisch aufsteigend. Ohne Limit,
    weil die Zahl der Dekaden klein bleibt (~3-5 ueber eine Sammler-
    Karriere, analog zu allen drei Zeit-Achsen-Dekaden-Helpern).
    """
    where = ("geaendert_am IS NOT NULL AND TRIM(geaendert_am) != '' "
             "AND substr(geaendert_am, 1, 4) GLOB '[0-9][0-9][0-9][0-9]'")
    if extra_where:
        where = f"{where} AND {extra_where}"
    sql = (
        f"SELECT (CAST(substr(geaendert_am, 1, 4) AS INTEGER) / 10) * 10 AS dekade, "
        f"       SUM({value_sql}) AS w FROM objects WHERE {where} "
        f"GROUP BY dekade HAVING w > 0 "
        f"ORDER BY w DESC, dekade ASC"
    )
    return [(f"{r['dekade']}er", float(r["w"])) for r in conn.execute(sql).fetchall()]


def _sum_by_erstellt_am_monat(conn: sqlite3.Connection, value_sql: str,
                              extra_where: str = "") -> list[tuple[str, float]]:
    """Aggregiert ``SUM(value_sql)`` gruppiert nach ``erstellt_am``-Monat (01..12).

    Spiegelt :func:`_sum_by_funddatum_monat` auf die Erfassungs-Achse: zeigt,
    in welchen Monaten ueber alle Jahre der hoechste Wert/das hoechste Gewicht
    erfasst wurde. Komplementaer zu :func:`_count_erstellt_am_monat` (Anzahl)
    und :func:`_sum_by_funddatum_monat` (Fund-Saison): die Erfassungs-Saison
    deckt sich oft nicht mit der Fund-Saison (Indoor-Erfassung im Winter
    aktuell schwerer/wertvoller als Sommer-Felderfassung).

    Akzeptiert nur Eintraege mit vierstelligem Jahres-Praefix und gueltigem
    Monatsteil 01..12 (defensive Behandlung historischer Imports mit kaputten
    Stempeln). Top-N absteigend nach Summe, Tie-Break aufsteigend nach Monat;
    ohne Limit, weil maximal 12 Eintraege moeglich.
    """
    where = ("erstellt_am IS NOT NULL AND TRIM(erstellt_am) != '' "
             "AND substr(erstellt_am, 1, 4) GLOB '[0-9][0-9][0-9][0-9]' "
             "AND substr(erstellt_am, 6, 2) GLOB '[0-1][0-9]' "
             "AND CAST(substr(erstellt_am, 6, 2) AS INTEGER) BETWEEN 1 AND 12")
    if extra_where:
        where = f"{where} AND {extra_where}"
    sql = (
        f"SELECT substr(erstellt_am, 6, 2) AS k, SUM({value_sql}) AS w "
        f"FROM objects WHERE {where} "
        f"GROUP BY k HAVING w > 0 "
        f"ORDER BY w DESC, k ASC"
    )
    return [(r["k"], float(r["w"])) for r in conn.execute(sql).fetchall()]


def _sum_by_erstellt_am_jahr(conn: sqlite3.Connection, value_sql: str,
                             limit: int,
                             extra_where: str = "") -> list[tuple[str, float]]:
    """Aggregiert ``SUM(value_sql)`` gruppiert nach ``erstellt_am``-Jahr.

    Spiegelt :func:`_sum_by_funddatum_jahr` auf die Erfassungs-Achse: nicht
    "wann wurde gefunden", sondern "wann wurde das Stueck digitalisiert".
    Komplementaer zu :func:`_count_erstellt_am_jahr` (Anzahl) und zu
    :func:`_sum_by_funddatum_jahr` (Wert/Gewicht je Fund-Jahr) - macht
    Erfassungs-Wellen wertlich/gewichtsmaessig sichtbar (z.B. eine grosse
    Migrations-Session, die viele wertvolle Altbestaende auf einmal in die
    DB schiebt).

    Wie bei :func:`_count_erstellt_am_jahr` zaehlen nur Eintraege mit
    vierstelligem Jahres-Praefix; kaputte Stempel und NULL/leer bleiben
    aussen vor. Top-N absteigend nach Summe, Tie-Break aufsteigend nach
    Jahr (analog zu :func:`_sum_by_funddatum_jahr`).
    """
    where = ("erstellt_am IS NOT NULL AND TRIM(erstellt_am) != '' "
             "AND substr(erstellt_am, 1, 4) GLOB '[0-9][0-9][0-9][0-9]'")
    if extra_where:
        where = f"{where} AND {extra_where}"
    sql = (
        f"SELECT substr(erstellt_am, 1, 4) AS k, SUM({value_sql}) AS w "
        f"FROM objects WHERE {where} "
        f"GROUP BY k HAVING w > 0 "
        f"ORDER BY w DESC, k ASC LIMIT ?"
    )
    return [(r["k"], float(r["w"])) for r in conn.execute(sql, (int(limit),)).fetchall()]


def _sum_by_geaendert_am_jahr(conn: sqlite3.Connection, value_sql: str,
                              limit: int,
                              extra_where: str = "") -> list[tuple[str, float]]:
    """Aggregiert ``SUM(value_sql)`` gruppiert nach ``geaendert_am``-Jahr.

    Spiegelt :func:`_sum_by_erstellt_am_jahr` auf die Aenderungs-Achse:
    nicht "wann wurde digitalisiert" (Erst-Erfassung), sondern "wann
    wurde zuletzt redaktionell angefasst". Komplementaer zu
    :func:`_count_geaendert_am_jahr` (Anzahl) und zu
    :func:`_sum_by_erstellt_am_jahr` (Wert/Gewicht je Erfassungs-Jahr) -
    macht Pflege-Wellen wertlich/gewichtsmaessig sichtbar (z.B. ein
    Neu-Klassifizierungs-Durchgang in einem Jahr, der eine Wert-Spitze
    fern vom urspruenglichen Erfassungs-Zeitpunkt erzeugt). Wert/Gewicht
    pro geaendert_am unterscheidet sich strukturell von Wert/Gewicht
    pro erstellt_am bei nie-aktualisierten Alt-Eintraegen, deren
    geaendert_am identisch zur erstellt_am bleibt (im _now()-Pfad
    identische Strings) - dort konvergieren die beiden Aggregate auf
    denselben Wert; bei nachgepflegten Stuecken driftet die Pflege-
    Spitze vom urspruenglichen Erfassungs-Jahr weg.

    Wie bei :func:`_sum_by_erstellt_am_jahr` zaehlen nur Eintraege mit
    vierstelligem Jahres-Praefix; kaputte Stempel und NULL/leer bleiben
    aussen vor. Top-N absteigend nach Summe, Tie-Break aufsteigend
    nach Jahr (analog zu allen drei Zeit-Achsen-Helpern).
    """
    where = ("geaendert_am IS NOT NULL AND TRIM(geaendert_am) != '' "
             "AND substr(geaendert_am, 1, 4) GLOB '[0-9][0-9][0-9][0-9]'")
    if extra_where:
        where = f"{where} AND {extra_where}"
    sql = (
        f"SELECT substr(geaendert_am, 1, 4) AS k, SUM({value_sql}) AS w "
        f"FROM objects WHERE {where} "
        f"GROUP BY k HAVING w > 0 "
        f"ORDER BY w DESC, k ASC LIMIT ?"
    )
    return [(r["k"], float(r["w"])) for r in conn.execute(sql, (int(limit),)).fetchall()]


def _sum_by_geaendert_am_monat(conn: sqlite3.Connection, value_sql: str,
                               extra_where: str = "") -> list[tuple[str, float]]:
    """Aggregiert ``SUM(value_sql)`` gruppiert nach ``geaendert_am``-Monat (01..12).

    Spiegelt :func:`_sum_by_erstellt_am_monat` auf die Aenderungs-Achse: zeigt,
    in welchen Monaten ueber alle Jahre der hoechste Pflege-Wert bzw. das
    hoechste Pflege-Gewicht zuletzt redaktionell beruehrt wurde. Komplementaer
    zu :func:`_count_geaendert_am_monat` (Anzahl) und :func:`_sum_by_erstellt_
    am_monat` (Erfassungs-Saison): bei nie-aktualisierten Alt-Eintraegen
    konvergiert die Aenderungs-Saison auf die Erfassungs-Saison (geaendert_am
    == erstellt_am im _now()-Pfad als identische Strings); bei aktiv
    nachgepflegten Stuecken driftet sie in das aktuelle Pflege-Monat ab und
    beziffert damit den wertlichen/gewichtmaessigen Schwerpunkt der letzten
    Datenpflege-Saisonalitaet.

    Akzeptiert nur Eintraege mit vierstelligem Jahres-Praefix und gueltigem
    Monatsteil 01..12 (defensive Behandlung historischer Imports mit kaputten
    Stempeln). Top-N absteigend nach Summe, Tie-Break aufsteigend nach Monat;
    ohne Limit, weil maximal 12 Eintraege moeglich.
    """
    where = ("geaendert_am IS NOT NULL AND TRIM(geaendert_am) != '' "
             "AND substr(geaendert_am, 1, 4) GLOB '[0-9][0-9][0-9][0-9]' "
             "AND substr(geaendert_am, 6, 2) GLOB '[0-1][0-9]' "
             "AND CAST(substr(geaendert_am, 6, 2) AS INTEGER) BETWEEN 1 AND 12")
    if extra_where:
        where = f"{where} AND {extra_where}"
    sql = (
        f"SELECT substr(geaendert_am, 6, 2) AS k, SUM({value_sql}) AS w "
        f"FROM objects WHERE {where} "
        f"GROUP BY k HAVING w > 0 "
        f"ORDER BY w DESC, k ASC"
    )
    return [(r["k"], float(r["w"])) for r in conn.execute(sql).fetchall()]


def _sum_by_funddatum_jahr(conn: sqlite3.Connection, value_sql: str,
                           limit: int,
                           extra_where: str = "") -> list[tuple[str, float]]:
    """Aggregiert ``SUM(value_sql)`` gruppiert nach Funddatum-Jahr.

    Pendant zu :func:`_sum_by` fuer Spalten, ergaenzt um den Substring-Trick fuer
    das Funddatum-Jahr. Selektiert nur Eintraege mit gueltigem Jahres-Praefix
    (vier Ziffern); andere Funddaten haben kein verlaessliches Jahr und wuerden
    die Aggregate verzerren (siehe :func:`_count_funddatum_jahr`).

    Top-N absteigend nach Summe; Tie-Break aufsteigend nach Jahr - damit das
    "bestes Sammeljahr"-Ranking stabil bleibt und gleichwertige Jahre
    chronologisch hintereinander stehen.
    """
    where = ("Funddatum IS NOT NULL AND TRIM(Funddatum) != '' "
             "AND substr(Funddatum, 1, 4) GLOB '[0-9][0-9][0-9][0-9]'")
    if extra_where:
        where = f"{where} AND {extra_where}"
    sql = (
        f"SELECT substr(Funddatum, 1, 4) AS k, SUM({value_sql}) AS w "
        f"FROM objects WHERE {where} "
        f"GROUP BY k HAVING w > 0 "
        f"ORDER BY w DESC, k ASC LIMIT ?"
    )
    return [(r["k"], float(r["w"])) for r in conn.execute(sql, (int(limit),)).fetchall()]


def compute_statistics(conn: sqlite3.Connection, top_fundorte: int = 10,
                       top_wert: int = 10, top_jahre: int | None = None,
                       top_wert_mineral: int = 10,
                       top_gewicht_mineral: int = 10,
                       top_wert_varietaet: int = 10,
                       top_gewicht_varietaet: int = 10,
                       top_wert_gesteinsart: int = 10,
                       top_gewicht_gesteinsart: int = 10,
                       top_wert_fundort: int = 10,
                       top_gewicht_fundort: int = 10,
                       top_wert_kategorie: int = 10,
                       top_gewicht_kategorie: int = 10,
                       top_wert_kristallsystem: int = 10,
                       top_gewicht_kristallsystem: int = 10,
                       top_wert_glanz: int = 10,
                       top_gewicht_glanz: int = 10,
                       top_wert_transparenz: int = 10,
                       top_gewicht_transparenz: int = 10,
                       top_wert_magnetismus: int = 10,
                       top_gewicht_magnetismus: int = 10,
                       top_wert_spaltbarkeit: int = 10,
                       top_gewicht_spaltbarkeit: int = 10,
                       top_wert_bruch: int = 10,
                       top_gewicht_bruch: int = 10,
                       top_wert_beste_verwendung: int = 10,
                       top_gewicht_beste_verwendung: int = 10,
                       top_gewicht: int = 10,
                       top_bilder: int = 10,
                       top_confidence: int = 10,
                       top_wert_funddatum_jahr: int = 10,
                       top_gewicht_funddatum_jahr: int = 10,
                       top_wert_erstellt_am_jahr: int = 10,
                       top_gewicht_erstellt_am_jahr: int = 10,
                       top_wert_geaendert_am_jahr: int = 10,
                       top_gewicht_geaendert_am_jahr: int = 10) -> Statistik:
    """Berechnet alle Kennzahlen in einer Sammlung von SQL-Aggregaten."""
    st = Statistik()
    st.objekte_total = conn.execute("SELECT COUNT(*) FROM objects").fetchone()[0]
    st.bilder_total = conn.execute("SELECT COUNT(*) FROM images").fetchone()[0]
    st.aliase_total = conn.execute("SELECT COUNT(*) FROM aliases").fetchone()[0]
    # Spiegelt objekte_mit_ki_analyse (zaehlt unique obj_id mit mindestens einem
    # Eintrag) - aliase_total ist die Summe aller Eintraege (eine Kanon-ID kann
    # mehrere Aliase haben), objekte_mit_alias die Anzahl verschmolzener Kanon-
    # Objekte (Provenienz-Sicht: "wie viele Stuecke sind tatsaechlich aus Duplikat-
    # Merges hervorgegangen?", unabhaengig von der Merge-Tiefe).
    st.objekte_mit_alias = conn.execute(
        "SELECT COUNT(DISTINCT canonical_id) FROM aliases"
    ).fetchone()[0]
    st.ki_analysen_total = conn.execute("SELECT COUNT(*) FROM ki_analysen").fetchone()[0]
    st.ki_analysen_uebernommen = conn.execute(
        "SELECT COUNT(*) FROM ki_analysen "
        "WHERE uebernommen_json IS NOT NULL AND TRIM(uebernommen_json) != ''"
    ).fetchone()[0]
    st.objekte_mit_ki_analyse = conn.execute(
        "SELECT COUNT(DISTINCT obj_id) FROM ki_analysen"
    ).fetchone()[0]
    # objekte_mit_ki_analyse_uebernommen: feinere Granularitaet als
    # objekte_mit_ki_analyse - zaehlt nur Objekte, in denen mindestens einer der
    # KI-Vorschlaege uebernommen wurde (uebernommen_json gesetzt). ki_analysen_
    # uebernommen ist die Summe aller uebernommenen Einzeleintraege (ein Objekt
    # kann mehrfach uebernommene Vorschlaege haben), hier die Anzahl der
    # tatsaechlich profitierenden Stuecke - "wie viele Objekte sind durch die
    # KI verbessert worden?" unabhaengig davon, wie oft die KI je Stueck lief.
    # Whitespace zaehlt wie leer, spiegelt has_ki_analyse_uebernommen.
    st.objekte_mit_ki_analyse_uebernommen = conn.execute(
        "SELECT COUNT(DISTINCT obj_id) FROM ki_analysen "
        "WHERE uebernommen_json IS NOT NULL AND TRIM(uebernommen_json) != ''"
    ).fetchone()[0]

    st.by_status = {
        r["status"]: r["n"]
        for r in conn.execute(
            "SELECT status, COUNT(*) AS n FROM objects GROUP BY status"
        ).fetchall()
    }
    st.objekte_aktiv = st.by_status.get("aktiv", 0)
    st.objekte_platzhalter = st.by_status.get("platzhalter", 0)
    st.objekte_archiviert = st.by_status.get("archiviert", 0)

    st.by_mineral = _count_by(conn, "Mineral_Primaer")
    # Varietaeten-Verteilung als feinere Sicht unter dem Hauptmineral: Quarz allein
    # sagt wenig - "Bergkristall", "Milchquarz", "Rauchquarz" trennt die Sammlung
    # auf der fuer Sammler interessanten Granularitaet. Ergaenzt by_mineral, das
    # auf der mineralogischen Hauptgruppe bleibt.
    st.by_varietaet = _count_by(conn, "Varietaet")
    # Petrologische Sicht: welche Gesteinsart traegt die Sammlung? Granit/Gneis/
    # Basalt/Sandstein gruppieren Stuecke nach geologischem Zusammenhang, der
    # weder durch Mineral_Primaer (mineralogisch) noch durch Kategorie (Form/
    # Aufbewahrung) abgedeckt ist. Ergaenzt by_varietaet (Mineral-Familie) um
    # die uebergeordnete Gesteins-Sicht.
    st.by_gesteinsart = _count_by(conn, "Gesteinsart")
    st.by_kategorie = _count_by(conn, "Kategorie")
    st.by_kristallsystem = _count_by(conn, "Kristallsystem")
    # Optische Sicht: welche Glanz-Charakteristik dominiert die Sammlung?
    # Glasiger Quarz vs. metallischer Pyrit vs. matter Sandstein trennt die
    # Sammlung auf einer Achse, die weder mineralogisch (by_mineral) noch
    # kristallographisch (by_kristallsystem) sichtbar ist. Sieben Enum-Werte
    # aus dem Feldwoerterbuch (glasig/wachsig/matt/metallisch/fettig/seidig/perlmutt).
    st.by_glanz = _count_by(conn, "Glanz")
    # Lichtdurchlaessigkeits-Sicht: wie transparent ist die Sammlung im Schnitt?
    # Komplementaer zu by_glanz (Oberflaechen-Reflexion vs. Volumen-Lichtgang):
    # durchsichtiger Bergkristall, durchscheinender Achat, opaker Pyrit liegen
    # optisch nebeneinander, brauchen aber unterschiedliches Licht-Setup beim
    # Fotografieren. Drei Enum-Werte (durchsichtig/durchscheinend/opak).
    st.by_transparenz = _count_by(conn, "Transparenz")
    # Magnetismus-Sicht: welcher Anteil der Sammlung reagiert auf den Magneten?
    # Drei Enum-Werte aus dem Feldwoerterbuch (ja/schwach/nein) - praktischer
    # Indikator fuer Magnetit/Pyrrhotin-Anteil (stark), Haematit/Ilmenit
    # (schwach) und alles uebrige (nein). Komplementaer zu by_mineral
    # (mineralogisch) und by_glanz (optisch): hier die physikalische
    # Eisengehalt-Achse, die mineralogisch quer durch alle Hauptgruppen geht.
    st.by_magnetismus = _count_by(conn, "Magnetismus")
    # Mineralogische Sicht: welche Spaltbarkeit dominiert die Sammlung?
    # Fuenf Enum-Werte aus dem Feldwoerterbuch (vollkommen/gut/deutlich/
    # undeutlich/keine) - klassische Lehrbuch-Sicht (Calcit/Fluorit/Glimmer:
    # vollkommen; Quarz: keine; Granat: deutlich). Komplementaer zu by_bruch
    # (Bruchverhalten) und by_glanz (Oberflaechen-Reflexion): hier die
    # Spaltflaechen-Charakteristik, die das Polieren/Praeparieren bestimmt.
    st.by_spaltbarkeit = _count_by(conn, "Spaltbarkeit")
    # Mineralogische Sicht: welches Bruchverhalten dominiert die Sammlung?
    # Sechs Enum-Werte aus dem Feldwoerterbuch (muschelig/uneben/splittrig/
    # faserig/erdig/glatt) - klassische Lehrbuch-Sicht (Quarz/Obsidian:
    # muschelig; Kupfer/Silber: hakig-uneben; Asbest: faserig). Komplementaer
    # zu by_spaltbarkeit (Spaltflaechen): Stuecke mit keiner Spaltbarkeit
    # zeigen ihr Bruchverhalten am deutlichsten - der Block macht das transparent.
    st.by_bruch = _count_by(conn, "Bruch")
    st.by_beste_verwendung = _count_by(conn, "Beste_Verwendung")
    st.by_fundort = _count_by(conn, "Fundort", limit=top_fundorte)
    # Diversitaets-Kennzahlen: Anzahl distinct, unabhaengig von Top-N-Limits.
    st.mineral_arten_total = _count_distinct(conn, "Mineral_Primaer")
    st.fundorte_total = _count_distinct(conn, "Fundort")
    # kategorien_total: Anzahl distinct dokumentierter Objekt-Kategorien
    # (Handstueck/Kristall/Duennschliff/...). Spiegelt mineral_arten_total
    # und fundorte_total auf die Inventar-Klassifizierungs-Achse und macht die
    # Diversitaets-Sicht "wie viele Kategorien pflege ich?" als eigene
    # Skalarkennzahl verfuegbar - Downstream-Konsumenten (Dashboards, JSON-
    # Export, XLSX-Bericht) muessen nicht ueber len(by_kategorie) abstrahieren
    # und behalten die Kennzahl konsistent, falls by_kategorie spaeter ein
    # Top-N-Limit bekommt (spiegelt die mineral_arten_total-Rolle: by_mineral
    # hat top_mineral=10-Default, mineral_arten_total dagegen die volle Zaehlung).
    # NULL und Whitespace-only werden ignoriert (spiegelt _count_distinct-
    # Konvention). Bei leerer DB / ohne jegliche Kategorie-Pflege bleibt 0
    # (dataclass-Default, spiegelt die uebrigen Diversitaets-Kennzahlen).
    st.kategorien_total = _count_distinct(conn, "Kategorie")
    # varietaeten_total: Anzahl distinct dokumentierter Mineral-Varietaeten
    # (Bergkristall/Amethyst/Rauchquarz/... innerhalb der Familie Quarz;
    # Malachit-Stalaktit als Habitus-Auspraegung innerhalb Malachit) als
    # Diversitaets-Zaehler auf der mineralogischen Sub-Klassifizierungs-
    # Achse. Spiegelt mineral_arten_total (Familien-Achse), fundorte_total
    # (geografische Achse) und kategorien_total (Inventar-Klassifizierungs-
    # Achse) und macht die Diversitaets-Sicht "wie viele Varietaeten pflege
    # ich?" als eigene Skalarkennzahl verfuegbar - Downstream-Konsumenten
    # (Dashboards, JSON-Export, XLSX-Bericht) muessen nicht ueber
    # len(by_varietaet) abstrahieren und behalten die Kennzahl konsistent,
    # falls by_varietaet spaeter ein Top-N-Limit bekommt (spiegelt die
    # mineral_arten_total-Rolle: by_mineral hat top_mineral=10-Default,
    # mineral_arten_total dagegen die volle Zaehlung).
    # NULL und Whitespace-only werden ignoriert (spiegelt _count_distinct-
    # Konvention und die has_varietaet-Filter-Konvention). Bei leerer DB /
    # ohne jegliche Varietaet-Pflege bleibt 0 (dataclass-Default, spiegelt
    # die uebrigen Diversitaets-Kennzahlen). Komplementaer zu
    # objekte_mit_varietaet (Coverage-Sicht: wie viele Stuecke ueberhaupt)
    # und quote_mit_varietaet_prozent (Coverage-Quote): hier die Streuung-
    # Sicht ueber die dokumentierten Auspraegungen.
    st.varietaeten_total = _count_distinct(conn, "Varietaet")
    # gesteinsarten_total: Anzahl distinct dokumentierter Gesteinsarten
    # (Granit / Gneis / Kalkstein / Sandstein / Basalt / ...) als
    # Diversitaets-Zaehler auf der petrologischen Klassifizierungs-Achse.
    # Vervollstaendigt das Diversitaets-Quintett mineral_arten_total /
    # fundorte_total / kategorien_total / varietaeten_total /
    # gesteinsarten_total - die fuenf zentralen "wie breit ist meine
    # Sammlung?"-Achsen liegen jetzt einheitlich als eigenstaendige
    # Skalarkennzahlen vor. Waehrend mineral_arten_total die mineralogische
    # Familien-Achse zaehlt ("welche Mineral-Familien?", Quarz/Calcit/Achat),
    # varietaeten_total die Sub-Klassifizierung darunter ("welche Auspraegung
    # in der Familie?", Bergkristall/Amethyst innerhalb Quarz), kategorien_total
    # die Inventar-Objekt-Typ-Achse ("welche Objekt-Typen?", Handstueck/
    # Kristall/Duennschliff) und fundorte_total die geografische Streuung
    # ("aus wie vielen Fundorten?"), deckt gesteinsarten_total die
    # petrologische Gesteins-Klassifizierungs-Achse ab ("in welchen
    # Gesteins-Einbettungen?", Granit als Wirt-Gestein fuer Quarz, Basalt
    # als Wirt-Gestein fuer Olivin/Zeolithe, Kalkstein als Wirt-Gestein
    # fuer Calcit-Adern). Die fuenf Diversitaets-Kennzahlen antworten auf
    # verschiedene Fragen und sind zueinander orthogonal: eine Sammlung mit
    # drei Quarz-Varietaeten aus einem einzigen Granit-Aufschluss hat
    # mineral_arten_total=1, varietaeten_total=3 und gesteinsarten_total=1.
    # Reuse-Pfad greift den bestehenden _count_distinct-Helper ab (spiegelt
    # mineral_arten_total / fundorte_total / kategorien_total /
    # varietaeten_total exakt: SELECT COUNT(DISTINCT ...) mit NULL- und
    # Whitespace-only-Filter), sodass jede Aenderung an der Distinct-
    # Konvention automatisch alle fuenf Diversitaets-Zaehler konsistent
    # haelt. Downstream-Konsumenten (Dashboards, JSON-Export, XLSX-Bericht)
    # muessen nicht ueber len(by_gesteinsart) abstrahieren und behalten die
    # Kennzahl konsistent, falls by_gesteinsart spaeter ein Top-N-Limit
    # bekommt (spiegelt die mineral_arten_total-Rolle: by_mineral hat
    # top_mineral=10-Default, mineral_arten_total dagegen die volle
    # Zaehlung). Komplementaer zu objekte_mit_gesteinsart (Coverage-Sicht:
    # wie viele Stuecke ueberhaupt) und quote_mit_gesteinsart_prozent
    # (Coverage-Quote): hier die Streuung-Sicht ueber die dokumentierten
    # Gesteinsarten. Bei leerer DB / ohne jegliche Gesteinsart-Pflege bleibt
    # 0 (dataclass-Default, spiegelt die uebrigen Diversitaets-Kennzahlen).
    st.gesteinsarten_total = _count_distinct(conn, "Gesteinsart")

    st.by_funddatum_jahr = _count_funddatum_jahr(conn, limit=top_jahre)
    st.by_funddatum_jahrzehnt = _count_funddatum_jahrzehnt(conn)
    st.by_funddatum_monat = _count_funddatum_monat(conn)
    # Sammlungswachstum-Histogramm: Objekte pro Jahr ihres erstellt_am-Stempels.
    # Komplementaer zu by_funddatum_jahr (wann gefunden) - hier wann erfasst.
    # Beantwortet "in welchen Jahren bin ich besonders aktiv im Digitalisieren gewesen?"
    # und macht ungleichmaessige Migrations-Wellen (z.B. eine grosse Erfassungs-
    # session 2026) sichtbar, die in der reinen Funddatums-Sicht untergehen.
    st.by_erstellt_am_jahr = _count_erstellt_am_jahr(conn)
    # Erfassungs-Dekaden-Histogramm: spiegelt by_funddatum_jahrzehnt um die
    # Erfassungs-Achse. Aggregiert das Erfassungs-Jahres-Histogramm auf 10er-
    # Schritte und macht so uebergreifende Erfassungs-Wellen sichtbar (alte
    # Excel-Migration in 2020+ vs. handgepflegte 2010er-Phase), die im Jahres-
    # Histogramm durch Einzeljahr-Rauschen verdeckt werden.
    st.by_erstellt_am_jahrzehnt = _count_erstellt_am_jahrzehnt(conn)
    # Erfassungs-Saisonalitaet (01..12, ueber alle Jahre): zeigt typische
    # Indoor-Phasen (Winter, Boersenvorbereitung) vs. Aussen-Pausen waehrend
    # der Feld-Saison. Spiegelt by_funddatum_monat um die Erfassungs-Achse.
    st.by_erstellt_am_monat = _count_erstellt_am_monat(conn)
    # Rarity-Histogramm: wie verteilt sich die Sammlung auf der globalen
    # Seltenheits-Skala (1=haeufig .. 10=sehr selten)? Komplementaer zu den
    # seltenheit_global_min/max-Filtern: zeigt nicht nur "ein Stueck ist hier
    # >=8", sondern wo das ganze Bestand-Schwerpunkt liegt. Sammler-typische
    # Diagnose vor Versicherungseinschaetzung (viel haeufiges Material vs.
    # konzentriert teure Rarit?ten).
    st.by_seltenheit_global = _count_scale_1_10(conn, "Seltenheit_global_1_10")
    # objekte_mit_seltenheit_global: Anzahl Objekte mit gueltigem globalen
    # Rarity-Score (1..10). Reuse der by_seltenheit_global-Buckets als Quelle,
    # damit Coverage- und Verteilungs-Sicht garantiert auf demselben Wertegrund
    # stehen: out-of-range-Werte (<1 / >10) sind in beiden ausgeschlossen, NULL
    # wird in keinem Bucket gezaehlt - spiegelt das objekte_mit_confidence-
    # Muster (Reuse von conf_werte mit BETWEEN 0 AND 100). Komplementaer zu
    # by_seltenheit_global (Verteilungs-Sicht ueber die 10 Skalen-Buckets),
    # wert_pro_seltenheit_global (Wert-Aufteilung je Bucket) und
    # gewicht_pro_seltenheit_global (Massen-Aufteilung je Bucket) - hier die
    # Coverage-Sicht ueber den Gesamtbestand.
    st.objekte_mit_seltenheit_global = sum(st.by_seltenheit_global.values())
    # Fundort-Rarity-Histogramm: am Standort selten vs. global selten - oft
    # verschieden, siehe SORTABLE_COLUMNS-Kommentar zu Seltenheit_Fundort. Ein
    # Stueck kann am Fundort haeufig (Quarz aus Berner Oberland) aber global
    # selten sein (oder umgekehrt: lokale Rarit?t aus einem ausgeschoepften
    # Stollen). Spiegelt by_seltenheit_global; nutzt denselben Helper und denselben
    # 1..10-Skala-Validator (out-of-range bleibt der Integrity ueberlassen).
    st.by_seltenheit_fundort = _count_scale_1_10(conn, "Seltenheit_Fundort_1_10")
    # objekte_mit_seltenheit_fundort: Anzahl Objekte mit gueltigem Standort-
    # Rarity-Score (1..10). Reuse der by_seltenheit_fundort-Buckets als Quelle,
    # damit Coverage- und Verteilungs-Sicht garantiert auf demselben Wertegrund
    # stehen - spiegelt das objekte_mit_seltenheit_global-Muster
    # (sum(by_seltenheit_global.values())). Out-of-range-Werte (<1 / >10) sind
    # in beiden ausgeschlossen (Integrity meldet separat), NULL wird in keinem
    # Bucket gezaehlt.
    st.objekte_mit_seltenheit_fundort = sum(st.by_seltenheit_fundort.values())
    # Marktnachfrage-Histogramm 1..10: wo liegt der Marktdruck-Schwerpunkt der
    # Sammlung? Komplementaer zum nachfrage_min/max-Filter (Drill-down auf
    # Verkaufs-Kandidaten); hier die Gesamtverteilung. Beantwortet Sammler-
    # typische Frage vor Boersenbesuch ("habe ich genug Stuecke mit Nachfrage>=7,
    # die sich verkaufen lassen, oder sitze ich auf reinem Tauschmaterial?").
    st.by_nachfrage = _count_scale_1_10(conn, "Nachfrage_1_10")
    # objekte_mit_nachfrage: Anzahl Objekte mit gueltigem Marktnachfrage-Score
    # (1..10). Reuse der by_nachfrage-Buckets als Quelle, damit Coverage- und
    # Verteilungs-Sicht garantiert auf demselben Wertegrund stehen - spiegelt
    # das objekte_mit_seltenheit_global-/objekte_mit_seltenheit_fundort-Muster
    # (sum(by_X.values())). Out-of-range-Werte (<1 / >10) sind in beiden
    # ausgeschlossen (Integrity meldet separat), NULL wird in keinem Bucket
    # gezaehlt. Schliesst die Coverage-Trias der drei 1..10-Markt-/Bewertungs-
    # Skalen aus dem Feldwoerterbuch ab (Seltenheit global / Seltenheit Fundort
    # / Nachfrage).
    st.objekte_mit_nachfrage = sum(st.by_nachfrage.values())
    st.funddatum_frueheste, st.funddatum_spaeteste = _funddatum_spanne(conn)
    # Erfassungs-Spanne: spiegelt funddatum_frueheste/spaeteste auf die
    # erstellt_am-Achse. Macht den Erfassungs-Zeitraum sichtbar (wann der
    # aelteste / neueste DB-Eintrag entstanden ist) und beantwortet "seit
    # wann digitalisiere ich diese Sammlung?". Voller Zeitstempel inkl.
    # HH:MM:SS bleibt erhalten, weil erstellt_am im Insert-Pfad mit Sekunden-
    # Aufloesung gesetzt wird (anders als Funddatum mit reiner Tag-Aufloesung).
    st.erstellt_am_frueheste, st.erstellt_am_spaeteste = _erstellt_am_spanne(conn)
    # Aenderungs-Spanne: vervollstaendigt das Trio der Zeit-Spannen (Fund /
    # Erfassung / Aenderung). Minimum verraet nie-aktualisierte Alt-Eintraege
    # bzw. das aelteste Bestand-Datum, Maximum nennt die letzte Datenpflege-
    # Aktivitaet ueber den gesamten Bestand. Voller Zeitstempel inkl. HH:MM:SS
    # bleibt erhalten, weil geaendert_am wie erstellt_am im repository._now()-
    # Pfad mit Sekunden-Aufloesung gesetzt wird.
    st.geaendert_am_frueheste, st.geaendert_am_spaeteste = _geaendert_am_spanne(conn)
    # Pflege-Aktivitaets-Histogramm pro Aenderungs-Jahr: spiegelt
    # by_erstellt_am_jahr (Sammlungswachstum: wann erfasst) auf die Aenderungs-
    # Achse (wann zuletzt redaktionell beruehrt). Beantwortet "in welchen Jahren
    # bin ich besonders aktiv im Pflegen gewesen?". Die Differenz beider
    # Histogramme zeigt nachtraegliche Pflege-Aktivitaet (KI-Analyse uebernommen,
    # Foto nachgereicht, Bestimmung korrigiert), die im reinen Erfassungs-
    # Wachstums-Bild untergeht.
    st.by_geaendert_am_jahr = _count_geaendert_am_jahr(conn)
    # Pflege-Dekaden-Histogramm: aggregiert das Pflege-Jahres-Histogramm auf
    # 10er-Schritte und macht uebergreifende Pflege-Wellen sichtbar (KI-Welle
    # 2024+ vs. handgepflegte 2010er-Phase), die im Einzel-Jahres-Histogramm
    # durch Jahres-Rauschen verdeckt werden. Spiegelt by_erstellt_am_jahrzehnt
    # auf die Aenderungs-Achse.
    st.by_geaendert_am_jahrzehnt = _count_geaendert_am_jahrzehnt(conn)
    # Pflege-Saisonalitaet (01..12, ueber alle Jahre): spiegelt
    # by_erstellt_am_monat auf die Aenderungs-Achse und schliesst die
    # Histogramm-Trias auf der Aenderungs-Achse ab (Jahr / Jahrzehnt / Monat),
    # parallel zur Fund- und Erfassungs-Achse. Zeigt typische Winter-Indoor-
    # Pflegephasen und Pflege-Wellen-Monate (KI-Analyse-Welle), waehrend die
    # Sommer-Feldsaison pflegearm bleibt. Die Differenz zur Erfassungs-
    # Saisonalitaet zeigt die nachtraegliche Pflege-Verschiebung pro Saison.
    st.by_geaendert_am_monat = _count_geaendert_am_monat(conn)

    st.bilder_by_kategorie = {
        r["kategorie"]: r["n"]
        for r in conn.execute(
            "SELECT kategorie, COUNT(*) AS n FROM images "
            "GROUP BY kategorie ORDER BY n DESC, kategorie ASC"
        ).fetchall()
    }

    st.objekte_mit_bildern = conn.execute(
        "SELECT COUNT(DISTINCT obj_id) FROM images"
    ).fetchone()[0]
    st.objekte_mit_funddatum = conn.execute(
        "SELECT COUNT(*) FROM objects "
        "WHERE Funddatum IS NOT NULL AND TRIM(Funddatum) != ''"
    ).fetchone()[0]
    # objekte_mit_kategorie: Anzahl Objekte mit dokumentierter Objekt-Kategorie
    # (Mineral-Korn/Handstueck/Duennschliff/Kristall/Geroell/Sonstiges).
    # Spiegelt objekte_mit_mineral/objekte_mit_fundort auf die Inventar-/ID-Gruppen-
    # Achse - Kategorie ist die erste Identifikations-Achse, sie sagt, was das
    # Stueck physisch ueberhaupt ist. Ohne Kategorie laesst sich das Stueck nur
    # mit der Objekt-ID adressieren; die Inventar-Sortierung (Vitrine fuer
    # Handstuecke, Schubladen fuer Mineral-Koerner, Mikroskop-Box fuer Duennschliffe)
    # wird unmoeglich. Niedriger Wert deutet auf einen Bestand vor der Inventar-
    # Vorklassifizierung oder Migrations-Restbestaende ohne Kategorie-Spalte in
    # den alten v1/obj043-CSVs. Whitespace zaehlt wie leer, spiegelt has_kategorie.
    # by_kategorie zaehlt distinkte Kategorien-Werte (Verteilung); diese Kennzahl
    # zaehlt Objekte mit irgendeiner Kategorie (Coverage) - komplementaer, beide
    # gemeinsam geben Auskunft ueber Vollstaendigkeit vs. Verteilung der Inventar-
    # Klassifizierung.
    st.objekte_mit_kategorie = conn.execute(
        "SELECT COUNT(*) FROM objects "
        "WHERE Kategorie IS NOT NULL AND TRIM(Kategorie) != ''"
    ).fetchone()[0]
    # objekte_mit_mineral: Anzahl Objekte mit dokumentiertem Mineral_Primaer
    # (Hauptmineral-Bestimmung). Spiegelt objekte_mit_funddatum auf die
    # mineralogische Identifikations-Achse - ohne Mineral_Primaer ist das
    # Stueck im Prinzip "noch nicht bestimmt" (entweder neu in der Sammlung
    # und noch nicht beurteilt, oder Migration-Restbestand aus alten CSVs
    # ohne Bestimmung). Eine fundamentalere Datenpflege-Kennzahl als
    # Wertschaetzung oder Gewicht, weil ohne Mineral_Primaer der ganze
    # mineralogische Block (Mohs/Dichte/Glanz/Bruch/Spaltbarkeit) im Datenblatt
    # ungenutzt bleibt. Whitespace zaehlt wie leer, spiegelt has_mineral.
    st.objekte_mit_mineral = conn.execute(
        "SELECT COUNT(*) FROM objects "
        "WHERE Mineral_Primaer IS NOT NULL AND TRIM(Mineral_Primaer) != ''"
    ).fetchone()[0]
    # objekte_mit_varietaet: Anzahl Objekte mit dokumentierter Varietaet (Sub-
    # Klassifizierung unter dem Hauptmineral). Spiegelt objekte_mit_mineral auf
    # die feinere Sub-Achse - Mineral_Primaer beantwortet "welche Mineral-Familie?"
    # (Quarz/Calcit/Pyrit), Varietaet "welche Auspraegung in der Familie?"
    # (Bergkristall/Milchquarz/Rauchquarz). Niedriger Wert ist normal - Varietaet
    # wird typisch erst nach der Familien-Bestimmung gepflegt, viele Stuecke
    # bleiben auf Mineral_Primaer stehen ohne weitere Sub-Klassifizierung.
    # Whitespace zaehlt wie leer, spiegelt has_varietaet. by_varietaet zaehlt
    # distinkte Varietaets-Werte (Streuung); diese Kennzahl zaehlt Objekte mit
    # irgendeiner Varietaet (Coverage) - komplementaer, beide gemeinsam geben
    # Auskunft ueber Vollstaendigkeit vs. Streuung der Sub-Klassifizierung.
    st.objekte_mit_varietaet = conn.execute(
        "SELECT COUNT(*) FROM objects "
        "WHERE Varietaet IS NOT NULL AND TRIM(Varietaet) != ''"
    ).fetchone()[0]
    # objekte_mit_gesteinsart: Anzahl Objekte mit dokumentierter Gesteinsart
    # (petrologische Einordnung). Spiegelt objekte_mit_mineral / objekte_mit_
    # varietaet auf die petrologische Achse - Mineral_Primaer beantwortet
    # "welche Mineral-Familie?" (Quarz/Calcit/Pyrit), Varietaet "welche
    # Auspraegung in der Familie?" (Bergkristall/Milchquarz), Gesteinsart
    # "in welcher Gesteins-Einbettung?" (Granit/Gneis/Basalt/Sandstein).
    # Niedriger Wert ist normal - Gesteinsart wird typisch erst nach Mineral-
    # Bestimmung gepflegt (wenn ueberhaupt), viele mineralogisch klare Stuecke
    # bleiben ohne petrologische Einordnung stehen (besonders bei Einzel-
    # Kristallen, fuer die die Gesteins-Einbettung beim Sammeln nicht
    # dokumentiert wurde). Whitespace zaehlt wie leer, spiegelt has_gesteinsart.
    # by_gesteinsart zaehlt distinkte Gesteinsarten-Werte (Streuung); diese
    # Kennzahl zaehlt Objekte mit irgendeiner Gesteinsart (Coverage) - komple-
    # mentaer, beide gemeinsam geben Auskunft ueber Vollstaendigkeit vs.
    # Streuung der petrologischen Einordnung.
    st.objekte_mit_gesteinsart = conn.execute(
        "SELECT COUNT(*) FROM objects "
        "WHERE Gesteinsart IS NOT NULL AND TRIM(Gesteinsart) != ''"
    ).fetchone()[0]
    # objekte_mit_kristallsystem: Anzahl Objekte mit dokumentiertem
    # Kristallsystem (kristallographische Symmetrie-Klassifizierung). Spiegelt
    # objekte_mit_mineral / objekte_mit_varietaet / objekte_mit_gesteinsart auf
    # die kristallographische Achse - Mineral_Primaer beantwortet "welche
    # Mineral-Familie?" (mineralogisch), Varietaet "welche Auspraegung in der
    # Familie?" (mineralogische Sub-Achse), Gesteinsart "in welcher Gesteins-
    # Einbettung?" (petrologische Achse), Kristallsystem "welcher Symmetrietyp?"
    # (kristallographische Achse, kubisch/tetragonal/hexagonal/trigonal/...).
    # Niedriger Wert ist normal - Kristallsystem wird typisch erst nach
    # Mineral_Primaer-Bestimmung gepflegt (deterministisch aus der Mineralart
    # ableitbar, aber haendisch zu uebernehmen), viele mineralogisch klare
    # Stuecke bleiben ohne Symmetrietyp-Einordnung stehen. Whitespace zaehlt
    # wie leer, spiegelt has_kristallsystem. by_kristallsystem zaehlt distinkte
    # Symmetrietyp-Werte (Streuung); diese Kennzahl zaehlt Objekte mit
    # irgendeinem Kristallsystem (Coverage) - komplementaer, beide gemeinsam
    # geben Auskunft ueber Vollstaendigkeit vs. Streuung der kristallographischen
    # Einordnung.
    st.objekte_mit_kristallsystem = conn.execute(
        "SELECT COUNT(*) FROM objects "
        "WHERE Kristallsystem IS NOT NULL AND TRIM(Kristallsystem) != ''"
    ).fetchone()[0]
    # objekte_mit_magnetismus: Anzahl Objekte mit dokumentiertem Magnetismus
    # (qualitative magnetische Reaktion: nein/schwach/ja, die drei Enum-Werte
    # aus dem Feldwoerterbuch). Spiegelt objekte_mit_kristallsystem auf die
    # magnetisch-physikalische Pruef-Achse: Kristallsystem klassifiziert die
    # innere Symmetrie, Magnetismus die qualitative Eisengehalts-Reaktion -
    # beide kurze Enum-Skalen unter den 43 Standardfeldern, beide bisher ohne
    # Coverage-Quote. Niedriger Wert ist normal - Sammler dokumentieren
    # haeufig nur die positiven Magnetismus-Treffer (Magnetit, Pyrrhotin) und
    # lassen offensichtlich-negative Mineralen (Quarz, Calcit, Pyrit) ohne
    # expliziten "nein"-Eintrag stehen. Whitespace zaehlt wie leer, spiegelt
    # has_magnetismus. by_magnetismus zaehlt distinkte Reaktions-Werte
    # (Streuung); diese Kennzahl zaehlt Objekte mit irgendeinem dokumentierten
    # Magnetismus-Wert (Coverage) - komplementaer, beide gemeinsam geben
    # Auskunft ueber Vollstaendigkeit vs. Streuung der magnetischen Pruefung.
    st.objekte_mit_magnetismus = conn.execute(
        "SELECT COUNT(*) FROM objects "
        "WHERE Magnetismus IS NOT NULL AND TRIM(Magnetismus) != ''"
    ).fetchone()[0]
    # objekte_mit_glanz: Anzahl Objekte mit dokumentiertem Glanz (optische
    # Oberflaechen-Reflexion: glasig/wachsig/matt/metallisch/fettig/seidig/
    # perlmutt, die sieben Enum-Werte aus dem Feldwoerterbuch). Spiegelt
    # objekte_mit_magnetismus / objekte_mit_kristallsystem auf die optische
    # Diagnose-Achse: Kristallsystem klassifiziert die innere Symmetrie,
    # Magnetismus die qualitative Eisengehalts-Reaktion, Glanz die qualitative
    # Oberflaechen-Reflexion - beide qualitative Pruefparameter ohne
    # instrumentelle Mess-Mittel (Magnet vs. blosses Auge unter normaler
    # Beleuchtung), beide kurze Enum-Skalen aus dem Feldwoerterbuch, beide
    # bisher ohne Coverage-Quote. Niedriger Wert ist normal - gerade weil
    # Glanz so offensichtlich beobachtbar ist, vergessen Sammler haeufig, ihn
    # explizit zu dokumentieren ("natuerlich ist Quarz glasig"). Whitespace
    # zaehlt wie leer, spiegelt has_glanz. by_glanz zaehlt distinkte
    # Reflexions-Werte (Streuung); diese Kennzahl zaehlt Objekte mit irgendeinem
    # dokumentierten Glanz-Wert (Coverage) - komplementaer, beide gemeinsam
    # geben Auskunft ueber Vollstaendigkeit vs. Streuung der optischen Pruefung.
    st.objekte_mit_glanz = conn.execute(
        "SELECT COUNT(*) FROM objects "
        "WHERE Glanz IS NOT NULL AND TRIM(Glanz) != ''"
    ).fetchone()[0]
    # objekte_mit_transparenz: Anzahl Objekte mit dokumentierter Transparenz
    # (qualitative Lichtdurchlaessigkeit: durchsichtig/durchscheinend/opak, die
    # drei Enum-Werte aus dem Feldwoerterbuch). Spiegelt objekte_mit_glanz auf
    # die optisch-physikalische Diagnose-Achse: Glanz klassifiziert die
    # qualitative Oberflaechen-Reflexion (Auflicht/Front-Beleuchtung pruefbar),
    # Transparenz die qualitative Lichtdurchlaessigkeit (Durchlicht/Gegenlicht
    # pruefbar) - beide qualitative Pruefparameter ohne instrumentelle Mess-
    # Mittel (blosses Auge unter Standard-Beleuchtung), beide kurze Enum-Skalen
    # aus dem Feldwoerterbuch, beide bisher ohne Coverage-Quote. Niedriger Wert
    # ist normal - gerade weil Transparenz so offensichtlich beobachtbar ist,
    # vergessen Sammler haeufig, sie explizit zu dokumentieren ("natuerlich ist
    # Quarz durchsichtig"). Whitespace zaehlt wie leer, spiegelt has_transparenz.
    # by_transparenz zaehlt distinkte Durchlaessigkeits-Werte (Streuung); diese
    # Kennzahl zaehlt Objekte mit irgendeinem dokumentierten Transparenz-Wert
    # (Coverage) - komplementaer, beide gemeinsam geben Auskunft ueber
    # Vollstaendigkeit vs. Streuung der optischen Pruefung.
    st.objekte_mit_transparenz = conn.execute(
        "SELECT COUNT(*) FROM objects "
        "WHERE Transparenz IS NOT NULL AND TRIM(Transparenz) != ''"
    ).fetchone()[0]
    # objekte_mit_spaltbarkeit: Anzahl Objekte mit dokumentierter Spaltbarkeit
    # (mechanisches Bruchverhalten entlang kristallographisch bevorzugter Ebenen:
    # vollkommen/gut/deutlich/undeutlich/keine - die fuenf Enum-Werte aus dem
    # Feldwoerterbuch). Spiegelt objekte_mit_glanz / objekte_mit_transparenz auf
    # die mechanisch-strukturelle Diagnose-Achse: waehrend Glanz und Transparenz
    # die optische Eigenschaft beschreiben, beschreibt Spaltbarkeit das
    # mechanische Bruchverhalten - ob das Mineral entlang bevorzugter Kristall-
    # ebenen spaltet (Glimmer: vollkommen blaettrig; Calcit/Halit: gut wuerfelig/
    # rhomboedrisch) oder unregelmaessig bricht (Quarz: keine Spaltbarkeit, nur
    # Bruch). Niedriger Wert ist typisch in Sammler-Bestaenden, weil der
    # Hammertest invasiv ist (man muss ein Stueck schlagen, um die Spaltflaechen
    # zu sehen) und daher seltener routinemaessig durchgefuehrt wird als
    # optische oder magnetische Pruefungen. Aus Datenpflege-Sicht ist die
    # Kombination Spaltbarkeit-vollkommen + Mohs-niedrig ein eindeutiger Marker
    # fuer Mineral-Klassen wie Glimmer/Calcit/Galenit - ohne Spaltbarkeits-
    # Eintrag fehlt diese Bestimmungs-Achse. Whitespace zaehlt wie leer,
    # spiegelt has_spaltbarkeit. by_spaltbarkeit zaehlt distinkte Spaltbarkeits-
    # Werte (Streuung); diese Kennzahl zaehlt Objekte mit irgendeinem
    # dokumentierten Spaltbarkeits-Wert (Coverage) - komplementaer, beide
    # gemeinsam geben Auskunft ueber Vollstaendigkeit vs. Streuung der
    # mechanischen Pruefung.
    st.objekte_mit_spaltbarkeit = conn.execute(
        "SELECT COUNT(*) FROM objects "
        "WHERE Spaltbarkeit IS NOT NULL AND TRIM(Spaltbarkeit) != ''"
    ).fetchone()[0]
    # objekte_mit_bruch: Anzahl Objekte mit dokumentiertem Bruch (ungeordnetes
    # mechanisches Versagen ausserhalb der Spaltebenen: muschelig/uneben/
    # splittrig/faserig/erdig/glatt - die sechs Enum-Werte aus dem
    # Feldwoerterbuch). Spiegelt objekte_mit_spaltbarkeit auf die paarweise
    # Bruchverhalten-Achse: waehrend Spaltbarkeit die geordnete Bruchrichtung
    # entlang kristallographisch bevorzugter Ebenen klassifiziert (Glimmer:
    # vollkommen blaettrig; Calcit/Halit: gut rhomboedrisch), klassifiziert
    # Bruch das ungeordnete Versagensmuster ausserhalb der Spaltebenen (Quarz:
    # muschelig wie Glasbruch; Pyrit: uneben; Asbest: faserig; Limonit: erdig;
    # Obsidian: glatt-muschelig). Schliesst die Coverage-Reihe der mechanisch-
    # strukturellen Diagnose-Doppel-Achse: Spaltbarkeit (geordnete Bruchrichtung)
    # -> Bruch (ungeordnetes Versagen). Niedriger Wert ist typisch in Sammler-
    # Bestaenden, weil der Hammertest invasiv ist (man muss ein Stueck schlagen,
    # um die Bruchflaeche zu sehen) und daher seltener routinemaessig durch-
    # gefuehrt wird als optische oder magnetische Pruefungen; spiegelt das
    # Pflege-Verhalten bei Spaltbarkeit. Aus Datenpflege-Sicht ist Bruch der
    # wichtigere Diagnose-Parameter bei spaltbarkeits-armen Mineralen (Quarz,
    # Opal, Obsidian, Chalcedon - alle mit muscheligem Bruch als Haupt-
    # Kennzeichen), waehrend Spaltbarkeit bei spaltungs-reichen Mineralen
    # (Glimmer, Calcit, Galenit) dominiert. Whitespace zaehlt wie leer,
    # spiegelt has_bruch. by_bruch zaehlt distinkte Bruch-Werte (Streuung);
    # diese Kennzahl zaehlt Objekte mit irgendeinem dokumentierten Bruch-Wert
    # (Coverage) - komplementaer, beide gemeinsam geben Auskunft ueber
    # Vollstaendigkeit vs. Streuung der mechanischen Pruefung.
    st.objekte_mit_bruch = conn.execute(
        "SELECT COUNT(*) FROM objects "
        "WHERE Bruch IS NOT NULL AND TRIM(Bruch) != ''"
    ).fetchone()[0]
    # objekte_mit_beste_verwendung: Anzahl Objekte mit dokumentierter Verwendungs-
    # Empfehlung (Schmuck/Sammlung/Forschung/Industrie/Talisman/Dekoration - die
    # sechs Enum-Werte aus dem Feldwoerterbuch). Schliesst die Coverage-Reihe
    # der strukturierten Enum-Achsen ab (Kategorie/Kristallsystem/Magnetismus/
    # Glanz/Transparenz/Spaltbarkeit/Bruch waren die uebrigen Enum-Felder).
    # Beste_Verwendung ist die einzige strukturierte Enum-Achse mit Empfehlungs-
    # Charakter (subjektive Sammler-Entscheidung ueber den weiteren Lebensweg
    # eines Stuecks), waehrend die uebrigen Enum-Achsen objektive Eigenschaften
    # am Stueck beschreiben (mineralogische Klasse, kristallographische Symmetrie,
    # optische/magnetische/mechanische Beobachtungen). Whitespace zaehlt wie
    # leer, spiegelt has_beste_verwendung. by_beste_verwendung zaehlt distinkte
    # Verwendungs-Werte (Streuung); diese Kennzahl zaehlt Objekte mit irgendeiner
    # Verwendungs-Empfehlung (Coverage) - komplementaer, beide gemeinsam geben
    # Auskunft ueber Vollstaendigkeit vs. Streuung der Verwendungs-Planung.
    # Niedriger Wert ist typisch in unsortierten Bestaenden (frisch importiert,
    # noch nicht durchgesehen) oder reinen Wissenschafts-Sammlungen (alle
    # Stuecke fuer Forschung, Empfehlung gar nicht zur Debatte).
    st.objekte_mit_beste_verwendung = conn.execute(
        "SELECT COUNT(*) FROM objects "
        "WHERE Beste_Verwendung IS NOT NULL AND TRIM(Beste_Verwendung) != ''"
    ).fetchone()[0]
    # objekte_mit_fundort: Anzahl Objekte mit dokumentiertem Fundort (geografische
    # Provenienz). Spiegelt objekte_mit_funddatum/objekte_mit_mineral auf die
    # Provenienz-Achse - "wo wurde das Stueck gefunden" ist symmetrisch zu
    # "wann" und "was" eine der drei Kern-Identifikations-Achsen jedes Sammlungs-
    # stuecks (Provenienz, Datierung, Bestimmung). Ohne Fundort fehlt der
    # geografische Kontext fuer Sammlungs-Recherche (welche Stuecke vom selben
    # Aufschluss?), Versicherungs-/Erbschafts-Wert (Provenienz-Nachweis) und
    # wissenschaftliche Verwertung (Vergleichs-Material mit dokumentierter
    # Herkunft). Whitespace zaehlt wie leer, spiegelt has_fundort. fundorte_total
    # zaehlt distinkte Fundorte (Diversitaet); diese Kennzahl zaehlt Objekte
    # mit irgendeinem Fundort (Coverage) - komplementaer, beide gemeinsam
    # geben Auskunft ueber Konzentration vs. Streuung der Sammlung.
    st.objekte_mit_fundort = conn.execute(
        "SELECT COUNT(*) FROM objects "
        "WHERE Fundort IS NOT NULL AND TRIM(Fundort) != ''"
    ).fetchone()[0]
    # objekte_mit_koordinaten: geocoded-Subset von objekte_mit_fundort - Anzahl
    # Objekte, deren freitext-Fundort ein per parse_coordinates erkennbares
    # Lat/Lon-Paar enthaelt (Dezimal mit/ohne Hemisphaere, DMS, ISO 6709). Die
    # Differenz zu objekte_mit_fundort beziffert den freitext-only-Anteil
    # ("Berner Oberland", "alte Halde bei X") und damit den verbleibenden
    # Pflege-Aufwand fuer eine vollstaendige Geocoding-Ergaenzung. Spiegelt
    # die repository-Bounding-Box-Achse list_objects_in_bbox auf die Coverage-
    # Sicht ("wie viel meiner Sammlung ist ueberhaupt fuer geografische Filter
    # erreichbar?"). Python-Schicht ueber Fundort, weil parse_coordinates eine
    # Python-Funktion mit Regex-Branching ohne SQL-Aequivalent ist; bei
    # Sammler-DBs mit O(10^3) Eintraegen bleibt der Pfad unter Sekundenzeit
    # (parallel zur Laufzeit-Annahme bei list_objects_in_bbox). Whitespace und
    # nicht-parsebare Eintraege zaehlen wie nicht-geocoded (spiegelt das
    # None-Verhalten von parse_coordinates).
    from stonebook.migration.validators import parse_coordinates
    fundort_rows = conn.execute(
        "SELECT Fundort FROM objects "
        "WHERE Fundort IS NOT NULL AND TRIM(Fundort) != ''"
    ).fetchall()
    geocoded_coords: list[tuple[float, float]] = []
    for r in fundort_rows:
        coords = parse_coordinates(r["Fundort"])
        if coords is not None:
            geocoded_coords.append(coords)
    st.objekte_mit_koordinaten = len(geocoded_coords)
    # koordinaten_bbox: geografische Bounding-Box (lat_min, lat_max, lon_min,
    # lon_max) ueber alle per parse_coordinates erkannten Fundort-Eintraege -
    # spiegelt list_objects_in_bbox auf die Aggregations-Sicht: waehrend die
    # repository-Sicht die Objekte zu einer vom Caller vorgegebenen Box auflistet
    # ("welche Stuecke liegen in dieser Box?"), liefert die Aggregations-Sicht
    # die minimal-umschliessende Box der Sammlung selbst ("wie weit reicht meine
    # Sammlung geografisch?"). Beantwortet die natuerliche Vorfrage zur
    # list_objects_in_bbox-Achse: ohne diese Extent-Achse muss der Caller die
    # Box-Grenzen blind raten (Schweiz-typisch lat 45..48, lon 5..11 - was bei
    # einer rein lokalen Bergketten-Sammlung viel zu weit ist und bei einer
    # globalen Boersen-Sammlung viel zu eng). Reuse-Pfad teilt die fundort_rows-
    # Iteration mit objekte_mit_koordinaten exakt (eine einzige parse_coordinates-
    # Runde ueber den gesamten Bestand, kein zweiter Pass). Inverted-Box-Konvention
    # spiegelt list_objects_in_bbox (BETWEEN-inklusiv, lat_min <= lat <= lat_max,
    # lon_min <= lon <= lon_max) - alle vier Grenzen sind tatsaechliche Werte aus
    # der Sammlung, daher gilt lat_min <= lat_max und lon_min <= lon_max trivial.
    # Bei genau einem geocoded-Stueck kollabieren beide Grenzen zur Punkt-Box
    # (lat_min == lat_max == lat_einzig, lon_min == lon_max == lon_einzig) - das
    # ist konsistent zur list_objects_in_bbox-Konvention und liefert eine
    # gueltige (wenn auch entartete) Box. Bei null geocoded-Stuecken bleibt die
    # Box None (kein Wertegrund fuer eine Min/Max-Definition - spiegelt die
    # funddatum_frueheste/spaeteste-Konvention, die bei leerer Spalte ebenfalls
    # None statt 0 bzw. einer Sentinel-Box zurueckgibt). Datums-Grenze
    # (lon ueber +/-180 hinweg) wird nicht behandelt - eine Sammlung, die
    # die +/-180-Linie ueberspannt (z.B. Pazifik-Inselgruppen) erzeugt eine
    # ganz-Welt-umfassende Box statt der korrekten Schmalband-Box, parallel
    # zur entsprechenden list_objects_in_bbox-Einschraenkung (in der Praxis
    # fuer Sammler-Daten irrelevant).
    if geocoded_coords:
        lats = [lat for lat, _ in geocoded_coords]
        lons = [lon for _, lon in geocoded_coords]
        st.koordinaten_bbox = (min(lats), max(lats), min(lons), max(lons))
        # koordinaten_zentrum: arithmetisches Mittel von Lat und Lon ueber alle
        # geocoded Fundort-Eintraege - geometrische Schwerpunkts-Achse zur
        # Extent-Achse koordinaten_bbox: waehrend die Box die aeusseren Grenzen
        # der Sammlung beziffert, gibt das Zentrum den Schwerpunkt an. Beide
        # Achsen gemeinsam beschreiben die Sammlung geografisch vollstaendig
        # (wo liegt sie, wie weit reicht sie) und ergaenzen sich symmetrisch.
        # Beantwortet die natuerliche Vorfrage zur list_objects_nearest-Sicht:
        # waehrend list_objects_nearest die N nahesten Stuecke zu einem
        # vom Caller vorgegebenen Mittelpunkt liefert, ist das Zentrum die
        # natuerliche Default-Wahl fuer den Mittelpunkt selbst ("welche
        # Stuecke liegen meinem Sammlungs-Schwerpunkt am naechsten?" als
        # natuerliche Start-Sicht bei der Bestand-Erkundung). Reuse-Pfad
        # spiegelt die Bounding-Box-Berechnung exakt - dieselbe lats/lons-
        # Liste wird einmal fuer min/max (Box) und einmal fuer den Mittelwert
        # (Zentrum) verwendet, kein zweiter Pass und kein zweiter
        # parse_coordinates-Aufruf. Konvention: arithmetisches Mittel ohne
        # Gewichtung nach Wert/Gewicht/Anzahl-Bildern - jedes geocoded-Stueck
        # zaehlt gleich, spiegelt die Bounding-Box-Konvention (Min/Max
        # ueber alle Stuecke, kein wert-gewichteter Schwerpunkt). Bei genau
        # einem geocoded-Stueck kollabiert das Zentrum auf das Stueck selbst
        # (lat_zentrum == lat_einzig, lon_zentrum == lon_einzig); bei null
        # geocoded-Stuecken bleibt das Zentrum None - spiegelt die
        # koordinaten_bbox-Konvention exakt. Datums-Grenze (lon ueber +/-180
        # hinweg) wird nicht behandelt - ein arithmetisches Mittel ueber die
        # +/-180-Linie hinweg liefert ein nicht-geodaetisches Antipoden-Mittel
        # (z.B. lon -179 + lon +179 mittelt auf 0 statt richtigerweise +/-180),
        # parallel zur entsprechenden Box-Einschraenkung (in der Praxis fuer
        # Sammler-Daten irrelevant).
        n = len(geocoded_coords)
        st.koordinaten_zentrum = (sum(lats) / n, sum(lons) / n)
        # koordinaten_radius_max_km: maximale geodaetische Distanz vom Zentrum
        # zu einem geocoded Stueck - Streuungs-Achse zum Extent (koordinaten_bbox)
        # und Centroid (koordinaten_zentrum). Waehrend die Box die rechteckige
        # Aussengrenze beziffert (achsenparallel in Lat/Lon, in der Naehe der
        # Pole stark verzerrt) und das Zentrum den Schwerpunkt angibt, beziffert
        # der Radius die maximale geodaetische Ausdehnung der Sammlung vom
        # Schwerpunkt aus - die Sphaeren-distanz statt der Lat/Lon-Spanne.
        # Beantwortet die natuerliche Vorfrage zur list_objects_in_radius-
        # Sicht: waehrend list_objects_in_radius die Stuecke in einer vom
        # Caller vorgegebenen Disk auflistet, ist die Disk um (zentrum,
        # radius_max_km) die natuerliche "alles dabei"-Disk - der kleinste
        # Radius um den Schwerpunkt, der die gesamte Sammlung umfasst (ohne
        # dass der Caller die Disk-Groesse blind raten muss). Reuse-Pfad
        # teilt geocoded_coords und das berechnete Zentrum exakt - dieselbe
        # Liste, dieselbe Haversine-Formel (Erd-Sphaere mit Radius 6371.0 km)
        # wie in repository.list_objects_in_radius/_nearest, ein einziger
        # Pass ueber die Koordinaten ohne erneutes parse_coordinates. Bei
        # genau einem geocoded-Stueck kollabiert das Zentrum auf das Stueck
        # selbst und der Radius auf 0.0 (Distanz vom Punkt zu sich selbst) -
        # konsistent zur Punkt-Box-Konvention (lat_min == lat_max) und zur
        # Definition des max-Operators ueber einen einzelnen Wert. Bei null
        # geocoded-Stuecken bleibt der Radius None (kein Wertegrund fuer eine
        # max-Distanz) - spiegelt die koordinaten_bbox/_zentrum-Konvention.
        # as_dict serialisiert mit 3 Nachkommastellen (~1 m Aufloesung in km,
        # ausreichend fuer Sammler-Distanzen, vermeidet float-Rauschen jenseits
        # der parse_coordinates-Eingabe-Genauigkeit).
        # koordinaten_radius_durchschnitt_km: arithmetisches Mittel der
        # Haversine-Distanzen vom Zentrum zu jedem geocoded Stueck - robuste
        # "typische Streuung"-Achse zur ausreisser-dominierten Max-Achse
        # koordinaten_radius_max_km. Waehrend Max die aeusserste Reichweite
        # beziffert (ein einziger Ausreisser-Fund irgendwo in Skandinavien
        # zieht den Max-Radius einer sonst rein lokalen Schweizer Sammlung
        # auf 1500 km hoch, ohne dass das typische Sammlungs-Bild widergespiegelt
        # wird), gibt der Durchschnitt die typische Distanz pro Stueck zum
        # Schwerpunkt an - die robustere "wie weit liegt das durchschnittliche
        # Stueck vom Zentrum?"-Achse, die wenig anfaellig auf einzelne weit
        # entfernte Stuecke ist. Die Differenz beider (Max - Durchschnitt)
        # beziffert die Ausreisser-Schiefe: bei symmetrisch um den Schwerpunkt
        # verteilten Stuecken liegt der Durchschnitt nahe Max/2 (gleichmaessige
        # Streuung), bei stark ausreisser-dominierten Sammlungen liegt der
        # Durchschnitt deutlich unter Max/2 (die meisten Stuecke konzentrieren
        # sich nahe dem Schwerpunkt, einzelne weit entfernte ziehen den Max-
        # Wert hoch). Spiegelt das wert_durchschnitt_chf / wert_max_chf-Paar
        # und das gewicht_durchschnitt_g / gewicht_max_g-Paar auf die
        # geografische Streuungs-Achse: Mittel + Max = paarweise Aggregations-
        # Sicht (typisch vs. extrem) ueber dieselbe Wert-/Streuungs-Verteilung.
        # Reuse-Pfad teilt die einmalige Haversine-Schleife mit dem Max-Pfad:
        # wir summieren die Distanzen waehrend wir das Max suchen (ein einziger
        # Pass ueber geocoded_coords, kein zweiter Pass und kein zweiter
        # parse_coordinates-Aufruf). Bei genau einem geocoded-Stueck kollabieren
        # Max und Durchschnitt beide auf 0.0 (Distanz vom Punkt zu sich selbst),
        # konsistent zur Max-Konvention und zur Definition des arithmetischen
        # Mittels ueber einen einzelnen Wert. Bei null geocoded-Stuecken bleibt
        # der Durchschnitt None (kein Wertegrund fuer einen Mittelwert) -
        # spiegelt die koordinaten_radius_max_km/zentrum/bbox-Konvention.
        # as_dict serialisiert auf 3 Nachkommastellen (~1 m Aufloesung in km,
        # spiegelt die Max-Serialisierung).
        # koordinaten_radius_median_km: Median der Haversine-Distanzen vom
        # Zentrum zu jedem geocoded Stueck - die ausreisser-robusteste
        # Streuungs-Achse zur durchschnittlichen Achse koordinaten_radius_
        # durchschnitt_km und zur extremen Achse koordinaten_radius_max_km.
        # Vervollstaendigt das Aggregations-Trio Max + Mittel + Median auf
        # der geografischen Streuungs-Achse, spiegelt das wert_max_chf /
        # wert_durchschnitt_chf / wert_median_chf-Trio und das
        # gewicht_max_g / gewicht_durchschnitt_g / gewicht_median_g-Trio
        # exakt: extrem (Max) + typisch-aber-ausreisser-anfaellig (Mittel)
        # + robust-typisch (Median) ueber dieselbe Verteilung. Der Median
        # ist die einzige der drei Achsen, die gegen einen einzigen weit
        # entfernten Ausreisser vollstaendig unempfindlich ist (Mittel
        # folgt dem Ausreisser anteilig, Median ueberhaupt nicht); fuer
        # eine Sammlung mit 9 Stuecken in Bern und 1 in Oslo ist der
        # Median schlicht der mittlere Bern-Bern-Abstand, der Mittel-
        # Wert haengt jedoch direkt an der Oslo-Distanz. Reuse-Pfad
        # teilt die einmalige Haversine-Schleife mit Max und Mittel:
        # wir sammeln die Distanzen einmalig in eine Liste und leiten
        # alle drei Achsen daraus ab (Max via builtins.max, Mittel via
        # sum/len, Median via Sort und Mittel-Index). Bei genau einem
        # geocoded-Stueck kollabieren alle drei auf 0.0 (Distanz vom
        # Punkt zu sich selbst). Bei null geocoded-Stuecken bleibt der
        # Median None - spiegelt die Max/Mittel-Konvention. Bei gerader
        # Anzahl wird der Mittelwert der beiden mittleren Elemente
        # genommen (klassische Median-Definition), spiegelt wert_median_
        # chf / gewicht_median_g exakt. as_dict serialisiert auf 3 Nach-
        # kommastellen (~1 m Aufloesung in km, spiegelt Max/Mittel).
        import math as _math
        lat_c, lon_c = st.koordinaten_zentrum
        lat_c_rad = _math.radians(lat_c)
        lon_c_rad = _math.radians(lon_c)
        earth_radius_km = 6371.0
        distances: list[float] = []
        for lat, lon in geocoded_coords:
            lat_rad = _math.radians(lat)
            lon_rad = _math.radians(lon)
            dlat = lat_rad - lat_c_rad
            dlon = lon_rad - lon_c_rad
            a = (_math.sin(dlat / 2) ** 2
                 + _math.cos(lat_c_rad) * _math.cos(lat_rad) * _math.sin(dlon / 2) ** 2)
            distances.append(
                2 * earth_radius_km * _math.asin(min(1.0, _math.sqrt(a))))
        st.koordinaten_radius_max_km = max(distances)
        st.koordinaten_radius_durchschnitt_km = sum(distances) / len(distances)
        distances.sort()
        n = len(distances)
        st.koordinaten_radius_median_km = (
            distances[n // 2] if n % 2
            else (distances[n // 2 - 1] + distances[n // 2]) / 2)
        # koordinaten_diameter_km: maximaler paarweise geodaetischer Abstand
        # zwischen je zwei geocoded Fundort-Eintraegen - die geografische
        # Sammlungs-Ausdehnung als Punkt-Paar-Achse zur Schwerpunkt-Achse
        # koordinaten_radius_max_km. Waehrend radius_max die Distanz vom
        # Zentroid zum entferntesten Stueck beziffert (Schwerpunkts-Sicht),
        # gibt der Durchmesser die echte Sammlungs-Spannweite zwischen den
        # beiden am weitesten voneinander entfernten Stuecken an
        # (Punkt-Paar-Sicht). Geometrisch gilt immer
        # radius_max <= diameter <= 2*radius_max: die untere Grenze wird
        # erreicht, wenn ein Stueck genau am Zentroid liegt und der
        # entfernteste Punkt das andere Ende des Durchmessers bildet
        # (Singleton-/Punkt-am-Zentroid-Sammlung), die obere wenn die
        # zwei aeussersten Stuecke diametral um den Zentroid liegen (rein
        # bipolare Sammlung). Die Differenz zwischen Durchmesser und 2*Radius
        # beziffert die Schwerpunkts-Schiefe: bei symmetrischer Verteilung
        # um den Zentroid liegt der Durchmesser nahe 2*Radius, bei einseitig
        # geclusterten Sammlungen mit Einzel-Ausreisser liegt er deutlich
        # darunter (der Zentroid wird zum Ausreisser gezogen, sodass radius_max
        # gross wird, aber die Bern-zu-Bern-Distanzen klein bleiben). Reuse-Pfad
        # nutzt die bereits berechneten geocoded_coords-Liste (keine zweite
        # parse_coordinates-Runde) und dieselbe Haversine-Formel auf einer
        # Erd-Sphaere mit Radius 6371.0 km wie radius_max / repository.
        # list_objects_in_radius/_nearest. Die Komplexitaet ist O(n^2) ueber
        # die Paar-Iteration (n*(n-1)/2 Paare); fuer Sammler-DBs mit O(10^3)
        # Eintraegen bleibt das unter Sekundenzeit. Bei genau einem geocoded-
        # Stueck kollabiert der Durchmesser auf 0.0 (kein Paar, der Punkt zu
        # sich selbst hat Distanz 0) - konsistent zur radius_max/durchschnitt/
        # median-Konvention bei n=1. Bei null geocoded-Stuecken bleibt der
        # Durchmesser None - spiegelt die uebrigen koordinaten_*-Konventionen.
        # as_dict serialisiert auf 3 Nachkommastellen (~1 m Aufloesung in km,
        # spiegelt die radius_max/durchschnitt/median-Serialisierung).
        max_pair_km = 0.0
        precomputed = [
            (_math.radians(lat), _math.radians(lon))
            for lat, lon in geocoded_coords
        ]
        for i in range(n):
            lat_i, lon_i = precomputed[i]
            cos_lat_i = _math.cos(lat_i)
            for j in range(i + 1, n):
                lat_j, lon_j = precomputed[j]
                dlat = lat_j - lat_i
                dlon = lon_j - lon_i
                a = (_math.sin(dlat / 2) ** 2
                     + cos_lat_i * _math.cos(lat_j) * _math.sin(dlon / 2) ** 2)
                d_km = 2 * earth_radius_km * _math.asin(min(1.0, _math.sqrt(a)))
                if d_km > max_pair_km:
                    max_pair_km = d_km
        st.koordinaten_diameter_km = max_pair_km
    # objekte_mit_farbe: Anzahl Objekte mit dokumentierter Farbe_beobachtet
    # (tatsaechlich gesehene Mineral-Farbe, die niederschwelligste visuelle
    # Diagnose-Achse - keine Werkzeuge noetig, am Tageslicht beobachtbar).
    # Spiegelt die umliegenden Coverage-Zaehler der visuellen Pruef-Achsen
    # (objekte_mit_glanz / objekte_mit_transparenz - Enum-Skalen fuer Ober-
    # flaechen-Reflexion und Lichtdurchlaessigkeit) auf die freie str-Farb-
    # Achse mit unbeschraenktem Wertebereich ("gelblich-weiss", "rotbraun mit
    # schwarzen Adern", "milchig-blau", ...). Komplementaer zu
    # objekte_mit_strichfarbe (Pulverfarbe nach Strichplaetten-Test): beide
    # Farb-Achsen zusammen ergeben das vollstaendige Farb-Profil. Whitespace
    # zaehlt wie leer, spiegelt die has_farbe-Filter-Konvention der
    # repository.filter_objects-API und die has_X-Konvention der umliegenden
    # freien str-Spalten (Fundort/Strichfarbe/Notizen).
    st.objekte_mit_farbe = conn.execute(
        "SELECT COUNT(*) FROM objects "
        "WHERE Farbe_beobachtet IS NOT NULL AND TRIM(Farbe_beobachtet) != ''"
    ).fetchone()[0]
    # objekte_mit_strichfarbe: Anzahl Objekte mit dokumentierter Strichfarbe
    # (Farbe des Mineral-Pulvers auf der Porzellan-Strichplaette - einer der
    # drei klassischen qualitativen Bestimmungs-Pruefparameter aus dem
    # Feldwoerterbuch neben Magnetismus und HCl-Reaktion). Spiegelt die
    # umliegenden Coverage-Zaehler (objekte_mit_magnetismus / objekte_mit_glanz
    # / objekte_mit_transparenz) auf die einzige freie str-Pruef-Achse mit
    # konventionsfest unbeschraenktem Wertebereich (Magnetismus ist Enum,
    # Glanz/Transparenz/Spaltbarkeit/Bruch sind Enum; Strichfarbe akzeptiert
    # jede Farbbeschreibung - "gelblich-weiss", "schwarz", "ziegelrot",
    # "gruenlich-schwarz"). Whitespace zaehlt wie leer, spiegelt die has_
    # notizen / has_fundort-Filter-Konvention (freie str-Spalten werden
    # symmetrisch behandelt). Niedriger Wert ist typisch, weil der Strichtest
    # invasiv ist (das Mineral wird abgerieben) und eine Porzellan-Strichplaette
    # erfordert - Sammler dokumentieren ihn typisch erst nach erster Mineral-
    # Hypothese als Bestaetigung, nicht routinemaessig fuer jedes Stueck.
    st.objekte_mit_strichfarbe = conn.execute(
        "SELECT COUNT(*) FROM objects "
        "WHERE Strichfarbe IS NOT NULL AND TRIM(Strichfarbe) != ''"
    ).fetchone()[0]
    # objekte_mit_hcl_reaktion: dritter Pruefparameter neben Magnetismus und
    # Strichfarbe; freie str-Spalte, Whitespace zaehlt wie leer.
    st.objekte_mit_hcl_reaktion = conn.execute(
        "SELECT COUNT(*) FROM objects "
        "WHERE HCl_Reaktion IS NOT NULL AND TRIM(HCl_Reaktion) != ''"
    ).fetchone()[0]
    # objekte_mit_uv_365nm: UV-Reaktion bei 365 nm (Langwellen-UV, Standard-
    # Wellenlaenge fuer Fluoreszenz-Sammler). Spiegelt objekte_mit_magnetismus /
    # objekte_mit_strichfarbe / objekte_mit_hcl_reaktion auf die optisch-UV-
    # Diagnose-Achse; freie str-Spalte mit Konvention "keine/schwach/stark +
    # Farbe", Whitespace zaehlt wie leer (spiegelt die has_X-Filter-Konvention
    # der umliegenden Pruef-Spalten).
    st.objekte_mit_uv_365nm = conn.execute(
        "SELECT COUNT(*) FROM objects "
        "WHERE UV_365nm IS NOT NULL AND TRIM(UV_365nm) != ''"
    ).fetchone()[0]
    # objekte_mit_uv_254nm: UV-Reaktion bei 254 nm (Kurzwellen-UV) - paarweise
    # zur Langwellen-Achse objekte_mit_uv_365nm und vervollstaendigt das
    # UV-Doppel-Wellenlaengen-Coverage. Spiegelt objekte_mit_uv_365nm exakt in
    # Struktur und Konvention; freie str-Spalte, Whitespace zaehlt wie leer.
    st.objekte_mit_uv_254nm = conn.execute(
        "SELECT COUNT(*) FROM objects "
        "WHERE UV_254nm IS NOT NULL AND TRIM(UV_254nm) != ''"
    ).fetchone()[0]
    # objekte_mit_reaktionshinweis: Anzahl Objekte mit dokumentiertem
    # erklaerendem Begleit-Kommentar zu den Reaktions-Pruefparametern
    # (UV/HCl/Magnetismus). Spiegelt die strukturellen Reaktions-Quoten
    # (Magnetismus/HCl/UV_365/UV_254) auf die zugehoerige Erklaer-Achse.
    # text-Spalte (mehrzeilig moeglich), Whitespace zaehlt wie leer - spiegelt
    # die has_reaktionshinweis-Filter-Konvention aus stonebook.db.repository
    # und das Coverage-Muster der umliegenden Pruef-Spalten.
    st.objekte_mit_reaktionshinweis = conn.execute(
        "SELECT COUNT(*) FROM objects "
        "WHERE Reaktionshinweis IS NOT NULL AND TRIM(Reaktionshinweis) != ''"
    ).fetchone()[0]
    # objekte_mit_pruefempfehlungen: Anzahl Objekte mit dokumentierter
    # Pruef-Vorausschau (welche Tests bestaetigen die aktuelle Hypothese als
    # naechstes?). Spiegelt objekte_mit_reaktionshinweis exakt in Struktur und
    # Konvention - beide sind Sonstiges-Freitext-Achsen mit thematisch festem
    # Geltungsbereich (Reaktionshinweis rueckblickend, Pruefempfehlungen
    # vorausblickend), beide mehrzeilig (text-Spalte). Whitespace zaehlt wie
    # leer, spiegelt die has_pruefempfehlungen-Filter-Konvention aus
    # stonebook.db.repository.
    st.objekte_mit_pruefempfehlungen = conn.execute(
        "SELECT COUNT(*) FROM objects "
        "WHERE Pruefempfehlungen IS NOT NULL AND TRIM(Pruefempfehlungen) != ''"
    ).fetchone()[0]
    # objekte_mit_notizen: Anzahl Objekte mit irgendeinem nicht-leeren
    # notizen-Eintrag (freie Beobachtungs-Spalte neben den 43 Standardfeldern).
    # Spiegelt die Feld-Coverage-Quoten (Bildern/Funddatum/Mineral/Fundort/Glanz/
    # ...) auf die unstrukturierte Freitext-Achse - notizen ist die einzige
    # echte Freitext-Spalte mit beliebigem Inhalt (anders als die multi-line
    # text-Felder Reaktionshinweis/Pruefempfehlungen, die zwar mehrzeilig sind,
    # aber thematisch fest stehen). Whitespace zaehlt wie leer, spiegelt
    # has_notizen-Filter-Konvention. Niedriger Wert ist typisch - der Sammler
    # pflegt notizen nur bei Beobachtungs-Anlass (auffaelliger Habitus,
    # Pflege-Anforderung, Fund-Erinnerung), nicht routinemaessig fuer jedes
    # Stueck. Komplementaer zu den strukturierten Feld-Coverage-Quoten:
    # eine hohe Strukturfeld-Coverage mit niedriger notizen-Quote zeigt eine
    # rein katalogisierende Sammlungs-Linie, eine niedrige Strukturfeld-
    # Coverage mit hoher notizen-Quote eine beobachtungs-orientierte Linie.
    st.objekte_mit_notizen = conn.execute(
        "SELECT COUNT(*) FROM objects "
        "WHERE notizen IS NOT NULL AND TRIM(notizen) != ''"
    ).fetchone()[0]

    sums = conn.execute(
        "SELECT "
        + ", ".join(f"COALESCE(SUM({c}), 0) AS {c}" for c in WERT_FELDER)
        + ", COALESCE(SUM(Gewicht_g), 0) AS gewicht, "
        "AVG(Confidence_Prozent) AS conf_avg FROM objects"
    ).fetchone()
    st.wert_summe_chf = float(sum(sums[c] for c in WERT_FELDER))
    st.wert_roh_summe_chf = float(sums["Wert_CHF_roh"])
    st.gewicht_summe_g = float(sums["gewicht"])
    st.durchschnitt_confidence_prozent = (
        float(sums["conf_avg"]) if sums["conf_avg"] is not None else None
    )
    # Median Confidence: symmetrisch zu wert_median_chf/gewicht_median_g.
    # Out-of-Range-Werte (<0 / >100) zaehlen nicht; sie werden in der Integrity
    # separat gemeldet und wuerden die zentrale Tendenz verzerren.
    conf_werte = [int(r["c"]) for r in conn.execute(
        "SELECT Confidence_Prozent AS c FROM objects "
        "WHERE Confidence_Prozent IS NOT NULL "
        "AND Confidence_Prozent BETWEEN 0 AND 100 "
        "ORDER BY c"
    ).fetchall()]
    # objekte_mit_confidence: Anzahl Objekte mit gueltigem Sicherheits-Score.
    # Reuse von conf_werte (bereits BETWEEN 0 AND 100 gefiltert), damit Coverage-
    # und Median-/Bucket-Sicht garantiert auf demselben Wertegrund stehen:
    # ein out-of-range-Eintrag (Integrity-Pruefung) wird in keiner der drei
    # Sichten gezaehlt. Komplementaer zu median_/durchschnitt_confidence_prozent
    # und confidence_buckets (innere Verteilung) - hier die Coverage-Sicht
    # ueber den Gesamtbestand.
    st.objekte_mit_confidence = len(conf_werte)
    if conf_werte:
        n = len(conf_werte)
        st.median_confidence_prozent = float(
            conf_werte[n // 2] if n % 2
            else (conf_werte[n // 2 - 1] + conf_werte[n // 2]) / 2
        )
        # confidence_min_prozent: kleinster Confidence-Wert der Sammlung als
        # symmetrisches Pendant zu wert_min_chf / gewicht_min_g auf die
        # quantitative Sicherheits-Achse. Waehrend die Wert-/Gewicht-Extrema
        # die monetaere/physikalische Untergrenze beziffern (billigstes bzw.
        # leichtestes Stueck), beziffert die Confidence-Untergrenze die
        # "unsicherste Bestimmung" - jenes Stueck der Sammlung, bei dem der
        # Sammler den kleinsten Sicherheitsgrad vergeben hat. Ergaenzt damit
        # das durchschnitt_/median_confidence_prozent-Paar (zentrale Tendenz)
        # um die untere Randlage-Kennzahl; komplementaer zu
        # confidence_buckets (Bucket-Verteilung), das die untere Region
        # nur grob als "0-24"-Bucket bemasst, ohne den konkreten Minimums-
        # Wert zu benennen. Reuse der bereits sortierten conf_werte-Liste
        # (ORDER BY c aufsteigend) - conf_werte[0] ist der kleinste gueltige
        # Confidence-Wert, spiegelt den werte[0]- und gewichte[0]-Zugriff
        # exakt. Out-of-Range-Werte (<0 / >100) zaehlen nicht (sie sind
        # bereits in der conf_werte-Query per BETWEEN 0 AND 100 gefiltert),
        # damit die Extrem-Kennzahl nicht durch einen Integrity-Verstoss
        # verzerrt wird - spiegelt die median_confidence-/objekte_mit_
        # confidence-Konvention. Bei leerer DB / ohne jegliche Confidence-
        # Pflege bleibt None (dataclass-Default), spiegelt die
        # median_/durchschnitt_confidence_prozent-None-Konvention (score-
        # basierte Groessen mit None statt 0 im Undefined-Fall), damit
        # Downstream-Konsumenten (as_dict / CLI-Zeile / Dashboard) den
        # Undefined-Zustand transparent unterscheiden koennen.
        st.confidence_min_prozent = conf_werte[0]
        # confidence_max_prozent: groesster Confidence-Wert der Sammlung
        # als symmetrisches Pendant zu confidence_min_prozent auf die
        # Obergrenzen-Achse und zu wert_max_chf / gewicht_max_g auf die
        # Confidence-Achse. Waehrend die Wert-/Gewicht-Extrema die
        # monetaere/physikalische Obergrenze beziffern (teuerstes bzw.
        # schwerstes Stueck), beziffert die Confidence-Obergrenze die
        # "sicherste Bestimmung" der Sammlung - jenes Stueck, bei dem der
        # Sammler den hoechsten Sicherheitsgrad vergeben hat. Vervollstaendigt
        # damit das confidence_min_prozent / durchschnitt_/median_confidence_
        # prozent-Trio um die obere Randlage-Kennzahl und schliesst so die
        # Extremum-Achse (min + max), spiegelt das Wert-/Gewicht-Extrema-
        # Paar (wert_min_chf / wert_max_chf, gewicht_min_g / gewicht_max_g).
        # Komplementaer zu confidence_buckets (Bucket-Verteilung), das die
        # obere Region nur grob als "75-100"-Bucket bemasst, ohne den
        # konkreten Maximums-Wert zu benennen - hier die Punkt-Sicht auf
        # die Obergrenze. Reuse-Pfad: greift den bereits sortierten
        # conf_werte-Buffer ab (ORDER BY c aufsteigend) - conf_werte[-1]
        # ist der groesste gueltige Confidence-Wert, spiegelt das Muster
        # wert_max_chf = werte[-1] / gewicht_max_g = gewichte[-1] (dort
        # zwar per SQL MAX() vorgezogen, semantisch aber identisch). Out-
        # of-Range-Werte (<0 / >100) zaehlen nicht (bereits per BETWEEN
        # 0 AND 100 in der conf_werte-Query gefiltert), damit die Extrem-
        # Kennzahl nicht durch einen Integrity-Verstoss (z.B. Confidence
        # 150) verzerrt wird - spiegelt die confidence_min_prozent- /
        # median_confidence-Konvention. Bei leerer DB / ohne jegliche
        # Confidence-Pflege bleibt None (dataclass-Default), spiegelt die
        # confidence_min_prozent- / median_/durchschnitt_confidence_prozent-
        # None-Konvention (score-basierte Groessen mit None statt 0 im
        # Undefined-Fall) - im Gegensatz zu wert_max_chf / gewicht_max_g,
        # die auf 0.0 defaulten (Waehrungs-/Massen-Groessen haben 0 als
        # natuerlichen Null-Zustand, Confidence hingegen ist "unbewertet"
        # anders als "0 % Sicherheit"). Damit Downstream-Konsumenten
        # (as_dict / CLI-Zeile / Dashboard) den Undefined-Zustand
        # transparent unterscheiden koennen.
        st.confidence_max_prozent = conf_werte[-1]
        # confidence_standardabweichung_prozent: Populations-Standardabweichung
        # der Confidence-Scores als Dispersions-Achse zur zentralen-Tendenz-
        # Achse (durchschnitt_/median_confidence_prozent). Spiegelt
        # wert_standardabweichung_chf / gewicht_standardabweichung_g /
        # mohs_kollektion_standardabweichung / dichte_kollektion_
        # standardabweichung auf die quantitative Sicherheits-Achse und
        # vervollstaendigt damit das σ-Quintett Wert/Gewicht/Mohs/Dichte/
        # Confidence: waehrend die Original-Einheiten (CHF, g, Mohs-Punkt,
        # g/cm3, Prozent) die vier physikalisch/monetaeren Achsen und die
        # score-Achse jeweils in ihren nativen Skalen abbilden, macht sigma
        # die Streuung der einzelnen Kennzahlen um den jeweiligen Durchschnitt
        # in der Sammlung ablesbar. Beantwortet damit die Frage "wie
        # heterogen ist meine Bestimmungs-Sicherheit?" - eine strikt
        # gepflegte Sammlung mit ausschliesslich Referenz-Bestimmungen und
        # Confidence 90..100 zeigt hier ~3-4 Prozent, eine gemischte
        # Sammlung aus sicheren Referenzen und tentativen Feldbestimmungen
        # (Confidence 20..100) mehrere 20er Prozent. Ergaenzt damit das
        # Confidence-Kennzahlen-Sextett (durchschnitt/median/min/max/buckets/
        # objekte_mit_confidence) um die Populations-Dispersions-Achse und
        # stellt es strukturidentisch zu den vier anderen quantitativen
        # Achsen der Sammlung. Reuse der bereits geladenen und sortierten
        # conf_werte-Liste (ORDER BY c aufsteigend, existierender Median-/
        # Min-/Max-Berechnungs-Pfad); Populations-Variante (Divisor n statt
        # n-1), spiegelt die _mohs_/_dichte_/_wert_/_gewicht_standardab-
        # weichung-Konvention (Sammlung als vollstaendige Grundgesamtheit,
        # nicht als Stichprobe einer groesseren Population). Numerisch
        # stabile Formel via (x - mean)^2 statt E[X^2] - E[X]^2, spiegelt
        # die Konvention der vier anderen sigma-Groessen. Bei einem
        # einzelnen Confidence-Eintrag oder uniformen Werten kollabiert
        # die Streuung auf 0.0 (keine Dispersion moeglich, spiegelt
        # _wert/_gewicht/_mohs/_dichte_standardabweichung-Single-Point-/
        # Uniform-Kollaps-Semantik). Bei leerer DB / ohne jegliche
        # Confidence-Pflege bleibt None (dataclass-Default), spiegelt die
        # median_/durchschnitt_/confidence_min_/confidence_max_prozent-
        # None-Konvention (score-basierte Groessen mit None statt 0 im
        # Undefined-Fall) und stellt Symmetrie zu mohs_kollektion_/dichte_
        # kollektion_standardabweichung her - im Gegensatz zu wert_/
        # gewicht_standardabweichung, die auf 0.0 defaulten (Waehrungs-/
        # Massen-Groessen haben 0 als natuerlichen Null-Zustand, Confidence
        # hingegen ist "unbewertet" anders als "0 % Sicherheit"). Als
        # Percent-Groesse serialisiert mit round(x, 2) in as_dict, spiegelt
        # das wert_/gewicht_/mohs_/dichte_standardabweichung-Serialisierungs-
        # Format (numerische Kennzahl mit 2 Nachkommastellen).
        #
        # Der lokale Mittelwert wird ueber conf_werte (BETWEEN 0 AND 100)
        # neu berechnet, NICHT ueber durchschnitt_confidence_prozent (SQL
        # AVG() ohne Range-Filter): AVG rechnet alle non-null-Werte
        # ein - inklusive out-of-range - waehrend die conf_werte-basierte
        # Streuung strikt nur gueltige Werte verwenden darf. Ohne diesen
        # lokalen Recompute wuerde bei einer Sammlung mit einem 200er-
        # Confidence-Verstoss der Mittelwert nach oben verzerrt, die
        # (c - mean)^2-Summe dann aber ueber die gefilterte 0..100-Menge
        # laufen - Ergebnis waere ein inkonsistenter sigma-Wert, der weder
        # zur median-/min-/max-Achse noch zum AVG-basierten Ø passt.
        # Spiegelt die BETWEEN 0 AND 100-Filter-Konvention der conf_werte-
        # Query auf den Mittelwert-Anker der Streuungs-Formel.
        conf_mean = sum(conf_werte) / len(conf_werte)
        st.confidence_standardabweichung_prozent = (
            sum((c - conf_mean) ** 2 for c in conf_werte) / len(conf_werte)
        ) ** 0.5
        # confidence_variationskoeffizient_prozent: dimensionsloser
        # Variationskoeffizient (sigma/mean * 100) als Ergaenzung zu
        # confidence_standardabweichung_prozent. Vervollstaendigt damit
        # das CV-Quintett wert_/gewicht_/mohs_kollektion_/dichte_kollektion_
        # variationskoeffizient_prozent auf allen fuenf zentralen
        # Kennzahlen-Achsen der Sammlung, strukturidentisch zum bereits
        # etablierten sigma-Quintett Wert/Gewicht/Mohs/Dichte/Confidence.
        # Waehrend sigma die Streuung in Original-Einheiten (Prozentpunkten
        # auf der Confidence-Skala) beziffert, normiert der CV sigma auf
        # den Confidence-Durchschnitt und macht die Bestimmungs-Sicherheits-
        # Streuung skalen-unabhaengig direkt mit CV Wert / CV Gewicht /
        # CV Mohs / CV Dichte vergleichbar - fuenf dimensionslos-normierte
        # Homogenitaets-Sichten auf einer einheitlichen Prozent-Skala,
        # sodass eine Sammlung als "wertlich heterogen (CV 200%), Massen
        # moderat (CV 80%), Haerte-homogen (CV 5%), Dichte-homogen (CV 2%),
        # Bestimmungs-Sicherheit gleichfoermig (CV 4%)" charakterisierbar
        # wird. Reuse-Pfad: greift den bereits berechneten conf_mean
        # (BETWEEN 0 AND 100-gefiltert) und die frisch geschriebene
        # confidence_standardabweichung_prozent ab - kein zusaetzlicher
        # SQL-Round-Trip, keine zweite Listen-Iteration ueber conf_werte.
        # Der lokale conf_mean wird bewusst verwendet (nicht das SQL-AVG-
        # basierte durchschnitt_confidence_prozent), spiegelt die
        # confidence_standardabweichung_prozent-Konvention: bei einem
        # out-of-range-Verstoss (Confidence 200) wuerde AVG den Mittelwert
        # nach oben verzerren, waehrend conf_mean strikt auf 0..100
        # normiert bleibt - CV muss konsistent zum sigma-Anker rechnen,
        # sonst waere die Division sinnlos. Guarded gegen conf_mean == 0
        # (bei ausschliesslich 0er-Confidence-Werten - erlaubt vom
        # BETWEEN 0 AND 100-Filter, aber semantisch "unbewertet" und
        # damit kein sinnvoller CV-Anker). Bei einem einzelnen Confidence-
        # Eintrag oder uniformen Werten kollabiert sigma auf 0.0 und
        # damit CV auf 0.0 (spiegelt die _wert/_gewicht/_mohs/_dichte-
        # Uniform-Kollaps-Semantik). Bei leerer DB / ohne jegliche
        # Confidence-Pflege bleibt None (dataclass-Default), spiegelt die
        # confidence_standardabweichung_prozent-/median_/durchschnitt_/
        # min_/max_-None-Konvention (score-basierte Groessen mit None
        # statt 0 im Undefined-Fall) und stellt Symmetrie zu
        # mohs_kollektion_/dichte_kollektion_variationskoeffizient_prozent
        # her (mean-basierte Groessen mit None im Undefined-Fall) - im
        # Gegensatz zu wert_/gewicht_variationskoeffizient_prozent, die
        # analog dazu bei mean == 0 None bleiben, aber bei fehlender Pflege
        # ebenfalls None (nicht 0.0) sind. Als Percent-Groesse serialisiert
        # mit round(x, 2) in as_dict, spiegelt das wert_/gewicht_/mohs_/
        # dichte_variationskoeffizient_prozent-Serialisierungs-Format.
        if conf_mean > 0:
            st.confidence_variationskoeffizient_prozent = (
                st.confidence_standardabweichung_prozent / conf_mean * 100.0)
        # confidence_spanweite_prozent: Spannweite (Range = max - min) in
        # Prozentpunkten auf der Bestimmungs-Sicherheits-Achse als
        # Original-Einheiten-Dispersions-Achse neben sigma und CV.
        # Vervollstaendigt damit das Spannweiten-Quintett wert_/gewicht_/
        # mohs_kollektion_/dichte_kollektion_/confidence_spanweite - alle
        # fuenf zentralen quantitativen Achsen der Sammlung (Preis /
        # Masse / Haerte / Dichte / Bestimmungs-Sicherheit) haben damit
        # die drei Dispersions-Sichten sigma / CV / Spannweite. Waehrend
        # confidence_standardabweichung_prozent die durchschnittliche
        # Streuung um den Mittelwert in Prozentpunkten beziffert (reagiert
        # auf die Verteilungsform) und confidence_variationskoeffizient_
        # prozent dieselbe Streuung dimensionslos-normiert liefert
        # (skalen-unabhaengig), beziffert die Spannweite die volle
        # beobachtete Sicherheits-Bandbreite - die Distanz zwischen der
        # unsichersten und der sichersten KI-Bestimmung ("zwischen 20% und
        # 95%"). Die naheliegendste Formulierung der Confidence-Bandbreite
        # ohne Statistik-Vokabular (jeder Sammler versteht "zwischen
        # Confidence X und Y" direkt). Complement zu sigma: sigma reagiert
        # auf die Verteilungsform (breite Streuung um den Mittel = grosses
        # sigma), die Spannweite reagiert nur auf die Extremwerte und
        # ignoriert die Dichte dazwischen - eine gleichmaessig gepflegte
        # Sammlung (Confidence 80..90) hat kleine Spannweite (10) und
        # kleines sigma (~3); eine gemischte Sammlung (5x Confidence 20 +
        # 5x Confidence 95) hat grosse Spannweite (75) und grosses sigma
        # (~37). Reuse-Pfad: greift die bereits gesetzten confidence_max_
        # prozent und confidence_min_prozent ab (kein zusaetzlicher
        # SQL-Round-Trip, keine zweite Listen-Iteration ueber conf_werte,
        # spiegelt die mohs_/dichte_kollektion_spanweite-Ableitung aus
        # max/min). Als int-Groesse (Confidence-Skala ist int-Prozent, kein
        # float-Nachkomma) - spiegelt confidence_min_prozent/max_prozent
        # (beide int); Differenz zweier int bleibt int, keine Rundung
        # noetig. Bei einem einzelnen Confidence-Eintrag oder uniformen
        # Werten kollabiert die Spannweite auf 0 (min == max, spiegelt die
        # sigma-Uniform-Kollaps-Semantik und mohs_/dichte_kollektion_
        # spanweite-Konvention). Bei leerer DB / ohne jegliche Confidence-
        # Pflege bleibt None (dataclass-Default), spiegelt die
        # confidence_min_/max_/durchschnitt_/median_/sigma-None-Konvention -
        # score-basierte Groessen bleiben im Undefined-Fall None statt 0.
        if (st.confidence_min_prozent is not None
                and st.confidence_max_prozent is not None):
            st.confidence_spanweite_prozent = (
                st.confidence_max_prozent - st.confidence_min_prozent)
    st.confidence_buckets = _confidence_buckets(conn)

    gewichte = [float(r["g"]) for r in conn.execute(
        "SELECT Gewicht_g AS g FROM objects "
        "WHERE Gewicht_g IS NOT NULL AND Gewicht_g > 0 ORDER BY g"
    ).fetchall()]
    st.objekte_mit_gewicht = len(gewichte)
    # objekte_mit_dimensionen: Anzahl Objekte mit mindestens einer der drei
    # geometrischen Achsen (Laenge_mm / Breite_mm / Hoehe_mm) dokumentiert.
    # Spiegelt has_dimensionen-Filter-Konvention exakt: in der Praxis wird oft
    # nur die laengste Achse erfasst (Vitrinen-/Schubladen-Index), Breite/Hoehe
    # erst beim Praeparieren nachgereicht - eine konjunktive Definition
    # (alle drei) wuerde den Pflege-Workflow missrepraesentieren. Komplementaer
    # zu objekte_mit_gewicht (Masse als physikalische Mess-Achse): hier die
    # geometrische Mess-Achse. Die Differenz beider beziffert die Vermessungs-
    # Luecke (gewogen aber nicht vermessen, oder vermessen aber nicht gewogen).
    st.objekte_mit_dimensionen = conn.execute(
        "SELECT COUNT(*) FROM objects "
        "WHERE Laenge_mm IS NOT NULL OR Breite_mm IS NOT NULL "
        "OR Hoehe_mm IS NOT NULL"
    ).fetchone()[0]
    # objekte_mit_mohs: Anzahl Objekte mit mindestens einem dokumentierten
    # Mohs-Haerte-Bereichsfeld (min ODER max). Spiegelt die has_mohs-Filter-
    # Konvention exakt: ein Objekt zaehlt als geprueft, sobald eines der
    # beiden Bereichsfelder gesetzt ist - die obere und untere Grenze werden
    # nicht immer zusammen gepflegt (oft nur "5-6" als Roh-Skala mit
    # min=5/max=NULL oder umgekehrt). Komplementaer zu objekte_mit_dimensionen
    # (geometrische Mess-Achse) und objekte_mit_gewicht (Masse): hier die
    # physikalische Haerte-Achse, die mit dem Kratztest (Glas/Stahl/Kupfer-/
    # Fingernagel-Skala) als billigste Bestimmungs-Methode verfuegbar ist.
    # Niedriger Wert ist normal - Mohs wird typisch erst nach Mineral-
    # Bestimmung gepflegt (deterministisch aus der Mineralart ableitbar),
    # viele mineralogisch klare Stuecke bleiben ohne explizite Haerte-Pruefung.
    st.objekte_mit_mohs = conn.execute(
        "SELECT COUNT(*) FROM objects "
        "WHERE Mohs_Haerte_min IS NOT NULL OR Mohs_Haerte_max IS NOT NULL"
    ).fetchone()[0]
    # Mohs-Haerte-Spanne ueber die ganze Sammlung: kleinste und groesste
    # Haerte, die ueberhaupt im Bestand dokumentiert ist. Spiegelt das
    # funddatum_/erstellt_am_/geaendert_am-Spannen-Trio auf die physikalische
    # Haerte-Achse - waehrend die Coverage-Quote (quote_mit_mohs_prozent)
    # beziffert, wieviel der Sammlung ueberhaupt eine Mohs-Pflege hat, zeigt
    # die Spanne die Haerte-Bandbreite des dokumentierten Anteils ("vom
    # weichsten Talk-Stueck zum haertesten Korund-Stueck"). Reuse der
    # has_mohs-/objekte_mit_mohs-Konvention (ein Objekt zaehlt, sobald eines
    # der beiden Bereichsfelder gesetzt ist). Bei leerer DB / ohne jegliche
    # Mohs-Pflege bleiben beide Grenzen None, spiegelt das _funddatum_spanne-
    # Verhalten.
    st.mohs_kollektion_min, st.mohs_kollektion_max = _mohs_spanne(conn)
    # Mohs-Durchschnitt: zentrale-Tendenz-Achse zur Spannen-Achse; pro Objekt
    # der Mittelpunkt von Mohs_Haerte_min/max (bei Single-Point-Pflege der eine
    # Wert), gemittelt ueber alle Objekte mit mindestens einem gesetzten
    # Bereichsfeld. Spiegelt gewicht_durchschnitt_g auf die Haerte-Achse.
    st.mohs_kollektion_durchschnitt = _mohs_durchschnitt(conn)
    # Mohs-Median: ausreisser-robuste zentrale Tendenz zur Durchschnitts-Achse.
    # Waehrend der Durchschnitt sensibel auf einzelne sehr weiche/harte
    # Ausreisser reagiert, bleibt der Median unempfindlich - das "typische"
    # Stueck als 50%-Quantil der Haerte-Verteilung. Spiegelt gewicht_median_g/
    # wert_median_chf auf die physikalische Haerte-Achse und vervollstaendigt
    # das Mohs-Kennzahlen-Trio (min/max/durchschnitt) um die Median-Achse.
    st.mohs_kollektion_median = _mohs_median(conn)
    # Mohs-Standardabweichung: Dispersions-Achse zur zentralen-Tendenz-Achse
    # (Durchschnitt/Median). Waehrend Durchschnitt und Median das "typische"
    # Stueck beziffern, beziffert die Standardabweichung die Streuung der
    # Sammlung um den Durchschnitt - eine Sammlung mit Durchschnitt 6.0 und
    # Standardabweichung 0.5 (reine Quarz-Familie 5.5..6.5) ist mineralogisch
    # anders als eine mit Durchschnitt 6.0 und Standardabweichung 3.0 (Talk
    # + Diamant gemischt). Vervollstaendigt damit das Mohs-Kennzahlen-
    # Quartett (min/max/durchschnitt/median) um die Dispersions-Achse.
    st.mohs_kollektion_standardabweichung = _mohs_standardabweichung(conn)
    # mohs_kollektion_variationskoeffizient_prozent: dimensionslose
    # Dispersions-Achse als Ergaenzung zu mohs_kollektion_standardabweichung.
    # Spiegelt wert_variationskoeffizient_prozent / gewicht_variations-
    # koeffizient_prozent auf die Haerte-Achse: waehrend sigma die
    # Streuung in Original-Einheiten (Mohs-Punkte) beziffert, normiert
    # der CV sigma auf den Durchschnitt und macht die Haerte-Streuung
    # skalen-unabhaengig vergleichbar. Eine reine Quarz-Familie (Ø 6.0,
    # sigma 0.5, CV ~8%) unterscheidet sich mineralogisch stark von
    # einer Talk+Diamant-Sammlung (Ø 5.5, sigma 3.5, CV ~64%) - beide
    # koennen aehnlichen Durchschnitt haben, aber der CV macht die
    # Heterogenitaet skalen-unabhaengig ablesbar. Damit ist der Mohs-
    # Kennzahlen-Block strukturidentisch zum Wert-/Gewicht-Block
    # (min/max/durchschnitt/median/sigma + CV). Reuse: greift den
    # bereits berechneten mohs_kollektion_durchschnitt und
    # mohs_kollektion_standardabweichung ab (kein zusaetzlicher SQL-
    # Round-Trip). Guarded gegen mean == 0.0 (Mohs-Punkte sind
    # strukturell > 0, aber die Guard schuetzt gegen numerische
    # Randfaelle bei extrem kleinen Werten). Bei leerer DB / ohne
    # jegliche Mohs-Pflege bleibt None (dataclass-Default), spiegelt
    # die mohs_kollektion_standardabweichung- / _durchschnitt-None-
    # Konvention (mean-basierte Groessen mit None statt 0.0 im
    # Undefined-Fall).
    if (st.mohs_kollektion_standardabweichung is not None
            and st.mohs_kollektion_durchschnitt is not None
            and st.mohs_kollektion_durchschnitt > 0):
        st.mohs_kollektion_variationskoeffizient_prozent = (
            st.mohs_kollektion_standardabweichung
            / st.mohs_kollektion_durchschnitt * 100.0)
    # mohs_kollektion_spanweite: Spannweite (Range) = max - min in Mohs-
    # Punkten als Original-Einheiten-Dispersions-Achse neben sigma und CV.
    # Spiegelt wert_spanweite_chf / gewicht_spanweite_g auf die Haerte-
    # Achse und vervollstaendigt damit den Mohs-Kennzahlen-Block
    # (min/max/durchschnitt/median/sigma/CV) um die Original-Einheiten-
    # Bandbreiten-Achse. Waehrend sigma die durchschnittliche Streuung
    # um den Mittelwert beziffert und der CV dieselbe Streuung dimensions-
    # los normiert, beziffert die Spannweite die volle beobachtete Haerte-
    # Bandbreite - die Distanz zwischen dem weichsten und dem haertesten
    # dokumentierten Stueck in Mohs-Punkten ("zwischen Mohs 2 und Mohs 7").
    # Complement zu sigma: sigma reagiert auf die Verteilungsform (breite
    # Streuung um den Mittel = grosses sigma), die Spannweite reagiert
    # nur auf die Extremwerte und ignoriert die Dichte dazwischen -
    # eine reine Quarz-Familie (5.5..6.5) hat kleine Spannweite (1.0) und
    # kleines sigma (~0.3); eine Talk+Diamant-Mischung hat grosse
    # Spannweite (9.0) und grosses sigma (~4). Reuse: greift die bereits
    # gesetzten mohs_kollektion_max und mohs_kollektion_min ab (kein
    # zusaetzlicher SQL-Round-Trip). Bei leerer DB / ohne jegliche Mohs-
    # Pflege bleibt None (dataclass-Default), spiegelt die mohs_kollektion_
    # min/max-None-Konvention (Bereichs-Groessen mit None statt 0.0 im
    # Undefined-Fall, anders als wert_/gewicht_spanweite die 0.0 bei
    # leerer DB liefern, weil deren min/max ebenfalls 0.0 sind). Bei einem
    # einzelnen Mohs-Eintrag oder uniformen Werten kollabiert die Spann-
    # weite auf 0.0 (min == max, spiegelt die sigma-Uniform-Kollaps-
    # Semantik). as_dict-Round auf 1 Nachkommastelle (spiegelt
    # mohs_kollektion_min/max/durchschnitt/median).
    if (st.mohs_kollektion_min is not None
            and st.mohs_kollektion_max is not None):
        st.mohs_kollektion_spanweite = (
            st.mohs_kollektion_max - st.mohs_kollektion_min)
    # objekte_mit_dichte: Anzahl Objekte mit mindestens einem dokumentierten
    # Dichte-Bereichsfeld (min ODER max). Spiegelt objekte_mit_mohs exakt auf
    # die Dichte-Achse: beide sind physikalische Bereichsfelder, beide zaehlen
    # ein Objekt als geprueft, sobald eines der beiden Felder gesetzt ist - die
    # obere und untere Grenze werden nicht immer zusammen gepflegt (oft nur
    # ein Punkt-Wert fuer ein Reinmineral, oder eine Roh-Skala "2.6-2.7" als
    # Standard-Tabellenwert aus der Mineraldatenbank uebernommen). Komplementaer
    # zu objekte_mit_mohs (physikalische Haerte-Achse) und objekte_mit_gewicht
    # (Masse): hier die physikalische Dichte-Achse als zweite zentrale
    # quantitative Pruef-Methode neben Mohs. Pyrit (~5.0) vs. Markasit (~4.9)
    # sind ohne Dichte nicht trennbar - beide haben Mohs 6-6.5 und metallischen
    # Glanz. Niedriger Wert ist typisch in Sammler-Bestaenden: die Messung
    # erfordert Wasserverdraengung mit Waage oder pyknometrische Bestimmung,
    # ist also nicht so trivial wie der Mohs-Kratztest, und wird daher seltener
    # gepflegt - oft nur als Tabellen-Uebernahme nach Mineral-Bestimmung.
    st.objekte_mit_dichte = conn.execute(
        "SELECT COUNT(*) FROM objects "
        "WHERE Dichte_min_gcm3 IS NOT NULL OR Dichte_max_gcm3 IS NOT NULL"
    ).fetchone()[0]
    # Dichte-Spanne ueber die ganze Sammlung: kleinste und groesste
    # Massendichte, die ueberhaupt im Bestand dokumentiert ist. Spiegelt das
    # Mohs-Spannen-Pendant (physikalische Haerte-Achse) auf die zweite
    # zentrale physikalische Pruef-Achse - waehrend die Coverage-Quote
    # (quote_mit_dichte_prozent) beziffert, wieviel der Sammlung ueberhaupt
    # eine Dichte-Pflege hat, zeigt die Spanne die Massendichte-Bandbreite
    # des dokumentierten Anteils ("vom leichtesten Bims-/Opal-Stueck zum
    # schwersten Pyrit-/Galenit-Stueck"). Vervollstaendigt damit die
    # physikalische Spannen-Achse: Mohs (Haerte 1..10) und Dichte (g/cm3,
    # typisch 1.0..7.5 fuer Sammlerbestaende) - die zwei zentralen
    # quantitativen Pruef-Methoden, die zusammen Quarz/Calcit/Fluorit-Klassen
    # diskriminieren. Reuse der has_dichte-/objekte_mit_dichte-Konvention
    # (ein Objekt zaehlt, sobald eines der beiden Bereichsfelder gesetzt
    # ist). Bei leerer DB / ohne jegliche Dichte-Pflege bleiben beide
    # Grenzen None, spiegelt das _mohs_spanne-/_funddatum_spanne-Verhalten.
    st.dichte_kollektion_min, st.dichte_kollektion_max = _dichte_spanne(conn)
    # Dichte-Durchschnitt: zentrale-Tendenz-Achse zur Dichte-Spannen-Achse; pro
    # Objekt der Mittelpunkt von Dichte_min_gcm3/max_gcm3 (bei Single-Point-
    # Pflege der eine Wert), gemittelt ueber alle Objekte mit mindestens einem
    # gesetzten Bereichsfeld. Spiegelt _mohs_durchschnitt auf die Dichte-Achse.
    st.dichte_kollektion_durchschnitt = _dichte_durchschnitt(conn)
    # Dichte-Median: ausreisser-robuste zentrale Tendenz zur Durchschnitts-
    # Achse. Vervollstaendigt das Dichte-Kennzahlen-Trio (min/max + durchschnitt)
    # um die Median-Achse und stellt es strukturidentisch neben das
    # Mohs-Kennzahlen-Quartett (min/max/durchschnitt/median).
    st.dichte_kollektion_median = _dichte_median(conn)
    # Dichte-Standardabweichung: Dispersions-Achse zur zentralen-Tendenz-Achse
    # (Durchschnitt/Median). Spiegelt mohs_kollektion_standardabweichung auf
    # die Dichte-Achse: waehrend Durchschnitt und Median das "typische" Stueck
    # beziffern, beziffert die Standardabweichung die Streuung um den
    # Durchschnitt - eine reine Quarz-Familie (Dichte 2.65..2.67) zeigt hier
    # ~0.01, eine gemischte Sammlung mit Bims bis Galenit ~2.0.
    st.dichte_kollektion_standardabweichung = _dichte_standardabweichung(conn)
    # dichte_kollektion_variationskoeffizient_prozent: dimensionslose
    # Dispersions-Achse als Ergaenzung zu dichte_kollektion_standard-
    # abweichung. Vervollstaendigt das CV-Quartett Wert / Gewicht /
    # Mohs / Dichte und macht die Dichte-Streuung skalen-unabhaengig
    # vergleichbar mit den drei Symmetrie-Partnern - eine reine Quarz-
    # Familie mit Dichte 2.65..2.67 zeigt hier ~0.3%, eine gemischte
    # Bims-bis-Galenit-Sammlung dagegen 30..60%. Direkter Vergleich der
    # Sammlungs-Homogenitaet zwischen den vier orthogonalen Sichten
    # (Preis / Masse / Haerte / Dichte) wird durch die einheitliche
    # dimensionslose Prozent-Skala erst moeglich. Reuse: greift den
    # bereits berechneten dichte_kollektion_durchschnitt und
    # dichte_kollektion_standardabweichung ab (kein zusaetzlicher SQL-
    # Round-Trip). Guarded gegen mean == 0 und mean None (Dichte-Werte
    # sind physikalisch > 0, aber die Guard schuetzt gegen numerische
    # Randfaelle und den None-Fall bei fehlender Dichte-Pflege). Bei
    # leerer DB / ohne jegliche Dichte-Pflege bleibt None (dataclass-
    # Default), spiegelt die dichte_kollektion_standardabweichung- /
    # _durchschnitt-None-Konvention (mean-basierte Groessen mit None
    # im Undefined-Fall) und stellt Symmetrie zu mohs_kollektion_
    # variationskoeffizient_prozent her.
    if (st.dichte_kollektion_standardabweichung is not None
            and st.dichte_kollektion_durchschnitt is not None
            and st.dichte_kollektion_durchschnitt > 0):
        st.dichte_kollektion_variationskoeffizient_prozent = (
            st.dichte_kollektion_standardabweichung
            / st.dichte_kollektion_durchschnitt * 100.0)
    # dichte_kollektion_spanweite: Spannweite (Range) = max - min in g/cm3
    # als Original-Einheiten-Dispersions-Achse neben sigma und CV.
    # Spiegelt mohs_kollektion_spanweite (Haerte-Achse) auf die zweite
    # zentrale physikalische Pruef-Achse und vervollstaendigt damit den
    # Dichte-Kennzahlen-Block (min/max/durchschnitt/median/sigma/CV) um
    # die Original-Einheiten-Bandbreiten-Achse. Waehrend sigma die
    # durchschnittliche Streuung in g/cm3 beziffert und der CV dieselbe
    # Streuung dimensionslos normiert, beziffert die Spannweite die volle
    # beobachtete Massendichte-Bandbreite - die Distanz zwischen dem
    # leichtesten und dem schwersten Stueck ("zwischen 1.0 g/cm3 Bims und
    # 7.5 g/cm3 Galenit"). Complement zu sigma: sigma reagiert auf die
    # Verteilungsform (breite Streuung um den Mittel = grosses sigma),
    # die Spannweite reagiert nur auf die Extremwerte und ignoriert die
    # Dichte dazwischen - eine reine Quarz-Familie (2.65..2.67 g/cm3) hat
    # winzige Spannweite (0.02) und winziges sigma (~0.01); eine gemischte
    # Bims-bis-Galenit-Sammlung hat grosse Spannweite (6.5) und grosses
    # sigma (~2). Reuse-Pfad: greift die bereits gesetzten dichte_kollektion_
    # max und dichte_kollektion_min ab (kein zusaetzlicher SQL-Round-Trip,
    # spiegelt die mohs_kollektion_spanweite-Ableitung aus max/min). Bei
    # einem einzelnen Dichte-Eintrag oder uniformen Werten kollabiert die
    # Spannweite auf 0.0 (min == max, spiegelt die sigma-Uniform-Kollaps-
    # Semantik und mohs_kollektion_spanweite-Konvention). Bei leerer DB /
    # ohne jegliche Dichte-Pflege bleibt None (dataclass-Default), spiegelt
    # die dichte_kollektion_min/max/durchschnitt/median/sigma-None-Konvention -
    # Bereichsgroessen bleiben im Undefined-Fall None statt 0.0 (spiegelt
    # mohs_kollektion_spanweite, anders als wert_/gewicht_spanweite die
    # 0.0 bei leerer DB liefern). as_dict-Round auf 2 Nachkommastellen
    # (Zenti-g/cm3-Aufloesung, spiegelt dichte_kollektion_min/max/
    # durchschnitt/median).
    if (st.dichte_kollektion_min is not None
            and st.dichte_kollektion_max is not None):
        st.dichte_kollektion_spanweite = (
            st.dichte_kollektion_max - st.dichte_kollektion_min)
    if gewichte:
        st.gewicht_min_g = gewichte[0]
        st.gewicht_max_g = gewichte[-1]
        st.gewicht_durchschnitt_g = sum(gewichte) / len(gewichte)
        n = len(gewichte)
        st.gewicht_median_g = (gewichte[n // 2] if n % 2
                               else (gewichte[n // 2 - 1] + gewichte[n // 2]) / 2)
        # Gewicht-Standardabweichung: Dispersions-Achse zur zentralen-Tendenz-
        # Achse (Durchschnitt/Median). Spiegelt mohs_kollektion_standardabweichung
        # und dichte_kollektion_standardabweichung auf die Massen-Achse: waehrend
        # Durchschnitt und Median das "typische" Stueck beziffern, beziffert die
        # Standardabweichung die Streuung der Massen um den Durchschnitt - eine
        # gleichfoermige Mineralkorn-Sammlung mit Gewichten in engem Cluster
        # zeigt hier ~1 g, eine gemischte Sammlung aus Splittern bis Handstuecken
        # hunderte Gramm. Vervollstaendigt damit das Gewicht-Kennzahlen-Quintett
        # (summe/min/max/durchschnitt/median) um die Dispersions-Achse. Reuse
        # der bereits geladenen und sortierten gewichte-Liste (kein zweiter
        # SQL-Round-Trip); Populations-Variante (Divisor n statt n-1), spiegelt
        # die _mohs_/_dichte_standardabweichung-Konvention (Sammlung als
        # vollstaendige Grundgesamtheit). Numerisch stabile Formel via
        # (x - mean)^2 statt E[X^2] - E[X]^2, weil Gewichte in Gramm bis in
        # den 10^5-Bereich reichen koennen (kg-schwere Handstuecke) und die
        # Katastrophal-Kancellations-Version (E[X^2] - E[X]^2) bei grossen
        # Werten mit kleiner Varianz Rundungsfehler erzeugt (10^10 - 10^10 =
        # Muell im Bit-Rest). Bei einem einzelnen Gewicht-Eintrag kollabiert
        # die Streuung auf 0.0 (keine Dispersion moeglich, spiegelt _mohs_/
        # _dichte_standardabweichung Single-Point-Kollaps).
        mean = st.gewicht_durchschnitt_g
        st.gewicht_standardabweichung_g = (
            sum((g - mean) ** 2 for g in gewichte) / n) ** 0.5
        # gewicht_variationskoeffizient_prozent: dimensionslose Dispersions-
        # Achse als Ergaenzung zu gewicht_standardabweichung_g. Spiegelt
        # wert_variationskoeffizient_prozent auf die Massen-Achse: waehrend
        # sigma die Streuung in Original-Einheiten g beziffert, normiert der
        # CV sigma auf den Durchschnitt und macht die Massen-Streuung
        # skalen-unabhaengig vergleichbar - eine Mineralkorn-Sammlung mit
        # Ø 5 g und sigma 0.5 (CV 10%) hat dieselbe relative Streuung wie
        # eine Handstueck-Sammlung mit Ø 500 g und sigma 50 (CV 10%), obwohl
        # die Absolutwerte um Faktor 100 auseinanderliegen. Beantwortet
        # damit die praeparations- und transport-relevante Frage "wie
        # homogen ist meine Sammlung gewichtsmaessig, unabhaengig vom
        # Groessen-Niveau?" - reine Mineralkorn-Klasse zeigt ~10%,
        # gemischte Splitter-bis-Handstueck-Sammlung dagegen mehrere
        # hundert Prozent. Ergaenzt damit das Gewicht-Kennzahlen-Sextett
        # (summe/min/max/durchschnitt/median/sigma) um die dimensionslose
        # Dispersions-Achse und macht die Gewicht-Streuung strukturell
        # vergleichbar mit der Wert-/Mohs-/Dichte-Streuung, deren Original-
        # Einheiten (CHF, Mohs-Punkt, g/cm3) sich sonst nicht miteinander
        # vergleichen lassen. Reuse-Pfad: greift den bereits berechneten
        # mean (gewicht_durchschnitt_g) und gewicht_standardabweichung_g ab
        # (kein zweiter SQL-Round-Trip, keine zweite Listen-Iteration
        # ueber gewichte). Ausgabe in Prozent (sigma/mean * 100),
        # spiegelt die wert_variationskoeffizient_prozent-Konvention.
        # Bei einem einzelnen Gewicht-Eintrag oder uniformen Gewichten
        # kollabiert sigma auf 0.0 und damit CV auf 0.0 (spiegelt die
        # gewicht_standardabweichung_g-Single-Point-/Uniform-Kollaps-
        # Semantik). Guarded gegen mean == 0.0 (ist im gewichte-Zweig
        # nie der Fall, weil das SELECT-Statement Gewicht_g > 0 filtert
        # bzw. NULL/0-Eintraege ignoriert werden, aber die Guard schuetzt
        # fuer den Fall spaeterer Filter-Aenderungen). Bei leerer DB /
        # ohne jegliche Gewicht-Pflege bleibt None (dataclass-Default),
        # damit as_dict und die CLI-Zeile den Undefined-Zustand
        # transparent unterscheiden koennen - anders als sigma (0.0 bei
        # leerer DB) ist CV mathematisch undefined bei mean == 0, nicht
        # 0.0. Spiegelt die wert_variationskoeffizient_prozent- /
        # mohs_kollektion_standardabweichung- / dichte_kollektion_
        # standardabweichung-None-Konvention (mean-basierte Groessen mit
        # None statt 0.0 im Undefined-Fall).
        if mean > 0:
            st.gewicht_variationskoeffizient_prozent = (
                st.gewicht_standardabweichung_g / mean * 100.0)
        # gewicht_spanweite_g: Spannweite (Range) = gewicht_max_g - gewicht_min_g
        # als Original-Einheiten-Dispersions-Achse auf der Massen-Achse,
        # symmetrisches Pendant zu wert_spanweite_chf auf der Wert-Achse.
        # Vervollstaendigt damit das Gewicht-Kennzahlen-Septett (summe/min/max/
        # durchschnitt/median/sigma/CV) um die Original-Einheiten-Bandbreiten-
        # Achse und stellt Symmetrie zum bereits eingefuehrten Wert-Septett her.
        # Waehrend gewicht_standardabweichung_g die durchschnittliche Streuung
        # um den Mittelwert in Gramm beziffert (reagiert auf die Verteilungs-
        # form) und gewicht_variationskoeffizient_prozent dieselbe Streuung
        # dimensionslos normiert (skalen-unabhaengiger Vergleich mit Wert/
        # Mohs/Dichte-CV), beziffert die Spannweite die volle beobachtete
        # Bandbreite - die Distanz zwischen leichtestem und schwerstem
        # dokumentiertem Stueck in Gramm ("zwischen 5 g und 2500 g"), die
        # naheliegendste Formulierung der Massen-Bandbreite ohne Statistik-
        # Vokabular. Ist zwar trivial aus min/max ableitbar, aber explizit
        # ausgegeben, damit Dashboard- und Bericht-Konsumenten die Bandbreite
        # ohne zweiten Rechenschritt zur Hand haben (spiegelt die durchschnitt/
        # median-Konvention: ebenfalls aus den gewichte-Rohdaten ableitbar,
        # aber vorberechnet exponiert). Complement zu sigma: sigma reagiert
        # auf die Verteilungsform (breite Streuung um den Mittel = grosses
        # sigma), die Spannweite reagiert nur auf die Extremwerte und
        # ignoriert die Dichte dazwischen - eine Sammlung mit einem einzelnen
        # schweren Ausreisser (10 Mineralkoerner a 5 g + 1 Handstueck 5000 g)
        # hat eine grosse Spannweite (4995 g) trotz kleinem sigma (~1500 g);
        # umgekehrt hat eine gleichmaessig ueber 10..1000 g verteilte Sammlung
        # ein mittleres sigma und eine mittlere Spannweite. Reuse: greift die
        # bereits gesetzten gewicht_max_g und gewicht_min_g ab (kein
        # zusaetzlicher SQL-Round-Trip, keine zweite Listen-Iteration -
        # spiegelt die wert_spanweite_chf-Ableitung aus wert_max_chf/min).
        # Bei einem einzelnen Gewicht-Eintrag oder uniformen Gewichten
        # kollabiert die Spannweite auf 0.0 (min == max, spiegelt die sigma-
        # Uniform-Kollaps-Semantik und wert_spanweite_chf-Konvention). Bei
        # leerer DB / ohne jegliche Gewicht-Pflege bleibt 0.0 (dataclass-
        # Default, spiegelt die uebrigen Gewicht-Kennzahlen min/max/median/
        # durchschnitt/sigma = 0.0 bei leerer DB - anders als CV, das None
        # bleibt, weil max - min bei leerer DB semantisch 0.0 ist (leere
        # Bandbreite = keine Spanne), waehrend CV mathematisch undefined ist
        # (Division durch mean = 0)). as_dict-Round auf 2 Nachkommastellen
        # (Zenti-Gramm-Aufloesung, spiegelt gewicht_max_g und wert_spanweite_chf).
        st.gewicht_spanweite_g = st.gewicht_max_g - st.gewicht_min_g

    wert_sql = wert_pro_objekt_sql()
    row = conn.execute(
        f"SELECT COALESCE(MAX({wert_sql}), 0) AS wmax, "
        f"COUNT(*) AS n FROM objects WHERE {wert_sql} > 0"
    ).fetchone()
    st.wert_max_chf = float(row["wmax"])
    st.objekte_mit_wert = int(row["n"])
    if st.objekte_mit_wert:
        st.wert_durchschnitt_chf = st.wert_summe_chf / st.objekte_mit_wert
        werte = [float(r["w"]) for r in conn.execute(
            f"SELECT {wert_sql} AS w FROM objects "
            f"WHERE {wert_sql} > 0 ORDER BY w"
        ).fetchall()]
        n = len(werte)
        # wert_min_chf: kleinster Objekt-Wert (Summe der WERT_FELDER pro
        # Objekt) in der Sammlung, symmetrisches Pendant zum bereits
        # bestehenden wert_max_chf. Spiegelt das gewicht_min_g /
        # gewicht_max_g-Paar auf die Wert-Achse: waehrend die Gewicht-
        # Extrema die physikalische Massen-Spanne ("leichtestes vs.
        # schwerstes Stueck") beziffern, beziffern die Wert-Extrema die
        # monetaere Spanne ("billigstes vs. teuerstes Stueck"). Ergaenzt
        # damit das wert_max_chf / wert_durchschnitt_chf / wert_median_chf-
        # Trio um die untere Grenze und vervollstaendigt so die Wert-
        # Kennzahlen-Achse symmetrisch zur Gewicht-Achse (gewicht_min_g /
        # gewicht_max_g / gewicht_durchschnitt_g / gewicht_median_g). Reuse
        # der bereits sortierten werte-Liste (ORDER BY w aufsteigend) -
        # werte[0] ist der kleinste Wert > 0, spiegelt den gewichte[0]-
        # Zugriff exakt. Der WHERE-Filter (wert_sql > 0) schliesst Objekte
        # ohne dokumentierten Wert (alle WERT_FELDER NULL oder 0) aus,
        # damit die Minimums-Achse nicht durch nicht-gepflegte Stuecke auf
        # 0 zusammenbricht - spiegelt die objekte_mit_wert-/objekte_mit_
        # gewicht-Konvention. Leere DB / keine Objekte mit Wert → 0.0,
        # spiegelt das gewicht_min_g-Verhalten (Default aus dataclass).
        st.wert_min_chf = werte[0]
        st.wert_median_chf = (werte[n // 2] if n % 2
                              else (werte[n // 2 - 1] + werte[n // 2]) / 2)
        # Wert-Standardabweichung: Dispersions-Achse zur zentralen-Tendenz-
        # Achse (Durchschnitt/Median). Spiegelt mohs_kollektion_standardab-
        # weichung / dichte_kollektion_standardabweichung / gewicht_standard-
        # abweichung_g auf die monetaere Wert-Achse: waehrend Durchschnitt
        # und Median den "typischen" Objekt-Wert beziffern, beziffert die
        # Standardabweichung die Streuung der Werte um den Durchschnitt -
        # eine gleichfoermige Feldspat-Sammlung mit CHF 30..50 pro Stueck
        # zeigt hier ~5, eine gemischte Sammlung mit einzelnen wertvollen
        # Bergkristallen (~CHF 5000) daneben hunderte CHF; Spanne und
        # Zentrums-Kennzahlen allein sehen bei enger vs. weiter Verteilung
        # um denselben Durchschnitt herum identisch aus, erst die Standard-
        # abweichung macht die Verteilungs-Form ueber die Bandbreite hinaus
        # sichtbar (typische versicherungsrelevante Frage: "wie homogen ist
        # meine Sammlung wertlich?" ist ueber Ø und Median allein nicht
        # beantwortbar - eine Sammlung mit Median CHF 100 kann eine
        # gleichfoermige Feldspat-Klasse sein oder ein einzelner Bergkristall
        # dominiert die Versicherungssumme). Vervollstaendigt damit das
        # Wert-Kennzahlen-Sextett (summe/min/max/durchschnitt/median) um die
        # Dispersions-Achse und stellt es strukturell parallel zur Gewicht-
        # Achse auf (gewicht_standardabweichung_g). Reuse der bereits
        # geladenen und sortierten werte-Liste (kein zweiter SQL-Round-Trip,
        # weil werte kurz vorher fuer min/median gefuellt wurde). Populations-
        # Variante (Divisor n statt n-1), spiegelt die _mohs_/_dichte_/
        # gewicht_standardabweichung-Konvention. Numerisch stabile Formel
        # via sum((w - mean)**2) / n statt E[X^2] - E[X]^2, weil Werte in
        # CHF bis in den 10^5-Bereich reichen koennen (Museums-Stuecke,
        # Investment-Mineralien) und die Katastrophal-Kancellations-Version
        # bei grossen Werten mit kleiner Varianz Rundungsfehler erzeugt -
        # spiegelt die gewicht_standardabweichung_g-Formel exakt. Bei einem
        # einzelnen Wert-Eintrag kollabiert die Streuung auf 0.0 (keine
        # Dispersion moeglich); bei leerer DB / ohne jegliche Wert-Pflege
        # bleibt 0.0 (dataclass-Default, spiegelt die uebrigen Wert-
        # Kennzahlen min/max/median/durchschnitt = 0.0 bei leerer DB).
        wert_mean = st.wert_durchschnitt_chf
        st.wert_standardabweichung_chf = (
            sum((w - wert_mean) ** 2 for w in werte) / n) ** 0.5
        # wert_variationskoeffizient_prozent: dimensionslose Dispersions-
        # Achse als Ergaenzung zu wert_standardabweichung_chf. Waehrend die
        # Standardabweichung die Streuung in Original-Einheiten (CHF)
        # beziffert, normiert der Variationskoeffizient sigma auf den
        # Durchschnitt und macht die Streuung damit skalen-unabhaengig
        # vergleichbar - eine 500-CHF-Sammlung mit sigma 50 (CV 10%) hat
        # dieselbe relative Streuung wie eine 5000-CHF-Sammlung mit sigma
        # 500 (CV 10%), obwohl die Absolutwerte um Faktor 10 auseinander-
        # liegen. Beantwortet damit die versicherungs- und portfolio-
        # relevante Frage "wie homogen ist meine Sammlung wertlich, un-
        # abhaengig vom Preis-Niveau?" - eine reine Feldspat-Klasse mit
        # engem Preis-Cluster zeigt hier ~10%, eine gemischte Sammlung
        # mit einzelnen Investment-Bergkristallen dagegen mehrere hundert
        # Prozent. Ergaenzt damit das Wert-Kennzahlen-Sextett (summe/min/
        # max/durchschnitt/median/sigma) um die dimensionslose
        # Dispersions-Achse und macht die Wert-Streuung strukturell
        # vergleichbar mit der Gewicht-/Mohs-/Dichte-Streuung, deren
        # Original-Einheiten (g, Mohs-Punkt, g/cm3) sich sonst nicht
        # miteinander vergleichen lassen. Reuse: greift den bereits
        # berechneten wert_mean und wert_standardabweichung_chf ab (kein
        # zweiter SQL-Round-Trip, keine zweite Listen-Iteration). Ausgabe
        # in Prozent (sigma/mean * 100), weil das die uebliche und
        # intuitivere Darstellung des Variationskoeffizienten ist (statt
        # der dimensionslosen Rohzahl sigma/mean). Bei einem einzelnen
        # Wert-Eintrag oder uniformen Werten kollabiert sigma auf 0.0 und
        # damit CV auf 0.0 (spiegelt wert_standardabweichung_chf-Single-
        # Point-/Uniform-Kollaps). Guarded gegen mean == 0.0 (ist im
        # objekte_mit_wert-Zweig nie der Fall, weil der wert_sql > 0
        # Filter greift, aber die Guard schuetzt fuer den Fall spaeterer
        # Filter-Aenderungen). Bei leerer DB / ohne jegliche Wert-Pflege
        # bleibt None (dataclass-Default), damit as_dict und CLI-Zeile
        # den Undefined-Zustand transparent unterscheiden koennen -
        # anders als sigma (0.0 bei leerer DB) ist CV mathematisch
        # undefined bei mean == 0, nicht 0.0. Spiegelt damit die
        # mohs_kollektion_standardabweichung / dichte_kollektion_
        # standardabweichung-None-Konvention (mean-basierte Groessen mit
        # None statt 0.0 im Undefined-Fall).
        if wert_mean > 0:
            st.wert_variationskoeffizient_prozent = (
                st.wert_standardabweichung_chf / wert_mean * 100.0)
        # wert_spanweite_chf: Spannweite (Range) = wert_max_chf - wert_min_chf
        # als Original-Einheiten-Dispersions-Achse zwischen sigma (Standard-
        # abweichung um den Durchschnitt) und CV (dimensionslose Streuung).
        # Waehrend sigma die durchschnittliche Streuung um den Mittelwert
        # beziffert und Median/Ø den typischen Objekt-Wert benennen, be-
        # ziffert die Spannweite die volle beobachtete Bandbreite - die
        # Distanz zwischen billigstem und teuerstem dokumentierten Stueck
        # in CHF. Ist die einfachste und intuitivste Dispersions-Kennzahl
        # (jeder Sammler versteht "zwischen CHF 10 und CHF 5000" ohne
        # Statistik-Vokabular) und ergaenzt damit das Wert-Kennzahlen-
        # Sextett (summe/min/max/durchschnitt/median/sigma/CV) um die
        # Original-Einheiten-Bandbreiten-Achse. Ist zwar trivial aus min/
        # max ableitbar, aber explizit ausgegeben, damit Dashboard- und
        # Bericht-Konsumenten die Bandbreite ohne zweiten Rechenschritt
        # zur Hand haben (spiegelt die durchschnitt/median-Konvention:
        # ebenfalls aus den werte-Rohdaten ableitbar, aber vorberechnet
        # exponiert). Complement zu sigma: sigma reagiert auf die Vertei-
        # lungsform (breite Streuung um den Mittel = grosses sigma), die
        # Spannweite reagiert nur auf die Extremwerte und ignoriert die
        # Dichte dazwischen - eine Sammlung mit einem einzelnen wertvollen
        # Ausreisser (10 Stuecke a CHF 50 + 1 x CHF 5000) hat eine grosse
        # Spannweite (4950 CHF) trotz kleinem sigma (~1500 CHF); umgekehrt
        # hat eine gleichmaessig ueber CHF 100..1000 verteilte Sammlung ein
        # mittleres sigma und eine mittlere Spannweite. Reuse: greift die
        # bereits gesetzten wert_max_chf und wert_min_chf ab (kein
        # zusaetzlicher SQL-Round-Trip, keine zweite Listen-Iteration).
        # Bei einem einzelnen Wert-Eintrag oder uniformen Werten kollabiert
        # die Spannweite auf 0.0 (min == max, spiegelt die sigma-Uniform-
        # Kollaps-Semantik). Bei leerer DB / ohne jegliche Wert-Pflege
        # bleibt 0.0 (dataclass-Default, spiegelt die uebrigen Wert-
        # Kennzahlen min/max/median/durchschnitt/sigma = 0.0 bei leerer DB
        # - anders als CV, das None bleibt, weil max - min bei leerer DB
        # semantisch 0.0 ist (leere Bandbreite = keine Spanne), waehrend
        # CV mathematisch undefined ist (Division durch mean = 0)).
        st.wert_spanweite_chf = st.wert_max_chf - st.wert_min_chf
    st.top_wert_objekte = [
        (r["obj_id"], r["Name"] or "", float(r["w"]))
        for r in conn.execute(
            f"SELECT obj_id, Name, {wert_sql} AS w FROM objects "
            f"WHERE {wert_sql} > 0 ORDER BY w DESC, obj_id LIMIT ?",
            (int(top_wert),),
        ).fetchall()
    ]
    st.top_gewicht_objekte = [
        (r["obj_id"], r["Name"] or "", float(r["g"]))
        for r in conn.execute(
            "SELECT obj_id, Name, Gewicht_g AS g FROM objects "
            "WHERE Gewicht_g IS NOT NULL AND Gewicht_g > 0 "
            "ORDER BY g DESC, obj_id LIMIT ?",
            (int(top_gewicht),),
        ).fetchall()
    ]
    # Best-fotografierte Objekte (analog top_wert/top_gewicht): zeigt, welche Stuecke
    # die hoechste Bilder-Coverage haben. Aggregiert ueber alle Foto-Kategorien.
    st.top_bilder_objekte = [
        (r["obj_id"], r["Name"] or "", int(r["n"]))
        for r in conn.execute(
            "SELECT o.obj_id AS obj_id, o.Name AS Name, COUNT(i.id) AS n "
            "FROM objects o JOIN images i ON i.obj_id = o.obj_id "
            "GROUP BY o.obj_id, o.Name HAVING n > 0 "
            "ORDER BY n DESC, o.obj_id LIMIT ?",
            (int(top_bilder),),
        ).fetchall()
    ]
    # Top-Confidence-Objekte: am verlaesslichsten identifizierte Stuecke (analog
    # top_wert/top_gewicht/top_bilder). Out-of-Range-Werte (<0 / >100) bleiben
    # ausgeschlossen, damit die Tabelle nicht von kaputten Confidence-Eintraegen
    # dominiert wird (Integrity meldet die separat).
    st.top_confidence_objekte = [
        (r["obj_id"], r["Name"] or "", int(r["c"]))
        for r in conn.execute(
            "SELECT obj_id, Name, Confidence_Prozent AS c FROM objects "
            "WHERE Confidence_Prozent IS NOT NULL "
            "AND Confidence_Prozent BETWEEN 0 AND 100 "
            "ORDER BY c DESC, obj_id LIMIT ?",
            (int(top_confidence),),
        ).fetchall()
    ]
    st.wert_pro_mineral = _sum_by(conn, "Mineral_Primaer", wert_sql, top_wert_mineral)
    # Varietaeten-Wert-Sicht: feinere Aufteilung unter dem Hauptmineral.
    # Komplementaer zu wert_pro_mineral (Hauptgruppe): "Bergkristall" vs.
    # "Milchquarz" innerhalb der Quarz-Familie laufen wertlich oft weit
    # auseinander; der Block zeigt, welche Varietaet das Geld traegt.
    st.wert_pro_varietaet = _sum_by(conn, "Varietaet", wert_sql, top_wert_varietaet)
    # Petrologische Wert-Sicht: welche Gesteinsart traegt den Sammlungswert?
    # Granit-Stuecke vs. Gneis-/Basalt-Stuecke liegen oft auf ganz unterschied-
    # lichen Preis-Niveaus (z.B. Edelgranite vs. Halden-Basalt); der Block
    # macht das transparent, komplementaer zu by_gesteinsart (Anzahl).
    st.wert_pro_gesteinsart = _sum_by(
        conn, "Gesteinsart", wert_sql, top_wert_gesteinsart)
    st.wert_pro_fundort = _sum_by(conn, "Fundort", wert_sql, top_wert_fundort)
    st.wert_pro_kategorie = _sum_by(conn, "Kategorie", wert_sql, top_wert_kategorie)
    # Kristallographische Sicht: welcher Symmetrietyp dominiert wertmaessig?
    # Komplementaer zu by_kristallsystem (Anzahl): trigonal-Quarz koennte ueber
    # viele kleine Stuecke den Wert dominieren, kubisch (Pyrit/Granat) hingegen
    # ueber wenige grosse - der Block macht das sichtbar.
    st.wert_pro_kristallsystem = _sum_by(
        conn, "Kristallsystem", wert_sql, top_wert_kristallsystem)
    # Optische Wert-Sicht: welcher Glanztyp traegt den Sammlungswert? Glasige
    # Quarz-Sammlungen vs. metallische Sulfide vs. matte Sedimentstuecke laufen
    # wertlich oft weit auseinander; der Block macht das transparent.
    # Komplementaer zu by_glanz (Anzahl).
    st.wert_pro_glanz = _sum_by(
        conn, "Glanz", wert_sql, top_wert_glanz)
    # Lichtdurchlaessigkeits-Wert-Sicht: welcher Transparenz-Typ traegt den
    # Sammlungswert? Komplementaer zu by_transparenz (Anzahl) und
    # wert_pro_glanz (Oberflaechen-Reflexion): durchsichtiger Bergkristall vs.
    # durchscheinender Achat vs. opaker Pyrit liegen wertlich oft auf ganz
    # unterschiedlichen Niveaus - der Block macht das transparent. Drei
    # Enum-Werte (durchsichtig/durchscheinend/opak); Limit von 10 reicht ueber-
    # gross, damit alle vorhandenen Stufen durchkommen.
    st.wert_pro_transparenz = _sum_by(
        conn, "Transparenz", wert_sql, top_wert_transparenz)
    # Magnetismus-Wert-Sicht: welcher Eisengehalts-Typ traegt den Sammlungswert?
    # Magnetit/Pyrrhotin-Stuecke (ja) liegen wertlich oft auf einem ganz anderen
    # Niveau als inerte Quarz-/Calcit-Stuecke (nein) oder schwach magnetische
    # Haematit-Stuecke (schwach). Komplementaer zu by_magnetismus (Anzahl) und
    # wert_pro_glanz/wert_pro_transparenz (optische Achsen): hier die
    # physikalische Eisengehalt-Achse.
    st.wert_pro_magnetismus = _sum_by(
        conn, "Magnetismus", wert_sql, top_wert_magnetismus)
    # Spaltbarkeits-Wert-Sicht: welche Spaltflaechen-Klasse traegt den
    # Sammlungswert? Komplementaer zu by_spaltbarkeit (Anzahl): Calcit/Fluorit
    # (vollkommen) ergeben oft viele kleine wertvolle Stuecke, Quarz (keine)
    # traegt ueber wenige grosse Stuecke. Praeparier-relevant: gut spaltbare
    # Stuecke lassen sich saubrer schneiden, was die Polier-Empfehlung und
    # damit Wert_CHF_poliert beeinflusst. Fuenf Enum-Werte aus dem Feld-
    # woerterbuch (vollkommen/gut/deutlich/undeutlich/keine); Limit von 10
    # reicht uebergross, damit alle vorhandenen Stufen durchkommen.
    st.wert_pro_spaltbarkeit = _sum_by(
        conn, "Spaltbarkeit", wert_sql, top_wert_spaltbarkeit)
    # Bruch-Wert-Sicht: welche Bruchverhalten-Klasse traegt den Sammlungswert?
    # Komplementaer zu by_bruch (Anzahl) und wert_pro_spaltbarkeit
    # (Spaltflaechen): muschelig brechende Quarz-/Obsidian-Stuecke liegen
    # wertlich oft auf einem anderen Niveau als fasrige Asbest-/Aktinolith-
    # Stuecke oder hakig-unebene Kupfer-/Silber-Plaettchen. Sechs Enum-Werte
    # aus dem Feldwoerterbuch (muschelig/uneben/splittrig/faserig/erdig/glatt).
    st.wert_pro_bruch = _sum_by(
        conn, "Bruch", wert_sql, top_wert_bruch)
    # Verwendungs-Sicht: wo steckt der Wert je Empfehlung (Schmuck/Sammlung/
    # Forschung/Industrie/Talisman/Dekoration)? Beantwortet "lohnt sich ein
    # Schmuck-Verkauf, oder steckt der Wert eher in Forschungs-/Sammler-Stuecken?".
    st.wert_pro_beste_verwendung = _sum_by(
        conn, "Beste_Verwendung", wert_sql, top_wert_beste_verwendung)
    # status: nur drei Werte (aktiv/platzhalter/archiviert); Limit von 10 reicht
    # uebergross, damit alle vorhandenen Status durchkommen. Beantwortet die Frage
    # "Wieviel Sammlungswert steckt im Archiv vs. aktiv vs. noch unbeschriftet?".
    st.wert_pro_status = _sum_by(conn, "status", wert_sql, 10)
    gewicht_where = "Gewicht_g IS NOT NULL AND Gewicht_g > 0"
    st.gewicht_pro_mineral = _sum_by(
        conn, "Mineral_Primaer", "Gewicht_g", top_gewicht_mineral,
        extra_where=gewicht_where)
    # Spiegelbild zu wert_pro_varietaet: welche Varietaet dominiert
    # gewichtsmaessig? Milchquarz-Geroelle vs. wenige feine Bergkristalle
    # entkoppeln sich oft vom Wert (viel Masse fuer wenig Geld).
    st.gewicht_pro_varietaet = _sum_by(
        conn, "Varietaet", "Gewicht_g", top_gewicht_varietaet,
        extra_where=gewicht_where)
    # Spiegelbild zu wert_pro_gesteinsart: welche Gesteinsart bringt die meiste
    # Masse? Basalt-/Granit-Geroelle dominieren oft die Sammlung gewichts-
    # maessig, ohne wertlich vorne zu liegen - der Block macht das sichtbar.
    st.gewicht_pro_gesteinsart = _sum_by(
        conn, "Gesteinsart", "Gewicht_g", top_gewicht_gesteinsart,
        extra_where=gewicht_where)
    st.gewicht_pro_fundort = _sum_by(
        conn, "Fundort", "Gewicht_g", top_gewicht_fundort,
        extra_where=gewicht_where)
    st.gewicht_pro_kategorie = _sum_by(
        conn, "Kategorie", "Gewicht_g", top_gewicht_kategorie,
        extra_where=gewicht_where)
    # Spiegelbild zu wert_pro_kristallsystem: welcher Symmetrietyp traegt die
    # meiste Masse? Bei Quarz-/Pyrit-lastigen Sammlungen oft entkoppelt vom Wert.
    st.gewicht_pro_kristallsystem = _sum_by(
        conn, "Kristallsystem", "Gewicht_g", top_gewicht_kristallsystem,
        extra_where=gewicht_where)
    # Spiegelbild zu wert_pro_glanz: welcher Glanztyp dominiert gewichtsmaessig?
    # Matte Geroellstuecke (Sediment) tragen oft die Sammlungsmasse, glasige
    # Kristalle den Wert - die Wert/Gewicht-Entkopplung wird auf der optischen
    # Achse sichtbar (analog zu kristallsystem-/varietaet-/gesteinsart-Aufteilung).
    st.gewicht_pro_glanz = _sum_by(
        conn, "Glanz", "Gewicht_g", top_gewicht_glanz,
        extra_where=gewicht_where)
    # Spiegelbild zu wert_pro_transparenz: welcher Transparenz-Typ traegt die
    # meiste Masse? Opake Geroellstuecke (Sediment, Pyrit) dominieren oft die
    # Sammlungsmasse, durchsichtige Kristalle den Wert - die Wert/Gewicht-
    # Entkopplung wird auch auf der Lichtdurchlaessigkeits-Achse sichtbar.
    st.gewicht_pro_transparenz = _sum_by(
        conn, "Transparenz", "Gewicht_g", top_gewicht_transparenz,
        extra_where=gewicht_where)
    # Spiegelbild zu wert_pro_magnetismus: welcher Eisengehalts-Typ traegt die
    # meiste Masse? Schwere Magnetit-Brocken (ja) heben das Gewicht in einer
    # Kategorie, die wertlich oft hinter klassischen Quarz-Stuecken zurueckbleibt.
    # Die Wert/Gewicht-Entkopplung wird auch auf der Magnetismus-Achse sichtbar.
    st.gewicht_pro_magnetismus = _sum_by(
        conn, "Magnetismus", "Gewicht_g", top_gewicht_magnetismus,
        extra_where=gewicht_where)
    # Spiegelbild zu wert_pro_spaltbarkeit: welche Spaltflaechen-Klasse traegt
    # die meiste Masse? Glimmer-Plaettchen (vollkommen) sind oft leicht und
    # zahlreich, dichte Quarz-Brocken (keine) tragen den Schwerteil. Die
    # Wert/Gewicht-Entkopplung wird auch auf der Spaltflaechen-Achse sichtbar.
    st.gewicht_pro_spaltbarkeit = _sum_by(
        conn, "Spaltbarkeit", "Gewicht_g", top_gewicht_spaltbarkeit,
        extra_where=gewicht_where)
    # Spiegelbild zu wert_pro_bruch: welche Bruchverhalten-Klasse traegt die
    # meiste Masse? Dichte muschelig brechende Obsidian-Brocken tragen oft
    # den Schwerteil, fasrige Aktinolith-Buendel bleiben leicht. Die Wert/
    # Gewicht-Entkopplung wird auch auf der Bruchverhalten-Achse sichtbar.
    st.gewicht_pro_bruch = _sum_by(
        conn, "Bruch", "Gewicht_g", top_gewicht_bruch,
        extra_where=gewicht_where)
    # Spiegelbild zu wert_pro_beste_verwendung: welche Verwendungs-Kategorie
    # bringt die meiste Masse? Industrie/Dekoration oft schwer, Schmuck oft
    # leicht aber hochpreisig - der Block macht den Unterschied sichtbar.
    st.gewicht_pro_beste_verwendung = _sum_by(
        conn, "Beste_Verwendung", "Gewicht_g", top_gewicht_beste_verwendung,
        extra_where=gewicht_where)
    st.gewicht_pro_status = _sum_by(
        conn, "status", "Gewicht_g", 10, extra_where=gewicht_where)
    # Zeit-Sicht des Sammlungswerts: "in welchem Funddatum-Jahr ist der hoechste
    # Wert/das hoechste Gewicht zusammengekommen?" Komplementaer zu
    # by_funddatum_jahr (Anzahl): zeigt nicht "wie viele Stuecke", sondern "wie
    # wertvoll/schwer war die Ausbeute". Beantwortet Sammler-Fragen wie "mein
    # bestes Jahr 2019 hatte zwar wenige Funde, aber einen seltenen Riesen-
    # kristall - taucht hier ganz oben auf".
    st.wert_pro_funddatum_jahr = _sum_by_funddatum_jahr(
        conn, wert_sql, top_wert_funddatum_jahr)
    st.gewicht_pro_funddatum_jahr = _sum_by_funddatum_jahr(
        conn, "Gewicht_g", top_gewicht_funddatum_jahr,
        extra_where=gewicht_where)
    # Erfassungs-Achse: wieviel Wert/Gewicht ist pro Erfassungs-Jahr in die
    # Sammlung eingeflossen? Komplementaer zu by_erstellt_am_jahr (Anzahl) und
    # zu wert_/gewicht_pro_funddatum_jahr (Fund- statt Erfassungs-Achse).
    # Macht Migrations-Wellen sichtbar (z.B. grosse Erfassungs-Session 2026
    # mit Altbestaenden), die in der reinen Funddatums-Sicht untergehen.
    st.wert_pro_erstellt_am_jahr = _sum_by_erstellt_am_jahr(
        conn, wert_sql, top_wert_erstellt_am_jahr)
    st.gewicht_pro_erstellt_am_jahr = _sum_by_erstellt_am_jahr(
        conn, "Gewicht_g", top_gewicht_erstellt_am_jahr,
        extra_where=gewicht_where)
    # Aenderungs-Achse: wieviel Wert/Gewicht ist pro Pflege-Jahr in der
    # Sammlung zuletzt redaktionell beruehrt worden? Vervollstaendigt die
    # paarweise Wert/Gewicht-Aggregation auf der dritten Zeit-Achse neben
    # wert_/gewicht_pro_funddatum_jahr (Fund) und wert_/gewicht_pro_erstellt_
    # am_jahr (Erfassung). Bei nie-aktualisierten Alt-Eintraegen konvergiert
    # die Aenderungs-Spitze auf den Erfassungs-Jahrgang (geaendert_am ==
    # erstellt_am im _now()-Pfad); bei aktiv gepflegten Stuecken driftet sie
    # in das aktuelle Pflege-Jahr ab und beziffert damit den wertlichen
    # Schwerpunkt der letzten Datenpflege-Aktivitaet.
    st.wert_pro_geaendert_am_jahr = _sum_by_geaendert_am_jahr(
        conn, wert_sql, top_wert_geaendert_am_jahr)
    st.gewicht_pro_geaendert_am_jahr = _sum_by_geaendert_am_jahr(
        conn, "Gewicht_g", top_gewicht_geaendert_am_jahr,
        extra_where=gewicht_where)
    # Erfassungs-Saison-Ertrag: welcher Monat des Jahres bringt ueber alle Jahre
    # den hoechsten Erfassungs-Wert/-Masse-Eintrag? Komplementaer zu
    # by_erstellt_am_monat (Anzahl) und wert_/gewicht_pro_funddatum_monat (Fund-
    # Saison): typische Indoor-Erfassungs-Spitzen (Winter, Boersenvorbereitung
    # Januar-Maerz) entkoppeln sich oft vom Fund-Saison-Profil.
    st.wert_pro_erstellt_am_monat = _sum_by_erstellt_am_monat(conn, wert_sql)
    st.gewicht_pro_erstellt_am_monat = _sum_by_erstellt_am_monat(
        conn, "Gewicht_g", extra_where=gewicht_where)
    # Aenderungs-Saison-Ertrag: welcher Monat des Jahres bringt ueber alle Jahre
    # den hoechsten Pflege-Wert/-Masse-Eintrag? Komplementaer zu
    # by_geaendert_am_monat (Anzahl) und wert_/gewicht_pro_erstellt_am_monat
    # (Erfassungs-Saison): bei nie-aktualisierten Alt-Eintraegen konvergiert
    # die Aenderungs-Saison auf die Erfassungs-Saison; bei aktiv gepflegten
    # Stuecken driftet die wertliche/gewichtmaessige Pflege-Spitze in das
    # aktuelle Pflege-Monat ab. Schliesst das Monats-Trio (Fund/Erfassung/
    # Aenderung) auf der dritten Zeit-Achse ab.
    st.wert_pro_geaendert_am_monat = _sum_by_geaendert_am_monat(conn, wert_sql)
    st.gewicht_pro_geaendert_am_monat = _sum_by_geaendert_am_monat(
        conn, "Gewicht_g", extra_where=gewicht_where)
    # Dekaden-Sicht des Sammlungswerts: "in welchem Jahrzehnt habe ich am meisten
    # Wert/Masse zusammengetragen?". Komplementaer zu wert_pro_funddatum_jahr
    # (Einzeljahres-Rauschen): zeigt grobe Aktivitaetsphasen ohne Verzerrung
    # durch einzelne Ausreisserjahre. Ohne Limit (max ~10-15 Dekaden).
    st.wert_pro_funddatum_jahrzehnt = _sum_by_funddatum_jahrzehnt(conn, wert_sql)
    st.gewicht_pro_funddatum_jahrzehnt = _sum_by_funddatum_jahrzehnt(
        conn, "Gewicht_g", extra_where=gewicht_where)
    # Erfassungs-Dekaden-Sicht des Sammlungswerts: spiegelt wert_/gewicht_pro_
    # funddatum_jahrzehnt auf die Erfassungs-Achse. Aggregiert das Erfassungs-
    # Jahres-Histogramm (wert_/gewicht_pro_erstellt_am_jahr) wertlich/gewichts-
    # maessig auf 10er-Schritte und macht uebergreifende Erfassungs-Wellen
    # sichtbar - typisch eine Excel-Migrations-Welle 2020+ vs. handgepflegte
    # 2010er-Phase, die im Einzeljahr-Histogramm durch Rauschen verdeckt sind.
    # Ohne Limit, weil die Zahl der Dekaden klein bleibt (~3-5 ueber eine
    # Sammler-Karriere, analog zu wert_/gewicht_pro_funddatum_jahrzehnt).
    st.wert_pro_erstellt_am_jahrzehnt = _sum_by_erstellt_am_jahrzehnt(conn, wert_sql)
    st.gewicht_pro_erstellt_am_jahrzehnt = _sum_by_erstellt_am_jahrzehnt(
        conn, "Gewicht_g", extra_where=gewicht_where)
    # Aenderungs-Dekaden-Sicht: spiegelt wert_/gewicht_pro_erstellt_am_jahrzehnt
    # auf die Pflege-Achse - in welcher Dekade ist wertlich/gewichtsmaessig am
    # meisten redaktionell beruehrt worden? Vervollstaendigt die Dekaden-Sicht
    # auf der dritten Zeit-Achse neben Fund und Erfassung. Bei nie-aktualisierten
    # Alt-Eintraegen konvergiert die Dekaden-Spitze auf die Erfassungs-Dekade;
    # bei aktiv gepflegten Stuecken driftet sie in die aktuelle Pflege-Dekade.
    # Ohne Limit, weil die Zahl der Dekaden klein bleibt.
    st.wert_pro_geaendert_am_jahrzehnt = _sum_by_geaendert_am_jahrzehnt(conn, wert_sql)
    st.gewicht_pro_geaendert_am_jahrzehnt = _sum_by_geaendert_am_jahrzehnt(
        conn, "Gewicht_g", extra_where=gewicht_where)
    # Saison-Sicht des Sammlungswerts: "welcher Monat bringt am meisten Wert/
    # Gewicht?". Komplementaer zu by_funddatum_monat (Anzahl): zeigt nicht
    # "wie oft sammle ich im Juli", sondern "wie ergiebig ist die Juli-Saison".
    # Berg-Saison (Jul/Aug) gegen Boersen-Spitzen (Dez/Feb) werden so
    # vergleichbar; keine Limit-Parameter, weil max 12 Eintraege moeglich.
    st.wert_pro_funddatum_monat = _sum_by_funddatum_monat(conn, wert_sql)
    st.gewicht_pro_funddatum_monat = _sum_by_funddatum_monat(
        conn, "Gewicht_g", extra_where=gewicht_where)
    # Rarity-Wert-/Gewicht-Sicht: wie verteilt sich Sammlungswert/Masse auf der
    # globalen Seltenheits-Skala (1..10)? Komplementaer zu by_seltenheit_global
    # (Anzahl): zeigt nicht "wie viele Stuecke pro Stufe", sondern "wo steckt
    # der Wert/das Gewicht" - typisch konzentriert sich der Wert in den oberen
    # Stufen (>=8 Rarit?ten), waehrend das Gewicht in der haeufigen Masse (<=3)
    # liegt. Skala-Spalte wird ueber SCALE_1_10_COLUMNS validiert.
    st.wert_pro_seltenheit_global = _sum_by_scale_1_10(
        conn, "Seltenheit_global_1_10", wert_sql)
    st.gewicht_pro_seltenheit_global = _sum_by_scale_1_10(
        conn, "Seltenheit_global_1_10", "Gewicht_g",
        extra_where=gewicht_where)
    # Standort-Rarity-Wert-/Gewicht-Sicht: spiegelt wert_/gewicht_pro_seltenheit_global,
    # diesmal auf der lokalen Skala. Am Standort haeufiger Quarz (lokal niedrig)
    # kann global selten und damit wertvoll sein - oder umgekehrt: eine lokale
    # Rarit?t aus einem ausgeschoepften Stollen wertet weniger als global selten.
    # Beide Aggregate zusammen zeigen, ob "lokale Spitze" und "globale Spitze"
    # zusammenfallen oder auseinanderdriften (interessant fuer Sammlungs-Schwerpunkte).
    st.wert_pro_seltenheit_fundort = _sum_by_scale_1_10(
        conn, "Seltenheit_Fundort_1_10", wert_sql)
    st.gewicht_pro_seltenheit_fundort = _sum_by_scale_1_10(
        conn, "Seltenheit_Fundort_1_10", "Gewicht_g",
        extra_where=gewicht_where)
    # Marktnachfrage-Wert-/Gewicht-Sicht: wo liegt der Verkaufs-Druck im
    # Sammlungs-Wert/-Gewicht? Komplementaer zu by_nachfrage (Anzahl) und
    # nachfrage_min/max-Filter (Drill-down auf einzelne Stuecke): zeigt, ob
    # die hochpreisigen Stuecke gerade auf den begehrten Skalen-Stufen (>=7)
    # liegen oder ob das Geld in Tauschmaterial (<=3) gebunden ist.
    # Sammler-typisch vor Boersenbesuch: "habe ich genug verkaufsfaehige Masse,
    # oder traegt die Verkaufs-Spitze nur Einzelstuecke?".
    st.wert_pro_nachfrage = _sum_by_scale_1_10(
        conn, "Nachfrage_1_10", wert_sql)
    st.gewicht_pro_nachfrage = _sum_by_scale_1_10(
        conn, "Nachfrage_1_10", "Gewicht_g",
        extra_where=gewicht_where)
    # Confidence-Wert-Sicht: wieviel Sammlungswert haengt an "sicheren"
    # Bestimmungen (75-100) vs. an noch unsicheren Stuecken (<50) vs. an
    # unbestimmten Stuecken (Confidence NULL, Bucket 'ohne')? Spiegelt
    # confidence_buckets (Anzahl) auf die Wert-Achse: konzentriert sich der
    # Sammlungswert dort, wo die KI sicher ist - oder steckt er gerade in
    # den noch zu pruefenden Stuecken, deren Pruefempfehlungen prioritaer
    # sind? Komplementaer zu top_confidence_objekte (Spitze) und
    # durchschnitt_/median_confidence_prozent (zentrale Tendenz).
    st.wert_pro_confidence_bucket = _sum_by_confidence_bucket(conn, wert_sql)
    # Spiegelbild zu wert_pro_confidence_bucket: wieviel Sammlungs-Gewicht
    # haengt an unbestimmten Stuecken (Bucket 'ohne') vs. an sicher
    # identifizierten (75-100)? Wert/Gewicht-Entkopplung auf der Confidence-
    # Achse: typisch sitzen schwere Geroellstuecke ohne KI-Analyse im
    # 'ohne'-Bucket, waehrend wertvolle Kristalle mit klarer Bestimmung den
    # 75-100-Bucket fuellen - der Block macht das transparent.
    st.gewicht_pro_confidence_bucket = _sum_by_confidence_bucket(
        conn, "Gewicht_g", extra_where=gewicht_where)
    return st
