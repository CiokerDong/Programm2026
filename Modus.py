"""Kompatible Exporte fuer den neuen harmonischen Kontext.

Die fruehere Funktion ``Modi_auf_der_Hiflsstimme`` wurde durch die Klasse
``HarmonischerKontext`` ersetzt. Neue Aufrufer importieren sie direkt aus dem
gleichnamigen Modul.
"""

from HarmonischerKontext import HarmonischerKontext, Harmoniesegment

__all__ = ["HarmonischerKontext", "Harmoniesegment"]
