from itertools import combinations
from typing import Iterable, Optional
from music21 import note, chord, interval

def entscheide_zielton_bei_gleichem_offset(
    n1: note.Note,
    n2: note.Note,
    slice_noten: Optional[Iterable[note.Note]],
) -> note.Note:
    """
    Zusätzliche Entscheidungslogik NUR für den Fall, dass n1 und n2 das gleiche Offset haben.
    Regeln:
      - Wenn Slice nur 2 PCs hat und Intervall = d5 oder A4 -> 'Quinten'-Heuristik: oberer Ton ist Zielton
      - Wenn (mind. 3 PCs) dim./aug. Dreiklang -> Quinte ist Zielton
      - Wenn vollständiger Septakkord -> Septime ist Zielton
      - Wenn (genau 3 PCs) unvollständiger Septakkord (umgruppelbar zu Terz+7 oder 5+7) -> Septime ist Zielton
      - Sonst: kürzere Note ist Zielton (bei Gleichstand: n1)

    Parameter
    ---------
    n1, n2 : music21.note.Note
    slice_noten : Iterable[music21.note.Note] | None
        Alle klingenden Noten im aktuellen Slice (ohne Duplikatfilterung).

    Rückgabe
    --------
    music21.note.Note : der gewählte Zielton (eine der beiden: n1 oder n2)
    """
    def _fallback_kürzer(a: note.Note, b: note.Note) -> note.Note:
        d1, d2 = float(a.quarterLength), float(b.quarterLength)
        if d1 < d2:
            return a
        elif d2 < d1:
            return b
        return a  # Gleichstand

    if not slice_noten:
        return _fallback_kürzer(n1, n2)

    # 1) Pro PitchClass genau eine Repräsentant-Note sammeln
    pc2notes = {}
    for x in slice_noten:
        pc2notes.setdefault(x.pitch.pitchClass, []).append(x)
    reps = [lst[0] for lst in pc2notes.values()]
    unique_pcs = set(pc2notes.keys())

    # 2) Zwei-Ton-Sonderfall: d5/A4 -> oberer Ton als „Quinte“
    if len(unique_pcs) == 2 and len(reps) == 2:
        iv = interval.Interval(reps[0], reps[1])
        gen = iv.generic.undirected
        qual = iv.semiSimpleName[0] if iv.semiSimpleName else iv.simpleName[0]  # 'A','d','M','m','P'
        if (gen == 5 and qual == 'd') or (gen == 4 and qual == 'A'):
            oberer = max((reps[0], reps[1]), key=lambda n: n.pitch.diatonicNoteNum)
            # auf n1/n2 abbilden per PC (bei Kollision diatonisch höher)
            if n1.pitch.pitchClass == oberer.pitch.pitchClass:
                return n1
            if n2.pitch.pitchClass == oberer.pitch.pitchClass:
                return n2


    # 3) Ab 3 PCs: Akkord-Checks
    if len(unique_pcs) >= 3:
        ch = chord.Chord(reps)

        # 3a) dim./aug. Dreiklang -> Quinte ist Zielton
        if ch.isTriad() and ch.quality in ('diminished', 'augmented'):
            try:
                quint_pc = ch.fifth.pitchClass
            except Exception:
                quint_pc = None
            if quint_pc is not None:
                if n1.pitch.pitchClass == quint_pc:
                    return n1
                if n2.pitch.pitchClass == quint_pc:
                    return n2

        # 3b) vollständiger Septakkord -> Septime ist Zielton
        sept_pc = None
        try:
            if ch.seventh is not None:
                sept_pc = ch.seventh.pitchClass
        except Exception:
            sept_pc = None

        if sept_pc is not None:
            if n1.pitch.pitchClass == sept_pc :
                return n1
            if n2.pitch.pitchClass == sept_pc:
                return n2

        # 3c) unvollständiger Septakkord (genau 3 PCs): Terz+7 ODER 5+7 möglich?
        if len(unique_pcs) == 3:
            reps_sorted = sorted(reps, key=lambda x: x.pitch.diatonicNoteNum)
            sept_pc_kandidaten = set()
            for a, b in combinations(reps_sorted, 2):
                iv_ab = interval.Interval(a, b)
                if iv_ab.generic.undirected == 7:  # m7/M7
                    dritter = next(x for x in reps_sorted if x is not a and x is not b)
                    hat_terz_oder_quinte = any(
                        interval.Interval(x, dritter).generic.undirected in (3, 5)
                        for x in (a, b)
                    )
                    if hat_terz_oder_quinte:
                        obere = max((a, b), key=lambda n: n.pitch.diatonicNoteNum)
                        sept_pc_kandidaten.add(obere.pitch.pitchClass)

            if sept_pc_kandidaten:
                if n1.pitch.pitchClass in sept_pc_kandidaten:
                    return n1
                if n2.pitch.pitchClass in sept_pc_kandidaten:
                    return n2

    # 4) Nichts gegriffen -> ursprüngliche „kürzere Note“-Regel
    return _fallback_kürzer(n1, n2)
