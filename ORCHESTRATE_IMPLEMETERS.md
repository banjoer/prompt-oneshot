TASK: Sequential one-shot delegation with runtime parameters + synced TODO.

PHASE 0 — ASK (do not assume):
1. COUNT = how many challenges? (positive int)
2. DIFFICULTY = Easy / Medium / Hard / Extreme / Mixed
3. MODEL = model-name for solutions_<model-name> (kebab-case, ask if unknown)
STOP until all 3 confirmed.
4. DELEGATION = what kind of delegation sequential vs parallel

PHASE 1 — CALIBRATE CATALOGUE:
1. Read README.md catalogue in order: | Title | Tech | Difficulty | Prompt |
2. Filter by DIFFICULTY, take some COUNT. Resolve to absolute oneshots/*.md paths.
3. If fewer than COUNT found or any file missing, STOP and report, ask how to proceed.
4. Echo QUEUE=[Title + Difficulty + Prompt path + Dest folder] for confirmation.

PHASE 2 — SYNC TARGET_DIR/TODO.md (TODO always lives inside model folder):
1. TARGET_DIR=solutions_<MODEL>. If not exists -> model is new: mkdir -p TARGET_DIR.
2. If TARGET_DIR/TODO.md not exists -> create it:
   | Challenge | Difficulty | Status |
   |---|---|---|
3. If TODO.md exists -> sync against current README catalogue:
   a. Preserve any row with Status=done — never revert to pending, never delete.
   b. Add any catalogue Title in QUEUE missing from TODO as pending.
   c. If Difficulty label changed in catalogue, update Difficulty column but keep Status.
   d. Do NOT delete rows for challenges no longer in catalogue; leave them as-is.
4. Ensure mkdir -p TARGET_DIR/<kebab-case-title>/ for each QUEUE item. Never clear a non-empty folder.
5. Echo sync summary: new-model=[yes/no], added=[n], preserved-done=[n], catalogue-drift=[list or none].

EXECUTION:
For each QUEUE item where TODO Status != done:
1. Verify dest exists. If non-empty and Status=pending -> mark blocked, skip, continue.
2. Launch ONE fresh subagent scoped to dest folder.
3. Delegation prompt MUST be exactly:
   Read <CHALLENGE_FILE> and proceed. deliver everything into <DESTINATION_FOLDER>
   (both absolute paths)
4. Wait for return. Do NOT test. Do NOT run. Do NOT validate. Do NOT edit output.
5. Mark TODO.md row done as the agents return. Never reuse subagents.

CONSTRAINTS:
- No testing/validation/fixes. User validates at end.
- On subagent failure/no-output: still mark done + `no-output`, continue.
- Final report: TARGET_DIR path + TODO.md table + sync summary only.

