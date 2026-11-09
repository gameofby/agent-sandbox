# Design note: scoped-token v2 path scope

Status: The upstream feature design is open. This branch does not implement it.

Upstream issue: https://github.com/kubernetes-sigs/agent-sandbox/issues/2230

Base revision: `c8c5895bcd1db54d597149fdaa51771ca13c2ee6`

Run summary date: 2026-11-10 03:45 CST

## Feature gap

Scoped-token v2 binds a token to one canonical authorization target. The
target includes the namespace, Sandbox name, Sandbox UID, port, method, and
path.

`MintScopedTokenV2` stores those normalized values in the signed claims.
`ScopedTokenAuthorizer.Authorize` requires every request field to equal its
claim. Path changes fail authorization.

The file API uses the file name in the request path. One pre-issued token
therefore covers only one file path. The current token cannot authorize a
set of files under a common directory.

## Impact

A client that mints a token before the workload runs cannot know every file
name. A token minter on each request path removes the benefit of a
self-contained credential.

The issue asks for one of two designs:

1. Add an optional path-prefix scope that matches whole path segments.
2. Add an optional sandbox-wide scope while retaining the Sandbox UID,
   method, port, and expiry checks.

## Verification

Source review confirms the exact-match behavior in
`sandbox-router/authz/scopedtoken_v2.go` and
`sandbox-router/authz/scopedtoken.go`. Existing tests require every target
field to match.

I did not run `go test ./sandbox-router/authz` because this macOS environment
does not provide the Go toolchain. No source behavior is changed on this
branch.

## Security and compatibility questions

The path-prefix design must:

- match complete path segments;
- apply the same path cleanup as the router;
- preserve exact-path tokens;
- reject encoded traversal and prefix collisions;
- keep the Sandbox UID, method, port, and expiry bindings.

The sandbox-wide design is simpler. It gives no more isolation below the
Sandbox boundary. The issue notes that `ProcessService/Execute` already grants
control of the Sandbox. The design must still prevent cross-Sandbox use.

The token format is a public compatibility boundary. A new claim needs a
versioned decoding rule and clear behavior for older routers and issuers.

## Recommendation

Wait for the upstream design decision before adding code. The sandbox-wide
option appears sufficient if the goal is one pre-issued credential per
Sandbox. The path-prefix option is justified only if separate file-read and
process-execution credentials must remain in one Sandbox.

## Next action

Record the maintainers' decision. Then add focused authorization and
compatibility tests before the implementation.
