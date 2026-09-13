# Plan: Ticket Lifecycle Completeness

## Goal
Add `assign_ticket`, `reply_to_ticket`, `list_staff`, and `get_ticket` tools so the agent can manage the full ticket lifecycle.

## Current State
- Backend APIs exist and work: assign, reply, get_ticket, list_staff
- Agent only has `create_ticket` — no way to assign, reply, or list staff

## Changes

### 1. `agent/tools.py` — 4 new tools

#### A. Handler functions (add after line ~183)

```python
def handle_list_staff() -> dict:
    return _get("/crm/staff")

def handle_get_ticket(ticket_id: str) -> dict:
    return _get(f"/crm/tickets/{ticket_id}")

def handle_assign_ticket(ticket_id: str, staff_id: str) -> dict:
    return _patch(f"/crm/tickets/{ticket_id}/assign", {"staff_id": staff_id})

def handle_reply_to_ticket(ticket_id: str, body_ar: str, send_to_whatsapp: bool = True) -> dict:
    return _post(f"/crm/tickets/{ticket_id}/reply", {
        "body_ar": body_ar,
        "sender": "agent",
        "send_to_whatsapp": send_to_whatsapp,
    })
```

#### B. TOOL_HANDLERS entries (add after line ~207)

```python
"list_staff": lambda **kw: handle_list_staff(),
"get_ticket": lambda **kw: handle_get_ticket(**kw),
"assign_ticket": lambda **kw: handle_assign_ticket(**kw),
"reply_to_ticket": lambda **kw: handle_reply_to_ticket(**kw),
```

#### C. TOOLS_OPENAI schemas (add after create_ticket entry, ~line 543)

4 new OpenAI function-calling schema entries following the existing pattern.

### 2. `agent/prompts.py` — Update Agent 5 flow

Update the "Speak to Employee" section to mention:
- After `create_ticket`, use `list_staff` to find appropriate staff
- Use `assign_ticket` to assign if user requests specific staff
- Use `reply_to_ticket` for follow-up responses

### 3. `agent/test_hard_scenarios.py` — ~8 unit tests

- list_staff returns staff list
- get_ticket returns detail
- assign_ticket succeeds
- assign_ticket invalid ticket → error
- assign_ticket invalid staff → error
- reply_to_ticket succeeds
- reply_to_ticket internal note
- Full lifecycle: create → assign → reply → close

### 4. `agent/test_live_integration.py` — ~3 live tests

- list_staff returns staff
- create_ticket → assign_ticket → reply_to_ticket flow
- get_ticket returns conversation history

## Execution Order
1. tools.py handlers + registrations + schemas
2. prompts.py updates
3. test_hard_scenarios.py unit tests
4. test_live_integration.py live tests
5. Run both suites to verify
