"""Project-specific additions to music21.chord.Chord.

The implementation of ``isIncompleteSeventh`` comes from
``chord___init___before_german_docstrings.py`` in this project.
"""

from music21 import chord
from music21.common.decorators import cacheMethod


@cacheMethod
def isIncompleteSeventh(self: chord.Chord) -> bool:
    """Return whether the chord has a root, seventh, and just one of third/fifth."""
    uniquePitchNames = set(self.pitchNames)
    if len(uniquePitchNames) == 3:
        if self.root() and self.seventh and (self.third or self.fifth):
            return True
    return False


chord.Chord.isIncompleteSeventh = isIncompleteSeventh
