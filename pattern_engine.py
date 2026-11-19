"""Pattern engine: places harmony, bass and drum events for one chord.

Rhythm rules (unchanged from the thesis version)
-----------------------------------------------
- Harmony: the voiced chord is held for the chord's full duration.
- Bass: plays the chord root on beat 1 (complexity 1), beats 1 and 3
  (complexity 2) or every beat (complexity 3). Beat 3 is pushed 10 ms early.
- Drums: kick on beats 1 and 3, snare on 2 and 4 (snare 12 ms late).
- Hi-hat: none (1), 8ths (2) or 16ths (3); off-beats 10 ms late,
  on-beats 3 ms early for a light swing.
"""

from config import BAR_BEATS

KICK, SNARE, HIHAT = 36, 38, 42

BASS_BEATS = {1: [0], 2: [0, 2], 3: [0, 1, 2, 3]}
DRUM_MAP = {0: KICK, 1: SNARE, 2: KICK, 3: SNARE}
HIHAT_SUBDIVISIONS = {1: 0, 2: 8, 3: 16}


def _event(pitch, start, end, track):
    return {
        "pitch": pitch,
        "start": max(0.0, start),
        "end": end,
        "track": track,
    }


def generate_patterns(
    voicing,
    bass_root,
    start_time,
    seconds_per_beat,
    complexity_level,
    bars=1,
):
    events = []
    bar_duration = BAR_BEATS * seconds_per_beat

    # Harmony: hold the chord for all of its bars
    for note in voicing:
        events.append(_event(
            note, start_time, start_time + bars * bar_duration, "harmony"
        ))

    for bar in range(bars):
        bar_start = start_time + bar * bar_duration

        # Bass
        for beat in BASS_BEATS[complexity_level]:
            base_start = bar_start + beat * seconds_per_beat
            offset = -0.01 if beat == 2 else 0
            events.append(_event(
                bass_root,
                base_start + offset,
                base_start + seconds_per_beat,
                "bass",
            ))

        # Kick and snare
        for beat in range(BAR_BEATS):
            base_start = bar_start + beat * seconds_per_beat
            pitch = DRUM_MAP[beat]
            offset = 0.012 if pitch == SNARE else 0
            events.append(_event(
                pitch,
                base_start + offset,
                base_start + 0.5 * seconds_per_beat,
                "drums",
            ))

        # Hi-hat
        subdivisions = HIHAT_SUBDIVISIONS[complexity_level]
        for i in range(subdivisions):
            base_position = bar_start + (i / subdivisions) * bar_duration
            offset = 0.01 if i % 2 == 1 else -0.003
            events.append(_event(
                HIHAT,
                base_position + offset,
                base_position + 0.02,
                "drums",
            ))

    return events
