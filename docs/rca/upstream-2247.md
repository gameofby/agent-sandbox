# Root cause analysis: upstream issue #2247

## Report

Upstream issue: https://github.com/kubernetes-sigs/agent-sandbox/issues/2247

Upstream pull request: https://github.com/kubernetes-sigs/agent-sandbox/pull/2250

The issue reports two effects from a terminal SandboxWarmPool member. First,
the pool counts the dead member as active until the readiness grace period
ends. Second, a SandboxClaim can adopt the dead member as a fallback candidate.

## Symptoms

- A warm Sandbox reaches `Finished=True` from `PodFailed` or `PodSucceeded`.
- A warm Sandbox reaches `Ready=False` with reason `SandboxExpired`.
- The warm pool continues to count the Sandbox for up to the default
  five-minute readiness grace period.
- The pool delays replacement of an object that cannot become ready.
- A SandboxClaim can adopt the terminal Sandbox while it remains in the
  adoption queue.

## Root cause

The warm-pool reconcile loop treated every non-ready Sandbox inside the
readiness grace period as a starting member. It placed that member in
`healthySandboxes` and scheduled a post-grace check. It did not first test
whether the member had reached a state that replacement must handle.

The adoption fallback had a related gap. `getCandidate` accepted any
pool-owned Sandbox with non-empty cached Pod IPs as a fallback candidate. It
did not reject `Finished=True`, `PodFailed`, `PodSucceeded`, or
`SandboxExpired`. A claim could therefore begin adoption before the pool
deleted the dead member.

The combined defect keeps a dead member in both views of the pool. The pool
view delays replacement. The claim view can assign the dead member as usable
capacity.

## Reproduction and verification

The upstream PR adds a focused fake-client test for the pool path. The test
failed on the pre-fix base for:

- `Finished=True` with `PodFailed`
- `Finished=True` with `PodSucceeded`
- `Ready=False` with `SandboxExpired`
- `SandboxExpired` with an unschedulable Pod
- `SandboxExpired` with a scheduling-gated Pod

The test runs this command:

```sh
go test ./extensions/controllers \
  -run '^TestReconcilePool_DeletesTerminalSandboxWithinGracePeriod$' \
  -count=1
```

The pre-fix code returned a grace-period requeue for each case. The corrected
code deletes the member in the first pass and creates the replacement in the
next observed pass.

The fork adds claim-path coverage for terminal fallback candidates that have
cached Pod IPs. The new test failed before the claim correction and passes
after it. It covers `PodFailed`, `PodSucceeded`, and `SandboxExpired`.

The test uses fake clients. It does not run a live controller against a
Kubernetes API server. The repository test harness reaches the real controller
seams without depending on live scheduling latency.

## Scope and revision

- PR base reference: `dced311eeb1e2d34718843a47a68af38d123bc6c`
- Review merge base: `580cb3e6d291722632dc7a6c8d686fca88d8a37a`
- Original PR head: `be3306bd2492beffbf21fa10f186ce09e8ca625f`
- Fork branch: `codex/issue-2247`

The branch preserves the original PR commit and appends corrective commits.
It does not rewrite upstream history.

## Solution

`isSandboxTerminalReplacementEligible` identifies the terminal conditions for
which a warm-pool replacement can resolve the fault. The warm pool now checks
this predicate before it applies the readiness grace period or the
unschedulable and scheduling-gated holds.

`getCandidate` now rejects replacement-eligible Sandboxes before it can use
them as a fallback. The claim controller can cold-start or use another healthy
candidate while the pool removes the terminal member.

The claim controller also checks the candidate against an authoritative read
after it records the assignment. If the candidate became terminal in that
window, the controller clears the assignment and selects another candidate.
The recorded-assignment recovery path applies the same terminal check.

`SandboxReasonInvalidConfiguration` is terminal for claim adoption but not for
warm-pool replacement. The pool retains the member even after the readiness
grace period because a replacement built from the same pool name and template
can hit the same validation error. The operator must correct the configuration
and replace the retained member instead of relying on a delete/create retry.

## Compatibility and migration

This change flags a breaking runtime behavior change. A default pool now
replaces a terminal Sandbox immediately instead of waiting for the readiness
grace period. A default claim now rejects a terminal warm Sandbox instead of
using it as fallback capacity. An `InvalidConfiguration` member remains in the
pool instead of entering the post-grace delete and create loop.

The change does not modify an API type, CRD, generated client, stored object,
or user-managed specification. It requires no data migration. The normal
controller rollout applies the behavior, and a rollback restores the previous
runtime behavior without reversing a storage change.

Claims still adopt ready members and retain the existing fallback behavior for
valid members that are still starting.

## Validation and review findings

Review validated the pool replacement and claim-adoption paths. The resolved
risks are:

- The readiness grace flag, field, and configuration documentation described
  a policy that excluded terminal members. The corrected descriptions now say
  that the grace applies to non-terminal members and that terminal members are
  replaced immediately.
- `Finished=True` must not mask `InvalidConfiguration` and restart a
  delete/create loop.
- A recorded assignment must not complete after its Sandbox becomes terminal.
- A completion conflict must re-read the Sandbox before retrying, so a
  terminal state observed between attempts clears the assignment.

## Regression coverage

The pool tests cover:

- `Finished=True` alone
- `PodFailed` through `Ready=False`
- `PodSucceeded` through `Ready=False`
- `SandboxExpired`
- Terminal states that also carry unschedulable and scheduling-gated Pod
  conditions
- `InvalidConfiguration` retained inside and after the grace period
- `Finished=True` combined with `InvalidConfiguration`

The claim test covers fallback candidates with cached Pod IPs for:

- `PodFailed`
- `PodSucceeded`
- `SandboxExpired`
- A recorded assignment that becomes terminal before retry
- A candidate that becomes terminal after assignment but before completion
- A candidate that becomes terminal between an adoption-write conflict and
  the authoritative completion retry

## Checks

The following focused checks pass with Go 1.27.3:

- `git diff --check`
- `unformatted="$(gofmt -l extensions/controllers/sandboxclaim_controller.go extensions/controllers/sandboxclaim_controller_test.go extensions/controllers/sandboxwarmpool_controller.go extensions/controllers/sandboxwarmpool_controller_test.go)" && test -z "$unformatted"`
- `go test ./extensions/controllers -count=1`
- `go test -race ./extensions/controllers -count=1`
- `go test ./cmd/agent-sandbox-controller -count=1`
- `go vet ./extensions/controllers`
- `make lint-go`
- `make lint-api`

`make all` reached the Go tests, including
`extensions/controllers`, and those tests passed. The run then failed in two
unrelated Python suites on macOS:

- The Kubernetes Python client injected the host's
  `http://127.0.0.1:7890` proxy into one sync-client kubeconfig assertion.
- Nine OpenAI integration tests raised `WorkspaceArchiveReadError` while
  reading temporary workspace archives.

The failure differs from the controller paths under test. The macOS run cannot
validate those two unrelated Python suites.
