import sys
import os

import ffmpeg

from pipeline_utils import find_input_for_step, output_path_for_step, ask_continue_chain

# ── CONFIG ────────────────────────────────────────────────────────────────────
STEP           = "captioned"
FONT_SIZE      = 24
FONT_COLOR     = "&HFFFFFF"   # white, ASS/SSA hex format
SUBTITLE_STYLE = f"FontSize={FONT_SIZE},PrimaryColour={FONT_COLOR},Outline=1,Shadow=0"
# ─────────────────────────────────────────────────────────────────────────────


def run(folder):
    src = find_input_for_step(folder, STEP)
    out = output_path_for_step(src, STEP)

    if os.path.exists(out):
        print(f"⚠  Step '{STEP}' already applied to this file.")
        return

    src_name = os.path.basename(src)
    out_name = os.path.basename(out)
    print(f"[{STEP}] {src_name} → {out_name}")

    # Derive SRT path from input stem
    srt_path = os.path.splitext(src)[0] + ".srt"
    if not os.path.exists(srt_path):
        raise FileNotFoundError(
            f"SRT file not found: '{srt_path}'. "
            "Run step_transcribed.py first to generate the subtitle file."
        )

    print(f"  Burning subtitles from {os.path.basename(srt_path)}...")
    try:
        # Escape colons in path for ffmpeg subtitles filter (Windows-safe too)
        escaped_srt = srt_path.replace("\\", "/").replace(":", "\\:")
        (
            ffmpeg
            .input(src)
            .output(
                out,
                vf=f"subtitles={escaped_srt}:force_style='{SUBTITLE_STYLE}'",
            )
            .overwrite_output()
            .run(quiet=True)
        )
    except ffmpeg.Error as exc:
        print(f"  ffmpeg error:\n{exc.stderr.decode() if exc.stderr else exc}")
        raise

    print(f"✓ Saved: {out_name}")
    ask_continue_chain(folder, STEP)


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print(f"Usage: python {sys.argv[0]} <folder>")
        sys.exit(1)
    run(sys.argv[1])
