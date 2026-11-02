# Plain-English Primer for Fireworks: Deploy

Read top to bottom once. Each concept has: what it is, an analogy, why it matters tomorrow, and one sentence you can say out loud.

---

## Part 1: The words in the challenge brief

### Model
A model is a big file of numbers that turns text in into text out. You never edit the numbers by hand. You either pick a different model, change what you send it (the prompt), or train it on examples.

**Analogy:** a very well-read temp worker who has never seen your company.

**Say:** "Which model are we starting from?"

### Open model
A model whose numbers are published (Llama, Qwen, DeepSeek, Mistral). Fireworks hosts them so you can call them over the internet without owning GPUs. Closed models (GPT, Claude) are off-limits tomorrow.

### Inference
Fancy word for "running the model." Every time you send text and get text back, that is one inference. You pay per token (roughly, per word) in and out.

**Say:** "What does one inference cost us at this model size?"

### Baseline
The result you get before changing anything: the off-the-shelf model with a plain prompt, scored on your test set. Everything you do tomorrow is "better than baseline by X."

**Analogy:** weighing yourself before the diet.

**Why it matters:** no baseline, no story. The brief literally says "against your baseline." Teams that skip this have nothing to show at 4:30.

**Say:** "Let's get the baseline number before we touch anything."

### Eval set (evaluation set)
A list of inputs with known correct answers. You run the model on every input, compare to the correct answer, and get a score (e.g., 73% right). 100 to 300 examples is plenty for a hackathon.

**Analogy:** an exam with an answer key.

**The three rules:**
1. Every example needs an answer you can check automatically. "Is this ticket about billing?" yes. "Is this poem good?" no.
2. Split it: train on some examples, test on others, never both. Testing on training examples is cheating and judges know it.
3. Make it look like reality. If real inputs are messy and short, so should yours be.

**Say:** "How do we score this automatically? If we can't, the task is wrong."

### Quality vs. efficiency, accuracy vs. latency, pass rate vs. cost
These are the tradeoffs the brief asks you to measure.
- **Quality / accuracy / pass rate:** how often the model is right.
- **Latency:** how long one answer takes (measured in seconds; p50 = the typical one, p95 = the slow ones).
- **Cost:** dollars per 1,000 requests.

Big models are more accurate but slower and pricier. The winning move is usually "we got a small cheap model to match the big one on OUR task."

**Say:** "What's our accuracy, p50 latency, and cost per 1k requests, baseline vs. ours?"

### Business value
Translate the table into money or minutes. "73% to 91% accuracy means 180 fewer misrouted tickets per 1,000, at 1/8 the cost of the big model." Judges remember that sentence, not the table.

---

## Part 2: The three ways to "make your own frontier"

### 1. Supervised fine-tuning (SFT)
You give the model a few hundred examples of input → ideal output. It adjusts its numbers to imitate them. On Fireworks this is an upload plus a button; the job takes 20 to 60 minutes.

**Analogy:** handing the temp worker a stack of 300 solved tickets and saying "do it like this."

**When to use it:** your task has a consistent style or format (always output JSON, always pick from these 5 labels) and a small model is almost but not quite good enough.

**Risk tomorrow:** you need clean training data by 12:00 or the job won't finish in time to evaluate. Start it before lunch.

### 2. Reinforcement fine-tuning (RFT)
Instead of showing ideal answers, you write a scoring function (a "reward"). The model tries answers, gets scored, and learns to score higher. Fireworks has an open-source library called Eval Protocol for writing these scorers.

**Analogy:** instead of showing solved tickets, you grade the temp's attempts and they learn from the grades.

**When to use it:** when there is no single right answer but you can tell good from bad. Powerful but slower and fiddlier. Probably not a 6-hour bet unless a teammate has done it.

### 3. Build a smarter harness
Don't train anything. Change what surrounds the model: better prompts, examples in the prompt, letting it use tools, retrying on bad outputs, routing easy inputs to a cheap model and hard ones to an expensive model.

**Analogy:** same temp worker, but you give them a checklist, a calculator, and a manager who double-checks.

**When to use it:** always try this first. It takes an hour, not a training job, and often gets you most of the way. Routing in particular produces great cost-vs-quality charts.

**Say:** "Before we train, what's the best we can do with prompting and routing?"

---

## Part 3: The six concepts from your list

### 3.1 ReAct agent pattern
ReAct = Reason + Act. The model is run in a loop: think about what to do → do one action (call a tool, search, run code) → look at the result → think again → repeat until done. Nearly every "AI agent" you've heard of is this loop.

**Analogy:** a detective. Think, check one clue, update your theory, check the next clue.

**Why it matters tomorrow:** if your task needs the model to look something up or take steps, you'll build this loop. Also, "harness" (below) is mostly about controlling this loop.

**Say:** "Is this a single-shot task or does the model need to take steps?"

### 3.2 What makes a good harness (and Pi)
The harness is all the code around the model: the system prompt, which tools it can use, how many loop turns it gets, how its output is checked, what happens on failure. The model is the engine; the harness is the car.

A good harness is:
- **Small and legible.** You can read the whole loop in one screen.
- **Observable.** Every model call and tool result is logged so you can see why it failed.
- **Bounded.** Max turns, max cost, timeouts. Agents left unbounded wander.
- **Validated.** Model outputs are checked against a schema before being trusted.

Pi (a minimal open-source coding agent by Mario Zechner) is cited as a good example because the whole harness is a few hundred readable lines. Worth skimming the README for 10 minutes, not studying.

**Say:** "Let's keep the harness small enough to read and log every call."

### 3.3 Model tradeoffs: price, capability, family, size, modality
- **Size** (8B, 70B, 400B parameters): bigger = smarter, slower, pricier. For a narrow task, 8B fine-tuned often beats 70B raw.
- **Family** (Llama, Qwen, DeepSeek, Mistral): different training, different strengths. Qwen tends to be strong on code and structured output; Llama is the safe default; DeepSeek for reasoning.
- **Capability:** does it follow instructions? output valid JSON? reason step by step? Test this on your actual data, not benchmarks.
- **Modality:** text only vs. text + images vs. audio. Tomorrow, stick to text.
- **Price:** roughly $0.10 to $0.20 per million tokens for small models, $0.90 or more for 70B class. A 10x cost difference is normal.

**Say:** "Let's run the same 50 examples through a small and a big model and look at the gap before we decide anything."

### 3.4 Embeddings and vector retrieval
An embedding turns a piece of text into a list of numbers such that similar meanings land near each other. Vector retrieval = "find the stored texts whose numbers are closest to this query." It is how you give a model access to documents it wasn't trained on (RAG).

**Analogy:** a library where books are shelved by meaning instead of alphabet, so "refund" sits next to "chargeback."

**Why it matters tomorrow:** probably doesn't, unless your task needs the model to look up facts in a document set. Know the word; skip the depth.

### 3.5 State machines
A list of allowed states and the allowed moves between them. "Ticket is NEW → can go to TRIAGED → can go to ASSIGNED or CLOSED." Nothing else is permitted.

**Why it matters:** agents are unpredictable; state machines are not. Wrap the agent in one so it can only do the next allowed thing. This is the single best trick for making agent demos reliable.

**Say:** "What are the allowed states, and which one can the model move us to?"

### 3.6 Guardrails around variable behavior
Use boring, deterministic code everywhere you can, and let the model touch only the step that truly needs judgment. Check its output with code (is it valid JSON? is the label one of our 5? is the number in range?). If the check fails, retry or fall back to a default.

**Analogy:** the model writes the draft; a checklist decides if it ships.

**Say:** "Which single step needs the model? Everything else should be plain code."

---

## Part 4: The one sentence version

> Pick a narrow task with an auto-checkable answer. Build 150 test examples. Score an off-the-shelf small model and a big one (baseline). Improve with prompts and routing first, fine-tune if there's time. Report accuracy, latency, and cost per 1k for each, and translate the gap into money.

If you can say that sentence and explain every noun in it, you understand this hackathon better than half the room.
