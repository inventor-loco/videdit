import sys
import os
import tempfile

import ffmpeg
import soundfile as sf
import noisereduce as nr
import pyloudnorm as pyln

from pipeline_utils import find_input_for_step, output_path_for_step, ask_continue_chain

# ── CONFIG ────────────────────────────────────────────────────────────────────
STEP = "enhanced"
TARGET_LUFS = -14           # ITU-R BS.1770 / YouTube standard
NOISE_SAMPLE_DURATION_S = 0.5  # seconds taken from the start as the noise profile
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
    tmp_raw = os.path.join(folder, f"{stem}_tmpraw.wav")
    tmp_enhanced = os.path.join(folder, f"{stem}_tmpenhanced.wav")

    try:
        # 1. Extract mono 16 kHz audio
        print("  Extracting audio...")
        (
            ffmpeg
            .input(src)
            .output(tmp_raw, ac=1, ar=16000, format="wav")
            .overwrite_output()
            .run(quiet=True)
        )

        # 2. Read WAV
        data, rate = sf.read(tmp_raw)

        # 3. Build noise profile from the first NOISE_SAMPLE_DURATION_S seconds
        noise_samples = int(NOISE_SAMPLE_DURATION_S * rate)
        noise_profile = data[:noise_samples]

        # 4. Denoise
        print("  Denoising...")
        denoised = nr.reduce_noise(y=data, sr=rate, y_noise=noise_profile)

        # 5. Loudness normalisation
        print("  Normalising loudness...")
        meter = pyln.Meter(rate)
        try:
            loudness = meter.integrated_loudness(denoised)
            normalized = pyln.normalize.loudness(denoised, loudness, TARGET_LUFS)
        except Exception as exc:
            print(f"  ⚠  Loudness normalisation skipped ({exc}); using denoised audio only.")
            normalized = denoised

        # 6. Write enhanced WAV
        sf.write(tmp_enhanced, normalized, rate)

        # 7. Remux: copy video + replace audio
        print("  Remuxing...")
        video_in = ffmpeg.input(src)
        audio_in = ffmpeg.input(tmp_enhanced)
        (
            ffmpeg
            .output(
                video_in.video,
                audio_in.audio,
                out,
                vcodec="copy",
                acodec="aac",
            )
            .overwrite_output()
            .run(quiet=True)
        )

    except ffmpeg.Error as exc:
        print(f"  ffmpeg error:\n{exc.stderr.decode() if exc.stderr else exc}")
        raise
    finally:
        for tmp in (tmp_raw, tmp_enhanced):
            if os.path.exists(tmp):
                os.remove(tmp)

    print(f"✓ Saved: {out_name}")
    ask_continue_chain(folder, STEP)


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print(f"Usage: python {sys.argv[0]} <folder>")
        sys.exit(1)
    run(sys.argv[1])
