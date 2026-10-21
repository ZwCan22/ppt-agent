"""Run the local acceptance checks; never starts production or runs a model."""
import argparse
from pathlib import Path
import shutil
import subprocess
import sys

PROJECT = Path(__file__).resolve().parents[1]


def run(title, command, directory):
    print(f"\n=== {title} ===", flush=True)
    result = subprocess.run(command, cwd=directory)
    if result.returncode:
        raise SystemExit(result.returncode)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--frontend", action="store_true", help="Also run frontend type checking and build")
    args = parser.parse_args()
    for folder, title in (("tests", "Backend unit tests"), ("integration_tests", "PostgreSQL integration tests")):
        run(title, [sys.executable, "-B", "-m", "unittest", "discover", "-s", folder, "-t", ".", "-v"], PROJECT / "backend")
    if args.frontend:
        npm = shutil.which("npm.cmd" if sys.platform == "win32" else "npm")
        if not npm:
            raise SystemExit("Node.js/npm was not found")
        run("Frontend type check and build", [npm, "run", "build"], PROJECT / "frontend")
    print("\nPASS: all requested checks completed", flush=True)


if __name__ == "__main__":
    main()
