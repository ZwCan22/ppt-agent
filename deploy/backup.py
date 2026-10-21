"""Local data backup for this project's single-host Docker Compose deployment.

Run through backup.cmd. No third-party Python packages are required.
Only API/Worker containers managed by this Compose file are coordinated.
"""

import argparse
from contextlib import contextmanager, ExitStack
from datetime import datetime, timezone
from hashlib import sha256
import json
import os
from pathlib import Path, PurePosixPath, PureWindowsPath
import shutil
import subprocess
import sys
from uuid import uuid4


BUSY_SQL = (
    "SELECT count(*) FROM public.ppt_tasks "
    "WHERE status IN ('queued','planning','rendering','checking');"
)
INVENTORY_SQL = """
SELECT json_build_object(
    'task_count', count(*),
    'busy_count', count(*) FILTER (
        WHERE status IN ('queued','planning','rendering','checking')),
    'succeeded_count', count(*) FILTER (WHERE status = 'succeeded'),
    'artifact_paths', coalesce(json_agg(artifact_path) FILTER (
        WHERE status = 'succeeded'), '[]'::json)
) FROM public.ppt_tasks;
"""


class BackupError(RuntimeError):
    pass


def utc_now():
    return datetime.now(timezone.utc).isoformat()


class Compose:
    """Use argument lists, never shell-built commands or printed credentials."""

    def __init__(self, root):
        self.root = root
        docker = shutil.which("docker")
        if not docker:
            raise BackupError("Docker CLI not found. Start Docker Desktop and check PATH.")
        self.prefix = [docker, "compose", "--env-file", "deploy/.env", "-f", "deploy/compose.yml"]

    def call(self, args, *, output_file=None, input_file=None, timeout=60):
        with ExitStack() as stack:
            output = stack.enter_context(output_file.open("xb")) if output_file else subprocess.PIPE
            source = stack.enter_context(input_file.open("rb")) if input_file else subprocess.DEVNULL
            try:
                result = subprocess.run(
                    self.prefix + list(args), cwd=self.root, stdin=source,
                    stdout=output, stderr=subprocess.PIPE, timeout=timeout,
                    check=False, shell=False,
                )
            except (OSError, subprocess.TimeoutExpired) as exc:
                raise BackupError(f"Docker operation failed: {args[0]} ({type(exc).__name__}).") from exc
        if result.returncode:
            # Compose/DB stderr can contain private configuration; do not print it.
            raise BackupError(f"Docker operation failed: {args[0]} (exit {result.returncode}).")
        return result.stdout.decode("utf-8") if result.stdout is not None else ""


def sql(compose, query):
    return compose.call([
        "exec", "-T", "postgres", "psql", "-X", "-U", "ppt_admin",
        "-d", "ppt_agent", "-v", "ON_ERROR_STOP=1", "-At", "-c", query,
    ]).strip()


def service_states(compose):
    raw = compose.call(["ps", "--all", "--format", "json"]).strip()
    if raw.startswith("["):
        rows = json.loads(raw)
    else:
        rows = [json.loads(line) for line in raw.splitlines() if line.strip()]
    states = {}
    for service in ("postgres", "api", "worker"):
        matches = [row for row in rows if row.get("Service") == service]
        if len(matches) != 1:
            raise BackupError(f"Expected one existing {service} container. Run deploy\\start.cmd first.")
        state = matches[0].get("State")
        if state not in ("running", "exited", "created"):
            raise BackupError(f"Container {service} has unsupported state: {state!r}.")
        states[service] = state
    if states["postgres"] != "running":
        raise BackupError("PostgreSQL must already be running.")
    return states


def require_idle(compose):
    count = int(sql(compose, BUSY_SQL))
    if count:
        raise BackupError(f"There are {count} queued/active tasks. Wait for them to finish, then retry.")


@contextmanager
def backup_lock(directory):
    """A second backup process must not restart services during the first copy."""
    lock = directory / ".backup.lock"
    try:
        stream = lock.open("x", encoding="ascii")
    except FileExistsError as exc:
        raise BackupError("Backup lock exists. Check for another backup process before removing it.") from exc
    try:
        with stream:
            stream.write(str(os.getpid()))
        yield
    finally:
        lock.unlink(missing_ok=True)


def reject_link(path):
    if path.is_symlink() or path.is_junction():
        raise BackupError("Storage must not contain symbolic links or directory junctions.")


def digest(path):
    with path.open("rb") as stream:
        return sha256_stream(stream)


def sha256_stream(stream):
    checksum = sha256()
    for block in iter(lambda: stream.read(1024 * 1024), b""):
        checksum.update(block)
    return checksum.hexdigest()


def copy_storage(source, destination):
    reject_link(source)
    destination.mkdir()
    files = []
    for current, folders, names in os.walk(source, followlinks=False, onerror=_walk_error):
        current = Path(current)
        for name in sorted(folders):
            reject_link(current / name)
            (destination / (current / name).relative_to(source)).mkdir()
        for name in sorted(names):
            original = current / name
            reject_link(original)
            if not original.is_file():
                raise BackupError("Storage contains an unsupported file type.")
            relative = original.relative_to(source)
            copied = destination / relative
            shutil.copy2(original, copied)
            original_hash, copied_hash = digest(original), digest(copied)
            if original_hash != copied_hash:
                raise BackupError("A storage file changed or was corrupted during copying.")
            files.append({"path": relative.as_posix(), "size": copied.stat().st_size, "sha256": copied_hash})
    return sorted(files, key=lambda item: item["path"])


def _walk_error(error):
    raise error


def verify_references(paths, files):
    available = {item["path"] for item in files}
    for value in paths:
        if not isinstance(value, str) or not value.strip():
            raise BackupError("A succeeded task has no valid artifact_path.")
        path = value.replace("\\", "/")
        windows = PureWindowsPath(path)
        parts = PurePosixPath(path).parts
        if windows.drive or windows.root or ".." in parts or ":" in path:
            raise BackupError("An artifact_path is absolute or escapes storage; review the task record.")
        if PurePosixPath(path).as_posix() not in available:
            raise BackupError("A succeeded task references a file missing from the storage backup.")


def save_manifest(bundle, manifest):
    temporary = bundle / "manifest.json.tmp"
    temporary.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temporary.replace(bundle / "manifest.json")


def run_backup(root, compose, *, check_only=False):
    """Return a new completed bundle; raise on any failed stage or restart."""
    for relative in ("deploy/.env", "deploy/compose.yml"):
        if not (root / relative).is_file():
            raise BackupError(f"Required project file missing: {relative}.")
    source = root / "backend" / "storage"
    if not source.is_dir():
        raise BackupError("backend/storage does not exist.")
    reject_link(source)
    backups = root / "backups"
    backups.mkdir(exist_ok=True)
    reject_link(backups)
    with backup_lock(backups):
        print("[1/6] Checking containers, database and pending tasks...", flush=True)
        compose.call(["config", "--quiet"])
        states = service_states(compose)
        require_idle(compose)
        if check_only:
            print("[PASS] Preflight passed. No services stopped; no backup created.")
            return None

        backup_id = "data-" + datetime.now().strftime("%Y%m%d-%H%M%S-") + uuid4().hex[:8]
        bundle = backups / (backup_id + ".incomplete")
        bundle.mkdir()
        manifest = {
            "format_version": 1, "backup_id": backup_id,
            "scope": "ppt_agent database and backend/storage only",
            "status": "in_progress", "started_at": utc_now(),
            "services_initially_running": [s for s in ("api", "worker") if states[s] == "running"],
            "services_restored": False,
            "restore_tested": False,
        }
        resume = []
        failure = None
        restart_errors = []
        try:
            save_manifest(bundle, manifest)
            print("[2/6] Pausing API; rechecking tasks; pausing Worker...", flush=True)
            if states["api"] == "running":
                resume.append("api")  # Register BEFORE stopping, including a partially failed stop.
                compose.call(["stop", "api"], timeout=90)
            require_idle(compose)  # Catch submissions accepted just before API shutdown.
            if states["worker"] == "running":
                resume.append("worker")
                compose.call(["stop", "worker"], timeout=90)

            inventory = json.loads(sql(compose, INVENTORY_SQL))
            if inventory["busy_count"]:
                raise BackupError("Tasks appeared during the pause. Check for another API/Worker process.")
            manifest["task_count"] = inventory["task_count"]
            manifest["succeeded_task_count"] = inventory["succeeded_count"]
            print("[3/6] Exporting database and checking the archive...", flush=True)
            archive = bundle / "database.dump"
            compose.call([
                "exec", "-T", "postgres", "pg_dump", "-U", "ppt_admin", "-d", "ppt_agent", "-Fc",
            ], output_file=archive, timeout=300)
            with archive.open("rb") as stream:
                if stream.read(5) != b"PGDMP":
                    raise BackupError("Database export is not a PostgreSQL custom archive.")
            # Parse all archived data into SQL without executing it or restoring any database.
            compose.call([
                "exec", "-T", "postgres", "pg_restore", "--file=/dev/null",
            ], input_file=archive, timeout=300)
            manifest["database"] = {"path": "database.dump", "size": archive.stat().st_size, "sha256": digest(archive)}
            print("[4/6] Copying storage and comparing SHA-256 checksums...", flush=True)
            files = copy_storage(source, bundle / "storage")
            manifest["storage_files"] = files
            print("[5/6] Checking files referenced by every succeeded task...", flush=True)
            verify_references(inventory["artifact_paths"], files)
            manifest["data_checked_at"] = utc_now()
        except (Exception, KeyboardInterrupt) as exc:
            failure = exc
        finally:
            print("[6/6] Restoring services that this backup paused...", flush=True)
            for service in resume:
                try:
                    compose.call(["start", "--wait", "--wait-timeout", "90", service], timeout=110)
                except (Exception, KeyboardInterrupt):
                    restart_errors.append(service)
            manifest["services_restored"] = not restart_errors
            manifest["finished_at"] = utc_now()
            manifest["status"] = "failed" if failure or restart_errors else "completed"
            if failure:
                # Store a safe category, not arbitrary exception text containing private values.
                manifest["error_type"] = type(failure).__name__
            if restart_errors:
                manifest["restart_failed_services"] = restart_errors
            save_manifest(bundle, manifest)
        if restart_errors:
            raise BackupError("Service restart failed. Run deploy\\start.cmd; keep the .incomplete folder for diagnosis.")
        if failure:
            if isinstance(failure, BackupError):
                raise failure
            if isinstance(failure, KeyboardInterrupt):
                raise BackupError("Backup interrupted. Partial files remain in the .incomplete folder.") from failure
            raise BackupError(f"Backup failed ({type(failure).__name__}); partial files kept for diagnosis.") from failure
        completed = backups / backup_id
        bundle.rename(completed)
        print(f"[PASS] Data backup completed: {completed}")
        print(f"[INFO] Tasks: {inventory['task_count']}; copied files: {len(files)}.")
        print("[INFO] This is a local data backup. A database restore drill is still required.")
        return completed


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check-only", action="store_true", help="Check readiness without pausing services or creating a backup.")
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    try:
        run_backup(root, Compose(root), check_only=args.check_only)
    except (Exception, KeyboardInterrupt) as exc:
        message = str(exc) if isinstance(exc, BackupError) else f"Operation failed ({type(exc).__name__})."
        print(f"[FAIL] {message}")
        print("[RECOVERY] If services are unavailable, run deploy\\start.cmd.")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
