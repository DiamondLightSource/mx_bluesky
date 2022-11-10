from ophyd import Component as Cpt
from ophyd import Device, EpicsMotor, EpicsSignal

"""
Real motors added to allow stops following pin load (e.g. real_x1.stop() )
Stub offsets are calibration values that are required to move between calibration pin position and spine pins. These are set in EPCICS and applied via the proc.
"""


class I03Smargon(Device):
    x: EpicsMotor = Cpt(EpicsMotor, "-MO-SGON-01:X")
    y: EpicsMotor = Cpt(EpicsMotor, "-MO-SGON-01:Y")
    z: EpicsMotor = Cpt(EpicsMotor, "-MO-SGON-01:Z")
    chi: EpicsMotor = Cpt(EpicsMotor, "-MO-SGON-01:CHI")
    phi: EpicsMotor = Cpt(EpicsMotor, "-MO-SGON-01:PHI")
    omega: EpicsMotor = Cpt(EpicsMotor, "-MO-SGON-01:OMEGA")

    stub_offset_set: EpicsSignal = Cpt(EpicsSignal, "-MO-SGON-01:SET_STUBS_TO_RL.PROC")

    real_x1: EpicsMotor = Cpt(EpicsMotor, "-MO-SGON-01:MOTOR_3")
    real_x2: EpicsMotor = Cpt(EpicsMotor, "-MO-SGON-01:MOTOR_4")
    real_y: EpicsMotor = Cpt(EpicsMotor, "-MO-SGON-01:MOTOR_1")
    real_z: EpicsMotor = Cpt(EpicsMotor, "-MO-SGON-01:MOTOR_2")
    real_phi: EpicsMotor = Cpt(EpicsMotor, "-MO-SGON-01:MOTOR_5")
    real_chi: EpicsMotor = Cpt(EpicsMotor, "-MO-SGON-01:MOTOR_6")
