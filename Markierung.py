from music21 import chord, stream


def note_am_dissonanzbeginn(score, dissonanz, objekt, beginn, tol=1e-6):
    """Split a sustained note at the first dissonant slice for score marking."""
    if beginn is None or objekt is None:
        return dissonanz, objekt

    traeger = objekt
    stelle = next(
        (
            s for s in score.recurse(includeSelf=True).getElementsByClass(stream.Stream)
            if any(el is traeger for el in s)
        ),
        None,
    )
    if stelle is None:
        return dissonanz, objekt

    anfang = float(traeger.getOffsetInHierarchy(score))
    schnitt = float(beginn) - anfang
    dauer = float(traeger.quarterLength)
    if schnitt <= tol or schnitt >= dauer - tol:
        return dissonanz, objekt

    notenindex = None
    if isinstance(traeger, chord.Chord):
        notenindex = next(
            (i for i, n in enumerate(traeger.notes) if n is dissonanz),
            None,
        )
        if notenindex is None:
            return dissonanz, objekt

    vorhandene_spanner = []
    for spanner in traeger.getSpannerSites():
        elemente = list(spanner.getSpannedElements())
        index = next((i for i, el in enumerate(elemente) if el is traeger), None)
        if index is not None:
            vorhandene_spanner.append((spanner, index == len(elemente) - 1 and index > 0))

    lokaler_anfang = float(traeger.getOffsetBySite(stelle))
    teile = traeger.splitAtQuarterLength(schnitt, retainOrigin=False, addTies=True)
    anfangsteil, fortsetzung = teile
    stelle.remove(traeger)
    stelle.insert(lokaler_anfang, anfangsteil)
    stelle.insert(lokaler_anfang + schnitt, fortsetzung)
    for spanner, ist_ende in vorhandene_spanner:
        spanner.replaceSpannedElement(traeger, fortsetzung if ist_ende else anfangsteil)
    for spanner in teile.spannerList:
        score.insert(0, spanner)

    if notenindex is not None:
        return fortsetzung.notes[notenindex], fortsetzung
    return fortsetzung, fortsetzung
