import argparse
import os
import re
import subprocess
from typing import NamedTuple
from uuid import uuid1

from create_venv import setup_venv
from git import Repo
from packaging.version import VERSION_PATTERN, Version

recognised_beamlines = ["dev", "i03", "i04"]

VERSION_PATTERN_COMPILED = re.compile(
    f"^{VERSION_PATTERN}$", re.VERBOSE | re.IGNORECASE
)

DEV_DEPLOY_LOCATION = "/scratch/30day_tmp/hyperion_release_test/bluesky"


class Options(NamedTuple):
    release_dir: str
    kubernetes: bool = False
    print_release_dir: bool = False
    quiet: bool = False


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

        if not options.quiet:
            print(f"Found {self.name}_versions:\n{os.linesep.join(self.versions)}")

        self.latest_version_str = self.versions[0]

    def deploy(self):
        print(f"Cloning latest version {self.name} into {self.deploy_location}")

        deploy_repo = Repo.init(self.deploy_location)
        deploy_origin = deploy_repo.create_remote("origin", self.origin.url)

        deploy_origin.fetch()
        deploy_origin.fetch("refs/tags/*:refs/tags/*")
        deploy_repo.git.checkout(self.latest_version_str)

        print("Setting permissions")
        groups_to_give_permission = ["i03_staff", "gda2", "dls_dasc"]
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


# Get the release directory based off the beamline and the latest hyperion version
def _parse_options() -> Options:
    parser = argparse.ArgumentParser(
        prog="deploy_hyperion", description="Deploy hyperion to a beamline"
    )
    parser.add_argument(
        "--kubernetes",
        action=argparse.BooleanOptionalAction,
        help="Prepare git workspaces for deployment to kubernetes; do not install virtual environment",
    )
    parser.add_argument(
        "beamline",
        type=str,
        choices=recognised_beamlines,
        help=f"The beamline to deploy hyperion to. 'dev' installs to {DEV_DEPLOY_LOCATION}",
    )
    parser.add_argument(
        "--print-release-dir",
        action=argparse.BooleanOptionalAction,
        help="Print the path to the release folder and then exit",
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
    )


def _create_environment_from_control_machine(
    hyperion_repo, path_to_create_venv, path_to_dls_dev_env
):
    try:
        user = os.environ["USER"]
    except KeyError:
        user = input(
            "Couldn't find username from the environment. Enter FedID in order to SSH to control machine:"
        )
    cmd = f"ssh {user}@i03-control python3 {path_to_create_venv} {path_to_dls_dev_env} {hyperion_repo.deploy_location}"

    process = None
    try:
        # Call python script on i03-control to create the environment
        process = subprocess.Popen(
            cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE
        )
        stdout, stderr = process.communicate()
        if process.returncode != 0:
            print(f"Error occurred: {stderr.decode()}")
        else:
            print(f"Output: {stdout.decode()}")
    except Exception as e:
        print(f"Exception while trying to install venv on i03-control: {e}")
    finally:
        if process:
            process.kill()


def main(options: Options):
    release_area = options.release_dir
    this_repo_top = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))

    if not options.quiet:
        print(f"Repo top is {this_repo_top}")

    hyperion_repo = Deployment(
        name="hyperion", repo_args=os.path.join(this_repo_top, ".git"), options=options
    )

    if hyperion_repo.name != "hyperion":
        raise ValueError("This function should only be used with the hyperion repo")

    release_area_version = os.path.join(
        release_area, f"mx_bluesky_{hyperion_repo.latest_version_str}"
    )

    if options.print_release_dir:
        print(release_area_version)
        return

    print(f"Putting releases into {release_area_version}")

    dodal_repo = Deployment(
        name="dodal",
        repo_args=os.path.join(this_repo_top, "../dodal/.git"),
        options=options,
    )

    dodal_repo.set_deploy_location(release_area_version)
    hyperion_repo.set_deploy_location(release_area_version)

    # Deploy hyperion repo
    hyperion_repo.deploy()

    # Now deploy the correct version of dodal
    dodal_repo.deploy()

    if not options.kubernetes:
        if hyperion_repo.name == "hyperion":
            path_to_dls_dev_env = os.path.join(
                hyperion_repo.deploy_location, "utility_scripts/dls_dev_env.sh"
            )
            path_to_create_venv = os.path.join(
                hyperion_repo.deploy_location, "utility_scripts/deploy/create_venv.py"
            )

            # SSH into control machine if not in dev mode
            if release_area != DEV_DEPLOY_LOCATION:
                _create_environment_from_control_machine(
                    hyperion_repo, path_to_create_venv, path_to_dls_dev_env
                )
            else:
                setup_venv(path_to_create_venv, hyperion_repo.deploy_location)

    def create_symlink_by_tmp_and_rename(dirname, target, linkname):
        tmp_name = str(uuid1())
        target_path = os.path.join(dirname, target)
        linkname_path = os.path.join(dirname, linkname)
        tmp_path = os.path.join(dirname, tmp_name)
        os.symlink(target_path, tmp_path)
        os.rename(tmp_path, linkname_path)

    move_symlink = input(
        """Move symlink (y/n)? WARNING: this will affect the running version!
Only do so if you have informed the beamline scientist and you're sure Hyperion is not running.
"""
    )
    # Creates symlinks: software/bluesky/hyperion_latest -> software/bluesky/hyperion_{version}/hyperion
    #                   software/bluesky/hyperion -> software/bluesky/hyperion_latest
    if move_symlink == "y":
        old_live_location = os.path.relpath(
            os.path.realpath(os.path.join(release_area, "hyperion")), release_area
        )
        make_live_stable_symlink = input(
            f"The last live deployment was {old_live_location}, do you want to set this as the stable version? (y/n)"
        )
        if make_live_stable_symlink == "y":
            create_symlink_by_tmp_and_rename(
                release_area, old_live_location, "hyperion_stable"
            )

        relative_deploy_loc = os.path.join(
            os.path.relpath(hyperion_repo.deploy_location, release_area)
        )
        create_symlink_by_tmp_and_rename(
            release_area, relative_deploy_loc, "hyperion_latest"
        )
        create_symlink_by_tmp_and_rename(release_area, "hyperion_latest", "hyperion")
        print(f"New version moved to {hyperion_repo.deploy_location}")
        print("To start this version run hyperion_restart from the beamline's GDA")
    else:
        print("Quitting without latest version being updated")


if __name__ == "__main__":
    # Gives path to /bluesky
    options = _parse_options()
    main(options)
