from typing import List, Tuple, Optional
from music21 import chord, interval, note

def bestimme_dissonanz_und_partner(
    El: chord.Chord,
    Intervall: interval.Interval,
    oberste_note: note.Note,
    bass_note: note.Note
) -> Tuple[List, List]:
    """
    Kapselt die Logik zur Bestimmung von Akkorddissonanz & Partner
    für die Modi 'G.' / 'G.5' (gebrochener dissonanter Akkord).

    Rückgabe:
        Akkorddissonanz: Liste von Noten/Pitches (wie im Originalcode)
        Partner:         Liste von Noten/Pitches (gleiche Länge/Zuordnung)
    """
    Akkorddissonanz: List = []
    Partner: List = []

    if El.seventh:
        rt, fv = El.root(), El.fifth
        if rt is not None and fv is not None:
            iv = interval.Interval(rt, fv)
            if iv.simpleName in ('d5', 'A4'):                       #Beim verminderten oder halb-verminderten Vierklang sind die Quinte und Septime als Dissonanzen anzusehen#
                Akkorddissonanz = [El.seventh, El.fifth]
                Partner = [El.root(), El.root()]
            else:
                if El.inversion() == 2:                            #Beim Terz-Quartakkord sind "die Septime und die Quinte" (mit Text "G.5") oder "die Septime und der Grunton" (ohne Text) als Dissonanzen anzusehen.
                    if El.lyric and El.lyric == "G.5":
                        Akkorddissonanz = [El.seventh, El.fifth]
                        Partner = [El.root(), El.root()]
                    else:
                        Akkorddissonanz = [El.seventh, El.root()]
                        Partner = [El.root(), El.fifth]
                else:
                    Akkorddissonanz = [El.seventh]                #Bei den anderen Vierklangen ist nur die Quinte als Dissonanzen anzusehen       
                    Partner = [El.root()]
        else:
            Akkorddissonanz = [El.seventh]
            Partner = [El.root()]

    elif El.isTriad() and El.inversion() == 2:                  #Beim Quart-Sextakkord 
        if El.lyric and El.lyric == "G.5":
            Akkorddissonanz = [El.fifth]
            Partner = [El.root()]
        else:
            Akkorddissonanz = [El.root()]
            Partner = [El.fifth]

    elif El.isTriad() and El.quality == 'diminished':        #Beim verminderten Dreiklang
        Akkorddissonanz = [El.fifth]
        Partner = [El.root()]


    else:
        Akkorddissonanz = []
        Partner = []

    return Akkorddissonanz, Partner