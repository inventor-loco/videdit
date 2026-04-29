import sys
import os

from moviepy import VideoFileClip, concatenate_videoclips

from pipeline_utils import find_input_for_step, output_path_for_step, ask_continue_chain

# ── CONFIG ────────────────────────────────────────────────────────────────────
STEP           = "concat"
INTRO_FILENAME = "assets/intro.mp4"   # relative to folder
OUTRO_FILENAME = "assets/outro.mp4"   # relative to folder
# ─────────────────────────────────────────────────────────────────────────────


def _resize_to_match(clip, path, target_w, target_h, target_fps):
    """Resize clip to target dimensions and set fps if they differ."""
    resized = clip
    if clip.size != (target_w, target_h):
        print(f"  ⚠  Resolution mismatch: {path} is {clip.size}, resizing to ({target_w}, {target_h})")
        resized = resized.resized((target_w, target_h))
    if clip.fps != target_fps:
        print(f"  ⚠  FPS mismatch: {path} is {clip.fps} fps, adjusting to {target_fps} fps")
        resized = resized.with_fps(target_fps)
    return resized


def run(folder):
    src = find_input_for_step(folder, STEP)
    out = output_path_for_step(src, STEP)

    if os.path.exists(out):
        print(f"⚠  Step '{STEP}' already applied to this file.")
        return

    src_name = os.path.basename(src)
    out_name = os.path.basename(out)
    print(f"[{STEP}] {src_name} → {out_name}")

    intro_path = os.path.join(folder, INTRO_FILENAME)
    outro_path = os.path.join(folder, OUTRO_FILENAME)

    main_clip = VideoFileClip(src)
    target_w, target_h = main_clip.size
    target_fps = main_clip.fps

    clips = []

    if os.path.exists(intro_path):
        print(f"  Using intro: {INTRO_FILENAME}")
        intro = VideoFileClip(intro_path)
        intro = _resize_to_match(intro, intro_path, target_w, target_h, target_fps)
        clips.append(intro)
    else:
        print(f"  Intro not found at '{intro_path}' — skipping.")

    clips.append(main_clip)

    if os.path.exists(outro_path):
        print(f"  Using outro: {OUTRO_FILENAME}")
        outro = VideoFileClip(outro_path)
        outro = _resize_to_match(outro, outro_path, target_w, target_h, target_fps)
        clips.append(outro)
    else:
        print(f"  Outro not found at '{outro_path}' — skipping.")

    print(f"  Concatenating {len(clips)} clip(s)...")
    final = concatenate_videoclips(clips, method="compose")
    final.write_videofile(out, logger=None)

    for c in clips:
        c.close()
    final.close()

    print(f"✓ Saved: {out_name}")
    ask_continue_chain(folder, STEP)


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print(f"Usage: python {sys.argv[0]} <folder>")
        sys.exit(1)
    run(sys.argv[1])
