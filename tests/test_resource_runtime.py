import asyncio
import contextlib
import sys
import time
import unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import psutil
from resource_policy import guard_worker, stop_worker_tree
from video_frames import choose_timestamps


class RuntimeTests(unittest.IsolatedAsyncioTestCase):
    async def test_busy_worker_is_throttled_and_resumed_on_cancel(self):
        child = await asyncio.create_subprocess_exec(sys.executable, '-c', 'while True: pass')
        process = psutil.Process(child.pid)
        def cpu_time():
            return sum(sum(p.cpu_times()[:2]) for p in [process] + process.children(recursive=True))
        guard = asyncio.create_task(guard_worker(child.pid,
            cpu_fraction=.20 / (psutil.cpu_count() or 1), interval=.05))
        try:
            start = time.monotonic()
            await asyncio.sleep(3)
            used = cpu_time() / (time.monotonic()-start)
            self.assertLess(used, .40, f'CPU core fraction: {used}')
            guard.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await guard
            before = cpu_time()
            await asyncio.sleep(.3)
            self.assertGreater(cpu_time(), before)
        finally:
            guard.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await guard
            stop_worker_tree(child.pid)
            await child.wait()

    async def test_memory_limit_reports_failure(self):
        child = await asyncio.create_subprocess_exec(sys.executable, '-c',
            'import time; allocation=bytearray(32*1024*1024); time.sleep(10)')
        try:
            with self.assertRaises(MemoryError):
                await asyncio.wait_for(guard_worker(child.pid, memory_limit=20*1024**2, interval=.05), 5)
        finally:
            stop_worker_tree(child.pid)
            await child.wait()

    def test_long_video_samples_cover_end(self):
        samples = choose_timestamps(5400)
        self.assertEqual(len(samples), 12)
        self.assertGreater(samples[-1], 5300)
