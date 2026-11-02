#!/usr/bin/env python3
"""Gold-first synthetic data. Sample labels programmatically, then ask glm-5p3 to write a transcript
that contains exactly those commitments and distractors.

    python3 scripts/gen_data.py --n 400 --out data/all.jsonl --workers 8
"""
import argparse, json, os, random, sys, re
from concurrent.futures import ThreadPoolExecutor, as_completed
sys.path.insert(0, os.path.dirname(__file__))
import fw

GEN_MODEL = "accounts/fireworks/models/glm-5p3"

CAST = ["Priya", "Marcus", "Elena", "Tom", "Aisha", "Daniel", "Mei", "Jonas", "Sofia", "Raj",
        "Hannah", "Omar", "Lucas", "Fatima", "Noah", "Grace", "Kenji", "Olivia", "Diego", "Nadia",
        "Sam", "Chloe", "Victor", "Leila"]

DOMAINS = {
    "product": ["the onboarding flow", "the pricing page", "the mobile checkout", "the Q3 roadmap", "the beta waitlist",
                "the notifications redesign", "the free-tier limits", "the admin dashboard"],
    "engineering": ["the payments service", "the staging environment", "the search index", "the auth migration",
                    "the flaky integration tests", "the API rate limiter", "the data pipeline", "the iOS crash on login"],
    "marketing": ["the launch blog post", "the webinar deck", "the partner newsletter", "the case study with Northwind",
                  "the conference booth", "the paid search campaign", "the brand refresh", "the customer survey"],
    "ops": ["the vendor contract renewal", "the office move", "the quarterly budget", "the hiring plan for support",
            "the new expense policy", "the security audit findings", "the SOC 2 evidence", "the offsite agenda"],
    "sales": ["the Acme renewal", "the enterprise pricing tiers", "the pipeline review", "the demo script",
              "the Globex proposal", "the churned accounts list", "the CRM cleanup", "the partner referral program"],
}
VERBS = ["draft", "send", "review", "finalize", "update", "schedule", "write up", "circulate", "fix", "test",
         "prepare", "share", "set up", "follow up on", "document", "ship", "benchmark", "clean up", "audit", "summarize"]
OBJECT_TEMPLATES = [
    "{v} the spec for {t}", "{v} the summary of {t}", "{v} the timeline for {t}", "{v} the budget estimate for {t}",
    "{v} the risks list for {t}", "{v} the Slack announcement about {t}", "{v} the one-pager on {t}",
    "{v} the test plan for {t}", "{v} the stakeholder update on {t}", "{v} the metrics dashboard for {t}",
    "{v} the kickoff meeting for {t}", "{v} the FAQ for {t}", "{v} the rollout checklist for {t}",
    "{v} the competitor comparison for {t}", "{v} the customer interviews for {t}",
]
PLAIN_TASKS = [  # tasks that do not need a topic
    "book the conference room for the all-hands", "send the calendar invite for the retro",
    "ping legal about the DPA template", "post the hiring update in #general", "renew the Figma seats",
    "order the new laptops for the interns", "reply to the Zendesk escalation from Contoso",
    "upload the recording to the shared drive", "add the new hires to the on-call rotation",
    "cancel the unused Datadog hosts", "rotate the production API keys", "file the expense report for the offsite",
]
DUES = ["Friday", "Monday", "Tuesday", "Wednesday", "Thursday", "end of day tomorrow", "end of the week", "end of month",
        "next Monday", "next Tuesday", "next Wednesday", "next Friday", "the 15th", "the end of the quarter", "tomorrow morning",
        "Thursday's standup", "the next sync", "noon tomorrow", "March 12", "April 3", "June 30", "October 20", "the 28th",
        "two weeks from now", "before the launch on the 9th"]
DISTRACTOR_TEMPLATES = [
    ("deferred", "The group discusses {thing} but explicitly decides to park it until next quarter; nobody takes it on."),
    ("rejected", "{who} suggests {thing}; the others push back and the idea is dropped with no owner."),
    ("done", "{who} reports that {thing} was already finished last week (past work, not a new action)."),
    ("open_question", "Someone asks whether {thing} is still needed; the question is left unanswered, no one is assigned."),
    ("vague", "{who} says 'we should probably look at {thing} at some point' and the conversation moves on, no commitment."),
    ("maybe_later", "{who} offers to help with {thing} 'if there is time', and the group says let's revisit later; not assigned."),
]


def sample_items(rng):
    participants = rng.sample(CAST, rng.choice([4, 5]))
    domain = rng.choice(list(DOMAINS))
    topics = rng.sample(DOMAINS[domain], 4)
    n_items = rng.choice([2, 3, 3, 4, 4, 5])
    n_dis = rng.choice([1, 2, 2, 3])
    items, used_tasks = [], set()
    for i in range(n_items):
        owner = rng.choice(participants)
        if rng.random() < 0.2:
            task = rng.choice([t for t in PLAIN_TASKS if t not in used_tasks])
        else:
            task = rng.choice(OBJECT_TEMPLATES).format(v=rng.choice(VERBS), t=topics[i % 4])
        used_tasks.add(task)
        due = rng.choice(DUES) if rng.random() < 0.65 else None
        items.append({"owner": owner, "task": task, "due": due})
    distractors = []
    for j in range(n_dis):
        kind, tmpl = rng.choice(DISTRACTOR_TEMPLATES)
        thing = rng.choice(OBJECT_TEMPLATES).format(v=rng.choice(VERBS), t=rng.choice(DOMAINS[domain]))
        thing = re.sub(r"^(\w+ ?\w*) the", lambda m: m.group(1) + "ing the" if not m.group(1).endswith("e") else m.group(1)[:-1] + "ing the", thing, count=1)
        distractors.append({"kind": kind, "text": tmpl.format(who=rng.choice(participants), thing=thing)})
    return participants, domain, items, distractors


def build_prompt(participants, domain, items, distractors):
    lines = []
    for it in items:
        due = f"due: say the deadline using exactly these words: \"{it['due']}\"" if it["due"] else "due: NO deadline is mentioned for this item"
        lines.append(f"- {it['owner']} commits to: {it['task']} ({due})")
    dis = "\n".join(f"- {d['text']}" for d in distractors)
    return f"""Write a realistic transcript of a {domain} team meeting.

Speakers (use exactly these names, each must speak at least twice): {', '.join(participants)}.
Format: one line per utterance, "Name: what they said". No stage directions, no headings, no summary at the end.
Length: 300 to 450 words.

The transcript must contain EXACTLY these {len(items)} commitments, and no others. For each, the named person must clearly take ownership (volunteering, or being asked and agreeing). Phrase them naturally, do not copy the wording verbatim, but keep the meaning and the owner unambiguous:
{chr(10).join(lines)}

The transcript must ALSO contain these {len(distractors)} discussion points that are NOT action items. Write them so that no one commits to doing them:
{dis}

Rules: no one else agrees to do anything. Do not add deadlines that are not listed above. Mix the commitments and the distractors into natural back-and-forth with small talk, questions, and disagreement. Output only the transcript."""


def generate_one(idx, seed):
    rng = random.Random(seed * 1000 + idx)
    participants, domain, items, distractors = sample_items(rng)
    prompt = build_prompt(participants, domain, items, distractors)
    content, lat, tin, tout, _ = fw.chat(GEN_MODEL, [{"role": "user", "content": prompt}], max_tokens=1000,
                                         extra={"reasoning_effort": "low"}, tag="gen")
    text = content.strip()
    return {"id": f"ma-{idx:04d}", "domain": domain, "participants": participants, "text": text,
            "items": items, "distractors": distractors, "n_words": len(text.split()), "gen_prompt_tokens": tin, "gen_out_tokens": tout}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=400)
    ap.add_argument("--start", type=int, default=0)
    ap.add_argument("--seed", type=int, default=2026)
    ap.add_argument("--out", default="data/all.jsonl")
    ap.add_argument("--workers", type=int, default=8)
    args = ap.parse_args()
    done = set()
    if os.path.exists(args.out):
        done = {json.loads(l)["id"] for l in open(args.out) if l.strip()}
    todo = [i for i in range(args.start, args.start + args.n) if f"ma-{i:04d}" not in done]
    print(f"{len(done)} already done, {len(todo)} to generate")
    with ThreadPoolExecutor(args.workers) as ex, open(args.out, "a") as f:
        futs = {ex.submit(generate_one, i, args.seed): i for i in todo}
        for n, fut in enumerate(as_completed(futs), 1):
            try:
                row = fut.result()
            except fw.CapReached as e:
                print("CAP:", e); break
            except Exception as e:
                print("ERR", futs[fut], e); continue
            f.write(json.dumps(row) + "\n"); f.flush()
            if n % 20 == 0 or n == len(todo):
                print(f"{n}/{len(todo)} words={row['n_words']} spend=${fw.ledger_total():.3f}")


if __name__ == "__main__":
    main()
