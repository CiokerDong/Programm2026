from __future__ import annotations
from typing import Iterable, List, Optional, Dict, Set, Tuple
from music21 import converter, stream, note, chord, interval
from music21 import note, chord as m21chord

# --------------------------------

def _flatten_to_notes(elems: Iterable) -> List[note.Note]:
    out: List[note.Note] = []
    for el in elems:
        if isinstance(el, m21chord.Chord):
            out.extend([n for n in el.notes if isinstance(n, note.Note)])
        elif isinstance(el, note.Note):
            out.append(el)
    return out

def _vorindexiere_ereignisse(hilfsstimme: stream.Stream) -> List[dict]:
    if hilfsstimme is None:
        return []
    flat = hilfsstimme.flatten()
    events: List[dict] = []
   
    for el in flat.getElementsByClass((note.Note, chord.Chord)):
        start = float(el.offset)
        ql = float(el.quarterLength) if hasattr(el, 'quarterLength') else 0.0
        end = start + ql
        if isinstance(el, note.Note):
            n = el
            n._abs_offset = start  
            events.append({'start': start, 'end': end, 'note': n})
        else:
            ch: chord.Chord = el
            for n in ch.notes:
                if not isinstance(n, note.Note):
                    continue
                n._abs_offset = start
                events.append({'start': start, 'end': end, 'note': n})
    events.sort(key=lambda e: e['start'])
    return events

def _baue_hilfs_slices_cache(hilfsstimme: stream.Stream, grenzen: list[float]):

    if hilfsstimme is None or not grenzen or len(grenzen) < 2:
        return []


    grezen = sorted(grenzen)
    grenzen = [float(g) for g in grezen]
    events = _vorindexiere_ereignisse(hilfsstimme)
    out: List[dict] = []
    active: List[dict] = []  
    j = 0                    

    tol = INTEGRATION_TOL

    for i in range(len(grenzen) - 1):
        a = float(grezen[i])
        b = float(grezen[i + 1])
        if b <= a:
            out.append({'offset': a, 'elements': []})
            continue

        while j < len(events) and events[j]['start'] < b - tol:
            active.append(events[j])
            j += 1

        if active:
            active = [ev for ev in active if ev['end'] > a + tol]

        elems = []
        for ev in active:
            n = ev['note']
            elems.append(n)

        out.append({'offset': a, 'elements': elems})

    return out


def klingende_Noten_im_Bereich(s: stream.Stream, start, ende):
    """
    慢路径保留（兼容性）：仍然使用 flatten()+getElementsByOffset。
    建议：仅用于应急；常规请走 _baue_hilfs_slices_cache 的线性扫描结果。
    """
    if s is None:
        return []
    Entfaltung = s.flatten()
    elems = Entfaltung.getElementsByOffset(
        start, ende,
        includeEndBoundary=False,
        mustBeginInSpan=False,
        includeElementsThatEndAtStart=False,
        classList=[note.Note, chord.Chord]
    )
    ausgabe = []
    for el in elems:
        if isinstance(el, chord.Chord):
            for n in el.notes:
                n._abs_offset = float(el.offset)
                ausgabe.append(n)
        elif isinstance(el, note.Note):
            n = el
            n._abs_offset = float(el.offset)
            ausgabe.append(n)
    return ausgabe

# =====================================================

def _pcs(notes_in: Iterable[note.Note]) -> Set[int]:
    return {n.pitch.pitchClass for n in notes_in if isinstance(n, note.Note)}

def _lowest_note(notes_in: Iterable[note.Note]) -> Optional[note.Note]:
    notes_list = [n for n in notes_in if isinstance(n, note.Note)]
    if not notes_list:
        return None
    return min(notes_list, key=lambda n: n.pitch.midi)

def _transpose_pcset(pcset: Set[int], semitones: int) -> Set[int]:
    return {(pc + semitones) % 12 for pc in pcset}


def classify_dissonant_harmony(obj,
    Annotationskennzeichen=None,
    current_offset: Optional[float] = None,
    lookback_quarters: Optional[float] = None,
) -> Optional[Dict]:
    result = {
        'dissonanter_Akkord': False,
        'category': None,
        'qualität': None,
        'dissonant_notes': [],
        'root_pc': None,
        'pcset': set(),
        'akkordtöne': set(),
        'chord': None,
    }
    if not isinstance(obj, chord.Chord):
        raise TypeError

    ch: chord.Chord = obj
    result['chord'] = ch
    notes = list(ch.notes)
    notes_all = list({n.name: n for n in notes if isinstance(n, note.Note)}.values())
    if not notes:
        return result
    
    pcs_abs = {n.pitch.pitchClass for n in notes if isinstance(n, note.Note)}
    result['pcset'] = pcs_abs
    Töne_name = {n.name for n in notes if isinstance(n, note.Note)}
    result['akkordtöne'] = Töne_name 
    rt = ch.root()
    th = ch.third
    ff = ch.fifth
    sv = ch.seventh
    oberste_note = max(ch.notes, key=lambda n: n.pitch.midi)
    bass_note = min(ch.notes, key=lambda n: n.pitch.midi)
    Intervall = interval.Interval(bass_note, oberste_note)
    durations = {n.quarterLength for n in notes}
    if rt is not None:
        result['root_pc'] = getattr(rt, 'pitchClass', None)
        result['root_pc'] = getattr(rt, 'pitchClass', None)
    if len(notes_all) == 2 and len(durations) == 1:
        iv = interval.Interval(notes[0], notes[1])
        simp = iv.simpleName
        if simp in ('A4', 'd5'):
            result['dissonanter_Akkord'] = True
            result['category'] = 'verminderter Dreiklang'
            if simp == 'A4':
                dis = notes[0] if notes[0].pitch.midi <= notes[1].pitch.midi else notes[1]
            else:
                dis = notes[0] if notes[0].pitch.midi > notes[1].pitch.midi else notes[1]
            result['dissonant_notes'] = [dis]
            return result

    elif len(notes_all) == 3:
        if ch.isTriad() and ch.quality == 'diminished':
            result['dissonanter_Akkord'] = True
            result['category'] = 'verminderter Dreiklang'
            if ff:
                try:
                    ff_note = next(n for n in notes if n.pitch == ff.pitch)
                except Exception:
                    ff_note = note.Note(ff)
                result['dissonant_notes'] = [ff_note]
            return result

        elif ch.isTriad() and ch.quality == 'augmented':
            result['dissonanter_Akkord'] = True
            result['category'] = 'übermäßiger Dreiklang'
            if ff:
                try:
                    ff_note = next(n for n in notes if n.pitch == ff.pitch)
                except Exception:
                    ff_note = note.Note(ff)
                result['dissonant_notes'] = [ff_note]
            return result

        elif ch.isTriad() and ch.quality not in ('diminished', 'augmented') and ch.inversion() == 2:
            result['dissonanter_Akkord'] = True
            result['category'] = 'Quartsextakkord'
            rt_note = note.Note(rt)
            ff_note = note.Note(ff)
            if Annotationskennzeichen=='D.B.':
                result['dissonant_notes'] = [ff_note]
            else: 
                result['dissonant_notes'] = [rt_note]
            return result
        
        elif sv is not None and rt is not None and (th is not None or ff is not None):
            if Annotationskennzeichen or th is not None:
                result['dissonanter_Akkord'] = True
                result['category'] = 'unvollständigen Septakkord'
                sv_note = note.Note(sv)
                result['dissonant_notes'] = [sv_note]
            else:
                return result
            
        elif Intervall.name in ('m9','M9'):
            result['dissonanter_Akkord'] = True
            result['category'] = 'Noneakkord'
            return result

    elif len(notes_all) == 4 and all(x is not None for x in (rt, th, ff, sv)):
        result['dissonanter_Akkord'] = True
        result['category'] = 'Septakkord'
        try:
            sv_note = next(n for n in notes if n.name == sv.name)
        except Exception:
            sv_note = note.Note(sv)
        result['dissonant_notes'] = [sv_note]
        return result

    return result

INTEGRATION_TOL = 1e-6

def _find_hilfs_slice(hilfs_slices: list[dict], offset: float):
    for d in hilfs_slices:
        if abs(d['offset'] - float(offset)) <= INTEGRATION_TOL:
            return d
    return None

def _classify_hilfs_akkord(hilfs_slices: list[dict], offset: float, cache: dict, lookback_quarters: float | None = None):
    key = round(float(offset), 6)
    if key in cache:
        return cache[key]
    curr = _find_hilfs_slice(hilfs_slices, offset)
    if curr is None:
        cache[key] = None
        return None
    elems_notes = _flatten_to_notes(curr.get('elements', []))
    if not elems_notes:
        cache[key] = None
        return None
    ch = chord.Chord(elems_notes)
    res = classify_dissonant_harmony(ch)
    cache[key] = res
    return res

def _norm_pcset(pcset: Set[int], root_pc: int) -> Set[int]:
    return {(pc - root_pc) % 12 for pc in pcset}
    
SEVENTHS: Dict[str, Set[int]] = {
    'großer Septakkord (M7)': {0, 4, 7, 11},
    'Dominantseptakkord (m7)': {0, 4, 7, 10},
    'kleiner Septakkord (m7)': {0, 3, 7, 10},
    'halbverminderter Septakkord (ø7)': {0, 3, 6, 10},
    'verminderter Septakkord (o7)': {0, 3, 6, 9},
    'übermäßig-großer Septakkord (+M7)': {0, 4, 8, 11},
}

unvollständige_SEVENTHS: Dict[str, Set[int]] = {
    'großer Septakkord (M7)': [{0, 4, 11},{0, 7, 11} ],
    'Dominantseptakkord (m7)': {0, 4, 10},
    'kleiner Septakkord (m7)': {0, 3, 10},
    'halbverminderter Septakkord (ø7)': {0, 6, 10},
    'verminderter Septakkord (o7)': [{0, 3, 9},{0, 6, 9}],
    'übermäßig-großer Septakkord (M7)': {0, 8, 11},
}


def _label_from_result(res: dict | None) -> str | None:
    if not res:
        return None
    typ = res.get('category')
    if typ == 'Quartsextakkord':
        return 'Quartsextakkord(P4)'
    if typ == 'verminderter Dreiklang':
        return 'verminderter Dreiklang'
    if typ == 'übermäßiger Dreiklang':
        return 'übermäßiger Dreiklang'
    if typ == 'Noneakkord':
        return 'None'    
    if typ == 'Septakkord':
        root_pc = res.get('root_pc')
        pcset_abs = res.get('pcset', set())
        if root_pc is not None:
            rel = _norm_pcset(pcset_abs, root_pc)
            for qual_name, rel_set in SEVENTHS.items():
                if rel == rel_set:
                    return qual_name
            return '!unbekannterSeptakkord'
        return '!falscherSeptakkord'
    if typ == 'unvollständigen Septakkord':
        root_pc = res.get('root_pc')
        pcset_abs = res.get('pcset', set())
        if root_pc is not None:
            rel = _norm_pcset(pcset_abs, root_pc)
            for qual_name, rel_set in unvollständige_SEVENTHS.items():
                if rel == rel_set or rel in rel_set:
                    return qual_name
            return '!unbekannterSeptakkord'
        return '!falscherSeptakkord' 
    return None

def _is_relevant_chord(res: dict | None) -> bool:
    if not res:
        return False
    return res.get('category') in {'Septakkord', 'Quartsextakkord','verminderter Dreiklang', 'übermäßiger Dreiklang'}
