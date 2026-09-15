from typing import Iterable, Optional
from music21 import stream, note,interval,chord


def notes_sounding_at(score: stream.Stream, x: float):
    s_flat  = score.flatten()
    x = float(x)
    eps = 1e-9
    elems = s_flat.getElementsByOffset(
        x, x + eps,
        includeEndBoundary=True, 
        mustFinishInSpan=False, 
        mustBeginInSpan=False, 
        includeElementsThatEndAtStart=False,
        classList=[note.Note, chord.Chord],
    )
    out = []
    for e in elems:
        if isinstance(e, note.Note):
            out.append(e)
        elif isinstance(e, chord.Chord):
            out.extend(e.notes) 
    return out

def klingende_Noten_ohne_unterste(score: stream.Score, offset):
    out = []
    top = list(score.getElementsByClass([stream.Part, stream.PartStaff]))
    for obj in top[:-1]:  #Hilfsstimme weglassen
        out.extend(notes_sounding_at(obj, offset))
    return out

def Grenzen_aller_Töne_im_Raum(score: stream.Score, start, ende):
    Entfaltung = score.flatten()
    Grenzen1 = set()
    for Element in Entfaltung.notesAndRests:
        off = float(Element.offset)
        if start <= off <= ende:   
            Grenzen1.add(off)
    return sorted(Grenzen1)

def Grenzen_aller_Elemente1(score: stream.Score):
    Entfaltung = score.flatten()
    Grenzen = {0.0}
    for Element in Entfaltung.notesAndRests:
        Grenzen.add(float(Element.offset))
    return sorted(Grenzen)



def _find_slice_index(Grenzen, t0: float) -> int | None:
    for i, g in enumerate(Grenzen):
        if abs(float(g) - float(t0)) <= 0.0001:
            return i
    return None

def Quinte_oder_Sexte_als_Dissonanz(
    score: stream.Score,
    Annotationston: note.Note,               
    Originaltöne: Iterable[note.Note]        
) -> Optional[dict]:
    
    # Quinte und Sexte sammeln
    Quinte_Töne = []
    Sexte_Töne = []
    for n in Originaltöne:
        Intervall = interval.Interval(n, Annotationston).simpleName
        if Intervall == 'P5':
            Quinte_Töne.append(n)
        elif Intervall in ('m6', 'M6') and Annotationston.pitch.midi < n.pitch.midi:
            Sexte_Töne.append(n)
    
    if not (Quinte_Töne and Sexte_Töne):
        return None
    
    quinte_offsets = {float(n.offset) for n in Quinte_Töne}
    sexte_offsets  = {float(n.offset) for n in Sexte_Töne}

    # Überprüfung, ob Quinte und Sexte in irgendeinem Zeitpunkt gleichzeitig klingen. 
    Beide_Töne_klingen_gleichzeitig = bool(quinte_offsets & sexte_offsets)

    ###### Parameter erstellen #######
    
    # 1. am frühsten vorkommende Quinte oder Sexte sowie ihr Offset entnehmen
    erste_Quinte = sorted(Quinte_Töne, key=lambda n: n.offset)[0]
    erste_Sexte = sorted(Sexte_Töne, key=lambda n: n.offset)[0]
    Offset_Quinte_Nr1 = erste_Quinte.offset
    Offset_Sexte_Nr1 = erste_Sexte.offset
    
    # 2. die Töne im Slice vor und nach der gefundenen Quinten und Sexten entnehmen
    Slice_nach_Quinte_Nr1 = float(Offset_Quinte_Nr1) + float(getattr(erste_Quinte, 'quarterLength', 0.0))
    Slice_nach_Sexte_Nr1 = float(Offset_Sexte_Nr1)  + float(getattr(erste_Sexte,  'quarterLength', 0.0))
    Töne_Slice_nach_Quinte = klingende_Noten_ohne_unterste(score, Slice_nach_Quinte_Nr1)
    Töne_Slice_nach_Sexte = klingende_Noten_ohne_unterste(score, Slice_nach_Sexte_Nr1)
    
    Grenzen = Grenzen_aller_Elemente1(score)
    Slice_5 = _find_slice_index(Grenzen,Offset_Quinte_Nr1)
    Slice_6  = _find_slice_index(Grenzen,Offset_Sexte_Nr1)
    if Slice_5 is None or Slice_5 == 0:
        Slice_vor_5 = None  
    else:
        Slice_vor_5 = float(Grenzen[Slice_5 - 1])
    if Slice_6 is None or Slice_6 == 0:
        Slice_vor_6 = 0.0
    else:
        Slice_vor_6 = float(Grenzen[Slice_6 - 1])

    Töne_Slice_vor_Quinte = klingende_Noten_ohne_unterste(score, Slice_vor_5)
    Töne_Slice_vor_Sexte = klingende_Noten_ohne_unterste(score, Slice_vor_6)
    
    schrittweise_nach_Quinte = False
    schrittweise_nach_Sexte = False
    schrittweise_vor_Quinte = False
    schrittweise_vor_Sexte = False



    
    # Überprüfen, ob die Töne schrittweise eingeführt und verlassen werden.
    def ist_Schritt(Zielton, n):
        iv = interval.Interval(Zielton, n)
        return iv.generic and iv.generic.undirected == 2 

    schrittweise_vor_Quinte  = any(ist_Schritt(erste_Quinte, n) for n in Töne_Slice_vor_Quinte)
    schrittweise_vor_Sexte   = any(ist_Schritt(erste_Sexte,  n) for n in Töne_Slice_vor_Sexte)
    schrittweise_nach_Quinte = any(ist_Schritt(erste_Quinte, n) for n in Töne_Slice_nach_Quinte)
    schrittweise_nach_Sexte  = any(ist_Schritt(erste_Sexte,  n) for n in Töne_Slice_nach_Sexte)

    
    
    bewegte_Quinte = []
    bewegte_Sexte = []
    Lange_Quinte=[]
    Lange_Sexte=[]

    for n in Quinte_Töne:
        Offset_irgendeiner_Quinte=n.offset
        Slice_irgendeine_Quinte = _find_slice_index(Grenzen,Offset_irgendeiner_Quinte)
        if Slice_irgendeine_Quinte is None or Slice_irgendeine_Quinte == 0:
            Slice_vor_irgendeiner_Quinte = None  
        else:
            Slice_vor_irgendeiner_Quinte = float(Grenzen[Slice_irgendeine_Quinte - 1])
        Slice_nach_irgendeiner_Quinte = float(Offset_irgendeiner_Quinte) + float(getattr(n, 'quarterLength', 0.0))
        Töne_Slice_vor_irgendeiner_Quinte = klingende_Noten_ohne_unterste(score, Slice_vor_irgendeiner_Quinte)
        Töne_Slice_nach_irgendeiner_Quinte = klingende_Noten_ohne_unterste(score, Slice_nach_irgendeiner_Quinte)

        schrittweise_vor_irgendeiner_Quinte  = any(ist_Schritt(n, n2) for n2 in Töne_Slice_vor_irgendeiner_Quinte)
        schrittweise_nach_irgendeiner_Quinte  = any(ist_Schritt(n, n2) for n2 in Töne_Slice_nach_irgendeiner_Quinte)
        Aktive_Bewegung_der_Quinte = (not schrittweise_vor_irgendeiner_Quinte) or (not schrittweise_nach_irgendeiner_Quinte)
        if Aktive_Bewegung_der_Quinte:
            bewegte_Quinte.append(n)
        if n.quarterLength > (Annotationston.quarterLength / 2):
            Lange_Quinte.append(n)

    for n in Sexte_Töne:
        Offset_irgendeiner_Sexte = n.offset
        Slice_irgendeine_Sexte = _find_slice_index(Grenzen,Offset_irgendeiner_Sexte)
        if Slice_irgendeine_Sexte is None or Slice_irgendeine_Sexte == 0:
            Slice_vor_irgendeiner_Sexte = 0.0 
        else:
            Slice_vor_irgendeiner_Sexte = float(Grenzen[Slice_irgendeine_Sexte - 1])
        Slice_nach_irgendeiner_Sexte = float(Offset_irgendeiner_Sexte) + float(getattr(n, 'quarterLength', 0.0))
        Töne_Slice_vor_irgendeiner_Sexte = klingende_Noten_ohne_unterste(score, Slice_vor_irgendeiner_Sexte)
        Töne_Slice_nach_irgendeiner_Sexte = klingende_Noten_ohne_unterste(score, Slice_nach_irgendeiner_Sexte)

        schrittweise_vor_irgendeiner_Sexte  = any(ist_Schritt(n, n2) for n2 in Töne_Slice_vor_irgendeiner_Sexte)
        schrittweise_nach_irgendeiner_Sexte  = any(ist_Schritt(n, n2) for n2 in Töne_Slice_nach_irgendeiner_Sexte)
        Aktive_Bewegung_der_Sexte = (not schrittweise_vor_irgendeiner_Sexte) or (not schrittweise_nach_irgendeiner_Sexte)
        if Aktive_Bewegung_der_Sexte:
            bewegte_Sexte.append(n)
        if n.quarterLength > (Annotationston.quarterLength / 2):
            Lange_Sexte.append(n)

    ######## Vergleichsprogramm: Quinte oder Sexte als Dissonanz behandelt.#########
    if (Quinte_Töne and Sexte_Töne) and (Beide_Töne_klingen_gleichzeitig or len(bewegte_Quinte) >= 2 or len(bewegte_Sexte) >= 2):
        
        Anzahl_der_Quinte = len(Quinte_Töne)
        Anzahl_der_Sexte = len(Sexte_Töne)
        Gesamte_Dauerzeit_der_Quinte = sum(float(getattr(n, 'quarterLength', 0.0)) for n in Quinte_Töne)
        Gesamte_Dauerzeit_der_Sexte = sum(float(getattr(n, 'quarterLength', 0.0)) for n in Sexte_Töne)
        harmonieeigener = None
        harmoniefremder = None
  
        # Punktzahlung：
        if Anzahl_der_Quinte == Anzahl_der_Sexte:
            Punkt_Anzahl_Quinte, Punkt_Anzahl_Sexte = 1, 1
        elif Anzahl_der_Quinte > Anzahl_der_Sexte:
            Punkt_Anzahl_Quinte, Punkt_Anzahl_Sexte = 1, 0
        elif Anzahl_der_Sexte  >Anzahl_der_Quinte:
            Punkt_Anzahl_Quinte, Punkt_Anzahl_Sexte = 0, 1
        else:
            Punkt_Anzahl_Quinte, Punkt_Anzahl_Sexte = 0, 0

        if Gesamte_Dauerzeit_der_Quinte == Gesamte_Dauerzeit_der_Sexte:
            Punkt_Gesamtdauerzeit_Quinte, Punkt_Gesamtdauerzeit_Sexte = 1, 1
        elif Gesamte_Dauerzeit_der_Quinte > Gesamte_Dauerzeit_der_Sexte:
            Punkt_Gesamtdauerzeit_Quinte, Punkt_Gesamtdauerzeit_Sexte = 1, 0
        elif Gesamte_Dauerzeit_der_Sexte > Gesamte_Dauerzeit_der_Quinte:
            Punkt_Gesamtdauerzeit_Quinte, Punkt_Gesamtdauerzeit_Sexte = 0, 1
        else:
            Punkt_Gesamtdauerzeit_Quinte, Punkt_Gesamtdauerzeit_Sexte = 0, 0


        
        Punkt_Lange_Quinte = 2 if Lange_Quinte else 0
        Punkt_Lange_Sexte = 2 if Lange_Sexte else 0
        
        Punkt_Bewegung_nach_Quinte = 2 if schrittweise_nach_Quinte is False else 0
        Punkt_Bewegung_vor_Quinte  = 2 if schrittweise_vor_Quinte is False else 0
        Punkt_Bewegung_nach_Sexte  = 2 if schrittweise_nach_Sexte is False else 0
        Punkt_Bewegung_vor_Sexte   = 2 if schrittweise_vor_Sexte is False else 0

        Punkt_Bewegung_Quinte = Punkt_Bewegung_vor_Quinte + Punkt_Bewegung_nach_Quinte
        Punkt_Bewegung_Sexte = Punkt_Bewegung_vor_Sexte + Punkt_Bewegung_nach_Sexte

        Gesamtpunkt_Quinte = Punkt_Anzahl_Quinte + Punkt_Gesamtdauerzeit_Quinte + Punkt_Bewegung_Quinte + Punkt_Lange_Quinte
        Gesamtpunkt_Sexte = Punkt_Anzahl_Sexte + Punkt_Gesamtdauerzeit_Sexte + Punkt_Bewegung_Sexte + Punkt_Lange_Sexte

        # Regeln der Punktzahlung：
            #  1.Wer mehr ist, bekommt 1 Punkt(Bei Gleichstand kriegen beide einen Punkt); 
            #  2.Wessen gesamte Dauerzeit länger ist, bekommt 1 Punkt(Bei Gleichstand kriegen beide einen Punkt); 
        if Gesamtpunkt_Quinte > Gesamtpunkt_Sexte:
            harmonieeigener, harmoniefremder,Akkord = erste_Quinte.name, erste_Sexte.name,'Grundakkord'
        elif Gesamtpunkt_Sexte > Gesamtpunkt_Quinte:
            harmonieeigener, harmoniefremder,Akkord = erste_Sexte.name, erste_Quinte.name,'Sextakkord'
        
        # GleichstandsRegel：Wer zuerst vokommt, ist als akkordeigenen Ton anzusehen 
        elif Gesamtpunkt_Sexte == Gesamtpunkt_Quinte:                         
            if Offset_Quinte_Nr1 < Offset_Sexte_Nr1:
                harmonieeigener, harmoniefremder,Akkord = erste_Quinte.name, erste_Sexte.name,'Grundakkord'
            elif Offset_Sexte_Nr1 < Offset_Quinte_Nr1:
                harmonieeigener, harmoniefremder,Akkord = erste_Sexte.name, erste_Quinte.name,'Sextakkord'
            else:
                harmonieeigener, harmoniefremder,Akkord = erste_Quinte.name, erste_Sexte.name,'Grundakkord'

        return {
            'Harmonieeigener': harmonieeigener, 'Harmoniefremder': harmoniefremder,'Akkord':Akkord, 
            'scores':   {erste_Quinte.name: {'count': Anzahl_der_Quinte, 'len': Gesamte_Dauerzeit_der_Quinte, 'bewegte_Quinte': len(bewegte_Quinte), 'score': Gesamtpunkt_Quinte},
                        erste_Sexte.name:  {'count': Anzahl_der_Sexte, 'len': Gesamte_Dauerzeit_der_Sexte, 'bewegte_Sexte': len(bewegte_Sexte), 'score': Gesamtpunkt_Sexte}}

        }

        # 'scores':   {erste_Quinte.name: {'count': Anzahl_der_Quinte, 'len': Gesamte_Dauerzeit_der_Quinte, 'Schrittweise':schrittweise_nach_Quinte, 'score': Gesamtpunkt_Quinte},
            #             erste_Sexte.name:  {'count': Anzahl_der_Sexte, 'len': Gesamte_Dauerzeit_der_Sexte, 'Schrittweise':schrittweise_nach_Quinte, 'score': Gesamtpunkt_Sexte}},
     # "Slice_5": Slice_5, "Slice_6": Slice_6, "len(Grenzen)": len(Grenzen),


    ##### Wenn im Segment keine reine Quinte oder keine Sexte gefunden werden kann, kommt es nicht in Vergleichprogramm ein. ########
    else:
        return None