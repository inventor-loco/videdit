import sys
import os
import re
import shutil
import subprocess

from moviepy import VideoFileClip, concatenate_videoclips

from pipeline_utils import find_input_for_step, output_path_for_step, ask_continue_chain, FFMPEG_CMD

# ── CONFIG ────────────────────────────────────────────────────────────────────
STEP               = "silenced"
SILENCE_THRESH_DB  = -35   # dBFS below which audio is considered silent
MIN_SILENCE_MS     = 500   # minimum silence duration that triggers a cut
SILENCE_PADDING_MS = 150   # ms kept at both edges of each kept segment
# ─────────────────────────────────────────────────────────────────────────────


def _detect_nonsilent(src):
    """Use ffmpeg silencedetect to find non-silent ranges. Returns list of (start_ms, end_ms)."""
    min_silence_s = MIN_SILENCE_MS / 1000
    noise = f"{SILENCE_THRESH_DB}dB"

    result = subprocess.run(
        [FFMPEG_CMD, "-i", src,
         "-af", f"silencedetect=noise={noise}:d={min_silence_s}",
         "-f", "null", "-"],
        capture_output=True, text=True, errors="replace",
    )
    output = result.stderr

    # Parse total duration
    dur_match = re.search(r"Duration:\s*(\d+):(\d+):([\d.]+)", output)
    if not dur_match:
        raise RuntimeError("Could not read video duration from ffmpeg output.")
    h, m, s = dur_match.groups()
    total_s = int(h) * 3600 + int(m) * 60 + float(s)
    total_ms = int(total_s * 1000)

    silence_starts = [float(x) for x in re.findall(r"silence_start:\s*([\d.]+)", output)]
    silence_ends   = [float(x) for x in re.findall(r"silence_end:\s*([\d.]+)", output)]

    if not silence_starts:
        return [(0, total_ms)]  # no silence found

    eps = 0.01  # ignore gaps smaller than 10 ms
    non_silent = []
    pos = 0.0

    for i, s_start in enumerate(silence_starts):
        if s_start - pos > eps:
            non_silent.append((int(pos * 1000), int(s_start * 1000)))
        pos = silence_ends[i] if i < len(silence_ends) else total_s

    if total_s - pos > eps:
        non_silent.append((int(pos * 1000), total_ms))

    return non_silent, total_ms


def run(folder):
    src = find_input_for_step(folder, STEP)
    out = output_path_for_step(src, STEP)

    if os.path.exists(out):
        print(f"⚠  Step '{STEP}' already applied to this file.")
        return

    src_name = os.path.basename(src)
    out_name = os.path.basename(out)
    print(f"[{STEP}] {src_name} → {out_name}")

    print("  Detecting silences...")
    result = _detect_nonsilent(src)

    # _detect_nonsilent returns (list, total_ms) when silences exist, or [(0, total_ms)] when none
    if isinstance(result, tuple) and len(result) == 2 and isinstance(result[0], list):
        non_silent, total_ms = result
    else:
        non_silent, total_ms = result, result[-1][1]

    if not non_silent:
        raise ValueError(
            f"The entire video appears to be silent (thresh={SILENCE_THRESH_DB} dBFS). "
            "Check the source file."
        )

    # Single segment covering the whole file → no silences to remove
    if len(non_silent) == 1 and non_silent[0][0] == 0 and non_silent[0][1] >= total_ms - 10:
        print("  No silences detected — copying source unchanged.")
        shutil.copy2(src, out)
        print(f"✓ Saved: {out_name}")
        ask_continue_chain(folder, STEP)
        return

    # Expand segments by padding (clamped to valid range)
    padded = []
    for start_ms, end_ms in non_silent:
        s = max(0, start_ms - SILENCE_PADDING_MS)
        e = min(total_ms, end_ms + SILENCE_PADDING_MS)
        padded.append((s, e))

    # Merge overlapping padded segments
    merged = [padded[0]]
    for s, e in padded[1:]:
        if s <= merged[-1][1]:
            merged[-1] = (merged[-1][0], max(merged[-1][1], e))
        else:
            merged.append((s, e))

    print(f"  Keeping {len(merged)} segment(s) out of original duration {total_ms / 1000:.1f}s")

    clip = VideoFileClip(src)
    subclips = [clip.subclipped(s / 1000, e / 1000) for s, e in merged]
    final = concatenate_videoclips(subclips)
    final.write_videofile(out, logger=None)
    clip.close()
    final.close()

    print(f"✓ Saved: {out_name}")
    ask_continue_chain(folder, STEP)


if __name__ == "__main__":
    from pipeline_utils import DEFAULT_FOLDER
    folder = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_FOLDER
    run(folder)
