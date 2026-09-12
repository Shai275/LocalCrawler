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


async def fetch_video(video_id: str, timeout: int, progress=None) -> dict:
    # The parent owns the folder so cancellation/forced worker exit also cleans up.
    workspace = tempfile.TemporaryDirectory(prefix="localcrawler_audio_")
    process = None
    reader = None
    async def read_progress():
        while line := await process.stderr.readline():
            message = line.decode("utf-8", errors="replace").strip()
            if message.startswith("PROGRESS:") and progress:
                progress(message.removeprefix("PROGRESS:"))
    try:
        process = await asyncio.create_subprocess_exec(
            sys.executable, str(Path(__file__).with_name("video_worker.py")), video_id, workspace.name,
            stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
            env={**os.environ, "PYTHONUTF8": "1"},
        )
        reader = asyncio.create_task(read_progress())
        async def collect():
            stdout = await process.stdout.read()
            await process.wait()
            return stdout
        stdout = await asyncio.wait_for(collect(), timeout=max(timeout + 20, 2700))
        if process.returncode:
            raise ValueError("影片文字處理程序失敗。")
        data = json.loads(stdout.decode("utf-8"))
        if data.get("error"):
            raise ValueError(data["error"])
        data["markdown"] = format_transcript(data.pop("snippets"), video_id)
        return data
    finally:
        if process and process.returncode is None:
            process.kill()
            await process.wait()
        if reader:
            reader.cancel()
            await asyncio.gather(reader, return_exceptions=True)
        workspace.cleanup()
