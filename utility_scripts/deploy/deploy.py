"""
Deploy latest release of mx-bluesky either on a beamline or in dev mode.
"""

import argparse
import os
import re
from typing import NamedTuple

from git import Repo
from packaging.version import VERSION_PATTERN, Version

help_message = """
To deploy mx_bluesky on a specific beamline, pass only the --beamline argument.
This will put the latest release in /dls_sw/ixx/software/bluesky/mx_bluesky_v#.#.# and \
set the permissions accordingly. \n
To run in dev mode instead, only the --dev-path should be passed, a test release will \
be placed in {dev_path}/mxbluesky_release_test/bluesky. \n
Finally, if both a --beamline and a --dev-path are specified, a beamline-specific test \
deployment will be put in the test directory.
"""  # TODO change

recognised_beamlines = ["i03", "i04", "i24"]

VERSION_PATTERN_COMPILED = re.compile(
    f"^{VERSION_PATTERN}$", re.VERBOSE | re.IGNORECASE
)

DEV_DEPLOY_LOCATION = "/scratch/30day_tmp/hyperion_release_test/bluesky"


class Options(NamedTuple):
    release_dir: str
    kubernetes: bool = False
    print_release_dir: bool = False
    quiet: bool = False
    dev_mode: bool = False
    use_control_machine: bool = True
    # NOTE For i24 for now will need to set it to false from the command line


class Deployment:
    # Set name, setup remote origin, get the latest version"""
    def __init__(self, name: str, repo_args, options: Options):
        self.name = name
        self.repo = Repo(repo_args)

        self.origin = self.repo.remotes.origin
        self.origin.fetch()
        self.origin.fetch("refs/tags/*:refs/tags/*")

        self.versions = [
            t.name for t in self.repo.tags if VERSION_PATTERN_COMPILED.match(t.name)
        ]
        self.versions.sort(key=Version, reverse=True)

        self.options = options
        if not self.options.quiet:
            print(f"Found {self.name}_versions:\n{os.linesep.join(self.versions)}")

        self.latest_version_str = self.versions[0]

    def deploy(self, beamline: str):
        print(f"Cloning latest version {self.name} into {self.deploy_location}")

        deploy_repo = Repo.init(self.deploy_location)
        deploy_origin = deploy_repo.create_remote("origin", self.origin.url)

        deploy_origin.fetch()
        deploy_origin.fetch("refs/tags/*:refs/tags/*")
        deploy_repo.git.checkout(self.latest_version_str)

        print("Setting permissions")
        groups_to_give_permission = get_permission_groups(
            beamline, self.options.dev_mode
        )
        setfacl_params = ",".join(
            [f"g:{group}:rwx" for group in groups_to_give_permission]
        )

        # Set permissions and defaults
        os.system(f"setfacl -R -m {setfacl_params} {self.deploy_location}")
        os.system(f"setfacl -dR -m {setfacl_params} {self.deploy_location}")

    # Deploy location depends on the latest hyperion version (...software/bluesky/hyperion_V...)
    def set_deploy_location(self, release_area):
        self.deploy_location = os.path.join(release_area, self.name)
        if os.path.isdir(self.deploy_location):
            raise Exception(
                f"{self.deploy_location} already exists, stopping deployment for {self.name}"
            )


# Get permission groups depending on beamline/dev install
def get_permission_groups(beamline: str, dev_mode: bool = False) -> list:
    beamline_groups = ["gda2", "dls_dasc"]
    if not dev_mode:
        beamline_groups.append(f"{beamline}_staff")
    return beamline_groups


def main(beamline: str, options: Options):
    print(beamline)
    print(options)


# Get the release directory based off the beamline and the latest mx-bluesky version
def _parse_options() -> tuple[str, Options]:
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
        help="The beamline to deploy mx_bluesky to.",
    )
    parser.add_argument(
        "--dev",
        action="store_true",
        help=f"Test deployment in dev mode, install to {DEV_DEPLOY_LOCATION}.",
    )
    parser.add_argument(
        "--kubernetes",
        action="store_true",
        help="Prepare git workspaces for deployment to kubernetes; do not install virtual environment.",
    )
    parser.add_argument(
        "--print-release-dir",
        action="store_true",
        help="Print the path to the release folder and then exit.",
    )
    parser.add_argument(
        "-nc",
        "--no-control",
        action="store_false",
        help="Create environment from the control machine.",
    )
    args = parser.parse_args()
    if args.dev:
        print("Running as dev")
        release_dir = DEV_DEPLOY_LOCATION
    else:
        release_dir = f"/dls_sw/{args.beamline}/software/bluesky"

    return args.beamline, Options(
        release_dir=release_dir,
        kubernetes=args.kubernetes,
        print_release_dir=args.print_release_dir,
        quiet=args.print_release_dir,
        dev_mode=args.dev,
        use_control_machine=args.no_control,
    )


if __name__ == "__main__":
    beamline, options = _parse_options()
    main(beamline, options)
