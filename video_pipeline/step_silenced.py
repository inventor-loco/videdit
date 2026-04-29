import sys
import os
import shutil
import tempfile

import ffmpeg
from pydub import AudioSegment
from pydub.silence import detect_nonsilent
from moviepy import VideoFileClip, concatenate_videoclips

from pipeline_utils import find_input_for_step, output_path_for_step, ask_continue_chain, FFMPEG_CMD

# ── CONFIG ────────────────────────────────────────────────────────────────────
STEP = "silenced"
SILENCE_THRESH_DB  = -40   # dBFS below which audio is considered silent
MIN_SILENCE_MS     = 700   # minimum silence duration that triggers a cut
SILENCE_PADDING_MS = 150   # ms kept at both edges of each kept segment
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

    stem = os.path.splitext(os.path.basename(src))[0]
    tmp_wav = os.path.join(folder, f"{stem}_tmpraw.wav")

    try:
        # 1. Extract mono 16 kHz audio
        print("  Extracting audio for silence detection...")
        (
            ffmpeg
            .input(src)
            .output(tmp_wav, ac=1, ar=16000, format="wav")
            .overwrite_output()
            .run(quiet=True, cmd=FFMPEG_CMD)
        )

        # 2. Detect non-silent ranges
        audio = AudioSegment.from_wav(tmp_wav)
        total_ms = len(audio)

        non_silent = detect_nonsilent(
            audio,
            min_silence_len=MIN_SILENCE_MS,
            silence_thresh=SILENCE_THRESH_DB,
        )

        if not non_silent:
            raise ValueError(
                f"The entire video appears to be silent (thresh={SILENCE_THRESH_DB} dBFS). "
                "Check the source file."
            )

        # Check if no silence was actually removed (non_silent covers the whole file)
        if len(non_silent) == 1 and non_silent[0][0] == 0 and non_silent[0][1] >= total_ms - 1:
            print("  No silences detected — copying source unchanged.")
            shutil.copy2(src, out)
            print(f"✓ Saved: {out_name}")
            ask_continue_chain(folder, STEP)
            return

        # 3. Expand each segment by padding (clamped to valid range)
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

        # 4. Cut and concatenate with moviepy
        clip = VideoFileClip(src)
        subclips = [clip.subclipped(s / 1000, e / 1000) for s, e in merged]
        final = concatenate_videoclips(subclips)
        final.write_videofile(out, logger=None)
        clip.close()
        final.close()

    except ffmpeg.Error as exc:
        print(f"  ffmpeg error:\n{exc.stderr.decode() if exc.stderr else exc}")
        raise
    finally:
        if os.path.exists(tmp_wav):
            os.remove(tmp_wav)

    print(f"✓ Saved: {out_name}")
    ask_continue_chain(folder, STEP)


if __name__ == "__main__":
    from pipeline_utils import DEFAULT_FOLDER
    folder = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_FOLDER
    run(folder)
