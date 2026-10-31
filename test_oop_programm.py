"""Kleine Satzbeispiele für Segmentgrenzen und sichere Einzeltonbefunde."""

import unittest

from music21 import chord, note, stream

from oop_programm import AnalyseProgramm, HarmonischerKontext


def beispiel_mit_hilfsstimme():
    score = stream.Score()
    musik = stream.Part(id="Musik")
    musik.insert(0, chord.Chord(["D3", "F#3", "A3"], quarterLength=1))
    musik.insert(1, chord.Chord(["C3", "E3", "G3"], quarterLength=1))
    hilfe = stream.Part(id="Hilfsstimme")
    marke = note.Note("D2", quarterLength=1)
    marke.lyric = "3"
    hilfe.insert(0, marke)
    hilfe.insert(1, note.Rest(quarterLength=1))
    score.insert(0, musik)
    score.insert(0, hilfe)
    return score


class ObjektprogrammTests(unittest.TestCase):
    def test_markierung_hat_vorrang_und_standard_endet_am_abschnitt(self):
        programm = AnalyseProgramm(beispiel_mit_hilfsstimme())
        erster = HarmonischerKontext.finde_bei(programm.kontexte, 0.5)
        zweiter = HarmonischerKontext.finde_bei(programm.kontexte, 1.5)
        self.assertEqual(erster.quelle, "Hilfsstimme")
        self.assertEqual(erster.bezifferung, 3)
        self.assertEqual((erster.anfang, erster.ende), (0.0, 1.0))
        self.assertEqual(zweiter.quelle, "Automatisch")
        self.assertEqual((zweiter.anfang, zweiter.ende), (1.0, 2.0))
        self.assertIsNone(HarmonischerKontext.finde_bei(programm.kontexte, 2.0))

    def test_automatik_ueberschreibt_spaetere_markierung_nicht(self):
        score = stream.Score()
        musik = stream.Part()
        musik.insert(0, chord.Chord(["C3", "E3", "G3"], quarterLength=2))
        hilfe = stream.Part()
        hilfe.insert(0, note.Rest(quarterLength=1))
        marke = note.Note("D2", quarterLength=1)
        marke.lyric = "0"
        hilfe.insert(1, marke)
        score.insert(0, musik)
        score.insert(0, hilfe)
        programm = AnalyseProgramm(score)
        self.assertEqual(programm.kontexte[0].ende, 1.0)
        self.assertEqual(programm.kontexte[1].quelle, "Hilfsstimme")

    def test_quarte_ueber_bass_und_offener_befund(self):
        score = stream.Score()
        unten = stream.Part()
        oben = stream.Part()
        unten.insert(0, note.Note("D3", quarterLength=1))
        oben.insert(0, note.Note("G3", quarterLength=1))
        score.insert(0, unten)
        score.insert(0, oben)
        programm = AnalyseProgramm(score, hilfsstimme_index=None)
        befund = programm.analysiere()
        self.assertTrue(any(b.ton.name == "G" and b.partner for b in befund))
        self.assertTrue(all(b.status == "offen" for b in befund))

    def test_quarte_ueber_oberstimme_ist_keine_dissonanz(self):
        score = stream.Score()
        unten = stream.Part()
        mitte = stream.Part()
        oben = stream.Part()
        unten.insert(0, note.Note("C3", quarterLength=1))
        mitte.insert(0, note.Note("E3", quarterLength=1))
        oben.insert(0, note.Note("A3", quarterLength=1))
        for part in (unten, mitte, oben):
            score.insert(0, part)
        programm = AnalyseProgramm(score, hilfsstimme_index=None)
        self.assertEqual(programm.analysiere(), [])

    def test_durchgang_aus_eindeutiger_stimmfuehrung(self):
        score = stream.Score()
        bass = stream.Part()
        melodie = stream.Part()
        bass.insert(0, note.Note("C3", quarterLength=3))
        for off, name in enumerate(("C4", "D4", "E4")):
            melodie.insert(off, note.Note(name, quarterLength=1))
        score.insert(0, bass)
        score.insert(0, melodie)
        befunde = AnalyseProgramm(score, hilfsstimme_index=None).analysiere()
        d = next(b for b in befunde if b.ton.name == "D")
        self.assertEqual(d.typ, "Durchgang")
        self.assertEqual(d.status, "wahrscheinlich_akkordfremd")

    def test_vollstaendiger_septakkord_erkennt_strukturelle_septime(self):
        score = stream.Score()
        part = stream.Part()
        part.insert(0, chord.Chord(["C3", "E3", "G3", "B3"], quarterLength=1))
        score.insert(0, part)
        befunde = AnalyseProgramm(score, hilfsstimme_index=None).analysiere()
        b = next(b for b in befunde if b.ton.name == "B")
        self.assertEqual(b.status, "akkordeigene_Dissonanz")
        self.assertEqual(b.klang.kategorie, "Septakkord")

    def test_unvollstaendige_ziffer_zeigt_hinweis_statt_ton_zu_erfinden(self):
        score = stream.Score()
        musik, hilfe = stream.Part(), stream.Part()
        musik.insert(0, note.Note("D3", quarterLength=1))
        n = note.Note("D2", quarterLength=1)
        n.lyric = "56"
        hilfe.insert(0, n)
        score.insert(0, musik)
        score.insert(0, hilfe)
        seg = AnalyseProgramm(score).kontexte[0]
        self.assertEqual(len(seg.klanggeruest.notes), 1)
        self.assertIn("nicht gefunden", seg.hinweise[0])

    def test_siebensechs_bleibt_gegen_septakkord_offen(self):
        score = stream.Score()
        for name in ("C3", "E3", "G3"):
            part = stream.Part()
            part.insert(0, note.Note(name, quarterLength=2))
            score.insert(0, part)
        oben = stream.Part()
        oben.insert(0, note.Note("B3", quarterLength=1))
        oben.insert(1, note.Note("A3", quarterLength=1))
        score.insert(0, oben)
        befunde = AnalyseProgramm(score, hilfsstimme_index=None).analysiere()
        b = next(x for x in befunde if x.ton.name == "B")
        self.assertEqual(b.klang.kategorie, "7-6_oder_Septakkord")
        self.assertNotEqual(b.status, "akkordeigene_Dissonanz")


if __name__ == "__main__":
    unittest.main()
