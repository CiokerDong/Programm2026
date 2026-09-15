from music21 import stream, note, chord, duration


def _ist_note_like(e):
    return isinstance(e, (note.Note, chord.Chord, note.Unpitched))


def _passender_container(e):
    for cls in (stream.Voice, stream.Measure, stream.Part, stream.Stream):
        ctx = e.getContextByClass(cls)
        if ctx is not None:
            return ctx
    return e.activeSite


def _naechstes_hauptelement(container, start_elem):
    start_off = start_elem.getOffsetBySite(container)
    seen = False
    for e in container.recurse().notesAndRests:
        off = e.getOffsetBySite(container)
        if e is start_elem:
            seen = True
            continue
        if seen and (_ist_note_like(e) or e.isRest):
            return e
    return None



def verzierungsnoten_umwandeln(
    stream_objekt,
    anteil_von_haupt=0.5,        # 👈 装饰音总时长 = 主音时长的一半（默认）
    zeit_von_hauptnote_stehlen=True,
    hauptnote_verschieben=True,
    epsilon=1e-6,                # 防止主音 duration 变成 0
    platzierung='gleich'         # 'gleich' = 从主音位置开始；'vor' = 提前
):
    """
    将 Grace Notes 转为普通 note.Note，并赋予真实时值。
    装饰音总时值 = 主音时值 × anteil_von_haupt

    - 支持多个装饰音均分总时值
    - 防止把主音缩成 0，因此导出 MusicXML 安全
    """

    graces = [n for n in stream_objekt.recurse().notes if getattr(n.duration, "isGrace", False)]
    done = set()

    for g in graces:
        if g in done:
            continue

        cont = _passender_container(g)
        nxt = _naechstes_hauptelement(cont, g)
        if cont is None or nxt is None:
            continue

        off_g = g.getOffsetBySite(cont)
        off_nxt = nxt.getOffsetBySite(cont)

        # 同 offset 的 Grace 视为一组
        gruppe = [
            e for e in cont.getElementsByOffset(off_nxt, off_nxt, includeEndBoundary=True)
            if hasattr(e, "duration") and getattr(e.duration, "isGrace", False)
        ]

        if not gruppe:
            continue

        # ✅ 装饰音总时值 = 主音 × 比例（默认 1/2）
        nxt_qL = float(nxt.duration.quarterLength)
        total = nxt_qL * anteil_von_haupt

        # ✅ 防止缩成 0
        total = min(total, max(0.0, nxt_qL - epsilon))

        per = total / len(gruppe)

        # offset 计算方式
        if platzierung == 'gleich':
            start = off_nxt
            ziel_haupt = off_nxt + total
        else:  # 'vor'
            start = off_nxt - total
            ziel_haupt = off_nxt

        # 修改装饰音
        pos = start
        for gr in gruppe:
            gr.duration = duration.Duration(per)   # 转为普通 note 时值
            cont.remove(gr, recurse=False)
            cont.insert(pos, gr)
            pos += per
            done.add(gr)

        # ✅ 移动主音
        if hauptnote_verschieben:
            cont.remove(nxt, recurse=False)
            cont.insert(ziel_haupt, nxt)

        # ✅ 缩短主音
        if zeit_von_hauptnote_stehlen and not nxt.isRest:
            nxt.duration.quarterLength = max(epsilon, nxt_qL - total)
