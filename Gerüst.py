from music21 import note, chord, interval
from Notenbearbeitung import Noten_am_Offset
from Klang import Beurteilung_dissonanten_Klangs

def Dissonanter_Gerüstton_und_Tönenamen(Töne_am_Modusanfang,Töne_im_Bereich):
    Klang=chord.Chord(Töne_am_Modusanfang)
    if Klang.isConsonant():
        return None
    else: 
        DissonanzKlang = Beurteilung_dissonanten_Klangs(Klang,None,None,None,Töne_im_Bereich)
        Dissonanter_Gerüstton = DissonanzKlang.get('dissonant_notes')
        Akkordtönenamen = DissonanzKlang.get('akkordtöne')
        if Dissonanter_Gerüstton:
            return Dissonanter_Gerüstton, Akkordtönenamen
        else:
            return None
        
