from __future__ import annotations

import os
import queue
import re
import shutil
import subprocess
import threading
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

try:
    from tkinterdnd2 import DND_FILES, TkinterDnD
except ImportError:  # Drag and drop is optional at import time.
    DND_FILES = None
    TkinterDnD = None


APP_TITLE = "Subtitle Softcoder"
VIDEO_EXTENSIONS = {
    ".mp4",
    ".m4v",
    ".mov",
    ".mkv",
    ".avi",
    ".webm",
    ".wmv",
}
SUBTITLE_EXTENSIONS = {".srt", ".vtt", ".webvtt", ".ass", ".ssa"}
MP4_LIKE_EXTENSIONS = {".mp4", ".m4v", ".mov"}
MKV_SUBTITLE_CODECS = {
    ".srt": "srt",
    ".vtt": "webvtt",
    ".webvtt": "webvtt",
    ".ass": "ass",
    ".ssa": "ssa",
}
OUTPUT_DEFAULT_SUBTITLE_CODECS = {
    ".mp4": "mov_text",
    ".m4v": "mov_text",
    ".mov": "mov_text",
    ".mkv": "srt",
    ".webm": "webvtt",
}
OUTPUT_EXTENSIONS = set(OUTPUT_DEFAULT_SUBTITLE_CODECS)
SUBTITLE_FILETYPES = [
    ("Supported subtitle files", "*.srt *.vtt *.webvtt *.ass *.ssa"),
    ("SubRip files", "*.srt"),
    ("WebVTT files", "*.vtt *.webvtt"),
    ("ASS/SSA files", "*.ass *.ssa"),
    ("All files", "*.*"),
]
OUTPUT_FILETYPES = [
    ("Supported output files", "*.mp4 *.m4v *.mov *.mkv *.webm"),
    ("MP4 files", "*.mp4"),
    ("M4V files", "*.m4v"),
    ("MOV files", "*.mov"),
    ("Matroska files", "*.mkv"),
    ("WebM files", "*.webm"),
    ("All files", "*.*"),
]
MP4_OUTPUT_FILETYPES = [
    ("MP4 files", "*.mp4"),
    ("All files", "*.*"),
]
SUBTITLE_POSITIONS = ("First", "Last")


class SrtSoftcoderApp:
    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.root.title(APP_TITLE)
        self.root.geometry("760x560")
        self.root.minsize(680, 500)

        self.video_path = tk.StringVar()
        self.srt_path = tk.StringVar()
        self.output_path = tk.StringVar()
        self.language = tk.StringVar(value="eng")
        self.subtitle_position = tk.StringVar(value="Last")
        self.remove_existing_subtitles = tk.BooleanVar(value=False)
        self.output_as_mp4 = tk.BooleanVar(value=False)
        self.overwrite_output = tk.BooleanVar(value=False)
        self.status = tk.StringVar(value="Choose a video and subtitle file.")
        self._last_default_output = ""

        self.event_queue: queue.Queue[tuple[str, object]] = queue.Queue()
        self.worker: threading.Thread | None = None
        self.process: subprocess.Popen[str] | None = None

        self._build_ui()
        self._register_drop_targets()
        self.root.after(100, self._drain_event_queue)

    def _build_ui(self) -> None:
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=1)

        outer = ttk.Frame(self.root, padding=18)
        outer.grid(row=0, column=0, sticky="nsew")
        outer.columnconfigure(0, weight=1)
        outer.rowconfigure(2, weight=1)

        title = ttk.Label(outer, text=APP_TITLE, font=("Segoe UI", 18, "bold"))
        title.grid(row=0, column=0, sticky="w")

        subtitle = ttk.Label(
            outer,
            text="Add a subtitle file as a selectable track without re-encoding the video.",
        )
        subtitle.grid(row=1, column=0, sticky="w", pady=(4, 16))

        drop_frame = ttk.LabelFrame(outer, text="Files", padding=14)
        drop_frame.grid(row=2, column=0, sticky="nsew")
        drop_frame.columnconfigure(1, weight=1)

        ttk.Label(drop_frame, text="Video").grid(row=0, column=0, sticky="w", padx=(0, 10))
        video_entry = ttk.Entry(drop_frame, textvariable=self.video_path)
        video_entry.grid(row=0, column=1, sticky="ew")
        ttk.Button(drop_frame, text="Browse...", command=self.choose_video).grid(
            row=0, column=2, padx=(10, 0)
        )

        ttk.Label(drop_frame, text="Subtitle").grid(
            row=1, column=0, sticky="w", padx=(0, 10), pady=(10, 0)
        )
        srt_entry = ttk.Entry(drop_frame, textvariable=self.srt_path)
        srt_entry.grid(row=1, column=1, sticky="ew", pady=(10, 0))
        ttk.Button(drop_frame, text="Browse...", command=self.choose_srt).grid(
            row=1, column=2, padx=(10, 0), pady=(10, 0)
        )

        ttk.Label(drop_frame, text="Output").grid(
            row=2, column=0, sticky="w", padx=(0, 10), pady=(10, 0)
        )
        output_entry = ttk.Entry(drop_frame, textvariable=self.output_path)
        output_entry.grid(row=2, column=1, sticky="ew", pady=(10, 0))
        ttk.Button(drop_frame, text="Save As...", command=self.choose_output).grid(
            row=2, column=2, padx=(10, 0), pady=(10, 0)
        )

        options = ttk.Frame(drop_frame)
        options.grid(row=3, column=0, columnspan=3, sticky="ew", pady=(14, 0))
        options.columnconfigure(5, weight=1)

        ttk.Label(options, text="Subtitle language").grid(row=0, column=0, sticky="w")
        language_entry = ttk.Entry(options, width=8, textvariable=self.language)
        language_entry.grid(row=0, column=1, sticky="w", padx=(8, 24))
        ttk.Label(options, text="Insert subtitle").grid(
            row=0, column=2, sticky="w"
        )
        subtitle_position_menu = ttk.Combobox(
            options,
            width=8,
            state="readonly",
            textvariable=self.subtitle_position,
            values=SUBTITLE_POSITIONS,
        )
        subtitle_position_menu.grid(row=0, column=3, sticky="w", padx=(8, 24))
        ttk.Checkbutton(
            options,
            text="Output as MP4",
            variable=self.output_as_mp4,
            command=self._handle_output_format_change,
        ).grid(
            row=1, column=0, columnspan=2, sticky="w", pady=(8, 0)
        )
        ttk.Checkbutton(
            options,
            text="Remove existing subtitles",
            variable=self.remove_existing_subtitles,
        ).grid(
            row=1, column=2, columnspan=2, sticky="w", padx=(24, 0), pady=(8, 0)
        )
        ttk.Checkbutton(
            options,
            text="Overwrite existing output",
            variable=self.overwrite_output,
        ).grid(
            row=1, column=4, columnspan=2, sticky="w", padx=(24, 0), pady=(8, 0)
        )

        dnd_text = (
            "Drag video and subtitle files here"
            if TkinterDnD is not None
            else "Install tkinterdnd2 to enable drag and drop"
        )
        self.drop_label = ttk.Label(
            drop_frame,
            text=dnd_text,
            anchor="center",
            relief="groove",
            padding=24,
        )
        self.drop_label.grid(row=4, column=0, columnspan=3, sticky="nsew", pady=(16, 0))
        drop_frame.rowconfigure(4, weight=1)

        command_frame = ttk.Frame(outer)
        command_frame.grid(row=3, column=0, sticky="ew", pady=(16, 0))
        command_frame.columnconfigure(0, weight=1)

        self.progress = ttk.Progressbar(command_frame, mode="determinate", maximum=100)
        self.progress.grid(row=0, column=0, sticky="ew", padx=(0, 12))
        self.start_button = ttk.Button(command_frame, text="Softcode Subtitles", command=self.start_softcode)
        self.start_button.grid(row=0, column=1)
        self.cancel_button = ttk.Button(command_frame, text="Cancel", command=self.cancel_softcode, state="disabled")
        self.cancel_button.grid(row=0, column=2, padx=(8, 0))

        status_label = ttk.Label(outer, textvariable=self.status)
        status_label.grid(row=4, column=0, sticky="w", pady=(10, 0))

        log_frame = ttk.LabelFrame(outer, text="FFmpeg Output", padding=8)
        log_frame.grid(row=5, column=0, sticky="nsew", pady=(14, 0))
        log_frame.columnconfigure(0, weight=1)
        log_frame.rowconfigure(0, weight=1)
        outer.rowconfigure(5, weight=2)

        self.log = tk.Text(log_frame, height=8, wrap="word", state="disabled")
        self.log.grid(row=0, column=0, sticky="nsew")
        scrollbar = ttk.Scrollbar(log_frame, command=self.log.yview)
        scrollbar.grid(row=0, column=1, sticky="ns")
        self.log.configure(yscrollcommand=scrollbar.set)

        self.video_path.trace_add("write", lambda *_: self._maybe_set_default_output())

    def _register_drop_targets(self) -> None:
        if TkinterDnD is None or DND_FILES is None:
            return

        for widget in (self.root, self.drop_label):
            widget.drop_target_register(DND_FILES)
            widget.dnd_bind("<<Drop>>", self.handle_drop)

    def choose_video(self) -> None:
        path = filedialog.askopenfilename(
            title="Choose video file",
            filetypes=[
                ("Video files", "*.mp4 *.m4v *.mov *.mkv *.avi *.webm *.wmv"),
                ("All files", "*.*"),
            ],
        )
        if path:
            self.video_path.set(path)

    def choose_srt(self) -> None:
        path = filedialog.askopenfilename(
            title="Choose subtitle file",
            filetypes=SUBTITLE_FILETYPES,
        )
        if path:
            self.srt_path.set(path)

    def choose_output(self) -> None:
        initial = self.output_path.get() or self._default_output_path()
        initial_path = Path(initial) if initial else None
        if self.output_as_mp4.get():
            defaultextension = ".mp4"
        elif initial_path:
            defaultextension = initial_path.suffix
        else:
            defaultextension = ".mp4"
        filetypes = MP4_OUTPUT_FILETYPES if self.output_as_mp4.get() else OUTPUT_FILETYPES
        path = filedialog.asksaveasfilename(
            title="Choose output video",
            defaultextension=defaultextension,
            filetypes=filetypes,
            initialdir=str(initial_path.parent) if initial_path else None,
            initialfile=initial_path.name if initial_path else None,
        )
        if path:
            output = Path(path)
            if self.output_as_mp4.get():
                output = output.with_suffix(".mp4")
            self.output_path.set(str(output))

    def handle_drop(self, event: object) -> None:
        raw_data = getattr(event, "data", "")
        paths = [Path(item) for item in self.root.tk.splitlist(raw_data)]
        found_video = False
        found_srt = False

        for path in paths:
            suffix = path.suffix.lower()
            if suffix in VIDEO_EXTENSIONS and not found_video:
                self.video_path.set(str(path))
                found_video = True
            elif suffix in SUBTITLE_EXTENSIONS and not found_srt:
                self.srt_path.set(str(path))
                found_srt = True

        if not paths:
            self.status.set("No files were dropped.")
        elif not (found_video or found_srt):
            self.status.set("Drop a video file and a supported subtitle file.")
        else:
            self.status.set("Dropped files added.")

    def start_softcode(self) -> None:
        try:
            video, srt, output = self._validate_inputs()
        except ValueError as exc:
            messagebox.showerror(APP_TITLE, str(exc))
            return

        ffmpeg_path = shutil.which("ffmpeg")
        ffprobe_path = shutil.which("ffprobe")
        if not ffmpeg_path:
            messagebox.showerror(APP_TITLE, "FFmpeg was not found on PATH.")
            return
        if not ffprobe_path:
            messagebox.showerror(APP_TITLE, "FFprobe was not found on PATH.")
            return

        self.progress["value"] = 0
        self._clear_log()
        self._set_running(True)
        self.status.set("Reading video duration...")

        self.worker = threading.Thread(
            target=self._run_ffmpeg,
            args=(ffmpeg_path, ffprobe_path, video, srt, output),
            daemon=True,
        )
        self.worker.start()

    def cancel_softcode(self) -> None:
        if self.process and self.process.poll() is None:
            self.process.terminate()
            self.status.set("Cancelling...")

    def _validate_inputs(self) -> tuple[Path, Path, Path]:
        video = Path(self.video_path.get().strip())
        srt = Path(self.srt_path.get().strip())
        output = Path(self.output_path.get().strip() or self._default_output_path())
        if self.output_as_mp4.get():
            output = output.with_suffix(".mp4")
            self.output_path.set(str(output))

        if not video.is_file():
            raise ValueError("Choose a valid video file.")
        if not srt.is_file():
            raise ValueError("Choose a valid subtitle file.")
        if srt.suffix.lower() not in SUBTITLE_EXTENSIONS:
            supported = ", ".join(sorted(SUBTITLE_EXTENSIONS))
            raise ValueError(f"The subtitle file must end with one of: {supported}.")
        if output.suffix.lower() not in OUTPUT_EXTENSIONS:
            supported = ", ".join(sorted(OUTPUT_EXTENSIONS))
            raise ValueError(f"The output file must end with one of: {supported}.")
        if video.resolve() == output.resolve():
            raise ValueError("The output file must be different from the input video.")
        if output.exists() and not self.overwrite_output.get():
            raise ValueError("The output file already exists. Choose another file or enable overwrite.")

        output.parent.mkdir(parents=True, exist_ok=True)
        return video, srt, output

    def _run_ffmpeg(
        self,
        ffmpeg_path: str,
        ffprobe_path: str,
        video: Path,
        srt: Path,
        output: Path,
    ) -> None:
        duration = self._probe_duration(ffprobe_path, video)
        if duration <= 0:
            self.event_queue.put(("status", "Could not read duration; running without progress estimate."))

        preserve_existing_subtitles = not self.remove_existing_subtitles.get()
        existing_subtitle_count = (
            self._probe_subtitle_count(ffprobe_path, video) if preserve_existing_subtitles else 0
        )
        insert_subtitle_first = self.subtitle_position.get() == "First"
        new_subtitle_index = 0 if insert_subtitle_first else existing_subtitle_count
        output_suffix = output.suffix.lower()
        subtitle_suffix = srt.suffix.lower()
        command = [
            ffmpeg_path,
            "-y" if self.overwrite_output.get() else "-n",
            "-i",
            str(video),
            "-i",
            str(srt),
            "-map",
            "0:v?",
            "-map",
            "0:a?",
        ]
        if insert_subtitle_first:
            command.extend(["-map", "1:0"])
            if preserve_existing_subtitles:
                command.extend(["-map", "0:s?"])
        else:
            if preserve_existing_subtitles:
                command.extend(["-map", "0:s?"])
            command.extend(["-map", "1:0"])
        command.extend(
            [
                "-map_metadata",
                "0",
                "-map_chapters",
                "0",
                "-c:v",
                "copy",
                "-c:a",
                "copy",
                "-c:s",
                "copy",
                f"-c:s:{new_subtitle_index}",
                self._subtitle_codec(output_suffix, subtitle_suffix),
                f"-metadata:s:s:{new_subtitle_index}",
                f"language={self.language.get().strip() or 'und'}",
            ]
        )
        if output_suffix in MP4_LIKE_EXTENSIONS:
            command.extend(["-movflags", "+faststart"])
        command.extend(["-progress", "pipe:1", "-nostats", str(output)])

        self.event_queue.put(("log", self._format_command(command)))
        self.event_queue.put(("status", "Softcoding subtitles..."))

        startupinfo = None
        if os.name == "nt":
            startupinfo = subprocess.STARTUPINFO()
            startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW

        try:
            self.process = subprocess.Popen(
                command,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                encoding="utf-8",
                errors="replace",
                startupinfo=startupinfo,
            )
            assert self.process.stdout is not None
            for line in self.process.stdout:
                self._handle_ffmpeg_line(line.rstrip(), duration)

            return_code = self.process.wait()
        except OSError as exc:
            self.event_queue.put(("error", f"Could not start FFmpeg: {exc}"))
            return
        finally:
            self.process = None

        if return_code == 0:
            self.event_queue.put(("progress", 100.0))
            self.event_queue.put(("done", output))
        elif return_code < 0:
            self.event_queue.put(("error", "The FFmpeg job was cancelled."))
        else:
            self.event_queue.put(("error", "FFmpeg could not create the output file. Check the log for details."))

    def _probe_duration(self, ffprobe_path: str, video: Path) -> float:
        command = [
            ffprobe_path,
            "-v",
            "error",
            "-show_entries",
            "format=duration",
            "-of",
            "default=noprint_wrappers=1:nokey=1",
            str(video),
        ]
        try:
            result = subprocess.run(
                command,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                check=False,
                startupinfo=self._hidden_startupinfo(),
            )
            return float(result.stdout.strip())
        except (OSError, ValueError):
            return 0.0

    def _probe_subtitle_count(self, ffprobe_path: str, video: Path) -> int:
        command = [
            ffprobe_path,
            "-v",
            "error",
            "-select_streams",
            "s",
            "-show_entries",
            "stream=index",
            "-of",
            "csv=p=0",
            str(video),
        ]
        try:
            result = subprocess.run(
                command,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                check=False,
                startupinfo=self._hidden_startupinfo(),
            )
        except OSError:
            return 0
        if result.returncode != 0:
            return 0
        return len([line for line in result.stdout.splitlines() if line.strip()])

    def _hidden_startupinfo(self) -> subprocess.STARTUPINFO | None:
        if os.name != "nt":
            return None
        startupinfo = subprocess.STARTUPINFO()
        startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        return startupinfo

    def _handle_ffmpeg_line(self, line: str, duration: float) -> None:
        if not line:
            return

        self.event_queue.put(("log", line))
        match = re.match(r"out_time_ms=(\d+)", line)
        if match and duration > 0:
            elapsed_seconds = int(match.group(1)) / 1_000_000
            progress = max(0.0, min(100.0, elapsed_seconds / duration * 100))
            self.event_queue.put(("progress", progress))
        elif line == "progress=end":
            self.event_queue.put(("progress", 100.0))

    def _drain_event_queue(self) -> None:
        try:
            while True:
                event, payload = self.event_queue.get_nowait()
                if event == "log":
                    self._append_log(str(payload))
                elif event == "progress":
                    self.progress["value"] = float(payload)
                elif event == "status":
                    self.status.set(str(payload))
                elif event == "done":
                    self._set_running(False)
                    self.status.set(f"Done: {payload}")
                    messagebox.showinfo(APP_TITLE, f"Created:\n{payload}")
                elif event == "error":
                    self._set_running(False)
                    self.status.set(str(payload))
                    messagebox.showerror(APP_TITLE, str(payload))
        except queue.Empty:
            pass
        finally:
            self.root.after(100, self._drain_event_queue)

    def _set_running(self, running: bool) -> None:
        self.start_button.configure(state="disabled" if running else "normal")
        self.cancel_button.configure(state="normal" if running else "disabled")

    def _append_log(self, text: str) -> None:
        self.log.configure(state="normal")
        self.log.insert("end", text + "\n")
        self.log.see("end")
        self.log.configure(state="disabled")

    def _clear_log(self) -> None:
        self.log.configure(state="normal")
        self.log.delete("1.0", "end")
        self.log.configure(state="disabled")

    def _default_output_path(self) -> str:
        video = self.video_path.get().strip()
        if not video:
            return ""
        path = Path(video)
        output_suffix = self._default_output_suffix(path.suffix.lower())
        return str(path.with_name(f"{path.stem}_softcoded{output_suffix}"))

    def _default_output_suffix(self, video_suffix: str) -> str:
        if self.output_as_mp4.get():
            return ".mp4"
        return self._default_output_suffix_for_video(video_suffix)

    def _default_output_suffix_for_video(self, video_suffix: str) -> str:
        if video_suffix in OUTPUT_EXTENSIONS:
            return video_suffix
        return ".mp4"

    def _subtitle_codec(self, output_suffix: str, subtitle_suffix: str) -> str:
        if output_suffix == ".mkv":
            return MKV_SUBTITLE_CODECS.get(subtitle_suffix, "srt")
        return OUTPUT_DEFAULT_SUBTITLE_CODECS[output_suffix]

    def _maybe_set_default_output(self) -> None:
        current = self.output_path.get().strip()
        default = self._default_output_path()
        if default and (
            not current
            or self._normalize_path(Path(current))
            == self._normalize_path(Path(self._last_default_output))
        ):
            self.output_path.set(default)
        self._last_default_output = default

    def _handle_output_format_change(self) -> None:
        current = self.output_path.get().strip()
        default = self._default_output_path()
        if default and (
            not current
            or self._normalize_path(Path(current))
            == self._normalize_path(Path(self._last_default_output))
        ):
            self.output_path.set(default)
        self._last_default_output = default

    def _normalize_path(self, path: Path) -> str:
        return os.path.normcase(os.path.abspath(path))

    def _format_command(self, command: list[str]) -> str:
        return " ".join(f'"{part}"' if " " in part else part for part in command)


def main() -> None:
    if TkinterDnD is not None:
        root = TkinterDnD.Tk()
    else:
        root = tk.Tk()

    try:
        root.call("tk", "scaling", 1.2)
    except tk.TclError:
        pass

    SrtSoftcoderApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
