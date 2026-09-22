"""Timestamp-preserving PyAV decoding with explicit hardware verification."""
import sys
from resource_policy import THREADS


class FrameDecoder:
    def __init__(self, path):
        import av
        from av.codec.hwaccel import HWAccel, hwdevices_available
        self.path = str(path)
        self.container = None
        self.status = 'software-fallback'
        self.device = None
        self.fallback_reason = None
        preferred = {'win32': 'd3d11va', 'darwin': 'videotoolbox'}.get(sys.platform, 'vaapi')
        try:
            if preferred not in hwdevices_available():
                raise RuntimeError('Hardware backend unavailable')
            self.container = av.open(self.path, hwaccel=HWAccel(preferred, allow_software_fallback=False))
            stream = self.container.streams.video[0]
            stream.codec_context.thread_count = THREADS
            next(self.container.decode(stream))
            if not stream.codec_context.is_hwaccel:
                raise RuntimeError('Decoder did not activate hardware acceleration')
            self.device = preferred
            self.status = 'hardware-verified'
        except Exception as exc:
            self.fallback_reason = type(exc).__name__
            self._software()

    def _software(self):
        import av
        self.close()
        self.container = av.open(self.path)
        try:
            self.container.streams.video[0].codec_context.thread_count = THREADS
        except Exception:
            self.close()
            raise
        self.status, self.device = 'software-fallback', None

    def _read_at(self, seconds):
        stream = self.container.streams.video[0]
        origin = stream.start_time or 0
        target = origin + int(seconds / stream.time_base)
        self.container.seek(target, stream=stream, backward=True)
        for frame in self.container.decode(stream):
            if frame.pts is None:
                continue
            actual = float((frame.pts - origin) * stream.time_base)
            if actual + 1e-6 >= seconds:
                # Return presentation timestamp, not requested seek position.
                return frame.to_ndarray(format='bgr24'), actual
        return None, None

    def read_at(self, seconds):
        try:
            return self._read_at(seconds)
        except Exception as exc:
            if self.status != 'hardware-verified':
                raise
            self.fallback_reason = type(exc).__name__
            self._software()
            return self._read_at(seconds)

    def close(self):
        if self.container is not None:
            self.container.close()
            self.container = None
