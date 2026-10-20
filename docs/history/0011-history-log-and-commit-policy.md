# 0011: history log, verbatim feedback and commit policy

Date: 2026-10-20 (06:03Z-07:21Z = 02:03-03:21 EDT)

## Context

The session had grown long enough to need compaction, and the user's hand-written review notes are the ground truth for what "realistic" means; paraphrasing loses it. They asked for:

- "also make sure to commit regularly" and "(backfill commits as well with rough timestamps)" (06:03Z);
- "we should be keeping track of changes that we make over time in some kind of running docs or ADRs folder, and typed-out text like the stuff currently in the html file is extremely valuable and should be kept verbatim along with its associated images. (you can spawn subgents to backfill past changes in the docs/history file)" (07:20Z);
- "also continue to commit regularly (you don't necessarily need to do one right now)" (07:21Z).

Earlier, the user also set the rules to re-open changed visuals once per change (feedback 0015 and 0018), which the history log follows.

## Decision

- `docs/history/` with ADR entries `NNNN-short-title.md` (Context, Decision, Consequences, Commits), `feedback/` for verbatim user text with timestamps and `images/` for screenshots decoded from the log; rule: new feedback is saved verbatim in the same turn, then summarised in an ADR.
- Commits: conventional commits, user account only. Answers to the planning question: "Everything except raw downloads and samples" for the generator repo, and a `.gitignore` was created in `kernelBashing`. The generator repo's `.gitignore` was extended (raw downloads, sample outputs, `output_dataset`, `finalDataset`, `docs/showcase/images/`, `.DS_Store`).
- Backfilled commits: the first seven commits (`a3ffe4e` to `654fcf2`) carry estimated timestamps 00:07, 00:27, 00:34, 00:52, 01:15, 01:48, 01:52 EDT. The first backfill grouped files by modification time and put the core generator after the audit, which was logically wrong, so the assistant reset its own backfill commits and redid them in logical order. The first generator commit is a snapshot of the then-current code (earlier states were never saved). Commits from `fc741b9` on use real time.

## Consequences

- Timestamps in ADRs 0001-0005 are estimates; ADRs 0007-0010 use real commit times. Dates in the feedback files are the log's UTC values with local equivalents.
- Not included as feedback: unrelated side exchanges (the statusline / agent-panel question at 05:48-05:51Z with its screenshot, `/compact`, "continue"), the grid failure notes the user typed in their browser (not exported, see ADR 0010) and queued agent hand-back messages, which are not the user's words.
- Limits: all screenshots the user sent from 05:40Z onward were embedded in the transcript and are decoded under `images/`; the user sent no screenshots before 05:40Z in the generator work. The statusline screenshot is not decoded because it is unrelated.

## Feedback that triggered this

- [0021 commit regularly and backfill](feedback/0021-commit-regularly-and-backfill.md)
- [0028 history docs request](feedback/0028-history-docs-request.md)
- [0015 re-open changed visuals](feedback/0015-reopen-changed-visuals.md)
- [0018 re-open rule updates](feedback/0018-reopen-rule-updates.md)

## Commits

- `a3ffe4e` through `654fcf2`: backfilled estimates, see the list in ADRs 0001-0005.
- `fc741b9`, `dd3c4da`, `61b6a85`, `c831415`: regular commits during the burial rounds and the grid (ADRs 0007-0010).
- This `docs/history/` folder itself is not committed by the backfill.
