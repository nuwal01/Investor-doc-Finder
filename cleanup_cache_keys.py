"""One-time cache-key cleanup: migrate mis-keyed rows in cache.db onto the
canonical (company key, fiscal_year, doc_type) produced by the *current*
cache._key / cache._norm_doc_type. Standalone; does NOT modify cache.py.

Dry-run by default (prints the plan, writes nothing). Pass --apply to execute;
--apply first backs up cache.db to cache.db.bak-<UTCstamp>.

Policy per canonical group = rows sharing (canonical key, fiscal_year, canonical
doc_type):
  * 1 row                   -> REKEY in place iff its stored key/doc_type differ
                               from canonical (makes orphaned rows reachable).
  * >1 row, all same URL    -> MERGE: keep most-recently-verified row's metadata,
                               rekey it to canonical, delete the rest.
  * >1 row, different URLs   -> CONFLICT: leave every row untouched, flag for
                               manual review (never silently pick one).

Different fiscal_year => different group => never merged (R R Kabel FY2023 vs
FY2024 stays two rows).
"""
import argparse
import shutil
import sqlite3
import sys
from collections import defaultdict
from datetime import datetime, timezone

import cache


def load_rows(conn):
    conn.row_factory = sqlite3.Row
    return [dict(r) for r in conn.execute("SELECT rowid, * FROM results")]


def canonical(r):
    return (cache._key(r["company_canonical"]),
            r["fiscal_year"],
            cache._norm_doc_type(r["doc_type"]))


def build_plan(rows):
    groups = defaultdict(list)
    for r in rows:
        groups[canonical(r)].append(r)

    merges, rekeys, conflicts, noops = [], [], [], []
    for (ck, fy, cdt), rs in sorted(groups.items()):
        if len(rs) == 1:
            r = rs[0]
            if r["company_canonical"] != ck or r["doc_type"] != cdt:
                rekeys.append((r, ck, cdt))
            else:
                noops.append(r)
            continue
        urls = {r["url"] for r in rs}
        if len(urls) == 1:
            keep = max(rs, key=lambda r: r["verified_at"] or "")
            drop = [r for r in rs if r["rowid"] != keep["rowid"]]
            merges.append(((ck, fy, cdt), keep, drop))
        else:
            conflicts.append(((ck, fy, cdt), rs))
    return merges, rekeys, conflicts, noops


def print_plan(rows, merges, rekeys, conflicts, noops):
    print(f"\nTotal rows: {len(rows)}\n")

    print(f"=== MERGES (same URL, >1 row -> 1) : {len(merges)} groups ===")
    for (ck, fy, cdt), keep, drop in merges:
        oldpks = sorted({(r['company_canonical'], r['doc_type']) for r in [keep]+drop})
        print(f"  [{ck!r} FY{fy} {cdt!r}]  {len(drop)+1} -> 1")
        print(f"      old keys: {oldpks}")
        print(f"      KEEP  verified_at={keep['verified_at']}  {keep['url'][:60]}")
        for d in drop:
            print(f"      DROP  ({d['company_canonical']!r},{d['doc_type']!r}) verified_at={d['verified_at']}")

    print(f"\n=== REKEYS (lone row, stored key != canonical) : {len(rekeys)} ===")
    for r, ck, cdt in rekeys:
        print(f"  ({r['company_canonical']!r},{r['doc_type']!r}) FY{r['fiscal_year']} -> ({ck!r},{cdt!r})   {r['url'][:50]}")

    print(f"\n=== CONFLICTS (same canonical key, DIFFERENT urls) : {len(conflicts)} — LEFT UNTOUCHED ===")
    for (ck, fy, cdt), rs in conflicts:
        print(f"  [{ck!r} FY{fy} {cdt!r}] {len(rs)} rows, {len({r['url'] for r in rs})} urls:")
        for r in rs:
            print(f"      ({r['company_canonical']!r},{r['doc_type']!r})  {r['url'][:70]}")

    deletes = sum(len(d) for _, _, d in merges)
    print(f"\n=== SUMMARY ===")
    print(f"  rows before          : {len(rows)}")
    print(f"  merge groups         : {len(merges)}  (rows deleted: {deletes})")
    print(f"  rekeys (in place)    : {len(rekeys)}")
    print(f"  conflicts (untouched): {len(conflicts)}")
    print(f"  no-ops (already canon): {len(noops)}")
    print(f"  rows AFTER           : {len(rows) - deletes}")


def confirm_known(rows):
    """Confirm the specific cases named in the task resolve as expected."""
    groups = defaultdict(list)
    for r in rows:
        groups[canonical(r)].append(r)

    def count_old(pattern_fn):
        return sum(1 for r in rows if pattern_fn(r))

    print("\n=== KNOWN-CASE CONFIRMATION (post-cleanup canonical groups) ===")
    checks = [
        ("ASML FY2023 annual_report", ("asml", 2023, "annual_report")),
        ("Avianca FY2023 annual_report", ("avianca", 2023, "annual_report")),
        ("R R Kabel FY2023 annual_report", ("kabel", 2023, "annual_report")),
        ("R R Kabel FY2024 annual_report (must stay separate)", ("kabel", 2024, "annual_report")),
        ("Tullow FY2023 annual_report", ("tullow", 2023, "annual_report")),
        ("Hermès FY2023 annual_report", ("hermes", 2023, "annual_report")),
    ]
    for label, key in checks:
        rs = groups.get(key, [])
        urls = {r["url"] for r in rs}
        verdict = "OK->1" if len(urls) <= 1 else f"CONFLICT ({len(urls)} urls)"
        print(f"  {label:52} : {len(rs)} row(s) -> {verdict}")

    tenk_old = count_old(lambda r: r["doc_type"] == "10-K")
    tenk_canon = sum(len(v) for k, v in groups.items() if k[2] == "10-k")
    print(f"  doc_type '10-K' rows (old) : {tenk_old}  ->  canonical '10-k' groups hold {tenk_canon} row(s)")

    split = count_old(lambda r: r["doc_type"] == "annual report")
    print(f"  doc_type 'annual report' (space) rows folded into 'annual_report' : {split}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true", help="write changes (default: dry-run)")
    args = ap.parse_args()

    conn = sqlite3.connect(cache.DB_PATH)
    rows = load_rows(conn)
    merges, rekeys, conflicts, noops = build_plan(rows)

    mode = "APPLY" if args.apply else "DRY-RUN"
    print(f"===== cache-key cleanup [{mode}] db={cache.DB_PATH} =====")
    print_plan(rows, merges, rekeys, conflicts, noops)
    confirm_known(rows)

    if not args.apply:
        print("\n[DRY-RUN] no changes written. Re-run with --apply to execute.")
        conn.close()
        return

    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    backup = f"{cache.DB_PATH}.bak-{stamp}"
    shutil.copy2(cache.DB_PATH, backup)
    print(f"\n[APPLY] backed up cache.db -> {backup}")

    cur = conn.cursor()
    for _, keep, drop in merges:
        for d in drop:
            cur.execute("DELETE FROM results WHERE rowid=?", (d["rowid"],))
    for (ck, fy, cdt), keep, drop in merges:
        if keep["company_canonical"] != ck or keep["doc_type"] != cdt:
            cur.execute("UPDATE results SET company_canonical=?, doc_type=? WHERE rowid=?",
                        (ck, cdt, keep["rowid"]))
    for r, ck, cdt in rekeys:
        cur.execute("UPDATE results SET company_canonical=?, doc_type=? WHERE rowid=?",
                    (ck, cdt, r["rowid"]))
    conn.commit()

    after = len(load_rows(conn))
    print(f"[APPLY] done. rows now: {after}")
    conn.close()


if __name__ == "__main__":
    main()
