import threading

import pytest
from bluesky.run_engine import RunEngine
from bluesky.simulators import RunEngineSimulator


@pytest.fixture
def sim_run_engine():
    return RunEngineSimulator()


@pytest.fixture
def RE():
    RE = RunEngine({}, call_returns_result=True)
    yield RE
    try:
        RE.halt()
    except Exception as e:
        print(f"Got exception while halting RunEngine {e}")
    finally:
        stopped_event = threading.Event()

        def stop_event_loop():
            RE.loop.stop()  # noqa: F821
            stopped_event.set()

        RE.loop.call_soon_threadsafe(stop_event_loop)
        stopped_event.wait(10)
    del RE
