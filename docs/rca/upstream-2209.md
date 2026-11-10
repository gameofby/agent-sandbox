# Root cause analysis: Upstream issue #2209

## Summary

When a user deletes a Sandbox with `propagationPolicy: Orphan`, the Kubernetes garbage collector's orphan processing removes the owner references from child resources. A race condition allowed a reconciler with a stale cache to observe unowned PVCs, Pods, or Services and re-add owner references pointing to the deleting Sandbox. The Kubernetes garbage collector then deleted the re-adopted resources when it finalized the Sandbox deletion.

## Root cause

The Sandbox controller cache lags behind the Kubernetes API server. When orphan deletion occurs:
1. The API server strips owner references from child objects and sets `deletionTimestamp` on the Sandbox.
2. The controller reconciles child resources using cached data.
3. If the cache does not reflect the deletion status yet, adoption logic treats the released resources as orphaned unowned items and re-attaches owner references.
4. When the API server completes Sandbox finalization, the garbage collector deletes the re-attached resources.

## Solution

The controller resolves this race before it adopts an unowned child:
- The controller uses an uncached direct API reader before adopting unowned PVCs, Pods, or Services.
- Helper `sandboxCanAdopt` verifies the current Sandbox object directly from the API server.
- The reconciler adopts a child only when the live Sandbox has the same UID
  and no deletion timestamp.
- The controller reports why adoption is blocked when the Sandbox is
  deleting, absent, recreated with a different UID, or cannot be read.

Pods follow the same orphan-deletion path as PVCs and Services. The controller
must guard all three resource types because any re-adopted dependent can
return to the deleting Sandbox and become eligible for garbage collection.

## Verification

Unit tests in `controllers/sandbox_controller_test.go` verify stale cache
rejection during deletion, absence, UID mismatch, and API reader errors. A
table test covers every adoption decision.
