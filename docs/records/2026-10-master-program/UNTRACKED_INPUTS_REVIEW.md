# Untracked owned inputs review

**Verdict:** approve with one corrected implementation detail.

The production failure was real: lanes are created from `HEAD`, while tracked
dirty files and untracked files are independent baseline state. Overlaying only
tracked dirty files lets a worker recreate an already-existing untracked file,
producing a patch that cannot integrate.

The opt-in design is sound. `git ls-files --others
--exclude-standard -z` excludes ignored files, the runner filters candidates by
ownership and `forbidden`, and `overlay_dirty_inputs` independently rejects
ignored, tracked, non-file, and symlink inputs before copying. Paths outside
ownership and forbidden paths are therefore not selected, and symlinked secrets
cannot be copied. With the flag absent, the expanded list is not computed and
existing explicit-list behavior is unchanged.

The reviewed implementation had one defect: it decoded Git's NUL-separated
output as locale text. On Windows, an untracked owned path containing characters
outside the active code page could fail decoding before task creation. This
review replaces that direct subprocess with the repository's existing UTF-8,
NUL-separated Git path parser and validates `include_untracked_owned` as a
boolean. A focused test covers ignored-file exclusion and a Unicode filename.

Replays and correction children remain consistent because persisted requests
store the expanded `include_untracked` list. Retry and correction construction
passes that explicit list back to `create_task`; `_validated_inherited_patch`
then compares the same list (and project fingerprint) before applying an
inherited patch. Newly appearing or removed untracked files change the project
fingerprint and fail the stale-result check rather than silently rebasing the
inherited patch.

## Residual risks

- An unignored, owned file containing secrets is intentionally treated as an
  authorized lane input; callers must keep secret files ignored or forbidden.
- Untracked symlink inputs fail closed rather than being skipped; the task must
  list a real file or avoid the symlink.
- A non-atomic change to the project between enumeration and fingerprinting
  can still make a submitted task stale, which is the safer existing outcome.
- Acceptance tests were not run in this sandbox because Python execution is
  prohibited by the task environment.
