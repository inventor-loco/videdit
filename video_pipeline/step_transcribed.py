import sys
import os
import shutil

import whisper

from pipeline_utils import find_input_for_step, output_path_for_step, ask_continue_chain

# ── CONFIG ────────────────────────────────────────────────────────────────────
STEP                     = "transcribed"
WHISPER_MODEL            = "medium"   # tiny | base | small | medium | large
LOW_CONFIDENCE_THRESHOLD = -0.6       # avg_logprob below this is flagged for review
# ─────────────────────────────────────────────────────────────────────────────


def _format_timestamp(seconds):
    """Convert float seconds to SRT timestamp HH:MM:SS,mmm."""
    ms = int(round(seconds * 1000))
    h = ms // 3_600_000
    ms %= 3_600_000
    m = ms // 60_000
    ms %= 60_000
    s = ms // 1000
    ms %= 1000
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def _write_srt(segments, srt_path):
    with open(srt_path, "w", encoding="utf-8") as fh:
        for i, seg in enumerate(segments, start=1):
            start = _format_timestamp(seg["start"])
            end = _format_timestamp(seg["end"])
            text = seg["text"].strip()
            fh.write(f"{i}\n{start} --> {end}\n{text}\n\n")


def _is_flagged(seg):
    return (
        seg.get("avg_logprob", 0) < LOW_CONFIDENCE_THRESHOLD
        or len(seg["text"].strip()) < 3
    )


def review_segments_cli(segments):
    """Interactive CLI review of low-confidence Whisper segments."""
    flagged_indices = [i for i, s in enumerate(segments) if _is_flagged(s)]

    print("\n── Caption Review ──────────────────────────────────")
    print(f"Scanning {len(segments)} segments... {len(flagged_indices)} flagged for review.")

    reviewed = list(segments)

    to_delete = set()
    for i in flagged_indices:
        seg = reviewed[i]
        logprob = seg.get("avg_logprob", "n/a")
        start = seg["start"]
        end = seg["end"]
        text = seg["text"].strip()

        print(f"\n⚠  [{start:.1f}s → {end:.1f}s]  logprob={logprob:.2f}" if isinstance(logprob, float) else f"\n⚠  [{start:.1f}s → {end:.1f}s]  logprob={logprob}")
        print(f'   Whisper said: "{text}"')
        replacement = input("   Fix (Enter=keep, 'd'=delete, or type replacement): ").strip()

        if replacement == "d":
            to_delete.add(i)
            print("✓ Deleted.")
        elif replacement == "":
            print("✓ Kept.")
        else:
            reviewed[i] = dict(seg, text=f" {replacement}")
            print("✓ Fixed.")

    reviewed = [s for i, s in enumerate(reviewed) if i not in to_delete]

    print(f"\n── Review complete. {len(reviewed)} segments kept. ──")
    return reviewed


def run(folder):
    src = find_input_for_step(folder, STEP)
    out = output_path_for_step(src, STEP)

    if os.path.exists(out):
        print(f"⚠  Step '{STEP}' already applied to this file.")
        return

    src_name = os.path.basename(src)
    out_name = os.path.basename(out)
    print(f"[{STEP}] {src_name} → {out_name}")

    # Load Whisper model
    print(f"  Loading Whisper model '{WHISPER_MODEL}'...")
    try:
        model = whisper.load_model(WHISPER_MODEL)
    except Exception as exc:
        print(f"  Failed to load Whisper model. Check the WHISPER_MODEL constant ('{WHISPER_MODEL}').")
        raise

    # Transcribe
    print("  Transcribing (this may take a while)...")
    result = model.transcribe(src)
    segments = result["segments"]

    # Interactive review
    segments = review_segments_cli(segments)

    # Derive SRT path from output stem
    out_stem = os.path.splitext(out)[0]
    srt_path = f"{out_stem}.srt"

    _write_srt(segments, srt_path)
    print(f"  SRT written: {os.path.basename(srt_path)}")

    # Hard pause for final manual review
    input("Open the .srt for a final manual check, then press Enter to continue...\n")

    # Video passthrough — no re-encoding
    print("  Copying video (no re-encode)...")
    shutil.copy2(src, out)

    print(f"✓ Saved: {out_name}")
    ask_continue_chain(folder, STEP)


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print(f"Usage: python {sys.argv[0]} <folder>")
        sys.exit(1)
    run(sys.argv[1])
