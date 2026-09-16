"""
Maintenance tasks that operate on the whole database.

Currently one task: merge duplicate open tickets that belong to the same caller.
Before the "one conversation per number" rule every WhatsApp request opened a new
ticket, so a person could end up with TK-2026-2031 … 2037.

Used by `scripts/merge_duplicate_tickets.py` (locally) and by
`POST /admin/merge-duplicate-tickets` (on a deployed environment, admins only).
"""
from collections import defaultdict

from backend import store as db

NOTE_AR = "تم دمج هذه التذكرة مع التذكرة {target} للحفاظ على محادثة واحدة لكل رقم."


def find_duplicate_groups():
    """Open tickets grouped by caller (phone, else beneficiary), oldest first."""
    conn = db._get_conn()
    placeholders = ",".join("?" * len(db.OPEN_TICKET_STATUSES))
    rows = [dict(r) for r in conn.execute(
        f"SELECT * FROM tickets WHERE status IN ({placeholders}) ORDER BY opened_at",
        db.OPEN_TICKET_STATUSES)]
    groups = defaultdict(list)
    for t in rows:
        key = db.phone_key(t["phone"]) if t.get("phone") else (t.get("beneficiary_id") or "")
        if key:
            groups[key].append(t)
    return {k: v for k, v in groups.items() if len(v) > 1}


def merge_duplicate_tickets(apply=False):
    """Merge each caller's open tickets into their oldest one.

    Messages move to the surviving ticket, the extras are closed and stamped with
    `merged_into`, and an internal note records the merge. Returns a report; with
    `apply=False` nothing is written.
    """
    conn = db._get_conn()
    groups = find_duplicate_groups()
    report = {"callers": len(groups), "merged": 0, "applied": bool(apply), "groups": []}

    for key, tickets in groups.items():
        target, extras = tickets[0], tickets[1:]
        entry = {"caller": key, "kept": target["id"], "merged": []}
        for extra in extras:
            count = conn.execute("SELECT COUNT(*) c FROM ticket_messages WHERE ticket_id = ?",
                                 (extra["id"],)).fetchone()["c"]
            entry["merged"].append({"id": extra["id"], "subject_ar": extra["subject_ar"], "messages": count})
            if not apply:
                continue
            # Keep the original subject visible in the thread, then move its messages over.
            db.append_ticket_message(target["id"], f"— {extra['subject_ar']}",
                                     direction="inbound", sender="beneficiary", dedupe=True)
            conn.execute("UPDATE ticket_messages SET ticket_id = ? WHERE ticket_id = ?",
                         (target["id"], extra["id"]))
            db.append_ticket_message(extra["id"], NOTE_AR.format(target=target["id"]),
                                     direction="outbound", sender="system", is_internal=True)
            conn.execute(
                "UPDATE tickets SET status='closed', closed_at=?, updated_at=?, merged_into=? WHERE id=?",
                (db.now_iso(), db.now_iso(), target["id"], extra["id"]))
            conn.commit()
            report["merged"] += 1
        if apply:
            conn.execute("UPDATE tickets SET updated_at=? WHERE id=?", (db.now_iso(), target["id"]))
            conn.commit()
        report["groups"].append(entry)

    if not apply:
        report["merged"] = sum(len(g["merged"]) for g in report["groups"])
    return report
