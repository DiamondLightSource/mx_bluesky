from argparse import ArgumentParser

from mx_bluesky.example import run_plan

from . import __version__

__all__ = ["main"]


def main(args=None):
    parser = ArgumentParser()
    parser.add_argument("-v", "--version", action="version", version=__version__)
    args = parser.parse_args(args)
    run_plan()


# test with: python -m mx_bluesky
if __name__ == "__main__":
    main()
