import sys
import os

from moviepy import VideoFileClip, ImageClip, CompositeVideoClip

from pipeline_utils import find_input_for_step, output_path_for_step, ask_continue_chain

# ── CONFIG ────────────────────────────────────────────────────────────────────
STEP                = "watermarked"
WATERMARK_FILENAME  = "assets/logo.png"
WATERMARK_HEIGHT_PX = 50
WATERMARK_OPACITY   = 0.6
WATERMARK_MARGIN_PX = 15
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

    watermark_path = os.path.join(folder, WATERMARK_FILENAME)
    if not os.path.exists(watermark_path):
        raise FileNotFoundError(
            f"Watermark image not found: '{watermark_path}'. "
            f"Place '{WATERMARK_FILENAME}' in the project folder."
        )

    print(f"  Loading video and watermark...")
    clip = VideoFileClip(src)

    logo = (
        ImageClip(watermark_path)
        .with_duration(clip.duration)
        .resized(height=WATERMARK_HEIGHT_PX)
        .with_opacity(WATERMARK_OPACITY)
    )
    pos_x = clip.w - logo.w - WATERMARK_MARGIN_PX
    pos_y = clip.h - logo.h - WATERMARK_MARGIN_PX
    logo = logo.with_position((pos_x, pos_y))

    print("  Compositing watermark...")
    composite = CompositeVideoClip([clip, logo])
    composite.write_videofile(out, logger=None)

    clip.close()
    composite.close()

    print(f"✓ Saved: {out_name}")
    ask_continue_chain(folder, STEP)


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print(f"Usage: python {sys.argv[0]} <folder>")
        sys.exit(1)
    run(sys.argv[1])
