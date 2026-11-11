# CLAUDE.md

## GitHub identity: always act as the bot

Agents in this repo act on GitHub as the GitHub App bot `anilhelvaci-agent[bot]`, never as the human owner.
The human makes their own commits by hand, with their own identity and signing key. Keep the two separate.

### Use `./agent-gh.sh` for anything that writes to git or touches GitHub

Prefix these commands with `./agent-gh.sh`:

- Commits and tags: `./agent-gh.sh git commit ...`, `./agent-gh.sh git tag ...`
- Anything that talks to the remote: `./agent-gh.sh git push|fetch|pull ...`
- Every `gh` command: `./agent-gh.sh gh pr create ...`, `./agent-gh.sh gh issue comment ...`, `./agent-gh.sh gh api ...`

Read-only local commands (`git status`, `git diff`, `git log`, `git switch`, `git add`) can run without the wrapper.

The wrapper needs `GH_APP_PRIVATE_KEY_PATH`. If it isn't set, use:

```bash
export GH_APP_PRIVATE_KEY_PATH=~/.config/agent-gh/app.pem
```

### Never

- Run `git commit`, `git push` or `gh` without the wrapper. That acts as the human.
- Change identity or auth settings: no `git config user.*`, no `git config commit.gpgsign`, no `gh auth login`/`logout`, no `git remote set-url`, no SSH or gpg changes. The wrapper sets everything per process.
- Push to `main`. Work on `agent/<topic>` branches and open a PR for human review.
- Commit or print the private key (`*.pem`) or an installation token.
- Edit `agent-gh.sh` unless the human asks.

### Expected

Bot commits are unsigned and show as "Unverified" on GitHub. That is intentional. Don't try to sign them.
