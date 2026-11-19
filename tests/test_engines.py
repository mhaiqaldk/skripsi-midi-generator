import io
import os
import sys

import pretty_midi
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from harmonic_engine import (  # noqa: E402
    ChordError, get_chord_tones, parse_chord, parse_progression, voice_lead,
    VOICE_RANGE,
)
from main import run_generator  # noqa: E402
from pattern_engine import HIHAT, generate_patterns  # noqa: E402


# --- harmony ---------------------------------------------------------------

@pytest.mark.parametrize("symbol, tones", [
    ("C", [60, 64, 67]),
    ("Am", [69, 72, 76]),
    ("Bb", [70, 74, 77]),
    ("A#", [70, 74, 77]),
    ("Ebm", [63, 66, 70]),
    ("G7", [67, 71, 74, 77]),
    ("Cmaj7", [60, 64, 67, 71]),
    ("Dm7", [62, 65, 69, 72]),
    ("Bdim", [71, 74, 77]),
    ("Fsus4", [65, 70, 72]),
])
def test_chord_tones(symbol, tones):
    assert get_chord_tones(symbol) == tones


def test_case_tolerant_root_and_quality():
    assert parse_chord("am")[2] == "Am"
    assert parse_chord("CMIN")[2] == "Cmin"
    # M (major) and m (minor) must stay distinct
    assert get_chord_tones("CM7") == [60, 64, 67, 71]
    assert get_chord_tones("Cm7") == [60, 63, 67, 70]


@pytest.mark.parametrize("bad", ["H", "Cxyz", "7", ""])
def test_invalid_chords(bad):
    with pytest.raises(ChordError):
        parse_chord(bad)


def test_parse_progression_with_durations():
    items, errors = parse_progression("C:2 G | Am, F:4")
    assert errors == []
    assert items == [("C", 2), ("G", 1), ("Am", 1), ("F", 4)]


def test_parse_progression_reports_errors():
    items, errors = parse_progression("C Q G:99")
    assert items == [("C", 1)]
    assert len(errors) == 2


def test_voice_leading_moves_less_than_root_position():
    chords = ["C", "G", "Am", "F"]

    def movement(voicings):
        return sum(
            sum(abs(a - b) for a, b in zip(sorted(v1), sorted(v2)))
            for (v1, _), (v2, _) in zip(voicings, voicings[1:])
        )

    smooth = voice_lead(chords)
    root = voice_lead(chords, smooth=False)
    assert movement(smooth) < movement(root)
    for voicing, _ in smooth[1:]:
        assert VOICE_RANGE[0] <= min(voicing) and max(voicing) <= VOICE_RANGE[1]


def test_bass_is_always_chord_root():
    for (voicing, bass), symbol in zip(voice_lead(["C", "G", "Am"]), ["C", "G", "Am"]):
        assert bass % 12 == parse_chord(symbol)[0] % 12


# --- patterns --------------------------------------------------------------

@pytest.mark.parametrize("complexity, bass_notes, hats", [(1, 1, 0), (2, 2, 8), (3, 4, 16)])
def test_event_counts_per_complexity(complexity, bass_notes, hats):
    events = generate_patterns([60, 64, 67], 48, 0.0, 0.5, complexity)
    assert sum(e["track"] == "harmony" for e in events) == 3
    assert sum(e["track"] == "bass" for e in events) == bass_notes
    assert sum(e["pitch"] == HIHAT for e in events) == hats


def test_multi_bar_chords_and_no_negative_times():
    events = generate_patterns([60, 64, 67], 48, 0.0, 0.5, 3, bars=2)
    assert sum(e["track"] == "bass" for e in events) == 8
    harmony = [e for e in events if e["track"] == "harmony"]
    assert all(e["end"] == pytest.approx(4.0) for e in harmony)
    assert min(e["start"] for e in events) >= 0


# --- end to end ------------------------------------------------------------

def test_same_seed_gives_identical_midi():
    a = run_generator(["C", "G", "Am", "F"], bpm=110, complexity_level=2, seed=42)
    b = run_generator(["C", "G", "Am", "F"], bpm=110, complexity_level=2, seed=42)
    c = run_generator(["C", "G", "Am", "F"], bpm=110, complexity_level=2, seed=43)
    assert a["midi_bytes"] == b["midi_bytes"]
    assert a["midi_bytes"] != c["midi_bytes"]


def test_generated_midi_is_valid_and_has_three_tracks():
    r = run_generator([("C", 2), ("G", 1)], bpm=120, complexity_level=1, seed=1)
    midi = pretty_midi.PrettyMIDI(io.BytesIO(r["midi_bytes"]))
    assert [i.name for i in midi.instruments] == ["Harmony", "Bass", "Drums"]
    assert r["bars"] == 3
    assert r["duration"] == pytest.approx(6.0)
    assert midi.get_end_time() == pytest.approx(6.0, abs=0.05)


# --- sessions and tempo ramp ----------------------------------------------

from main import plan_session, tempo_schedule  # noqa: E402
from pattern_engine import SIDE_STICK, bar_seconds  # noqa: E402


def test_tempo_schedule_equal_steps():
    assert tempo_schedule(100, 100, 3) == [100.0, 100.0, 100.0]
    assert tempo_schedule(90, 110, 5) == [90.0, 95.0, 100.0, 105.0, 110.0]
    assert tempo_schedule(80, 60, 3) == [80.0, 70.0, 60.0]


def test_session_reaches_target_with_fewest_loops():
    loops, bpms = plan_session(4, 120, 120, 1, count_in=False, ending=False)
    total = sum(bar_seconds(b) for b in bpms)
    assert total >= 60
    assert total - 4 * bar_seconds(120) < 60  # one fewer loop would be short
    assert loops == 8


def test_count_in_and_ending_add_one_bar_each():
    plain = run_generator(["C", "G"], bpm=100, seed=1)
    extra = run_generator(["C", "G"], bpm=100, seed=1, count_in=True, ending=True)
    assert extra["bars"] == plain["bars"] + 2
    midi = pretty_midi.PrettyMIDI(io.BytesIO(extra["midi_bytes"]))
    clicks = [n for n in midi.instruments[2].notes if n.pitch == SIDE_STICK]
    assert len(clicks) == 4 and max(n.start for n in clicks) < bar_seconds(100)
    # ending bar holds the first chord's root in the bass
    last_bass = max(midi.instruments[1].notes, key=lambda n: n.start)
    assert last_bass.pitch % 12 == 0  # C


def test_tempo_ramp_writes_tempo_map_and_keeps_bar_grid():
    r = run_generator(["C", "G", "Am", "F"], bpm=90, bpm_end=110,
                      session_minutes=1, ending=True, seed=5)
    assert r["bar_bpms"][0] == 90 and r["bar_bpms"][-1] == 110
    midi = pretty_midi.PrettyMIDI(io.BytesIO(r["midi_bytes"]))
    _, tempi = midi.get_tempo_changes()
    assert len(tempi) == r["bars"]
    assert tempi[0] == pytest.approx(90, abs=0.1)
    assert tempi[-1] == pytest.approx(110, abs=0.1)
    # every kick on beat 1 sits exactly on a bar line of the tempo map
    ticks_per_bar = 4 * midi.resolution
    downbeat_kicks = sorted(n.start for n in midi.instruments[2].notes if n.pitch == 36)[::2]
    for t in downbeat_kicks:
        assert midi.time_to_tick(t) % ticks_per_bar in (0, ticks_per_bar - 1)
    assert r["duration"] >= 60


def test_same_seed_identical_with_session_options():
    kwargs = dict(bpm=80, bpm_end=60, session_minutes=2, count_in=True, ending=True, seed=9)
    a = run_generator(["Am", "F", "C", "G"], **kwargs)
    b = run_generator(["Am", "F", "C", "G"], **kwargs)
    assert a["midi_bytes"] == b["midi_bytes"]


# --- explanation -------------------------------------------------------------

from explain_engine import explain, harmony_rows, inversion_name  # noqa: E402


def test_inversion_names():
    assert inversion_name("C", [60, 64, 67]) == "root position"
    assert inversion_name("G", [59, 62, 67]) == "1st inversion"
    assert inversion_name("F", [60, 65, 69]) == "2nd inversion"


def test_explanation_matches_the_result():
    r = run_generator(["C", "G", "Am", "F"], bpm=70, bpm_end=90, session_minutes=1,
                      count_in=True, ending=True, preset_name="Relaxation", seed=77)
    sections = dict(explain(r))
    assert list(sections) == ["Preset", "Session", "Rhythm", "Harmony",
                              "Loudness", "Reproducibility"]
    text = " ".join(" ".join(v) for v in sections.values())
    assert "seed **77**" in text
    assert "70 → 90 BPM" in text
    assert "hi-hat" not in " ".join(sections["Loudness"])  # complexity 1: no hats
    rows = harmony_rows(r)
    assert [row["Chord"] for row in rows] == ["C", "G", "Am", "F"]
    assert rows[1]["Movement"] == "3 semitones"
