from music21 import note, chord, interval
from Notenbearbeitung import Noten_am_Offset, ist_Transition,notes_in_time_span
from dataclasses import dataclass
from typing import Any, Optional, Sequence
import bisect
import math
import copy


@dataclass
class HarmonischerRhythmusSlice:
    """Zustand eines vom Gerüstbass getragenen Harmonieabschnitts.

    Die drei Dissonanzfelder bleiben zunächst ``None``. Sie sind bewusst als
    Platzhalter angelegt, damit die spätere Analyse zentral über die bereits in
    diesem Modul vorhandenen Beurteilungsfunktionen erfolgen kann.
    """

    Anfang: float
    Ende: float
    Gerüstbass: note.Note
    Tönenamen: tuple
    Klang_ist_dissonant: Optional[bool] = None
    Gerüstbass_ist_dissonant: Optional[bool] = None
    Klangdissonanzname: Optional[bool] = None


    def enthält(self, offset, tol=1e-6):
        """Halboffene Zugehörigkeit: Anfang <= offset < Ende."""
        zeit = float(offset)
        return (
            zeit >= self.Anfang - tol
            and zeit < self.Ende
            and not math.isclose(zeit, self.Ende, abs_tol=tol)
        )


class HarmonischerRhythmusKontext:
    """Verwaltet den aktiven Harmonieabschnitt während des Offset-Scans."""

    def __init__(self):
        self.aktiver_Slice = None

    def zurücksetzen(self):
        self.aktiver_Slice = None

    def aktualisieren(self, offset, Töne_am_Anfang: Sequence[note.Note],Original_Slices):
        """Gibt ``(Slice, geerbt)`` zurück, ohne Dissonanzen zu analysieren.

        Ein noch aktiver Slice hat Vorrang vor einem neu gescannten Klang. Erst
        außerhalb seines Zeitbereichs kann bei mehr als zwei Tönen der tiefste
        Ton einen neuen Harmonieabschnitt eröffnen.
        """
        zeit = float(offset)
        if self.aktiver_Slice is not None and self.aktiver_Slice.enthält(zeit):
            return self.aktiver_Slice, True

        self.aktiver_Slice = None
        if len(Töne_am_Anfang) <= 2:
            return None, False

        gerüstbass = min(Töne_am_Anfang, key=lambda n: n.pitch.midi)
        ende = float(gerüstbass.abs_offset) + float(gerüstbass.quarterLength)
        if ende <= zeit:
            return None, False

        Töne_im_Bereich = notes_in_time_span(Original_Slices, zeit, ende)
        Beurteilung = Beurteilung_dissonanten_Klangs(chord.Chord(Töne_am_Anfang),None,None,None,Töne_im_Bereich)
        Dissonantklang = Beurteilung.get("dissonant_notes")
        Tönenamen= {ton.name for ton in Töne_am_Anfang}
        self.aktiver_Slice = HarmonischerRhythmusSlice(
            Anfang=zeit,
            Ende=ende,
            Gerüstbass=gerüstbass,
            Klangdissonanzname=Dissonantklang,
            Tönenamen=Tönenamen
        )
        return self.aktiver_Slice, False

def index_von_offset(Grenzen, offset, tol=1e-6):
    i = bisect.bisect_left(Grenzen, float(offset))
    if i < len(Grenzen) and math.isclose(Grenzen[i], float(offset), abs_tol=tol):
        return i
    # 有时 offset 会落在两点之间但“应该属于左边”
    if i > 0 and math.isclose(Grenzen[i-1], float(offset), abs_tol=tol):
        return i - 1
    raise ValueError(f"offset {offset} 不在 Grenzen 中（tol={tol}）")

def Intervalls_von_Basston_im_Akkord(ch):
    bass = ch.bass()
    pitches = sorted(ch.pitches, key=lambda p: p.ps)
    return [interval.Interval(bass, p) for p in pitches if p != bass]

def Generalbassbezifferung(Akkordtöne, Basston):
    """Gibt die Ziffernkombination der Akkordtöne über dem Bass zurück.

    Oktavverdopplungen bleiben als 8 erhalten. Zusammengesetzte Intervalle
    über der None werden um Oktaven reduziert. Beispiele: C-F-A -> 46,
    C-E-G -> 35.
    """
    if not Akkordtöne:
        raise ValueError("Aus einer leeren Tonliste kann keine Ziffernkombination gebildet werden")
    if not isinstance(Basston, note.Note):
        raise TypeError("Basston muss eine music21.note.Note sein")

    Intervallzahlen = []
    for Ton in Akkordtöne:
        Intervallzahl = interval.Interval(Basston, Ton).generic.undirected
        while Intervallzahl > 9:
            Intervallzahl -= 7
        if Intervallzahl > 1:
            Intervallzahlen.append(Intervallzahl)

    if not Intervallzahlen:
        return 1

    return int(''.join(str(z) for z in sorted(Intervallzahlen)))

def finden_Note_über_Bass(ch, Nummer):
    bass = ch.bass()
    Noten = []
    for n in ch.notes:
        if interval.Interval(bass, n).generic.simpleUndirected == Nummer:
            Noten.append(n)

    if len(Noten) == 1:
        return Noten[0]
    
    return min(Noten, key=lambda n: n.pitch.midi)

def Verständigung_des_Septakkordes(Anfang,Grenzen,score_slices,Akkordobjekt,i=None):
    
    Vollständige_Septakkordnamen=[
        'major seventh chord', 'dominant seventh chord','minor seventh chord',
        'minor-augmented tetrachord','augmented major tetrachord','diminished seventh chord','half-diminished seventh chord']
    
    Akkord = Akkordobjekt.closedPosition()
    Akkordtöne = list(Akkord.notes)

    Grundton = note.Note(Akkordobjekt.root()) if Akkordobjekt.root() else None
    Terz = note.Note(Akkordobjekt.third) if Akkordobjekt.third else None
    Quinte = note.Note(Akkordobjekt.fifth) if Akkordobjekt.fifth else None
    Septime = note.Note(Akkordobjekt.seventh) if Akkordobjekt.seventh else None
    Basston = note.Note(Akkordobjekt.bass()) if Akkordobjekt.bass() else None
    
    Noten_davor=[]

    if len(Akkordtöne) == 3 and Septime and Grundton and (Terz or Quinte):
        if i is None:
            i = index_von_offset(Grenzen, Anfang)
        if Terz is None:
            for j in range(i - 1, -1, -1):
                a0 = float(Grenzen[j])
                Noten_davor = Noten_am_Offset(score_slices, a0)
                for n in Noten_davor:
                    Interval=interval.Interval(n, Grundton).simpleName
                    if Interval in ('M3','m3') and Grundton.pitch.midi < n.pitch.midi or Interval in ('M6','m6') and Grundton.pitch.midi > n.pitch.midi:
                        # zu garantieren, dass der neu hinzuzufügende Ton höher ist als der Basston.
                        n_Kopie = copy.deepcopy(n)
                        while n_Kopie.pitch.midi <= Basston.pitch.midi:
                            n_Kopie.pitch.octave += 1
                        Akkord = chord.Chord(list(Akkordobjekt.notes) + [n_Kopie])
                        return Akkord
            return Akkordobjekt
        
        elif Quinte is None:
            for j in range(i - 1, -1, -1):
                a0 = float(Grenzen[j])
                Noten_davor = Noten_am_Offset(score_slices, a0)
                for n in Noten_davor:
                    Interval=interval.Interval(n, Terz).simpleName
                    if Interval in ('M3','m3') and Terz.pitch.midi < n.pitch.midi or Interval in ('M6','m6') and Terz.pitch.midi > n.pitch.midi:
                        # zu garantieren, dass der neu hinzuzufügende Ton höher ist als der Basston.
                        n_Kopie = copy.deepcopy(n)
                        while n_Kopie.pitch.midi <= Basston.pitch.midi:
                            n_Kopie.pitch.octave += 1
                        Akkord = chord.Chord(list(Akkordobjekt.notes) + [n_Kopie])
                        return Akkord
            return Akkordobjekt
    else:
        return Akkordobjekt


def ist_Ein_Septakkord(Klang,Zahl=None,Töne_im_Bereich=None,Offset=None):
    Bass = note.Note(Klang.bass()) if Klang.bass() else None
    Terz = note.Note(Klang.third) if Klang.third else None
    Quinte = note.Note(Klang.fifth) if Klang.fifth else None
    Septime = note.Note(Klang.seventh) if Klang.seventh else None
    Grundton = note.Note(Klang.root()) if Klang.root() else None
    Einfachklang= Klang.closedPosition()
    Umkehrung= Klang.inversion()
    Zufällige_Dissonanz=None
    if Klang.isSeventh():
        if Umkehrung == 0:
            return 37
        elif Umkehrung == 1:
            if Töne_im_Bereich and len(Töne_im_Bereich) > 0:
                Auflösung = Wie_ein_Klang_aufgelöst('allgemeiner Klang',Töne_im_Bereich,None,None,Grundton)
                if Auflösung == 'Grundton':
                  return 56
            else:
                return 56
        elif Umkehrung == 2:
            return 34
        elif Umkehrung == 3:
            if Töne_im_Bereich and len(Töne_im_Bereich) > 0:
                Auflösung = Wie_ein_Klang_aufgelöst('allgemeiner Klang',Töne_im_Bereich,None,None,Grundton)
                if Auflösung == 'Grundton':
                  return 24
            return 24
    elif len(Einfachklang.notes) == 3:
        if Septime and Grundton and (Terz or Quinte):
            if Grundton.name == Bass.name:
                if Terz and Töne_im_Bereich:
                    Auflösung = Wie_ein_Klang_aufgelöst('37',Töne_im_Bereich,None,None,Septime)
                    return 37 if Auflösung == '37' else False
                return 37 if Terz else 57
            elif Terz and Terz.name==Bass.name:
                if Töne_im_Bereich:
                    Auflösung = Wie_ein_Klang_aufgelöst('allgemeiner Klang',Töne_im_Bereich,None,None,Grundton)
                    return 56 if Auflösung == 'Grundton' else False
                return 56
            elif Quinte and Quinte.name==Bass.name:
                if Töne_im_Bereich:
                    Auflösung = Wie_ein_Klang_aufgelöst('34',Töne_im_Bereich,None,None,Grundton,Offset)
                    return 34 if Auflösung == '34' else False
                return 34
            elif Septime.name == Bass.name:#
                #print('Grundton für 24',Klang,Grundton.nameWithOctave)
                if Terz:
                    return 24
                elif Quinte:
                    if Töne_im_Bereich:
                        Auflösung = Wie_ein_Klang_aufgelöst('26',Töne_im_Bereich,None,Grundton,None,Offset=None)
                        return 24 if Auflösung == '26' else False
                    return 24
        else:
            Zufällige_Dissonanz=True
            Intervalle=Intervalls_von_Basston_im_Akkord(Einfachklang)
            Intervallzahle = ''.join(str(i.generic.value) for i in Intervalle)
            if Intervallzahle in ['26','67','57']:
                Note1 = Bass
                Note2 = finden_Note_über_Bass(Klang, int(Intervallzahle[0]))
                Note3 = finden_Note_über_Bass(Klang, int(Intervallzahle[1]))
                Auflösung = Wie_ein_Klang_aufgelöst(Intervallzahle,Töne_im_Bereich,Note1,Note2,Note3,Offset)
                if Auflösung in ['24','26','57','37']:
                    return Auflösung
    elif Zahl and Zahl in [34,56,37,57,24,26]:
        return Zahl
    else:
        return False
    
def Beurteilung_dissonanten_Klangs(
    Objekt, Zahl=None, Kennzeichen=None, Modusanfang=None, Töne_im_Bereich=None,
    Hilfstimme_Kontext=None
):
    
    if not isinstance(Objekt, chord.Chord):
        raise TypeError
    
    result = {
        'dissonanter_Akkord': False,
        'category': None,
        'qualität': None,
        'Generalbassnummer':None,
        'Septakkord':False,
        'dissonant_notes': [],
        'Parnerton': None,
        'pcset': set(),
        'akkordtöne': set(),
        'chord': None,
        'Objekt':Objekt,
        'None':None,
        'Umkehrung':None,
        'Grundton':None,
        'Basston': None,
        'zusätzliche_Konsonanz':None
    }
    
#die Inforamtionen, die vor der Klangvorständigung festgestellt werden müssen:

 
    Umkehrung = Objekt.inversion()
    Alle_Akkordtöne=list(Objekt.notes)
    Nonee=None
    Akkord = Objekt.closedPosition()
    Akkordtöne = list(Akkord.notes)
    Töne_name = {n.name for n in Akkordtöne if isinstance(n, note.Note)}
    result['akkordtöne'] = Töne_name 
    
    oberste_note = max(Alle_Akkordtöne, key=lambda n: n.pitch.midi)
    Basston = min(Alle_Akkordtöne, key=lambda n: n.pitch.midi)

    Grundton = note.Note(Objekt.root()) if Objekt.root() else None
    Terz = note.Note(Objekt.third) if Objekt.third else None
    Quinte = note.Note(Objekt.fifth) if Objekt.fifth else None
    Septime = note.Note(Objekt.seventh) if Objekt.seventh else None

    result['Grundton'] = Grundton

    if Zahl is None:
        Zahl = Generalbassbezifferung(Akkordtöne, Basston)

    Septakkord=ist_Ein_Septakkord(Objekt,Zahl,Töne_im_Bereich,Modusanfang)

    def Annotationston_ist_Transition():
        if Hilfstimme_Kontext is None:
            return False
        Annotationston, Elemente, Annotationston_Index = Hilfstimme_Kontext
        return ist_Transition(Annotationston,Elemente,modus="Hilfstimme",Zielindex=Annotationston_Index)
 
    if Kennzeichen and 'B' in Kennzeichen:
        result['dissonant_notes'] = [Basston]
        if Septakkord==34:
            result['dissonant_notes'] = [Septime,Basston]
    else:
        if len(Akkordtöne) == 2:
            if Zahl == 7:
                result['dissonant_notes'] = [oberste_note]
            elif Zahl == 2:
                result['dissonant_notes'] = [Basston]
            elif Zahl == 4:
                if interval.Interval(Akkordtöne[0], Akkordtöne[1]).simpleName == 'P4':
                    wie=Wie_ein_Klang_aufgelöst("allgemeiner Klang",Töne_im_Bereich,None,None,oberste_note)
                    if wie== 'Grundton':
                        result['dissonant_notes'] = [oberste_note]
                elif interval.Interval(Akkordtöne[0], Akkordtöne[1]).simpleName == 'A4':
                    result['dissonant_notes'] = [Basston]
                else:
                    print('Unbekannte Quartegerüst:',Modusanfang)
            elif Zahl == 5 and interval.Interval(Akkordtöne[0], Akkordtöne[1]).simpleName == 'd5':
                result['dissonant_notes'] = [oberste_note]
            elif Zahl == 6 and interval.Interval(Akkordtöne[0], Akkordtöne[1]).simpleName == 'A6': #übermäßige Sexte
                result['dissonant_notes'] = [Basston,oberste_note]
            else:
                #print('Fehler bei 2-Tönige_Klanggerüst::was ist die Klangdissonanz???','Modusanfang:',Modusanfang)
                return result
        elif Akkord.isTriad():
                if Akkord.isAugmentedTriad() or Akkord.isDiminishedTriad():
                    result['dissonant_notes'] = [Quinte]
                elif Zahl == 46:
                    result['dissonant_notes'] = [
                        Basston if Annotationston_ist_Transition() else Grundton
                    ]
                elif Akkord.isItalianAugmentedSixth():
                    result['dissonant_notes'] = [Basston,oberste_note]
        elif Septakkord:
            result['Septakkord'] = True
            if isinstance(Septakkord, str):
                gefundene_Töne = [Basston]
                for zahl in Septakkord:
                    ziel_intervall = int(zahl)
                    for Ton in sorted(Töne_im_Bereich, key=lambda x: x.offset):
                        intervall = interval.Interval(Basston, Ton)
                        if (
                            intervall.generic.simpleDirected == ziel_intervall
                            and Ton.pitch.midi > Basston.pitch.midi
                        ):
                            gefundene_Töne.append(Ton)
                            break
                Akkordtöne = gefundene_Töne
                Töne_name = {n.name for n in Akkordtöne if isinstance(n, note.Note)}
                result['akkordtöne'] = Töne_name 
                Akkord = chord.Chord(gefundene_Töne)
                Grundton = note.Note(Akkord.root()) if Akkord.root() else None
                Quinte = note.Note(Akkord.fifth) if Akkord.fifth else None
                Septime = note.Note(Akkord.seventh) if Akkord.seventh else None
            if Akkord.commonName in ['diminished seventh chord',
                            'enharmonic equivalent to diminished triad',
                            'incomplete half-diminished seventh chord',
                            'half-diminished seventh chord']:
                result['dissonant_notes'] = [Septime,Quinte]
            else:
                if Umkehrung in [0,1,3]:
                    result['dissonant_notes'] = [Septime]
                elif Umkehrung == 2:
                    #print(Modusanfang,Objekt,Akkord.commonName)
                    result['dissonant_notes'] = [Septime,Quinte]
                else:
                    print('Bug-Meldung:Unbekante Vierklangsumkehrung:',Modusanfang,Objekt)
    return result

def Beurteilung_dissonanten_Klangs2(Objekt,Vollständigung=None,Anfang=None,Grenzen=None,score_slices=None,
    Annotationskennzeichen=None,Töne_im_Bereich=None,i=None
):
    
    if not isinstance(Objekt, chord.Chord):
        raise TypeError
    
    result = {
        'dissonanter_Akkord': False,
        'category': None,
        'qualität': None,
        'Generalbassnummer':None,
        'Septakkord':False,
        'dissonant_notes': [],
        'Parnerton': None,
        'pcset': set(),
        'akkordtöne': set(),
        'chord': None,
        'Objekt':Objekt,
        'None':None,
        'Umkehrung':None,
        'Grundton':None,
        'Basston': None,
        'zusätzliche_Konsonanz':None
    }
    
#die Inforamtionen, die vor der Klangvorständigung festgestellt werden müssen:

 
    Umkehrung = Objekt.inversion()
    Alle_Akkordtöne=list(Objekt.notes)
    if not Alle_Akkordtöne:
        print(f"⚠️ Leerer Akkord bei Offset: {Anfang}",Objekt)
        return None
    oberste_note = max(Alle_Akkordtöne, key=lambda n: n.pitch.midi)
    bass_note = min(Alle_Akkordtöne, key=lambda n: n.pitch.midi)
    Nonee=None

#die vor der Klangvorständigung
    if Vollständigung:
        if i:
            i = i
        Objekt=Verständigung_des_Septakkordes(Anfang,Grenzen,score_slices,Objekt,i)
        Alle_Akkordtöne=list(Objekt.notes)
    
    Akkord = Objekt.closedPosition()
    Akkordtöne = list(Akkord.notes)
    Qualität = Akkord.commonName
    
#die Reine-Oktave-Intervall beibehalten
    if len(Alle_Akkordtöne) == 2 and interval.Interval(Alle_Akkordtöne[0], Alle_Akkordtöne[1]).simpleName =='P1':
        Akkordtöne=Alle_Akkordtöne
    

    result['Umkehrung'] = Umkehrung
    result['chord'] = Akkord
    result['qualität'] = Qualität
    pcs_abs = {n.pitch.pitchClass for n in Alle_Akkordtöne if isinstance(n, note.Note)}
    result['pcset'] = pcs_abs
    Töne_name = {n.name for n in Akkordtöne if isinstance(n, note.Note)}
    result['akkordtöne'] = Töne_name 

    Basston = note.Note(Objekt.bass()) if Objekt.bass() else None
    Grundton = note.Note(Objekt.root()) if Objekt.root() else None
    Terz = note.Note(Objekt.third) if Objekt.third else None
    Quinte = note.Note(Objekt.fifth) if Objekt.fifth else None
    Septime = note.Note(Objekt.seventh) if Objekt.seventh else None
    
    Intervall=interval.Interval(bass_note, oberste_note)
    Intervalle=Intervalls_von_Basston_im_Akkord(Akkord)
    Intervallzahle =[i.generic.value for i in Intervalle]

    result['Parnerton'] = Grundton
    result['Grundton'] = Grundton
    result['Basston'] = Basston
    
    if Intervall.name in ('m9','M9','m16','M16','m23','M23','m30','M30'):
        Nonee = oberste_note

    if len(Akkordtöne) == 4:
        if Akkord.isSeventh():
            result['dissonanter_Akkord'] = True
            result['Septakkord'] = True
            result['category'] = 'Septakkord'
            if Qualität in ('major seventh chord', 'dominant seventh chord','minor seventh chord','minor-augmented tetrachord'):
                if Umkehrung != 2:
                    result['dissonant_notes'] = [Septime]
                if Umkehrung == 2:      
                    if Annotationskennzeichen and 'G' in Annotationskennzeichen:
                        result['dissonant_notes'] = [Grundton,Septime]
                    else:
                        result['Generalbassnummer'] = '34'  
                        result['dissonant_notes'] = [Quinte,Septime]
            elif Qualität in ('diminished seventh chord','half-diminished seventh chord'):
                result['dissonant_notes'] = [Quinte,Septime]
            elif Akkord.isGermanAugmentedSixth():  
                result['dissonant_notes'] = [Grundton,Terz,Quinte,Septime]
                result['category'] = 'Akkord mit übermäßiger Sexte'
            else:
                result['dissonant_notes'] = [Septime]
                result['category'] = 'Unbekannter_Septakkord'
        else:
            return result
    
    elif len(Akkordtöne) == 3:
        if Akkord.isTriad(): 
            if Akkord.isAugmentedTriad() or Akkord.isDiminishedTriad():
                result['dissonanter_Akkord'] = True
                result['dissonant_notes'] = [Quinte]
                if Akkord.isDiminishedTriad():
                    result['category'] = 'verminderter Dreiklang'
                if Akkord.isAugmentedTriad():
                    result['category'] =  'übermäßiger Dreiklang'
            
            elif (Akkord.isMajorTriad() or Akkord.isMinorTriad()) and Umkehrung == 2:
                result['Generalbassnummer'] = '46' 
                result['dissonanter_Akkord'] = True
                result['category'] = 'Quartsextakkord'
                if Annotationskennzeichen and 'G' in Annotationskennzeichen:
                    result['dissonant_notes'] = [Grundton]
                else:
                    result['dissonant_notes'] = [Quinte]

            elif Akkord.isItalianAugmentedSixth():
                result['dissonanter_Akkord'] = True
                result['category'] = 'Akkord mit übermäßiger Sexte'
                result['dissonant_notes'] = [Grundton, Terz, Quinte]
            
            else:
                result['dissonant_notes'] = [Quinte]
                result['category'] = 'Unbekannter_Dreiklang'

        elif Septime and Grundton and (Terz or Quinte):
            if Terz:
                if Töne_im_Bereich:
                    Wie_Auflösung = Wie_ein_Klang_aufgelöst("37",Töne_im_Bereich,Note1=None,Note2=None,Note3=Septime)
                    if Wie_Auflösung =="7-6":
                        result['dissonanter_Akkord'] = False
                    elif Wie_Auflösung =="37":
                        result['dissonanter_Akkord'] = True
                        result['category'] = 'unvollständigen Septakkord'
                        if Qualität in ('incomplete major-seventh chord','incomplete dominant-seventh chord','incomplete minor-seventh chord'):
                            result['dissonant_notes'] = [Septime]
                        elif Qualität == 'enharmonic equivalent to diminished triad':
                            result['dissonant_notes'] = [Septime]
                        else:
                            result['dissonant_notes'] = [Septime]
                            result['category'] = 'Unbekannter_Dreiklang'
                else:
                    result['dissonanter_Akkord'] = True
                    result['category'] = 'unvollständigen Septakkord'
                    result['dissonant_notes'] = [Septime]
            if Quinte:
                result['dissonanter_Akkord'] = True
                result['category'] = 'unvollständigen Septakkord'
                if Qualität in ('incomplete major-seventh chord','incomplete dominant-seventh chord'):
                    if Umkehrung == 1:
                        result['dissonant_notes'] = [Septime]
                    elif Umkehrung == 3:
                        if Töne_im_Bereich:
                            Wie_Auflösung= Wie_ein_Klang_aufgelöst("26", Töne_im_Bereich,Note1=None,Note2=None,Note3=Quinte)
                            if Wie_Auflösung == "25":
                                result['dissonanter_Akkord'] = True
                                result['dissonant_notes'] = [Septime]
                            elif Wie_Auflösung == "26":
                                result['dissonanter_Akkord'] = True
                                result['dissonant_notes'] = [Septime]
                        else:
                            result['dissonanter_Akkord'] = True
                            result['dissonant_notes'] = [Septime]
                    else:

                        if Annotationskennzeichen and 'G' in Annotationskennzeichen:
                            result['dissonant_notes'] = [Grundton,Septime]
                        else:
                            result['dissonant_notes'] = [Quinte,Septime]
                            result['Generalbassnummer'] = '34' 
                elif Qualität in ('incomplete half-diminished seventh chord','enharmonic equivalent to diminished triad'):
                    result['dissonant_notes'] = [Quinte,Septime]
                else:
                    result['dissonant_notes'] = [Septime]
                    result['category'] = 'Unbekannter_Dreiklang'
            # nicht bei Standartmodus
            if Töne_im_Bereich:
                if Intervallzahle == [2,5]:
                    Sekunde = finden_Note_über_Bass(Objekt, 2)
                    Quinte = finden_Note_über_Bass(Objekt, 5)
                    print(Anfang,Töne_im_Bereich)
                    Wie_Auflösung = Wie_ein_Klang_aufgelöst("25",Töne_im_Bereich,Basston,Sekunde,Quinte)
                    if Wie_Auflösung=="36":
                        result['dissonanter_Akkord'] = False
                    elif Wie_Auflösung=="35":
                        result['dissonanter_Akkord'] = False
                    elif Wie_Auflösung=="25": 
                        result['dissonanter_Akkord'] = True
                        result['dissonant_notes'] = [Basston]
                    return result

                elif Intervallzahle == [4,7]:
                    Quarte = finden_Note_über_Bass(Objekt, 4)
                    Septime = finden_Note_über_Bass(Objekt, 7)
                    Wie_Auflösung = Wie_ein_Klang_aufgelöst("47",Töne_im_Bereich,None,Quarte,Septime)
                    if Wie_Auflösung=="37":
                        result['dissonanter_Akkord'] = True
                        result['category'] = 'Septakkord'
                        result['dissonant_notes'] = [Septime]
                    elif Wie_Auflösung=="46":
                        result['dissonanter_Akkord'] = True
                        result['category'] = 'Quartsextakkord'
                        result['dissonant_notes'] = [Septime]
                        if Annotationskennzeichen and 'B' in Annotationskennzeichen:
                            result['dissonant_notes'] = [Basston]
                        else:
                            result['dissonant_notes'] = [Quarte]
                    elif Wie_Auflösung=="47":
                        result['dissonanter_Akkord'] = True
                        result['category'] = 'Quartseptakkord'
                        result['dissonant_notes'] = [Quarte,Septime]
                    elif Wie_Auflösung=="36":
                        result['dissonanter_Akkord'] = False
                    return result
                
                elif Intervallzahle == [4,5]:
                    Quarte = finden_Note_über_Bass(Objekt, 4)
                    Wie_Auflösung = Wie_ein_Klang_aufgelöst("45",Töne_im_Bereich,Quarte,Quinte)
                    if Wie_Auflösung=="35":
                        result['dissonanter_Akkord'] = False
                    elif Wie_Auflösung=="45":
                        result['dissonanter_Akkord'] = True
                        result['dissonant_notes'] = [Quarte]

                elif Intervallzahle == [3,9]:
                    Nonee = finden_Note_über_Bass(Objekt, 2)
                    result['dissonanter_Akkord'] = True
                    result['category'] = '39'
                    result['dissonant_notes'] = [Quarte]
            
        elif Terz and Nonee and Grundton.name == Basston.name:
            result['dissonanter_Akkord'] = True
            result['category'] = 'Dreiakkord mit None'
            result['dissonant_notes'] = [Nonee]
            
        elif Annotationskennzeichen and 'Da' in Annotationskennzeichen:
            result['dissonanter_Akkord'] = True
            result['category'] = 'Unbekannt Akkord'
            if 'B' in Annotationskennzeichen:
                result['dissonant_notes'] = [bass_note]
        else:
            return result
    
    elif len(Akkordtöne) == 2 and Akkordtöne[0].quarterLength == Akkordtöne[1].quarterLength:
        iv = interval.Interval(Akkordtöne[0], Akkordtöne[1])
        simp = iv.simpleName
        if simp in ('A4', 'd5'):
            if len(Alle_Akkordtöne) == 2 and Alle_Akkordtöne[0].quarterLength == Alle_Akkordtöne[1].quarterLength:
                result['dissonanter_Akkord'] = True
                result['category'] = 'Tritonus'
                if Akkordtöne[0].pitch.midi <= Akkordtöne[1].pitch.midi:
                    oberton, unterton = Akkordtöne[1],Akkordtöne[0]
                else:
                    oberton, unterton = Akkordtöne[0],Akkordtöne[1]
                if simp == 'A4':
                    result['dissonant_notes'] = [unterton]
                    result['Parnerton'] = oberton
                else:
                    result['dissonant_notes'] = [oberton]
                    result['Parnerton'] = unterton
                return result
            else:
                return result
        elif iv.name in ('m9','M9'):
            result['dissonanter_Akkord'] = True
            result['category'] = 'Noneakkord'
            dis = Akkordtöne[0] if Akkordtöne[0].pitch.midi > Akkordtöne[1].pitch.midi else Akkordtöne[1]
            result['dissonant_notes'] = [dis]
            return result
        else:
            return result
        
    elif len(Akkordtöne) >= 4:
        if Qualität in ('dominant-ninth', 'flat-ninth pentachord', 'minor-diminished ninth chord', 'minor-ninth chord') and Umkehrung== 0:
            result['dissonanter_Akkord'] = True
            result['category'] = 'Noneakkord'
            result['dissonant_notes'] = [Septime,Nonee]

    return result


def reduced_interval_name(iv, max_degree=9):
    """
    Nimmt ein music21.interval.Interval und gibt den Namen mit max. 15 Stufen zurück.
    z.B. M17 -> M10, P29 -> P15
    """
    Zahl = iv.generic.undirected
    while Zahl > max_degree:
        Zahl -= 7  # reduziere um Oktaven
    simple = iv.simpleName
    quality = simple[0]    # M, m, P, A, d
    return f"{quality}{Zahl}"

def Sammlung_Akkordtöne_ohne_Wiederholung(Akkord):
    Alle_Akkordtöne=list(Akkord.notes)
    Basston = min(Alle_Akkordtöne, key=lambda x: x.pitch.midi)
    Akkordtöne = []
    bestehende_Töne = set()
    Akkordtöne.append(Basston)
    bestehende_Töne.add(Basston.name)
    # die wiederholten Akkordtöne weglassen.
    for n in Alle_Akkordtöne:
        Namen = n.name
        if Namen not in bestehende_Töne:
            Akkordtöne.append(n)
            bestehende_Töne.add(Namen)
    return Akkordtöne

def Intervallkombination_im_Akkord(Akkordtöne):
    Basston = min(Akkordtöne, key=lambda x: x.pitch.midi)
    intervalzahl_list = []
    intervalqualität_list= []
    interval_list = []
    for n in Akkordtöne[1:]:
        itv = interval.Interval(Basston, n)
        simple = itv.simpleName
        Qualität = simple[0]  
        Zahl = itv.generic.undirected
        while Zahl > 9:
            Zahl -= 7
        interval_list.append((Qualität, Zahl))
    interval_list.sort(key=lambda x: int(x[1]))
    intervalzahl_list = tuple(c[1] for c in interval_list)
    intervalqualität_list = [c[0] for c in interval_list]
    return intervalqualität_list, intervalzahl_list

def vereinfachte_Bezifferung(Bezifferung,intervalqualität_list,intervalzahl_list):
    Zahlbeibehaltung = [int(x) for x in Bezifferung]   # z.B. "79" → [7,9]
    nutzbare_Qualität = []
    for Q,Nr in zip(intervalqualität_list,intervalzahl_list):
        if Nr in Zahlbeibehaltung:
            nutzbare_Qualität.append(Q[0])   # “m”, “M”, “P”…
    Qualitäten = "".join(nutzbare_Qualität)
    Qualitäten = Qualitäten.replace("P", "")
    return Qualitäten + Bezifferung


def direkte_Bezifferung(Akkordtöne):
    Basston = min(Akkordtöne, key=lambda x: x.pitch.midi)
    interval_list = []
    
    for n in Akkordtöne [1:]:
        itv = interval.Interval(Basston, n)
         # print(itv)
        sname = itv.simpleName  # e.g., "M3", "m7", "P5"
        Qualität = sname[0]        # "M", "m", "P", "A", "d"
        Zahl = itv.generic.undirected   # "3", "5", "7"
        while Zahl > 9:                   # maxmal ist 9
            Zahl -= 7  
        interval_list.append((Qualität, Zahl))
    
    # nach Zahlen neuordnen
    interval_list.sort(key=lambda x: int(x[1]))
    
    # die Ergebnisse zusammenstellen
    q_str = ''.join(q for q, _ in interval_list)
    q_str = q_str.replace("P", "")
    d_str = ''.join(str(d) for _, d in interval_list)
    return q_str + d_str



def Bezifferung_Generalbass(Akkordsinformation,Dissonanz=None,Intervallname=None):
    
    Generalbass= {
        # vierstimmig:
            #Septakkord:
        ('major seventh chord', 0): "M7", ('major seventh chord', 1): "M56", 
        ('major seventh chord', 2): "M34",  ('major seventh chord', 3): "M24",
        
        ('dominant seventh chord', 0): "D7", ('dominant seventh chord', 1): "D56", 
        ('dominant seventh chord', 2): "D34", ('dominant seventh chord', 3): "D24",
        
        ('minor seventh chord', 0): "m7", ('minor seventh chord', 1): "m56", 
        ('minor seventh chord', 2): "m34", ('minor seventh chord', 3): "m24",
        
        ('half-diminished seventh chord', 0): "h7", ('half-diminished seventh chord', 1): "h56", 
        ('half-diminished seventh chord', 2): "h34", ('half-diminished seventh chord', 3): "h24",
        
        ('diminished seventh chord', 0): "d7", ('diminished seventh chord', 1): "d56", 
        ('diminished seventh chord', 2): "d34", ('diminished seventh chord', 3): "d24",

        ('augmented major tetrachord', 0):"AM7",('augmented major tetrachord', 1):"AM56",
        ('augmented major tetrachord', 2):"AM34",('augmented major tetrachord', 3):"AM24",

        ('minor-augmented tetrachord', 0):"mM7", ('minor-augmented tetrachord', 1):"mM56",
        ('minor-augmented tetrachord', 2):"mM34",('minor-augmented tetrachord', 3):"mM24",

        ('German augmented sixth chord', 1):"Ü6",
        
            #kein-Septakkord:
        (3,5,9): "39", (3,7,9): "79",  (5,7,9): "79", (3,6,7): "67", (3,6,7): "67", (3,4,5,6):"345",(3,5,6,9): "69",(3,6,9): "69",
        # dreistimmig:
            #Akkord:
        ('major triad', 0): "M35",('major triad', 1): "M36",('major triad', 2): "M46", 
        ('minor triad', 0): "m35",  ('minor triad', 1): "m36", ('minor triad', 2): "m46",  
        ('diminished triad', 0): "d35",('diminished triad', 1): "d6",('diminished triad', 2): "d46",
        ('augmented triad', 0): "A35",  ('augmented triad', 1): "A6",  ('augmented triad', 2): "A46",
        ('Italian augmented sixth chord', 1):"Ü6",
        
        #
        ('incomplete major-seventh chord', 'Ohne Quinte',0) :"M7", ('incomplete major-seventh chord', 'Ohne Quinte', 1) :"M56",
        ('incomplete major-seventh chord','Ohne Quinte', 3) :"M24",
        
        ('incomplete dominant-seventh chord', 'Ohne Quinte', 0):"D7", ('incomplete dominant-seventh chord','Ohne Quinte', 1):"D56",
        ('incomplete dominant-seventh chord', 'Ohne Quinte',3):"D24",
        
        ('incomplete minor-seventh chord','Ohne Quinte', 0): "?m7", ('incomplete minor-seventh chord', 'Ohne Quinte',1): "?m56", 
        ('incomplete minor-seventh chord','Ohne Quinte', 3): "?m24",
        
        ('enharmonic equivalent to diminished triad','Ohne Quinte', 0):"d7",('enharmonic equivalent to diminished triad','Ohne Quinte', 1):"d56",
        ('enharmonic equivalent to diminished triad', 'Ohne Quinte',3):"d24",

        ('incomplete major-seventh chord', 'Ohne Terz',0) :"M7 ohne3", 
        ('incomplete major-seventh chord', 'Ohne Terz',2) :"M34 ohne3",('incomplete major-seventh chord','Ohne Terz', 3) :"M24 ohne3",
        
        ('incomplete dominant-seventh chord', 'Ohne Terz', 0):"?D7 ohne3", 
        ('incomplete dominant-seventh chord', 'Ohne Terz',2):"?D34 ohne3",('incomplete dominant-seventh chord', 'Ohne Terz',3):"?D24 ohne3",
        
        ('incomplete half-diminished seventh chord','Ohne Terz', 0):"h7",
        ('incomplete half-diminished seventh chord','Ohne Terz', 2):"h34",('incomplete half-diminished seventh chord','Ohne Terz', 3):"h24",
        
        ('enharmonic equivalent to diminished triad','Ohne Terz', 0):"d7",
        ('enharmonic equivalent to diminished triad','Ohne Terz', 2):"d34",('enharmonic equivalent to diminished triad', 'Ohne Terz',3):"d24",

         # mehr als vierstimmig:   
        ('dominant-ninth', 0):"D79", ('flat-ninth pentachord', 0):"Dm79", ('minor-diminished ninth chord', 0) :"mm79", ('minor-ninth chord', 0):"mM79",
        (3,5,7,9): "79"
    }
    
    Akkord=Akkordsinformation['Objekt']

    if not isinstance(Akkord, chord.Chord):
        raise TypeError

    #den Akkord in die enge Lage umwandeln, wobei die wiederholten Akkordtöne weggelassen werden.

    Qualität=Akkordsinformation['qualität']
    Umkehrung=Akkordsinformation['Umkehrung']
    geschlossener_Akkord=Akkordsinformation['chord']   
    Kateloge=Akkordsinformation['category'] 
    Dissonant_Töne=Akkordsinformation['dissonant_notes']
    Dissonanter_Akkord=Akkordsinformation['dissonanter_Akkord']

    Akkordtöne = list(geschlossener_Akkord.notes)
    Akkordtöne0 = Sammlung_Akkordtöne_ohne_Wiederholung(Akkord)
    a = (Qualität, Umkehrung) 
    
    intervalqualität_list, intervalzahl_list=Intervallkombination_im_Akkord(Akkordtöne0)
    Bezifferung = Generalbass.get(a, "Unbekannt") 
    Bezifferung0=direkte_Bezifferung(Akkordtöne0)

    Grundton = note.Note(Akkord.root()) if Akkord.root() else None
    Terz = note.Note(Akkord.third) if Akkord.third else None
    Quinte = note.Note(Akkord.fifth) if Akkord.fifth else None
    Septime = note.Note(Akkord.seventh) if Akkord.seventh else None
    None_Note=Akkordsinformation['None'] 

    def finde_intervall_name(Dissonanz, Akkord,None_Note):
        mapping = {
            "1": Akkord.root(),
            "3": Akkord.third,
            "5": Akkord.fifth,
            "7": Akkord.seventh,
            "9": None_Note
        }

        for var_name, obj in mapping.items():
            Name = obj.name if obj else None
            if Name  == Dissonanz.name:
                return var_name
        return None
    
    Akkorddissonanz= {n.name for n in Dissonant_Töne}

    if Dissonanz:
        Identität=finde_intervall_name(Dissonanz,Akkord,None_Note)
        if len(Akkordtöne) <= 2:
            return Intervallname
        else:
            if not Dissonanter_Akkord:                                                  # akkordfremde Dissonanz bearbeiten
                Bezifferung1 = Generalbass.get(intervalzahl_list, "Unbekannt") 
                if Bezifferung1 != 'Unbekannt':
                    Bezifferung2=vereinfachte_Bezifferung(Bezifferung1,intervalqualität_list,intervalzahl_list)
                    return f"{Bezifferung2}:{Intervallname}"
                else: 
                    #print(Bezifferung0,Dissonanz.Takt_Nr,Dissonanz.offset_Takt)
                    return f"{Bezifferung0}:{Intervallname}"
            else:                                                                        # akkordeigene Dissonanz bearbeiten
                if Dissonanz.name in Akkorddissonanz: 
                    if Bezifferung != 'Unbekannt':
                        return f"{Bezifferung}({Identität})"
                    else:
                        return f"{Bezifferung0}({Identität})"
                else:
                    if Bezifferung != 'Unbekannt':
                        return f"{Bezifferung}:{Intervallname}"
                    else:
                        return f"{Bezifferung0}:{Intervallname}"

    else:
        Alle_Akkordtöne=list(Akkord.notes)
        if len(Alle_Akkordtöne) == 2 and Alle_Akkordtöne[0].name == Alle_Akkordtöne[1].name:
            Akkordtöne=Alle_Akkordtöne
        
        if len(Akkordtöne) < 2:
            print("WARN: too few tones:", Akkordtöne[0].Takt_Nr if Akkordtöne[0] else None, Akkordtöne[0].offset_Takt if Akkordtöne[0] else None, Akkordtöne)
            return None
        elif len(Akkordtöne) == 2:
            Intervallname=interval.Interval(Akkordtöne[0], Akkordtöne[1]).simpleName
            return Intervallname
        else:
            if Dissonanter_Akkord or Akkord.isTriad():
                return Bezifferung
            else:
                Bezifferung1 = Generalbass.get(intervalzahl_list, "Unbekannt")
                if Bezifferung1 != 'Unbekannt':
                    Bezifferung2=vereinfachte_Bezifferung(Bezifferung1,intervalqualität_list,intervalzahl_list)
                    return Bezifferung2
                else: 
                    #print(Bezifferung0,Dissonanz.Takt_Nr,Dissonanz.offset_Takt)
                    return Bezifferung0

def Bezifferung_Auflösungsklangs(Grenzen,score_slices,Kennzeichen,PartnerTon,Auflösungsoffset):

        Töne_des_Auflösungsklangs = Noten_am_Offset(score_slices, Auflösungsoffset)
        Töne_des_Auflösungsklangs = [n for n in Töne_des_Auflösungsklangs if not n.duration.isGrace]
        
        if Töne_des_Auflösungsklangs == []:
            i = bisect.bisect_right(Grenzen, Auflösungsoffset)

            if i < len(Grenzen):
                nächster_offset = Grenzen[i]
                Töne_des_Auflösungsklangs = [
                    n for n in Noten_am_Offset(score_slices, nächster_offset)
                    if not n.duration.isGrace
                ]
                #print('nächster_offset',Töne_des_Auflösungsklangs)
            else:
                print('nächster_offset is None')
                return None

        elif len(Töne_des_Auflösungsklangs) == 1:
            #Töne_des_Auflösungsklangs.append(PartnerTon)
            return '?'

        
        zum_Akkord_der_Auflösung=chord.Chord(Töne_des_Auflösungsklangs)
        #print(Auflösungsoffset,zum_Akkord_der_Auflösung)
        #print(Auflösungsoffset,zum_Akkord_der_Auflösung)
        Akkordinformation_2 = Beurteilung_dissonanten_Klangs2(zum_Akkord_der_Auflösung,1,Auflösungsoffset,Grenzen,score_slices,Kennzeichen) 
        Generalbassbezifferung = Bezifferung_Generalbass(Akkordinformation_2)
        return Generalbassbezifferung



def Bestimmung_der_Zielnote(
    n1: note.Note,
    n2: note.Note,
    slice_noten,
    score_slices,
    Modus=None
):

    o1=n1.abs_offset
    o2=n2.abs_offset
    d1=n1.quarterLength
    d2=n2.quarterLength
    
    #die spätere Note ist Dissonaz
    if o1 != o2:
        return n1 if o1 > o2 else n2

    else:
        # Im Figurationsmodus wird die Dissonanz ausschließlich anhand der
        # melodischen Bewegung bestimmt; die Akkordstruktur bleibt unberücksichtigt.
        if Modus == 'Figuration':
            n1_ist_Transition = ist_Transition(n1, score_slices, modus="Original_Slices")
            n2_ist_Transition = ist_Transition(n2, score_slices, modus="Original_Slices")

            # Ist nur einer der beiden Töne ein Verbindungston, hat er Vorrang.
            if n1_ist_Transition != n2_ist_Transition:
                print(n1.Takt_Nr, n1.offset_Takt, n1.nameWithOctave, "Transition:", n1_ist_Transition,n2_ist_Transition)
                return n1 if n1_ist_Transition else n2

            # Sind beide oder keiner Verbindungstöne, gilt der kürzere Ton
            # als Dissonanz.
            if d1 != d2:
                return n1 if d1 < d2 else n2

            # Vollständiger Gleichstand: stabile, deterministische Rückgabe.
            return n1

        # beurteilen, ob es die akkordeigene Dissonanz betrifft.
        ch = chord.Chord([x.nameWithOctave for x in slice_noten if isinstance(x, note.Note)])
        if ch.isTriad() and ch.inversion()==2:
            Quinte_0 = note.Note(ch.fifth) if ch.fifth else None
            if n1.pitch == ch.root() and n2.nameWithOctave == Quinte_0.nameWithOctave:
                Grundton, Quinte = n1, n2
                #print(Grundton, Quinte)
            elif n2.pitch == ch.root() and n1.nameWithOctave == Quinte_0.nameWithOctave:
                Grundton, Quinte = n2, n1
            else:
                print("DEBUG types:",
                    type(n1.pitch), type(ch.root()),
                    type(n2.pitch), type(ch.fifth))
                print("DEBUG eq:",
                    n1.pitch == ch.root(),
                    n2.pitch == ch.fifth)
                print('Fehler bei 46-Akkord:',
                    n1.Takt_Nr, n1.offset_Takt,
                    'Grundton und Quinte', ch.root(), ch.fifth,
                    'Pitch töne:', n1.pitch, n2.pitch)
            if Grundton.quarterLength >= Quinte.quarterLength:
                return Quinte
            else: 
                Offset=float(Grundton.abs_offset + Grundton.quarterLength)
                Töne_danach=Noten_am_Offset(score_slices,Offset)
                #print(Töne_danach)
                Abstieg_Sekunde = False
                Aufstieg_Sekunde = False
                Prime = False

                for n in Töne_danach:
                    iv = interval.Interval(Grundton, n)
                    Sekunde = (iv.generic is not None and iv.generic.undirected == 2)
                    if Sekunde:
                        if Grundton.pitch.midi > n.pitch.midi:
                            Abstieg_Sekunde = True
                        elif Grundton.pitch.midi < n.pitch.midi:
                            Aufstieg_Sekunde = True

                    if Grundton.pitch == n.pitch:
                        Prime = True
                if Abstieg_Sekunde and (not Aufstieg_Sekunde) and (not Prime):
                    #print('Grundton-Treffer')
                    return Grundton
                else:
                    return Quinte
        ch_1 = chord.Chord([x for x in slice_noten if isinstance(x, note.Note)])           
        res = Beurteilung_dissonanten_Klangs2(ch_1)
        if res and res.get('dissonanter_Akkord') and res.get('Septakkord', False):
            dn_names = {dn.name for dn in res.get('dissonant_notes', [])}
            if n1.name in dn_names:
                #print(n1.name)
                return n1
            elif n2.name  in dn_names:
                #print(n2.name)
                return n2
            else:
                print(res.get('akkordtöne'))
                print(res.get('qualität'))
                print('unbekannte_Dissonanz:',n1.nameWithOctave,n1.Takt_Nr,n1.offset_Takt,n2.nameWithOctave,n2.Takt_Nr,n2.offset_Takt)
                return n1
        else:
        #die kürzere Note ist Dissonaz
            if d1 != d2:
                return n2 if d1 > d2 else n1
            else:
                return n1


def Wie_ein_Klang_aufgelöst(Klang,Noten_im_Bereich,Note1=None,Note2=None,Note3=None,Offset=None):
    """
    在一个时间段(segment)中，基于 annotationston 判断是：
    - 独立七和弦结构: 'independent_seventh'
    - 7-6进行: 'seven_six'
    - 无法判断 / 不符合: 'none'
    """
    if Klang=="37":
        seventh_candidates = []
        sixth_candidates = []
        Septime=Note3
        for n in Noten_im_Bereich:
            if n.nameWithOctave==Septime.nameWithOctave:
                seventh_candidates.append(n)
        seventh_note = sorted(seventh_candidates, key=lambda n: (n.offset, n.pitch.midi))[0]
        seventh_end = seventh_note.offset + seventh_note.quarterLength
        sixth_candidates = []

        for n in Noten_im_Bereich:
            if n.offset < seventh_end:
                continue
            else:
                iv_from_seventh = interval.Interval(seventh_note, n)
                if iv_from_seventh.generic.directed == -2:
                    sixth_candidates.append(n) 
        offset_letzter_7 = max(n.offset for n in seventh_candidates)
        if sixth_candidates and max(n.offset for n in sixth_candidates) > offset_letzter_7:
            return "36"
        return "37"

    elif Klang=="34":
        Quarte=Note3
        Quarte_candidates = []
        Quartauflösung_abwärts = []
        Quartauflösung_aufwärts = []

        for n in Noten_im_Bereich:
            if n.nameWithOctave==Quarte.nameWithOctave:
                Quarte_candidates.append(n)
        if len(Quarte_candidates) < 1:
            print("Kein Quarteeeee!",Offset,Quarte.nameWithOctave,[n.nameWithOctave for n in Noten_im_Bereich])
        Quarte_note = sorted(Quarte_candidates, key=lambda n: (n.offset, n.pitch.midi))[0]
        Quarte_end = Quarte_note.offset + Quarte_note.quarterLength

        for n in Noten_im_Bereich:
            Intevall_mit_Quarte = interval.Interval(Quarte_note, n)
            if n.offset >= Quarte_end and Intevall_mit_Quarte.generic.directed == -2:
                Quartauflösung_abwärts.append(n)
            elif n.offset >= Quarte_end and Intevall_mit_Quarte.generic.directed == 2:
                Quartauflösung_aufwärts.append(n)
        offset_letzter_4 =  max((n.offset for n in Quarte_candidates), default=None)
        offset_letzter_3 = max((n.offset for n in Quartauflösung_abwärts), default=None)
        offset_letzter_5 = max((n.offset for n in Quartauflösung_aufwärts), default=None)
        if Quartauflösung_abwärts and offset_letzter_3 > offset_letzter_4:
            return "35"
        elif Quartauflösung_aufwärts and offset_letzter_5 > offset_letzter_4:
            return "35"
        else:
            return "34"
        
    elif Klang=="26":
        Sekunde=Note2
        #print([n.nameWithOctave for n in Noten_im_Bereich],Sekunde.nameWithOctave)
        Sekunde_candidates = []
        Sekundeauflösung_abwärts = []
        Sekundeauflösung_aufwärts = []
        for n in Noten_im_Bereich:
            if n.nameWithOctave==Sekunde.nameWithOctave:
                Sekunde_candidates.append(n)
        #print(Sekunde_candidates)
        Sekunde_note = sorted(Sekunde_candidates, key=lambda n: (n.offset, n.pitch.midi))[0]
        Sekunde_end = Sekunde_note.offset + Sekunde_note.quarterLength

        for n in Noten_im_Bereich:
            Intevall_mit_Sekunde = interval.Interval(Sekunde_note, n)
            if n.offset >= Sekunde_end and Intevall_mit_Sekunde.generic.directed == -2:
                Sekundeauflösung_abwärts.append(n)
            elif n.offset >= Sekunde_end and Intevall_mit_Sekunde.generic.directed == 2:
                Sekundeauflösung_aufwärts.append(n)
        offset_letzter_2 =  max((n.offset for n in Sekunde_candidates), default=None)
        offset_letzter_8 = max((n.offset for n in Sekundeauflösung_abwärts), default=None)
        offset_letzter_3 = max((n.offset for n in Sekundeauflösung_aufwärts), default=None)
        if Sekundeauflösung_abwärts and offset_letzter_8 > offset_letzter_2:
            return "36"
        elif Sekundeauflösung_aufwärts and offset_letzter_3 > offset_letzter_2:
            return "36"
        else:
            return "26"

    elif Klang=="47":
        # Möglichkeit: 46, 37 or 47
        Septime_candidates = []
        Quarte_candidates = []
        Quarte=Note2
        Septime=Note3
        for n in Noten_im_Bereich:
            if n.nameWithOctave==Septime.nameWithOctave:
                Septime_candidates.append(n)
            elif n.nameWithOctave==Quarte.nameWithOctave:
                Quarte_candidates.append(n)
        Septime_note = sorted(Septime_candidates, key=lambda n: (n.offset, n.pitch.midi))[0] if Septime_candidates else None
        Septime_end = Septime_note.offset + Septime_note.quarterLength if Septime_note else None
        Quarte_note = sorted(Quarte_candidates, key=lambda n: (n.offset, n.pitch.midi))[0] if Quarte_candidates else None
        Quarte_end = Quarte_note.offset + Quarte_note.quarterLength if Quarte_note else None

        
        Sexte_candidates = []
        Terz_candidates = []

        for n in Noten_im_Bereich:
            Intevall_mit_Septime = interval.Interval(Septime_note, n)
            Intevall_mit_Quarte = interval.Interval(Quarte_note, n)

            if n.offset >= Septime_end and Intevall_mit_Septime.generic.directed == -2:
                Sexte_candidates.append(n)
            elif n.offset >= Quarte_end and Intevall_mit_Quarte.generic.directed == -2:
                Terz_candidates.append(n)  
        
        offset_letzter_7 = max((n.offset for n in Septime_candidates), default=None)
        offset_letzter_6 = max((n.offset for n in Sexte_candidates), default=None)
        offset_letzter_4 = max((n.offset for n in Quarte_candidates), default=None)
        offset_letzter_3 = max((n.offset for n in Terz_candidates), default=None)
    
        if bool(Sexte_candidates) ^ bool(Terz_candidates):
            if Sexte_candidates and offset_letzter_6 > offset_letzter_7:
                return "46"
            elif Terz_candidates and offset_letzter_4 > offset_letzter_3:
                return "37"
            else:
                return "47"
        elif Sexte_candidates and Terz_candidates:

            # wenn die Septime aufgelöst aber die Quarte nicht
            if offset_letzter_6 > offset_letzter_7 and offset_letzter_4 > offset_letzter_3:
                return "37"
            # wenn die Quarte aufgelöst aber die Septime nicht 
            elif offset_letzter_7 > offset_letzter_6 and offset_letzter_3 > offset_letzter_4:
                return "46"
            # wenn Beide aufgelöst
            elif offset_letzter_6 > offset_letzter_7 and offset_letzter_3 > offset_letzter_4:
                return "36"
            # wenn Beide nicht aufgelöst
            else:
                return "47"
        elif not Sexte_candidates and not Terz_candidates:
            return "47"
        
    elif Klang=="45":
        # Möglichkeit: 46, 37 or 47
        Quarte_candidates = []
        Quinte_candidates = []
        Quarte=Note2
        Quinte=Note3
        for n in Noten_im_Bereich:
            if n.nameWithOctave==Quarte.nameWithOctave:
                Quarte_candidates.append(n)
            elif n.nameWithOctave==Quinte.nameWithOctave:
                Quinte_candidates.append(n)
        Quarte_note = sorted(Quarte_candidates, key=lambda n: (n.offset, n.pitch.midi))[0]
        Quarte_end = Quarte_note.offset + Quarte_note.quarterLength
        Quinte_note = sorted(Quinte_candidates, key=lambda n: (n.offset, n.pitch.midi))[0]
        Quinte_end = Quinte_note.offset + Quinte_note.quarterLength

        Sexte_candidates = []
        Terz_candidates = []

        for n in Noten_im_Bereich:
            Intevall_mit_Quinte = interval.Interval(Quinte_note, n)
            Intevall_mit_Quarte = interval.Interval(Quarte_note, n)

            if n.offset >= Quarte_end and Intevall_mit_Quarte.generic.directed == -2:
                Terz_candidates.append(n)
            elif n.offset >= Quinte_end and Intevall_mit_Quinte.generic.directed == 2:
                Sexte_candidates.append(n)  
        
        offset_letzter_6 = max((n.offset for n in Sexte_candidates), default=None)
        offset_letzter_3 = max((n.offset for n in Terz_candidates), default=None)
        offset_letzter_4 = max((n.offset for n in Quarte_candidates), default=None)
        offset_letzter_5 = max((n.offset for n in Quinte_candidates), default=None)
        
        if bool(Sexte_candidates) ^ bool(Terz_candidates):
            if Sexte_candidates and offset_letzter_6 > offset_letzter_5:
                return "46"
            elif Terz_candidates and offset_letzter_4 > offset_letzter_3:
                return "35"
            else:
                return "45"
        elif Sexte_candidates and Terz_candidates:

            # wenn die Septime aufgelöst aber die Quarte nicht
            if offset_letzter_6 > offset_letzter_5 and offset_letzter_3 > offset_letzter_4:
                return "36"
            # wenn die Quarte aufgelöst aber die Septime nicht 
            elif offset_letzter_5 > offset_letzter_6 and offset_letzter_3 > offset_letzter_4:
                return "35"
            # wenn Beide aufgelöst
            elif offset_letzter_6 > offset_letzter_5 and offset_letzter_4 > offset_letzter_3:
                return "46"
            # wenn Beide nicht aufgelöst
            else:
                return "45"
        elif not Sexte_candidates and not Terz_candidates:
            return "45"
    
    elif Klang=="25":
        # Möglichkeit: 36, 24 , 35 oder 25 
        Sekunde_candidates = []
        Quinte_candidates = []
        Bass_candidates = []
        Bass=Note1
        Sekunde=Note2
        Quinte=Note3
        if Noten_im_Bereich==None:
            print(Sekunde.nameWithOctave)
        for n in Noten_im_Bereich:
            if n.nameWithOctave==Quinte.nameWithOctave:
                Quinte_candidates.append(n)
            elif n.nameWithOctave==Bass.nameWithOctave:
                Bass_candidates.append(n)
            elif n.nameWithOctave==Sekunde.nameWithOctave:
                Sekunde_candidates.append(n)
        Sekunde_note = sorted(Sekunde_candidates, key=lambda n: (n.offset, n.pitch.midi))[0]
        Sekunde_end = Sekunde_note.offset + Sekunde_note.quarterLength
        if not Bass_candidates:
            print("Kein Bass!",Offset,Bass.nameWithOctave,[n.nameWithOctave for n in Noten_im_Bereich])
        Bass_note = sorted(Bass_candidates, key=lambda n: (n.offset, n.pitch.midi))[0]
        Bass_end = Bass_note.offset + Bass_note.quarterLength
        Quinte_note = sorted(Quinte_candidates, key=lambda n: (n.offset, n.pitch.midi))[0]
        Quinte_end = Quinte_note.offset + Quinte_note.quarterLength
        
        Quarte_candidates = []
        Terz_candidates = []
        Terz_unter_Bass_candidates = []

        for n in Noten_im_Bereich:
            Intevall_mit_Bass= interval.Interval(Bass_note, n)
            Intevall_mit_Sekunde = interval.Interval(Sekunde_note, n)
            Intevall_mit_Quinte = interval.Interval(Quinte_note, n)

            if n.offset >= Bass_end and Intevall_mit_Bass.generic.directed == -2:
                Terz_unter_Bass_candidates.append(n)
            elif n.offset >= Quinte_end and Intevall_mit_Quinte.generic.directed == -2:
                Quarte_candidates.append(n)  
            elif n.offset >= Sekunde_end and Intevall_mit_Sekunde.generic.directed == 2:
                Terz_candidates.append(n)  
        offset_letzter_5 = max((n.offset for n in Quinte_candidates), default=None)
        offset_letzter_4 = max((n.offset for n in Quarte_candidates), default=None)
        offset_letzter_2 = max((n.offset for n in Sekunde_candidates), default=None)
        offset_letzter_3 = max((n.offset for n in Terz_candidates), default=None)
        offset_letzter_1 = max((n.offset for n in Bass_candidates), default=None)
        offset_letzter_unter3 = max((n.offset for n in Terz_unter_Bass_candidates), default=None)
    

        if bool(Terz_unter_Bass_candidates) ^ bool(Terz_candidates) ^ bool(Quarte_candidates): 
            if Terz_unter_Bass_candidates and offset_letzter_unter3 > offset_letzter_1:
                return "36" 
            elif Quarte_candidates and offset_letzter_4 > offset_letzter_5:
                return "24"
            elif Terz_candidates and offset_letzter_3 > offset_letzter_2:
                return "35"
            else:
                return "25"
        else:
            Bassauflösung = False
            Sekundauflösung_aufwärts = False
            Quintauflösung = False
            if Terz_unter_Bass_candidates and offset_letzter_unter3 > offset_letzter_1:
                Bassauflösung = True
            if Quarte_candidates and offset_letzter_4 > offset_letzter_5:
                Quintauflösung = True
            if Terz_candidates and offset_letzter_3 > offset_letzter_2:
                Sekundauflösung_aufwärts = True
            if Bassauflösung and Sekundauflösung_aufwärts== False and Quintauflösung== False:
                return "36"
            elif Bassauflösung and Sekundauflösung_aufwärts and Quintauflösung == False:
                return "46"
            elif Bassauflösung and Sekundauflösung_aufwärts== False and Quintauflösung:
                return "35"
            elif Bassauflösung == False and Sekundauflösung_aufwärts and Quintauflösung:
                return "34"
            elif Bassauflösung == False and Sekundauflösung_aufwärts and Quintauflösung== False:
                return "35"
            elif Bassauflösung == False and Sekundauflösung_aufwärts and Quintauflösung== False:
                return "35"
            elif Bassauflösung == False and Sekundauflösung_aufwärts== False and Quintauflösung== False:
                return "25"
            else:
                print('unidentifiziebare 25-Klang')
    
    elif Klang=="39":
        Noone_candidates = []
        Noone=Note3
        for n in Noten_im_Bereich:
            if n.nameWithOctave==Noone.nameWithOctave:
                Noone_candidates.append(n) 
        Noone_note = sorted(Noone_candidates, key=lambda n: (n.offset, n.pitch.midi))[0]
        Noone_end = Noone_note.offset + Noone_note.quarterLength
        Oktave_candidates = []
        Dezime_candidates = []
        for n in Noten_im_Bereich:
            Intevall_mit_Noone= interval.Interval(Noone_note, n)
            if n.offset >= Noone_end and Intevall_mit_Noone.generic.directed == -2:
                Oktave_candidates.append(n)
            elif n.offset >= Noone_end and Intevall_mit_Noone.generic.directed == 2:
                Dezime_candidates.append(n)  
        offset_letzter_9 = max(n.offset for n in Quinte_candidates)
        offset_letzter_8 = max(n.offset for n in Oktave_candidates)
        offset_letzter_10 = max(n.offset for n in Dezime_candidates)

        if Oktave_candidates and offset_letzter_8 > offset_letzter_9:
            return "38"
        elif Dezime_candidates and offset_letzter_10 > offset_letzter_9:
            return "38" 
        else: 
            return "39" 
        
    elif Klang=="67":
        Sexte_candidates = []
        Sexte=Note2
        for n in Noten_im_Bereich:
            if n.nameWithOctave==Sexte.nameWithOctave:
                Sexte_candidates.append(n) 
        Sexte_note = sorted(Sexte_candidates, key=lambda n: (n.offset, n.pitch.midi))[0]
        Sexte_end = Sexte_note.offset + Sexte_note.quarterLength
        Quinte_candidates = []
        for n in Noten_im_Bereich:
            Intevall_mit_Sexte= interval.Interval(Sexte_note, n)
            if n.offset >= Sexte_end and Intevall_mit_Sexte.generic.directed == -2:
                Quinte_candidates.append(n)

        offset_letzter_5 = max(n.offset for n in Quinte_candidates)
        offset_letzter_6 = max(n.offset for n in Sexte_candidates)

        if Quinte_candidates and offset_letzter_5 > offset_letzter_6:
            return "57"
        else: 
            return "67" 
    
    elif Klang=="57":
        Bass_candidates = []
        Bass=Note1
        for n in Noten_im_Bereich:
            if n.nameWithOctave==Bass.nameWithOctave:
                Bass_candidates.append(n) 
        Bass_note = sorted(Bass_candidates, key=lambda n: (n.offset, n.pitch.midi))[0]
        Bass_end = Bass_note.offset + Bass_note.quarterLength
        Oktave_candidates = []
        for n in Noten_im_Bereich:
            Intevall_mit_Bass= interval.Interval(Bass_note, n)
            if n.offset >= Bass_end and Intevall_mit_Bass.generic.directed == -2:
                Oktave_candidates.append(n)

        offset_letzter_Bass = max(n.offset for n in Bass_candidates)
        offset_letzter_2_unter_Bass = max(n.offset for n in Oktave_candidates)

        if Oktave_candidates and offset_letzter_2_unter_Bass > offset_letzter_Bass:
            return "68"
        else: 
            return "57" 
        
    elif Klang=="allgemeiner Klang":
        Grunton_candidates = []
        Grundton=Note3
        Auflösungston_candidates = []
        Auflösungston2_candidates = []
        for n in Noten_im_Bereich:
            if n.nameWithOctave==Grundton.nameWithOctave:
                Grunton_candidates.append(n) 
        Grundnote = sorted(Grunton_candidates, key=lambda n: (n.offset, n.pitch.midi))[0]
        Grundton_end =Grundnote.offset + Grundnote.quarterLength
        offset_letzter_Grundton = max(n.offset for n in Grunton_candidates)

        for n in Noten_im_Bereich:
            Intevall_mit_Grundton= interval.Interval(Grundton, n)
            if n.offset >= Grundton_end and Intevall_mit_Grundton.generic.directed == -2:
                Auflösungston_candidates.append(n)  
            elif n.offset >= Grundton_end and Intevall_mit_Grundton.generic.directed == 2:  
                Auflösungston2_candidates.append(n)
        if bool(Auflösungston_candidates) ^ bool(Auflösungston2_candidates):
            if Auflösungston_candidates:
                offset_letzter_Auflösungston = max(n.offset for n in Auflösungston_candidates)
                if offset_letzter_Auflösungston > offset_letzter_Grundton:
                    return "zufällige Dissonanz" 
                else:
                    return "Grundton" 
            elif Auflösungston2_candidates:
                offset_letzter_Auflösungston2 = max(n.offset for n in Auflösungston2_candidates)
                if offset_letzter_Auflösungston2 > offset_letzter_Grundton:
                    return "zufällige Dissonanz" 
                else:
                    return "Grundton" 
        elif Auflösungston_candidates and Auflösungston2_candidates:
            offset_letzter_Auflösungston = max(n.offset for n in Auflösungston_candidates)
            offset_letzter_Auflösungston2 = max(n.offset for n in Auflösungston2_candidates)
            if offset_letzter_Auflösungston > offset_letzter_Grundton or offset_letzter_Auflösungston2 > offset_letzter_Grundton:
                return "zufällige Dissonanz"
        else: 
            return "Grundton" 

def Bildung_Klanggerüst(Töne, Generalbass, Annotationsnote):
    # z.B. 3 -> [3]；56 -> [5, 6]；"5,6" -> [5, 6]
    if isinstance(Generalbass, int):
        Generalbass_Zahlen = [int(z) for z in str(Generalbass)]
    elif isinstance(Generalbass, str):
        Generalbass_Zahlen = [int(z) for z in Generalbass if z.isdigit()]
    else:
        Generalbass_Zahlen = list(Generalbass)

    gefundene_Töne = [Annotationsnote]

    for gb in Generalbass_Zahlen: #Nach der Beziefferungsannotation die Gerüsttöne finden
        ziel = gb
        while ziel <= gb + 14:
            gefunden = False
            for n in sorted(Töne, key=lambda x: x.offset):
                intervall = interval.Interval(Annotationsnote, n)
                if intervall.generic.directed == ziel:
                    gefunden = True
                    gefundene_Töne.append(n)
                    break
            if gefunden:
                break
            ziel += 7
    Klanggerüst = chord.Chord(gefundene_Töne)
    höchster_Ton = max(gefundene_Töne, key=lambda ton: ton.pitch.midi)
    if Generalbass in [5, 6]:       #für manche abgekürtzte Bezifferungen 6, 5, 7  andere mögliche Gerüsttöne ergänzen
        for Terz in sorted(Töne, key=lambda x: x.offset):
            intervall2= interval.Interval(Annotationsnote, Terz)
            if intervall2.generic.simpleDirected == 3 and höchster_Ton.pitch.midi > Terz.pitch.midi > Annotationsnote.pitch.midi:
                Klanggerüst = chord.Chord([Annotationsnote,Terz,n])
                return Klanggerüst
        return Klanggerüst
    elif Generalbass == 7:
        andere=[Annotationsnote,n]
        for Terz_oder_Quinte in sorted(Töne, key=lambda x: x.offset):
            intervall2 = interval.Interval(Annotationsnote, Terz_oder_Quinte)
            if intervall2.generic.simpleDirected in [3,5] and höchster_Ton.pitch.midi > Terz_oder_Quinte.pitch.midi> Annotationsnote.pitch.midi:
                andere.append(Terz_oder_Quinte)
        Klanggerüst = chord.Chord(andere)
        return Klanggerüst
    elif Generalbass in [34, 24]:
        for Sexte in sorted(Töne, key=lambda x: x.offset):
            intervall2 = interval.Interval(Annotationsnote, Sexte)
            if intervall2.generic.simpleDirected == 6 and Sexte.pitch.midi> Annotationsnote.pitch.midi:
                Klanggerüst = chord.Chord(list(Klanggerüst.notes) + [Sexte])
                return Klanggerüst
        return Klanggerüst 
    elif Generalbass == 56:
        for Terz in sorted(Töne, key=lambda x: x.offset):
            intervall2 = interval.Interval(Annotationsnote, Terz)
            if intervall2.generic.simpleDirected == 3 and Terz.pitch.midi> Annotationsnote.pitch.midi:
                Klanggerüst = chord.Chord(list(Klanggerüst.notes) + [Terz])
                return Klanggerüst
        return Klanggerüst   
    else:
        return Klanggerüst
