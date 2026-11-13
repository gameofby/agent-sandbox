# Root cause analysis: upstream issue #2209

## Report

Upstream issue: https://github.com/kubernetes-sigs/agent-sandbox/issues/2209

Upstream pull request: https://github.com/kubernetes-sigs/agent-sandbox/pull/2212

The report describes data loss after an orphan delete. The user asks Kubernetes
to keep the child resources. A stale controller cache can record new ownership
by the deleting Sandbox. The garbage collector can then delete those children.

## Symptoms

- A Sandbox delete with `propagationPolicy: Orphan` leaves its PVC, Pod, and
  Service unowned as expected.
- The controller can re-add a controller owner reference that names the
  deleting Sandbox.
- The garbage collector can delete the re-adopted child when the Sandbox
  deletion completes.
- The user loses storage or other resources that the orphan policy should keep.

## Root cause

The Sandbox controller cache can lag behind the Kubernetes API server. The
orphan delete sequence exposes the race:

1. The API server records the Sandbox deletion.
2. The garbage collector's orphan processing removes owner references from the
   child objects.
3. The controller reconciles a child from cached data.
4. The cached Sandbox can still appear live after the child appears unowned.
5. The adoption path re-adds an owner reference to the deleting Sandbox.
6. The garbage collector deletes the re-adopted child when Sandbox deletion
   completes.

Pods use the same adoption path as PVCs and Services. Any re-adopted dependent
can make the child eligible for garbage collection.

## Verification and limits

The issue report, the existing pull request, the controller source, and the
regression tests support the diagnosis. The regression test uses a fake client
with a stale Sandbox cache and a live API reader. The test cases cover a
deleting Sandbox, an absent Sandbox, a recreated Sandbox with a different UID,
and a live Sandbox that the controller still adopts.

This run did not repeat the race on a live Kubernetes cluster. A live test
needs deterministic control of informer cache timing. The fake-client test
exercises the adoption decision and verifies that released PVCs, Pods, and
Services stay unowned.

## Upstream status

The reviewed upstream PR head is
`588d346cee90aa9fd5290d9aac6b9b928e60e318`. It adds a positive test for children
of a live Sandbox. All required Prow presubmits and the three kOps benchmark
checks pass. The latest commit removed the prior `lgtm` label. OWNERS approval
and a new `lgtm` remain pending.

## Scope and revision

- Reviewed upstream PR head:
  `588d346cee90aa9fd5290d9aac6b9b928e60e318`
- PR base reference: `993fd4aa9f576b8374b8810ef45e7305ed2dd95d`
- Review merge base: `993fd4aa9f576b8374b8810ef45e7305ed2dd95d`
- Fork branch: `codex/issue-2209-rev2`
- Prior fork branch: `codex/issue-2209`
- Prior corrective head:
  `d19f48009eabcdc29dd0d1b29065231eb083ec4f`

The new revision branch preserves both upstream PR commits. It appends the
corrective change to the new approved PR head.

Pods use the same adoption helper as PVCs and Services. The upstream PR
explicitly includes the Pod path in its contract, so the correction protects
all three resource kinds. The RCA is part of the user's required tracking
workflow.

## Solution

The controller uses an uncached direct API reader before it adopts an unowned
PVC, Pod, or Service. It refuses adoption when:

- The live Sandbox is absent.
- The live Sandbox has a deletion timestamp.
- The live Sandbox has a different UID.

The reconciler requires the API reader. It does not fall back to the cache. It
returns an error when the reader is missing or the live read fails. An unknown
adoption decision also fails closed.

The typed `sandboxAdoptionDecision` keeps admission state separate from log
text. `refusalReason` supplies the message for the reason-specific `V(4)` log.

## Compatibility

The change does not alter an API type, CRD, generated client, or stored object.
Normal adoption still occurs when the live Sandbox is present, has the same
UID, and is not deleting.

The controller now requires a live API read when it considers an unowned child.
An API read failure returns an error instead of admitting the child. This fail
closed behavior protects orphan-delete data.

## Reviews

Separate fresh-context Matt Standards and Spec reviews checked the combined
patch. Functional Spec review passed. Standards review found an inaccurate
comment, string-based control state, and inherited commit messages that did
not explain their motivation. The corrections name the API server as the
deletion recorder, use a typed fail-closed decision, and consolidate the
unpublished revision into motivation-led commits.

Spec review also found that the live upstream PR description still claims a
cached fallback, names an old test, and says existing tests are unchanged. That
description drift needs correction during an approved upstream submission.

## Regression coverage

`TestReconcileSkipsAdoptionWhenCachedSandboxIsStale` covers PVC, Pod, and
Service adoption under each stale-cache state:

- Sandbox deletion in progress
- Sandbox absence
- Sandbox recreation with a different UID
- Allowed adoption of children of a live Sandbox

Other tests cover an API read error, a missing API reader, normal adoption, and
the typed decision and refusal text.

## Checks

The following focused checks pass with Go 1.27.3:

- `git diff --check`
- `gofmt`
- `go test ./controllers -count=1`
- `go test -race ./controllers -count=1`
- `go test ./cmd/agent-sandbox-controller -count=1`
- `go vet ./controllers`
- `make lint-go`
- `make lint-api`

The repository-wide `make all` check does not pass in this macOS environment.
Six PTY timing subtests receive no terminal-size output. Python setup also
cannot install `anyio==4.14.2` with Python 3.9. A supported Linux host and a
compatible Python version must repeat the full suite.

## Unresolved work

- Run `make all` on a supported Linux and Python environment.
- Obtain OWNERS approval for upstream PR #2212.
- Obtain explicit user confirmation before updating the upstream PR
  description or submitting corrective commits.
