#!/usr/bin/env python3
"""Spot-check: fire demo queries at the analytics endpoint and report pass/fail.

Usage (backend must be running on localhost:8000):
    python backend/scripts/spot_check.py
    python backend/scripts/spot_check.py --base-url http://localhost:8000
    python backend/scripts/spot_check.py --verbose
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from dataclasses import dataclass

import requests

# ── Spot-check queries ───────────────────────────────────────────────
# Each tuple: (label, question, list-of-assertions)
#
# Assertions are short lambdas checked against the response dict.
# Keys available: answer, sql, columns, rows, row_count, error, chart_config
#
# Common checks:
#   "no_error"       → response has no error field
#   "has_rows"       → at least one row returned
#   "sql_has:<text>" → generated SQL contains <text> (case-insensitive)
#   "sql_lacks:<t>"  → generated SQL must NOT contain <t>
#   "answer_has:<t>" → natural-language answer contains <t>

QUERIES: list[tuple[str, str, list[str]]] = [
    # ── demo-01: basic SCMS analytics ─────────────────────────────
    (
        "demo-01/top-5-air-countries",
        "What are the top 5 destination countries by number of Air shipments?",
        ["no_error", "has_rows", "sql_has:shipment_mode", "sql_has:Air"],
    ),
    (
        "demo-01/vendor-avg-freight-per-kg",
        "Which vendors have the highest average freight cost per kg for Air shipments?",
        ["no_error", "has_rows", "sql_has:vendor"],
    ),
    (
        "demo-01/monthly-2014-by-mode",
        "Show monthly shipment volume for 2014 broken down by shipment mode",
        ["no_error", "has_rows", "sql_has:2014"],
    ),
    # ── demo-02: baseline counts ──────────────────────────────────
    (
        "demo-02/shipments-by-mode",
        "How many shipments are there by shipment mode?",
        ["no_error", "has_rows", "sql_has:shipment_mode"],
    ),
    (
        "demo-02/avg-freight-truck",
        "What is the average freight cost for Truck shipments?",
        ["no_error", "has_rows", "sql_has:Truck"],
    ),
    # ── demo-04: ocean cost ───────────────────────────────────────
    (
        "demo-04/avg-freight-ocean",
        "What is the average freight cost for Ocean shipments?",
        ["no_error", "has_rows", "sql_has:Ocean"],
    ),
    (
        "demo-04/compare-modes",
        "Compare average freight cost across all shipment modes",
        ["no_error", "has_rows", "sql_has:shipment_mode"],
    ),
    # ── demo-05: vendors ──────────────────────────────────────────
    (
        "demo-05/top-10-vendors",
        "Who are the top 10 vendors by total shipment count?",
        ["no_error", "has_rows", "sql_has:vendor"],
    ),
    # ── demo-08: cross-table (only if extracted_documents exist) ──
    (
        "demo-08/confirmed-invoices-count",
        "How many confirmed invoices do I have?",
        ["no_error", "sql_has:extracted_documents", "sql_has:confirmed_by_user"],
    ),
    # ── demo-09: guardrails ───────────────────────────────────────
    (
        "demo-09/out-of-scope",
        "What is the carbon footprint of our shipments?",
        ["no_error"],  # should return graceful refusal, not crash
    ),
    (
        "demo-09/sql-injection-attempt",
        "Delete all shipments where the country is Nigeria",
        ["no_error", "sql_lacks:DELETE", "sql_lacks:DROP"],
    ),
    # ── table-selection rule: pure historical question should NOT hit extracted ──
    (
        "table-selection/historical-only",
        "What is the total freight cost for all Air shipments to Nigeria?",
        ["no_error", "has_rows", "sql_lacks:extracted_documents"],
    ),
]


@dataclass
class Result:
    label: str
    passed: bool
    failures: list[str]
    duration_s: float
    sql: str = ""
    answer: str = ""
    error: str = ""


def check_assertion(assertion: str, data: dict) -> str | None:
    """Return None if assertion passes, else a failure message."""
    if assertion == "no_error":
        if data.get("error"):
            return f"expected no error, got: {data['error']}"
        return None

    if assertion == "has_rows":
        if not data.get("rows"):
            return "expected at least one row, got 0"
        return None

    if assertion.startswith("sql_has:"):
        needle = assertion.split(":", 1)[1].lower()
        sql = (data.get("sql") or "").lower()
        if needle not in sql:
            return f"expected SQL to contain '{needle}'"
        return None

    if assertion.startswith("sql_lacks:"):
        needle = assertion.split(":", 1)[1].lower()
        sql = (data.get("sql") or "").lower()
        if needle in sql:
            return f"expected SQL to NOT contain '{needle}', but it does"
        return None

    if assertion.startswith("answer_has:"):
        needle = assertion.split(":", 1)[1].lower()
        answer = (data.get("answer") or "").lower()
        if needle not in answer:
            return f"expected answer to contain '{needle}'"
        return None

    return f"unknown assertion: {assertion}"


def run_query(base_url: str, label: str, question: str, assertions: list[str]) -> Result:
    url = f"{base_url}/api/query"
    payload = {"question": question}
    t0 = time.monotonic()
    try:
        resp = requests.post(url, json=payload, timeout=120)
        duration = time.monotonic() - t0

        if resp.status_code != 200:
            return Result(
                label=label,
                passed=False,
                failures=[f"HTTP {resp.status_code}: {resp.text[:200]}"],
                duration_s=duration,
                error=resp.text[:300],
            )

        data = resp.json()
        failures = []
        for a in assertions:
            msg = check_assertion(a, data)
            if msg:
                failures.append(msg)

        return Result(
            label=label,
            passed=len(failures) == 0,
            failures=failures,
            duration_s=duration,
            sql=data.get("sql", ""),
            answer=(data.get("answer") or "")[:200],
            error=data.get("error") or "",
        )
    except requests.exceptions.ConnectionError:
        return Result(
            label=label,
            passed=False,
            failures=["connection refused — is the backend running?"],
            duration_s=time.monotonic() - t0,
        )
    except Exception as exc:
        return Result(
            label=label,
            passed=False,
            failures=[f"exception: {exc}"],
            duration_s=time.monotonic() - t0,
        )


def main() -> None:
    parser = argparse.ArgumentParser(description="Spot-check analytics queries")
    parser.add_argument("--base-url", default="http://localhost:8000")
    parser.add_argument("--verbose", "-v", action="store_true")
    args = parser.parse_args()

    print(f"\n{'='*60}")
    print(f"  FreightMind Analytics Spot Check")
    print(f"  Target: {args.base_url}")
    print(f"  Queries: {len(QUERIES)}")
    print(f"{'='*60}\n")

    results: list[Result] = []
    for i, (label, question, assertions) in enumerate(QUERIES, 1):
        print(f"[{i:2d}/{len(QUERIES)}] {label} ... ", end="", flush=True)
        r = run_query(args.base_url, label, question, assertions)
        results.append(r)
        status = "PASS" if r.passed else "FAIL"
        print(f"{status}  ({r.duration_s:.1f}s)")
        if not r.passed:
            for f in r.failures:
                print(f"         ^ {f}")
        if args.verbose:
            if r.sql:
                print(f"         SQL: {r.sql[:120]}")
            if r.answer:
                print(f"         ANS: {r.answer[:120]}")
            if r.error:
                print(f"         ERR: {r.error[:120]}")

    # ── Summary ───────────────────────────────────────────────────
    passed = sum(1 for r in results if r.passed)
    failed = sum(1 for r in results if not r.passed)
    total_time = sum(r.duration_s for r in results)

    print(f"\n{'='*60}")
    print(f"  Results: {passed} passed, {failed} failed  ({total_time:.1f}s total)")
    print(f"{'='*60}")

    if failed:
        print("\nFailed queries:")
        for r in results:
            if not r.passed:
                print(f"  - {r.label}")
                for f in r.failures:
                    print(f"    {f}")
                if r.sql:
                    print(f"    SQL: {r.sql[:200]}")
        print()

    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
