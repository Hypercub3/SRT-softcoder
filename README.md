# Subtitle Softcoder

A Python GUI for adding a text subtitle file to a video as a selectable soft subtitle track.

## Features

- Adds subtitles without re-encoding the video or audio streams
- Supports SRT, WebVTT, ASS, and SSA subtitle files
- Preserves existing subtitle tracks unless you choose to remove them
- Keeps compatible source containers or optionally creates MP4 output
- Supports drag and drop when `tkinterdnd2` is installed
- Shows FFmpeg progress and output inside the app

The app uses FFmpeg and copies the existing video and audio streams without re-encoding them. When the input container supports soft text subtitles, the default output keeps the same container. AVI and WMV inputs fall back to MP4 output because those containers are less reliable for soft subtitle muxing.

## Requirements

- Python 3.10 or newer
- FFmpeg and FFprobe available on `PATH`
- `tkinterdnd2` for drag-and-drop support

Check that Python and FFmpeg are available:

```powershell
python --version
ffmpeg -version
ffprobe -version
```

## Installation

Clone the repository, open a terminal in its folder, and optionally create a virtual environment:

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```

On macOS or Linux, activate the environment with:

```bash
source .venv/bin/activate
python -m pip install -r requirements.txt
```

FFmpeg is a separate system dependency and is not installed by `requirements.txt`.

## Running the app

Run the app:

```powershell
python srt_softcoder.py
```

## Usage

1. Choose or drag in a video file.
2. Choose or drag in a supported subtitle file.
3. Confirm the output path.
4. Check **Output as MP4** to create an `.mp4` output instead of keeping the input format.
5. Leave **Remove existing subtitles** unchecked to preserve subtitle tracks that are already in the video, or check it to drop them.
6. Click **Softcode Subtitles**.

Supported input video files:

```text
.mp4, .m4v, .mov, .mkv, .avi, .webm, .wmv
```

Supported subtitle files:

```text
.srt, .vtt, .webvtt, .ass, .ssa
```

Supported output files:

```text
.mp4, .m4v, .mov, .mkv, .webm
```

The app uses this stream strategy:

```text
-map 0:v? -map 0:a? -map 0:s? -map 1:0 -c:v copy -c:a copy -c:s copy
```

When **Remove existing subtitles** is checked, the `-map 0:s?` step is skipped.

The newly added subtitle track uses a codec that depends on the output container:

```text
.mp4, .m4v, .mov -> mov_text
.mkv             -> srt, webvtt, ass, or ssa, matching the input subtitle format
.webm            -> webvtt
```

That keeps the original video and audio streams intact while adding the new subtitle track as the last selectable subtitle. Existing subtitle tracks from the source video are copied before the newly added subtitle track by default. Converting styled ASS/SSA subtitles to MP4 or WebM can lose styling because those containers use simpler text subtitle formats, and some existing subtitle formats may not be compatible with every output container.
