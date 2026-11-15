# Upstream issue 2289: silent process streams

## Status and value

Source: https://github.com/kubernetes-sigs/agent-sandbox/issues/2289.
Verified source revision: `454d3353e5c26c561dd6de389f32f7f285030e38`.
Checked on 2026-11-15. No resolving PR was found in the issue timeline or PR search.

This is a feature proposal with reported operational failures. It is not a locally reproduced controller bug. A silent command can leave a stream without application data. An intermediary can then close the stream under its idle policy. The reporter measured this on a v1.0.11 deployment with a 60-second proxy timeout. Those measurements are reporter evidence, not results from this run.

## Source evidence and causal limits

`packages/sandboxd/spec/process/v1/process.proto` defines four `StartResponse` events: init, stdout, stderr, and exit. It has no keep-alive event or requested interval in `StartRequest`.

`packages/sandboxd/pkg/server/process.go`, in `ProcessServer.Start`, sends init, copies output from blocking readers, waits for process completion, and sends exit. There is no periodic application event. A command that emits no output therefore produces no additional application event between init and exit.

This supports the proposed failure mechanism. It does not prove which timeout closed a given connection. Proxy configuration, transport behavior, cancellation, and child cleanup need an integration reproduction. Do not assume that a process survives client disconnection: inspect and test server cancellation behavior before making that claim.

## Contribution and design decision

The author offers to implement the feature after maintainers select its shape. Useful contributions are a deterministic idle-proxy regression harness and a compatibility review. Maintainers must choose metadata versus a request field and whether SDKs opt in by default. Keep defaults unchanged until that decision is made.

A future implementation needs a bounded interval, serialized stream writes, cancellation ownership, and correct exit ordering. Reset the silence timer after normal output. Stop the timer at completion. Test pipe and PTY paths, cancellation, invalid intervals, slow readers, and no events after exit. Test opt-out behavior and older clients. Application events can reset some idle timers; they cannot override every intermediary policy or an absolute request deadline.

## Validation and next action

Source inspection confirms the missing event and timer. No runtime reproduction, proxy experiment, source fix, or new regression test ran. No executable code changed. Full repository checks and the Matt implementation/TDD/review loop remain pending because no implementation contract or resolving PR exists. This document does not claim fix readiness.

Next action: monitor the maintainer decision and any PR. Review that PR with independent Standards and Spec reviewers when available. Preserve this evidence and append a fix only for demonstrated defects. Upstream submissions still need explicit user confirmation.
