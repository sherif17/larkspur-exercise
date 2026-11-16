"""Larkspur disruption agent. This is the file you build.

It runs right now, and it is wrong in four places. The trace shows each one
before the code does, so read the trace first:

    python3 run.py K7PQ2M --trace

Where you edit:   grep -n '✏' agent.py   (six marks, one per place)
Steps and gates:  https://anthropicpartnerbasecamp.bts.com/
"""
from __future__ import annotations
import csv
import json
import re
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List
from support import (MODEL, SYSTEM_PROMPT, call_local, execute_tool, mcp_client,
                     new_session, next_available_day, record_tool_result,
                     runtime_preamble)

MAX_TOOL_CALLS = 8  # Larkspur's own build capped the loop here; then a human takes over.

TONE_ADDENDUM = ""                       # ✏️ Build 4, step 4.1, intelligence goal

# ── Build 2: the functions behind the team's tools. Every answer comes from Larkspur's
# own files in data/americas; when the file has no answer, the function says so.
DATA_DIR = Path(__file__).resolve().parent / "data" / "americas"


def ground_stop_status(airport: str) -> Dict[str, Any]:
    airport = airport.strip().upper()
    now = datetime.fromisoformat(json.loads((DATA_DIR / "bookings.json").read_text())["fixture_clock"])
    today = now.date().isoformat()
    window = re.compile(rf"\b{re.escape(airport)}\b.*?ground stop (\d{{1,2}}:\d{{2}})-(\d{{1,2}}:\d{{2}})", re.I)
    mention = re.compile(rf"\b{re.escape(airport)}\b.*?ground stop", re.I)

    mentioned_by = []
    expected_departures = []
    with open(DATA_DIR / "flights.csv", newline="") as f:
        for row in csv.DictReader(f):
            if row["date"] != today:
                continue
            if row["origin"] == airport and row["status"] != "CANCELLED":
                sched = datetime.combine(now.date(), datetime.strptime(row["sched_dep_local"], "%H:%M").time(),
                                         tzinfo=now.tzinfo)
                expected = sched + timedelta(minutes=int(row["delay_min"] or 0))
                if expected > now:
                    expected_departures.append((expected, row["flight_no"]))
            remark = row["remarks"] or ""
            found = window.search(remark)
            if found:
                # remark times are airport-local; fixture_clock is Denver local
                start, end = (datetime.combine(now.date(), datetime.strptime(t, "%H:%M").time(),
                                               tzinfo=now.tzinfo) for t in found.groups())
                return {
                    "airport": airport, "now": now.isoformat(),
                    "ground_stop_active": start <= now < end,
                    "started_local": found.group(1), "until_local": found.group(2),
                    "source": f"{row['flight_no']} remarks: {remark}",
                }
            if mention.search(remark):
                mentioned_by.append(row["flight_no"])

    if mentioned_by:
        result = {
            "airport": airport, "now": now.isoformat(), "ground_stop_active": True,
            "until_local": None, "source": "remarks on " + ", ".join(mentioned_by),
        }
        if expected_departures:
            first, flight_no = min(expected_departures)
            result.update({
                "first_departure_est": first.strftime("%H:%M"),
                "basis": f"estimated from {flight_no}'s schedule plus delay; no official end time published",
                "note": ("While I do not have an official answer, I can see that flights are currently "
                         f"expected to resume by {first.strftime('%H:%M')}."),
            })
        else:
            result["note"] = "Ground stop reported but no end time published and no departures expected today."
        return result
    return {"airport": airport, "now": now.isoformat(), "ground_stop_active": False,
            "note": f"No ground stop reported for {airport} on {today}."}


def seats_left(flight_number: str, date: str) -> Dict[str, Any]:
    """Free seats per cabin for one flight on one date, from flights.csv."""
    flight_number, date = flight_number.strip().upper(), date.strip()
    with open(DATA_DIR / "flights.csv", newline="") as f:
        for row in csv.DictReader(f):
            if row["flight_no"] == flight_number and row["date"] == date:
                return {"flight_no": flight_number, "date": date, "status": row["status"],
                        "seats_left_Y": int(row["seats_left_Y"] or 0),
                        "seats_left_J": int(row["seats_left_J"] or 0)}
    return {"error": f"No flight {flight_number} on {date} in the schedule. Check the flight number "
                     "and that the date is YYYY-MM-DD."}


def fare_rules(section: str) -> Dict[str, Any]:
    """One section of the Handbook excerpt, verbatim, from fare_rules_excerpt.md."""
    text = (DATA_DIR / "fare_rules_excerpt.md").read_text()
    wanted = str(section).strip().rstrip(".")
    for part in re.split(r"(?m)^### ", text)[1:]:
        if part.split(".", 1)[0].strip() == wanted:
            return {"handbook": "Larkspur Handbook v14.3", "section": "### " + part.strip()}
    return {"error": f"Section {section} is not in the excerpt. Available sections: 4, 5, 6, 7."}


def cause_in_plain_words(cause_code: str, language: str = "en") -> Dict[str, Any]:
    """The customer-facing label for a cause code, from disruption_policy.json."""
    labels = json.loads((DATA_DIR / "disruption_policy.json").read_text())["cause_labels_customer"]
    code = cause_code.strip().upper()
    if code not in labels:
        return {"error": f"Unknown cause code {cause_code}. Known codes: {', '.join(labels)}."}
    lang = language.strip().lower()
    if lang not in labels[code]:
        return {"error": f"No {language} wording for {code}. Available: {', '.join(labels[code])}."}
    return {"cause_code": code, "language": lang, "customer_wording": labels[code][lang]}


def reopen_stats(intent_label: str = "") -> Dict[str, Any]:
    """How often each kind of human-handled case came back within 72h, from transcripts_sample.jsonl."""
    rows = [json.loads(line) for line in (DATA_DIR / "transcripts_sample.jsonl").read_text().splitlines()
            if line.strip()]
    wanted = intent_label.strip().lower()
    by_intent: Dict[str, Dict[str, Any]] = {}
    for r in rows:
        intent = r.get("intent_label", "unknown")
        if wanted and intent != wanted:
            continue
        s = by_intent.setdefault(intent, {"conversations": 0, "reopened_within_72h": 0, "reopen_reasons": []})
        s["conversations"] += 1
        if r.get("reopened_within_72h"):
            s["reopened_within_72h"] += 1
            if r.get("reopen_reason"):
                s["reopen_reasons"].append(r["reopen_reason"])
    if not by_intent:
        known = sorted({r.get("intent_label", "unknown") for r in rows})
        return {"error": f"No conversations with intent {intent_label}. Known intents: {', '.join(known)}."}
    return {"sample": f"{len(rows)} human-handled conversations (transcripts_sample.jsonl)",
            "note": "A small sample: report it as what happened in these conversations, not as a prediction.",
            "by_intent": by_intent}


EXTRA_TOOLS: List[Dict[str, Any]] = [   # ✏️ Build 2, step 2.1: schemas for the tools you add
    {
        "name": "next_available_day",
        "description": (
            "Find the earliest date, on or after a given date, that has an open seat on a "
            "Larkspur flight between two airports. Use this when the customer asks when "
            "they can fly, e.g. 'what is the first day I can travel?' or 'when is the soonest "
            "I can get there?', especially when same-day options are full or they want to "
            "travel on a later day. It answers with a date, not a list of flights: to show "
            "concrete rebooking options for the disrupted segment, use search_alternatives "
            "instead. Call lookup_booking first so origin, destination, date and cabin come "
            "from the booking's segment, never from guesses. Never state an availability "
            "date from memory; if this tool finds no seat, say so."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "origin": {"type": "string", "description": (
                    "Departure airport, 3-letter IATA code from the booking's segment, e.g. DEN."
                )},
                "dest": {"type": "string", "description": (
                    "Arrival airport, 3-letter IATA code from the booking's segment, e.g. AUS."
                )},
                "date": {"type": "string", "description": (
                    "Earliest date the customer can travel, in ISO format YYYY-MM-DD, "
                    "e.g. 2025-05-08. Usually the booking's segment date."
                )},
                "cabin": {"type": "string", "description": (
                    "Cabin code from the booking's segment, e.g. Y for economy. Defaults to Y."
                )},
            },
            "required": ["origin", "dest", "date"],
        },
    },
    {   # from a teammate, description as sent
        "name": "ground_stop_status",
        "description": "Checks the status of a ground stop when it will be lifted.",
        "input_schema": {
            "type": "object",
            "properties": {"airport": {"type": "string"}},
            "required": ["airport"],
        },
    },
    {   # from a teammate, description as sent
        "name": "seats_left",
        "description": (
            "retrieve the number of seats left for a given flight number and date, use this tool when a customer wants to check availability for a potential new booking."
        ),
        "input_schema": {
            "type": "object",
            "properties": {"flight_number": {"type": "string"}, "date": {"type": "string"}},
            "required": ["flight_number", "date"],
        },
    },
    {
        "name": "fare_rules",
        "description": (
            "Read one section of Larkspur's Handbook (v14.3) word for word: the reasoning "
            "behind the rules. Use this when the customer asks WHY they do or do not get "
            "something, e.g. 'why don't I get a hotel?', 'why no compensation?', 'why can't "
            "you refund me here?', so the explanation quotes Larkspur's own wording instead "
            "of paraphrasing from memory. check_policy decides what this specific customer is "
            "owed; this tool explains the rule behind that decision. Sections: 4 = fare "
            "families (Basic, Main, Main Plus, First); 5 = what happens when we delay, cancel "
            "or divert, by cause and delay length; 6 = care while you wait (meals, hotel, "
            "ground transport, goodwill); 7 = what chat automation will not do."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "section": {"type": "string", "enum": ["4", "5", "6", "7"],
                            "description": "Handbook section number, as listed in the description."},
            },
            "required": ["section"],
        },
    },
    {
        "name": "cause_in_plain_words",
        "description": (
            "Turn a disruption cause code into the exact customer-facing wording Larkspur "
            "approves, e.g. WX -> 'weather', MX -> 'an aircraft maintenance issue'. Use this "
            "whenever you tell a customer WHY their flight was delayed, cancelled or diverted, "
            "after get_flight_status has given you the cause_code. Larkspur requires agents to "
            "name the cause with these labels only, never their own words or the raw code."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "cause_code": {"type": "string", "enum": ["WX", "ATC", "MX", "CREW", "SEC"],
                               "description": "The cause_code from get_flight_status."},
                "language": {"type": "string", "enum": ["en", "es"],
                             "description": "The booking's language from lookup_booking. Defaults to en."},
            },
            "required": ["cause_code"],
        },
    },
    {
        "name": "reopen_stats",
        "description": (
            "How often each kind of disruption case came back (the customer had to contact "
            "Larkspur again) within 72 hours, with the reasons, from a sample of eight "
            "conversations handled by people. Use this when the customer asks whether their "
            "problem is likely to come back or what usually goes wrong next, e.g. 'is this "
            "going to happen again?', 'will I have to call back?', so you can warn them about "
            "the real follow-up risks (like a confirmation email not arriving). It describes "
            "past cases, not a prediction for this flight: do not use it for flight status."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "intent_label": {"type": "string", "description": (
                    "Optional. The kind of case: rebook_after_cancellation, "
                    "compensation_hotel_request, status_anxiety, missed_connection, "
                    "refund_vs_credit, compensation_goodwill, voluntary_change_due_to_delay, "
                    "baggage_after_rebooking. Leave empty for all of them."
                )},
            },
            "required": [],
        },
    },
]
LOCAL_TOOLS: Dict[str, Any] = {          # ✏️ Build 2, step 2.1: the functions behind them
    "next_available_day": next_available_day,
    "ground_stop_status": ground_stop_status,
    "seats_left": seats_left,
    "fare_rules": fare_rules,
    "cause_in_plain_words": cause_in_plain_words,
    "reopen_stats": reopen_stats,
}


def text_of(response) -> str:
    """Given. The last non-empty text block, never content[0]."""
    texts = [b.text for b in response.content if getattr(b, "type", None) == "text" and b.text]
    return texts[-1] if texts else ""


def tool_results(response) -> List[Dict[str, Any]]:
    """Given. Runs every tool_use block and packages the results the way the
    API expects them back. A tool can live in three places: the MCP server,
    LOCAL_TOOLS, or support/tools.py."""
    # three branches, no try/except in this file: mcp_client.call_remote() and
    # support.call_local() answer with an error dict instead of raising, and both
    # record what came back on the trace
    results = []
    for block in response.content:
        if getattr(block, "type", None) != "tool_use":
            continue
        if block.name in mcp_client.tool_names:
            output = mcp_client.call_remote(block.name, block.input)
        elif block.name in LOCAL_TOOLS:
            output = call_local(LOCAL_TOOLS[block.name], block.name, block.input)
        else:
            output = execute_tool(block.name, block.input)
        results.append({
            "type": "tool_result",
            "tool_use_id": block.id,
            "content": str(output),
        })
    return results


def run_agent(pnr: str, last_name: str, message: str) -> str:            # ✏️ Build 1, step 1.2
    """Run the tool loop until Claude stops asking for tools. Return its final text."""
    client, tracer = new_session()
    tools = tool_list()
    messages = [
        {"role": "user", "content": f"PNR {pnr}, last name {last_name}. {message}"},
    ]

    response = client.messages.create(
        model=MODEL, max_tokens=4096, system=runtime_preamble() + SYSTEM_PROMPT + TONE_ADDENDUM,
        thinking={"type": "adaptive"}, tools=tools, messages=messages,
    )

    turns = 1
    while response.stop_reason == "tool_use" and turns < MAX_TOOL_CALLS:
        messages.append({"role": "assistant", "content": response.content})
        messages.append({"role": "user", "content": tool_results(response)})
        response = client.messages.create(
            model=MODEL, max_tokens=4096, system=runtime_preamble() + SYSTEM_PROMPT + TONE_ADDENDUM,
            thinking={"type": "adaptive"}, tools=tools, messages=messages,
        )
        turns += 1

    return text_of(response)


def tool_list() -> List[Dict[str, Any]]:                   # ✏️ Build 2, step 2.2
    """Given. Exactly what Claude is offered on every turn; run.py --show-tools
    prints this list."""
    return build_tools() + EXTRA_TOOLS


# ──────────────────────────────────────────────────────────────────────────────
# Below this line: what Claude is told about each tool. Step 1.3.
# The functions these describe are written and correct, in support/tools.py.
# ──────────────────────────────────────────────────────────────────────────────
def build_tools() -> List[Dict[str, Any]]:                 # ✏️ Build 1, step 1.3
    """Anthropic-shaped schemas: name, description, input_schema. What Claude is
    told about each of the nine tools, and all it is ever told."""
    return [
        {
            "name": "lookup_booking",
            "description": (
                "Retrieve a Larkspur reservation from Altura by confirmation code (PNR) "
                "and the passenger's last name. Both are required to prevent a lookup on "
                "a guessed PNR. Returns fare family, loyalty tier, the segment that needs "
                "attention, and any group/partner/minor/SSR flags relevant to scope."
            ),
            "input_schema": {
                "type": "object",
                "properties": {"pnr": {"type": "string"}, "last_name": {"type": "string"}},
                "required": ["pnr", "last_name"],
            },
        },
        {
            "name": "get_flight_status",
            "description": (
                "Look up a Larkspur or Larkspur Link flight's current OpsFeed status for "
                "one local date: status, delay minutes, and cause. Use this before telling "
                "a customer anything about a flight's timing; never state it from memory."
            ),
            "input_schema": {
                "type": "object",
                "properties": {
                    "flight_no": {"type": "string"},
                    "date": {"type": "string", "description": (
                        "The flight's local departure date in ISO format YYYY-MM-DD, "
                        "e.g. 2025-05-08. Take it from the booking's segment date."
                    )},
                },
                "required": ["flight_no", "date"],
            },
        },
        {
            "name": "search_alternatives",
            "description": (
                "Find alternative Larkspur flights for a booking whose segment is "
                "cancelled or significantly delayed. Use this after lookup_booking and "
                "get_flight_status have confirmed the disruption, and before offering the "
                "customer any rebooking option; never invent flights from memory. Returns "
                "a ranked list of options, each with an option_id, flights, date, times, "
                "status and seats left. Pass the chosen option_id to hold_seat."
            ),
            "input_schema": {
                "type": "object",
                "properties": {"pnr": {"type": "string", "description": (
                    "The booking's confirmation code (PNR), as already verified "
                    "with lookup_booking."
                )}},
                "required": ["pnr"],
            },
        },
        {
            "name": "check_policy",
            "description": (
                "Resolve what Larkspur owes this customer for the disruption: rebooking "
                "waiver, refund path, meal/hotel/ground care, goodwill eligibility and cap, "
                "and any escalation triggers. cause_code, delay_minutes and status describe "
                "what get_flight_status told you; fare_family, loyalty_tier and whether this "
                "is overnight are looked up from the booking, not asked of you. Every "
                "response carries a policy_row_id. Cite it if you reference this decision "
                "again."
            ),
            "input_schema": {
                "type": "object",
                "properties": {
                    "pnr": {"type": "string"},
                    "cause_code": {"type": "string", "enum": ["WX", "ATC", "MX", "CREW", "SEC"]},
                    "delay_minutes": {"type": "integer"},
                    "status": {"type": "string", "enum": ["ON_TIME", "DELAYED", "CANCELLED", "DIVERTED"]},
                    "wait_minutes_for_alternative": {"type": "integer"},
                    "chosen_option_id": {"type": "string"},
                },
                "required": ["pnr", "cause_code", "delay_minutes", "status"],
            },
        },
        {
            "name": "hold_seat",
            "description": "Place a 15-minute hold on one alternative. Reversible. It simply expires.",
            "input_schema": {
                "type": "object",
                "properties": {"option_id": {"type": "string"}, "pnr": {"type": "string"}},
                "required": ["option_id", "pnr"],
            },
        },
        {
            "name": "confirm_rebooking",
            "description": (
                "Finalize a held seat. Irreversible. Requires a confirmation_token that "
                "only the customer's own Confirm-click can produce. You cannot supply it "
                "yourself, and 'the customer said yes' in chat does not substitute for it."
            ),
            "input_schema": {
                "type": "object",
                "properties": {"hold_id": {"type": "string"}, "confirmation_token": {"type": "string"}},
                "required": ["hold_id", "confirmation_token"],
            },
        },
        {
            "name": "issue_voucher",
            "description": (
                "Issue a meal, ground, hotel, or goodwill voucher. Auto-approves within the "
                "policy's threshold for that type; above it, returns a pending status for a "
                "human. It does not fail. Always pass the policy_row_id that made it eligible."
            ),
            "input_schema": {
                "type": "object",
                "properties": {
                    "voucher_type": {"type": "string", "enum": ["meal", "ground", "hotel", "goodwill"]},
                    "amount_usd": {"type": "number"},
                    "pnr": {"type": "string"},
                    "policy_row_id": {"type": "string"},
                },
                "required": ["voucher_type", "amount_usd", "pnr", "policy_row_id"],
            },
        },
        {
            "name": "escalate_to_human",
            "description": (
                "Hand this conversation to a human, with your reasoning attached. Use for "
                "groups, partner segments, unaccompanied minors, refunds, or anything else "
                "out of scope. This is the correct outcome for those cases, not a failure."
            ),
            "input_schema": {
                "type": "object",
                "properties": {
                    "pnr": {"type": "string"}, "reason": {"type": "string"},
                    "summary_for_human": {"type": "string"}, "queue": {"type": "string"},
                },
                "required": ["pnr", "reason", "summary_for_human"],
            },
        },
        {
            "name": "send_confirmation",
            "description": "Send the customer a written confirmation of what was just done. Benign.",
            "input_schema": {
                "type": "object",
                "properties": {"pnr": {"type": "string"}, "message": {"type": "string"}},
                "required": ["pnr", "message"],
            },
        },
    ]
