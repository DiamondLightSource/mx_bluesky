from dodal.devices.zebra import (
    AND3,
    AND4,
    DISCONNECT,
    OR1,
    PC_GATE,
    PC_GATE_SOURCE_POSITION,
    PC_GATE_SOURCE_TIME,
    PC_PULSE_SOURCE_POSITION,
    SOFT_IN2,
    Zebra,
)

from mx_bluesky.I24.serial.setup_beamline.setup_zebra_plans import (
    arm_zebra,
    disarm_zebra,
    get_zebra_settings_for_extruder,
    reset_output_panel,
    reset_pc_gate_and_pulse,
    reset_zebra_when_collection_done_plan,
    set_shutter_mode,
    setup_pc_sources,
    setup_zebra_for_extruder_with_pump_probe_plan,
    setup_zebra_for_fastchip_plan,
    setup_zebra_for_quickshot_plan,
    zebra_return_to_normal_plan,
)


def test_arm_and_disarm_zebra(zebra: Zebra, RE):
    zebra.pc.arm.TIMEOUT = 0.5

    RE(arm_zebra(zebra))
    assert zebra.pc.is_armed()

    RE(disarm_zebra(zebra))
    assert not zebra.pc.is_armed()


def test_set_shutter_mode(zebra: Zebra, RE):
    RE(set_shutter_mode(zebra, "manual"))
    assert zebra.inputs.soft_in_1.get() == DISCONNECT


def test_setup_pc_sources(zebra: Zebra, RE):
    RE(setup_pc_sources(zebra, PC_GATE_SOURCE_TIME, PC_PULSE_SOURCE_POSITION))

    assert zebra.pc.gate_source.get() == PC_GATE_SOURCE_TIME
    assert zebra.pc.pulse_source.get() == PC_PULSE_SOURCE_POSITION


def test_get_zebra_settings_for_extruder_pumpprobe():
    width, step = get_zebra_settings_for_extruder(0.01, 0.005, 0.001)
    assert round(width, 3) == 0.016
    assert round(step, 3) == 0.026


def test_setup_zebra_for_quickshot(zebra: Zebra, RE):
    RE(setup_zebra_for_quickshot_plan(zebra, exp_time=0.001, num_images=10, wait=True))
    assert zebra.pc.arm_source.get() == "Soft"
    assert zebra.pc.gate_start.get() == 1.0
    assert zebra.pc.gate_input.get() == SOFT_IN2


def test_setup_zebra_for_extruder_pp_eiger_collection(zebra: Zebra, RE):
    inputs_list = (0.01, 10, 0.005, 0.001)
    # With eiger
    RE(
        setup_zebra_for_extruder_with_pump_probe_plan(
            zebra, "eiger", *inputs_list, wait=True
        )
    )
    assert zebra.output.out_1.get() == AND4
    assert zebra.output.out_2.get() == AND3

    assert zebra.inputs.soft_in_1.get() == DISCONNECT
    assert zebra.logic_gates.and_gate_3.source_1.get() == SOFT_IN2
    assert zebra.pc.num_gates.get() == 10


def test_setup_zebra_for_extruder_pp_pilatus_collection(zebra: Zebra, RE):
    inputs_list = (0.01, 10, 0.005, 0.001)
    # With pilatus
    RE(
        setup_zebra_for_extruder_with_pump_probe_plan(
            zebra, "pilatus", *inputs_list, wait=True
        )
    )
    # Check that SOFT_IN:B0 gets disabled
    assert zebra.output.out_1.get() == AND3

    assert zebra.pc.gate_start.get() == 1.0
    assert zebra.output.pulse_1.delay.get() == 0.0
    assert zebra.output.pulse_2.delay.get() == 0.001


def test_setup_zebra_for_fastchip(zebra: Zebra, RE):
    num_gates = 400
    num_exposures = 2
    exposure_time = 0.001
    # With Eiger
    RE(
        setup_zebra_for_fastchip_plan(
            zebra, "eiger", num_gates, num_exposures, exposure_time, wait=True
        )
    )
    # Check that SOFT_IN:B0 gets disabled
    assert zebra.output.out_1.get() == AND3

    # Check ttl out1 is set to AND3
    assert zebra.output.out_1.get() == AND3
    assert zebra.pc.num_gates.get() == num_gates
    assert zebra.pc.pulse_max.get() == num_exposures
    assert zebra.pc.pulse_width.get() == exposure_time - 0.0001

    # With Pilatus
    RE(
        setup_zebra_for_fastchip_plan(
            zebra, "pilatus", num_gates, num_exposures, exposure_time, wait=True
        )
    )
    # Check ttl out2 is set to AND3
    assert zebra.output.out_2.get() == AND3
    assert zebra.pc.pulse_width.get() == exposure_time / 2

    assert zebra.pc.pulse_step.get() == exposure_time + 0.0001


def test_reset_pc_gate_and_pulse(zebra: Zebra, RE):
    RE(reset_pc_gate_and_pulse(zebra))

    assert zebra.pc.gate_start.get() == 0
    assert zebra.pc.pulse_width.get() == 0
    assert zebra.pc.pulse_step.get() == 0


def test_reset_output_panel(zebra: Zebra, RE):
    RE(reset_output_panel(zebra))

    assert zebra.output.out_2.get() == PC_GATE
    assert zebra.output.out_4.get() == OR1
    assert zebra.output.pulse_1.input.get() == DISCONNECT
    assert zebra.output.pulse_2.input.get() == DISCONNECT


def test_zebra_return_to_normal(zebra: Zebra, RE):
    RE(zebra_return_to_normal_plan(zebra, wait=True))

    assert zebra.pc.reset.get() == 1
    assert (
        zebra.pc.gate_source.get() == PC_GATE_SOURCE_POSITION
        and zebra.pc.pulse_source.get() == PC_PULSE_SOURCE_POSITION
    )
    assert zebra.pc.gate_trigger.get() == "Enc2"
    assert zebra.pc.gate_start.get() == 0

    assert zebra.output.out_3.get() == DISCONNECT
    assert zebra.output.pulse_1.input.get() == DISCONNECT


def test_reset_zebra_plan(zebra: Zebra, RE):
    RE(reset_zebra_when_collection_done_plan(zebra))

    assert zebra.inputs.soft_in_2.get() == DISCONNECT
    assert not zebra.pc.is_armed()
