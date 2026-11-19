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


from harmonic_engine import parse_chord, voice_lead
from midi_engine import OUTPUT_DIR, build_midi, midi_to_bytes, save_midi
from pattern_engine import bar_seconds, count_in_bar, ending_bar, generate_patterns

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


MAX_LOOPS = 2000


def tempo_schedule(bpm_start, bpm_end, n_bars):
    """Rule: tempo moves in equal steps from the first bar to the last."""
    if n_bars <= 1 or bpm_start == bpm_end:
        return [float(bpm_start)] * n_bars
    step = (bpm_end - bpm_start) / (n_bars - 1)
    return [round(bpm_start + step * k, 1) for k in range(n_bars)]


def plan_session(loop_bars, bpm_start, bpm_end, session_minutes, count_in, ending):
    """Pick how many times to loop the progression.

    Rule: play the progression once, or repeat it until the session is at
    least ``session_minutes`` long. Returns ``(loops, bar_bpms)``.
    """
    extra = int(count_in) + int(ending)

    def schedule(loops):
        return tempo_schedule(bpm_start, bpm_end, loops * loop_bars + extra)

    if not session_minutes:
        return 1, schedule(1)

    target = session_minutes * 60
    for loops in range(1, MAX_LOOPS + 1):
        bpms = schedule(loops)
        if sum(bar_seconds(b) for b in bpms) >= target:
            return loops, bpms
    return MAX_LOOPS, schedule(MAX_LOOPS)


def run_generator(
    chords,
    bpm=100,
    complexity_level=1,
    preset_name="Manual",
    seed=None,
    smooth_voicing=True,
    save=False,
    bpm_end=None,
    session_minutes=None,
    count_in=False,
    ending=False,
):
    items = _normalize_chords(chords)
    if seed is None:
        seed = new_seed()
    if bpm_end is None:
        bpm_end = bpm

    loop_bars = sum(b for _, b in items)
    loops, bar_bpms = plan_session(
        loop_bars, bpm, bpm_end, session_minutes, count_in, ending
    )

    symbols = [s for s, _ in items] * loops
    if ending:
        symbols.append(items[0][0])  # end on the progression's first chord
    voicings = voice_lead(symbols, smooth=smooth_voicing)

    all_events = []
    current_time = 0.0
    bar_index = 0

    if count_in:
        all_events.extend(count_in_bar(current_time, bar_bpms[0]))
        current_time += bar_seconds(bar_bpms[0])
        bar_index += 1

    for (symbol, bars), (voicing, bass) in zip(items * loops, voicings):
        chord_bpms = bar_bpms[bar_index:bar_index + bars]
        all_events.extend(generate_patterns(
            voicing, bass, current_time, 60 / chord_bpms[0],
            complexity_level, bars=bars, bar_bpms=chord_bpms,
        ))
        current_time += sum(bar_seconds(b) for b in chord_bpms)
        bar_index += bars

    if ending:
        voicing, bass = voicings[-1]
        all_events.extend(ending_bar(voicing, bass, current_time, bar_bpms[-1]))
        current_time += bar_seconds(bar_bpms[-1])

    midi = build_midi(all_events, bpm, seed=seed, bar_bpms=bar_bpms)
    midi_bytes = midi_to_bytes(midi)

    tempo_label = f"{bpm}bpm" if bpm == bpm_end else f"{bpm}-{bpm_end}bpm"
    length_label = f"_{session_minutes}min" if session_minutes else ""
    filename = f"rgmbi_{tempo_label}_c{complexity_level}{length_label}_seed{seed}.mid"

    result = {
        "midi": midi,
        "midi_bytes": midi_bytes,
        "filename": filename,
        "event_count": len(all_events),
        "chords": items,
        "progression": progression_label(items),
        "voicings": [
            {"symbol": s, "voicing": v, "bass": b}
            for (s, _), (v, b) in zip(items, voicings)
        ],
        "loop_bars": loop_bars,
        "loops": loops,
        "bars": len(bar_bpms),
        "bar_bpms": bar_bpms,
        "duration": current_time,
        "bpm": bpm,
        "bpm_end": bpm_end,
        "session_minutes": session_minutes,
        "count_in": count_in,
        "ending": ending,
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
