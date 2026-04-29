import sys
import os
import subprocess

from pipeline_utils import find_input_for_step, output_path_for_step, ask_continue_chain, FFMPEG_CMD

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

    # Run ffmpeg from the SRT's directory and pass only the filename.
    # This avoids Windows path escaping issues (drive letter colons) in the
    # subtitles filter, which cannot reliably handle absolute paths on Windows.
    srt_dir = os.path.dirname(os.path.abspath(srt_path))
    srt_name = os.path.basename(srt_path)
    src_abs = os.path.abspath(src)
    out_abs = os.path.abspath(out)

    vf = f"subtitles={srt_name}:force_style='{SUBTITLE_STYLE}'"
    result = subprocess.run(
        [FFMPEG_CMD, "-i", src_abs, "-vf", vf, "-y", out_abs],
        cwd=srt_dir,
        capture_output=True,
        text=True,
        errors="replace",
    )
    if result.returncode != 0:
        print(f"  ffmpeg error:\n{result.stderr}")
        raise RuntimeError("ffmpeg subtitle burn failed.")

    print(f"✓ Saved: {out_name}")
    ask_continue_chain(folder, STEP)


if __name__ == "__main__":
    from pipeline_utils import DEFAULT_FOLDER
    folder = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_FOLDER
    run(folder)
