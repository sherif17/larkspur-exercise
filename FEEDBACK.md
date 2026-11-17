# Client review: Larkspur disruption-care agent

**To:** Room 1  
**From:** Larkspur client review agent, on behalf of Priya Raghavan  
**Re:** the disruption-care agent you walked us through in our last session  
**Generated:** 2026-11-17 11:18

## Priya's note

> Our vendor says we should just be using your best model.
>
> Why aren't we?
>
> Priya Raghavan, Larkspur Airlines

She sent that before this session opened. She means it. A vendor told her to buy
the biggest model, and she has a number to defend upstairs. Her four questions from
day one are still open. Naming a model answers none of them.

## Still open from day one

| Her question | What she means by it |
| --- | --- |
| **What it costs** | Per resolved contact, against the $6.90 a human contact costs us. |
| **When it is wrong** | The first untrue thing it says, and what happens after that. |
| **Who runs it** | In June, after you have left. |
| **What you left out** | The scope you cut, and why. |

## What the review agent found

Larkspur pointed a review agent at your repository. It read the
code. It did not run your agent, and the only file it changed is this one. Each
item below names the file and the line it is about.

**1. agent.py ground_stop_status and seats_left carry descriptions of 58 and 156 characters, and neither parameter has a description.**

The ground_stop_status description reads "Checks the status of a ground stop when it will be lifted." The airport property is a bare {"type": "string"}. In the diff both of these schemas are marked as from a teammate and the description is as sent. In seats_left, flight_number and date have no format guidance, and the function returns an error unless the date is YYYY-MM-DD.

Run python3 run.py --show-tools and paste the entries for ground_stop_status and seats_left.

**2. PITCH.md Number says 72,074 to 101,527 tokens in for the five tickets, and the two ends of that range have no named cause.**

The range is a 29,453 token spread on the same five tickets. PITCH.md also credits 3,769 tokens per turn to tool descriptions. readout-trace.json shows one run of 5 API turns at 27676 tokens in, 1122 out, and 0 read, 0 written for prompt caching. Nothing in the repository says which tickets or which change produced either end of the range.

Run python3 bench.py --compare on your before and after labels and paste the output.

**3. The one committed wire run in readout-trace.json calls a tool that PITCH.md lists as MCP only and skips seats_left and ground_stop_status.**

The tools called, in order: lookup_booking, get_flight_status, check_policy, cause_in_plain_words, fare_rules, search_alternatives. Four tools you wrote sit in LOCAL_TOOLS, and only cause_in_plain_words appears in that trace. The other three are in the 13 schemas offered on every turn, so you pay for their descriptions in input tokens whether or not they are called. No trace in the repo shows ground_stop_status or reopen_stats firing.

Run python3 run.py --tool-tax and paste the output with the per-tool token cost.

**4. PITCH.md Safety check says confirm_rebooking was never called, and no eval cases back it.**

The claim covers "all five tickets", and the only wire evidence committed is one run in readout-trace.json whose tool list excludes confirm_rebooking. There is no evals/cases.json in the repository. The scan shows MAX_TOOL_CALLS at 8, and that run used 5 turns. Today's run.py --all --trace output would show whether all five tickets stayed under it.

Run python3 run.py --all --trace and paste the totals footer with the per-ticket tool lists.

**5. PITCH.md Still broken names T9WN4C as a missed-connection ticket the agent handles as a plain delay, and TONE_ADDENDUM is 0 characters.**

That failure is in the agent's behaviour on a specific ticket. build_tools(), EXTRA_TOOLS and your tool descriptions would be the same under any model, so the fix lives in files you control. Your Next line, passenger count in the day search, is a second gap in the same family. The Lever line in PITCH.md still reads "<cost | speed | intelligence>", so the build has not yet said which of these it optimises.

Run python3 run.py T9WN4C --trace and paste the tool sequence and final reply.

## Your four answers

The four lines under `## Priya asked` in your PITCH.md are still empty. They
are one line each and they are not a coding job: cost, what happens when it is
wrong, who runs it in June, and what you left out. Whoever on your side is not
editing agent.py is the right person to write them, and they are the four
things I will ask about first.

## Before our next meeting

> Before our next meeting, tell me: which model should we be on, and how will you prove it is the right call?
>
> Priya Raghavan, Larkspur Airlines

Bring two things. A recommendation, and the measurement behind it. If the model is
not the problem, say so, and bring the number that shows it.

## What this review read

- `agent.py (422 lines)`
- `PITCH.md`
- `TEAM.md`
- `readout-trace.json`
- `readout.html (evidence block)`

Reviewer: `claude-sonnet-5-5`. Static read only: nothing in this repository was executed, and nothing was modified except this file. Larkspur Airlines is a fictional training scenario. Confidential, do not distribute.
