# Root cause analysis: warm pools retain terminal Sandboxes

## Summary

Issue #2247 reports that `SandboxWarmPool` keeps terminal Sandboxes during the
readiness grace period. The pool delays replacement. A `SandboxClaim` can also
adopt the dead member as fallback capacity.

The reported terminal states include:

- `Finished=True`
- `Ready=False` with reason `PodFailed`
- `Ready=False` with reason `PodSucceeded`
- `Ready=False` with reason `SandboxExpired`

## Impact

A terminal Sandbox cannot become ready. Keeping it in the active replica count
hides the capacity loss for up to five minutes by default. Claim fallback also
risks assigning a Sandbox that cannot serve work.

## Verification

The source review traced the pool and claim paths. The upstream tests use the
existing fake-client harness.

The pre-fix test kept each terminal member in the active pool and scheduled a
grace-period requeue. The corrected test deletes the member on the first pass
and creates the replacement after the delete is observed.

The claim test now covers a cached fallback candidate that expired without a
`Finished` condition.

## Cause

`reconcilePool` checked the readiness grace period and scheduling holds before
it checked whether the Sandbox had reached a terminal state. The claim fallback
also accepted terminal warm-pool members.

## Fix

`isSandboxTerminal` recognizes `Finished=True` and the three requested
`Ready=False` reasons. Terminal members bypass the grace period, the
unschedulable hold, and the scheduling-gate hold. The claim controller skips
them before fallback adoption.

The correction removes the new five-second to five-minute replacement backoff.
The issue asks for immediate replacement. Operators already have
`--sandbox-warm-pool-replenish-delay` and
`--sandbox-warm-pool-max-refill-rate` when they need to pace refill.

## Compatibility

A default warm pool now replaces the named terminal states without waiting for
the readiness grace period. Claims no longer use those states as fallback
capacity.

The change does not modify an API type, CRD, generated client, or stored
object. It needs no data migration. The upstream PR must add the
`release-note-action-required` label because it changes default runtime
behavior.

Operators should review warm-pool templates that intentionally exit. The
existing replenishment delay and maximum refill rate controls can pace
replacement. A controller rollback restores the previous runtime behavior.

## Provenance

- Issue: https://github.com/kubernetes-sigs/agent-sandbox/issues/2247
- Pull request: https://github.com/kubernetes-sigs/agent-sandbox/pull/2250
- PR base: `dced311eeb1e2d34718843a47a68af38d123bc6c`
- Reviewed upstream head:
  `37c962e9014fa8a9170ebeb62c3d766e9ba72cba`
- Upstream commits:
  `be3306bd2492beffbf21fa10f186ce09e8ca625f`
  and `37c962e9014fa8a9170ebeb62c3d766e9ba72cba`
- Fork branch: `codex/issue-2247-rev2`
- Previous fork branch: `codex/issue-2247` at
  `d7711fb41f53527ecf4befce7d63491198d253b5`

The new revision starts from the current upstream head. It preserves prior
branches and does not force-push.

## Review findings

The fresh Standards review found passive sentences in the readiness-grace
text, a missing migration record for the default behavior change, and an
upstream commit message that does not stand alone.

The correction fixes the passive sentences and records the migration and
rollback behavior here. The upstream commit message and release label remain
external blockers under the hard guardrail.

The fresh Spec review found that the new head dropped the `SandboxExpired`
reason and added an unrequested backoff. The correction restores the full
terminal set and removes the backoff.

## Regression coverage

- A `Finished=True` member bypasses the grace period.
- `PodFailed` and `PodSucceeded` members without `Finished=True` bypass the
  grace period.
- A `SandboxExpired` member bypasses the grace period.
- Expiry bypasses the unschedulable and scheduling-gate holds.
- A claim skips an expired fallback candidate without `Finished=True`.
- The pool deletes a terminal member and creates its replacement without a
  replacement backoff.

## Checks

- `go test ./extensions/controllers -count=1` passed.
- `go test -race ./extensions/controllers -count=1` passed.
- `go test ./cmd/agent-sandbox-controller -count=1` passed.
- `go vet ./extensions/controllers ./cmd/agent-sandbox-controller` passed.
- `git diff --check` passed.
