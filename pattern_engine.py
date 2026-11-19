"""Pattern engine: places harmony, bass and drum events for one chord.

Rhythm rules (unchanged from the thesis version)
-----------------------------------------------
- Harmony: the voiced chord is held for the chord's full duration.
- Bass: plays the chord root on beat 1 (complexity 1), beats 1 and 3
  (complexity 2) or every beat (complexity 3). Beat 3 is pushed 10 ms early.
- Drums: kick on beats 1 and 3, snare on 2 and 4 (snare 12 ms late).
- Hi-hat: none (1), 8ths (2) or 16ths (3); off-beats 10 ms late,
  on-beats 3 ms early for a light swing.

Session rules
-------------
- Count-in (optional): one bar of four side-stick clicks before the music.
- Ending (optional): one bar holding the progression's first chord, with
  the bass root and a single kick on beat 1.
- Tempo ramp: each bar has its own tempo (``bar_bpms``), so every event
  carries the BPM of the bar it sits in.
"""

from config import BAR_BEATS

KICK, SIDE_STICK, SNARE, HIHAT = 36, 37, 38, 42

BASS_BEATS = {1: [0], 2: [0, 2], 3: [0, 1, 2, 3]}
DRUM_MAP = {0: KICK, 1: SNARE, 2: KICK, 3: SNARE}
HIHAT_SUBDIVISIONS = {1: 0, 2: 8, 3: 16}


def _event(pitch, start, end, track, bpm, **flags):
    return {
        "pitch": pitch,
        "start": max(0.0, start),
        "end": end,
        "track": track,
        "bpm": bpm,
        **flags,
    }


def bar_seconds(bpm):
    return BAR_BEATS * 60 / bpm


def generate_patterns(
    voicing,
    bass_root,
    start_time,
    seconds_per_beat,
    complexity_level,
    bars=1,
    bar_bpms=None,
):
    """Events for one chord lasting ``bars`` bars.

    ``bar_bpms`` gives each bar's tempo (for tempo ramps); by default every
    bar uses ``60 / seconds_per_beat``.
    """
    if bar_bpms is None:
        bar_bpms = [60 / seconds_per_beat] * bars

    events = []
    chord_end = start_time + sum(bar_seconds(b) for b in bar_bpms)

    # Harmony: hold the chord for all of its bars
    for note in voicing:
        events.append(_event(note, start_time, chord_end, "harmony", bar_bpms[0]))

    bar_start = start_time
    for bpm in bar_bpms:
        beat = 60 / bpm
        bar_duration = BAR_BEATS * beat

        # Bass
        for b in BASS_BEATS[complexity_level]:
            base_start = bar_start + b * beat
            offset = -0.01 if b == 2 else 0
            events.append(_event(
                bass_root, base_start + offset, base_start + beat, "bass", bpm,
                downbeat=(b == 0),
            ))

        # Kick and snare
        for b in range(BAR_BEATS):
            base_start = bar_start + b * beat
            pitch = DRUM_MAP[b]
            offset = 0.012 if pitch == SNARE else 0
            events.append(_event(
                pitch, base_start + offset, base_start + 0.5 * beat, "drums", bpm,
            ))

        # Hi-hat
        subdivisions = HIHAT_SUBDIVISIONS[complexity_level]
        for i in range(subdivisions):
            base_position = bar_start + (i / subdivisions) * bar_duration
            offset = 0.01 if i % 2 == 1 else -0.003
            events.append(_event(
                HIHAT, base_position + offset, base_position + 0.02, "drums", bpm,
            ))

        bar_start += bar_duration

    return events


def count_in_bar(start_time, bpm):
    """Four side-stick clicks, one per beat."""
    beat = 60 / bpm
    return [
        _event(SIDE_STICK, start_time + b * beat, start_time + b * beat + 0.1,
               "drums", bpm, count_in=True)
        for b in range(BAR_BEATS)
    ]


def ending_bar(voicing, bass_root, start_time, bpm):
    """Final bar: chord and bass held, one kick on beat 1."""
    end = start_time + bar_seconds(bpm)
    events = [_event(n, start_time, end, "harmony", bpm) for n in voicing]
    events.append(_event(bass_root, start_time, end, "bass", bpm, downbeat=True))
    events.append(_event(KICK, start_time, start_time + 0.5 * 60 / bpm, "drums", bpm))
    return events
