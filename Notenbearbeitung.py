from music21 import stream, note, chord,interval
from collections import defaultdict
INTEGRATION_TOL = 1e-6
BOUNDARY_TOL = 1e-6


def Grenzen_aller_Elemente(s: stream.Score):
    entfaltung = s.flatten()
    Grenzen = {0.0}
    for el in entfaltung.notesAndRests:
        start = float(el.offset)
        end = float(el.offset + el.quarterLength)
        Grenzen.add(start)
        Grenzen.add(end)
    return sorted(Grenzen)


def _baue_taktindex(score: stream.Score, pickup_qL: float | None = None):
    """
    构建小节索引。
    
    pickup_qL:
        None → 无弱起（默认），第一小节 offset = 0.0
        float → 弱起长度（quarterLength），弱起视为 0 小节，第一小节 offset = pickup_qL
    """
    # ------------------------------------------------------------
    # 1) 检查是否已有 measure，如没有则生成
    # ------------------------------------------------------------
    try:
        hat_measures = any(
            isinstance(el, stream.Measure)
            for el in score.recurse().getElementsByClass(stream.Measure)
        )
    except Exception:
        hat_measures = False
        
    score_norm = score
    if not hat_measures:
        try:
            score_norm = score.makeMeasures(inPlace=False)
        except Exception:
            score_norm = score  

    # ------------------------------------------------------------
    # 2) 选择 measure 最多的 part 做为参考
    # ------------------------------------------------------------
    parts = list(getattr(score_norm, 'parts', [])) or [score_norm]

    def _count_measures(p):
        try:
            return len(list(p.getElementsByClass(stream.Measure)))
        except Exception:
            return 0

    ref = max(parts, key=_count_measures)

    idx = []

    # ------------------------------------------------------------
    # 3) 若有弱起，先创建一个"人工弱起小节"
    # ------------------------------------------------------------
    if pickup_qL is not None and pickup_qL > 0:
        idx.append({
            'no': 0,               # 弱起小节编号为 0
            'start': 0.0,
            'end': float(pickup_qL)
        })

    # ------------------------------------------------------------
    # 4) 处理其余正常小节
    # ------------------------------------------------------------
    for m in ref.getElementsByClass(stream.Measure):
        # offset 计算
        try:
            start = float(m.getOffsetInHierarchy(score_norm))
        except Exception:
            start = float(getattr(m, 'offset', 0.0))

        # shift offset if pickup exists
        if pickup_qL is not None:
            start += float(pickup_qL)

        # duration 判断
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

    # ------------------------------------------------------------
    # 5) 排序返回
    # ------------------------------------------------------------
    idx.sort(key=lambda d: d['start'])

    return idx


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

# alle Noten in einer Partitur sammeln und ihnen zusätzliche Eigenschaften ergänzen
def Sammlung_aller_Noten(s: stream.Score,Auftakt) -> list:
    taktindex = _baue_taktindex(s,Auftakt)
    Entfaltung = s.flatten()
    Events = []
    for el in Entfaltung.notesAndRests:
        Globales_Offset = float(el.offset)
        Takt_Nr, offset_Takt = _find_measure_for_abs_offset(taktindex, Globales_Offset)
        if isinstance(el, note.Note):
            el.abs_offset = Globales_Offset
            el.end = el.abs_offset + float(el.quarterLength)
            el.Chord_Objekt = None
            el.Takt_Nr = Takt_Nr
            el.offset_Takt = offset_Takt
            Events.append(el)

        elif isinstance(el, chord.Chord):
            for n in el.notes:
                n.abs_offset = Globales_Offset
                n.end = n.abs_offset + float(n.quarterLength)
                n.Chord_Objekt = el
                n.Takt_Nr = Takt_Nr
                n.offset_Takt = offset_Takt
                Events.append(n)     

    Events.sort(key=lambda e: e.abs_offset)
    return Events

# eine Liste,in der alle klingenden Noten in irgendeinem Offset-Slice gespeichert werden, für die Nutzung zur Verfügung stellen
def Sammlung_aller_Slice(s: stream.Stream, grenzen: list[float],Auftakt) -> list[dict]:
    grezen = list(sorted(map(float, grenzen)))
    events = Sammlung_aller_Noten(s,Auftakt)
    out = []
    Noten_im_Slice = []
    Notenummer = 0
    tol = INTEGRATION_TOL

    for i in range(len(grezen) - 1):
        a, b = grezen[i], grezen[i + 1]
        if b <= a:
            out.append({'offset': a, 'elements': [], 'bass': None})
            continue
        
        # für jedes Slice die Noten hinzufügen
        while Notenummer < len(events) and events[Notenummer].abs_offset < b - tol:
            Noten_im_Slice.append(events[Notenummer])
            Notenummer += 1
        
        Noten_im_Slice = [
            ev for ev in Noten_im_Slice
            if (ev.end > a + tol) or
               (ev.abs_offset >= a - tol and ev.abs_offset < b) # speziell für die kleine Verzierungsnote
        ]
        elems = list(Noten_im_Slice)  
        bass = min(elems, key=lambda n: n.pitch.midi) if elems else None
        out.append({'offset': a, 'elements': elems, 'bass': bass})
    return out


def Noten_am_Offset(Slice_Sammlung: list[dict], offset: float) -> list|None:
    for d in Slice_Sammlung:
        if abs(d['offset'] - offset) <= INTEGRATION_TOL:
            return list(d['elements'])
    return None


def ist_Transition(Zielnote: note.Note, Quelle, modus="Hilfstimme",
                   Zielindex=None, TOL=INTEGRATION_TOL) -> bool:
    """Prüft, ob ``Zielnote`` von beiden Seiten sekundweise erreicht wird."""

    if not isinstance(Zielnote, note.Note):
        return False

    def ist_Sekunde(n1, n2):
        if not isinstance(n1, note.Note) or not isinstance(n2, note.Note):
            return False
        try:
            iv = interval.Interval(n1, n2)
            return iv.generic is not None and iv.generic.undirected == 2
        except Exception:
            return False

    if modus == "Hilfstimme":
        # Quelle ist die bereits in Modus.py erzeugte Liste ``Elemente``.
        # Hier wird bewusst nicht erneut flatten() aufgerufen.
        Elemente = Quelle
        if Zielindex is None:
            Zielindex = next(
                (i for i, el in enumerate(Elemente) if el is Zielnote),
                None
            )
        if Zielindex is None or Zielindex == 0 or Zielindex >= len(Elemente) - 1:
            return False

        vorheriges_Element = Elemente[Zielindex - 1]
        naechstes_Element = Elemente[Zielindex + 1]
        return (ist_Sekunde(vorheriges_Element, Zielnote)and ist_Sekunde(Zielnote, naechstes_Element))

    if modus == "Original_Slices":
        Original_Slices = Quelle
        Zieloffset = float(getattr(Zielnote, "abs_offset", Zielnote.offset))
        Zielende = (float(Zielnote.abs_offset)+ float(Zielnote.quarterLength))
        Sliceindex = next(
            (
                i for i, sl in enumerate(Original_Slices)
                if abs(float(sl["offset"]) - Zieloffset) <= TOL
            ),
            None
        )
        if Sliceindex is None or Sliceindex == 0 or Sliceindex >= len(Original_Slices) - 1:
            return False

        vorherige_Noten = [
            n for n in Original_Slices[Sliceindex - 1].get("elements", [])
            if isinstance(n, note.Note)
        ]
        naechste_Noten = Noten_am_Offset(Original_Slices,Zielende)
        #print(Zielnote.Takt_Nr,Zielnote.offset_Takt, Zielnote.nameWithOctave,vorherige_Noten,naechste_Noten)
        return (
            any(ist_Sekunde(n, Zielnote) for n in vorherige_Noten)
            and any(ist_Sekunde(Zielnote, n) for n in naechste_Noten)
        )

    raise ValueError("modus muss 'Hilfstimme' oder 'Original_Slices' sein.")



def _find_slice_index(t0: float,Grenzen) -> int | None:

    for i, g in enumerate(Grenzen):
        if abs(float(g) - float(t0)) <= 0.0001:
            return i
    return None

def next_slice_offset(t0,Nummer,Grenzen):
    idx = _find_slice_index(t0,Grenzen)
    if idx is None:
        print("⚠️ offset 不存在于 Grenz 中:", t0)
        return None
    if idx + Nummer == len(Grenzen):
        print("⚠️ 已经是最后一个 slice，没有下一个 offset")
        return None
    return Grenzen[idx + Nummer]


def weglassen_doppelte_Noten(notes,modus="offset"):
    Filterung = {}

    if not notes:
        return notes
    
    if modus=="Bereich":
        # 先为每个 offset 找到该时刻的最低音 name
        tiefste_namen_pro_offset = {}

        offsets = set(n.abs_offset for n in notes)
        for offset in offsets:
            noten_an_diesem_offset = [n for n in notes if n.abs_offset == offset]
            if noten_an_diesem_offset:
                tiefste_note = min(noten_an_diesem_offset, key=lambda n: n.pitch.midi)
                tiefste_namen_pro_offset[offset] = tiefste_note.name

        # 再按原来的 key 处理八度重复
        for n in notes:
            key = (n.name, n.abs_offset, n.quarterLength)

            if key not in Filterung:
                Filterung[key] = n
            else:
                existierende = Filterung[key]
                tiefste_name = tiefste_namen_pro_offset.get(n.abs_offset)

                # 如果这一组的 name 就是该 offset 的最低音名，保留低音
                if n.name == tiefste_name:
                    if n.pitch.midi < existierende.pitch.midi:
                        Filterung[key] = n
                # 否则保留高音
                else:
                    if n.pitch.midi > existierende.pitch.midi:
                        Filterung[key] = n

        notes = list(Filterung.values())
        return notes
    
    if modus=="offset":
        # 全局最低音
        tiefste_note = min(notes, key=lambda n: n.pitch.midi)
        tiefste_name = tiefste_note.name

        for n in notes:
            key = (n.name, n.quarterLength)

            if key not in Filterung:
                Filterung[key] = n
            else:
                existierende = Filterung[key]

                if n.name == tiefste_name:
                    # 低音组：统一用最低音
                    Filterung[key] = tiefste_note
                else:
                    # 其他组：保留高音
                    if n.pitch.midi > existierende.pitch.midi:
                        Filterung[key] = n

        # 🔽 最终还是输出 notes（list）
        notes = list(Filterung.values())
        return notes

def weglassen_doppelte_Noten_bei_Figurierung(notes):
    """
    给定若干 music21.note.Note 对象，
    对于音名相同（不管八度）的音，只保留八度最高的那些音；
    若最高音重复出现，则全部保留。
    并保持原列表中的顺序。
    """

    hoechste_ps_pro_name = defaultdict(lambda: float("-inf"))

    # 先找每个音名的最高 pitch.ps
    for n in notes:
        name = n.pitch.name
        if n.pitch.ps > hoechste_ps_pro_name[name]:
            hoechste_ps_pro_name[name] = n.pitch.ps

    # 再按原顺序保留最高的那些
    return [
        n for n in notes
        if n.pitch.ps == hoechste_ps_pro_name[n.pitch.name]
    ]


def finde_passenden_Sliceoffset(Original_Slices,Anfang,Grenzen,Ende=None,modus="Noten"):
    """
    从 Anfang 开始向后寻找符合条件的 slice offset。

    参数:
        Original_Slices : 原始切片数据
        Anfang          : 起始 offset
        Grenzen         : 所有 slice 的边界 / offset 信息
        El              : 可选；如果给出，则不会搜索到超过 El.offset 的位置
        modus           : 控制搜索逻辑，可选：
                          - "mehrere_noten"
                            一直往后找，直到某个 slice 的音符数量 > 1
                          - "neue_tonhoehe"
                            一直往后找，直到出现新的音名（忽略八度）

    返回:
        符合条件的 slice offset；
        如果找不到，返回 None
    """

    def offset_ist_zu_weit(offset):
        return Ende is not None and offset > Ende

    if modus == "Noten":
        schritt = 0
        while True:
            aktueller_offset = next_slice_offset(Anfang, schritt, Grenzen)
            if aktueller_offset is None or offset_ist_zu_weit(aktueller_offset):
                print("aktueller_offset is zu_weit:", aktueller_offset)
                return None

            aktuelle_töne = Noten_am_Offset(Original_Slices, aktueller_offset)
            aktuelle_töne = list(aktuelle_töne or [])

            if len(aktuelle_töne) > 1:
                return aktueller_offset

            schritt += 1

    elif modus == "Akkord":
        start_töne = Noten_am_Offset(Original_Slices, Anfang)
        start_töne = list(start_töne or [])

        bekannte_tonnamen = set(n.pitch.name for n in start_töne)

        schritt = 1
        
        while True:
            aktueller_offset = next_slice_offset(Anfang, schritt, Grenzen)
            if aktueller_offset is None or offset_ist_zu_weit(aktueller_offset):
                return None

            aktuelle_töne = Noten_am_Offset(Original_Slices, aktueller_offset)
            aktuelle_töne = list(aktuelle_töne or [])

            aktuelle_tonnamen = set(n.pitch.name for n in aktuelle_töne)

            if not aktuelle_tonnamen.issubset(bekannte_tonnamen):
                nächster_offset = next_slice_offset(aktueller_offset, 1, Grenzen)
                if nächster_offset is None or offset_ist_zu_weit(nächster_offset):
                    #print("nächster_offset is zu_weit:", nächster_offset )
                    return aktueller_offset
                return nächster_offset

            bekannte_tonnamen.update(aktuelle_tonnamen)
            schritt += 1

    else:
        raise ValueError(
            "modus muss 'mehrere_noten' oder 'neue_tonhoehe' sein."
        )
    
def ist_Konsonantes_Intervall(note1,note2,Bass=None,Intervall=None):
    Intervall = interval.Interval(note1,note2)
    if Bass:
        Unterer = note1 if note1.pitch.midi <= note2.pitch.midi else note2
        Intervallname = Intervall.simpleName
        ist_Konsonant = (Unterer.nameWithOctave != Bass.nameWithOctave) if Intervallname == 'P4' else Intervall.isConsonant()
    else:
        ist_Konsonant = Intervall.isConsonant() 
    if ist_Konsonant:
        return True
    else:
        return False
    
def notes_in_time_span(cache_slices: list[dict], t0: float, t1: float, TOL: float = 1e-6):
    collected = []
    seen_ids = set()
    for sl in cache_slices:
        off = float(sl['offset'])
        if t0 - TOL <= off < t1 - TOL:
            for el in sl.get('elements', []):
                if id(el) not in seen_ids:
                    seen_ids.add(id(el))
                    collected.append(el)
    return collected
