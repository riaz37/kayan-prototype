"""
Merge duplicate open tickets that belong to the same caller.

Before the "one conversation per number" rule, every WhatsApp request opened a new
ticket, so one person could end up with TK-2026-2031 … 2037. This merges each
number's open tickets into the oldest one: messages move across, the extras are
closed and marked `merged_into`, and a note records what happened.

    python scripts/merge_duplicate_tickets.py            # dry run, prints the plan
    python scripts/merge_duplicate_tickets.py --apply    # perform the merge

Set DATA_DIR to point at another database (e.g. a copy) before running.
"""
import argparse
import os
import sys
from collections import defaultdict

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from backend import store as db  # noqa: E402

OPEN = db.OPEN_TICKET_STATUSES
NOTE_AR = "تم دمج هذه التذكرة مع التذكرة {target} للحفاظ على محادثة واحدة لكل رقم."


def plan(conn):
    """Group open tickets by caller (phone, else beneficiary), oldest first."""
    placeholders = ",".join("?" * len(OPEN))
    rows = [dict(r) for r in conn.execute(
        f"SELECT * FROM tickets WHERE status IN ({placeholders}) ORDER BY opened_at", OPEN)]
    groups = defaultdict(list)
    for t in rows:
        key = db.phone_key(t["phone"]) if t.get("phone") else (t.get("beneficiary_id") or "")
        if key:
            groups[key].append(t)
    return {k: v for k, v in groups.items() if len(v) > 1}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true", help="write the changes (default: dry run)")
    args = ap.parse_args()

    conn = db._get_conn()
    groups = plan(conn)
    if not groups:
        print("No duplicate open tickets found.")
        return

    merged = 0
    for key, tickets in groups.items():
        target, extras = tickets[0], tickets[1:]
        print(f"\n{key}: keep {target['id']} ({target['opened_at'][:16]}) "
              f"← merge {', '.join(t['id'] for t in extras)}")
        for extra in extras:
            count = conn.execute("SELECT COUNT(*) c FROM ticket_messages WHERE ticket_id = ?",
                                 (extra["id"],)).fetchone()["c"]
            print(f"    {extra['id']}: {count} message(s), subject: {extra['subject_ar']}")
            if not args.apply:
                continue
            # Keep the original subject visible in the thread, then move the messages.
            db.append_ticket_message(target["id"], f"— {extra['subject_ar']}",
                                     direction="inbound", sender="beneficiary", dedupe=True)
            conn.execute("UPDATE ticket_messages SET ticket_id = ? WHERE ticket_id = ?",
                         (target["id"], extra["id"]))
            db.append_ticket_message(extra["id"], NOTE_AR.format(target=target["id"]),
                                     direction="outbound", sender="system", is_internal=True)
            conn.execute("UPDATE tickets SET status='closed', closed_at=?, updated_at=?, merged_into=? WHERE id=?",
                         (db.now_iso(), db.now_iso(), target["id"], extra["id"]))
            conn.commit()
            merged += 1
        if args.apply:
            # Messages moved in keep their own timestamps; refresh the thread's activity.
            conn.execute("UPDATE tickets SET updated_at=? WHERE id=?", (db.now_iso(), target["id"]))
            conn.commit()

    print(f"\n{'Merged' if args.apply else 'Would merge'} {merged if args.apply else sum(len(v) - 1 for v in groups.values())} "
          f"ticket(s) across {len(groups)} caller(s).")
    if not args.apply:
        print("Dry run — re-run with --apply to perform the merge.")


if __name__ == "__main__":
    main()
