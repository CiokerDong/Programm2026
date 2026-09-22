
from music21 import chord, interval, converter, note
from Notenbearbeitung import Noten_am_Offset,notes_in_time_span,ist_Transition
from Klang import Wie_ein_Klang_aufgelöst


def Dissonanz_Finden(chordified_stream): 
    """
    1.reine Quarten über der Bassnote und andere dissonante Intervalle aufgrund des Zustand von Chordify finden
    2.eine Liste, inklusiv Offset, nameWithOctave und interval_name aller Dissonanzen erhalten
    """
    dissonance = [] 
    dissonant_intervals = {'A1', 'm2', 'M2', 'A2', 'd3', 'd4', 'A4', 'd5', 'A5', 'A6', 'd6', 'm7', 'M7', 'd8', 'Dis.4'}  

    for element in chordified_stream.flatten().notesAndRests:
        if isinstance(element, chord.Chord):
            notes = element.notes
            bass_note = element.bass() 
            dissonant_labels = []  # ein Label erstellen, um die dissonanten Intervalle zu speichern.

            for i, note_obj in enumerate(notes):
                for other_note in notes[i + 1:]: 
                    intvl = interval.notesToInterval(note_obj, other_note)

                    # Beurteilung, ob eine reine Quarte dissonant ist.
                    if intvl.simpleName == 'P4' and (
                        note_obj.nameWithOctave == bass_note.nameWithOctave or 
                        other_note.nameWithOctave == bass_note.nameWithOctave):
                        interval_name = 'Dis.4'
                    else:
                        interval_name = intvl.simpleName

                    # das Intervall protokollieren, deren Name des einfachen Intervalls in der Dissonanzliste steht
                    if interval_name in dissonant_intervals:
                        dissonance.append({
                            'offset_1': note_obj.offset,  
                            'pitch_1': note_obj.nameWithOctave,  
                            'offset_2': other_note.offset, 
                            'pitch_2': other_note.nameWithOctave,  
                            'interval': interval_name  
                        })
                        
                        dissonant_labels.append(f"{interval_name}")

            # die gefundenen Dissonanzen als Liedtext markieren
            if dissonant_labels:
                element.addLyric("\n".join(dissonant_labels)) 

    return dissonance, chordified_stream


def _find_slice_index(Offset, Grenzen):
    """Gibt den Index des Slice zurück, in dem der Offset liegt."""
    for Index, Grenze in enumerate(Grenzen):
        if abs(float(Grenze) - float(Offset)) <= 1e-6:
            return Index
    return None


def gibt_es_Sekunde(Ton, Töne):
    """
    Prüft, ob der gegebene Ton mit einem Ton in Töne eine Sekundbeziehung bildet.
    Dabei gelten kleine/große/gesteigerte Sekunde als relevant.
    """
    if Ton is None or not isinstance(Ton, note.Note):
        return False

    for Anderer_Ton in Töne:
        if Anderer_Ton is Ton:
            continue
        if not isinstance(Anderer_Ton, note.Note):
            continue
        try:
            Intervall = interval.Interval(Ton, Anderer_Ton)
            if Intervall.generic and Intervall.generic.undirected == 2:
                return True
        except Exception:
            pass
    return False


def _Töne_im_vorherigen_Slice(Ton, Original_Slices, Grenzen):
    """Vorheriger Slice per Index aus dem aktuellen Offset der Note bestimmen."""
    if Ton is None or not isinstance(Ton, note.Note):
        return []

    Offset = float(getattr(Ton, 'abs_offset', getattr(Ton, 'offset', 0.0)))
    Index = _find_slice_index(Offset, Grenzen)
    if Index is None or Index <= 0:
        return []

    Vorheriger_Offset = float(Grenzen[Index - 1])
    return list(Noten_am_Offset(Original_Slices, Vorheriger_Offset) or [])


def _Töne_im_nachfolgenden_Slice(Ton, Original_Slices, Grenzen):
    """Nachfolgender Slice per Endoffset der Note bestimmen."""
    if Ton is None or not isinstance(Ton, note.Note):
        return []

    Offset = float(getattr(Ton, 'abs_offset', getattr(Ton, 'offset', 0.0)))
    Ende_Ton = Offset + float(getattr(Ton, 'quarterLength', 0.0))
    Index_Ende = _find_slice_index(Ende_Ton, Grenzen)
    if Index_Ende is None or Index_Ende >= len(Grenzen) - 1:
        return []

    Nachfolger_Offset = float(Grenzen[Index_Ende])
    return list(Noten_am_Offset(Original_Slices, Nachfolger_Offset) or [])


def Hauptstimme_Stufenbewegung(Ton, Original_Slices, Grenzen):
    """
    Prüft, ob ein Ton in der Hauptstimme durch Stufenbewegung vor und nachher
    als Sekundbewegung verbunden ist.

    Rückgabewerte:
      - 'Transition' : vor und nach dem Ton gibt es jeweils eine Sekundbeziehung
      - 'Sprung'     : in mindestens einer Richtung fehlt die Sekundbeziehung
      - None         : nicht ausreichend Informationen
    """
    if Ton is None or not isinstance(Ton, note.Note):
        return None

    # Tied / gebundene Noten als keinen neuen Eintritt/Austritt behandeln
    Bindung = getattr(Ton, 'tie', None)
    if Bindung is not None and Bindung.type in ('start', 'continue', 'stop'):
        return None

    Vorherige_Töne = _Töne_im_vorherigen_Slice(Ton, Original_Slices, Grenzen)
    Nachfolgende_Töne = _Töne_im_nachfolgenden_Slice(Ton, Original_Slices, Grenzen)

    Vorher_hat_Sekunde = gibt_es_Sekunde(Ton, Vorherige_Töne)
    Nachher_hat_Sekunde = gibt_es_Sekunde(Ton, Nachfolgende_Töne)

    if Vorher_hat_Sekunde and Nachher_hat_Sekunde:
        return 'Transition'
    return 'Sprung'



def ist_ein_Klangkonsonanz(Ton, Original_Slices, Grenzen,übrige_Töne_im_Bereich=None,Annotationston=None):
    ist_Transition = Hauptstimme_Stufenbewegung(Ton, Original_Slices, Grenzen)
    if ist_Transition == 'Sprung':
        return False   
    else:
        if Ton.quarterLength >= 0.5 * Annotationston.quarterLength:
            return True
        else:
            if Ton.quarterLength >= 0.5 * Annotationston.quarterLength:
                return True
            else:
                alle_Töne = [n for n in übrige_Töne_im_Bereich if n.name == Ton.name]


def ist_der_Ton_aufgelöst(Ton, stream, Stimmen,Einzele_Stimme_slices, Anfang_Modus, Ende_Modus):
    """
    Prüft, ob ein Ton aufgelöst ist.
    Ein Ton gilt als aufgelöst, wenn er in der Hauptstimme durch Stufenbewegung
    vor und nachher als Sekundbewegung verbunden ist.
    """
    parent = n.getContextByClass(stream.Part)
    Stimme_idx = next(
        (i for i, stimme in enumerate(Stimmen)
        if stimme.id == parent.id or str(stimme.id) + "_flat" == str(parent.id)),
        None
    )
    Töne_in_Stimme= notes_in_time_span(Einzele_Stimme_slices.get(Stimme_idx, []), Anfang_Modus, Ende_Modus)
    Grunton_candidates = []
    Grundton=Ton
    Auflösungston_candidates = []
    Auflösungston2_candidates = []
    for n in Töne_in_Stimme:
        if n.nameWithOctave==Grundton.nameWithOctave:
            Grunton_candidates.append(n) 
    Grundnote = sorted(Grunton_candidates, key=lambda n: (n.offset, n.pitch.midi))[0]
    Grundton_end =Grundnote.offset + Grundnote.quarterLength
    offset_letzter_Grundton = max(n.offset for n in Grunton_candidates)

    for n in Töne_in_Stimme:
        Intevall_mit_Grundton= interval.Interval(Grundton, n)
        if n.offset >= Grundton_end and Intevall_mit_Grundton.generic.directed == -2:
            Auflösungston_candidates.append(n)  
        elif n.offset >= Grundton_end and Intevall_mit_Grundton.generic.directed == 2:  
            Auflösungston2_candidates.append(n)
    if bool(Auflösungston_candidates) ^ bool(Auflösungston2_candidates):
        if Auflösungston_candidates:
            offset_letzter_Auflösungston = max(n.offset for n in Auflösungston_candidates)
            if offset_letzter_Auflösungston > offset_letzter_Grundton:
                return "Aufgelöst" 
            else:
                return "nicht Aufgelöst" 
        elif Auflösungston2_candidates:
            offset_letzter_Auflösungston2 = max(n.offset for n in Auflösungston2_candidates)
            if offset_letzter_Auflösungston2 > offset_letzter_Grundton:
                return "Aufgelöst" 
            else:
                return "nicht Aufgelöst" 
    elif Auflösungston_candidates and Auflösungston2_candidates:
        offset_letzter_Auflösungston = max(n.offset for n in Auflösungston_candidates)
        offset_letzter_Auflösungston2 = max(n.offset for n in Auflösungston2_candidates)
        if offset_letzter_Auflösungston > offset_letzter_Grundton or offset_letzter_Auflösungston2 > offset_letzter_Grundton:
            return "Aufgelöst"
    else: 
        return "nicht Aufgelöst" 



def isSynpoke(n,offset,Modusanfang):

    Tie=n.tie.type if n.tie else None

    if (offset < Modusanfang or
         (offset == Modusanfang and Tie in ("stop", "continue"))):
        return True
    return False

def Standart_Analyse(n1,n2,score_slices,Modus=None,Annotationston=None):

    o1=n1.abs_offset
    o2=n2.abs_offset
    d1=n1.quarterLength
    d2=n2.quarterLength
    
    if not Annotationston:
        Annotationston = n1 if d1>d2 else n2
    oA=Annotationston.abs_offset if Annotationston else None

    Synpoke1=isSynpoke(n1,o1,oA)
    Synpoke2=isSynpoke(n2,o2,oA)

    #Sonderfall
    if (Synpoke1 and o2==oA) or (Synpoke2 and o1==oA):
        #print(n1.Takt_Nr,n1.offset_Takt,n2.offset_Takt,n1.name,n2.name,Synpoke1,Synpoke2)
        return n1 if Synpoke1 else n2

    if o1 != o2:
        return n1 if o1 > o2 else n2

    Dissonanz=Analyse_durchAnnotationston(n1, n2, Annotationston)
    if Dissonanz:
        return Dissonanz
    n1_ist_Transition = ist_Transition(n1, score_slices, modus="Original_Slices")
    n2_ist_Transition = ist_Transition(n2, score_slices, modus="Original_Slices")
    if n1_ist_Transition != n2_ist_Transition:
        return n1 if n1_ist_Transition else n2
    if d1 != d2:
        return n1 if d1 < d2 else n2
    print("unbekannte Dissonanz",n1.Takt_Nr, n1.offset_Takt,n1,n2)


def Analyse_durchAnnotationston(n1: note.Note,n2: note.Note,Annotationston: note.Note):
    """
    Vergleicht zwei Noten n1 und n2 anhand eines Annotationstons.
    Die Note, die näher am Annotationston liegt, wird bevorzugt.
    """
    # Berechne die Intervalle zwischen den Noten und dem Annotationston
    Intervall_1 = interval.Interval(n1, Annotationston)
    Intervall_2 = interval.Interval(n2, Annotationston)

    if Intervall_1.isConsonant() != Intervall_2.isConsonant():
        if not Intervall_1.isConsonant():
            return n1             
        else:
            return n2
    elif not Intervall_1.isConsonant() and not Intervall_2.isConsonant():
        return n1  
    else:
        return None

 
def Dominant_unterTerz(Klang,note,score_slices):

    if Klang.commonName in ["dominant seventh chord", "incomplete dominant-seventh chord"]:
        return None
    
    if Klang.intervalFromChordStep(5) and Klang.intervalFromChordStep(5).simpleName == 'd5':
        Bass = min(Klang, key=lambda n: n.pitch.midi)
        Intevall= interval.Interval(Bass, note)
        Schrittweise=None
        if note.pitch.midi < Bass.pitch.midi and Intevall.simpleName == "M3":
           Schrittweise = ist_Transition(note, score_slices, modus="Original_Slices")
        if not Schrittweise:
            return note
    return None


def ist_zusätzliche_Ton_konsonant(Note,Klang,Töne,Urklang=None):

    if Klang.isSeventh() or Klang.isIncompleteSeventh() or Klang.isTriad():
        if Note.pitch == Klang.third:
            return True
        if Klang.fifth and Note.pitch == Klang.fifth and Klang.intervalFromChordStep(5).simpleName=="P5":
            return True
        if Note.pitch== Klang.root():
            Auflösung=Wie_ein_Klang_aufgelöst("allgemeiner Klang",Töne,None,None,Note)
            if Auflösung=="Grundton":
                return True
    return False

def konsonante_Quarte(Kategorie,Quarte,Bass):
    if Kategorie in ['46','34']:
        if Quarte.name == Bass.name and Quarte.nameWithOctave != Bass.nameWithOctave:
            return True
    return False