#!/usr/bin/env python3
"""FreightMind document trigger — folder watcher.

Monitors an incoming drop directory and automatically submits trade documents
to the verification pipeline, simulating an SU email arriving with attachments.

Directory layout
----------------
  incoming/
    DEMO_CUSTOMER_001/
      invoice.pdf              ← single doc → POST /api/verify/submit/stream
      bundle-2024-03/          ← subdirectory → batch when ≥2 files AND stable
        demo_shipment_CI.pdf
        demo_shipment_BL.pdf
        demo_shipment_PL.pdf

Customer ID is inferred from the first subdirectory level.
Unknown customer IDs default to DEMO_CUSTOMER_001.

On successful submission the file(s) are moved to:
  processed/<customer_id>/<YYYY-MM-DD_HH-MM-SS_filename>

Usage
-----
  # Development (macOS/Linux, native FS events):
  uv run python backend/scripts/folder_watcher.py

  # Docker sidecar (polling fallback because Docker Desktop doesn't relay FSEvents):
  WATCH_POLL=1 uv run python backend/scripts/folder_watcher.py

Environment variables
---------------------
  WATCH_DIR          Path to monitor (default: backend/data/incoming)
  PROCESSED_DIR      Destination for processed files (default: backend/data/processed)
  API_BASE_URL       Backend API URL (default: http://localhost:8000)
  WATCH_POLL         Set to 1 to force polling observer (required inside Docker on macOS)
  BUNDLE_QUIET_SEC   Seconds a bundle dir must be stable before submitting (default: 3)
  CUSTOMER_DEFAULT   Fallback customer ID (default: DEMO_CUSTOMER_001)
"""

from __future__ import annotations

import logging
import os
import shutil
import threading
import time
from datetime import datetime, timezone
from pathlib import Path

import httpx
from watchdog.events import (
    DirCreatedEvent,
    DirModifiedEvent,
    FileCreatedEvent,
    FileSystemEvent,
    FileSystemEventHandler,
)
from watchdog.observers import Observer
from watchdog.observers.polling import PollingObserver

# ── Config ────────────────────────────────────────────────────────────────────

REPO_ROOT = Path(__file__).resolve().parents[2]

WATCH_DIR       = Path(os.environ.get("WATCH_DIR",      REPO_ROOT / "backend" / "data" / "incoming"))
PROCESSED_DIR   = Path(os.environ.get("PROCESSED_DIR",  REPO_ROOT / "backend" / "data" / "processed"))
API_BASE_URL    = os.environ.get("API_BASE_URL",        "http://localhost:8000")
USE_POLLING     = os.environ.get("WATCH_POLL", "").strip() == "1"
BUNDLE_QUIET_SEC = float(os.environ.get("BUNDLE_QUIET_SEC", "3"))
CUSTOMER_DEFAULT = os.environ.get("CUSTOMER_DEFAULT", "DEMO_CUSTOMER_001")

SUPPORTED_EXTS = {".pdf", ".png", ".jpg", ".jpeg"}

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("folder_watcher")


# ── Helpers ───────────────────────────────────────────────────────────────────

def _customer_from_path(path: Path) -> str:
    """Extract customer ID from directory structure.

    Expected:  <WATCH_DIR>/<customer_id>/...
    Falls back to CUSTOMER_DEFAULT.
    """
    try:
        rel = path.relative_to(WATCH_DIR)
        parts = rel.parts
        if parts:
            return parts[0]
    except ValueError:
        pass
    return CUSTOMER_DEFAULT


def _archive(src: Path, customer_id: str) -> Path:
    """Move a processed file to the archive directory."""
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%d_%H-%M-%S")
    dest_dir = PROCESSED_DIR / customer_id
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest = dest_dir / f"{ts}_{src.name}"
    shutil.move(str(src), dest)
    return dest


def _archive_dir(src_dir: Path, customer_id: str) -> None:
    """Move all files in a bundle directory to the archive."""
    for f in src_dir.iterdir():
        if f.is_file() and f.suffix.lower() in SUPPORTED_EXTS:
            _archive(f, customer_id)
    try:
        src_dir.rmdir()  # remove if now empty
    except OSError:
        pass


def _content_type(path: Path) -> str:
    ext = path.suffix.lower()
    return {
        ".pdf":  "application/pdf",
        ".png":  "image/png",
        ".jpg":  "image/jpeg",
        ".jpeg": "image/jpeg",
    }.get(ext, "application/octet-stream")


# ── Submission ────────────────────────────────────────────────────────────────

def submit_single(file_path: Path, customer_id: str) -> None:
    """POST a single file to /api/verify/submit/stream and stream the result."""
    if not file_path.exists():
        return
    logger.info("[SINGLE] Submitting %s for customer %s", file_path.name, customer_id)
    url = f"{API_BASE_URL}/api/verify/submit/stream"
    try:
        with file_path.open("rb") as fh:
            with httpx.stream(
                "POST",
                url,
                files={"file": (file_path.name, fh, _content_type(file_path))},
                data={"customer_id": customer_id},
                timeout=300,
            ) as resp:
                resp.raise_for_status()
                overall_status = None
                for line in resp.iter_lines():
                    if not line.startswith("data: "):
                        continue
                    import json
                    try:
                        evt = json.loads(line[6:])
                    except json.JSONDecodeError:
                        continue
                    if evt.get("type") == "stage":
                        logger.info("  [stage %d] %s", evt.get("step", 0), evt.get("message", ""))
                    elif evt.get("type") == "complete":
                        overall_status = evt.get("overall_status")
                    elif evt.get("type") == "error":
                        logger.error("  [error] %s", evt.get("message"))

        if overall_status:
            logger.info("[SINGLE] ✓ %s → %s", file_path.name, overall_status.upper())
        _archive(file_path, customer_id)

    except httpx.HTTPStatusError as e:
        logger.error("[SINGLE] HTTP %s: %s", e.response.status_code, e.response.text[:200])
    except Exception as e:
        logger.error("[SINGLE] Failed: %s", e)


def submit_batch(bundle_dir: Path, customer_id: str) -> None:
    """POST all docs in a bundle directory to /api/verify/submit-batch/stream."""
    files_in_bundle = sorted(
        f for f in bundle_dir.iterdir()
        if f.is_file() and f.suffix.lower() in SUPPORTED_EXTS
    )
    if not files_in_bundle:
        return

    logger.info(
        "[BATCH] Submitting %d docs from %s for customer %s",
        len(files_in_bundle), bundle_dir.name, customer_id,
    )
    url = f"{API_BASE_URL}/api/verify/submit-batch/stream"

    try:
        open_handles = []
        multipart_files = []
        try:
            for fp in files_in_bundle:
                fh = fp.open("rb")
                open_handles.append(fh)
                multipart_files.append(("files", (fp.name, fh, _content_type(fp))))

            with httpx.stream(
                "POST",
                url,
                files=multipart_files,
                data={"customer_id": customer_id},
                timeout=600,
            ) as resp:
                resp.raise_for_status()
                overall_status = None
                cross_issues = 0
                for line in resp.iter_lines():
                    if not line.startswith("data: "):
                        continue
                    import json
                    try:
                        evt = json.loads(line[6:])
                    except json.JSONDecodeError:
                        continue
                    etype = evt.get("type")
                    if etype == "stage":
                        logger.info("  [stage %d] %s", evt.get("step", 0), evt.get("message", ""))
                    elif etype == "doc_detected":
                        logger.info("  [detected] %s → %s", evt.get("filename"), evt.get("label"))
                    elif etype == "cross_check":
                        cross_issues += 1
                        logger.warning("  [cross-doc] %s: %s", evt.get("field"), evt.get("conflict"))
                    elif etype == "complete":
                        overall_status = evt.get("overall_status")
                        docs = evt.get("documents_processed") or []
                        logger.info(
                            "  [complete] processed %d docs: %s",
                            len(docs), ", ".join(d["label"] for d in docs),
                        )
                    elif etype == "error":
                        logger.error("  [error] %s", evt.get("message"))
        finally:
            for fh in open_handles:
                fh.close()

        if overall_status:
            suffix = f" ({cross_issues} cross-doc conflict{'s' if cross_issues != 1 else ''})" if cross_issues else ""
            logger.info("[BATCH] ✓ %s → %s%s", bundle_dir.name, overall_status.upper(), suffix)
        _archive_dir(bundle_dir, customer_id)

    except httpx.HTTPStatusError as e:
        logger.error("[BATCH] HTTP %s: %s", e.response.status_code, e.response.text[:200])
    except Exception as e:
        logger.error("[BATCH] Failed: %s", e)


# ── Bundle debounce ───────────────────────────────────────────────────────────

class _BundleTimer:
    """Debounce rapid file arrivals into a bundle directory.

    Starts a timer on first activity. Every new event resets the timer.
    When the timer fires (BUNDLE_QUIET_SEC of silence), submits the bundle.
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._timers: dict[Path, threading.Timer] = {}

    def touch(self, bundle_dir: Path, customer_id: str) -> None:
        with self._lock:
            existing = self._timers.get(bundle_dir)
            if existing:
                existing.cancel()
            t = threading.Timer(
                BUNDLE_QUIET_SEC,
                self._fire,
                args=(bundle_dir, customer_id),
            )
            self._timers[bundle_dir] = t
            t.start()

    def _fire(self, bundle_dir: Path, customer_id: str) -> None:
        with self._lock:
            self._timers.pop(bundle_dir, None)
        logger.info("[BUNDLE] Quiet period over — submitting %s", bundle_dir.name)
        submit_batch(bundle_dir, customer_id)


_bundle_timers = _BundleTimer()


# ── Watchdog event handler ────────────────────────────────────────────────────

class DropFolderHandler(FileSystemEventHandler):
    """Handle new files/dirs dropped into the incoming directory.

    Rules:
    - File dropped directly in <WATCH_DIR>/<customer_id>/  → single-doc submit
    - File dropped in a subdirectory                        → bundle debounce → batch submit
    - New subdirectory created                              → start watching for files
    """

    def on_created(self, event: FileSystemEvent) -> None:
        path = Path(event.src_path)
        customer_id = _customer_from_path(path)

        if event.is_directory:
            # A new bundle directory appeared — nothing to do yet; wait for files
            rel_depth = len(path.relative_to(WATCH_DIR).parts)
            if rel_depth == 2:
                logger.info("[WATCH] New bundle directory: %s (customer: %s)", path.name, customer_id)
            return

        if path.suffix.lower() not in SUPPORTED_EXTS:
            return

        # Determine depth: 1 = direct file, 2 = inside a bundle subdir
        rel = path.relative_to(WATCH_DIR)
        depth = len(rel.parts)  # e.g. DEMO_CUSTOMER_001/file.pdf → 2

        if depth == 2:
            # Direct file under customer dir → single-doc (give file a moment to finish writing)
            threading.Timer(1.0, submit_single, args=(path, customer_id)).start()
        elif depth == 3:
            # File inside a bundle subdir → debounce then batch
            bundle_dir = path.parent
            _bundle_timers.touch(bundle_dir, customer_id)

    def on_modified(self, event: FileSystemEvent) -> None:
        # Some OSes fire modified instead of created for new files
        if event.is_directory:
            return
        path = Path(event.src_path)
        if path.suffix.lower() not in SUPPORTED_EXTS:
            return
        rel = path.relative_to(WATCH_DIR)
        depth = len(rel.parts)
        customer_id = _customer_from_path(path)
        if depth == 3:
            bundle_dir = path.parent
            _bundle_timers.touch(bundle_dir, customer_id)


# ── Main ──────────────────────────────────────────────────────────────────────

def main() -> None:
    WATCH_DIR.mkdir(parents=True, exist_ok=True)
    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)

    # Seed customer drop directories so the structure is obvious
    (WATCH_DIR / CUSTOMER_DEFAULT).mkdir(parents=True, exist_ok=True)

    ObserverClass = PollingObserver if USE_POLLING else Observer
    observer = ObserverClass()
    observer.schedule(DropFolderHandler(), str(WATCH_DIR), recursive=True)
    observer.start()

    mode = "polling" if USE_POLLING or ObserverClass is PollingObserver else "native FSEvents/inotify"
    logger.info("FreightMind Folder Watcher started")
    logger.info("  Watch dir : %s", WATCH_DIR)
    logger.info("  Processed : %s", PROCESSED_DIR)
    logger.info("  API       : %s", API_BASE_URL)
    logger.info("  Observer  : %s", mode)
    logger.info("  Bundle quiet: %.1fs", BUNDLE_QUIET_SEC)
    logger.info("")
    logger.info("Drop a single PDF/PNG/JPEG into:")
    logger.info("  %s/<customer_id>/filename.pdf  → single-doc verification", WATCH_DIR)
    logger.info("Drop 2-3 files into a subdirectory for batch:")
    logger.info("  %s/<customer_id>/<bundle>/     → batch verification", WATCH_DIR)
    logger.info("")
    logger.info("Quick demo (3-document batch):")
    logger.info("  cp backend/data/demo_invoices/demo_shipment_*.pdf %s/%s/shipment-set/",
                WATCH_DIR, CUSTOMER_DEFAULT)

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        logger.info("Shutting down…")
    finally:
        observer.stop()
        observer.join()


if __name__ == "__main__":
    main()
