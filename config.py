# config.py

APP_NAME = "RG-MBI Generator"
APP_TAGLINE = "Rule-based therapeutic MIDI for music-based interventions"

DEFAULT_BPM = 100
TIME_SIGNATURE = (4, 4)
BAR_BEATS = 4

MIN_BPM, MAX_BPM = 60, 140

# Velocity rules ---------------------------------------------------------
# Base velocity is chosen by tempo band: (upper BPM bound, base velocity).
# The first band whose bound is above the tempo wins.
TEMPO_VELOCITY_BANDS = [
    (80, 65),     # < 80 BPM   -> soft
    (110, 80),    # 80–109     -> medium
    (140, 95),    # 110–139    -> firm
    (999, 110),   # >= 140     -> strong
]

# Per-track offsets from the base velocity, plus random humanisation range
HARMONY_OFFSET, HARMONY_JITTER = -5, 6
BASS_DOWNBEAT_OFFSET = 10
BASS_OFFSET, BASS_JITTER = -5, 5
KICK_OFFSET = 20
SNARE_OFFSET = 10
HIHAT_OFFSET, HIHAT_JITTER = -20, 3

# General MIDI programs
HARMONY_PROGRAM = 0   # Acoustic Grand Piano
BASS_PROGRAM = 33     # Electric Bass (finger)

# Kept for reference by older code; the bands above are what is used now
BASE_VELOCITY = 90
VELOCITY_VARIATION = 10

# Therapeutic presets: tempo and complexity auto-filled when a preset is picked
PRESET_CONFIG = {
    "Relaxation": {"bpm": 70, "complexity": 1, "range": "60–80 BPM",
                   "purpose": "slow, calming stimuli"},
    "Motor Synchronization": {"bpm": 110, "complexity": 2, "range": "100–120 BPM",
                              "purpose": "steady rhythmic entrainment"},
    "Cognitive Stimulation": {"bpm": 135, "complexity": 3, "range": "130–140 BPM",
                              "purpose": "higher-tempo engagement"},
}
