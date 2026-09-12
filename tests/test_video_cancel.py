import asyncio
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import video


class VideoCancelTests(unittest.TestCase):
    def test_cancel_kills_worker_and_removes_partial_audio(self):
        async def scenario():
            original = asyncio.create_subprocess_exec
            ready = asyncio.Event()
            folders = []
            processes = []
            async def fake_worker(*args, **kwargs):
                folder = args[-1]
                folders.append(Path(folder))
                code = "import sys,time,pathlib; pathlib.Path(sys.argv[1],'audio.part').write_bytes(b'partial'); print('PROGRESS:ready',file=sys.stderr,flush=True); time.sleep(30)"
                process = await original(sys.executable, '-c', code, folder, **kwargs)
                processes.append(process)
                return process
            with patch('video.asyncio.create_subprocess_exec', new=fake_worker):
                task = asyncio.create_task(video.fetch_video('abcdefghijk', 5, lambda _: ready.set()))
                await asyncio.wait_for(ready.wait(), 10)
                self.assertTrue((folders[0] / 'audio.part').exists())
                task.cancel()
                with self.assertRaises(asyncio.CancelledError):
                    await task
            self.assertFalse(folders[0].exists())
            self.assertIsNotNone(processes[0].returncode)
        asyncio.run(scenario())
