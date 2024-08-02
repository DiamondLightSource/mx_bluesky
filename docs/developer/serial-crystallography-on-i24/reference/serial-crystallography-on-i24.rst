Serial Crystallography on I24
-----------------------------

**Note:** this document contains a lot of things which should be split up into smaller documents in their respective categories.

Setting up the environment
~~~~~~~~~~~~~~~~~~~~~~~~~~

To set up an enviroment to run the serial crystallography collection
scripts, please follow the instructions
`here <https://github.com/DiamondLightSource/mx_bluesky/wiki/Getting-started>`__.
Once this is done, the environment can be started by running:

.. code:: bash

   cd /path/to/mx_bluesky
   source .venv/bin/activate

On beamline I24, the package will be saved in
``/dls_sw/i24/software/bluesky``.

Deploying a local version of the EDM screens
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Every time a change is made to the template EDM screens saved in the
repo, a new set should be deployed to the beamline ot to the ``dev``
environment to get the update. The ``deploy_edm_for_ssx.sh`` will create
a local copy of the all EDM screens - both for a fixed target and for a
serial jet collection - in a ``edm_serial/`` directory with all the
shell commands pointing to the correct scripts/edm locations.

.. code:: bash

   ./path/to/mx_bluesky/deploy/deploy_edm_for_ssx.sh

Setting the current visit directory
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

A new visit directory might need to be set before every user or
commissioning beamtime. This can be done by a member of the beamline
staff by modifying the file ``/dls_sw/i24/etc/ssx_current_visit.txt`` to
point to the current visit and then running the command:

.. code:: bash

   ./path/to/mx_bluesky/src/mx_bluesky/I24/serial/set_visit_directory.sh

Note that the default experiment type for the script setting the
directory will be ``fixed-target``. In case of an extruder collection,
to set the correct visit PV the experiment type should be modified from
the command line.

.. code:: bash

   ./path/to/mx_bluesky/src/mx_bluesky/I24/serial/set_visit_directory.sh extruder

--------------

Running a collection
--------------------

Starting the EDM screens
~~~~~~~~~~~~~~~~~~~~~~~~

A couple of entry points have been set up so that:

-  ``run_fixed_target`` starts the edm screens for a fixed target
   collection
-  ``run_extruder`` starts the edm screens for a serial jet collection

Before opening the experiment specific edm, each of these entry points
will start a ``BlueAPI`` server. The configuration used by ``BlueAPI``
is saved in ``src/mx_bluesky/I24/serial/blueapi_config.yaml``.

Detector choice
~~~~~~~~~~~~~~~

The detector currently in use is identified by reading the position of
the detector stage in the y direction. A different detector can be chose
by opening the ``Detector`` tab in the main edm screen, selecting the
detector name from the list and clicking the ``Move Stage`` button,
which will move the detector stage to the correct height and update the
relative PVs.

Detectors available for serial: Pilatus 6M or Eiger CdTe 9M.

Extruder (Serial Jet)
~~~~~~~~~~~~~~~~~~~~~

On startup, once both the visit and the detector have been set up,
**always** press the ``initialise on start`` button, which will autofill
the general purpose PVs for an extruder collection with sensible default
values, as well as the chosen visit directory and detector. Ensure that
the visit shown on the edm screen is correct.

I - **Align Jet**

Open the viewer and switch on the backlight to visualise the jet stream.
You can use the positioners in the ``Align Jet`` panel on the edm screen
to move the orizontal goniometer table and align the jet.

II - **Set experiment parameters**

1. Data collection set up

In the edm screen fill the fields in ``Data Collation Setup`` with
information such as sub-directory, filename, number of images, exposure
time and detector distance. It is recommended to not collect all data
into a single sub-directory but split into multiple smaller collections.

2. Pump Probe

For a pump-probe experiment, select ``True`` on the dropdown menu in
``Data Collection Setup`` and then set the laser dwell and delay times
in the ``Pump Probe`` panel. **WARNING** This setting requires an
hardware change, as there are only 4 outputs on the zebra and they are
all in use. When using the Eiger the Pilatus trigger cable should be
used to trigger the light source. When using the pilatus the eiger
trigger cable should be used.

III - **Run collection**

Once all parameters have been set, press ``Start`` to run the
collection. A stream log will show what is going on in the terminal.

Fixed-Target (Serial Fixed)
~~~~~~~~~~~~~~~~~~~~~~~~~~~

I - **Make coordinate system**

Generally the first thing to do before running a chip collection is to
set up the coordinate system.

Before this step remember to reset the scale and skew factors as well as
the motor directions as needed. Current values are saved in
``src/mx_bluesky/I24/serial/parameters/fixed_target`` in the
``cs_maker.json`` and ``motor_direction.txt`` files.

1. From the main edm screen open the ``viewer`` and ``moveonclick``.
2. Find the first fiducial in the top left corner, centre it and press
   ``set fiducial 0``.
3. Move to Fiducial 1 and 2 and repeat the process.
4. Once all fiducials have been set, press ``make coordianates system``.
   If all worked correctly it will find the first window in the first
   block.
5. Run ``block check`` to check that all blocks are correctly aligned.
   WARNING: ``block check`` is not available for a custom chip.

II - **Select experiment parameters**

1. In the edm screen fill the fields in
   ``Chip and Data Collation Setup`` with information such as
   sub-directory, filename, exposure time and detector distance.

2. Select chip and map type

Select the ``Chip Type`` from the drop-down menu on the edm screen.
Currently available chips: 0. Oxford 1. Oxford Inner 2. Custom 3.
Minichip

When using a non-custom chip ``Map Type`` should always be selected, for
other chips it’s only necessary when wanting to collect only on selected
blocks.

-  For a full-chip collection on an Oxford-type chip, ``Map Type``
   should simply be set to ``None``.
-  For a Custom Chip, click on the ``Custom Chip`` button, which will
   bring up the relative edm. Here, the steps are the following:

   1. Clear Coordinate System. This will reset the coordinates.
   2. Fill in the fields for number of windows and step size in x/y
      direction.
   3. Press ``Set current position as start``.
   4. Once finished, close and return to main screen.

-  For collecting only on specific windows on an Oxford chip:

   1. Set the ``Mapping Type`` to ``Lite``. This will make the Lite
      launchers button visible.
   2. On the launcher, select the blocks to collect - either manually or
      using a preset set.
   3. Run ``Save Screen Map``. This will create a ``currentchip.map``
      file which will be copied to the data directory at collection
      time.
   4. Run ``Upload Parameters``.
   5. Once finished, close and return to main screen.

3. Select pump probe

After setting the exposure time, open ``Pump Probe`` screen from main
edm. The box will appear by selecting one of the settings from the drop
down menu.

-  ``Short1`` and ``Short2``: once opened set the laser dwell and delay
   times.
-  ``Repeat#``: Set laser dwell and press calculate to get the delay
   times for each repeat mode.
-  ``Medium1``: open and close fast shutter between exposures, long
   delays between each one.

Select the most appropriate pump probe setting for your collection and
set the laser dwell and delay times accordingly.

For more details on the pump probe settings see `Dynamics and fixed
targets <https://confluence.diamond.ac.uk/display/MXTech/Dynamics+and+fixed+targets>`__

III - **Save the parameters**

**This step cannot be skipped!**

Once all of the previous steps have been completed - and before running
a collection - all parameters have to be saved using the
``Set parameters`` button so that they can be applied to the collection.
A copy parameter file will be saved along with the chip map (if
applicable) in the data directory at collection time.

IV - **Run a collection**

Once all parameters have been set, press ``Start`` to run the
collection. A stream log will show what is going on in the terminal.

--------------

Stage motor moves using the PMAC device
---------------------------------------

Notes on PMAC coordinate system and motors
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

In a PMAC, motors that should move in a coordinated fashion ware put
into the same coordinate system that can run a motion program. Motors
that should move independently of each other should go into a separate
coordinate system. A coordinate system is established by assigning axes
to motors. The axes allocations defined for the chip stages set up are:

::

   #1->X
   #2->Y
   #3->Z

When an X-axis move is executed, the #1 motor will make the move.
https://github.com/DiamondLightSource/mx_bluesky/wiki/Serial-Crystallography-on-I24#cs_reset-custom-chips
### Use in code

When running chip collections, the stage motors are moved via the `PMAC
device <https://github.com/DiamondLightSource/dodal/blob/main/src/dodal/devices/i24/pmac.py>`__
in a couple of different ways.

1. In most cases, the {x,y,z} motors are moved by sending a command to
   the PMAC as a ``PMAC_STRING``.

   -  Using a JOG command ``J:{const}``, to jog the motor a specified
      distance from the current position. For example, this will move
      motor Y by 10 motor steps:
      ``python      yield from bps.abs_set(pmac.pmac_string, "#2J:10")``

   -  The ``hmz`` strings are homing commands which will reset the
      encoders counts to 0 for the axis. All three motors are homed by
      sending the string: ``#1hmz#2hmz#3hmz``. In the plans this is done
      by triggering the home move:
      ``python       yield from bps.trigger(pmac.home)``

   -  Another pmac_string that can start a move has the format
      ``!x..y..``. This is a command designed to blend any ongoing move
      into a new position. A common one through the serial collection
      code is ``!x0y0z0``, which will start a move to 0 for all motors.
      ``python      yield from bps.trigger(pmac.to_xyz_zero)``

2. The stage motors can also be moved directly through the existing PVs
   ``ME14E-MO-CHIP-01:{X,Y,Z}``, for example:

   .. code:: python

      yield from bps.mv(pmac.x, 0, pmac.y, 1)https://github.com/DiamondLightSource/mx_bluesky/wiki/Serial-Crystallography-on-I24#cs_reset-custom-chips

Notes on the coordinate system for a fixed-target collection
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

CS_MAKER: Oxford-type chips (Oxford, Oxford-Inner, Minichip)
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Generally, the first step before a chip collection is to create the
coordinate system. This is done by first selecting the 3 fiducials on
the and then clicking the ``Make co-ordinate system`` button. This
button runs the ``cs_maker`` plan, which computes the correct
pmac_strings to assign axes values to each motors.

Theory for this computation

::

   Rx: rotation about X-axis, pitch
   Ry: rotation about Y-axis, yaw
   Rz: rotation about Z-axis, roll
   The order of rotation is Roll->Yaw->Pitch (Rx*Ry*Rz)
   Rx           Ry          Rz
   |1  0   0| | Cy  0 Sy| |Cz -Sz 0|   | CyCz        -CxSz         Sy  |
   |0 Cx -Sx|*|  0  1  0|*|Sz  Cz 0| = | SxSyCz+CxSz -SxSySz+CxCz -SxCy|
   |0 Sx  Cx| |-Sy  0 Cy| | 0   0 1|   |-CxSyCz+SxSz  CxSySz+SxCz  CxCy|

   Skew:
   Skew is the difference between the Sz1 and Sz2 after rotation is taken out.
   This should be measured in situ prior to expriment, ie. measure by hand using
   opposite and adjacent RBV after calibration of scale factors.

The plan needs information stored in a few files: \* The motor
directions are stored in
``src/mx_bluesky/I24/serial/parameters/fixed_target/cs/motor_directions.txt. The motor number multiplied by the motor direction should give the positive chip direction. * The scale values for x,y,z, the skew value and the sign of``\ Sx,
Sy,
Sz\ ``are all stored in``\ src/mx_bluesky/I24/serial/parameters/fixed_target/cs/cs_maker.json\ ``* The fiducials 1 and 2 positions are written to file when selecting the fiducials (Setting fiducial 0 instead sends a homing command directly to the``\ pmac_string\`
PV)

NOTE. The ``motor_direction.txt`` and ``cs_maker.json`` files should
only be modified by staff when needed (usually when the stages have been
off for awhile).

CS_RESET: Custom chips
^^^^^^^^^^^^^^^^^^^^^^

When using a Custom chip, open the ``Custom chip`` edm and before doing
anything else click the ``Clear coordinate system`` button. This will
ensure that any pre-existing coordinate system from pre-vious chip
experiments is wiped and reset.

This operation is done by the ``cs_reset`` plan, which sends
instructions to the PMAC device to assign coordinates to each motor via
the following pmac_strings:

::

   "#1->10000X+0Y+0Z"
   "#2->+0X-10000Y+0Z"
   "#3->0X+0Y-10000Z"