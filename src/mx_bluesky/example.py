from bluesky.plan_stubs import rd
from bluesky.run_engine import RunEngine
from ophyd import Component, Device, EpicsSignal


class Synchrotron(Device):
    ring_current = Component(EpicsSignal, "SR-DI-DCCT-01:SIGNAL")


def example_plan(synch: Synchrotron):
    current = yield from rd(synch.ring_current)
    print(current)


def run_plan():
    RE = RunEngine()
    my_synch = Synchrotron(name="Synchrotron")
    my_synch.wait_for_connection()
    RE(example_plan(my_synch))
