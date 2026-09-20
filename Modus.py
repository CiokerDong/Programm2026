from music21 import stream, note, chord, interval
from Notenbearbeitung import Noten_am_Offset,finde_passenden_Sliceoffset,notes_in_time_span
from Klang import Beurteilung_dissonanten_Klangs,Bildung_Klanggerüst,ist_Ein_Septakkord
import re


def haben_vertikale_Überlappung(noten, TOL: float = 1e-6) -> bool:
    """Prueft, ob sich die klingenden Zeitintervalle der Noten ueberlappen.

    Wenn eine Note genau beim Einsatz der naechsten Note endet, gelten die
    beiden Noten als aufeinanderfolgend und nicht als vertikal ueberlappt.
    """
    intervalle = sorted(
        (
            float(n.abs_offset),
            float(n.end),
        )
        for n in noten
    )

    groesstes_ende = float('-inf')
    for anfang, ende in intervalle:
        if anfang < groesstes_ende - TOL:
            return True
        groesstes_ende = max(groesstes_ende, ende)

    return False


#O: "Oktavedoppelte Dissonanz weglassen". In diesem Modus wird die Dissonanz oktavedoppelt und die niederigere Dissonanz ignoriert. 
#Of:"oktavedoppelter Dissonanz in der Figurierung weglassen"
#B: Den Basston im angegebenen Klang als Dissonanz ansehen, der Ton über dem Bass ist der tatsächliche Akkordton.


def Modi_auf_der_Hiflsstimme(score: stream.Score,Grenzen,Original_Slices,hilfsstimme_index: int = -1):
    Stimmen = list(score.parts)
    Hilfsstimme = Stimmen[hilfsstimme_index]
    Hilfsstimme = Hilfsstimme.flatten()
    Elemente = list(Hilfsstimme.notesAndRests)
    Alberti=False
    MODI = []
    
    # 将辅助声部中的连线的音符合并为同一个Segment
    i = 0
    while i < len(Elemente):
        i0 = i 
        Anfang, Ende, i = Zusammenstellung_verbundener_Noten(Elemente, i)
        if Ende <= Anfang:
            continue
        El = Elemente[i0]
        Töne_im_Bereich = notes_in_time_span(Original_Slices, Anfang, Ende)
        Kennzeichen = El.lyric if El.lyric else []
        if El.isRest:
            MODI.append({'Modus': 'Standard', 'Anfang': Anfang, 'Ende': Ende})
            continue
        elif any(c.isdigit() for c in Kennzeichen):
            Zahlen = int(re.search(r'\d+', Kennzeichen).group())
            #print(Zahlen)
            Akkordeigene_Töne = []
            Akkorddissonanz = []
            Basston = min(El.notes, key=lambda n: n.pitch.midi) if El.isChord else El
            Annotationston  = Basston
            if Zahlen == 0: 
                Klanggerüst=chord.Chord(Töne_im_Bereich)
                Klanggerüst_alle=Klanggerüst
                Beurteilung = Beurteilung_dissonanten_Klangs(
                    Klanggerüst, Zahlen, Kennzeichen, Anfang,
                    Hilfstimme_Kontext=(Annotationston, Elemente, i0)
                )
                Dissonanzakkord = Beurteilung.get('dissonanter_Akkord')
                if Dissonanzakkord:
                    Akkorddissonanz = Beurteilung.get('dissonant_notes')
                    Akkordeigene_Töne = Beurteilung.get('akkordtöne')
            else:
                Klanggerüst = Bildung_Klanggerüst(Töne_im_Bereich, Zahlen, El)
                Töne_am_Modusanfang = list(Noten_am_Offset(Original_Slices, Anfang) or [])
                Namen_im_Klanggerüst = {n.name for n in Klanggerüst.notes}
                Töne_am_Modusanfang = [n for n in Töne_am_Modusanfang if n.name not in Namen_im_Klanggerüst]
                Klanggerüst_alle = chord.Chord(list(Klanggerüst.notes) + Töne_am_Modusanfang)
            Geruesttoene_nur_einstimmig=None
            if len(Klanggerüst.notes) == 2:
                Namen_im_Klanggerüst = {n.name for n in Klanggerüst.notes}
                alle_Gerüsttöne = [
                    n for n in Töne_im_Bereich
                    if n.name in Namen_im_Klanggerüst
                ]
                alle_Gerüsttönename = [n.nameWithOctave for n in alle_Gerüsttöne]

                # Nur beurteilen, wenn kein Geruestton in gleicher Oktavlage
                # mehrfach in der Begleitungsstimme vorkommt.
                if len(alle_Gerüsttönename) == len(set(alle_Gerüsttönename)):
                    Geruesttoene_vertikal_ueberlappt = haben_vertikale_Überlappung(alle_Gerüsttöne)
                    Geruesttoene_nur_einstimmig = not Geruesttoene_vertikal_ueberlappt
            if not Geruesttoene_nur_einstimmig:
                if Klanggerüst is None:
                    print("框架是None!!!:", Anfang)
                MODI.append({
                    'Modus': 'Alberti',
                    'Kennzeichen': Kennzeichen,
                    'Klanggerüst': Klanggerüst,
                    'Töne_am_Anfang':Klanggerüst_alle,
                    'Anfang': Anfang,
                    'Zahl':Zahlen,
                    'Ende': Ende,
                    'Annotationston': Annotationston,
                    'Hilfstimme_Kontext': (Annotationston, Elemente, i0),
                    'Bass': Basston,
                    'Akkordeigene_Töne':Akkordeigene_Töne,
                    'Akkorddissonanz': Akkorddissonanz
                })
            else:
                MODI.append({
                    'Modus': 'Alberti_mit_Kontrapunkt',
                    'Kennzeichen': Kennzeichen,
                    'Klanggerüst': Klanggerüst,
                    'Töne_am_Anfang':Klanggerüst_alle,
                    'Anfang': Anfang,
                    'Zahl':Zahlen,
                    'Ende': Ende,
                    'Annotationston': Annotationston,
                    'Hilfstimme_Kontext': (Annotationston, Elemente, i0),
                    'Bass': Basston,
                    'Akkordeigene_Töne':Akkordeigene_Töne,
                    'Akkorddissonanz': Akkorddissonanz
                })
        
        elif not any(c.isdigit() for c in Kennzeichen) and Kennzeichen != "Op":
            Töne_am_Modusanfang = Noten_am_Offset(Original_Slices, Anfang) 
            Töne_am_Modusanfang = list(Töne_am_Modusanfang or [])
            zum_Akkord = chord.Chord(Töne_am_Modusanfang)
            Basston = min(El.notes, key=lambda n: n.pitch.midi) if El.isChord else El
            Annotationston  = Basston
            Beurteilung = Beurteilung_dissonanten_Klangs(
                zum_Akkord, None, Kennzeichen, Anfang, Töne_im_Bereich,
                Hilfstimme_Kontext=(Annotationston, Elemente, i0)
            )
            Klangdissonanz = Beurteilung.get('dissonant_notes')
            if Klangdissonanz:
                Konsonant=False
                Akkorddissonanz = Klangdissonanz
                Akkordeigene_Töne=Beurteilung.get('akkordtöne')
            else:
                Akkordeigene_Töne=None
                Akkorddissonanz=None
                Konsonant=True
            MODI.append({
                'Modus': 'Figuration',
                'Kennzeichen':Kennzeichen,
                'Anfang': Anfang,
                'Ende': Ende,
                'Qualität':Konsonant,
                'Annotationston': Annotationston,
                'Hilfstimme_Kontext': (Annotationston, Elemente, i0),
                'Bass': Basston,
                'Klang':zum_Akkord,
                'Akkordeigene_Töne':Akkordeigene_Töne,
                'Akkorddissonanz': Akkorddissonanz
                 })

        elif Kennzeichen == "Op":
                Orgelpunkt = {El.nameWithOctave}
                MODI.append({'Modus': 'Orgelpunkt',
                             'Anfang': Anfang, 
                             'Ende': Ende, 
                             'Orgelpunkt': Orgelpunkt
                             })
        else:
            print(Anfang, Ende, 'Unbekanntes Modus')

    MODI.sort(key=lambda d: d['Anfang'])
    Zusammensetzung = []
    for Ausschnitt in MODI:
        if (Zusammensetzung and Zusammensetzung[-1]['Modus'] == 'Standard' and Ausschnitt['Modus'] == 'Standard'
                and abs(Ausschnitt['Anfang'] - Zusammensetzung[-1]['Ende']) < 1e-9):
            Zusammensetzung[-1]['Ende'] = Ausschnitt['Ende']
        else:
            Zusammensetzung.append(Ausschnitt)
    return Zusammensetzung


def Zusammenstellung_verbundener_Noten(Elemente, i: int):
    """
    给定 Elemente[i]，返回 (Anfang, Ende, next_i)
    - 若 Note/Chord 形成 tie 链，会把后续片段合并进来
    - next_i 是合并后应该跳到的下一个索引
    """
    El = Elemente[i]
    Anfang = float(El.offset)
    Gesamtdauer = float(El.quarterLength)

    # 1) Rest：直接返回
    if isinstance(El, note.Rest):
        return Anfang, float(El.offset + El.quarterLength), i + 1

    # 2) Note：按单音 tie 合并
    if isinstance(El, note.Note):

        if not El.tie or El.tie.type not in ("start", "continue"):
            return Anfang, float(El.offset + El.quarterLength), i + 1

        j = i + 1
        while j < len(Elemente):
            nächste_Note = Elemente[j]
            Gesamtdauer += float(nächste_Note.quarterLength)
            if nächste_Note.tie.type == "stop":
                j += 1
                break
            j += 1

        return Anfang, float(El.offset + Gesamtdauer), j

    # 3) Chord：只有“整块和弦都在 tie 链里”才合并
    if isinstance(El, chord.Chord):
        tie_map = _chord_tie_types_by_pitch(El)
        pitches = set(tie_map.keys())

        # 必须每个音都有 tie，且类型是 start/continue（否则不合并）
        if not pitches or any(tie_map[p] not in ("start", "continue") for p in pitches):
            return Anfang, float(El.offset + El.quarterLength), i + 1

        j = i + 1
        while j < len(Elemente):
            nächste_Note = Elemente[j]
            if not isinstance(nächste_Note, chord.Chord):
                break

            nxt_map = _chord_tie_types_by_pitch(nächste_Note)
            nxt_pitches = set(nxt_map.keys())

            # 必须音高集合完全相同（非常重要：否则和弦已经变了，就不该“合并成同一事件”）
            if nxt_pitches != pitches:
                break

            # 下一个 chord 的每个音也必须有 tie（continue/stop）
            if any(nxt_map[p] not in ("continue", "stop") for p in pitches):
                break

            Gesamtdauer += float(nächste_Note.quarterLength)

            # 当所有音都到 stop，就结束
            if all(nxt_map[p] == "stop" for p in pitches):
                j += 1
                break

            j += 1

        return Anfang, float(El.offset + Gesamtdauer), j

    # 兜底：其他类型直接不合并
    return Anfang, float(El.offset + El.quarterLength), i + 1


def _tie_type(n):
    return None if n.tie is None else n.tie.type
    
def _chord_tie_types_by_pitch(ch: chord.Chord):
    # 返回 {pitch: tie_type}
    d = {}
    for n in ch.notes:
        d[n.pitch] = _tie_type(n)
    return d
