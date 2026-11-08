# Root cause analysis: Upstream issue #2215

## Summary

The Python SDK `signal()` and `async_signal()` methods called `SendSignal` on the gRPC stub without a timeout deadline. If the gRPC connection stalled or the daemon hung, callers waited indefinitely.

## Root cause

In `clients/python/agentic-sandbox-client/k8s_agent_sandbox/commands/_process_handle.py`, the sync and async signal implementations did not supply a timeout parameter to the `SendSignal` RPC call:
```python
self._stub.SendSignal(request)
await self._stub.SendSignal(request)
```
Without a deadline parameter or timeout configuration, gRPC calls wait indefinitely for transport responses.

## Solution and review

Upstream PR #2216 resolves the issue:
- Sync and async implementations accept a configurable `timeout` parameter with a 5.0-second default.
- Signal deadlines raise standard Python `TimeoutError` while preserving the underlying gRPC exception cause.
- A signal timeout does not cancel or corrupt the primary output and exit stream.
- Matt Pocock Standards and Spec reviews completed with zero actionable findings.

## Verification

Unit tests in `k8s_agent_sandbox/test/unit/commands/test_process_handle.py` verify default and custom timeout arguments, exception propagation, and process stream survival after signal timeouts.
