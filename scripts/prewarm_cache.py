#!/usr/bin/env python3
"""Pre-warm the LLM response cache for all demo PDFs.

Submits each demo PDF through the live verification stream endpoint once,
so all subsequent demo runs are instant cache hits.

Run from repo root:
    python scripts/prewarm_cache.py
"""

import sys
import json
import time
from pathlib import Path

try:
    import httpx
except ImportError:
    print("httpx not installed. Run: pip install httpx")
    sys.exit(1)

DEMO_DIR = Path(__file__).parent.parent / "demo"
API_BASE = "http://localhost:8000"

SCENARIOS = [
    # (filename,              customer_id,         expected_status)
    ("globaltech_CI_approved.pdf",   "DEMO_CUSTOMER_001", "approved"),
    ("globaltech_CI_amendment.pdf",  "DEMO_CUSTOMER_001", "amendment_required"),
    ("globaltech_BL.pdf",            "DEMO_CUSTOMER_001", "approved"),
    ("globaltech_PL.pdf",            "DEMO_CUSTOMER_001", "approved"),
    ("medsupply_CI_approved.pdf",    "DEMO_CUSTOMER_002", "approved"),
    ("medsupply_CI_amendment.pdf",   "DEMO_CUSTOMER_002", "amendment_required"),
    ("medsupply_AWB.pdf",            "DEMO_CUSTOMER_002", "approved"),
    ("medsupply_PL.pdf",             "DEMO_CUSTOMER_002", "approved"),
]


def warm(filename: str, customer_id: str, expected: str, client: httpx.Client) -> bool:
    path = DEMO_DIR / filename
    if not path.exists():
        print(f"  ✗ {filename} — file not found")
        return False

    with path.open("rb") as f:
        data = f.read()

    print(f"  → {filename} [{customer_id}] ... ", end="", flush=True)
    t0 = time.time()

    try:
        with client.stream(
            "POST",
            f"{API_BASE}/api/verify/submit/stream",
            data={"customer_id": customer_id},
            files={"file": (filename, data, "application/pdf")},
            timeout=300.0,
        ) as resp:
            resp.raise_for_status()
            status = None
            cache_hit = False
            for line in resp.iter_lines():
                if not line.startswith("data: "):
                    continue
                evt = json.loads(line[6:])
                if evt.get("type") == "complete":
                    status = evt.get("overall_status")
                elif evt.get("type") == "error":
                    print(f"ERROR — {evt.get('message')}")
                    return False
                # Detect cache hit: stage 2 completes in < 1s means vision was cached
                if evt.get("type") == "stage" and evt.get("step") == 3:
                    elapsed = time.time() - t0
                    if elapsed < 2.0:
                        cache_hit = True

    except httpx.HTTPStatusError as e:
        print(f"HTTP {e.response.status_code}")
        return False
    except Exception as e:
        print(f"FAILED — {e}")
        return False

    elapsed = time.time() - t0
    hit_label = " (cache hit)" if cache_hit else " (fresh — now cached)"
    ok = "✓" if status == expected else f"⚠ got {status}, expected {expected}"
    print(f"{ok} · {elapsed:.1f}s{hit_label}")
    return True


def main():
    print("Pre-warming demo cache...\n")

    # Quick health check
    try:
        r = httpx.get(f"{API_BASE}/api/health", timeout=5)
        r.raise_for_status()
    except Exception as e:
        print(f"Backend not reachable at {API_BASE}: {e}")
        sys.exit(1)

    print("Single-doc scenarios:")
    passed = 0
    with httpx.Client() as client:
        for filename, customer_id, expected in SCENARIOS:
            if warm(filename, customer_id, expected, client):
                passed += 1

    print(f"\n{passed}/{len(SCENARIOS)} docs warmed.")
    if passed == len(SCENARIOS):
        print("\nAll demo PDFs are now cached — submissions during the demo will be instant.")
    else:
        print("\nSome docs failed — re-run to retry, or check server logs.")

    print("\nBatch sets (upload these together during demo):")
    print("  DEMO_CUSTOMER_001: globaltech_CI_approved.pdf + globaltech_BL.pdf + globaltech_PL.pdf")
    print("  DEMO_CUSTOMER_002: medsupply_CI_approved.pdf  + medsupply_AWB.pdf  + medsupply_PL.pdf")
    print("\nNote: batch runs (3 docs) each trigger 2 LLM calls per doc (type detection + extraction).")
    print("Upload each batch set once now to cache those too.")


if __name__ == "__main__":
    main()
