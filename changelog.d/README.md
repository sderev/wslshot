# Changelog fragments

Use scriv fragments to record every change before release.

## Workflow
1. Run `uv run --extra dev scriv create`.
2. Edit the new file under `changelog.d/` using the template prompts.
3. Keep each change under the correct heading (Added, Changed, Deprecated, Removed, Fixed, Security).
4. Use short, past-tense bullet points; include links to issues or PRs when helpful.
5. Commit the fragment with the related code change.
6. Do not collect fragments manually; release automation will handle `uv run scriv collect`.

## Tips
- One fragment per logical change keeps the history clear.
- Leave empty sections commented out instead of deleting headings to simplify future edits.
- Preview fragments without modifying files: `uv run --extra dev scriv print` (returns status 2 if no fragments exist).
