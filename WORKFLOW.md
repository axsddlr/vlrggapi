# Workflow: one branch, clean history

`master` is the only long-lived branch. It is always deployable: whatever is on
`master` is what runs in production and what the scheduled selector/smoke checks
watch. There is no `dev` branch.

```
master ──●──●──●──●──●──●──●──▶   always deployable, append-only
           \    /   \    /
        short-lived branches, squash-merged
```

Every change follows the same path:

```
branch ──▶ pull request ──▶ CI + CodeQL + dependency review ──▶ squash merge ──▶ delete branch
```

The point of this document is not the merge button. It is **how to keep messy,
experimental, half-finished work from ever touching `master`**, and what to do on
the rare occasion something bad does land.

## Why one branch

A long-lived `dev` plus `master` means every change is integrated twice, monitored
in one place and deployed from another, and the two drift apart forever. For a
single-maintainer API with a stateless deploy, PR previews already give you the
"try it before production" that a `dev` branch pretends to give. One branch also
means the things that watch the code (CI, CodeQL, the selector check, the smoke
test) watch *the same code that is deployed*.

## The loop

```bash
# 1. start from a current trunk
git switch master
git pull --ff-only

# 2. branch off with a name that says what it does
git switch -c fix/stats-region-guard

# 3. work, committing as messily as you like (this branch is scratch space)
git commit -m "wip"
git commit -m "actually fix it"

# 4. before you push, put it on top of the latest trunk
git fetch origin
git rebase origin/master

# 5. prove it locally
uv sync
uv run pytest -q
uv run ruff check .
uv run pip-audit

# 6. push and open a PR
git push -u origin HEAD
gh pr create --base master --fill
```

Then squash-merge the PR and delete the branch. `master` ends up with **one
commit per change**, no "wip", no "fix typo", no merge bubbles.

Useful git defaults for this model:

```bash
git config --global pull.ff only          # never accidentally create a merge commit
git config --global push.default current  # push the branch you're on
git config --global rebase.autoStash true # keep local edits across a rebase
```

## Keeping the trunk clean

The rule that makes this work: **your branch is disposable, `master` is not.**

| Stage | What it looks like | Allowed operations |
|---|---|---|
| Working copy / local commits | anything, including `wip` | amend, rebase, reset, reorder |
| Pushed to your own PR branch | reasonably shaped, CI green | amend + `--force-with-lease` |
| Merged into `master` | one squashed commit | **revert only** — never rewrite |

### 1. Never push unfinished work to `master`

Not even "just to run CI". If you need CI feedback on something half-done, push
the branch and open a **draft PR** — CI runs identically, and nothing is
mergeable until you mark it ready.

```bash
gh pr create --base master --draft --fill
```

### 2. Treat the branch as scratch space, the PR as the deliverable

Commit early and often locally; nobody sees it. The reviewable unit is the PR
diff, and the merge is a single squashed commit. You are not punished for a messy
branch — you are only punished for a messy *diff*.

### 3. Rebase before you push, not after

```bash
git fetch origin
git rebase origin/master      # replay your work on today's trunk
```

Conflicts are cheapest to solve here, in your branch, on your machine. If a
rebase goes sideways:

```bash
git rebase --abort            # back to where you were, nothing lost
```

### 4. Rewrite your own branch freely — with a lease

Once a branch is pushed, rewriting it needs a force-push, but only ever your
branch:

```bash
git commit --amend                    # fix the last commit (message or content)
git push --force-with-lease           # refuses if someone else pushed meanwhile
```

`--force-with-lease` is the difference between "I replaced my branch" and "I
deleted someone's commits". Never use plain `--force`, and never use either on
`master`.

### 5. Squash away the noise

If your branch has ten commits and you want one:

```bash
git reset --soft "$(git merge-base master HEAD)"
git commit    # write the one message you want on the trunk
```

Or let GitHub do it: the PR is merged with **Squash and merge**, and the branch's
commit history never reaches `master` at all.

### 6. Keep PRs small

One logical change per PR. This is not aesthetics: **the revert radius is the
PR**. A 30-line PR that breaks something is a one-line `git revert`. A 900-line
PR that mixes a refactor with a behaviour change is an afternoon of untangling.

### 7. Gate it with CI, not discipline

Discipline fails at 2am. The branch protection on `master` requires a pull
request and green checks (`Test Python 3.11`–`3.14`, CodeQL, dependency review),
and forbids force-pushes and deletion. If CI is red, the button is unavailable —
no "I'll fix it after merge".

### 8. If a change must land but must not be live

That is what a flag/env var is for, not a long-lived branch. Ship the code gated
off, then turn it on deliberately. A branch that lives for two weeks is a merge
conflict with a countdown.

## When something bad does land

**Default answer: revert forward.** `master` is append-only, so "undo" means a
new commit that reverses an old one — not a rewritten history. Rewriting the
trunk means force-pushing it, invalidating everyone's clones and any open PRs,
and it is almost never worth it.

### Decision table

| Situation | Do this |
|---|---|
| Bad commit, not pushed anywhere yet | amend / rebase / reset locally, freely |
| Bad commit, pushed to *your* branch | fix it, `git push --force-with-lease` |
| Bad commit already merged to `master` | `git revert <sha>` → PR → merge |
| Bad merge commit on `master` | `git revert -m 1 <merge-sha>` |
| Release is live and broken | roll back the deploy (Vercel → Instant Rollback / previous image), *then* revert forward on `master` |
| Secret committed | **rotate the secret first**, then decide; history rewriting is a separate, coordinated incident |
| Only the deploy is broken, code is fine | roll back the deployment; no code change needed |

### Recipes

Revert a single bad commit (creates a new commit, safe on `master`):

```bash
git switch -c revert/bad-change
git revert --no-edit <sha>
git push -u origin HEAD
gh pr create --base master --fill
```

Revert a whole merge (undoes everything the branch brought in):

```bash
git revert -m 1 --no-edit <merge-sha>
```

> `-m 1` says "keep the trunk side". If you later want to re-merge that branch,
> git still considers it merged — you must revert the revert first:
> `git revert <revert-sha>`, then merge again.

Undo a commit that is only local (never pushed):

```bash
git reset --hard HEAD~1     # discards it entirely
git reset --soft HEAD~1     # keeps the changes staged
```

Move a commit you accidentally made on `master` (not pushed):

```bash
git switch -c fix/moved-off-master   # carries the commit with you
git switch master
git reset --hard origin/master       # master back to the deployed state
```

Recover a branch you deleted (local or remote), if you know roughly when:

```bash
git reflog                    # find the sha
git switch -c recovered <sha>
```

Drop local junk without touching commits:

```bash
git stash push -m "wip before rebase"
git stash pop
```

### Hotfixes

There is no hotfix branch to invent: branch from `master`, keep it tiny, get CI
green, squash-merge. That *is* the hotfix path, and because there is no `dev`,
there is no "merge it back to dev too" step to forget.

## What is automated

| Thing | Trigger | Guards |
|---|---|---|
| `ci.yml` | push / PR to `master` | tests on 3.11–3.14, ruff, `pip-audit`, Docker smoke on PRs, `:latest` image on release |
| `codeql.yml` | push / PR to `master`, weekly | static analysis |
| `dependency-review.yml` | PR to `master` | blocks PRs that add vulnerable deps |
| `selector-check.yml` | daily + manual | vlr.gg markup still matches our selectors |
| `smoke.yml` | weekly + manual | the deployed API answers correctly |
| dependabot | weekly | opens PRs against `master` |

All of them point at the same branch, which is the deployed branch. That is the
whole argument for one branch in one sentence.

## FAQ

**"I want to test something in CI before it's clean."**
Push the branch, open a draft PR. CI runs on it; it just cannot merge.

**"I already pushed ugly commits to my branch."**
Squash-merge hides them: `master` gets one commit. Rewrite the branch first only
if the diff is hard to review.

**"Can I just push this one-liner straight to `master`?"**
Branch protection says no, and that is a feature. A PR for a one-liner costs ~20
seconds and keeps the history and the audit trail uniform.

**"The trunk is broken right now."**
Revert the offending commit (or roll back the deploy) first, then fix forward
with a normal PR. Restoring `master` to green beats diagnosing in place.

**"Do I still need `dev` for a staging environment?"**
Only if you have a real staging environment with different data or state. A PR
preview deploy is not that; it is a per-change preview, and it is better because
it is thrown away with the PR.
