"""
Deploy latest release of mx-bluesky either on a beamline or in dev mode.
"""

import argparse
from typing import NamedTuple

help_message = """
To deploy mx_bluesky on a specific beamline, pass only the --beamline argument.
This will put the latest release in /dls_sw/ixx/software/bluesky/mx_bluesky_v#.#.# and \
set the permissions accordingly. \n
To run in dev mode instead, only the --dev-path should be passed, a test release will \
be placed in {dev_path}/mxbluesky_release_test/bluesky. \n
Finally, if both a --beamline and a --dev-path are specified, a beamline-specific test \
deployment will be put in the test directory.
"""  # TODO change

recognised_beamlines = ["dev", "i03", "i04", "i24"]

DEV_DEPLOY_LOCATION = "/scratch/30day_tmp/hyperion_release_test/bluesky"


class Options(NamedTuple):
    release_dir: str
    kubernetes: bool = False
    print_release_dir: bool = False
    quiet: bool = False
    use_control_machine: bool = (
        True  # NOTE For i24 for now will need to set it to false, or viceversa
    )


# Get the release directory based off the beamline and the latest hyperion version
def _parse_options() -> Options:
    parser = argparse.ArgumentParser(
        formatter_class=argparse.RawTextHelpFormatter,
        prog="deploy_mx_bluesky",
        description=__doc__,
        epilog=help_message,
    )
    parser.add_argument(
        "beamline",
        type=str,
        choices=recognised_beamlines,
        help=f"The beamline to deploy hyperion to. 'dev' installs to {DEV_DEPLOY_LOCATION}",
    )
    parser.add_argument(
        "--kubernetes",
        action=argparse.BooleanOptionalAction,
        help="Prepare git workspaces for deployment to kubernetes; do not install virtual environment",
    )
    parser.add_argument(
        "--print-release-dir",
        action=argparse.BooleanOptionalAction,
        help="Print the path to the release folder and then exit",
    )
    parser.add_argument(
        "-c",
        "--control",
        action=argparse.BooleanOptionalAction,
        help="Create environment from the control machine.",
    )
    args = parser.parse_args()
    if args.beamline == "dev":
        print("Running as dev")
        release_dir = DEV_DEPLOY_LOCATION
    else:
        release_dir = f"/dls_sw/{args.beamline}/software/bluesky"

    return Options(
        release_dir=release_dir,
        kubernetes=args.kubernetes,
        print_release_dir=args.print_release_dir,
        quiet=args.print_release_dir,
        use_control_machine=args.control,
    )


if __name__ == "__main__":
    options = _parse_options()
