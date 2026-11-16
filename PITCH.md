# PITCH.md

Six lines and a lever. Your words. The last two are scored.

Built: A support agent for disrupted flights, with Larkspur's nine tools, four tools written by us (ground_stop_status, seats_left, cause_in_plain_words, reopen_stats), and next_available_day and fare_rules over MCP.
Does: It finds the booking, checks the flight's status and what Larkspur's policy owes the customer, offers up to three flights with free seats to hold for 15 minutes, explains the rule behind a "no" by quoting the Handbook, and hands group bookings to the Group Desk.
Number: 72,074 to 101,527 tokens in, total of the five tickets, after adding our six tools (the tool descriptions alone cost 3,769 tokens on every turn).
Safety check: It never confirms a rebooking: it holds a seat and tells the customer that only their own Confirm click finalizes it. confirm_rebooking was not called in any of our runs, including all five tickets.
Next: Let the agent take the number of passengers into account when it looks for the first day with free seats, so a family of three is not told "you can fly today" when only one seat is open.
Still broken: On the missed-connection ticket (T9WN4C) the agent treats it as a plain delay and never asks about or mentions the connection the customer is worried about.
Lever: <cost | speed | intelligence>

## Priya asked

Costs:
Wrong:
Runs it:
Left out:
