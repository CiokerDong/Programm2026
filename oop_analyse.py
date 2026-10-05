"""MusicXML mit dem neuen objektorientierten Programm untersuchen."""

import argparse
import csv
from collections import Counter

from music21 import converter

from oop_programm import AnalyseProgramm


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("partitur", help="Pfad zu MusicXML oder einer music21-Datei")
    parser.add_argument("--output", help="CSV-Datei für die Einzeltonbefunde")
    parser.add_argument(
        "--no-helper", action="store_true",
        help="Die Partitur enthält keine Hilfsstimme (sonst letzte Stimme)",
    )
    args = parser.parse_args()
    score = converter.parse(args.partitur)
    programm = AnalyseProgramm(score, None if args.no_helper else -1)
    befunde = programm.analysiere()

    if args.output:
        with open(args.output, "w", newline="", encoding="utf-8-sig") as datei:
            writer = csv.writer(datei)
            writer.writerow((
                "Offset", "Ton", "Segmentanfang", "Segmentende",
                "Modus", "Segmentquelle", "Geruestbass", "Bezifferung",
                "Klangkategorie", "Partner", "Status", "Typ", "Begruendung",
            ))
            for b in befunde:
                writer.writerow((
                    b.offset, b.ton.nameWithOctave, b.kontext.anfang,
                    b.kontext.ende, b.kontext.modus, b.kontext.quelle,
                    b.kontext.geruestbass.nameWithOctave
                    if b.kontext.geruestbass else "",
                    b.kontext.bezifferung if b.kontext.bezifferung is not None else "",
                    b.klang.kategorie or "",
                    ", ".join(n.nameWithOctave for n in b.partner),
                    b.status, b.typ or "", "; ".join(b.begruendung),
                ))
        print(f"{len(befunde)} Befunde nach {args.output} geschrieben.")
    else:
        print(f"{len(programm.kontexte)} Segmente, {len(befunde)} Befunde.")
        for status, zahl in Counter(b.status for b in befunde).items():
            print(f"  {status}: {zahl}")


if __name__ == "__main__":
    main()
