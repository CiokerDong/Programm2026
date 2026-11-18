"""Objektorientierter Einstieg für die Analyse von Programm2026.

Segmentbildung, Klangbefund und Einzeltonbefund haben gemeinsame Schnittstellen.
Die sicheren Grundregeln sind hier neu implementiert; komplexe Spezialfälle der
alten Module müssen separat übertragen werden. Unklare Fälle bleiben offen.
"""

from __future__ import annotations

from bisect import bisect_right
from dataclasses import dataclass, field
import re

from music21 import chord, interval, note, stream

TOL = 1e-6


class PartiturIndex:
    """Zeitindex der musikalischen Stimmen, ohne die optionale Hilfsstimme."""

    def __init__(self, score: stream.Score, hilfsstimme_index: int | None = -1):
        self.score = score
        self.parts = list(score.parts)
        if not self.parts:
            raise ValueError("Die Partitur hat keine Stimmen.")
        self.hilfsstimme = (
            self.parts[hilfsstimme_index] if hilfsstimme_index is not None else None
        )
        self.musikstimmen = [
            part for part in self.parts if part is not self.hilfsstimme
        ]
        if not self.musikstimmen:
            raise ValueError("Es gibt keine musikalische Stimme neben der Hilfsstimme.")

        self.ereignisse: list[note.Note] = []
        self._besitzer: dict[int, stream.Stream] = {}
        grenzen = {0.0}
        for part in self.musikstimmen:
            for element in part.flatten().notes:
                start = float(element.offset)
                tones = element.notes if isinstance(element, chord.Chord) else (element,)
                for ton in tones:
                    if not isinstance(ton, note.Note):
                        continue
                    ton.abs_offset = start
                    ton.end = start + float(ton.quarterLength)
                    self._besitzer[id(ton)] = part
                    self.ereignisse.append(ton)
                    grenzen.update((start, ton.end))

        if self.hilfsstimme is not None:
            for element in self.hilfsstimme.flatten().notesAndRests:
                grenzen.update(
                    (float(element.offset), float(element.offset + element.quarterLength))
                )
        self.ereignisse.sort(key=lambda ton: (ton.abs_offset, ton.pitch.midi))
        self.grenzen = sorted(grenzen)
        self.dauer = self.grenzen[-1]
        self.slices = [
            {"offset": start, "elements": self.noten_bei(start)}
            for start in self.grenzen[:-1]
        ]

    def noten_bei(self, offset: float) -> list[note.Note]:
        """Alle zu diesem Zeitpunkt klingenden Noten; das Ende ist exklusiv."""
        return [
            n for n in self.ereignisse
            if n.abs_offset <= offset + TOL and n.end > offset + TOL
        ]

    def noten_im_bereich(self, anfang: float, ende: float) -> list[note.Note]:
        return [
            n for n in self.ereignisse
            if anfang - TOL <= n.abs_offset < ende - TOL
        ]

    def _gleiche_linie(self, a: note.Note, b: note.Note) -> bool:
        va, vb = a.getContextByClass(stream.Voice), b.getContextByClass(stream.Voice)
        if va is not None or vb is not None:
            return va is not None and va is vb
        return self._besitzer.get(id(a)) is self._besitzer.get(id(b))

    def nachbarn(self, ton: note.Note) -> tuple[note.Note | None, note.Note | None]:
        """Nur eindeutige, unmittelbar benachbarte Ereignisse derselben Linie.

        Ohne explizite Voice führt gleichzeitige Mehrstimmigkeit zu (None, None).
        So werden Klavierakkorde nicht stillschweigend als Melodie gelesen.
        """
        linie = [n for n in self.ereignisse if self._gleiche_linie(n, ton)]
        if any(
            n is not ton and n.abs_offset < ton.end - TOL
            and n.end > ton.abs_offset + TOL
            for n in linie
        ):
            return None, None
        vorher = [n for n in linie if abs(n.end - ton.abs_offset) <= TOL]
        nachher = [n for n in linie if abs(n.abs_offset - ton.end) <= TOL]
        return (
            vorher[0] if len(vorher) == 1 else None,
            nachher[0] if len(nachher) == 1 else None,
        )


@dataclass
class HarmonischerKontext:
    """Ein Segment einschließlich seiner Herkunft und Gerüstinformation."""

    anfang: float
    ende: float
    modus: str
    quelle: str
    geruestbass: note.Note | None = None
    bezifferung: int | None = None
    annotationston: note.Note | None = None
    klanggeruest: chord.Chord | None = None
    kennzeichen: str = ""
    hilfsstimme_kontext: tuple | None = field(default=None, repr=False)
    hinweise: tuple[str, ...] = ()

    def enthaelt(self, offset: float) -> bool:
        return self.anfang - TOL <= offset < self.ende - TOL

    @staticmethod
    def _verbundenes_ende(elemente: list, i: int) -> tuple[float, int]:
        """Vollständig gebundene Noten/Chords zu einem Hilfsereignis verbinden."""
        start = float(elemente[i].offset)
        end = start + float(elemente[i].quarterLength)
        first = elemente[i]
        if isinstance(first, note.Rest):
            return end, i + 1
        tones = first.notes if isinstance(first, chord.Chord) else (first,)
        pitches = tuple(n.pitch.nameWithOctave for n in tones)
        if not pitches or any(n.tie is None or n.tie.type != "start" for n in tones):
            return end, i + 1
        j = i + 1
        while j < len(elemente):
            other = elemente[j]
            other_tones = other.notes if isinstance(other, chord.Chord) else (
                (other,) if isinstance(other, note.Note) else ()
            )
            if tuple(n.pitch.nameWithOctave for n in other_tones) != pitches:
                break
            ties = [n.tie.type if n.tie else None for n in other_tones]
            if any(t not in ("continue", "stop") for t in ties):
                break
            end = float(other.offset + other.quarterLength)
            j += 1
            if all(t == "stop" for t in ties):
                break
        return end, j

    @staticmethod
    def _baue_geruest(
        bass: note.Note, toene: list[note.Note], zahl: int
    ) -> tuple[chord.Chord, tuple[str, ...]]:
        """Bezifferte Töne im Segment suchen; fehlende Töne nicht erfinden."""
        if zahl == 0:
            return chord.Chord(toene or [bass]), ()
        ziffern = [int(z) for z in str(zahl)]
        gefunden = [bass]
        fehlend = []
        kandidaten = sorted(toene, key=lambda n: (n.abs_offset, n.pitch.midi))

        def finde(ziffer: int) -> note.Note | None:
            for n in kandidaten:
                if n.pitch.midi <= bass.pitch.midi:
                    continue
                iv = interval.Interval(bass, n)
                if iv.generic.directed > 0 and (
                    (iv.generic.directed - ziffer) % 7 == 0
                ):
                    return n
            return None

        for z in ziffern:
            n = finde(z)
            if n is None:
                fehlend.append(str(z))
            elif n not in gefunden:
                gefunden.append(n)

        # Die bisherige verkürzte Bezifferung ergänzt diese Töne nur,
        # wenn sie tatsächlich in dem Abschnitt auftreten.
        ergaenzungen = {5: (3,), 6: (3,), 7: (3, 5), 34: (6,),
                        24: (6,), 56: (3,)}
        for z in ergaenzungen.get(zahl, ()):
            n = finde(z)
            if n is not None and n not in gefunden:
                gefunden.append(n)
        hinweise = (
            ("Bezifferte Stufen nicht gefunden: " + ", ".join(fehlend),)
            if fehlend else ()
        )
        return chord.Chord(gefunden), hinweise

    @classmethod
    def aus_annotation(
        cls, index: PartiturIndex, element, ende: float,
        elemente: list, element_index: int,
    ) -> HarmonischerKontext:
        anfang = float(element.offset)
        if isinstance(element, note.Rest):
            return cls(anfang, ende, "Standard", "Hilfsstimme")

        marke = str(element.lyric or "")
        basston = min(element.notes, key=lambda n: n.pitch.midi) if isinstance(
            element, chord.Chord
        ) else element
        tonbereich = index.noten_im_bereich(anfang, ende)
        ziffer = re.search(r"\d+", marke)
        if ziffer:
            zahl = int(ziffer.group())
            geruest, hinweise = cls._baue_geruest(basston, tonbereich, zahl)
            modus = "Alberti"
            if len(geruest.notes) == 2:
                namen = {n.name for n in geruest.notes}
                geruesttoene = [n for n in tonbereich if n.name in namen]
                eindeutige_lage = len({
                    n.nameWithOctave for n in geruesttoene
                }) == len(geruesttoene)
                keine_ueberlappung = all(
                    a.end <= b.abs_offset + TOL
                    for a, b in zip(
                        sorted(geruesttoene, key=lambda n: n.abs_offset),
                        sorted(geruesttoene, key=lambda n: n.abs_offset)[1:],
                    )
                )
                if len(geruesttoene) >= 2 and eindeutige_lage and keine_ueberlappung:
                    modus = "Alberti_mit_Kontrapunkt"
            return cls(
                anfang, ende, modus, "Hilfsstimme", basston, zahl,
                basston, geruest, marke, (basston, elemente, element_index),
                hinweise,
            )
        if marke == "Op":
            return cls(
                anfang, ende, "Orgelpunkt", "Hilfsstimme",
                basston, annotationston=basston, kennzeichen=marke,
            )
        return cls(
            anfang, ende, "Figuration", "Hilfsstimme", basston,
            annotationston=basston, kennzeichen=marke,
            hilfsstimme_kontext=(basston, elemente, element_index),
        )

    @classmethod
    def aus_standard_slice(
        cls, index: PartiturIndex, offset: float, hoechstens: float
    ) -> HarmonischerKontext:
        toene = index.noten_bei(offset)
        folgegrenzen = [g for g in index.grenzen if g > offset + TOL]
        naechste = min(folgegrenzen[0] if folgegrenzen else hoechstens, hoechstens)
        if len(toene) > 2:
            bass = min(toene, key=lambda n: n.pitch.midi)
            ende = min(float(bass.end), hoechstens)
            if ende > offset + TOL:
                return cls(
                    offset, ende, "Standard", "Automatisch", bass,
                    klanggeruest=chord.Chord(toene),
                    hinweise=("Gerüstbass aus dem tiefsten klingenden Ton abgeleitet",),
                )
        return cls(
            offset, naechste, "Standard", "Automatisch",
            hinweise=("Kein automatisch bestimmbarer Gerüstbass",),
        )

    @classmethod
    def erzeuge_alle(cls, index: PartiturIndex) -> list[HarmonischerKontext]:
        """Hilfssegmente zuerst; Standardabschnitte ausschließlich darin ergänzen."""
        roh: list[HarmonischerKontext] = []
        if index.hilfsstimme is not None:
            elemente = list(index.hilfsstimme.flatten().notesAndRests)
            i = 0
            while i < len(elemente):
                ende, naechster_index = cls._verbundenes_ende(elemente, i)
                roh.append(cls.aus_annotation(index, elemente[i], ende, elemente, i))
                i = naechster_index
        roh.sort(key=lambda seg: seg.anfang)
        if not roh:
            roh = [cls(0.0, index.dauer, "Standard", "Hilfsstimme")]

        # Nicht markierte Lücken sollen ebenfalls nach der Standardregel laufen.
        zonen: list[HarmonischerKontext] = []
        cursor = 0.0
        for seg in roh:
            if seg.anfang < cursor - TOL:
                raise ValueError("Die Segmente der Hilfsstimme überlappen.")
            if seg.anfang > cursor + TOL:
                zonen.append(cls(cursor, seg.anfang, "Standard", "Luecke"))
            zonen.append(seg)
            cursor = seg.ende
        if cursor < index.dauer - TOL:
            zonen.append(cls(cursor, index.dauer, "Standard", "Luecke"))

        ergebnis: list[HarmonischerKontext] = []
        for zone in zonen:
            if zone.modus != "Standard":
                ergebnis.append(zone)
                continue
            offset = zone.anfang
            while offset < zone.ende - TOL:
                seg = cls.aus_standard_slice(index, offset, zone.ende)
                if seg.ende <= offset + TOL:
                    raise ValueError(f"Segment ohne positive Dauer bei {offset}")
                ergebnis.append(seg)
                offset = seg.ende
        return ergebnis

    @staticmethod
    def finde_bei(
        kontexte: list[HarmonischerKontext], offset: float
    ) -> HarmonischerKontext | None:
        starts = [seg.anfang for seg in kontexte]
        i = bisect_right(starts, offset + TOL) - 1
        return kontexte[i] if i >= 0 and kontexte[i].enthaelt(offset) else None


@dataclass
class Klang:
    """Klang an einem Offset; die Beurteilung gehört zum Objekt selbst."""

    offset: float
    kontext: HarmonischerKontext
    klingende_toene: tuple[note.Note, ...]
    untersuchter_akkord: chord.Chord | None
    kategorie: str | None
    untersuchte_tonnamen: frozenset[str]
    strukturelle_dissonanzen: frozenset[str]
    regelbefund: dict = field(default_factory=dict, repr=False)

    @staticmethod
    def _strukturanalyse(
        akkord: chord.Chord, kontext: HarmonischerKontext,
        index: PartiturIndex, offset: float,
    ) -> tuple[str | None, frozenset[str], dict]:
        """Sichere Grundfälle; unvollständige Akkorde bleiben vorerst offen."""
        namen: set[str] = set()
        kategorie = None
        inversion = akkord.inversion()
        bass = akkord.bass()
        root, fifth, seventh = akkord.root(), akkord.fifth, akkord.seventh
        if akkord.isSeventh():
            kategorie = "Septakkord"
            if seventh:
                namen.add(seventh.name)
                # Die Vertikale allein unterscheidet 7-6 und Septakkord nicht.
                for ton in index.noten_bei(offset):
                    if ton.name != seventh.name:
                        continue
                    _, folge = index.nachbarn(ton)
                    if (
                        folge is not None
                        and folge.abs_offset < kontext.ende - TOL
                        and interval.Interval(ton, folge).generic.directed == -2
                    ):
                        kategorie = "7-6_oder_Septakkord"
                        namen.discard(seventh.name)
                        break
            if inversion == 2 and fifth:
                namen.add(fifth.name)
            if akkord.isDiminishedSeventh() or akkord.isHalfDiminishedSeventh():
                if fifth:
                    namen.add(fifth.name)
        elif akkord.isTriad():
            if akkord.isDiminishedTriad() or akkord.isAugmentedTriad():
                kategorie = (
                    "verminderter Dreiklang" if akkord.isDiminishedTriad()
                    else "übermäßiger Dreiklang"
                )
                if fifth:
                    namen.add(fifth.name)
            elif inversion == 2:
                kategorie = "Quartsextakkord"
                if root:
                    namen.add(root.name)
        elif len({n.name for n in akkord.notes}) == 2:
            tief, hoch = sorted(akkord.notes, key=lambda n: n.pitch.midi)[:2]
            iv = interval.Interval(tief, hoch)
            if iv.simpleName in ("A4", "d5"):
                kategorie = "Tritonus"
                namen.add(tief.name if iv.simpleName == "A4" else hoch.name)
            # Eine reine Quarte oder Septime allein belegt keinen
            # selbständigen Akkord. Ihre Einzelnoten bleiben zu prüfen.
        return kategorie, frozenset(namen), {
            "inversion": inversion,
            "bass": bass.name if bass else None,
            "vollstaendiger_septakkord": akkord.isSeventh(),
        }

    @classmethod
    def analysiere(
        cls, index: PartiturIndex, kontext: HarmonischerKontext, offset: float
    ) -> Klang:
        toene = tuple(index.noten_bei(offset))
        if not toene:
            return cls(offset, kontext, toene, None, None, frozenset(), frozenset())
        untersuchte = (
            kontext.klanggeruest
            if kontext.quelle == "Hilfsstimme" and kontext.klanggeruest is not None
            else chord.Chord(toene)
        )
        if len(untersuchte.notes) < 2:
            return cls(
                offset, kontext, toene, untersuchte, None,
                frozenset(n.name for n in untersuchte.notes), frozenset(),
            )
        kategorie, dissonanzen, befund = cls._strukturanalyse(
            untersuchte, kontext, index, offset
        )
        return cls(
            offset, kontext, toene, untersuchte,
            kategorie,
            frozenset(n.name for n in untersuchte.notes),
            dissonanzen,
            befund,
        )


@dataclass
class Dissonanz:
    """Befund zu genau einem Ton in genau einem zeitlichen Slice."""

    ton: note.Note
    offset: float
    kontext: HarmonischerKontext
    klang: Klang
    partner: tuple[note.Note, ...]
    status: str
    typ: str | None
    begruendung: tuple[str, ...]

    @classmethod
    def analysiere(
        cls, ton: note.Note, klang: Klang, kontext: HarmonischerKontext,
        index: PartiturIndex,
    ) -> Dissonanz:
        bass = min(klang.klingende_toene, key=lambda n: n.pitch.midi)
        partner = tuple(
            n for n in klang.klingende_toene
            if n is not ton and cls._dissonantes_intervall(ton, n, bass)
        )
        gruende: list[str] = []
        if ton.name in klang.strukturelle_dissonanzen:
            return cls(
                ton, klang.offset, kontext, klang, partner,
                "akkordeigene_Dissonanz", None,
                ("Tonname gehört zur strukturellen Akkorddissonanz",),
            )
        if not partner:
            return cls(
                ton, klang.offset, kontext, klang, (), "kein_Dissonanzintervall",
                None, ("Kein dissonantes Intervall in diesem Slice",),
            )
        gruende.append("Dissonantes Intervall zu " + ", ".join(
            n.nameWithOctave for n in partner
        ))
        vorher, nachher = index.nachbarn(ton)
        typ = None
        if vorher is not None and nachher is not None:
            hinein = interval.Interval(vorher, ton)
            hinaus = interval.Interval(ton, nachher)
            hinein_schritt = hinein.generic.undirected == 2
            hinaus_schritt = hinaus.generic.undirected == 2
            if hinein_schritt and hinaus_schritt:
                typ = (
                    "Nebennote" if vorher.pitch == nachher.pitch
                    else "Durchgang"
                )
            elif not hinein_schritt and hinaus_schritt:
                typ = "Appoggiatur_Kandidat"
            if typ:
                gruende.append("Eindeutige Nachbarn derselben melodischen Linie")
        elif ton.abs_offset < klang.offset - TOL and nachher is not None:
            if interval.Interval(ton, nachher).generic.undirected == 2:
                typ = "Vorhalt_Kandidat"
                gruende.append("Gehaltene Note mit schrittweiser Fortsetzung")
        if typ is None:
            gruende.append("Stimmführung oder Akkordzugehörigkeit bleibt offen")
        return cls(
            ton, klang.offset, kontext, klang, partner,
            "wahrscheinlich_akkordfremd" if typ else "offen", typ,
            tuple(gruende),
        )

    @staticmethod
    def _dissonantes_intervall(a: note.Note, b: note.Note, bass: note.Note) -> bool:
        iv = interval.Interval(a, b)
        if iv.simpleName == "P4":
            unterer = min((a, b), key=lambda n: n.pitch.midi)
            return unterer.nameWithOctave == bass.nameWithOctave
        return not iv.isConsonant()


class AnalyseProgramm:
    """Orchestriert eine vollständige Analyse; keine zweite Regelverwaltung."""

    def __init__(self, score: stream.Score, hilfsstimme_index: int | None = -1):
        self.index = PartiturIndex(score, hilfsstimme_index)
        self.kontexte = HarmonischerKontext.erzeuge_alle(self.index)

    def analysiere(self) -> list[Dissonanz]:
        ergebnis: list[Dissonanz] = []
        for offset in self.index.grenzen[:-1]:
            kontext = HarmonischerKontext.finde_bei(self.kontexte, offset)
            if kontext is None:
                continue
            klang = Klang.analysiere(self.index, kontext, offset)
            for ton in klang.klingende_toene:
                befund = Dissonanz.analysiere(ton, klang, kontext, self.index)
                if befund.status != "kein_Dissonanzintervall":
                    ergebnis.append(befund)
        return ergebnis
