from music21 import pitch as m21pitch, pitch, interval


# ---- Hilfs-Mapping: Tonname (ohne Oktave) -> pitchClass (0..11)
def _pc(nname: str) -> int:
    # Nur 1x je Unique-Name konvertieren (sauber, wenig .pitch-Nutzung)
    return m21pitch.Pitch(nname).pitchClass

def _pcset_von_namen(namen_set: set[str]) -> frozenset[int]:
    return frozenset(_pc(n) for n in namen_set)

# Triaden relativ zum Grundton 0
_TRIADS = {
    'Dur': frozenset({0, 4, 7}),
    'Moll': frozenset({0, 3, 7}),
    'vermindert': frozenset({0, 3, 6}),
    'übermäßig': frozenset({0, 4, 8}),
}

# Septakkorde relativ zum Grundton 0
_SEVENTHS = {
    '!großer Septakkord':        frozenset({0, 4, 7, 11}),  # Maj7
    '!Dominantseptakkord':       frozenset({0, 4, 7, 10}),  # Mm7
    '!kleiner Septakkord':       frozenset({0, 3, 7, 10}),  # m7
    '!halbverminderter Septakkord': frozenset({0, 3, 6, 10}),  # ø7
    '!verminderter Septakkord':  frozenset({0, 3, 6, 9}),   # o7
    '!übermäßiger-großer Septakkord':   frozenset({0, 4, 8, 11}),  # +7 (selten)
}

def _transpositions(pcset: frozenset[int]) -> list[frozenset[int]]:
    """Alle Transpositionen (jede mögliche Wahl des Grundtons als 0)."""
    lst = sorted(pcset)
    outs = []
    for r in lst:
        outs.append(frozenset(((p - r) % 12) for p in pcset))
    return outs

def _qualifiziere_triad(pcset: frozenset[int]) -> str | None:
    if len(pcset) != 3:
        return None
    for tset in _transpositions(pcset):
        for name, tpl in _TRIADS.items():
            if tset == tpl:
                # Für Dur/Moll-Dreiklang nennen wir (wie gewünscht) "Quartsextakkord"
                if name in ('Dur', 'Moll'):
                    return 'Quartsextakkord'
                return f'{name}er Dreiklang'
    return None

def _qualifiziere_sept(pcset: frozenset[int]) -> str | None:
    if len(pcset) != 4:
        return None
    for tset in _transpositions(pcset):
        for name, tpl in _SEVENTHS.items():
            if tset == tpl:
                return name
    return None

def _fehlender_pc_fuer_unvollst_sept(pcset3: frozenset[int]) -> tuple[str | None, int | None]:
    """
    Prüft, ob pcset3 (Größe=3) in irgendeinem Septakkord-Template steckt.
    Gibt (Name-des-vollständigen-Septakkords, fehlender_pc) zurück oder (None, None).
    """
    if len(pcset3) != 3:
        return (None, None)
    for name, tpl in _SEVENTHS.items():
        # Prüfen, ob pcset3 als Teilmenge eines transponierten tpl vorkommt
        # Dazu: für jeden möglichen Grundton die transponierte tpl bilden
        for root in range(12):
            transp_tpl = frozenset(((p + root) % 12) for p in tpl)
            if pcset3.issubset(transp_tpl):
                fehlende = list(transp_tpl - pcset3)
                if len(fehlende) == 1:
                    return (name, fehlende[0])
    return (None, None)

def _finde_fehlenden_tonname_rueckwaerts(previous_slices_names: list[set[str]], fehlender_pc: int) -> str | None:
    """
    Geht von hinten nach vorne durch die früheren Slices (je ein Set von TonNamen ohne Oktave)
    und gibt den ersten TonNamen zurück, dessen pitchClass == fehlender_pc.
    """
    for names in previous_slices_names:  # already in rückwärts-Reihenfolge übergeben
        for nn in names:
            try:
                if _pc(nn) == fehlender_pc:
                    return nn
            except Exception:
                continue
    return None

def analyse_slice_akkord_label(namen_im_slice: set[str],
                               previous_slices_names_desc: list[set[str]],
                               reduced_name: str,
                               offset_imTakt_Dissonanz: float | None = None,
                               offset_imTakt_Partnerton: float | None = None) -> str | None:
    """
    Hauptroutine:
    - Input: aktuelle TonNamen (ohne Oktave, Duplikate bereits entfernt),
             Liste früherer Slices (jedes als Set von TonNamen, in rückwärts Reihenfolge),
             sowie reduced_name (z.B. 'm7').
    - Output: 'NameDesAkkords+reduced_name' oder None (falls kein Treffer).
    """
    # 1) Direkte Klassifikation (Dreiklang/Septakkord)
    pcset = _pcset_von_namen(namen_im_slice)
    Töne = namen_im_slice
    if len(pcset) == 2 and offset_imTakt_Dissonanz == offset_imTakt_Partnerton:
        namen_liste = list(namen_im_slice)
        p1 = pitch.Pitch(namen_liste[0] + "4")
        p2 = pitch.Pitch(namen_liste[1] + "4")
        interv = interval.Interval(p1, p2)
        if interv.name in ("A4", "d5"):   
            return f"Tritonus"  

        
    # Septakkord
    sept = _qualifiziere_sept(pcset)
    if sept:
        return f'{sept}+{reduced_name}'
        
    # Dreiklang direkt
    tri = _qualifiziere_triad(pcset)
    if tri:
        return f'{tri}+{reduced_name}'
    # 2) Unvollständiger Septakkord? (Terz+Septime oder Quinte+Septime „umgeschichtet“)
    if len(pcset) == 3:
        septname, fehl_pc = _fehlender_pc_fuer_unvollst_sept(pcset)
        if septname and fehl_pc is not None:
            # Fehlenden Ton rückwärts suchen
            fehl_name = _finde_fehlenden_tonname_rueckwaerts(previous_slices_names_desc, fehl_pc)
            if fehl_name is not None:
                # Erfolg: als kompletter Septakkord zählen
                return f'{septname}+{reduced_name}'
    # 3) Kein Treffer -> None (dann nimmst du einfach reduced_name)
    return None
