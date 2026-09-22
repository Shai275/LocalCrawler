"""Conservative per-worker limits; does not change global machine settings."""
import os
import asyncio
import time

THREADS = max(1, min(2, (os.cpu_count() or 2) // 2))


def worker_environment():
    return {**os.environ, 'PYTHONUTF8': '1', 'OMP_NUM_THREADS': str(THREADS),
            'OPENBLAS_NUM_THREADS': str(THREADS), 'MKL_NUM_THREADS': str(THREADS),
            'NUMEXPR_NUM_THREADS': str(THREADS)}


def configure_worker():
    import psutil
    process = psutil.Process()
    status = {'threads': THREADS, 'affinity': None, 'priority': 'unchanged'}
    try:
        available = process.cpu_affinity()
        selected = available[:max(1, min(THREADS, len(available)//2))]
        process.cpu_affinity(selected)
        status['affinity'] = selected
    except (AttributeError, psutil.Error):
        pass
    try:
        process.nice(psutil.BELOW_NORMAL_PRIORITY_CLASS if os.name == 'nt' else 10)
        status['priority'] = 'below-normal'
    except psutil.Error:
        pass
    return status


async def guard_worker(pid, *, cpu_fraction=.40, memory_limit=None, interval=.25):
    """Soft CPU duty-cycle and sampled RSS ceiling for our worker only."""
    import psutil
    if not 0 < cpu_fraction <= 1 or interval <= 0:
        raise ValueError('Invalid resource policy')
    try:
        process = psutil.Process(pid)
    except psutil.NoSuchProcess:
        return
    budget = max(1, psutil.cpu_count() or 1) * cpu_fraction
    if memory_limit is None:
        memory_limit = min(2 * 1024**3, int(psutil.virtual_memory().total * .25))
    last_cpu = 0; last_wall = time.monotonic()
    while True:
        await asyncio.sleep(interval)
        try:
            members = [process] + process.children(recursive=True)
            cpu, rss = 0, 0
            for member in members:
                try:
                    cpu += sum(member.cpu_times()[:2])
                    rss += member.memory_info().rss
                except psutil.NoSuchProcess:
                    pass
            if rss > memory_limit:
                raise MemoryError('影片工作程序超過記憶體保護上限，已停止本次處理。')
            now = time.monotonic()
            excess = (cpu-last_cpu)/budget - (now-last_wall)
            if excess > .02:
                suspended = []
                try:
                    for member in members:
                        try:
                            member.suspend()
                            suspended.append(member)
                        except psutil.NoSuchProcess:
                            pass
                    await asyncio.sleep(excess)
                finally:
                    for member in reversed(suspended):
                        try:
                            member.resume()
                        except psutil.NoSuchProcess:
                            pass
            last_cpu, last_wall = cpu, time.monotonic()
        except psutil.NoSuchProcess:
            return


def stop_worker_tree(pid):
    """Terminate only this task's worker and its descendants."""
    import psutil
    try:
        parent = psutil.Process(pid)
        children = parent.children(recursive=True)
        for member in [parent] + children:
            try:
                member.kill()
            except psutil.NoSuchProcess:
                pass
        psutil.wait_procs(children, timeout=3)
    except psutil.NoSuchProcess:
        pass
