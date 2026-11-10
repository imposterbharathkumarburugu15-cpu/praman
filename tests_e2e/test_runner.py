"""Unified test runner for PRAMAN E2E test suite.
Supports tiered execution, test type isolation (unit, integration, e2e),
device execution mode filtering (mock vs physical device), JSON report emission,
and structured terminal reporting with breakdown tables.
"""

import os
import sys
import time
import json
import argparse
from typing import List, Dict, Any, Optional
import pytest


TIER_DIRECTORIES = {
    "1": "tests_e2e/tier1_features",
    "2": "tests_e2e/tier2_boundaries",
    "3": "tests_e2e/tier3_interactions",
    "4": "tests_e2e/tier4_real_world",
    "5": "tests_e2e/tier5_adversarial",
}


def classify_test(nodeid: str) -> Dict[str, str]:
    """Classifies a test case by Tier, Test Type, and Device Mode based on its node ID."""
    clean_id = nodeid.replace("\\", "/")

    # 1. Tier classification
    if "tier1_features" in clean_id:
        tier = "Tier 1: Feature Coverage"
    elif "tier2_boundaries" in clean_id:
        tier = "Tier 2: Boundary Cases"
    elif "tier3_interactions" in clean_id:
        tier = "Tier 3: Interactions"
    elif "tier4_real_world" in clean_id:
        tier = "Tier 4: Real-World Scenarios"
    elif "tier5_adversarial" in clean_id:
        tier = "Tier 5: Adversarial Attacks"
    else:
        tier = "Other"

    # 2. Test Type classification
    if "tier4_real_world" in clean_id or "tier3_interactions" in clean_id or "tier5_adversarial" in clean_id:
        test_type = "e2e"
    elif any(f in clean_id for f in [
        "test_f08", "test_f09", "test_f10", "test_f11", "test_f12",
        "test_f13", "test_f14", "test_f15", "test_f16", "test_f17",
        "test_f40", "test_f41", "test_f42", "test_f43", "test_f44", "test_f45"
    ]):
        test_type = "integration"
    else:
        test_type = "unit"

    # 3. Device Mode classification
    if "physical_device" in clean_id:
        device_mode = "physical"
    else:
        device_mode = "mock"

    return {
        "tier": tier,
        "type": test_type,
        "device": device_mode,
    }


class ResultCollectorPlugin:
    """Pytest plugin to gather detailed execution statistics and tier/type breakdowns."""

    def __init__(self):
        self.passed = 0
        self.failed = 0
        self.skipped = 0
        self.errors = 0
        self.tests: List[Dict[str, Any]] = []

    def pytest_runtest_logreport(self, report):
        if report.when == "call":
            outcome = report.outcome
            if outcome == "passed":
                self.passed += 1
            elif outcome == "failed":
                self.failed += 1
            elif outcome == "skipped":
                self.skipped += 1

            meta = classify_test(report.nodeid)
            self.tests.append({
                "nodeid": report.nodeid,
                "outcome": outcome,
                "duration": round(report.duration, 4),
                **meta,
            })
        elif report.when == "setup" and report.skipped:
            # Handle tests skipped at setup phase (e.g. skipif on physical devices)
            self.skipped += 1
            meta = classify_test(report.nodeid)
            self.tests.append({
                "nodeid": report.nodeid,
                "outcome": "skipped",
                "phase": "setup",
                "duration": round(report.duration, 4),
                **meta,
            })
        elif report.when in ("setup", "teardown") and report.failed:
            self.errors += 1
            meta = classify_test(report.nodeid)
            self.tests.append({
                "nodeid": report.nodeid,
                "outcome": "error",
                "phase": report.when,
                "duration": round(report.duration, 4),
                **meta,
            })


def run_e2e_tests(
    tiers: List[str],
    test_type: str = "all",
    device_mode: str = "all",
    verbose: bool = False,
    report_file: Optional[str] = None,
    extra_args: Optional[List[str]] = None,
) -> int:
    """Executes selected tiers of the E2E test suite with type and device filtering."""
    target_dirs = []
    for tier in tiers:
        if tier in TIER_DIRECTORIES:
            target_dirs.append(TIER_DIRECTORIES[tier])
        elif tier == "all":
            target_dirs = list(TIER_DIRECTORIES.values())
            break
        else:
            print(f"[ERROR] Unknown tier: {tier}. Valid options: 1, 2, 3, 4, all", file=sys.stderr)
            return 2

    # Ensure all target paths exist
    resolved_paths = [os.path.abspath(d) for d in target_dirs if os.path.exists(d)]
    if not resolved_paths:
        print(f"[ERROR] None of the specified target directories exist: {target_dirs}", file=sys.stderr)
        return 2

    pytest_args = list(resolved_paths)
    if verbose:
        pytest_args.append("-v")
    else:
        pytest_args.append("-q")

    # Prevent cache pollution
    pytest_args.extend(["-p", "no:cacheprovider"])

    # Build marker expressions for type and device filtering
    marker_exprs = []
    if test_type != "all":
        if test_type in ("unit", "integration", "e2e"):
            marker_exprs.append(test_type)
        else:
            print(f"[ERROR] Unknown test type: {test_type}. Valid: unit, integration, e2e, all", file=sys.stderr)
            return 2

    if device_mode != "all":
        if device_mode == "mock":
            marker_exprs.append("not physical_device")
        elif device_mode == "physical":
            marker_exprs.append("physical_device")
        else:
            print(f"[ERROR] Unknown device mode: {device_mode}. Valid: mock, physical, all", file=sys.stderr)
            return 2

    if marker_exprs:
        pytest_args.extend(["-m", " and ".join(marker_exprs)])

    if extra_args:
        pytest_args.extend(extra_args)

    print("=" * 72)
    print(" PRAMAN E2E TEST RUNNER")
    print(f" Targets:     {', '.join(target_dirs)}")
    print(f" Test Type:   {test_type}")
    print(f" Device Mode: {device_mode}")
    print(f" Pytest Args: {' '.join(pytest_args)}")
    print("=" * 72)

    collector = ResultCollectorPlugin()
    start_time = time.time()
    exit_code = pytest.main(pytest_args, plugins=[collector])
    elapsed_time = round(time.time() - start_time, 2)

    total_run = collector.passed + collector.failed + collector.skipped + collector.errors
    pass_rate = round((collector.passed / total_run * 100), 2) if total_run > 0 else 0.0

    # Calculate breakdowns
    breakdowns = {
        "tiers": {},
        "types": {"unit": 0, "integration": 0, "e2e": 0},
        "devices": {"mock": 0, "physical": 0},
    }
    for t in collector.tests:
        tier_k = t.get("tier", "Other")
        type_k = t.get("type", "other")
        dev_k = t.get("device", "mock")

        breakdowns["tiers"][tier_k] = breakdowns["tiers"].get(tier_k, 0) + 1
        if type_k in breakdowns["types"]:
            breakdowns["types"][type_k] += 1
        if dev_k in breakdowns["devices"]:
            breakdowns["devices"][dev_k] += 1

    print("\n" + "=" * 72)
    print(" EXECUTION SUMMARY")
    print(f" Total Tests Collected: {total_run}")
    print(f" Passed:                {collector.passed}")
    print(f" Failed:                {collector.failed}")
    print(f" Errors:                {collector.errors}")
    print(f" Skipped:               {collector.skipped}")
    print(f" Pass Rate:             {pass_rate}%")
    print(f" Elapsed Time:          {elapsed_time}s")
    print(f" Exit Code:             {exit_code}")
    print("-" * 72)
    print(" COVERAGE BREAKDOWN")
    print(" [By Tier]")
    for tier_name, count in sorted(breakdowns["tiers"].items()):
        print(f"   - {tier_name:<30} : {count} tests")
    print(" [By Test Type]")
    print(f"   - Unit Tests                   : {breakdowns['types']['unit']} tests")
    print(f"   - Integration Tests            : {breakdowns['types']['integration']} tests")
    print(f"   - End-to-End Tests             : {breakdowns['types']['e2e']} tests")
    print(" [By Device Execution Mode]")
    print(f"   - Mock / Software Emulation    : {breakdowns['devices']['mock']} tests")
    print(f"   - Physical Android Hardware    : {breakdowns['devices']['physical']} tests")
    print("=" * 72)

    if report_file:
        report_data = {
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "tiers": tiers,
            "target_dirs": target_dirs,
            "test_type": test_type,
            "device_mode": device_mode,
            "total": total_run,
            "passed": collector.passed,
            "failed": collector.failed,
            "errors": collector.errors,
            "skipped": collector.skipped,
            "pass_rate_pct": pass_rate,
            "elapsed_seconds": elapsed_time,
            "exit_code": int(exit_code),
            "breakdowns": breakdowns,
            "test_details": collector.tests,
        }
        with open(report_file, "w", encoding="utf-8") as f:
            json.dump(report_data, f, indent=2)
        print(f" Execution report saved to: {report_file}")

    return int(exit_code)


def main():
    parser = argparse.ArgumentParser(description="PRAMAN E2E Test Suite Runner")
    parser.add_argument(
        "--tier",
        type=str,
        default="all",
        help="Comma-separated tiers to run: 1, 2, 3, 4, 5, or 'all' (default: all)",
    )
    parser.add_argument(
        "--type",
        type=str,
        default="all",
        choices=["unit", "integration", "e2e", "all"],
        help="Filter by test categorization: unit, integration, e2e, or all (default: all)",
    )
    parser.add_argument(
        "--device",
        type=str,
        default="all",
        choices=["mock", "physical", "all"],
        help="Filter by device mode: mock, physical, or all (default: all)",
    )
    parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="Enable verbose output",
    )
    parser.add_argument(
        "--report",
        type=str,
        default=None,
        help="Path to write JSON test report",
    )
    args, unknown = parser.parse_known_args()

    tier_list = [t.strip() for t in args.tier.split(",")]
    code = run_e2e_tests(
        tiers=tier_list,
        test_type=args.type,
        device_mode=args.device,
        verbose=args.verbose,
        report_file=args.report,
        extra_args=unknown,
    )
    sys.exit(code)


if __name__ == "__main__":
    main()
