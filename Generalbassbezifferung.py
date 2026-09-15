from music21 import note, chord, interval
from Beurteilung import classify_dissonant_harmony

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



def Bezifferung_Generalbass(Akkord,Dissonanz):
    
    Generalbass= {
        # vierstimmig:
            #Septakkord:
        ('major seventh chord', 0): "MM7", ('major seventh chord', 1): "MM56", 
        ('major seventh chord', 2): "MM34",  ('major seventh chord', 3): "MM24",
        
        ('dominant seventh chord', 0): "D7", ('dominant seventh chord', 1): "D56", 
        ('dominant seventh chord', 2): "D34", ('dominant seventh chord', 3): "D24",
        
        ('minor seventh chord', 0): "mm7", ('minor seventh chord', 1): "mm56", 
        ('minor seventh chord', 2): "mm34", ('minor seventh chord', 3): "mm24",
        
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
        (3,5,9): "39", (3,7,9): "79",  (5,7,9): "79", (3,6,7): "67", 
        # dreistimmig:
            #Akkord:
        ('major triad', 2): "M46", ('minor triad', 2): "m46",  
        ('diminished triad', 0): "d35",('diminished triad', 1): "d6",('diminished triad', 2): "d46",
        ('augmented triad', 0): "A35",  ('augmented triad', 1): "A6",  ('augmented triad', 2): "A46",
        ('Italian augmented sixth chord', 1):"A6+",
        
        ('incomplete major-seventh chord',0) :"MM7", ('incomplete major-seventh chord', 1) :"MM56",
        ('incomplete major-seventh chord', 2) :"MM34",('incomplete major-seventh chord', 3) :"MM24",
        
        ('incomplete dominant-seventh chord',  0):"D7", ('incomplete dominant-seventh chord', 1):"D56",
        ('incomplete dominant-seventh chord', 2):"D34",('incomplete dominant-seventh chord', 3):"D24",
        
        ('incomplete minor-seventh chord', 0): "mm7", ('incomplete minor-seventh chord',1): "mm56", 
        ('incomplete minor-seventh chord', 3): "mm24",
        
        #
        ('incomplete half-diminished seventh chord', 0):"h7",
        ('incomplete half-diminished seventh chord', 2):"h34",('incomplete half-diminished seventh chord', 3):"h24",
        
        ('enharmonic equivalent to diminished triad', 0):"d7",('enharmonic equivalent to diminished triad', 1):"d56",
        ('enharmonic equivalent to diminished triad', 2):"d34",('enharmonic equivalent to diminished triad',3):"d24",

        #
        ('incomplete major-seventh chord', 'Ohne Quinte',0) :"MM37", ('incomplete major-seventh chord', 'Ohne Quinte', 1) :"m56",
        ('incomplete major-seventh chord','Ohne Quinte', 3) :"m24",
        
        ('incomplete dominant-seventh chord', 'Ohne Quinte', 0):"Mm37", ('incomplete dominant-seventh chord','Ohne Quinte', 1):"dm56",
        ('incomplete dominant-seventh chord', 'Ohne Quinte',3):"MA24",
        
        ('incomplete minor-seventh chord','Ohne Quinte', 0): "mm37", ('incomplete minor-seventh chord', 'Ohne Quinte',1): "M56", 
        ('incomplete minor-seventh chord','Ohne Quinte', 3): "M24",
        
        ('enharmonic equivalent to diminished triad','Ohne Quinte', 0):"md37",('enharmonic equivalent to diminished triad','Ohne Quinte', 1):"dM56",
        ('enharmonic equivalent to diminished triad', 'Ohne Quinte',3):"AA24",

        ('incomplete major-seventh chord', 'Ohne Terz',0) :"M57", 
        ('incomplete major-seventh chord', 'Ohne Terz',2) :"M34",('incomplete major-seventh chord','Ohne Terz', 3) :"mm26",
        
        ('incomplete dominant-seventh chord', 'Ohne Terz', 0):"m57", 
        ('incomplete dominant-seventh chord', 'Ohne Terz',2):"m34",('incomplete dominant-seventh chord', 'Ohne Terz',3):"MM26",
        
        ('incomplete half-diminished seventh chord','Ohne Terz', 0):"dm57",
        ('incomplete half-diminished seventh chord','Ohne Terz', 2):"MA34",('incomplete half-diminished seventh chord','Ohne Terz', 3):"Mm26",
        
        ('enharmonic equivalent to diminished triad','Ohne Terz', 0):"dd57",
        ('enharmonic equivalent to diminished triad','Ohne Terz', 2):"mA34",('enharmonic equivalent to diminished triad', 'Ohne Terz',3):"AM26",
        (3,9): "9",(4,5): "45",
         # mehr als vierstimmig:   
        ('dominant-ninth', 0):"D79", ('flat-ninth pentachord', 0):"Dm79", ('minor-diminished ninth chord', 0) :"mm79", ('minor-ninth chord', 0):"m79",
        (3,5,7,9): "79"
    }
    
    if not isinstance(Akkord, chord.Chord):
        raise TypeError

    #den Akkord in die enge Lage umwandeln, wobei die wiederholten Akkordtöne weggelassen werden.
    geschlossener_Akkord = Akkord.closedPosition()
    Akkordtöne = list(geschlossener_Akkord.notes)
    Akkordtöne0 = Sammlung_Akkordtöne_ohne_Wiederholung(Akkord)
    Qualität = geschlossener_Akkord.commonName
    Umkehrung = geschlossener_Akkord.inversion()
    a = (Qualität, Umkehrung)  
    intervalqualität_list, intervalzahl_list=Intervallkombination_im_Akkord(Akkordtöne0)
    Bezifferung = Generalbass.get(a, "Unbekannt") 
    Bezifferung0=direkte_Bezifferung(Akkordtöne0)

    Grundton = note.Note(Akkord.root()) if Akkord.root() else None
    Terz = note.Note(Akkord.third) if Akkord.third else None
    Quinte = note.Note(Akkord.fifth) if Akkord.fifth else None
    Septime = note.Note(Akkord.seventh) if Akkord.seventh else None

    def finde_intervall_name(Dissonanz, Akkord):

        mapping = {
            "1": Akkord.root(),
            "3": Akkord.third,
            "5": Akkord.fifth,
            "7": Akkord.seventh
        }

        for var_name, obj in mapping.items():
            Name = obj.name if obj else None
            if Name  == Dissonanz.name:
                return var_name
        return None
    
    Identität=finde_intervall_name(Dissonanz, Akkord)
    
    if len(Akkordtöne) == 4:
        if Bezifferung != 'Unbekannt':
             if Grundton and Terz and Quinte and Septime: 
                return f"{Bezifferung}({Identität})"
             else:
                return Bezifferung 
        else:
            Bezifferung1 = Generalbass.get(intervalzahl_list, "Unbekannt") 
            if Bezifferung1 != 'Unbekannt':
                Bezifferung2=vereinfachte_Bezifferung(Bezifferung1,intervalqualität_list,intervalzahl_list)
                return Bezifferung2
            else: 
                #print(Bezifferung0,Dissonanz.Takt_Nr,Dissonanz.offset_Takt)
                return Bezifferung0
      

    if len(Akkordtöne) == 3:
        if Akkord.isTriad():
            if Bezifferung != 'Unbekannt':
                return f"{Bezifferung}({Identität})"
            else:
                 Bezifferung0
        elif Akkord.seventh and Akkord.third:
             if Akkord.lyric and Akkord.lyric in ("D", "DW","DB","DWZ"):
                return f"{Bezifferung}({Identität})"
             else:
                a1 = (Qualität,'Ohne Quinte' ,Umkehrung)  
                Bezifferung = Generalbass.get(a1, "Unbekannt") 
                return f"{Bezifferung}({Identität})"
        elif Akkord.seventh and Akkord.fifth:
            if Akkord.lyric and Akkord.lyric in ("D", "DW","DB","DWZ"):
                return f"{Bezifferung}({Identität})"
            else:
                a1 = (Qualität,'Ohne Terz' ,Umkehrung)  
                Bezifferung = Generalbass.get(a1, "Unbekannt") 
                return f"{Bezifferung}({Identität})"
        else:
            Bezifferung = Generalbass.get(intervalzahl_list, "Unbekannt") 
            if Bezifferung != 'Unbekannt':
                Bezifferung1=vereinfachte_Bezifferung(Bezifferung,intervalqualität_list,intervalzahl_list)
                return Bezifferung1
            else: 
                return Bezifferung0
              
    if len(Akkordtöne) == 2:
        iv = interval.Interval(Akkordtöne0[0], Akkordtöne0[1])
        Einfache_Name= reduced_interval_name(iv)
        return Einfache_Name
    
    if len(Akkordtöne) > 4:
        if Bezifferung != 'Unbekannt':
            return Bezifferung 
        else:
            Bezifferung = Generalbass.get(intervalzahl_list, "Unbekannt") 
            if Bezifferung != 'Unbekannt':
                Bezifferung1=vereinfachte_Bezifferung(Bezifferung,intervalqualität_list,intervalzahl_list)
                return Bezifferung1
            else: 
                return Bezifferung0