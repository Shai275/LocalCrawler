"""YouTube URL recognition and cancellable local subtitle/transcription work."""
import asyncio
import json
import os
from pathlib import Path
import re
import sys
import tempfile
from urllib.parse import parse_qs, urlsplit


def youtube_id(url: str) -> str | None:
    parts = urlsplit(url)
    host = (parts.hostname or "").lower()
    path = parts.path.strip("/").split("/")
    if host in ("youtu.be", "www.youtu.be"):
        value = path[0]
    elif host in ("youtube.com", "www.youtube.com", "m.youtube.com", "music.youtube.com", "youtube-nocookie.com", "www.youtube-nocookie.com"):
        value = parse_qs(parts.query).get("v", [""])[0] if path[0] == "watch" else path[1] if len(path) > 1 and path[0] in ("shorts", "embed", "live") else ""
        if not value:
            raise ValueError("請貼上單支 YouTube 影片連結，不是頻道或播放清單。")
    else:
        return None
    if not re.fullmatch(r"[\w-]{11}", value, flags=re.ASCII):
        raise ValueError("YouTube 影片 ID 格式不正確。")
    return value


def format_transcript(snippets: list[dict], video_id: str) -> str:
    lines = []
    for snippet in snippets:
        seconds = max(0, int(snippet["start"]))
        text = str(snippet["text"]).replace("\n", " ").strip()
        if text:
            label = f"{seconds // 3600:02d}:{seconds // 60 % 60:02d}:{seconds % 60:02d}"
            lines.append(f"[{label}](https://www.youtube.com/watch?v={video_id}&t={seconds}s) {text}")
    if not lines:
        raise ValueError("這支影片的字幕沒有可使用的文字。")
    return "\n\n".join(lines)


async def fetch_video(video_id: str, timeout: int, progress=None, frame_output: Path | None = None) -> dict:
    # The parent owns the folder so cancellation/forced worker exit also cleans up.
    workspace = tempfile.TemporaryDirectory(prefix="localcrawler_audio_")
    process = None
    reader = None
    guard = None
    collector = None
    async def read_progress():
        while line := await process.stderr.readline():
            message = line.decode("utf-8", errors="replace").strip()
            if message.startswith("PROGRESS:") and progress:
                progress(message.removeprefix("PROGRESS:"))
    completed = False
    try:
        if getattr(sys, "frozen", False):
            worker = Path(sys.executable).with_name("LocalCrawlerWorker.exe")
            if not worker.is_file():
                raise ValueError("影片工作程序不存在，請重新安裝完整版本。")
            worker_args = [str(worker), video_id, workspace.name]
        else:
            worker_args = [sys.executable, str(Path(__file__).with_name("video_worker.py")), video_id, workspace.name]
        if frame_output:
            worker_args.append(str(frame_output))
        process = await asyncio.create_subprocess_exec(
            *worker_args,
            stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
            env=__import__('resource_policy').worker_environment(),
        )
        reader = asyncio.create_task(read_progress())
        from resource_policy import guard_worker
        guard = asyncio.create_task(guard_worker(process.pid))
        async def collect():
            stdout = await process.stdout.read()
            await process.wait()
            return stdout
        collector = asyncio.create_task(collect())
        done, _ = await asyncio.wait([collector, guard], timeout=max(timeout + 20, 2700), return_when=asyncio.FIRST_COMPLETED)
        if not done:
            raise asyncio.TimeoutError()
        if guard in done:
            try:
                guard.result()
            except MemoryError as exc:
                raise ValueError(str(exc)) from None
        stdout = await collector
        if process.returncode:
            raise ValueError("影片文字處理程序失敗。")
        data = json.loads(stdout.decode("utf-8"))
        if data.get("error"):
            raise ValueError(data["error"])
        if frame_output:
            frame_output.mkdir(parents=True, exist_ok=True)
            (frame_output / 'capture.json').write_text(json.dumps({
                'frames': data.get('frames', []), 'resources': data.get('resource_status', {}),
                'warning': data.get('frame_warning', '')}, ensure_ascii=False, indent=2), encoding='utf-8')
            (frame_output / 'transcript.json').write_text(json.dumps({
                'video_id': video_id, 'language': data.get('language'),
                'audio_transcribed': data.get('audio_transcribed', False),
                'snippets': data['snippets']}, ensure_ascii=False, indent=2), encoding='utf-8')
        data["markdown"] = format_transcript(data.pop("snippets"), video_id)
        completed = True
        return data
    finally:
        if guard:
            guard.cancel()
            await asyncio.gather(guard, return_exceptions=True)
        if process and process.returncode is None:
            from resource_policy import stop_worker_tree
            await asyncio.to_thread(stop_worker_tree, process.pid)
            await process.wait()
        if reader:
            reader.cancel()
            await asyncio.gather(reader, return_exceptions=True)
        if collector:
            collector.cancel()
            await asyncio.gather(collector, return_exceptions=True)
        workspace.cleanup()
        if frame_output and not completed and frame_output.is_dir():
            for image in frame_output.glob("F???_??????s.jpg"):
                image.unlink(missing_ok=True)
            try:
                frame_output.rmdir()
            except OSError:
                pass
