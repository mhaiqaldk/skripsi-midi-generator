"""Generation pipeline: chords -> voicings -> patterns -> MIDI.

``run_generator`` works fully in memory and returns a result dict, so the
Streamlit app never needs to write files on the server. Pass ``save=True``
for local research runs: the MIDI goes to ``outputs/`` and a row is added
to ``outputs/run_log.csv``.
"""

import csv
import os
import random
from datetime import datetime

from config import BAR_BEATS
from harmonic_engine import parse_chord, voice_lead
from midi_engine import OUTPUT_DIR, build_midi, midi_to_bytes, save_midi
from pattern_engine import generate_patterns

LOG_FILE = os.path.join(OUTPUT_DIR, "run_log.csv")
LOG_HEADER = [
    "timestamp", "bpm", "complexity", "preset", "chord_progression",
    "output_filename", "number_of_events", "seed", "voice_leading",
]

SEED_MAX = 99_999


def new_seed():
    return random.randint(1, SEED_MAX)


def _normalize_chords(chords):
    """Accept ``["C", "G"]`` or ``[("C", 2), ("G", 1)]``."""
    items = []
    for chord in chords:
        if isinstance(chord, (tuple, list)):
            symbol, bars = chord
        else:
            symbol, bars = chord, 1
        items.append((parse_chord(symbol)[2], int(bars)))
    return items


def progression_label(items):
    return " ".join(s if b == 1 else f"{s}:{b}" for s, b in items)


def run_generator(
    chords,
    bpm=100,
    complexity_level=1,
    preset_name="Manual",
    seed=None,
    smooth_voicing=True,
    save=False,
):
    items = _normalize_chords(chords)
    if seed is None:
        seed = new_seed()

    seconds_per_beat = 60 / bpm
    bar_duration = BAR_BEATS * seconds_per_beat

    voicings = voice_lead([s for s, _ in items], smooth=smooth_voicing)

    all_events = []
    current_time = 0.0
    for (symbol, bars), (voicing, bass) in zip(items, voicings):
        all_events.extend(generate_patterns(
            voicing, bass, current_time, seconds_per_beat,
            complexity_level, bars=bars,
        ))
        current_time += bars * bar_duration

    midi = build_midi(all_events, bpm, seed=seed)
    midi_bytes = midi_to_bytes(midi)

    filename = f"rgmbi_{bpm}bpm_c{complexity_level}_seed{seed}.mid"

    result = {
        "midi": midi,
        "midi_bytes": midi_bytes,
        "filename": filename,
        "event_count": len(all_events),
        "chords": items,
        "progression": progression_label(items),
        "bars": sum(b for _, b in items),
        "duration": current_time,
        "bpm": bpm,
        "complexity": complexity_level,
        "preset": preset_name,
        "seed": seed,
        "smooth_voicing": smooth_voicing,
        "created": datetime.now().isoformat(timespec="seconds"),
    }

    if save:
        result["path"] = save_midi(midi_bytes, filename)
        write_run_log(result)

    return result


def write_run_log(result):
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    if os.path.exists(LOG_FILE):
        with open(LOG_FILE, newline="") as f:
            header = next(csv.reader(f), None)
        if header != LOG_HEADER:
            # keep the thesis-era log intact, start a new one
            os.rename(LOG_FILE, LOG_FILE.replace(".csv", "_legacy.csv"))

    is_new = not os.path.exists(LOG_FILE)
    with open(LOG_FILE, "a", newline="") as f:
        writer = csv.writer(f)
        if is_new:
            writer.writerow(LOG_HEADER)
        writer.writerow([
            result["created"], result["bpm"], result["complexity"],
            result["preset"], result["progression"], result["filename"],
            result["event_count"], result["seed"], result["smooth_voicing"],
        ])
