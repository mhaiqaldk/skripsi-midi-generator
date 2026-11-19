"""Explain a generated result in terms of the rules that produced it.

Everything here is derived from the result and the same rule tables the
generator uses (config, pattern_engine, harmonic_engine), so the
explanation can't drift from what the generator actually did.
"""

import config
from harmonic_engine import midi_to_name, parse_chord, voice_movement
from midi_engine import base_velocity_for
from pattern_engine import BASS_BEATS, HIHAT_SUBDIVISIONS

BAND_NAMES = ["soft", "medium", "firm", "strong"]
BEAT_NAMES = {0: "1", 1: "2", 2: "3", 3: "4"}
INVERSION_NAMES = ["root position", "1st inversion", "2nd inversion", "3rd inversion"]


def _plural(n, word):
    return f"{n} {word}" + ("" if n == 1 else "s")


def _band(bpm):
    for i, (upper, velocity) in enumerate(config.TEMPO_VELOCITY_BANDS):
        if bpm < upper:
            return i, velocity
    return len(config.TEMPO_VELOCITY_BANDS) - 1, config.TEMPO_VELOCITY_BANDS[-1][1]


def _band_label(i):
    upper = config.TEMPO_VELOCITY_BANDS[i][0]
    lower = config.TEMPO_VELOCITY_BANDS[i - 1][0] if i else None
    if lower is None:
        return f"under {upper} BPM"
    if upper >= 999:
        return f"{lower} BPM and above"
    return f"{lower}–{upper - 1} BPM"


def semitones_moved(prev, cur):
    """Plain distance the voices travel: lowest to lowest, next to next.
    (Chords of different sizes fall back to the nearest-note measure.)"""
    if len(prev) == len(cur):
        return sum(abs(a - b) for a, b in zip(sorted(prev), sorted(cur)))
    return round(voice_movement(prev, cur) / 2)


def inversion_name(symbol, voicing):
    root, intervals, _ = parse_chord(symbol)
    classes = [i % 12 for i in intervals]
    lowest = (min(voicing) - root) % 12
    idx = classes.index(lowest) if lowest in classes else 0
    return INVERSION_NAMES[min(idx, len(INVERSION_NAMES) - 1)]


def preset_section(result):
    preset = config.PRESET_CONFIG.get(result["preset"])
    if not preset:
        return None
    lines = [
        f"**{result['preset']}** is meant for {preset['purpose']}, so it "
        f"suggests **{preset['bpm']} BPM** (range {preset['range']}) and "
        f"**complexity {preset['complexity']}**."
    ]
    if result["bpm"] != preset["bpm"]:
        lines.append(f"You set the tempo to {result['bpm']} BPM instead.")
    if result["complexity"] != preset["complexity"]:
        lines.append(f"You set the complexity to {result['complexity']} instead.")
    return "Preset", lines


def dynamics_section(result):
    bar_bpms = result.get("bar_bpms") or [result["bpm"]]
    runs = []  # (band index, first bar, last bar)
    for n, bpm in enumerate(bar_bpms, start=1):
        band, _ = _band(bpm)
        if runs and runs[-1][0] == band:
            runs[-1][2] = n
        else:
            runs.append([band, n, n])

    lines = []
    if len(runs) == 1:
        band, velocity = _band(bar_bpms[0])
        lines.append(
            f"Tempo {result['bpm']} BPM is in the {_band_label(band)} band, "
            f"so the base loudness is **{velocity}** ({BAND_NAMES[band]})."
        )
    else:
        lines.append("The tempo ramp crosses loudness bands, so loudness follows it:")
        for band, first, last in runs:
            velocity = config.TEMPO_VELOCITY_BANDS[band][1]
            lines.append(
                f"- bars {first}–{last}: {_band_label(band)} → base "
                f"**{velocity}** ({BAND_NAMES[band]})"
            )

    base = base_velocity_for(bar_bpms[0])
    c = result["complexity"]
    parts = [
        f"kick {base + config.KICK_OFFSET}",
        f"snare {base + config.SNARE_OFFSET}",
        f"bass on beat 1 {base + config.BASS_DOWNBEAT_OFFSET}",
    ]
    if len(BASS_BEATS[c]) > 1:
        parts.append(f"other bass notes {base + config.BASS_OFFSET}±{config.BASS_JITTER}")
    parts.append(f"harmony {base + config.HARMONY_OFFSET}±{config.HARMONY_JITTER}")
    if HIHAT_SUBDIVISIONS[c]:
        parts.append(f"hi-hat {base + config.HIHAT_OFFSET}±{config.HIHAT_JITTER}")
    lines.append(
        f"Each part is set relative to that base (shown for {base}): "
        + ", ".join(parts)
        + " (out of 127). Accenting beat 1 makes the pulse easy to follow."
    )
    return "Loudness", lines


def rhythm_section(result):
    c = result["complexity"]
    beats = ", ".join(BEAT_NAMES[b] for b in BASS_BEATS[c])
    hats = HIHAT_SUBDIVISIONS[c]
    hat_text = (
        "no hi-hat" if hats == 0
        else f"a hi-hat on every {'8th' if hats == 8 else '16th'} note"
    )
    offsets = ["snare 12 ms late"]
    if 2 in BASS_BEATS[c]:
        offsets.append("bass on beat 3 10 ms early")
    if hats:
        offsets.append("off-beat hi-hats 10 ms late")
    return "Rhythm", [
        f"Complexity **{c}** → bass on beat{'s' if len(BASS_BEATS[c]) > 1 else ''} "
        f"{beats}, and {hat_text}.",
        "Kick on beats 1 and 3, snare on 2 and 4: a steady backbeat in every "
        "preset.",
        "Small fixed timing offsets add groove without randomness: "
        + ", ".join(offsets) + ".",
    ]


def harmony_rows(result):
    rows = []
    prev = None
    for v in result.get("voicings", []):
        voicing = v["voicing"]
        rows.append({
            "Chord": v["symbol"],
            "Notes (low → high)": " ".join(midi_to_name(p) for p in sorted(voicing)),
            "Voicing": inversion_name(v["symbol"], voicing),
            "Bass": midi_to_name(v["bass"]),
            "Movement": "—" if prev is None else _plural(semitones_moved(prev, voicing), "semitone"),
        })
        prev = voicing
    return rows


def harmony_section(result):
    symbols = [v["symbol"] for v in result.get("voicings", [])]
    if not symbols:
        return None
    if result["smooth_voicing"]:
        root_position = [
            [parse_chord(s)[0] + i for i in parse_chord(s)[1]] for s in symbols
        ]
        smooth = [v["voicing"] for v in result["voicings"]]

        def total(vs):
            return sum(semitones_moved(a, b) for a, b in zip(vs, vs[1:]))

        lines = [
            "**Smooth voice leading:** each chord uses the inversion whose "
            "notes move the least from the previous chord, which keeps the "
            "harmony calm and connected.",
            f"Across one pass the voices move **{total(smooth)} semitones**, "
            f"compared with {total(root_position)} if every chord were in root "
            "position.",
        ]
    else:
        lines = [
            "Every chord is in **root position** (original thesis behaviour), "
            "so the harmony jumps when the root moves."
        ]
    lines.append("The bass always plays the chord's root, an octave below "
                 "the chord.")
    return "Harmony", lines


def session_section(result):
    lines = []
    loops = result.get("loops", 1)
    loop_bars = result.get("loop_bars", result["bars"])
    if result.get("session_minutes"):
        lines.append(
            f"To fill **{result['session_minutes']} min**, the {loop_bars}-bar "
            f"progression repeats **{loops}×**, the fewest repeats that reach "
            "the length."
        )
    else:
        lines.append(f"The {loop_bars}-bar progression plays once.")
    if result.get("bpm_end", result["bpm"]) != result["bpm"]:
        bars = result["bars"]
        step = (result["bpm_end"] - result["bpm"]) / max(bars - 1, 1)
        lines.append(
            f"**Tempo ramp:** {result['bpm']} → {result['bpm_end']} BPM in "
            f"equal steps of {step:+.2f} BPM per bar over {bars} bars. The MIDI "
            "file stores a tempo for every bar, so it lines up with the grid "
            "in any DAW."
        )
    if result.get("count_in"):
        lines.append("**Count-in:** one bar of four side-stick clicks so the "
                     "listener can find the pulse before the music starts.")
    if result.get("ending"):
        lines.append(f"**Ending:** a final bar holds {result['chords'][0][0]}, "
                     "the progression's first chord, which usually sounds "
                     "like home.")
    return "Session", lines


def reproducibility_section(result):
    return "Reproducibility", [
        f"The only random part is the small loudness variation (the ± values "
        f"above), and it comes from seed **{result['seed']}**. With the same "
        "settings and seed you always get exactly the same file."
    ]


def explain(result):
    """Return a list of ``(title, lines)`` sections."""
    sections = [
        preset_section(result),
        session_section(result),
        rhythm_section(result),
        harmony_section(result),
        dynamics_section(result),
        reproducibility_section(result),
    ]
    return [s for s in sections if s]
