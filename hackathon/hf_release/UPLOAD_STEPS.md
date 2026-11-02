# Publishing on Hugging Face (website only, about 10 minutes)

You need: a browser, this `hf_release` folder on your computer, and an email address.

Two decisions to make before you start:

- **Owner:** your personal account, or an organization (team page). An org looks better for a team submission. Pick its short name now, e.g. `your-team-name`.
- **Visibility:** **Public** if the dataset should be judged or cited. You can start Private and flip it later, but a private dataset cannot be opened by judges.

## 1. Create an account (skip if you have one)

1. Go to https://huggingface.co/join
2. Enter email and password, click **Next**, fill in username and full name, accept the terms, click **Create Account**.
3. Open the confirmation email and click the link. Uploads are blocked until the email is confirmed.

## 2. (Optional) Create an organization

1. Click your avatar (top right) > **New Organization**.
2. **Organization Username:** short, lowercase, no spaces (this appears in the URL).
3. **Organization Full name:** your team name.
4. Plan: **Free**. Click **Create Organization**.

## 3. Create the dataset repository

1. Click your avatar > **New Dataset** (or go to https://huggingface.co/new-dataset).
2. **Owner:** pick your account or the org.
3. **Dataset name:** `text2cypher-executed-200`
4. **License:** choose **apache-2.0**. (It is also set in `README.md`; the two should match.)
5. **Visibility:** Public or Private (see above).
6. Click **Create dataset**.

## 4. Upload the files

1. On the new dataset page, click the **Files and versions** tab.
2. Click **Add file** (top right of the file list) > **Upload files**.
3. Open the `hf_release` folder in Finder. Select **everything inside it** (`README.md`, `UPLOAD_STEPS.md`, the `data` folder, the `scorer` folder) and drag it onto the upload box. Drag the *contents*, not the `hf_release` folder itself, so `README.md` lands at the top level. Folders keep their structure.
4. Check the list shows these 13 files:
   - `README.md`, `UPLOAD_STEPS.md`
   - `data/test.jsonl`, `data/train.jsonl`, `data/test.parquet`, `data/train.parquet`, `data/test_annotations.jsonl`, `data/test_annotations.parquet`
   - `scorer/README.md`, `scorer/score.py`, `scorer/test_score.py`, `scorer/executor.py`
   (If Finder shows a hidden `.DS_Store`, remove it from the list or ignore it.)
5. **Commit message** box, paste:

   ```
   Initial release: 200 execution-verified test rows, 500 train rows, annotations, scorer
   ```

6. Leave "Commit directly to the main branch" selected. Click **Commit changes to main**.

## 5. Check it worked

1. Click the **Dataset card** tab. You should see the title "Text2Cypher Executed 200", tags on the right (license apache-2.0, English, text2cypher), and the tables render.
2. Scroll to the **Dataset Viewer** at the top of the card. Within a few minutes it should show:
   - a subset dropdown with **default** and **test_annotations**
   - under **default**, splits **test (200 rows)** and **train (500 rows)**
   - `gold_result` shows as text (a JSON string), which is expected.
3. If the viewer says it is still processing, wait 2-5 minutes and refresh. If it shows an error, open the error text; the usual cause is `README.md` not being at the top level (redo step 4 dragging the folder *contents*).
4. Integrity check: open **Files and versions** > `data/test.jsonl` and confirm the size is 1.05 MB. The expected sha256 is in the dataset card.

## 6. Share

Copy the page URL, `https://huggingface.co/datasets/<owner>/text2cypher-executed-200`, into the hackathon submission.

To fix something later: open the file in **Files and versions**, click **Edit** (pencil icon) for text files, or upload a replacement with **Add file > Upload files**. Never edit `data/test.jsonl`; its hash is the point.
