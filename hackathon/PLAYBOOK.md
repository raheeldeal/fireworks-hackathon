# Day-of Playbook: Fireworks Deploy, Nov 2

## 0. Tonight's checklist
- [ ] Fireworks account, API key created, `export FIREWORKS_API_KEY=...` works (`python3 eval/run_eval.py --model accounts/fireworks/models/llama-v3p1-8b-instruct --prompt eval/prompts/v1_plain.txt --limit 5` returns real answers)
- [ ] Registration approved on Luma
- [ ] This folder pushed to a GitHub repo you can share by link
- [ ] Laptop charged, charger packed, phone hotspot works
- [ ] Two task ideas written on the card below
- [ ] Read PRIMER.md once more; be able to say Part 4 from memory

## 1. Team formation (9:00 to 10:00)

### Your 20-second intro
> "I'm Raheel, product manager. I've got an eval harness ready to go: drop in a JSONL dataset, it scores any Fireworks model and prints the baseline vs. tuned table with accuracy, latency, and cost. I'll own task definition, the eval set, and the pitch so you can stay heads-down on the model. I've got two task ideas with data, or I'm happy to run yours."

### What to look for
Ask: "Have you fine-tuned a model or built an eval before?" You want:
- One person who has used the Fireworks SDK or any fine-tuning API (they run the SFT job).
- One person comfortable in Python (they wire data in, write scoring).
- Team of 3, maybe 4. Not 5.

### Red flags
- Everyone wants to build the demo UI. Nobody wants to own data.
- An idea that can't be scored automatically ("an agent that writes better emails").
- An idea that needs data nobody in the group has.

### Task idea card (fill in tonight)
| | Idea A | Idea B |
|---|---|---|
| Task in one line | | |
| Input → output | | |
| How we score automatically | | |
| Data source (public / synthetic / own) | | |
| Business value sentence | | |

Good shapes: classify, extract to JSON, route, generate SQL, summarize to a fixed template. Anything where the right answer is checkable.

## 2. Working with engineers (the part you haven't done before)

Your job is to protect three things: the baseline, the honesty of the eval, and the clock. Here is what that sounds like.

**At kickoff (10:30):**
- "Let's lock the task in 20 minutes. What is the input, what is the output, how do we score?"
- Propose the split: "A, can you get the baseline running on 50 examples? B, can you start building the training set? I'll build the test set and the results table."

**Every 60 minutes, a 2-minute standup:**
- "What's the current best number? What's blocking?"
- If no baseline by 12:00: "Let's cut the task in half. What's the smallest version we can score?"

**When someone wants to add scope:**
- "Does that move the number on the table? If not, after 3:30."

**When someone says a change helped:**
- "By how many examples? Did we test on examples we trained on?"

**Things engineers appreciate from a PM:**
- You write the pitch and slides while they build; they never have to.
- You keep the results table current so they can see progress.
- You handle the submission form, timing, and mentor conversations.
- You don't ask "how's it going" more than once an hour.

**Things that annoy them:**
- Changing the task after 11:30.
- Asking for a demo UI before the number is good.
- Vague feedback ("can it be smarter?") instead of examples ("here are the 6 tickets it got wrong").

## 3. Hour by hour

| Time | Goal | You |
|---|---|---|
| 10:30 | Task locked, roles split | Run the 20-minute lock meeting |
| 11:30 | Baseline number exists | Have the results table showing row 1 |
| 12:00 | Training data ready, SFT job started (if training) | Check data has no test examples in it |
| 12:30 | Lunch | Talk to a mentor about your task; ask "what would make judges care?" |
| 13:30 | First intervention scored (prompt / routing) | Update table, note the misses |
| 14:30 | Second intervention scored (fine-tune or routing) | Update table; start the slides |
| 15:30 | Freeze the model. No more changes. | Write the pitch; rehearse once |
| 16:00 | Submit | Never 4:29 |
| 16:00 to 16:30 | Demo rehearsal x2 | Time it. 3 minutes max. |

## 4. Pitch template (3 minutes)

1. **Problem and who pays (20s):** "Support teams misroute X% of tickets; each one costs Y minutes."
2. **Task and eval (20s):** "We built a 200-ticket test set with labels and score accuracy automatically."
3. **Baseline (20s):** "Off-the-shelf 8B model: 73%. 70B model: 90% but 7x the cost and 3x the latency."
4. **What we changed (40s):** one slide, one diagram. "Rubric prompt, then fine-tuned the 8B on 300 examples."
5. **Result (40s):** the table. "8B fine-tuned: 94%, same cost as baseline, 3x faster than 70B."
6. **Business value (20s):** "At 10k tickets/day that's 2,100 fewer misroutes and $X saved vs. the big model."
7. **How far we pushed it (20s):** the tradeoff curve or the ablation. "Prompt alone got +5; fine-tune got +16."

Slides: 1 title, 1 table, 1 diagram, 1 business value. That's it.

## 5. Submission checklist
- [ ] Repo link with README that shows the table
- [ ] Deployed model id on Fireworks (the brief says "deploy")
- [ ] Eval set and scoring script in the repo
- [ ] Baseline vs. tuned numbers for accuracy, latency, cost
- [ ] One paragraph of business value
- [ ] Demo video or live demo plan (live is riskier; have a recording)
