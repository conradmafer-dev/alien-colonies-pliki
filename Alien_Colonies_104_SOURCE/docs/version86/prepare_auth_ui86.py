#!/usr/bin/env python3
"""Copy release86 dependencies into an isolated project and run offline UI checks."""

import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import zipfile


FIXTURE_FILES = {
    "test_auth86.gd", "TestHost.gd", "FakeGoogle.gd", "FakeEmail.gd",
    "project.godot", "test_auth86.tscn",
}
ASSETS = (
    "alien_colonies_portrait.png", "alien_colonies_icon.png", "google_signin_g.png",
)


def main():
    here = Path(__file__).resolve().parent
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--godot", required=True, help="Godot 4.5.1 executable path or command")
    parser.add_argument("--source", type=Path, default=here.parent.parent,
                        help="Source86 directory (default: package containing this script)")
    parser.add_argument("--work-dir", type=Path,
                        help="New/empty isolated work directory (default: a temporary directory)")
    args = parser.parse_args()
    source = args.source.resolve()
    godot = shutil.which(args.godot)
    if godot is None and Path(args.godot).is_file():
        godot = str(Path(args.godot).resolve())
    if godot is None:
        parser.error("Godot executable not found")

    # Validate the source actually corresponds to the accompanying PASS report.
    freeze = json.loads((here / "client_freeze86.json").read_text(encoding="utf-8"))
    for relative, expected in freeze["files"].items():
        path = source / relative
        if not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest() != expected:
            parser.error("Source differs from the validated release86 file: " + relative)

    work = args.work_dir.resolve() if args.work_dir else Path(tempfile.mkdtemp(prefix="alien_auth86_"))
    if work.exists() and any(work.iterdir()):
        parser.error("--work-dir must be empty; no existing project will be overwritten")
    if work == source or source in work.parents:
        parser.error("Choose --work-dir outside the source package")
    work.mkdir(parents=True, exist_ok=True)
    project = work / "ui_project"
    project.mkdir()

    # No .godot cache, Android build tree, private state, server configuration,
    # backend, account credentials, full art library, or entire source duplicate.
    for relative in ("client/scripts", "localization"):
        shutil.copytree(source / relative, project / relative)
    for path in (source / "addons").rglob("*.gd"):
        target = project / path.relative_to(source)
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, target)
    for name in ASSETS:
        target = project / "client/assets" / name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source / "client/assets" / name, target)
    with zipfile.ZipFile(here / "auth_ui86_fixture.zip") as archive:
        if set(archive.namelist()) != FIXTURE_FILES or archive.testzip() is not None:
            raise SystemExit("Unexpected or damaged test fixture archive")
        for name in sorted(FIXTURE_FILES):
            (project / name).write_bytes(archive.read(name))

    environment = os.environ.copy()
    report = work / "auth_ui86_report.json"
    environment["AC_AUTH86_REPORT_PATH"] = str(report)
    commands = (
        ("auth_ui86_import.log", [godot, "--headless", "--editor", "--import", "--path", str(project)]),
        ("auth_ui86_runtime.log", [godot, "--headless", "--path", str(project)]),
    )
    print("Isolated test directory:", work, flush=True)
    for log_name, command in commands:
        with (work / log_name).open("w", encoding="utf-8") as log:
            completed = subprocess.run(command, env=environment, stdout=log, stderr=subprocess.STDOUT,
                                       cwd=project, check=False)
        if completed.returncode != 0:
            raise SystemExit("Godot failed; see " + str(work / log_name))
    result = json.loads(report.read_text(encoding="utf-8"))
    if result["failures"] or result["checks"] != 1796:
        raise SystemExit("Unexpected test results; see " + str(report))
    print("PASS: 1796 checks, 0 failures. Report:", report)


if __name__ == "__main__":
    main()
