import os
import shutil
import importlib
from steps import STEPS

# ── CONFIG ────────────────────────────────────────────────────────────────────
# Set this to your videos folder. Used by all steps when called with no argument.
# Windows example:  r"C:\Users\YourName\Videos\my_project"
# Mac/Linux example: "/home/yourname/videos/my_project"
DEFAULT_FOLDER = r"C:\Users\YourName\Videos\my_project"
# ─────────────────────────────────────────────────────────────────────────────


def _resolve_ffmpeg():
    """Return the ffmpeg binary to use — system install if on PATH, else the
    one bundled with imageio_ffmpeg (installed as a moviepy dependency)."""
    if shutil.which("ffmpeg"):
        return "ffmpeg"
    try:
        import imageio_ffmpeg
        return imageio_ffmpeg.get_ffmpeg_exe()
    except ImportError:
        raise RuntimeError(
            "ffmpeg not found. Install it from https://ffmpeg.org/download.html "
            "and add it to your system PATH, or install imageio_ffmpeg."
        )

FFMPEG_CMD = _resolve_ffmpeg()


def _parse_chain(stem):
    """Return (base, [applied_steps]) by splitting stem on '_' and recognising STEPS tokens."""
    parts = stem.split("_")
    applied = []
    # parts[0] is always the base name; scan the rest for known step tokens
    for part in parts[1:]:
        if part in STEPS:
            applied.append(part)
    base = parts[0]
    return base, applied


def find_input_for_step(folder, step_name):
    """Return the path of the best candidate .mp4 to feed into step_name.

    Selection rules:
    1. File must not already contain step_name in its applied chain.
    2. For step index 0: raw file (no applied steps).
       For step index N>0: last applied step must be STEPS[N-1].
    3. Among multiple candidates, prefer the one with the longest chain.
    """
    step_idx = STEPS.index(step_name)
    required_prev = STEPS[step_idx - 1] if step_idx > 0 else None

    candidates = []
    for fname in os.listdir(folder):
        if not fname.lower().endswith(".mp4"):
            continue
        # Skip anything inside assets/
        full = os.path.join(folder, fname)
        if os.path.isdir(full):
            continue

        stem = os.path.splitext(fname)[0]
        _, applied = _parse_chain(stem)

        if step_name in applied:
            continue

        if required_prev is None:
            # First step: accept files with no applied steps
            if len(applied) == 0:
                candidates.append((len(applied), full))
        else:
            # Subsequent step: last applied step must be the immediately preceding one
            if applied and applied[-1] == required_prev:
                candidates.append((len(applied), full))

    if not candidates:
        if required_prev is None:
            raise FileNotFoundError(
                f"No raw (unprocessed) .mp4 found in '{folder}' for step '{step_name}'."
            )
        raise FileNotFoundError(
            f"No .mp4 ending in '_{required_prev}' found in '{folder}' "
            f"as input for step '{step_name}'. "
            f"Make sure step '{required_prev}' has been run first."
        )

    # Prefer longest chain (most processing applied)
    candidates.sort(key=lambda x: x[0], reverse=True)
    return candidates[0][1]


def output_path_for_step(input_path, step_name):
    """Append _<step_name> to the stem of input_path, preserving folder and .mp4 extension."""
    folder = os.path.dirname(input_path)
    stem = os.path.splitext(os.path.basename(input_path))[0]
    return os.path.join(folder, f"{stem}_{step_name}.mp4")


def ask_continue_chain(folder, current_step):
    """Offer to run the next step immediately after the current one completes."""
    current_idx = STEPS.index(current_step)
    remaining = STEPS[current_idx + 1:]

    if not remaining:
        print("✅ All steps complete.")
        return

    print(f"\nRemaining steps: {', '.join(remaining)}")
    answer = input("Continue to next step now? [y/N]: ").strip().lower()

    if answer == "y":
        next_step = remaining[0]
        module_name = f"step_{next_step}"
        try:
            mod = importlib.import_module(module_name)
        except ImportError as exc:
            print(f"Could not import '{module_name}': {exc}")
            return
        mod.run(folder)
    else:
        print("⏸  Stopped. Re-run the next step script when ready.")
