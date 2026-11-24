from music21 import articulations, chord, expressions, stream


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
        neue_dissonanz = fortsetzung.notes[notenindex]
        neue_dissonanz.abs_offset = float(beginn)
        neue_dissonanz.end = float(beginn) + float(neue_dissonanz.quarterLength)
        return neue_dissonanz, fortsetzung

    fortsetzung.abs_offset = float(beginn)
    fortsetzung.end = float(beginn) + float(fortsetzung.quarterLength)
    return fortsetzung, fortsetzung


def Markierungen_der_Ereignissen(Ereignisse):
    Markirungen = []
    for Evente in Ereignisse:
        Dissonanz = Evente['Dissonanz_Objekt']
        Nummerierung = Evente['Objekt']
        Dissonanz_Nummer = Evente['Nummer']
        Markirungen.append({
            'note': Dissonanz,
            'Objekt': Nummerierung,
            'label': Dissonanz_Nummer,
            'Farbe': 'red',
            'SliceAnfang': Evente['SliceAnfang'],
            'Dissonanz_Beginn': Evente['Dissonanz_Beginn'],
            'Ereignis': Evente,
        })
    return Markirungen


def _note_hat_gleichen_fingering(n, label) -> bool:
    ziel = str(label)
    for a in getattr(n, 'articulations', []):
        if isinstance(a, articulations.Fingering):
            val = (
                getattr(a, 'fingerNumber', None)
                or getattr(a, 'number', None)
                or getattr(a, 'content', None)
                or str(a)
            )
            if str(val) == ziel:
                return True
    return False


def Einfuegung_der_Markierungen(
    Markirungen,
    placement='above',
    default_font_size=10,
    score=None,
):
    for mk in Markirungen:
        n = mk['note']
        m = mk['Objekt']
        if score is not None:
            alte_dissonanz = n
            n, m = note_am_dissonanzbeginn(
                score,
                n,
                m,
                mk.get('Dissonanz_Beginn'),
            )
            if n is not alte_dissonanz:
                ereignis = mk.get('Ereignis')
                if ereignis is not None:
                    ereignis['Dissonanz_Offset'] = float(n.abs_offset)
        label = str(mk['label'])
        farbe = mk.get('Farbe', 'red')
        fs = mk.get('FontSize', default_font_size)
        try:
            n.style.color = farbe
        except Exception:
            pass

        # vorhandenes Label leeren:
        if not hasattr(m, '_finger_cleared'):
            try:
                m.articulations = [
                    a for a in getattr(m, 'articulations', [])
                    if not isinstance(a, articulations.Fingering)
                ]
            except Exception:
                m.articulations = []

            m._finger_cleared = True

        # Nummerlabel hinzufuegen
        try:
            f = articulations.Fingering(label)
            try:
                f.placement = placement
            except Exception:
                pass
            try:
                f.style.fontSize = 8
            except Exception:
                pass
            m.articulations.append(f)
        except Exception:
            try:
                te = expressions.TextExpression(label)
                te.placement = 'above'
                try:
                    te.style.fontSize = fs
                except Exception:
                    pass
                m.expressions.append(te)
            except Exception:
                pass
