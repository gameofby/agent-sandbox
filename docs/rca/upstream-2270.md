# Root cause analysis: resumed Sandboxes look like newly created Sandboxes

## Summary

Issue #2270 reports that `agent_sandboxes` cannot distinguish a Sandbox that
resumed from suspension from one that a user created and never suspended. Both
resources report `operating_mode="Running"`.

Pull request #2271 adds a `Resumed` reason to the `Suspended` condition. It also
adds a bounded `suspended_reason` label to `agent_sandboxes`. This fork
correction makes the reason accurate after delete failures and Pod read errors.

## Symptoms and impact

A capacity planner cannot count how many running Sandboxes resumed from
suspension. The resume counter reports transitions. The gauge does not show how
many resumed Sandboxes are running now.

A failed Pod delete could make a later cancellation look like a resume. A later
Pod read error could replace the completed suspension condition with `Unknown`
and erase the resume record.

## Verification

The source review traced these paths:

1. A completed suspension reports `Suspended=True/PodTerminated`.
2. A later Pod read error changes that condition to `Unknown/PodStateUnknown`.
3. A failed Pod delete returns the existing Pod and an error. The condition
   remains `False/PodTerminating` for compatibility.
4. The original correction read only the condition. It could use stale or
   ambiguous condition data to report `Resumed`.

The regression tests cover a failed delete, a Pod read error after completion,
a cleanup error, and a second failed suspend.

## Cause

The `Suspended` condition is a presentation field. It does not store every
suspend attempt. An error transition can replace the condition reason that
proved completion.

Pod existence alone also does not prove that Pod deletion started. A failed
delete can leave a running Pod in place.

## Fix

The controller now stores the suspend attempt in `status.suspension`. The value
includes state and generation:

- `Started` means the controller accepted the suspend request.
- `Terminating` means Pod deletion started.
- `Completed` means the backing Pod is gone.

A new suspend generation replaces an earlier result with `Started`. A later Pod
read or cleanup error cannot erase `Terminating` or `Completed` for the same
generation. A running Sandbox reports `Resumed` only when this status field
shows that deletion started or completed. The condition remains a fallback for
status written before the field existed. A matching-generation
`Suspended=True/PodTerminated` condition seeds the new field even when a Pod
read error occurs during the first reconcile after an upgrade.

The correction keeps the existing `Suspended` status, message,
`lastTransitionTime`, and `Ready` condition behavior. The failed-delete error
has a sentinel so state logic can distinguish it from a cleanup error. The
status field and condition use one optimistic-locked status patch, so a stale
reconcile cannot record state for an old spec generation.

## Compatibility

`Resumed` remains an added condition reason. Only the reason changes from the
base revision. The new metric label has a fixed allowlist. The status field
adds observed state without changing `spec`. The condition fallback preserves
resume detection for objects written before the field existed.

## Provenance

- Issue: https://github.com/kubernetes-sigs/agent-sandbox/issues/2270
- Pull request: https://github.com/kubernetes-sigs/agent-sandbox/pull/2271
- Upstream base and merge base: `13470fedf66b31c178c51f33830ba1f17431529a`
- Reviewed upstream head: `97b18c2626dec271dc52976d6f93a05232c74dcc`
- Fork branch: `codex/issue-2270`

## Review findings

The first Spec review rejected condition changes that altered status and
`lastTransitionTime`. It also found that the generic `podErr` path included
annotation cleanup errors.

The correction preserves the condition transitions. It adds a typed
failed-delete error and a generation-aware status field. Regression tests
exercise the rejected paths.

The Standards review found that the upstream pull request body lacks the
required release-note block. The hard guardrail forbids an upstream body edit
without user confirmation. That Standards finding remains open on the upstream
pull request.

## Regression coverage

- A failed delete reports `PodTerminating` and records only `started`.
- A failed delete followed by cancellation reports `NotSuspended`.
- A completed suspension remains in status after a Pod read error.
- A pre-field completed condition seeds the status field during a Pod read error.
- The `Suspended` condition still changes to `Unknown` during that read error.
- A later running reconciliation reports `Resumed`.
- A second failed suspend cannot reuse the prior completed state.
- A cleanup error keeps the existing condition behavior.
- The status field persists through the status subresource.

## Checks

- `go test ./controllers ./internal/metrics -count=1` passes.
- `git diff --check` passes.

The fork tracking issue records the final Standards and Spec reviews and the
repository-wide check results.
