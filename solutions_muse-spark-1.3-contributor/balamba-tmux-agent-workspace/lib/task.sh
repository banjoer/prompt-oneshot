# balamba task helpers: new task, close task, terminals (state mutations).
# State JSON is the source of truth; tmux backend windows are created alongside.
# Sign-off: produced 2026-11-25 by Muse Spark 1.3 Contributor (opencode-go).
set -u

task_new_id() {
  python3 -c 'import secrets; print("t-" + secrets.token_hex(4))'
}

task_new_session_id() {
  python3 -c 'import uuid; print("ses_" + uuid.uuid4().hex)'
}

task_unique_slug() {
  # $1=repo $2=wanted-slug $3=parent-dir : echoes unique slug (suffix -2,-3..)
  local repo="$1" want="$2" parent="$3" cand="$2" i=2
  while [ -e "$parent/$cand" ] || git -C "$repo" show-ref --verify --quiet "refs/heads/$cand" 2>/dev/null; do
    cand="${want}-${i}"
    i=$((i + 1))
  done
  echo "$cand"
}

task_worktree_path() {
  # $1=project-path $2=slug -> sibling balamba_worktrees/<folder>/<slug>
  local proj="$1" slug="$2"
  local parent base folder
  parent="$(dirname "$proj")"
  folder="$(basename "$proj")"
  echo "$parent/balamba_worktrees/$folder/$slug"
}

task_agent_command() {
  # $1=agent $2=session $3=dir -> expanded command
  local agent="$1" session="$2" dir="$3" tmpl var
  var="BALAMBA_AGENT_${agent}_COMMAND"
  tmpl="${!var:-opencode --session {{session}}}"
  tmpl="${tmpl//\{\{session\}\}/$session}"
  tmpl="${tmpl//\{\{dir\}\}/$dir}"
  echo "$tmpl"
}

task_add_state() {
  # Append task JSON via python. Args: $1=project-path $2=task-json-file
  local proj="$1" jf="$2"
  STATE_FILE="$BALAMBA_STATE_FILE" PROJ="$proj" JF="$jf" python3 <<'EOF'
import json, os
sf = os.environ["STATE_FILE"]; proj = os.environ["PROJ"]
with open(os.environ["JF"]) as f: task = json.load(f)
with open(sf) as f: st = json.load(f)
for p in st.get("projects", []):
    if p["path"] == proj:
        p.setdefault("tasks", []).append(task)
        break
with open(sf, "w") as f: json.dump(st, f, indent=2)
EOF
}

task_remove_state() {
  # $1=project-path $2=slug
  STATE_FILE="$BALAMBA_STATE_FILE" PROJ="$1" SLUG="$2" python3 <<'EOF'
import json, os
sf = os.environ["STATE_FILE"]
with open(sf) as f: st = json.load(f)
for p in st.get("projects", []):
    if p["path"] == os.environ["PROJ"]:
        p["tasks"] = [t for t in p.get("tasks", []) if t.get("slug") != os.environ["SLUG"]]
with open(sf, "w") as f: json.dump(st, f, indent=2)
EOF
}
