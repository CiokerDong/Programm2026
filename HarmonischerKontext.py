"""Aufbau einer einheitlichen Zeitliste harmonischer Segmente.

Die Hilfsstimme bestimmt weiterhin den Modus eines Bereichs.  Bereiche im
Modus ``Standard`` werden zusaetzlich mit dem automatisch ermittelten
harmonischen Kontext angereichert.  Alle Modi werden nach aussen durch
denselben Datentyp :class:`Harmoniesegment` dargestellt.
"""

from __future__ import annotations
from dataclasses import dataclass
import math
import re
from typing import Any, Optional, Sequence

from music21 import chord, interval, note, stream
from Klang import Beurteilung_dissonanten_Klangs, Bildung_Klanggerüst
from Notenbearbeitung import (
    Noten_am_Offset,
    notes_in_time_span,
    weglassen_doppelte_Noten,
)


@dataclass
class Harmoniesegment:
    """Ein Modus- und Harmonieabschnitt der Partitur.

    Nicht jeder Modus benoetigt alle Felder.  Die Feldnamen entsprechen den
    bisherigen Schluesseln der von ``Modi_auf_der_Hiflsstimme`` erzeugten
    Dictionaries.  ``get`` und ``__getitem__`` erleichtern die schrittweise
    Migration bestehender Aufrufer.
    """

    Modus: str
    Anfang: float
    Ende: float
    Kennzeichen: Any = ""
    HarmonieAnfang: Optional[float] = None
    Bass: Optional[note.Note] = None
    Gerüstbass: Optional[note.Note] = None
    Annotationston: Optional[note.Note] = None
    Klang: Optional[chord.Chord] = None
    Klanggerüst: Optional[chord.Chord] = None
    Tönenamen: Any = None
    Klangdissonanzname: Any = None
    Akkordeigene_Töne: Any = None
    Akkorddissonanz: Any = None
    Töne_am_Anfang: Any = None
    Zahl: Optional[int] = None
    Kategorie: Any = None
    Qualität: Optional[bool] = None
    Septakkord: Any = None
    Orgelpunkt: Any = None
    Hilfstimme_Kontext: Any = None
    hat_harmonischen_kontext: bool = False

    def enthält(self, offset, tol: float = 1e-6) -> bool:
        """Halboffene Zugehoerigkeit: ``Anfang <= offset < Ende``."""
        zeit = float(offset)
        return (
            zeit >= self.Anfang - tol
            and zeit < self.Ende
            and not math.isclose(zeit, self.Ende, abs_tol=tol)
        )

    def get(self, key: str, default=None):
        return getattr(self, key, default)

    def __getitem__(self, key: str):
        try:
            return getattr(self, key)
        except AttributeError as exc:
            raise KeyError(key) from exc


class HarmonischerKontext:
    """Erzeugt und indiziert Harmoniesegmente fuer die gesamte Partitur."""

    def __init__(
        self,
        score: stream.Score,
        Grenzen,
        score_slices,
        Original_Slices,
        hilfsstimme_index: int = -1,
    ):
        self.score = score
        self.Grenzen = [float(grenze) for grenze in Grenzen]
        self.score_slices = score_slices
        self.Original_Slices = Original_Slices
        self.hilfsstimme_index = hilfsstimme_index
        self._modusbereiche: list[Harmoniesegment] = []
        self._standardsegmente: list[Harmoniesegment] = []
        self.Segmente: list[Harmoniesegment] = []
        self._erstellt = False

    def erstelle_segmente(self) -> list[Harmoniesegment]:
        """Erstellt die gemeinsame Segmentzeitleiste genau einmal."""
        if self._erstellt:
            return self.Segmente

        self._modusbereiche = self._erstelle_modusbereiche()
        self._standardsegmente = self._erstelle_standardsegmente()
        self.Segmente = sorted(
            [
                segment
                for segment in self._modusbereiche
                if segment.Modus != "Standard"
            ]
            + self._standardsegmente,
            key=lambda segment: (segment.Anfang, segment.Ende),
        )
        self._erstellt = True
        return self.Segmente

    def segment_bei(self, offset) -> Optional[Harmoniesegment]:
        """Gibt fuer ``offset`` unabhaengig vom Modus denselben Segmenttyp zurueck."""
        if not self._erstellt:
            self.erstelle_segmente()

        modusbereich = self._modusbereich_bei(offset)
        if modusbereich is None:
            return None
        if modusbereich.Modus != "Standard":
            return modusbereich

        for segment in self._standardsegmente:
            if segment.enthält(offset):
                return segment

        # Kein automatisch bestimmbarer harmonischer Slice: Der Standardmodus
        # bleibt dennoch bekannt, wie zuvor durch den Rest der Hilfsstimme.
        return modusbereich

    def _modusbereich_bei(self, offset) -> Optional[Harmoniesegment]:
        for segment in self._modusbereiche:
            if segment.enthält(offset):
                return segment
        return None

    def _erstelle_modusbereiche(self) -> list[Harmoniesegment]:
        stimmen = list(self.score.parts)
        if not stimmen:
            return []
        hilfsstimme = stimmen[self.hilfsstimme_index].flatten()
        elemente = list(hilfsstimme.notesAndRests)
        modi: list[Harmoniesegment] = []

        i = 0
        while i < len(elemente):
            i0 = i
            anfang, ende, i = Zusammenstellung_verbundener_Noten(elemente, i)
            if ende <= anfang:
                continue

            element = elemente[i0]
            töne_im_bereich = notes_in_time_span(
                self.Original_Slices, anfang, ende
            )
            kennzeichen = element.lyric if element.lyric else []

            if element.isRest:
                modi.append(Harmoniesegment("Standard", anfang, ende))
                continue

            if any(zeichen.isdigit() for zeichen in kennzeichen):
                modi.append(
                    self._erstelle_alberti_segment(
                        element,
                        elemente,
                        i0,
                        anfang,
                        ende,
                        kennzeichen,
                        töne_im_bereich,
                    )
                )
                continue

            if kennzeichen == "Op":
                modi.append(
                    Harmoniesegment(
                        Modus="Orgelpunkt",
                        Anfang=anfang,
                        Ende=ende,
                        Kennzeichen=kennzeichen,
                        HarmonieAnfang=anfang,
                        Orgelpunkt={element.nameWithOctave},
                    )
                )
                continue

            modi.append(
                self._erstelle_figurationssegment(
                    element,
                    elemente,
                    i0,
                    anfang,
                    ende,
                    kennzeichen,
                    töne_im_bereich,
                )
            )

        modi.sort(key=lambda segment: segment.Anfang)
        zusammensetzung: list[Harmoniesegment] = []
        for ausschnitt in modi:
            if (
                zusammensetzung
                and zusammensetzung[-1].Modus == "Standard"
                and ausschnitt.Modus == "Standard"
                and math.isclose(
                    ausschnitt.Anfang,
                    zusammensetzung[-1].Ende,
                    abs_tol=1e-9,
                )
            ):
                zusammensetzung[-1].Ende = ausschnitt.Ende
            else:
                zusammensetzung.append(ausschnitt)
        return zusammensetzung

    def _erstelle_alberti_segment(
        self,
        element,
        elemente,
        i0,
        anfang,
        ende,
        kennzeichen,
        töne_im_bereich,
    ) -> Harmoniesegment:
        zahl = int(re.search(r"\d+", kennzeichen).group())
        basston = min(element.notes, key=lambda n: n.pitch.midi) if element.isChord else element
        annotationston = basston
        if zahl == 0:
            klanggerüst_roh = chord.Chord(töne_im_bereich)
        else:
            klanggerüst_roh = Bildung_Klanggerüst(
                töne_im_bereich, zahl, element
            )

        töne_am_modusanfang = list(
            Noten_am_Offset(self.Original_Slices, anfang) or []
        )
        namen_im_klanggerüst = {n.name for n in klanggerüst_roh.notes}
        hilfstimme_kontext = (annotationston, elemente, i0)
        Beurteilung = Beurteilung_dissonanten_Klangs(
            klanggerüst_roh,
            zahl,
            kennzeichen,
            anfang,
            töne_im_bereich,
            Hilfstimme_Kontext=hilfstimme_kontext,
            Original_Slices=self.Original_Slices,
        )
        akkorddissonanz = Beurteilung.get("dissonant_notes")
        
        akkordeigene_töne = Beurteilung.get("akkordtöne")
        kategorie = Beurteilung.get("category")
        klanggerüst = chord.Chord(list(akkordeigene_töne))
        töne_am_modusanfang = [
            n for n in töne_am_modusanfang if n.name not in namen_im_klanggerüst
        ]
        klanggerüst_alle = chord.Chord(
            list(klanggerüst.notes) + töne_am_modusanfang
        )

        # Bestehende Entscheidung Alberti/Alberti_mit_Kontrapunkt unveraendert.
        gerüsttöne_nur_einstimmig = None
        genaue_namen = {n.nameWithOctave for n in klanggerüst_roh.notes}
        alle_gerüsttöne = [
            n for n in töne_im_bereich if n.nameWithOctave in genaue_namen
        ]
        alle_gerüsttönenamen = [n.nameWithOctave for n in alle_gerüsttöne]
        if len(alle_gerüsttönenamen) == len(set(alle_gerüsttönenamen)):
            verdoppelte_oktave = []
            for n in töne_im_bereich:
                intervall = interval.Interval(annotationston, n)
                if intervall.generic.directed == 8 and intervall.name == "P8":
                    verdoppelte_oktave.append(n)
            if len(verdoppelte_oktave) < 2:
                gerüsttöne_nur_einstimmig = not haben_vertikale_Überlappung(
                    alle_gerüsttöne
                )

        modus = (
            "Alberti_mit_Kontrapunkt"
            if gerüsttöne_nur_einstimmig
            else "Alberti"
        )
        return Harmoniesegment(
            Modus=modus,
            Anfang=anfang,
            Ende=ende,
            Kennzeichen=kennzeichen,
            HarmonieAnfang=anfang,
            Klanggerüst=klanggerüst,
            Töne_am_Anfang=klanggerüst_alle,
            Zahl=zahl,
            Kategorie=kategorie,
            Annotationston=annotationston,
            Hilfstimme_Kontext=hilfstimme_kontext,
            Bass=basston,
            Akkordeigene_Töne=akkordeigene_töne,
            Akkorddissonanz=akkorddissonanz,
        )

    def _erstelle_figurationssegment(
        self,
        element,
        elemente,
        i0,
        anfang,
        ende,
        kennzeichen,
        töne_im_bereich,
    ) -> Harmoniesegment:
        töne_am_modusanfang = list(
            Noten_am_Offset(self.Original_Slices, anfang) or []
        )
        zum_akkord = chord.Chord(töne_am_modusanfang)
        basston = min(element.notes, key=lambda n: n.pitch.midi) if element.isChord else element
        annotationston = basston
        hilfstimme_kontext = (annotationston, elemente, i0)
        beurteilung = Beurteilung_dissonanten_Klangs(
            zum_akkord,
            None,
            kennzeichen,
            anfang,
            töne_im_bereich,
            Hilfstimme_Kontext=hilfstimme_kontext,
            Original_Slices=self.Original_Slices,
        )
        klangdissonanz = beurteilung.get("dissonant_notes")
        if klangdissonanz:
            konsonant = False
            akkorddissonanz = klangdissonanz
            akkordeigene_töne = beurteilung.get("akkordtöne")
        else:
            konsonant = True
            akkorddissonanz = None
            akkordeigene_töne = None

        return Harmoniesegment(
            Modus="Figuration",
            Anfang=anfang,
            Ende=ende,
            Kennzeichen=kennzeichen,
            HarmonieAnfang=anfang,
            Qualität=konsonant,
            Annotationston=annotationston,
            Hilfstimme_Kontext=hilfstimme_kontext,
            Bass=basston,
            Klang=zum_akkord,
            Akkordeigene_Töne=akkordeigene_töne,
            Akkorddissonanz=akkorddissonanz,
        )

    def _erstelle_standardsegmente(self) -> list[Harmoniesegment]:
        segmente: list[Harmoniesegment] = []
        for bereich in self._modusbereiche:
            if bereich.Modus != "Standard":
                continue

            aktiver_slice: Optional[Harmoniesegment] = None
            for anfang in self.Grenzen[:-1]:
                if not bereich.enthält(anfang):
                    continue

                originaltöne = Noten_am_Offset(self.Original_Slices, anfang)
                if not originaltöne or len(originaltöne) < 2:
                    continue

                töne_alle = Noten_am_Offset(self.score_slices, anfang) or []
                töne_am_anfang = [
                    n for n in töne_alle if not n.duration.isGrace
                ]
                töne_am_anfang = weglassen_doppelte_Noten(
                    töne_am_anfang, modus="offset"
                )
                if not töne_am_anfang:
                    continue

                gerüstbass = min(töne_am_anfang, key=lambda n: n.pitch.midi)
                if len(töne_am_anfang) == 2:
                    l1 = töne_am_anfang[0].duration.quarterLength
                    l2 = töne_am_anfang[1].duration.quarterLength
                    if l1 != l2:
                        gerüstbass = (
                            töne_am_anfang[0]
                            if l1 > l2
                            else töne_am_anfang[1]
                        )

                Harmonieanfang = float(gerüstbass.abs_offset)
                Harmonieende = Harmonieanfang + float(gerüstbass.quarterLength)
                if (
                    aktiver_slice is not None
                    and aktiver_slice.HarmonieAnfang is not None
                    and Harmonieanfang >= aktiver_slice.HarmonieAnfang - 1e-6
                    and Harmonieanfang < aktiver_slice.Ende
                    and not math.isclose(Harmonieanfang, aktiver_slice.Ende, abs_tol=1e-6)
                ):
                    continue

                aktiver_slice = None
                if len(töne_am_anfang) < 2 or Harmonieende <= Harmonieanfang:
                    continue

                tönenamen = {ton.name for ton in töne_am_anfang}
                töne_im_bereich = notes_in_time_span(
                    self.Original_Slices, Harmonieanfang, Harmonieende
                )
                beurteilung = Beurteilung_dissonanten_Klangs(
                    chord.Chord(töne_am_anfang),
                    None,
                    None,
                    None,
                    töne_im_bereich,
                    Original_Slices=self.Original_Slices,
                )
                dissonantklang = beurteilung.get("dissonant_notes")
                dissonantklangnamen = [n.name for n in dissonantklang]
                if dissonantklang:
                    tönenamen = [n.name for n in beurteilung.get("akkordtöne")]

                effektiver_anfang = max(Harmonieanfang, bereich.Anfang)
                effektives_ende = min(Harmonieende, bereich.Ende)
                if effektives_ende <= effektiver_anfang:
                    continue
                aktiver_slice = Harmoniesegment(
                    Modus="Standard",
                    Anfang=effektiver_anfang,
                    Ende=effektives_ende,
                    HarmonieAnfang=Harmonieanfang,
                    Bass=gerüstbass,
                    Gerüstbass=gerüstbass,
                    Klang=chord.Chord(töne_am_anfang),
                    Tönenamen=tönenamen,
                    Klangdissonanzname=dissonantklangnamen,
                    hat_harmonischen_kontext=True,
                )
                segmente.append(aktiver_slice)

        return segmente


def haben_vertikale_Überlappung(noten, TOL: float = 1e-6) -> bool:
    """Prueft, ob sich klingende Zeitintervalle der Noten ueberlappen."""
    intervalle = sorted((float(n.abs_offset), float(n.end)) for n in noten)
    groesstes_ende = float("-inf")
    for anfang, ende in intervalle:
        if anfang < groesstes_ende - TOL:
            return True
        groesstes_ende = max(groesstes_ende, ende)
    return False


def Zusammenstellung_verbundener_Noten(Elemente, i: int):
    """Fasst eine vollstaendige Tie-Kette zu einem Bereich zusammen."""
    element = Elemente[i]
    anfang = float(element.offset)
    gesamtdauer = float(element.quarterLength)

    if isinstance(element, note.Rest):
        return anfang, float(element.offset + element.quarterLength), i + 1

    if isinstance(element, note.Note):
        if not element.tie or element.tie.type not in ("start", "continue"):
            return anfang, float(element.offset + element.quarterLength), i + 1
        j = i + 1
        while j < len(Elemente):
            nächste_note = Elemente[j]
            gesamtdauer += float(nächste_note.quarterLength)
            if nächste_note.tie.type == "stop":
                j += 1
                break
            j += 1
        return anfang, float(element.offset + gesamtdauer), j

    if isinstance(element, chord.Chord):
        tie_map = _chord_tie_types_by_pitch(element)
        pitches = set(tie_map)
        if not pitches or any(
            tie_map[p] not in ("start", "continue") for p in pitches
        ):
            return anfang, float(element.offset + element.quarterLength), i + 1

        j = i + 1
        while j < len(Elemente):
            nächste_note = Elemente[j]
            if not isinstance(nächste_note, chord.Chord):
                break
            nächste_map = _chord_tie_types_by_pitch(nächste_note)
            if set(nächste_map) != pitches:
                break
            if any(
                nächste_map[p] not in ("continue", "stop") for p in pitches
            ):
                break
            gesamtdauer += float(nächste_note.quarterLength)
            if all(nächste_map[p] == "stop" for p in pitches):
                j += 1
                break
            j += 1
        return anfang, float(element.offset + gesamtdauer), j

    return anfang, float(element.offset + element.quarterLength), i + 1


def _tie_type(n):
    return None if n.tie is None else n.tie.type


def _chord_tie_types_by_pitch(ch):
    return {n.pitch: _tie_type(n) for n in ch.notes}
