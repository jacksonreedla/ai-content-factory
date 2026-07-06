# Phase 3 — Media Generation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans.

**Goal:** Build the media spine: TTS voice generation, subtitle generation (faster-whisper word timings + ASS styler), the ffmpeg video editor, and the video library — so a script can be turned into a rendered video file on disk (no approval UI yet).

**Architecture:** Each media capability is a plugin contract (`VoiceEngine`, `CaptionStyler`, `VideoEditor`, `MusicTrack`) with a built-in implementation. Agents (`VoiceAgent`, `SubtitleAgent`, `EditorAgent`) wrap the contracts and persist artifacts. ffmpeg is invoked via subprocess (v8-safe filter graphs). External tool/model availability is detected lazily; tests use fakes and skip on missing tools.

**Tech Stack:** ffmpeg/ffprobe (system), faster-whisper (pip), piper-tts (optional), Pillow (thumbnails later), numpy (waveform peaks if needed).

## Global Constraints

- No network in unit tests; fakes for all contracts.
- ffmpeg/whisper/piper integration tests are marked `@needs_ffmpeg` / `@needs_whisper` / `@needs_piper` and skip gracefully.
- ffmpeg invoked as subprocess; always pass explicit `-y`, never assume version <8.
- Per-job artifacts under `~/.aicf/jobs/<job_id>/`.
- Same layering rule: agents never import subprocess/whisper directly.

---

## File Structure

| File | Responsibility |
|------|----------------|
| `plugins/voice/__init__.py` | package marker |
| `plugins/voice/base.py` | `VoiceOpts` dataclass + `AudioClip` |
| `plugins/voice/piper/__init__.py` | package marker |
| `plugins/voice/piper/engine.py` | `PiperVoiceEngine` (subprocess) |
| `plugins/captions/__init__.py` | package marker |
| `plugins/captions/word_timing.py` | `WordTiming` dataclass |
| `plugins/captions/ass_styler.py` | `ASSStyler` — builds .ass from word timings |
| `infra/whisper/transcribe.py` | faster-whisper wrapper → word timings |
| `infra/ffmpeg/probe.py` | ffprobe duration/resolution |
| `infra/ffmpeg/run.py` | subprocess wrapper + filter_complex helpers |
| `plugins/editor/__init__.py` | package marker |
| `plugins/editor/ffmpeg_editor.py` | `FFmpegEditor(VideoEditor)` |
| `plugins/music/__init__.py` | package marker |
| `plugins/music/ducker.py` | `MusicDucker(MusicTrack)` — loop + duck under narration |
| `infra/storage.py` | job dir helpers (`job_dir(paths, job_id)`) |
| `agents/voice_agent.py` | VOICE stage |
| `agents/subtitle_agent.py` | SUBTITLE stage |
| `agents/editor_agent.py` | EDIT stage |
| `infra/db/repositories.py` | extend: voice_clips/subtitles/videos inserts |

---

### Task 1: storage + repos extension

- Add `infra/storage.py`:
```python
def job_dir(paths, job_id: int) -> Path:
    d = paths.jobs_dir / str(job_id)
    d.mkdir(parents=True, exist_ok=True)
    return d
```
- Extend `infra/db/repositories.py`:
```python
def insert_voice_clip(conn, script_id, engine, voice, speed, pitch, emotion,
                      duration_sec, audio_path) -> int: ...
def get_voice_clip_by_job(conn, job_id):  # joins stories→scripts→voice_clips
    return conn.execute(
        "SELECT vc.* FROM voice_clips vc JOIN scripts s ON vc.script_id=s.id "
        "JOIN stories st ON s.story_id=st.id WHERE st.job_id=?", (job_id,)).fetchone()

def insert_subtitle(conn, voice_clip_id, fmt, styler, ass_path, srt_path) -> int: ...
def insert_video(conn, job_id, format, aspect, width, height, duration_sec,
                 background_id, music_id, video_path, thumbnail_path,
                 size_bytes) -> int: ...
```
- Tests in `tests/test_storage.py` and extend `tests/test_repositories.py`.

### Task 2: voice plugin base + Piper engine

- `plugins/voice/base.py`: `VoiceOpts(voice, speed, pitch, emotion, volume)`, `AudioClip(path, duration_sec)`.
- `plugins/voice/piper/engine.py`: `PiperVoiceEngine` — calls `piper` binary via subprocess; falls back to a simple sine-wave wav generator if piper missing (so the pipeline is testable without TTS). The "fallback wav" path is also what fakes use.
- Tests: `tests/test_voice_engine.py` — fake engine returns a stub wav; real piper test marked `@needs_piper`.

### Task 3: faster-whisper transcription wrapper

- `infra/whisper/transcribe.py`: `transcribe_words(audio_path, model_size="base") -> list[WordTiming]`. Lazily imports faster-whisper; raises `MissingDependency` if not installed.
- `WordTiming(word, start, end, confidence)`.
- Tests skip if whisper missing.

### Task 4: caption styler (ASS)

- `plugins/captions/ass_styler.py`: `ASSStyler.render(words, style) -> SubtitleArtifacts(ass_path, srt_path)`. Builds ASS with word-by-word `Dialogue` events (karaoke style) + a plain SRT.
- Style templates loaded from `config/caption_templates.json`.
- Tests build ASS for fake word timings and assert the file contains the words.

### Task 5: ffmpeg infra (probe + run)

- `infra/ffmpeg/probe.py`: `probe_duration(path)`, `probe_resolution(path)` — via `ffprobe -v error -show_entries ...`.
- `infra/ffmpeg/run.py`: `run_ffmpeg(args, timeout)` subprocess wrapper; `MissingFFmpeg` exception.
- Tests marked `@needs_ffmpeg`.

### Task 6: FFmpeg editor + music ducker

- `plugins/editor/ffmpeg_editor.py`: `FFmpegEditor.compose(EditSpec) -> VideoFile`. Builds a `filter_complex` that: scales+crops background to target aspect, loops to narration length, overlays caption ASS (`ass=`), mixes narration + ducked music (`sidechaincompress`).
- `plugins/music/ducker.py`: `MusicDucker.apply(track_path, narration_path, out_path)` — loops, fades, ducks.
- `EditSpec` dataclass: voice_path, background_path, music_path (optional), ass_path (optional), format, watermark_path (optional), intro/outro (optional).
- Tests with `@needs_ffmpeg`.

### Task 7: Voice / Subtitle / Editor agents

- `agents/voice_agent.py`: `make_voice_agent(engine, conn, opts, paths)` — reads script, synthesizes, persists voice_clip.
- `agents/subtitle_agent.py`: `make_subtitle_agent(conn, styler, paths, model_size)` — transcribes voice clip, builds ASS+SRT, persists subtitle row.
- `agents/editor_agent.py`: `make_editor_agent(editor, conn, paths, library, format)` — composes video, persists video row.
- All testable with fakes; ffmpeg tests marked.

### Task 8: wire Phase 3 into container + add deps

- Add deps: `faster-whisper`, `pillow`, `numpy` to `pyproject.toml` (piper stays a system binary; we detect it).
- Container: register `PiperVoiceEngine`, `ASSStyler`, `FFmpegEditor`, `MusicDucker`; register VOICE/SUBTITLE/EDIT agents.
- Library view: a minimal browser for the media library (Phase 4 refines).

### Self-review checkpoint
After Task 8: full pipeline (RESEARCH→...→EDIT) runs end-to-end with a fake stack; with real ffmpeg+piper+whisper it renders an actual video file.

---

Phase 3 deliverable: a chosen story flows through to a rendered video file on disk, ready for Phase 4's approval gate.
