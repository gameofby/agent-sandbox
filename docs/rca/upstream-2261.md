# RCA: Python SDK lifecycle options accept an invalid TTL

## Summary

The Python SDK can create a SandboxClaim with
`spec.lifecycle.ttlSecondsAfterFinished`. Issue #2261 requested that capability.
Pull request #2262 adds it for the synchronous and asynchronous clients.

The first PR revision accepted TTL values above the API's signed 32-bit
integer limit. The Kubernetes API server would reject those claims after the
SDK returned from validation. This is a feature-gap fix and a caught review
defect. It does not describe a production incident.

## Symptoms and impact

A caller can pass `ttl_seconds_after_finished=2147483648` to
`create_sandbox`. The SDK accepts the value and sends it in the claim body.
The SandboxClaim field is `*int32`, so the API rejects the body.

The caller sees a late Kubernetes validation error. The SDK should reject the
value before it sends a request.

## Verification

The API type is `*int32` in
`extensions/api/v1beta1/sandboxclaim_types.go`. The generated CRD also declares
`format: int32`.

At PR head `8b11df42c3d23ddcea5885e4b5a3694e3fd8c333`, a focused assertion
failed because the lifecycle constructor accepted
`2147483648`. The exact error was:

```text
AssertionError: value above int32 was accepted
```

## Cause

The first revision checked only that the TTL was an exact `int` and was
nonnegative. It did not check the field's signed 32-bit maximum.

The revision also assembled lifecycle data from separate primitive arguments.
That bypassed the Python SDK rule to use Pydantic models for data structures.

## Fix

`SandboxClaimLifecycleConfig` now validates the lifecycle options. It enforces:

- A positive integer shutdown delay.
- A nonnegative integer TTL no greater than `2147483647`.
- One shared shutdown-policy literal with the API's three valid values.
- Strict integer types so booleans and numeric strings remain invalid.

Both clients normalize their public keyword arguments into this model. The
utility layer returns a `SandboxClaimLifecycle` wire model. The synchronous and
asynchronous Kubernetes helpers serialize that model with the API field names.

The sync and async signatures expose the same options. Adoption still
preserves the existing lifecycle. A timer without a policy still sends
`Delete`, consistent with existing SDK behavior.

## Reviewed change

- Issue: https://github.com/kubernetes-sigs/agent-sandbox/issues/2261
- Pull request: https://github.com/kubernetes-sigs/agent-sandbox/pull/2262
- Original PR base: `890de53a4dd18e35313173e6dc34d9559b1a9733`
- Original PR head: `8b11df42c3d23ddcea5885e4b5a3694e3fd8c333`
- Fork branch: `codex/issue-2261`

The original PR commit remains in history. The corrective commit explains why
the change exists because rewriting the original commit would alter the
reviewed upstream history.

## Review findings

The independent Spec review found one issue: the missing `int32` upper bound.
It found no other functional gap.

The independent Standards review found two hard violations:

- The lifecycle data bypassed Pydantic.
- The original commit headline described the patch instead of the user
  problem.

The first violation is corrected here. The original-history violation is
recorded because the fork must preserve the upstream commit.

## Regression coverage

`test_lifecycle.py` now checks these boundaries:

- `2147483647` is accepted.
- `2147483648` is rejected.

The existing tests still cover:

- Sync and async behavior.
- Shutdown-policy values.
- Positive and exact-integer shutdown delays.
- Nonnegative and exact-integer TTLs.
- Adoption behavior.
- Tracing without a shutdown time.

## Checks

The following checks pass on the corrected fork branch:

- Python SDK suite: 1073 passed and 168 subtests passed.
- Python mypy: no issues in 38 source files.
- Generated Python documentation: current.
- Table of contents: current.
- `git diff --check`: pass.

`make all` regenerated files, built all executables, and passed Go and API lint.
Its full test target reached unrelated failures in
`packages/sandboxd/pkg/server`. Six subtests of
`TestStartWithPTY_InitialSizeVisibleImmediately` fail on this macOS host.
The run continued through the project's Python suites. It then waited on a
large `nemo-gym` dependency installation. The operator stopped that unrelated
installation after the relevant SDK checks and other suites had passed. The
same repository target also skips tests that require Linux `/proc`.

## Remaining work

The corrective branch is published only to `gameofby/agent-sandbox`.
No upstream comment, review, commit, or pull-request update has been submitted.
An upstream submission needs explicit user confirmation.
