import sys
import tempfile
import unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import av
import numpy as np
from frame_decoder import FrameDecoder
from video_frames import extract_keyframes


class DecoderTests(unittest.TestCase):
    def test_real_h264_seek_and_metadata(self):
        with tempfile.TemporaryDirectory() as tmp:
            video = Path(tmp) / 'sample.mp4'
            with av.open(str(video), 'w') as output:
                stream = output.add_stream('libx264', rate=10)
                stream.width, stream.height, stream.pix_fmt = 320, 240, 'yuv420p'
                stream.codec_context.thread_count = 1
                for i in range(60):
                    pixels = np.zeros((240, 320, 3), dtype=np.uint8)
                    pixels[20:180, 10+i:150+i] = (40+i*3, 150, 210)
                    frame = av.VideoFrame.from_ndarray(pixels, format='rgb24')
                    for packet in stream.encode(frame):
                        output.mux(packet)
                for packet in stream.encode():
                    output.mux(packet)
            decoder = FrameDecoder(video)
            try:
                image, seconds = decoder.read_at(2.35)
                self.assertEqual(image.shape, (240, 320, 3))
                self.assertAlmostEqual(seconds, 2.4, places=3)
                print('Decoder acceptance:', decoder.status, decoder.device, seconds)
                # Both results are valid on user machines; never claim hardware on fallback.
                self.assertEqual(decoder.status == 'hardware-verified', decoder.device is not None)
            finally:
                decoder.close()
            frames = extract_keyframes(video, Path(tmp)/'frames', 6)
            self.assertTrue(frames)
            self.assertTrue(all(f['decoded_seconds'] >= f['requested_seconds'] for f in frames))
