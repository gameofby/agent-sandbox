# Root cause analysis: Python SDK lacks Sandbox lifecycle methods

## Summary

Issue #2272 requested `suspend()`, `resume()`, and `is_suspended()` for the
Python synchronous and asynchronous Sandbox handles.

Pull request #2273 adds the methods and waits for the requested lifecycle
condition. This fork correction closes race and replacement gaps found in
review.

## Symptoms and impact

Python callers had to patch `spec.operatingMode` themselves. They also had to
implement condition waits, timeout handling, connection teardown, and reconnect
behavior. Snapshots were the only Python API with suspend and resume support.

Without UID and termination checks, a stale handle could patch a same-name
Sandbox replacement or report success for a Sandbox that was being deleted.

## Verification

The source review checked the current four-commit pull request head. It traced:

1. The initial GET, UID check, merge patch, condition watch, and final mode
   check.
2. Sync and async timeout behavior and the lifecycle lock.
3. Connector replacement after suspend and resume.
4. Snapshot subclass signatures and return values.
5. Reattach paths that already fetch the current Sandbox object.

The tests reproduce termination and close races before the correction.

## Cause

The lifecycle methods learned the Sandbox UID on their first call. Reattach
already had the Sandbox object, but did not pass its UID to the new handle.

The async handle replaced a connector after an await. A concurrent
`close_connection()` could mark the handle closed before the replacement was
published, which left the replacement open.

The lifecycle check inspected the UID and mode but ignored
`metadata.deletionTimestamp`.

## Fix

The reattach paths bind the fetched Sandbox UID before returning the handle.
Lifecycle calls reject a Sandbox with a deletion timestamp before the patch and
after the condition wait. The async close path takes the lifecycle lock, so it
closes the connector that the active operation publishes. A queued lifecycle
call checks the closed state again after it acquires the lock. Close may obtain
the lock before a lifecycle waiter even when the waiter passed the initial
check. The second check prevents the waiter from rebuilding a connector after
close.

The original pull request commits and authorship remain unchanged.

## Compatibility

The new methods are additive. The snapshot extension keeps its method
signatures and return types and accepts `timeout=` as an alias for
`wait_timeout`. Existing sync and async callers keep their current behavior.

## Provenance

- Issue: https://github.com/kubernetes-sigs/agent-sandbox/issues/2272
- Pull request: https://github.com/kubernetes-sigs/agent-sandbox/pull/2273
- Upstream base and merge base: `13470fedf66b31c178c51f33830ba1f17431529a`
- Reviewed upstream head: `9e2d68f7b6479d881faa148354f358677fa26954`
- Fork branch: `codex/issue-2272`

## Review findings

The initial practical concerns about Kubernetes 35 content-type handling and
connector private-state transfer were fixed in the reviewed pull request head.

The independent Standards review found an async close and connector replacement
race. The Spec review found that UID fencing started too late on reattach and
that lifecycle calls could accept a terminating Sandbox.

The corrective commit fixes all three issues and adds sync and async regression
tests.

## Regression coverage

- A handle rejects a replacement Sandbox on its first lifecycle call after
  reattach.
- Sync and async lifecycle calls reject `metadata.deletionTimestamp`.
- Async close waits for an active suspend and closes the replacement connector.
- A lifecycle waiter rejects a handle when close obtains the lock first.

## Checks

- Full Python suite passes: 1106 tests and 186 subtests.
- `mypy` reaches only two pre-existing errors in `trace_manager.py`.
- `git diff --check` passes.

The fork tracking issue records repository-wide checks and final review results.
