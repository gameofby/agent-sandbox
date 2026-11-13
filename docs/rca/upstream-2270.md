# Root cause analysis: resumed Sandboxes look newly created

## Summary

Issue #2270 reports that `agent_sandboxes` cannot separate a running Sandbox
that resumed from suspension from one that was created and never suspended.
Both have `operating_mode="Running"`.

Pull request #2271 adds the `Resumed` reason to the `Suspended` condition. It
also adds the bounded `suspended_reason` label to `agent_sandboxes`.

## Symptoms and impact

A capacity planner cannot count how much running capacity belongs to resumed
Sandboxes. The resume counter records transitions. The gauge does not show the
number of resumed Sandboxes that are running now.

An incorrect resume signal also makes capacity reports unreliable. A failed
delete must not count as a resume. A transient Pod read error must not erase a
completed suspension.

## Verification

Source review traced three paths:

1. A completed suspension reports `Suspended=True/PodTerminated`.
2. A Pod lookup failure must not replace that completed condition with
   `Unknown`, because the next resume uses it as evidence.
3. A failed Pod delete leaves the original Pod in place. A later cancel must
   report `NotSuspended`, not `Resumed`.

The upstream regression tests cover created, resumed, canceling, and fully
suspended Sandboxes. They also cover a failed lookup and the multiple-Pods
error.

## Cause

The existing `Suspended` condition records the current suspension state. It
does not separate a new Pod from a Pod recreated after suspension. The metric
also lacked a label that carried this distinction.

## Fix

The controller records `Resumed` after a completed suspension. It retains this
reason across later reconciles until the next suspend. A failed Pod delete
does not count as a resume. A failed Pod lookup preserves a completed
suspension. The multiple-Pods error reports `Unknown`, because running Pods
mean the suspension cannot be confirmed.

The metric collector copies the condition reason through a fixed allowlist.
The label keeps cardinality bounded. Unknown values become `unknown`.
Suspend-requested accounting treats `Resumed` as a running state, so a later
suspend is still counted.

## Compatibility

`Resumed` is a new reason value on an existing condition. The `Suspended`
status and `lastTransitionTime` behavior stays the same except when a failed
Pod lookup follows a confirmed suspension. In that case, the confirmed
condition stays `True`.

Clients that test only `Suspended=False` remain compatible. Clients that
compare the reason with `NotSuspended` must also accept `Resumed`.

## Provenance

- Issue: https://github.com/kubernetes-sigs/agent-sandbox/issues/2270
- Pull request: https://github.com/kubernetes-sigs/agent-sandbox/pull/2271
- Merge base: `13470fedf66b31c178c51f33830ba1f17431529a`
- Reviewed upstream head:
  `81d09b52fb3c0cb758a79a860f799b1756b9ce27`
- Fork branch: `codex/issue-2270-rev2`
- Previous fork correction:
  `codex/issue-2270` at `4cdb6d18ddf39f6ea2a768cc1f3dfcab58c45e97`

The previous fork correction used a new status field. Upstream commits
`227ad644` and `81d09b52` fixed the same failure modes with the existing
condition. The new revision starts from the upstream head. It keeps the old
branch as history and does not force-push it.

## Review findings

The fresh Standards review found three issues. It found no Fowler smell that
needed action.

1. The condition reason changes observable API behavior. The compatibility
   and migration path therefore need maintainer approval.
2. The pull request changed the hand-written controller metrics page under
   `site/content/`.
3. The pull request changed the hand-written condition reference under
   `site/content/`.

The repository instructions reserve hand-written pages under `site/content/`
for documentation tasks. This fork correction restores items 2 and 3 to the
merge base.

The fresh Spec review found one contract issue. The issue asks for a
maintainer call, but the pull request says the maintainers already made that
call. The issue body also says status behavior stays unchanged, while the
chosen implementation preserves a confirmed `True` status after a failed Pod
lookup. The fork cannot resolve this through an upstream issue or pull request
edit without user approval.

## Remaining work

Maintainers must select the condition model and confirm the failed-lookup
status behavior. The upstream pull request must add a release note and a
migration note for reason-based condition checks. The hard guardrail blocks
all upstream writes until the user gives explicit approval.

## Checks

- `go test ./controllers ./internal/metrics ./internal/metricsdocs -count=1`
  passed.
- `go vet ./controllers ./internal/metrics ./internal/metricsdocs` passed.
- `git diff --check` passed.
