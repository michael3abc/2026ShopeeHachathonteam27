"""Run the demo case through API, Redis, Agent Service, and LangGraph."""

from __future__ import annotations

import argparse
import json
import time
from typing import Any
from urllib.request import Request, urlopen
from uuid import uuid4


def _request_json(
    method: str,
    url: str,
    payload: dict[str, object] | None = None,
) -> dict[str, Any]:
    body = None if payload is None else json.dumps(payload).encode("utf-8")
    request = Request(
        url,
        data=body,
        method=method,
        headers={"Content-Type": "application/json"},
    )
    with urlopen(request, timeout=10) as response:
        return json.load(response)


def _wait_for_status(
    *,
    api_url: str,
    case_ref: str,
    expected: set[str],
    timeout_seconds: float,
) -> dict[str, Any]:
    deadline = time.monotonic() + timeout_seconds
    last_status = "UNKNOWN"
    while time.monotonic() < deadline:
        case = _request_json("GET", f"{api_url}/cases/{case_ref}")
        last_status = str(case["status"])
        print(f"case={case_ref} status={last_status}")
        if last_status in expected:
            return case
        if last_status in {"ESCALATED", "RESOLVED"}:
            raise RuntimeError(json.dumps(case, ensure_ascii=False, indent=2))
        time.sleep(1)
    raise TimeoutError(
        f"case {case_ref} stayed at {last_status} for {timeout_seconds:g}s"
    )


def run(api_url: str, timeout_seconds: float) -> None:
    api_url = api_url.rstrip("/")
    order_ref = f"ORDER-DEMO-E2E-{uuid4().hex[:8].upper()}"
    created = _request_json(
        "POST",
        f"{api_url}/cases",
        {
            "order_ref": order_ref,
            "user_ref": "USER-DEMO",
            "initial_message": (
                f"{order_ref} 的 Demo Bluetooth Speaker 到貨時外箱與商品都已損壞，"
                "我要退貨退款"
            ),
        },
    )
    case_ref = str(created["case_ref"])
    print(f"created case={case_ref} order={order_ref}")

    interrupted = _wait_for_status(
        api_url=api_url,
        case_ref=case_ref,
        expected={"AWAITING_EVIDENCE"},
        timeout_seconds=timeout_seconds,
    )
    if interrupted.get("evidence_request") is None:
        raise RuntimeError("AWAITING_EVIDENCE response omitted evidence_request")

    _request_json(
        "POST",
        f"{api_url}/cases/{case_ref}/messages",
        {
            "message": "補上同一張照片，清楚拍到壓損外箱與喇叭裂痕",
            "attached_artifact_refs": [
                "artifact://demo/EV-DEMO-ARRIVAL-PACKAGING-AND-DAMAGE"
            ],
        },
    )
    completed = _wait_for_status(
        api_url=api_url,
        case_ref=case_ref,
        expected={"RESOLVED"},
        timeout_seconds=timeout_seconds,
    )
    print(json.dumps(completed, ensure_ascii=False, indent=2))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--api-url", default="http://127.0.0.1:8000")
    parser.add_argument("--timeout", type=float, default=180.0)
    args = parser.parse_args()
    run(args.api_url, args.timeout)


if __name__ == "__main__":
    main()
