Deploy a New Release
-----------------------

**Remember to discuss any new deployments with the appropriate beamline scientist.**

The ``/deploy/deploy_mxbluesky.py`` script will deploy the latest Hyperion version to a specified beamline. Deployments live in ``/dls_sw/ixx/software/bluesky/mx-bluesky_vXXX``. To do a new deployment you should run the deploy script from your mx-bluesky dev environment with e.g.

``python ./deploy/deploy_mxbluesky.py --beamline i24``


If you want to test the script you can run:

``python ./deploy/deploy_mxbluesky.py --dev-path /your-path/``

and a released version will be put in ``/your-path/mxbluesky_release_test``.

If you need a specific beamline test deployment you can also run:

``python ./deploy/deploy_mxbluesky.py --beamline i24 --dev-path /your-path/``

which will create the beamline deployment (eg. I24) in the specified test directory ``/your-path/mxbluesky_release_test``.


**Note:** When deploying on I24, the edm screens for serial crystallography will be deployed automatically along with the mx-bluesky release. 
When running a ``dev`` deployment instead, `this script <https://github.com/DiamondLightSource/mx-bluesky/wiki/Serial-Crystallography-on-I24#deploying-a-local-version-of-the-edm-screens>`_ will also need to be run to get the latest version of the screens.
