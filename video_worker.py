"""Public YouTube transcript fetcher with local audio transcription fallback.

The temporary audio file is removed before the worker exits. It uses no cookies,
login, proxy rotation, or access-control bypasses.
"""
import json
import sys
import tempfile
from contextlib import nullcontext
from pathlib import Path


def fetch(video_id):
    import requests
    from youtube_transcript_api import YouTubeTranscriptApi

    class Session(requests.Session):
        def request(self, method, url, **kwargs):
            kwargs.setdefault("timeout", 12)
            return super().request(method, url, **kwargs)

    with Session() as session:
        api = YouTubeTranscriptApi(http_client=session)
        tracks = list(api.list(video_id))
        if not tracks:
            raise ValueError("這支影片沒有可取得的字幕。")
        languages = ["zh-TW", "zh-Hant", "zh", "zh-CN", "zh-Hans", "en", "ja"]
        track = min(tracks, key=lambda t: (languages.index(t.language_code) if t.language_code in languages else 99, t.is_generated))
        transcript = track.fetch()
        title = f"YouTube · {video_id}"
        try:
            meta = session.get("https://www.youtube.com/oembed", params={"url": f"https://www.youtube.com/watch?v={video_id}", "format": "json"})
            if meta.ok:
                title = meta.json().get("title", title)
        except (requests.RequestException, ValueError):
            pass
        return {"title": title, "language": track.language_code, "generated": track.is_generated, "snippets": transcript.to_raw_data()}


def progress(message):
    print("PROGRESS:" + message, file=sys.stderr, flush=True)


def transcribe_public_audio(video_id, workspace=None):
    """Download a bounded public audio stream and transcribe it locally."""
    import yt_dlp
    from faster_whisper import WhisperModel

    url = f"https://www.youtube.com/watch?v={video_id}"
    with (nullcontext(workspace) if workspace else tempfile.TemporaryDirectory(prefix="localcrawler_audio_")) as temp:
        progress("沒有字幕，正在取得公開音訊…")
        def download_progress(state):
            if state.get("downloaded_bytes", 0) > 120 * 1024 * 1024:
                raise ValueError("音訊超過 120 MB 上限。")
        output = str(Path(temp) / "audio.%(ext)s")
        options = {
            "format": "bestaudio[ext=m4a]/bestaudio/best",
            "outtmpl": output,
            "noplaylist": True,
            "quiet": True,
            "no_warnings": True,
            "noprogress": True,
            "max_filesize": 120 * 1024 * 1024,
            "socket_timeout": 20,
            "progress_hooks": [download_progress],
        }
        with yt_dlp.YoutubeDL(options) as downloader:
            info = downloader.extract_info(url, download=False)
            if not info or info.get("is_live"):
                raise ValueError("直播或無法判定長度的影片暫不支援本機轉錄。")
            duration = info.get("duration")
            if not isinstance(duration, (int, float)) or duration <= 0 or duration > 90 * 60:
                raise ValueError("音訊轉錄目前限 90 分鐘內的公開影片。")
            downloader.process_ie_result(info, download=True)
            audio_files = list(Path(temp).glob("audio.*"))
            if not audio_files:
                raise ValueError("公開音訊下載未產生可轉錄的檔案。")
            audio = audio_files[0]
            title = str(info.get("title") or f"YouTube · {video_id}")
        # CPU int8 is dependable on Windows and keeps all speech recognition local.
        progress("載入本機語音模型（首次使用需下載）…")
        model = WhisperModel("small", device="cpu", compute_type="int8")
        segments, details = model.transcribe(str(audio), beam_size=5, vad_filter=True,
                                             condition_on_previous_text=False,
                                             initial_prompt="影片標題（專有名詞參考）：" + title[:160])
        snippets = []
        last_percent = -1
        for segment in segments:
            if segment.text.strip():
                snippets.append({"start": float(segment.start), "text": segment.text.strip()})
            percent = min(100, int(segment.end / duration * 100))
            if percent >= last_percent + 5:
                progress(f"本機語音轉文字 {percent}% · {int(segment.end)//60}:{int(segment.end)%60:02d}")
                last_percent = percent
        if not snippets:
            raise ValueError("本機語音轉文字沒有辨識到可用內容。")
        return {"title": title, "language": details.language or "unknown",
                "generated": True, "audio_transcribed": True, "snippets": snippets}


if __name__ == "__main__":
    try:
        try:
            result = fetch(sys.argv[1])
        except Exception as subtitle_error:
            if type(subtitle_error).__name__ not in {"TranscriptsDisabled", "NoTranscriptFound", "ValueError"}:
                raise
            result = transcribe_public_audio(sys.argv[1], sys.argv[2] if len(sys.argv) > 2 else None)
            result["subtitle_fallback"] = type(subtitle_error).__name__
    except Exception as exc:
        name = type(exc).__name__
        messages = {
            "TranscriptsDisabled": "影片未提供可取得的字幕。",
            "RequestBlocked": "YouTube 阻擋了本次字幕請求，無法據此總結影片。",
            "IpBlocked": "YouTube 阻擋了目前網路的字幕請求。",
            "VideoUnavailable": "影片不存在、已下架或無法公開存取。",
            "AgeRestricted": "影片有年齡限制，無法讀取字幕。",
            "NoTranscriptFound": "找不到可用字幕。",
        }
        result = {"error": messages.get(name, f"無法處理公開影片音訊（{name}）。") + " 請確認影片可公開播放，或改用「貼上文字／字幕」。"}
    print(json.dumps(result, ensure_ascii=False))
