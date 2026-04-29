import sys
import os
import shutil

import ffmpeg
import numpy as np
import soundfile as sf
import whisper

from pipeline_utils import find_input_for_step, output_path_for_step, ask_continue_chain, FFMPEG_CMD

# ── CONFIG ────────────────────────────────────────────────────────────────────
STEP                     = "transcribed"
WHISPER_MODEL            = "large"   # tiny | base | small | medium | large
LOW_CONFIDENCE_THRESHOLD = -0.6       # avg_logprob below this is flagged for review
MAX_CAPTION_WORDS        = 7          # split segments longer than this into shorter chunks
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


def _split_segments(segments):
    """Break any segment longer than MAX_CAPTION_WORDS into shorter chunks.
    Timestamps are distributed proportionally by word count."""
    result = []
    for seg in segments:
        words = seg["text"].strip().split()
        if len(words) <= MAX_CAPTION_WORDS:
            result.append(seg)
            continue

        duration = seg["end"] - seg["start"]
        total_words = len(words)
        chunks = [words[i:i + MAX_CAPTION_WORDS] for i in range(0, total_words, MAX_CAPTION_WORDS)]

        chunk_start = seg["start"]
        for chunk in chunks:
            chunk_dur = duration * len(chunk) / total_words
            chunk_end = chunk_start + chunk_dur
            result.append({**seg, "text": " " + " ".join(chunk), "start": chunk_start, "end": chunk_end})
            chunk_start = chunk_end

    return result


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

    # Extract audio to temp WAV so Whisper never needs to call ffmpeg itself
    stem = os.path.splitext(os.path.basename(src))[0]
    tmp_wav = os.path.join(folder, f"{stem}_tmpwhisper.wav")
    try:
        print("  Extracting audio for Whisper...")
        (
            ffmpeg
            .input(src)
            .output(tmp_wav, ac=1, ar=16000, format="wav")
            .overwrite_output()
            .run(quiet=True, cmd=FFMPEG_CMD)
        )
        audio_data, _ = sf.read(tmp_wav, dtype="float32")
    finally:
        if os.path.exists(tmp_wav):
            os.remove(tmp_wav)

    # Transcribe — pass numpy array directly so Whisper skips its internal ffmpeg call
    print("  Transcribing (this may take a while)...")
    result = model.transcribe(audio_data)
    segments = result["segments"]

    # Interactive review
    segments = review_segments_cli(segments)

    # Break long captions into shorter chunks for phone-friendly display
    segments_before = len(segments)
    segments = _split_segments(segments)
    if len(segments) != segments_before:
        print(f"  Split into {len(segments)} captions (was {segments_before}, max {MAX_CAPTION_WORDS} words each).")

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
    from pipeline_utils import DEFAULT_FOLDER
    folder = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_FOLDER
    run(folder)
