"""
Merge duplicate open tickets that belong to the same caller.

Before the "one conversation per number" rule, every WhatsApp request opened a new
ticket, so one person could end up with TK-2026-2031 … 2037. This merges each
number's open tickets into the oldest one: messages move across, the extras are
closed and marked `merged_into`, and a note records what happened.

    python scripts/merge_duplicate_tickets.py            # dry run, prints the plan
    python scripts/merge_duplicate_tickets.py --apply    # perform the merge

Set DATA_DIR to point at another database (e.g. a copy) before running. On a
deployed environment use POST /admin/merge-duplicate-tickets instead.
"""
import argparse
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from backend.maintenance import merge_duplicate_tickets  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true", help="write the changes (default: dry run)")
    args = ap.parse_args()

    report = merge_duplicate_tickets(apply=args.apply)
    if not report["groups"]:
        print("No duplicate open tickets found.")
        return

    for group in report["groups"]:
        print(f"\n{group['caller']}: keep {group['kept']}")
        for extra in group["merged"]:
            print(f"    {extra['id']}: {extra['messages']} message(s), subject: {extra['subject_ar']}")

    verb = "Merged" if args.apply else "Would merge"
    print(f"\n{verb} {report['merged']} ticket(s) across {report['callers']} caller(s).")
    if not args.apply:
        print("Dry run — re-run with --apply to perform the merge.")


if __name__ == "__main__":
    main()
