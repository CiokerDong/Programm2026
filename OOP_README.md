# Objektorientierter Neuaufbau (erster lauffähiger Stand)

Die alten Dateien und das Hauptnotebook bleiben unangetastet. Der neue Einstieg
steht in `oop_programm.py`; `oop_analyse.py` liest eine Partitur und kann eine
CSV-Datei mit Einzeltonbefunden ausgeben. Voraussetzung: Python und `music21`.

```bash
python -m pip install music21
python oop_analyse.py partitur.musicxml --output befund.csv
```

Die letzte Stimme wird als Hilfsstimme gelesen. Ohne Hilfsstimme:

```bash
python oop_analyse.py partitur.musicxml --no-helper --output befund.csv
```

## Objekte

- `PartiturIndex` enthält die musikalischen Noten und ihre absoluten Offsets.
  Die Hilfsstimme wird aus dem klingenden Satz ausgeschlossen.
- Jeder `HarmonischerKontext` ist **ein Segment**. Die Klasse erzeugt Segmente
  aus Hilfsstimmen-Annotationen und füllt Standardbereiche automatisch. Eine
  Annotation hat Vorrang; ein automatisches Segment endet spätestens an der
  nächsten markierten Grenze. Ein fehlender bezifferter Ton wird gemeldet und
  nicht als vorhandener Ton erfunden.
- `Klang` analysiert die Vertikale an **einem Offset**. Innerhalb eines
  Segments können daher mehrere verschiedene Klänge entstehen.
- `Dissonanz` untersucht einen konkreten Ton an einem konkreten Offset;
  `AnalyseProgramm` verbindet die vier anderen Klassen.

## Umfang der ersten Version

Der Neuaufbau erkennt dissonante Intervalle (reine Quarte nur über dem Bass)
und Grundstrukturen wie vollständige Septakkorde, verminderte/übermäßige
Dreiklänge sowie Quartsextakkorde. Löst sich eine Septime innerhalb des
Segments abwärts zur Sexte, bleibt die Alternative 7–6 / selbständiger
Septakkord ausdrücklich offen. Durchgänge und Nebennoten werden nur bei
eindeutigen Nachbarn derselben melodischen Linie vorgeschlagen; eine
Appoggiatur ist zunächst ausdrücklich ein Kandidat. Bei mehrdeutiger
Klavierstimmführung bleibt der Einzeltonbefund offen. Fehlende Töne im
bezifferten Gerüst werden nicht als Akkordtöne ergänzt.

Noch **nicht übertragen** sind die zahlreichen Spezialregeln des bisherigen
`Klang.py`, die komplette Einführungs-/Verlassensklassifikation, Betonungs-
analyse, die abschließende 7–6-Entscheidung, Vorhalte-/Antizipationsregeln
und der vollständige Export des Hauptnotebooks. CSV-Offsets sind absolute
Viertelwerte; Takt und Taktzeit müssen noch ergänzt werden. Ergebnisse aus
diesem Modul sind deshalb noch kein Ersatz für die alte Gesamtauswertung.

Tests: `python -m unittest -v test_oop_programm`.
