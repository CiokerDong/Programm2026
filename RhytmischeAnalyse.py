
from music21 import stream, meter, converter

def Taktart_Analyse(score):
    """
    Bestimmung der Taktart eines Musikstücks: 
    Dreier-Takt, Zweier-Takt oder gemischten Takt
    """
    if not isinstance(score, (stream.Score, stream.Part)):
        raise ValueError("Input must be a music21 stream.Score or stream.Part")

    time_signatures = score.flatten().getElementsByClass(meter.TimeSignature)

    for ts in time_signatures:
        numerator = ts.numerator
        if numerator % 3 == 0:
            return "Dreier-Takt"   #"Wenn der Zähler durch 3 ist, wird 'Dreier-Takt' rückgegeben."
        elif numerator % 2 == 0:
            return "Zweier-Takt"    #"Wenn der Zähler durch 2 ist, wird 'Dreier-Takt' rückgegeben."

    return "gemischter Takt"  #"Wenn der Zähler weder durch 3 noch durch 2 teilbar ist, wird 'gemischter Takt' ausgegeben."


from music21 import duration

def GrundrhythmusallerStimmen_dict(score):
    """
    Im chordify-Zustand den gemeinsamen Grundrhythmus aller Stimmen für jeden Takt bestimmen. 
    """
    chordified_score = score.chordify()
    rhythmic_patterns = {}

    valid_types = duration.typeToDuration.keys()

    for measure in chordified_score.getElementsByClass(stream.Measure):
        measure_number = measure.measureNumber
        note_durations = {}

        # ------------------------------
        # 1) 收集当前小节所有合法的 duration.type
        # ------------------------------
        for element in measure.notesAndRests:
            dur_type = element.duration.type
            
            # ❗跳过 "complex" 或任何非法时值
            if dur_type not in valid_types:
                continue

            note_durations[dur_type] = note_durations.get(dur_type, 0) + 1

        # ------------------------------
        # 2) 找出最常见的时值
        # ------------------------------
        if note_durations:
            most_common_durations = [
                k for k, v in note_durations.items()
                if v == max(note_durations.values())
            ]

            most_common_duration = max(
                most_common_durations,
                key=lambda d: duration.Duration(type=d).quarterLength
            )
        else:
            most_common_duration = "unknown"

        rhythmic_patterns[measure_number] = most_common_duration

    return rhythmic_patterns


import numpy as np

def Bestimme_betontePosition(score):
    """
    Diese Funktion kann basierend auf den verschiedenen Taktarten und Grundrhytmus-Musteren die betonten Positionen jedes Takts bestimmen.
    Rückgabewert: dict: Die betonten Positionen jedes Takts im Format {Taktnummer: [Offsets]}."
    """

    part1 = score.parts[1]  
    taktart = Taktart_Analyse(score)
    grundrhythmus = GrundrhythmusallerStimmen_dict(score)

    betontePositionen = {}
    zweite_betonte_Position= {}
    # Überprüfung des Durchlaufs des jeden Takts in Parts[1]
    for measure in part1.getElementsByClass(stream.Measure):
        measure_number = measure.measureNumber
        rhythm_type = grundrhythmus.get(measure_number, None)
        #print(f"Takt {measure_number}, Grundrhythmus: {rhythm_type}")
        #print("Takt", measure.measureNumber)
        #print("Objekte im Takt:", list(measure))
        #print("Noten im Takt:", list(measure.notes))
        #print("NotesAndRests:", [(n, n.offset, getattr(n, 'duration', None)) for n in measure.notesAndRests])
        #print("duration.quarterLength:", measure.duration.quarterLength)
        if rhythm_type is None:
            print(f"Takt {measure_number}: nichts")
            continue
        if measure.duration is None:
            print(f"Takt {measure_number}: keine Dauerangabe")
            continue

        # Logik für Zweiertakt
        if taktart == "Zweier-Takt":
            #print(taktart)
            if rhythm_type in ["32th", "16th"]:
                strong_beats = [offset for offset in np.arange(0, measure.duration.quarterLength, 1)]
                halfstrong_beats = [offset for offset in np.arange(0.5, measure.duration.quarterLength, 1)]
            
            elif rhythm_type == "eighth":
                strong_beats = [offset for offset in range(0, int(measure.barDuration.quarterLength), 2)]
                halfstrong_beats = [offset for offset in range(1, int(measure.barDuration.quarterLength), 2)]
            # jede 4tel-Note als betonte Position
           
            elif rhythm_type == "quarter":
                strong_beats = [offset for offset in range(0, int(measure.duration.quarterLength), 4)]
                halfstrong_beats = [offset for offset in range(2, int(measure.duration.quarterLength), 4)]
            # jede Halbnote als betonte Position
            
            elif rhythm_type == "half":
                strong_beats = [offset for offset in range(0, int(measure.duration.quarterLength), 4)]
                halfstrong_beats = [offset for offset in range(2, int(measure.duration.quarterLength), 4)]
            # jede Ganznote als betonte Position
            elif rhythm_type == "whole":
                strong_beats = [offset for offset in range(0, int(measure.duration.quarterLength), 4)]
                halfstrong_beats = []
            # Breve als betonte Position
            else:
                strong_beats = [offset for offset in range(0, int(measure.duration.quarterLength), 8)]
                halfstrong_beats = []
            #print(strong_beats)
        # Logik für Dreiertakt
        elif taktart == "Dreier-Takt":
            time_signatures = score.flatten().getElementsByClass(meter.TimeSignature)
            for ts in time_signatures:
                denominator = ts.denominator

                # beim 8tel-Takt (3/8, 6/8, 9/8 usw.)
                if denominator == 8:
                    # jede punktierte 4tel-Note als betonte Position
                    if rhythm_type == "16th":
                        strong_beats = list(np.arange(0, measure.duration.quarterLength, 1.5))
                        halfstrong_beats = [
                            s + sub
                            for s in strong_beats
                            for sub in (0.5, 1.0)
                            if s + sub < measure.duration.quarterLength
                        ]
                    elif rhythm_type in [ "eighth", "quarter"]:
                        strong_beats = [offset for offset in np.arange(0, measure.duration.quarterLength, 1.5)]
                        halfstrong_beats = []
                    else:
                        strong_beats = []
                        halfstrong_beats = []

                # beim 16tel-Takt (12/16, usw.)
                elif denominator == 16:
                    # jede punktierte 8tel-Note als betonte Position
                    strong_beats = [offset for offset in np.arange(0, measure.duration.quarterLength, 1.5)]
                    halfstrong_beats = [offset for offset in np.arange(0.75, measure.duration.quarterLength, 1.5)]
                # beim 4tel-Takt (3/4, 6/4, usw.)
                elif denominator == 4:
                    # 
                    if rhythm_type == "16th":
                        strong_beats = [offset for offset in range(0, int(measure.duration.quarterLength), 1)]
                        halfstrong_beats = [offset for offset in np.arange(0.5, measure.duration.quarterLength, 1)]
                    elif rhythm_type == "eighth":
                        strong_beats = [offset for offset in range(0, int(measure.duration.quarterLength), 3)]
                        halfstrong_beats = [
                            s + sub
                            for s in strong_beats
                            for sub in (1.0, 2.0)
                            if s + sub < measure.duration.quarterLength
                        ]
                    # jede 4tel-Note als betonte Position
                    elif rhythm_type in ["quarter", "half"]:
                        strong_beats = [offset for offset in range(0, int(measure.duration.quarterLength), 3)]
                        halfstrong_beats = []
                    # jede punktierte Halbnote als betonte Position
                    else:
                        strong_beats = [offset for offset in range(0, int(measure.duration.quarterLength), 3)]
                        halfstrong_beats = []

                # beim 2tel-Takt (3/2, usw.)
                elif denominator == 2:
                    # jede Halbnote als betonte Position
                    if rhythm_type == "eighth":
                        strong_beats = [offset for offset in range(0, int(measure.duration.quarterLength), 2)]
                        halfstrong_beats = [offset for offset in range(1, int(measure.duration.quarterLength), 2)]
                    elif rhythm_type == "quarter":
                        strong_beats = [offset for offset in range(0, int(measure.duration.quarterLength), 6)]
                        halfstrong_beats = [
                            s + sub
                            for s in strong_beats
                            for sub in (2.0, 4.0)
                            if s + sub < measure.duration.quarterLength
                        ]
                    # jede punktierte Ganznote als betonte Position
                    elif rhythm_type in ["half", "whole"]:
                        strong_beats = [offset for offset in range(0, int(measure.duration.quarterLength), 6)]
                        halfstrong_beats = []
                    else:
                        strong_beats = []
                        halfstrong_beats = []
                else:
                    strong_beats = []
                    halfstrong_beats = []

        else:
            strong_beats = []
            halfstrong_beats = []
        #print(taktart)
        #print(strong_beats)
        betontePositionen[measure_number] = [float(offset) for offset in strong_beats]
        zweite_betonte_Position[measure_number] = [float(offset) for offset in halfstrong_beats]
    return betontePositionen,zweite_betonte_Position