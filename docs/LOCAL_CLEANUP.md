# Local scratch cleanup

Run from the repository root:

```powershell
python tools/clean_scratch.py
python tools/clean_scratch.py --apply
```

The default is a preview. Only direct child folders of `.tmp/` and `.test-work/` with a `.disposable` marker and no modifications in fourteen days qualify. `--days N` adjusts the inactivity threshold (minimum one day). Output lists folders and their logical file sizes. Filesystem errors stop the command and are visible to the caller.

Create disposable experiments in those folders, protect active work with `.active`, and remove it when finished. `.keep` pins evidence indefinitely. Folders containing either marker, Git metadata, symbolic links or Windows reparse points are skipped. Unmarked legacy folders stay untouched pending review. Do not run cleanup concurrently with a task writing to eligible scratch folders.

Session-end housekeeping is the regular process: preview, inspect and apply. During weeks when the repository is used, do this at least weekly; idle weeks need no scheduled job. This is a local developer tool, so no Pages deployment, provider calls, or runtime version change is needed.

`.ffw-work/` is deliberately outside automatic cleanup because it mixes disposable files with valuable recovery evidence. Remove its known disposable outputs after the task, and review incident files individually. Production artifacts already have configured retention; this tool does not change it. Archive/state data and Git history are never cleanup targets. Registered worktrees require clean-status and retained-commit checks followed by `git worktree remove`, not recursive deletion.

October 20 inspection: the two September worktrees `fix-no-recommendations` and `reclassify-703` were clean and their commits were ancestors of the current branch. They accounted for approximately 10.6 MiB. Remaining incident evidence was preserved. Next: use marked scratch for future disposable experiments and session-end sweeps.
