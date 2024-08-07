Roadmap
-------

For a closer look at the ongoing work: `I24ssx
board <https://github.com/orgs/DiamondLightSource/projects/10/views/2>`__

Ongoing list of things needed:

1. Solution for enabling users to run mx_bluesky instead of old scripts:
   blocked by permission issues. Preferred solution would be run on
   beamline kubernetes cluster - in the meantime also loooking into
   procserv as a possibility. (Fixing this should also allow us to stop
   using the Pilatus to make directories during an Eiger collection.)
   Temporary workaround in place for beamline staff, who should be
   starting to run this for testing/in house beamtimes.
2. Convert detector set up to use bluesky plans and ophyd_async devices.
   Investigate using the existing Pilatus in ophyd_async which writes
   HDF5 instead of CBFs (may want to make a CBF-writing Pilatus).
3. Start looking into moving away from edm screens towards a web-based
   GUI.
4. Improve alignment of chip: get it to work correctly for multiple
   zooms.

(TBC…)

+---------------------------------------+----------------+---------------------------------+
|             Work Ongoing              | Rough Timeline |            Completed            |
+=======================================+================+=================================+
| Document how to set up the current    | Ongoing        | :material-regular:`pending;2em` |
| visit, deploy the edm screens and run |                |                                 |
| a simple collection                   |                |                                 |
+---------------------------------------+----------------+---------------------------------+
| Chip collections using bluesky        | Jan./Feb. 24   | :material-regular:`pending;2em` |
+---------------------------------------+----------------+---------------------------------+
| Extruder collections using bluesky    | Feb. 24        | :material-regular:`pending;2em` |
+---------------------------------------+----------------+---------------------------------+
| Create an Ophyd device for the        | Jan. 24        | :material-regular:`pending;2em` |
| Pilatus detector and use it, along    |                |                                 |
| with the Eiger device, to collect     |                |                                 |
| data                                  |                |                                 |
+---------------------------------------+----------------+---------------------------------+
| Start using Ophyd devices for the     | 15th Dec. 23   | :material-regular:`check;2em`   |
| set up tasks - eg. zebra              |                |                                 |
+---------------------------------------+----------------+---------------------------------+
| Use a plan to find the fiducials      | 15th Dec. 23   | :material-regular:`check;2em`   |
+---------------------------------------+----------------+---------------------------------+
| Create an Ophyd device for for the    | 1st Dec. 23    |                                 |
| pmac and use it to move the chip      |                | :material-regular:`check;2em`   |
| stages                                |                |                                 |
+---------------------------------------+----------------+---------------------------------+
| Set up a first bluesky plan to move   | 15th Nov. 23   |                                 |
| the detector stage and set up the     |                | :material-regular:`check;2em`   |
| detector in use                       |                |                                 |
+---------------------------------------+----------------+---------------------------------+
| Come up with a first parameter        | 1st Dec 23     |                                 |
| model                                 |                | :material-regular:`check;2em`   |
+---------------------------------------+----------------+---------------------------------+
| Start sending logs to graylog         | Nov. 23        | :material-regular:`check;2em`   |
+---------------------------------------+----------------+---------------------------------+
| Permissions issues - run as a service | Dec. 23        | :material-regular:`check;2em`   |
+---------------------------------------+----------------+---------------------------------+
| Deploy a first version of MX_BLUESKY  | Nov. 23        |                                 |
| with the current iteration - tested   |                | :material-regular:`check;2em`   |
| on the beamline - of the serial       |                |                                 |
| tools. Set up a ``module load`` that  |                |                                 |
| they can use it for ssx data          |                |                                 |
| collections.                          |                |                                 |
+---------------------------------------+----------------+---------------------------------+
| Generic deployment for edm screens    | Summer 23      | :material-regular:`check;2em`   |
+---------------------------------------+----------------+---------------------------------+
| Tidy up original code and add some    | Summer 23      | :material-regular:`check;2em`   |
| tests                                 |                |                                 |
+---------------------------------------+----------------+---------------------------------+

--------------

Experiment types required
=========================

-  Extruder

   -  Standard
   -  Pump probe

-  Fixed target (probably about 80-85% of serial on I24)

   -  Standard chip collection – option for multiple exposures in each
      spot
   -  Pump probe - see for short description
      https://confluence.diamond.ac.uk/display/MXTech/Dynamics+and+fixed+targets

      -  Short delays
      -  Excite and visit again
      -  Long delays with fs opening/closing

-  (Future) Fixed target with rotation at each “window” (Preliminary
   work done by beamline staff on the PMAC program
   https://confluence.diamond.ac.uk/display/MXTech/Grids+with+rotations)

Details of zebra settings for each type:
https://confluence.diamond.ac.uk/display/MXTech/Zebra+settings+I24

Note that most of the set up for the fixed target is actually done by
the PMAC via PMAC strings.