"""Fix 2 — commit-triggered cache resweep.

Re-verifies each cached row's STORED URL through verify() (NOT full-agent
rediscovery — the load-bearing cost optimization: ~2-8s/row vs the agent's
45s give_up). Rows whose cached document no longer passes the *current* gate
logic are purged and audited. Rediscovery of a replacement is deliberately left
to the next user query (cache miss -> agent); the sweep only validates+purges.

Trigger: a sweep is DUE if EITHER
  (a) a `Gate-Change: true` trailer commit exists in (last_swept_commit..HEAD], OR
  (b) sha256(verify.py) differs from the last-swept fingerprint (catches gate
      edits made without the trailer — the only backstop, since there is no CI
      and the pre-commit hook is bypassable).
State: sibling `sweep_meta.json`. Audit: `cache_sweeps.log` (JSON lines).

Marker + fingerprint advance ONLY after a full sweep completes; per-row deletes
commit immediately. So an interrupted run re-sweeps from scratch next time —
safe because re-verification is idempotent (a passing row re-passes; a purged
row is already gone).

sweep_status() / format_due_warning() are the SHARED detection used by both
api.py and streamlit_app.py startup checks, so all three agree on "due".

Usage:
  python sweep_cache.py                 # dry-run: due-status + rows that would be checked
  python sweep_cache.py --preview       # live re-verify all rows, report, DELETE NOTHING
  python sweep_cache.py --apply [--all] # backup, re-verify, purge gate-failures, advance marker
  python sweep_cache.py --since <sha>   # override last-swept commit for the due check
"""
import argparse
import hashlib
import json
import logging
import re
import sqlite3
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path

import cache
from verify import verify

logger = logging.getLogger(__name__)

_ROOT = Path(__file__).resolve().parent
_VERIFY_PY = _ROOT / "verify.py"
_META_PATH = _ROOT / "sweep_meta.json"
_AUDIT_PATH = _ROOT / "cache_sweeps.log"

# A not-ok verify() result is only a reason to PURGE when it's a genuine
# CONTENT-based gate rejection (the downloaded document itself fails a gate).
# NEVER purge on:
#   - transport/parse failures (timeout, HTTP error, unreachable host, corrupt
#     download) — a network blip must not wipe good rows; or
#   - Step-0 URL/filename PRE-DOWNLOAD heuristics ("URL year … does not match",
#     "URL contains quarterly signal") — these are cheap pre-checks on the URL
#     string, not verdicts on document content, and they misfire on legitimate
#     split-year filenames: R R Kabel's genuine 2023-24 report lives at
#     ".../Annual-Rrport_2023-24.pdf", whose filename year reads as 2023, so a
#     FY2024 row's Step-0 check falsely rejects it. The equivalent CONTENT gate
#     ("primary fiscal year …" from the actual cover) still catches a truly
#     wrong-year document, so excluding the URL pre-check loses no real catch.
# Fail-safe: purge ONLY on a recognized CONTENT gate verdict; keep (and log as
# inconclusive) on anything else, including unknown reasons.
_GATE_REJECT_MARKERS = (
    "does not match the requested company",   # identity divergence gate
    "company tokens missing",                 # identity (non-trusted)
    "no company name tokens",                 # identity
    "lacks corroboration",                    # single-token corroboration guard
    "primary fiscal year",                    # FY primary-year gate (the Avianca case)
    "no year from",                           # FY not found in downloaded front matter
    "no annual-report document markers",      # doc-type name gate
    "signal 3 length gate failed",            # Signal 3 (length)
    "signal 5 publisher gate failed",         # Signal 5 (publisher)
    "quarterly/interim document rejected",    # negative doc-type gate (content)
    "sec-regulatory cover markers absent",    # SEC gate
    "trusted source but document company",    # trusted-path identity mismatch
)


def _is_gate_rejection(reason: str) -> bool:
    r = (reason or "").lower()
    return any(m in r for m in _GATE_REJECT_MARKERS)


# ── git + fingerprint helpers ────────────────────────────────────────────────
def _git(args: list[str]) -> str | None:
    try:
        r = subprocess.run(["git", *args], cwd=_ROOT, capture_output=True,
                           text=True, timeout=15)
        return r.stdout.strip() if r.returncode == 0 else None
    except Exception:
        return None


def _head() -> str | None:
    return _git(["rev-parse", "HEAD"])


def _commit_exists(sha: str) -> bool:
    return _git(["cat-file", "-e", f"{sha}^{{commit}}"]) is not None


def _verify_fingerprint() -> str | None:
    try:
        return hashlib.sha256(_VERIFY_PY.read_bytes()).hexdigest()
    except Exception:
        return None


def _gate_change_commits(since: str) -> list[tuple[str, str]]:
    """(short_sha, subject) for commits in (since..HEAD] carrying `Gate-Change: true`."""
    out = _git(["log", f"{since}..HEAD", "--format=%H%x1f%B%x1e"])
    if not out:
        return []
    found = []
    for rec in out.split("\x1e"):
        rec = rec.strip()
        if not rec:
            continue
        sha, _, body = rec.partition("\x1f")
        if re.search(r"(?im)^[ \t]*Gate-Change:[ \t]*true[ \t]*$", body):
            subj = (body.strip().splitlines() or [""])[0]
            found.append((sha.strip()[:9], subj))
    return found


def _load_meta() -> dict | None:
    try:
        return json.loads(_META_PATH.read_text(encoding="utf-8"))
    except Exception:
        return None


def _save_meta(head: str | None, fingerprint: str | None) -> None:
    _META_PATH.write_text(json.dumps({
        "last_swept_commit": head,
        "verify_fingerprint": fingerprint,
        "swept_at": datetime.now(timezone.utc).isoformat(),
    }, indent=2), encoding="utf-8")


# ── SHARED detection (imported by api.py + streamlit_app.py) ─────────────────
def sweep_status(since: str | None = None) -> dict:
    """Is a sweep due? Pure detection — no DB reads, no verify calls, cheap."""
    head = _head()
    fp = _verify_fingerprint()
    meta = _load_meta()
    reasons: list[str] = []
    notes: list[str] = []
    tagged: list[tuple[str, str]] = []

    last = since or (meta or {}).get("last_swept_commit")
    last_fp = (meta or {}).get("verify_fingerprint")

    if meta is None and since is None:
        reasons.append("no prior sweep recorded")
    else:
        if fp and last_fp and fp != last_fp:
            reasons.append("verify.py fingerprint changed since last sweep")
        if head and last:
            if not _commit_exists(last):
                reasons.append(f"recorded commit {last[:9]} not found (history rewrite?)")
            elif head != last:
                tagged = _gate_change_commits(last)
                if tagged:
                    reasons.append(f"{len(tagged)} Gate-Change commit(s) since {last[:9]}")
                else:
                    notes.append(f"HEAD advanced past {last[:9]} but no Gate-Change commits")
        elif not head:
            notes.append("git HEAD unavailable — fingerprint-only detection")
        elif not last:
            reasons.append("no last_swept_commit recorded")

    return {
        "due": bool(reasons),
        "reasons": reasons,
        "notes": notes,
        "head": head,
        "last_swept_commit": last,
        "tagged_commits": tagged,
        "verify_fingerprint": fp,
    }


def format_due_warning(status: dict) -> str | None:
    """Human warning string if due, else None. Same message for both entrypoints."""
    if not status.get("due"):
        return None
    lines = ["⚠️  Cache sweep DUE — verification gate logic may have changed since the cache was last validated:"]
    for r in status["reasons"]:
        lines.append(f"     - {r}")
    for sha, subj in status.get("tagged_commits", []):
        lines.append(f"       · {sha}  {subj[:70]}")
    lines.append("     Cached results may include stale accepts. Run:  python sweep_cache.py --apply")
    lines.append("     (full re-verify of cached rows; minutes-scale — run it backgrounded, not inline.)")
    return "\n".join(lines)


# ── row -> verify() inputs (faithful reconstruction) ─────────────────────────
def _intent_for(row: dict) -> dict:
    # company_canonical is the canonical KEY; its distinctive tokens are what the
    # identity check needs. raw_company == company_name => divergence gate is a
    # no-op (as it was for the original in-jurisdiction resolution).
    key = row["company_canonical"]
    # Re-offer the SAME fy candidate the row was cached under (matched_fy), NOT a
    # naive [fiscal_year]: India split-year reports (e.g. "FY2023-24", primary
    # year 2024) are cached under fiscal_year=2023 and would be FALSELY purged by
    # the FY-primary-year gate if re-verified against ['2023'] alone.
    mf = (row.get("matched_fy") or "").strip() or str(row["fiscal_year"])
    return {"company_name": key, "raw_company": key, "fy_candidates": [mf], "cik": None}


def _candidate_for(row: dict) -> dict:
    # Reproduce the trusted-source flag the aggregators path set originally, so a
    # trusted-host row isn't purged by gates (Signal 3/5) it never had applied.
    return {"url": row["url"], "source": row.get("source") or "",
            "skip_company_check": (row.get("source") == "aggregators")}


def _rows() -> list[dict]:
    conn = sqlite3.connect(cache.DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        return [dict(r) for r in conn.execute("SELECT rowid, * FROM results")]
    finally:
        conn.close()


def _audit(record: dict) -> None:
    with open(_AUDIT_PATH, "a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")


def run(apply: bool, preview: bool, since: str | None) -> None:
    status = sweep_status(since)
    head = status["head"]
    mode = "APPLY" if apply else ("PREVIEW" if preview else "DRY-RUN")
    print(f"===== cache sweep [{mode}] db={cache.DB_PATH} =====")
    print(f"due={status['due']}  head={head}  last_swept={status['last_swept_commit']}")
    for r in status["reasons"]:
        print(f"  reason: {r}")
    for n in status["notes"]:
        print(f"  note:   {n}")

    rows = _rows()
    print(f"\ncached rows: {len(rows)}")

    if not apply and not preview:
        print("\n[DRY-RUN] rows that WOULD be re-verified (full scope):")
        for row in rows:
            print(f"  {row['company_canonical']!r:26} FY{row['fiscal_year']} "
                  f"{row['doc_type']!r:14} src={row.get('source') or '':11} {row['url'][:50]}")
        print("\n  Run --preview to live-verify without deleting, or --apply to execute.")
        return

    if apply:
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        backup = f"{cache.DB_PATH}.bak-{stamp}"
        # SQLite online backup API — a consistent snapshot that INCLUDES any
        # uncheckpointed WAL, unlike a live shutil.copy2 of the .db file alone
        # (which can miss the -wal sidecar and yield an inconsistent/stale backup).
        src = sqlite3.connect(cache.DB_PATH)
        dst = sqlite3.connect(backup)
        try:
            src.backup(dst)
        finally:
            dst.close()
            src.close()
        print(f"[APPLY] backed up cache.db -> {backup}")

    conn = sqlite3.connect(cache.DB_PATH)
    conn.row_factory = sqlite3.Row
    purged, kept, inconclusive = [], 0, []
    t0 = time.time()
    for i, row in enumerate(rows, 1):
        intent, cand = _intent_for(row), _candidate_for(row)
        rt = time.time()
        try:
            res = verify(cand, intent)
        except Exception as exc:
            res = {"ok": False, "reason": f"sweep verify exception: {type(exc).__name__}: {exc}"}
        dt = time.time() - rt
        ok = bool(res.get("ok"))
        reason = res.get("reason", "")
        label = f"{row['company_canonical']!r} FY{row['fiscal_year']} {row['doc_type']!r}"

        if ok:
            kept += 1
            print(f"  [{i}/{len(rows)}] KEEP  {label}  ({dt:.1f}s)")
        elif _is_gate_rejection(reason):
            print(f"  [{i}/{len(rows)}] PURGE {label}  ({dt:.1f}s) — {reason}")
            purged.append({"company_key": row["company_canonical"], "fy": row["fiscal_year"],
                           "doc_type": row["doc_type"], "url": row["url"],
                           "old_verified_at": row.get("verified_at"), "fail_reason": reason})
            if apply:
                conn.execute("DELETE FROM results WHERE rowid=?", (row["rowid"],))
                conn.commit()                      # per-row commit -> crash-safe
                _audit({"swept_at": datetime.now(timezone.utc).isoformat(),
                        "target_commit": head, **purged[-1]})
        else:
            inconclusive.append((label, reason))
            print(f"  [{i}/{len(rows)}] KEEP* {label}  ({dt:.1f}s) — inconclusive (not a gate verdict): {reason}")
    conn.close()
    elapsed = time.time() - t0

    print(f"\n=== SUMMARY [{mode}] ===")
    print(f"  rows checked     : {len(rows)}")
    print(f"  kept (passed)    : {kept}")
    print(f"  purged (gate-fail): {len(purged)}"
          + ("" if apply else "  [PREVIEW — not deleted]"))
    print(f"  inconclusive kept: {len(inconclusive)} (transport/parse/unknown — never purged)")
    for lbl, rsn in inconclusive:
        print(f"       · {lbl}: {rsn}")
    print(f"  wall-clock       : {elapsed:.1f}s  ({elapsed/max(len(rows),1):.1f}s/row avg)")

    if apply:
        _save_meta(head, _verify_fingerprint())    # advance marker ONLY after full completion
        print(f"  marker advanced  : last_swept_commit={head} (+ verify.py fingerprint)")
    else:
        print("  [PREVIEW] marker NOT advanced, nothing deleted.")


def main() -> None:
    logging.basicConfig(level=logging.WARNING)
    ap = argparse.ArgumentParser(description="Commit-triggered cache resweep (Fix 2).")
    # --apply and --preview are mutually exclusive: argparse rejects both together
    # (exit 2) before run() executes, so --preview can never reach the destructive
    # apply path. Neither given => dry-run.
    mode = ap.add_mutually_exclusive_group()
    mode.add_argument("--apply", action="store_true", help="execute: backup, re-verify, purge, advance marker")
    mode.add_argument("--preview", action="store_true", help="live re-verify all rows, report, delete nothing")
    ap.add_argument("--all", action="store_true", help="full-scope sweep (default and only scope; explicit affirmation)")
    ap.add_argument("--since", metavar="COMMIT", help="override last-swept commit for the due check")
    args = ap.parse_args()
    run(apply=args.apply, preview=args.preview, since=args.since)


if __name__ == "__main__":
    main()
