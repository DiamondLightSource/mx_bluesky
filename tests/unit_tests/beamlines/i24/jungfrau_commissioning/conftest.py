import threading
import time
from collections.abc import Callable
from unittest.mock import MagicMock

import pytest
from bluesky.run_engine import RunEngine
from dodal.beamlines import i24
from dodal.devices.i24.i24_vgonio import VGonio
from dodal.devices.i24.jungfrau import JungfrauM1
from dodal.devices.i24.read_only_attenuator import ReadOnlyEnergyAndAttenuator
from dodal.devices.zebra import Zebra
from ophyd.device import Device
from ophyd.status import Status


@pytest.fixture
def completed_status():
    result = Status()
    result.set_finished()
    return result


@pytest.fixture
def fake_vgonio(completed_status) -> VGonio:
    gon: VGonio = i24.vgonio(fake_with_ophyd_sim=True)

    def set_omega_side_effect(val):
        gon.omega.user_readback.sim_put(val)
        return completed_status

    gon.omega.set = MagicMock(side_effect=set_omega_side_effect)

    gon.x.user_setpoint._use_limits = False
    gon.yh.user_setpoint._use_limits = False
    gon.z.user_setpoint._use_limits = False
    gon.omega.user_setpoint._use_limits = False
    return gon


@pytest.fixture
def fake_jungfrau(completed_status) -> JungfrauM1:
    JF: JungfrauM1 = i24.jungfrau(fake_with_ophyd_sim=True)

    def set_acquire_side_effect(val):
        JF.acquire_rbv.sim_put(1)
        JF.writing_rbv.sim_put(1)

        def go_low():
            time.sleep(1)
            JF.acquire_rbv.sim_put(0)
            time.sleep(0.5)
            JF.writing_rbv.sim_put(0)

        threading.Thread(target=go_low, daemon=True).start()
        return completed_status

    JF.acquire_start.set = MagicMock(side_effect=set_acquire_side_effect)

    return JF


@pytest.fixture
def fake_beam_params() -> ReadOnlyEnergyAndAttenuator:
    BP: ReadOnlyEnergyAndAttenuator = i24.beam_params(fake_with_ophyd_sim=True)
    BP.transmission.sim_put(0.1)
    BP.energy.sim_put(20000)
    BP.wavelength.sim_put(0.65)
    BP.intensity.sim_put(9999999)
    return BP


@pytest.fixture
def fake_devices(
    fake_vgonio, fake_jungfrau, fake_zebra, fake_beam_params
) -> dict[str, Device]:
    devices = {
        "jungfrau": fake_jungfrau,
        "gonio": fake_vgonio,
        "zebra": fake_zebra,
        "beam_params": fake_beam_params,
    }
    return devices


@pytest.fixture
def fake_create_devices_function(fake_devices) -> Callable[..., dict[str, Device]]:
    return lambda: fake_devices


@pytest.fixture
def RE() -> RunEngine:
    return RunEngine()


@pytest.fixture
def fake_zebra(zebra) -> Zebra:
    return zebra
