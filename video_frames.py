"""Bounded key-frame extraction and evidence-linked visual notes."""
from __future__ import annotations

import base64
import re
from pathlib import Path

MAX_FRAMES = 12
MAX_DURATION = 90 * 60


def choose_timestamps(duration: float, *, max_frames: int = MAX_FRAMES) -> list[float]:
    """Spread candidates across a video while skipping likely title/end cards."""
    if duration <= 0 or duration > MAX_DURATION:
        raise ValueError("畫面分析目前限 90 分鐘內的影片。")
    if not 1 <= max_frames <= MAX_FRAMES:
        raise ValueError('影格數量必須介於 1 與 12。')
    count = min(max_frames, max(3, round(duration / 90) + 2))
    start, end = min(5.0, duration * .05), max(duration * .92, duration - 5)
    if count == 1:
        return [round(duration / 2, 2)]
    return [round(start + (end - start) * i / (count - 1), 2) for i in range(count)]


def candidate_timestamps(duration: float, *, max_frames: int = MAX_FRAMES) -> list[float]:
    """Inspect more positions than we retain so short-lived slides are less likely to be missed."""
    retained = len(choose_timestamps(duration, max_frames=max_frames))
    count = min(MAX_FRAMES * 4, max(retained, retained * 4))
    start, end = min(3.0, duration * .03), max(duration * .97, duration - 3)
    return [round(start + (end - start) * i / (count - 1), 2) for i in range(count)] if count > 1 else [duration / 2]


def select_candidates(candidates: list[dict], duration: float, count: int) -> list[dict]:
    """Keep the strongest frame in each time segment for coverage plus visual information."""
    if len(candidates) <= count:
        return candidates
    selected = []
    for index in range(count):
        low, high = duration * index / count, duration * (index + 1) / count
        bucket = [item for item in candidates if low <= item['requested_seconds'] <= high]
        if not bucket:
            midpoint = (low + high) / 2
            bucket = sorted(candidates, key=lambda item: abs(item['requested_seconds'] - midpoint))[:1]
        best = max(bucket, key=lambda item: (item['selection_score'], -abs(item['requested_seconds']-(low+high)/2)))
        if best not in selected:
            selected.append(best)
    if len(selected) < count:
        remaining = sorted((x for x in candidates if x not in selected), key=lambda x: x['selection_score'], reverse=True)
        selected.extend(remaining[:count-len(selected)])
    return sorted(selected, key=lambda item: item['requested_seconds'])


def extract_keyframes(video_path: str | Path, output: str | Path, duration: float,
                      *, max_frames: int = MAX_FRAMES) -> list[dict]:
    """Save compact JPEG evidence, dropping near-duplicate and blank frames."""
    import cv2
    from resource_policy import THREADS
    cv2.setNumThreads(THREADS)

    output = Path(output)
    output.mkdir(parents=True, exist_ok=True)
    from frame_decoder import FrameDecoder
    capture = FrameDecoder(video_path)
    retained_count = len(choose_timestamps(duration, max_frames=max_frames))
    candidates, previous = [], None
    try:
        for seconds in candidate_timestamps(duration, max_frames=max_frames):
            image, actual_seconds = capture.read_at(seconds)
            if image is None:
                continue
            height, width = image.shape[:2]
            if width > 1280:
                image = cv2.resize(image, (1280, round(height * 1280 / width)), interpolation=cv2.INTER_AREA)
            gray = cv2.resize(cv2.cvtColor(image, cv2.COLOR_BGR2GRAY), (32, 18))
            if gray.mean() < 12 or gray.std() < 8:
                continue
            change = cv2.absdiff(gray, previous).mean() if previous is not None else 20.0
            if previous is not None and change < 7:
                continue
            edge = cv2.Laplacian(gray, cv2.CV_64F).var()
            ok, encoded = cv2.imencode('.jpg', image, [cv2.IMWRITE_JPEG_QUALITY, 82])
            if not ok:
                continue
            candidates.append({'image': encoded.tobytes(), 'selection_score': round(float(change + gray.std() + min(edge, 500)/10), 3),
                "seconds": int(seconds),
                'requested_seconds': seconds,
                'decoded_seconds': actual_seconds,
                'decoder_acceleration': capture.device,
                'decoder_status': capture.status,
                'decoder_fallback_reason': capture.fallback_reason})
            previous = gray
    finally:
        capture.close()
    frames = []
    for index, candidate in enumerate(select_candidates(candidates, duration, retained_count), 1):
        frame_id = f'F{index:03d}'
        filename = f"{frame_id}_{int(candidate['requested_seconds']):06d}s.jpg"
        (output / filename).write_bytes(candidate.pop('image'))
        candidate.update(id=frame_id, file=filename)
        frames.append(candidate)
    return frames


def encoded_frames(frames: list[dict], folder: str | Path) -> list[dict]:
    folder = Path(folder)
    return [dict(frame, data=base64.b64encode((folder / frame["file"]).read_bytes()).decode("ascii")) for frame in frames]


def read_frame_text(frames: list[dict], folder: str | Path) -> list[dict]:
    """Attach offline OCR text; failure leaves the frame usable as an image."""
    from rapidocr import RapidOCR
    from resource_policy import THREADS
    engine = RapidOCR(params={'EngineConfig.onnxruntime.intra_op_num_threads': THREADS,
                              'EngineConfig.onnxruntime.inter_op_num_threads': 1})
    folder = Path(folder)
    for frame in frames:
        try:
            result = engine(str(folder / frame["file"]))
            layout = []
            boxes = result.boxes if result.boxes is not None else ()
            for text, score, box in zip(result.txts or (), result.scores or (), boxes):
                text = str(text).strip()
                if not text or float(score) < .45:
                    continue
                center = [round(float(sum(point[0] for point in box) / len(box)), 1),
                          round(float(sum(point[1] for point in box) / len(box)), 1)]
                layout.append({'text': text, 'confidence': round(float(score), 3), 'center': center})
            frame['ocr_layout'] = layout[:30]
            frame["ocr"] = [item['text'] for item in layout[:30]]
            frame['layout_hints'] = infer_layout_hints(layout[:30])
        except Exception:
            frame["ocr"] = []
            frame['ocr_layout'] = []
            frame['layout_hints'] = []
    return frames


def infer_layout_hints(items: list[dict]) -> list[str]:
    """Create conservative, visibly verifiable hints from OCR positions."""
    hints = []
    numbers = [item for item in items if re.fullmatch(r'[-+]?\d+(?:[.,]\d+)?%?', item['text'])]
    labels = [item for item in items if re.fullmatch(r'(?=.*[A-Za-z])[A-Za-z0-9]{2,8}', item['text'])]
    pairs = []
    for label in labels:
        above = [number for number in numbers if number['center'][1] < label['center'][1]
                 and abs(number['center'][0] - label['center'][0]) <= 90]
        if above:
            number = min(above, key=lambda item: abs(item['center'][0]-label['center'][0]) + abs(item['center'][1]-label['center'][1])*.1)
            pairs.append(f"{label['text']} ↔ {number['text']}")
    if len(pairs) >= 2:
        hints.append('位置配對：' + '、'.join(pairs[:8]))
    rows = []
    # Only use concise uppercase labels here; arbitrary same-line prose is not a process sequence.
    candidates = [item for item in items if re.fullmatch(r'[A-Z][A-Z0-9 _-]{1,23}', item['text'])
                  and len(re.findall(r'[A-Z]', item['text'])) >= 4 and item not in numbers]
    for seed in candidates:
        row = sorted((item for item in candidates if abs(item['center'][1]-seed['center'][1]) <= 35), key=lambda item: item['center'][0])
        texts = [item['text'] for item in row]
        if len(texts) >= 3 and texts not in rows:
            rows.append(texts)
    if rows:
        best = max(rows, key=len)
        hints.append('水平排列：' + ' → '.join(best[:8]))
    return hints[:2]


def render_gallery(frames: list[dict], video_id: str, folder_name: str) -> str:
    hardware = sum(frame.get('decoder_status') == 'hardware-verified' for frame in frames)
    rows = ["## 智慧挑選的畫面關鍵影格", "",
            f"從影片各時段的候選畫面中保存 {len(frames)} 張；{hardware} 張經確認使用硬體解碼。這是抽樣，不代表檢查過每一秒。", ""]
    for frame in frames:
        seconds = frame["seconds"]
        stamp = f"{seconds//3600:02d}:{seconds//60%60:02d}:{seconds%60:02d}"
        rows += [f"### [{stamp}](https://www.youtube.com/watch?v={video_id}&t={seconds}s)", "",
                 f"![{stamp} 畫面]({folder_name}/{frame['file']})", ""]
    return "\n".join(rows)
