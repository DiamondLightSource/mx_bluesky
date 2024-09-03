from unittest.mock import MagicMock, patch

from bluesky.run_engine import RunEngine
from ophyd.sim import make_fake_device

from mx_bluesky.example import Synchrotron, example_plan


@patch("mx_bluesky.example.print")
def test_example_reads_correct_value(mock_print: MagicMock):
    RE = RunEngine()
    fake_device: Synchrotron = make_fake_device(Synchrotron)(name="fake_synch")
    fake_device.ring_current.sim_put(378.8)  # type: ignore
    RE(example_plan(fake_device))

    mock_print.assert_called_once_with(378.8)
