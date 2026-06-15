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
    if st.by_fundort:
        lines += ["", "Top-Fundorte:"]
        for name, n in list(st.by_fundort.items())[:top]:
            lines.append(f"  {name:40s} {n}")
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
    if st.wert_pro_mineral:
        # Beantwortet "Welcher Mineraltyp ist insgesamt am wertvollsten?"
        # (komplementaer zu top_wert_objekte, das das wertvollste Einzelstueck zeigt).
        # Summen aus wert_pro_objekt_sql() ueber alle CHF-Felder pro Mineral-Gruppe.
        lines += ["", "Wert pro Mineral (CHF):"]
        for mineral, wert in st.wert_pro_mineral[:top]:
            lines.append(f"  {mineral:40s} {wert:>12,.0f}")
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
            top_wert_mineral=args.top, top_gewicht_mineral=args.top,
            top_wert_fundort=args.top, top_gewicht_fundort=args.top,
            top_wert_kategorie=args.top, top_gewicht_kategorie=args.top,
            top_gewicht=args.top)
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
