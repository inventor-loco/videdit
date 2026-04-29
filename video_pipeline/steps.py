# steps.py
# Single source of truth for step order and short names.
# All other scripts import STEPS from here.

STEPS = [
    "enhanced",      # 01 — denoise + normalize audio
    "silenced",      # 02 — remove silences
    "transcribed",   # 03 — whisper → .srt (with review gate)
    "captioned",     # 04 — burn .srt into video
    "concat",        # 05 — prepend intro / append outro
    "watermarked",   # 06 — overlay watermark image
]
