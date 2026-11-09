# Root cause analysis: Upstream issue #2209

## Summary

When a user deletes a Sandbox with `propagationPolicy: Orphan`, the controller releases child resources by removing owner references. A race condition allowed a reconciler with a stale cache to observe unowned PVCs, Pods, or Services and re-add owner references pointing to the deleting Sandbox. The Kubernetes garbage collector then deleted the re-adopted resources when it finalized the Sandbox deletion.

## Root cause

The Sandbox controller cache lags behind the Kubernetes API server. When orphan deletion occurs:
1. The API server strips owner references from child objects and sets `deletionTimestamp` on the Sandbox.
2. The controller reconciles child resources using cached data.
3. If the cache does not reflect the deletion status yet, adoption logic treats the released resources as orphaned unowned items and re-attaches owner references.
4. When the API server completes Sandbox finalization, the garbage collector deletes the re-attached resources.

## Solution and reviews

Upstream PR #2212 resolves this race:
- The controller uses an uncached direct API reader before adopting unowned PVCs, Pods, or Services.
- Helper `sandboxCanAdopt` verifies the current Sandbox object directly from the API server.
- The reconciler refuses adoption if the Sandbox has a `deletionTimestamp`, a mismatched UID, or no longer exists.

The first Matt Pocock Standards review found one code-quality problem. The
helper returned one boolean for three different states, and every caller
logged that the Sandbox was being deleted. That message was false when the
Sandbox was absent or had a different UID. The controller now returns a typed
adoption decision and logs the actual reason.

The Spec review found that the PR also protects Pod adoption. Issue #2209
names PVCs and Services, but Pods follow the same orphan-deletion path. The
Pod change remains because removing it would leave the same data-loss race.
The PR body discloses the Pod change. A maintainer can confirm the intended
scope before merge.

## Verification

Unit tests in `controllers/sandbox_controller_test.go` verify stale cache
rejection during deletion, absence, UID mismatch, and API reader errors. A
table test covers every adoption decision.
