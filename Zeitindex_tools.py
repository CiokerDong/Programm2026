from music21 import stream as m21stream, chord as m21chord, note, chord

INTEGRATION_TOL = 1e-6
BOUNDARY_TOL = 1e-6

def _baue_taktindex(score: m21stream.Score):
    try:
        hat_measures = any(isinstance(el, m21stream.Measure)
                           for el in score.recurse().getElementsByClass(m21stream.Measure))
    except Exception:
        hat_measures = False
        
    score_norm = score
    if not hat_measures:
        try:
            score_norm = score.makeMeasures(inPlace=False)
        except Exception:
            score_norm = score  

    parts = list(getattr(score_norm, 'parts', [])) or [score_norm]

    def _count_measures(p):
        try:
            return len(list(p.getElementsByClass(m21stream.Measure)))
        except Exception:
            return 0

    ref = max(parts, key=_count_measures)

    idx = []
    for m in ref.getElementsByClass(m21stream.Measure):
        try:
            start = float(m.getOffsetInHierarchy(score_norm))
        except Exception:
            start = float(getattr(m, 'offset', 0.0))

        dur = None
        try:
            if m.barDuration is not None:
                dur = float(m.barDuration.quarterLength)
        except Exception:
            pass
        if dur is None:
            try:
                dur = float(m.duration.quarterLength)
            except Exception:
                dur = 0.0

        idx.append({
            'no': getattr(m, 'number', None),
            'start': start,
            'end': start + dur
        })
    idx.sort(key=lambda d: d['start'])
    return idx, score_norm


def _find_measure_for_abs_offset(taktindex: list[dict], abs_off: float) -> tuple[int | None, float | None]:

    tol = BOUNDARY_TOL
    lo, hi = 0, len(taktindex) - 1
    while lo <= hi:
        mid = (lo + hi) // 2
        rec = taktindex[mid]
        if abs_off < rec['start'] - tol:
            hi = mid - 1
        elif abs_off >= rec['end'] - tol:
            lo = mid + 1
        else:
            return rec['no'], float(abs_off - rec['start'])

    if taktindex:
        last = taktindex[-1]
        return last['no'], max(0.0, float(abs_off - last['start']))
    return None, None


def _slice_at_offset(slices_cache: list[dict], offset: float) -> dict | None:
    key = float(offset)
    for d in slices_cache:
        if abs(d['offset'] - key) <= INTEGRATION_TOL:
            return d
    return None


def _timed_carrier(el):
    parent_ch = el.getContextByClass(m21chord.Chord)
    return parent_ch if (parent_ch is not None and parent_ch is not el) else el


def _top_site(el):
    for cls in (m21stream.Score, m21stream.Part):
        s = el.getContextByClass(cls)
        if s is not None:
            return s
    return getattr(el, 'activeSite', None) or el


def _cache_measure_fields(n: note.Note, abs_start: float, taktindex: list[dict]):
    meas_no, meas_off = _find_measure_for_abs_offset(taktindex, abs_start)
    n._abs_offset = float(abs_start)
    n._meas_no = meas_no
    n._meas_off = None if meas_off is None else float(meas_off)


def _vorindexiere_ereignisse_fuer_stream(s: m21stream.Stream, taktindex: list[dict]) -> list[dict]:
    if s is None:
        return []

    flat = s.flatten()
    events = []

    for el in flat.recurse():
        # ① 单独 Note，包括 grace notes
        if isinstance(el, note.Note):
            start = float(el.offset)
            end = start + float(el.quarterLength)  # grace note = 0
            _cache_measure_fields(el, start, taktindex)
            events.append({'start': start, 'end': end, 'note': el, 'Chord':None})
        # ② Chord：把和弦中的每个 note 单独加入（包含 grace notes）
        elif isinstance(el, chord.Chord):
            start = float(el.offset)
            end = start + float(el.quarterLength)
            for n in el.notes:
                # n.isGrace 也可能为 True
                _cache_measure_fields(n, start, taktindex)
                events.append({'start': start, 'end': end, 'note': n, 'Chord':el})
    events.sort(key=lambda e: e['start'])
    #print(events)
    return events


def _baue_slices_cache_fuer_stream(s: m21stream.Stream, grenzen: list[float], taktindex: list[dict]) -> list[dict]:
    if s is None or not grenzen:
        return []
    grezen = list(sorted(map(float, grenzen)))
    if len(grezen) < 2:
        return []
    events = _vorindexiere_ereignisse_fuer_stream(s, taktindex)
    out = []
    active = []
    j = 0
    tol = INTEGRATION_TOL

    for i in range(len(grezen) - 1):
        a, b = grezen[i], grezen[i + 1]
        if b <= a:
            out.append({'offset': a, 'elements': [], 'bass': None})
            continue

        while j < len(events) and events[j]['start'] < b - tol:
            active.append(events[j])
            j += 1

        if active:
             active = [ev for ev in active if (ev['end'] > a + tol) or (ev['start'] >= a - tol and ev['start'] < b)]
        elems = [ev['note'] for ev in active]
        bass = min(elems, key=lambda n: n.pitch.midi) if elems else None
        Chord = next((ev['Chord'] for ev in active if ev['Chord'] is not None), None)
        if Chord is None:
            out.append({'offset': a, 'elements': elems, 'bass': bass,'Chord': None})
        else:
            out.append({'offset': a, 'elements': elems, 'bass': bass,'Chord': Chord})
    return out


__all__ = [
    '_baue_taktindex',
    '_find_measure_for_abs_offset',
    '_slice_at_offset',
    '_timed_carrier',
    '_top_site',
    '_cache_measure_fields',
    '_vorindexiere_ereignisse_fuer_stream',
    '_baue_slices_cache_fuer_stream',
]


def _measure_and_offsets(el, score):
    carrier = _timed_carrier(el)
    meas = carrier.getContextByClass(m21stream.Measure)
    abs_off = carrier.getOffsetInHierarchy(score)
    off_in_meas = None
    if meas is not None:
        off_in_meas = carrier.getOffsetBySite(meas)
    return meas, off_in_meas, abs_off 