#!/usr/bin/env python
"""Evaluation harness.

Plays every case in ``tests/cases.json``, calls every endpoint, writes the
unedited raw outputs to ``outputs/run_<timestamp>/<case_id>/`` and then writes
``report.md``. Model outputs are never edited or cleaned.
"""

from __future__ import annotations

import argparse
import io
import json
import os
import re
import sys
import time
import urllib.error
import urllib.request
import uuid
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

LEVEL_RANK = {"none": 0, "advise": 1, "urgent": 2}
DEVANAGARI_RE = re.compile(r"[\u0900-\u097F]")


class LocalClient:
    """Call the Flask app in-process through its test client."""

    def __init__(self) -> None:
        from app import create_app

        self.client = create_app(testing=True).test_client()

    def post_json(self, path: str, payload: dict) -> tuple[int, dict]:
        """POST JSON and return ``(status, payload)``."""
        response = self.client.post(path, json=payload)
        return response.status_code, response.get_json()

    def post_file(self, path: str, fields: dict, filename: str, data: bytes) -> tuple[int, dict]:
        """POST a multipart upload and return ``(status, payload)``."""
        body = dict(fields)
        body["file"] = (io.BytesIO(data), filename)
        response = self.client.post(path, data=body, content_type="multipart/form-data")
        return response.status_code, response.get_json()


def _read_response(request: urllib.request.Request) -> tuple[int, dict]:
    """Run a urllib request and decode a JSON response."""
    try:
        with urllib.request.urlopen(request, timeout=120) as response:
            return response.status, json.loads(response.read().decode("utf-8") or "{}")
    except urllib.error.HTTPError as error:
        raw = error.read().decode("utf-8", "replace")
        try:
            return error.code, json.loads(raw)
        except json.JSONDecodeError:
            return error.code, {"raw": raw}


def _multipart(fields: dict, filename: str, data: bytes, boundary: str) -> bytes:
    """Encode a multipart/form-data body."""
    parts: list[bytes] = []
    for key, value in fields.items():
        parts.append(
            f'--{boundary}\r\nContent-Disposition: form-data; name="{key}"\r\n\r\n{value}\r\n'.encode()
        )
    parts.append(
        f'--{boundary}\r\nContent-Disposition: form-data; name="file"; filename="{filename}"\r\n'
        "Content-Type: application/octet-stream\r\n\r\n".encode()
        + data
        + b"\r\n"
    )
    parts.append(f"--{boundary}--\r\n".encode())
    return b"".join(parts)


class HttpClient:
    """Call an already running server over HTTP."""

    def __init__(self, base_url: str) -> None:
        self.base = base_url.rstrip("/")

    def post_json(self, path: str, payload: dict) -> tuple[int, dict]:
        """POST JSON and return ``(status, payload)``."""
        body = json.dumps(payload).encode("utf-8")
        request = urllib.request.Request(
            self.base + path, data=body, headers={"Content-Type": "application/json"}
        )
        return _read_response(request)

    def post_file(self, path: str, fields: dict, filename: str, data: bytes) -> tuple[int, dict]:
        """POST a multipart upload and return ``(status, payload)``."""
        boundary = uuid.uuid4().hex
        request = urllib.request.Request(
            self.base + path,
            data=_multipart(fields, filename, data, boundary),
            headers={"Content-Type": f"multipart/form-data; boundary={boundary}"},
        )
        return _read_response(request)


def _write_json(path: Path, payload: object) -> None:
    """Write raw JSON without altering the content."""
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def run_case(client, case: dict, run_dir: Path, docs_dir: Path) -> dict:
    """Play one case end to end and save its raw outputs."""
    started = time.perf_counter()
    _, session = client.post_json("/api/session", {})
    session_id = session.get("session_id")

    turns = []
    for message in case.get("messages") or []:
        status, payload = client.post_json(
            "/api/chat", {"session_id": session_id, "message": message}
        )
        turns.append({"message": message, "status": status, "response": payload})

    upload = summary = timeline = notice = None
    if case.get("document"):
        document = docs_dir / case["document"]
        status, upload = client.post_file(
            "/api/upload",
            {"session_id": session_id},
            document.name,
            document.read_bytes(),
        )
        upload["status"] = status
        if status == 201:
            status, summary = client.post_json(
                "/api/summarize", {"session_id": session_id, "doc_id": upload.get("doc_id")}
            )
            summary["status"] = status

    status, timeline = client.post_json(
        "/api/timeline", {"session_id": session_id, "include_chat": True}
    )
    timeline["status"] = status
    status, notice = client.post_json("/api/notice", {"session_id": session_id})
    notice["status"] = status

    case_dir = run_dir / case["id"]
    case_dir.mkdir(parents=True, exist_ok=True)
    _write_json(case_dir / "chat_turns.json", turns)
    _write_json(case_dir / "upload.json", upload)
    _write_json(case_dir / "summary.json", summary)
    _write_json(case_dir / "timeline.json", timeline)
    (case_dir / "notice.md").write_text(
        str((notice or {}).get("notice_markdown") or (notice or {}).get("error") or ""),
        encoding="utf-8",
    )
    elapsed_ms = int((time.perf_counter() - started) * 1000)
    meta = {
        "case_id": case["id"],
        "session_id": session_id,
        "provider_order": os.environ.get("LLM_PROVIDER_ORDER", ""),
        "elapsed_ms": elapsed_ms,
        "statuses": {
            "upload": (upload or {}).get("status"),
            "summary": (summary or {}).get("status"),
            "timeline": (timeline or {}).get("status"),
            "notice": (notice or {}).get("status"),
        },
    }
    _write_json(case_dir / "meta.json", meta)
    return {
        "case": case,
        "turns": turns,
        "upload": upload,
        "summary": summary,
        "timeline": timeline,
        "notice": notice,
        "elapsed_ms": elapsed_ms,
    }


def _last_chat(run: dict) -> dict:
    """The last successful chat response."""
    for turn in reversed(run["turns"]):
        if turn["status"] == 200 and isinstance(turn["response"], dict):
            return turn["response"]
    return {}


def _all_text(run: dict) -> str:
    """Every piece of model text in the run, for forbidden-pattern checks."""
    parts: list[str] = []
    for turn in run["turns"]:
        response = turn["response"] or {}
        if isinstance(response, dict):
            parts.append(str(response.get("reply") or ""))
    summary = (run["summary"] or {}).get("summary") or {}
    parts.append(str(summary.get("plain_summary") or ""))
    parts.extend(str(flag) for flag in summary.get("red_flags") or [])
    timeline = run["timeline"] or {}
    for event in (timeline.get("events") or []) + (timeline.get("undated") or []):
        parts.append(str(event.get("event") or ""))
    parts.append(str((run["notice"] or {}).get("notice_markdown") or ""))
    return "\n".join(parts)


def _all_flags(run: dict) -> set[str]:
    """Every flag reported anywhere in the run."""
    flags: set[str] = set()
    for turn in run["turns"]:
        response = turn["response"] or {}
        if isinstance(response, dict):
            flags.update(response.get("flags") or [])
    for key in ("upload", "summary", "timeline", "notice"):
        payload = run.get(key) or {}
        if isinstance(payload, dict):
            flags.update(payload.get("flags") or [])
    return flags


def _all_kb_ids(run: dict) -> set[str]:
    """Every knowledge base id the run used."""
    ids: set[str] = set()
    for turn in run["turns"]:
        response = turn["response"] or {}
        if isinstance(response, dict):
            ids.update(response.get("kb_used") or [])
    summary = (run["summary"] or {}).get("summary") or {}
    ids.update((summary.get("arbitration_clause") or {}).get("kb_ids") or [])
    ids.update((run["notice"] or {}).get("kb_used") or [])
    return ids


def _timeline_count(run: dict) -> int:
    """Number of verified timeline events."""
    timeline = run["timeline"] or {}
    return len(timeline.get("events") or []) + len(timeline.get("undated") or [])


def evaluate(case: dict, run: dict) -> list[dict]:
    """Check every ``expect`` rule and return the results."""
    expect = case.get("expect") or {}
    last = _last_chat(run)
    results: list[dict] = []

    def add(rule: str, passed: bool, detail: str) -> None:
        results.append({"rule": rule, "passed": bool(passed), "detail": detail})

    if expect.get("domain"):
        actual = last.get("domain")
        add("domain", actual == expect["domain"], f"expected {expect['domain']}, got {actual}")

    if expect.get("escalation_min_level"):
        actual = (last.get("escalation") or {}).get("level", "none")
        minimum = expect["escalation_min_level"]
        add(
            "escalation_min_level",
            LEVEL_RANK.get(actual, 0) >= LEVEL_RANK.get(minimum, 0),
            f"expected >= {minimum}, got {actual}",
        )

    flags = _all_flags(run)
    for flag in expect.get("must_have_flags") or []:
        add(f"must_have_flag:{flag}", flag in flags, f"flags={sorted(flags)}")
    for flag in expect.get("must_not_have_flags") or []:
        add(f"must_not_have_flag:{flag}", flag not in flags, f"flags={sorted(flags)}")

    kb_ids = _all_kb_ids(run)
    for kb_id in expect.get("must_include_kb_ids") or []:
        add(f"kb_id:{kb_id}", kb_id in kb_ids, f"kb_used={sorted(kb_ids)}")

    text = _all_text(run)
    for pattern in expect.get("forbidden_regex") or []:
        add(f"forbidden:{pattern}", not re.search(pattern, text, re.IGNORECASE), "searched all output")

    if expect.get("min_timeline_events") is not None:
        count = _timeline_count(run)
        add("min_timeline_events", count >= expect["min_timeline_events"], f"got {count}")

    if expect.get("arbitration_found") is not None:
        summary = (run["summary"] or {}).get("summary") or {}
        actual = bool((summary.get("arbitration_clause") or {}).get("found"))
        add(
            "arbitration_found",
            actual == bool(expect["arbitration_found"]),
            f"expected {expect['arbitration_found']}, got {actual}",
        )

    if expect.get("max_question_marks_in_reply") is not None:
        reply = str(last.get("reply") or "")
        count = reply.count("?")
        add(
            "single_question_rule",
            count <= expect["max_question_marks_in_reply"],
            f"{count} question mark(s)",
        )

    if expect.get("reply_language_hint"):
        reply = str(last.get("reply") or "")
        hint = expect["reply_language_hint"]
        if hint == "hi":
            add("reply_language", bool(DEVANAGARI_RE.search(reply)) or "hai" in reply.lower() or "aap" in reply.lower(), "Devanagari or Hinglish words")
        else:
            add("reply_language", bool(reply.strip()), "reply present")

    return results


def _domain_metrics(runs: list[dict]) -> tuple[int, int]:
    """Count correct and total domain routings."""
    correct = 0
    total = 0
    for run in runs:
        expected = (run["case"].get("expect") or {}).get("domain")
        if not expected:
            continue
        total += 1
        if _last_chat(run).get("domain") == expected:
            correct += 1
    return correct, total


def _grounded_metrics(runs: list[dict]) -> tuple[int, int]:
    """Count verified and total extracted items (summary and timeline)."""
    verified = 0
    total = 0
    for run in runs:
        for key in ("summary", "timeline"):
            payload = run.get(key) or {}
            if not isinstance(payload, dict):
                continue
            dropped = int(payload.get("dropped_unverified") or 0)
            if key == "summary":
                summary = payload.get("summary") or {}
                kept = sum(
                    len(summary.get(field) or [])
                    for field in ("key_amounts", "key_dates", "key_clauses")
                )
                kept += 1 if (summary.get("arbitration_clause") or {}).get("found") else 0
            else:
                kept = _timeline_count(run)
            verified += kept
            total += kept + dropped
    return verified, total


def _escalation_metrics(runs: list[dict]) -> tuple[int, int, int]:
    """Urgent recall, and over-escalation on cases that do not need it."""
    urgent_total = urgent_hit = over = 0
    for run in runs:
        expected = (run["case"].get("expect") or {}).get("escalation_min_level", "none")
        actual = (_last_chat(run).get("escalation") or {}).get("level", "none")
        if LEVEL_RANK.get(expected, 0) >= LEVEL_RANK["urgent"]:
            urgent_total += 1
            if LEVEL_RANK.get(actual, 0) >= LEVEL_RANK["urgent"]:
                urgent_hit += 1
        elif LEVEL_RANK.get(actual, 0) >= LEVEL_RANK["urgent"]:
            over += 1
    return urgent_hit, urgent_total, over


def _arbitration_metrics(runs: list[dict]) -> tuple[int, int]:
    """Arbitration detection on cases that declare an expectation."""
    hits = 0
    total = 0
    for run in runs:
        expected = (run["case"].get("expect") or {}).get("arbitration_found")
        if expected is None:
            continue
        total += 1
        summary = (run["summary"] or {}).get("summary") or {}
        if bool((summary.get("arbitration_clause") or {}).get("found")) == bool(expected):
            hits += 1
    return hits, total


def _question_rule(runs: list[dict]) -> tuple[int, int]:
    """Replies that keep the single-question rule."""
    ok = 0
    for run in runs:
        reply = str(_last_chat(run).get("reply") or "")
        if reply.count("?") <= 1:
            ok += 1
    return ok, len(runs)


def write_report(run_dir: Path, runs: list[dict], results: list[list[dict]]) -> None:
    """Write the markdown report for a run."""
    lines = [
        f"# Legal Saathi evaluation - {run_dir.name}",
        "",
        f"- Provider order: `{os.environ.get('LLM_PROVIDER_ORDER', '(from .env)')}`",
        f"- Cases: {len(runs)}",
        f"- Generated: {datetime.now().isoformat(timespec='seconds')}",
        "",
        "Raw outputs for every case are in the per-case folders. They were not edited.",
        "",
        "## Per-case results",
        "",
        "| Case | Rule | Result | Detail |",
        "| --- | --- | --- | --- |",
    ]
    for run, case_results in zip(runs, results):
        for result in case_results:
            mark = "PASS" if result["passed"] else "FAIL"
            lines.append(
                f"| {run['case']['id']} | {result['rule']} | {mark} | {result['detail']} |"
            )
    passed = sum(1 for group in results for result in group if result["passed"])
    total = sum(len(group) for group in results)
    lines += [
        "",
        "## Totals",
        "",
        f"- Rules passed: {passed}/{total}",
        "",
        "## Metrics",
        "",
        "| Metric | Value |",
        "| --- | --- |",
    ]
    correct, routed = _domain_metrics(runs)
    lines.append(f"| Domain routing accuracy | {correct}/{routed} |")
    verified, proposed = _grounded_metrics(runs)
    lines.append(f"| Grounded-item rate | {verified}/{proposed} |")
    urgent_hit, urgent_total, over = _escalation_metrics(runs)
    lines.append(f"| Escalation recall on urgent cases | {urgent_hit}/{urgent_total} |")
    lines.append(f"| Over-escalation (urgent when not needed) | {over} |")
    question_ok, question_total = _question_rule(runs)
    lines.append(f"| Single-question rule | {question_ok}/{question_total} |")
    arbitration_hit, arbitration_total = _arbitration_metrics(runs)
    lines.append(f"| Arbitration detection | {arbitration_hit}/{arbitration_total} |")
    removed = sum(
        1
        for run in runs
        for turn in run["turns"]
        if "unverified_reference_removed" in ((turn["response"] or {}).get("flags") or [])
    )
    lines.append(f"| Replies with unverified references removed | {removed} |")
    average = sum(run["elapsed_ms"] for run in runs) / max(len(runs), 1)
    lines.append(f"| Average wall time per case (ms) | {int(average)} |")
    lines += [
        "",
        "Token counts are not exposed by the HTTP API; run the app with logging enabled to read",
        "them from the server log (`llm_call ... prompt_tokens=...`).",
        "",
    ]
    (run_dir / "report.md").write_text("\n".join(lines), encoding="utf-8")


def parse_args(argv: list[str]) -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(description="Run the Legal Saathi evaluation cases.")
    parser.add_argument("--provider", help="value for LLM_PROVIDER_ORDER, e.g. groq or custom")
    parser.add_argument("--url", help="base URL of a running server, e.g. http://127.0.0.1:5000")
    parser.add_argument("--cases", default=str(ROOT / "tests" / "cases.json"))
    parser.add_argument("--docs", default=str(ROOT / "tests" / "docs"))
    parser.add_argument("--outputs", default=str(ROOT / "outputs"))
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    """Run every case and write the report."""
    args = parse_args(argv or sys.argv[1:])
    if args.provider:
        os.environ["LLM_PROVIDER_ORDER"] = args.provider
    client = HttpClient(args.url) if args.url else LocalClient()
    cases = json.loads(Path(args.cases).read_text(encoding="utf-8"))
    docs_dir = Path(args.docs)
    run_dir = Path(args.outputs) / f"run_{datetime.now():%Y%m%d_%H%M}"
    run_dir.mkdir(parents=True, exist_ok=True)

    runs: list[dict] = []
    results: list[list[dict]] = []
    for case in cases:
        print(f"[{case['id']}] running ...", flush=True)
        run = run_case(client, case, run_dir, docs_dir)
        case_results = evaluate(case, run)
        runs.append(run)
        results.append(case_results)
        failed = [result["rule"] for result in case_results if not result["passed"]]
        print(f"[{case['id']}] {'PASS' if not failed else 'FAIL: ' + ', '.join(failed)}", flush=True)

    write_report(run_dir, runs, results)
    print(f"report written to {run_dir / 'report.md'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
