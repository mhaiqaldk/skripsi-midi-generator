"""MIDI engine: turns pattern events into a multi-track MIDI file.

Velocity rules live in ``config.py``. Humanisation uses a seeded random
generator, so the same seed and inputs always give an identical file.
"""

import io
import os
import random

import pretty_midi

import config
from pattern_engine import KICK, SNARE

OUTPUT_DIR = "outputs"

TRACK_ORDER = ["harmony", "bass", "drums"]


def base_velocity_for(bpm):
    for upper, velocity in config.TEMPO_VELOCITY_BANDS:
        if bpm < upper:
            return velocity
    return config.TEMPO_VELOCITY_BANDS[-1][1]


def velocity_for(event, bpm, rng):
    base = base_velocity_for(bpm)
    track = event["track"]

    if track == "harmony":
        v = base + config.HARMONY_OFFSET + rng.randint(
            -config.HARMONY_JITTER, config.HARMONY_JITTER
        )
    elif track == "bass":
        bar_length = config.BAR_BEATS * (60 / bpm)
        if event["start"] % bar_length < 0.01:
            v = base + config.BASS_DOWNBEAT_OFFSET
        else:
            v = base + config.BASS_OFFSET + rng.randint(
                -config.BASS_JITTER, config.BASS_JITTER
            )
    elif event["pitch"] == KICK:
        v = base + config.KICK_OFFSET
    elif event["pitch"] == SNARE:
        v = base + config.SNARE_OFFSET
    else:  # hi-hat
        v = base + config.HIHAT_OFFSET + rng.randint(
            -config.HIHAT_JITTER, config.HIHAT_JITTER
        )

    return max(1, min(127, v))


def build_midi(all_events, bpm, seed=None):
    """Return a ``pretty_midi.PrettyMIDI`` object for the events."""
    rng = random.Random(seed)

    midi = pretty_midi.PrettyMIDI(initial_tempo=bpm)
    instruments = {
        "harmony": pretty_midi.Instrument(
            program=config.HARMONY_PROGRAM, name="Harmony"
        ),
        "bass": pretty_midi.Instrument(
            program=config.BASS_PROGRAM, name="Bass"
        ),
        "drums": pretty_midi.Instrument(
            program=0, is_drum=True, name="Drums"
        ),
    }

    for event in all_events:
        instruments[event["track"]].notes.append(pretty_midi.Note(
            velocity=velocity_for(event, bpm, rng),
            pitch=event["pitch"],
            start=event["start"],
            end=event["end"],
        ))

    midi.instruments.extend(instruments[t] for t in TRACK_ORDER)
    return midi


def midi_to_bytes(midi):
    buffer = io.BytesIO()
    midi.write(buffer)
    return buffer.getvalue()


def save_midi(midi_bytes, filename, output_dir=OUTPUT_DIR):
    os.makedirs(output_dir, exist_ok=True)
    path = os.path.join(output_dir, filename)
    with open(path, "wb") as f:
        f.write(midi_bytes)
    return path


def create_midi(all_events, bpm, complexity_level=1, output_name=None, seed=None):
    """Thesis-era helper: build and save to ``outputs/``. Returns the path."""
    from datetime import datetime

    if output_name is None:
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_name = f"output_{bpm}_c{complexity_level}_{stamp}.mid"
    midi = build_midi(all_events, bpm, seed=seed)
    return save_midi(midi_to_bytes(midi), output_name)
