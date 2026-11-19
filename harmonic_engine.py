"""Harmonic engine: chord symbols -> pitches, with rule-based voice leading.

Rules
-----
1. A chord symbol is ROOT + QUALITY, e.g. ``C``, ``Bb``, ``F#m7``, ``Gsus4``.
   Roots accept sharps (#) and flats (b); the letter is case-insensitive.
2. Each quality maps to a fixed set of intervals above the root
   (see ``CHORD_QUALITIES``).
3. Voice leading: for every chord after the first, all inversions are
   tried and the one whose notes move the least (sum of semitone
   distances to the previous chord) is chosen, staying inside
   ``VOICE_RANGE``. Ties prefer the lower voicing.
4. Bass always plays the chord root, one octave below the chord's
   root-position root.
"""

import re

NOTE_TO_MIDI = {
    "C": 60, "C#": 61, "Db": 61,
    "D": 62, "D#": 63, "Eb": 63,
    "E": 64, "Fb": 64, "E#": 65,
    "F": 65, "F#": 66, "Gb": 66,
    "G": 67, "G#": 68, "Ab": 68,
    "A": 69, "A#": 70, "Bb": 70,
    "B": 71, "Cb": 71, "B#": 60,
}

NOTE_NAMES = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]

# quality suffix -> intervals in semitones above the root
CHORD_QUALITIES = {
    "": [0, 4, 7],          # major
    "maj": [0, 4, 7],
    "M": [0, 4, 7],
    "m": [0, 3, 7],         # minor
    "min": [0, 3, 7],
    "-": [0, 3, 7],
    "dim": [0, 3, 6],
    "aug": [0, 4, 8],
    "+": [0, 4, 8],
    "sus2": [0, 2, 7],
    "sus4": [0, 5, 7],
    "sus": [0, 5, 7],
    "5": [0, 7],            # power chord
    "6": [0, 4, 7, 9],
    "m6": [0, 3, 7, 9],
    "7": [0, 4, 7, 10],     # dominant 7
    "maj7": [0, 4, 7, 11],
    "M7": [0, 4, 7, 11],
    "m7": [0, 3, 7, 10],
    "min7": [0, 3, 7, 10],
    "dim7": [0, 3, 6, 9],
    "m7b5": [0, 3, 6, 10],
    "add9": [0, 4, 7, 14],
}

QUALITY_LABELS = (
    "major, m, dim, aug, sus2, sus4, 5, 6, m6, 7, maj7, m7, dim7, m7b5, add9"
)

# Harmony voicings stay between G3 and G5
VOICE_RANGE = (55, 79)

MAX_BARS_PER_CHORD = 8

_SYMBOL_RE = re.compile(r"^([A-Ga-g])([#b]?)(.*)$")
_DURATION_RE = re.compile(r"^(.+?):(\d+)$")

# case-insensitive lookup, except M / M7 which must stay distinct from m / m7
_QUALITY_LOWER = {
    k.lower(): k for k in CHORD_QUALITIES if k not in ("M", "M7")
}


class ChordError(ValueError):
    """Raised for chord symbols the engine cannot read."""


def parse_chord(chord_symbol):
    """Return ``(root_midi, intervals, normalized_symbol)``.

    Raises ``ChordError`` with a human-readable reason.
    """
    symbol = chord_symbol.strip()
    match = _SYMBOL_RE.match(symbol)
    if not match:
        raise ChordError(
            f"'{chord_symbol}' must start with a note letter A–G"
        )

    letter, accidental, quality = match.groups()
    root_name = letter.upper() + accidental

    if quality not in CHORD_QUALITIES:
        if quality.lower() in _QUALITY_LOWER:
            quality = _QUALITY_LOWER[quality.lower()]
        else:
            raise ChordError(
                f"'{chord_symbol}': unknown chord type '{quality}'. "
                f"Supported: {QUALITY_LABELS}"
            )

    return (
        NOTE_TO_MIDI[root_name],
        CHORD_QUALITIES[quality],
        root_name + quality,
    )


def get_chord_tones(chord_symbol):
    """Root-position MIDI pitches for a chord (root around middle C)."""
    root, intervals, _ = parse_chord(chord_symbol)
    return [root + i for i in intervals]


def get_triad(chord_symbol):
    """Backward-compatible alias used by the thesis version."""
    return get_chord_tones(chord_symbol)


def parse_progression(text):
    """Parse ``"C:2 G Am F"`` into ``[("C", 2), ("G", 1), ...]``.

    ``:N`` sets how many bars a chord lasts (default 1). Commas and
    bar lines (``|``) are treated as separators.
    Returns ``(items, errors)``; ``errors`` is a list of messages.
    """
    tokens = text.replace(",", " ").replace("|", " ").split()
    items, errors = [], []

    for token in tokens:
        bars = 1
        dur_match = _DURATION_RE.match(token)
        if dur_match:
            token, bars = dur_match.group(1), int(dur_match.group(2))
            if not 1 <= bars <= MAX_BARS_PER_CHORD:
                errors.append(
                    f"'{token}:{bars}': bars must be 1–{MAX_BARS_PER_CHORD}"
                )
                continue
        try:
            _, _, normalized = parse_chord(token)
            items.append((normalized, bars))
        except ChordError as exc:
            errors.append(str(exc))

    if not tokens:
        errors.append("Enter at least one chord, e.g. C G Am F")

    return items, errors


def _inversions(root_position):
    """All inversions of a voicing, at every octave that fits VOICE_RANGE."""
    n = len(root_position)
    candidates = []
    for k in range(n):
        inv = root_position[k:] + [p + 12 for p in root_position[:k]]
        for shift in range(-24, 25, 12):
            voiced = [p + shift for p in inv]
            if VOICE_RANGE[0] <= voiced[0] and voiced[-1] <= VOICE_RANGE[1]:
                candidates.append(voiced)
    return candidates


def _movement(prev, cand):
    """Semitone movement between two voicings (nearest-note matching,
    counted in both directions so added/dropped notes are penalised)."""
    return sum(min(abs(c - p) for p in prev) for c in cand) + sum(
        min(abs(p - c) for c in cand) for p in prev
    )


def voice_lead(chord_symbols, smooth=True):
    """Return a list of ``(voicing, bass_root)`` for each chord.

    With ``smooth=False`` every chord is in root position (thesis behaviour).
    """
    result = []
    prev = None

    for symbol in chord_symbols:
        root, intervals, _ = parse_chord(symbol)
        root_position = [root + i for i in intervals]
        bass = root - 12

        if not smooth or prev is None:
            voicing = root_position
        else:
            candidates = _inversions(root_position) or [root_position]
            voicing = min(
                candidates,
                key=lambda c: (_movement(prev, c), c[0]),
            )

        result.append((voicing, bass))
        prev = voicing

    return result


def midi_to_name(pitch):
    return f"{NOTE_NAMES[pitch % 12]}{pitch // 12 - 1}"
