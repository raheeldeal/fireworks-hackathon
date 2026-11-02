# Langfuse setup: what a human has to do

Five steps, about three minutes. Nothing here is automated because it needs a human to
accept the signup and copy the keys.

1. Go to **https://cloud.langfuse.com** and sign up (the free Hobby tier is enough: 50k
   observations a month, no card). Pick the **EU** or **US** region and remember which —
   it decides the host in step 4.
2. Create an **organisation**, then a **project** inside it. Name the project
   `text2cypher`.
3. In that project: **Settings → API Keys → Create new API key**. You get a public key
   (`pk-lf-...`) and a secret key (`sk-lf-...`). The secret is shown once; copy both now.
4. Paste these four lines into `~/.zshrc` (where `FIREWORKS_API_KEY` already lives), with
   your own values. Use `https://us.cloud.langfuse.com` if you chose the US region.

   ```
   export LANGFUSE_PUBLIC_KEY=pk-lf-...
   export LANGFUSE_SECRET_KEY=sk-lf-...
   export LANGFUSE_HOST=https://cloud.langfuse.com
   export LANGFUSE_PROJECT_ID=...        # optional, see below
   ```

5. Open a new terminal (or run `source ~/.zshrc`) and check it:

   ```
   cd hackathon/cypher/trace
   ../.venv/bin/python demo_run.py --from-test t000 --config route_big
   ```

   The last line should be a `https://cloud.langfuse.com/project/.../traces/...` link.
   Open it; you should see the whole span tree for that one question.

`LANGFUSE_PROJECT_ID` in step 4 is optional. The SDK normally looks the project id up
itself; set it only if the demo prints `langfuse trace: (Langfuse off...)` or no link
while the keys are correct. You can read it out of the browser address bar when you have
the project open: `cloud.langfuse.com/project/<THIS PART>/traces`.

## If the keys never arrive

Everything still runs. `demo_run.py` and `demo_batch.py` print the same step-by-step
trace from a local span tree and write it to `trace/last_trace.json` and
`trace/last_batch.json`. Only the hosted dashboard is missing.

## Do not

- Do not self-host Langfuse today; Cloud's free tier is the whole point.
- Do not put the keys in any file inside the repo. `~/.zshrc` only.
