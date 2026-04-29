# Video Processing Pipeline

A modular, step-based Python pipeline for processing video files. Each step is an independent, re-runnable script. Intermediate files are preserved at every stage using a naming convention that tracks applied steps.

---

## Installation

### 1. System dependency

`ffmpeg` must be installed and available on your `$PATH`.

```bash
# macOS
brew install ffmpeg

# Ubuntu / Debian
sudo apt install ffmpeg
```

### 2. Python packages

```bash
pip install -r requirements.txt
```

---

## Folder Setup

Create a project folder for each video, place the raw source file inside it, and add an `assets/` subdirectory for optional intro, outro, and logo files:

```
videos/lecture01/
├── lecture01.mp4          ← raw input (never modified)
└── assets/
    ├── intro.mp4          ← optional: prepended by step_concat
    ├── outro.mp4          ← optional: appended by step_concat
    └── logo.png           ← required by step_watermarked
```

---

## Running Steps

Each step is invoked with the project folder as its only argument:

```bash
python step_enhanced.py    ./videos/lecture01/
python step_silenced.py    ./videos/lecture01/
python step_transcribed.py ./videos/lecture01/
python step_captioned.py   ./videos/lecture01/
python step_concat.py      ./videos/lecture01/
python step_watermarked.py ./videos/lecture01/
```

After each step completes you will be asked whether to continue to the next step immediately or stop and resume later.

### Example file progression

```
lecture01.mp4
lecture01_enhanced.mp4
lecture01_enhanced_silenced.mp4
lecture01_enhanced_silenced_transcribed.mp4  +  .srt
lecture01_enhanced_silenced_transcribed_captioned.mp4
lecture01_enhanced_silenced_transcribed_captioned_concat.mp4
lecture01_enhanced_silenced_transcribed_captioned_concat_watermarked.mp4
```

---

## Re-running a Step

Simply run the script again — it automatically finds the correct input file by scanning for the file whose last applied step is the one immediately before the step you are running. If the output already exists, the script warns and exits without overwriting anything.

---

## Skipping Re-processing

Intermediate files are preserved between runs. If an output file already exists the script prints:

```
⚠  Step 'enhanced' already applied to this file.
```

and exits cleanly. Delete the output file manually if you need to re-process.

---

## Step Reference

| # | Script                | Step tag      | What it does                                         |
|---|----------------------|---------------|------------------------------------------------------|
| 1 | `step_enhanced.py`   | `enhanced`    | Denoise audio + loudness-normalize to −14 LUFS       |
| 2 | `step_silenced.py`   | `silenced`    | Remove long silences (≥ 700 ms by default)           |
| 3 | `step_transcribed.py`| `transcribed` | Whisper transcription → `.srt`, with CLI review gate |
| 4 | `step_captioned.py`  | `captioned`   | Burn `.srt` hard subtitles into the video            |
| 5 | `step_concat.py`     | `concat`      | Prepend intro and/or append outro clip               |
| 6 | `step_watermarked.py`| `watermarked` | Overlay semi-transparent logo at bottom-right        |

---

## Adding a New Step

1. Add the step's short name to the `STEPS` list in `steps.py` at the correct position.
2. Create `step_<name>.py` following the pattern of any existing step:
   - Define `STEP = "<name>"` and a `CONFIG` block.
   - Implement `run(folder)` using `find_input_for_step`, `output_path_for_step`, and `ask_continue_chain` from `pipeline_utils`.
   - Add an `if __name__ == "__main__":` entry point.
3. Add any new dependencies to `requirements.txt`.

> **Warning:** Inserting a step in the middle of `STEPS` changes the expected input/output chain for all subsequent steps. Existing intermediate files will no longer match the new chain order, so you will need to re-run affected steps.
