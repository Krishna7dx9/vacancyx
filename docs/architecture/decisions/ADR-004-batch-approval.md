# ADR-004: Revision-bound batch approval

- Status: Accepted

## Context
Per-application prompts are disruptive; unreviewed external submission risks inaccurate or unintended data.

## Decision
Prepare many applications into a batch. Users approve/reject/edit entries in one session. Approval binds to immutable application revision hash, resume version and answer revision. Material edits invalidate approval. Workers submit only approved current revisions.

## Alternatives
Prompt every application harms usability. Blanket future approval is not informed review. Blind auto-submit is unsafe.

## Consequences
One review session authorizes multiple entries. CAPTCHA, OTP, legal attestations, ambiguous fields and uncertain outcomes enter an exception queue. External submissions cannot guarantee exactly-once; reconcile before retry.