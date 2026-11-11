# Root cause analysis: upstream issue #2230

## Report

Upstream issue: https://github.com/kubernetes-sigs/agent-sandbox/issues/2230

Upstream pull request: https://github.com/kubernetes-sigs/agent-sandbox/pull/2258

The issue reports that scoped-token v2 cannot authorize the sandboxd file API.
An exact v2 token binds one namespace, Sandbox name, Sandbox UID, port, method,
and path. A token minted before a workload runs cannot know the file paths that
the workload will create.

## Root cause

The v2 authorizer requires every request target field to equal its signed
claims. This works for one exact endpoint. It does not work for clients that
use one token for REST and gRPC calls across one Sandbox.

The v1 authorizer gives these clients one token for one Sandbox, but it uses a
shared HMAC secret and binds the Sandbox name instead of the UID. A safer
replacement must keep the UID and expiry binding from v2.

## Solution

PR #2258 adds an opt-in sandbox scope. The new
`MintScopedTokenV2Sandbox` function signs a `scope: sandbox` claim with the
namespace, Sandbox name, Sandbox UID, and expiry. The authorizer checks those
identity fields and then permits every port, method, and path for that Sandbox.

Exact v2 tokens remain unchanged. Unknown scope values, target fields on a
sandbox-scoped token, a missing Sandbox UID, and routing overrides fail closed.
Older routers ignore the scope field and reject the token because its port,
method, and path fields are unset.

## Security boundary

The sandbox scope covers all in-Pod services, including sidecars. This matches
the current v1 boundary and the access already available through
`ProcessService/Execute`. Issuers must keep the token lifetime short.

The UID check prevents a token from following a Sandbox name to a recreated
Sandbox. The namespace and name check prevents cross-Sandbox use.

## Review and corrections

The fork preserves PR commits:

- `960af525ddefdf6cfd42820851b748aceff137b8`
- `bc426c99d13a9fcc91ca7e310693ac41a8ee3bf7`

The reviewed merge base is `dced311eeb1e2d34718843a47a68af38d123bc6c`.

The Spec reviews found that the Python SDK example did not show how to supply
the minted token. They also found that the unit test did not name separate
cross-Sandbox and recreated-UID cases. This branch adds a complete Python
example and separate identity denial cases. A compatibility test now verifies
that sandbox-scoped claims leave the exact target fields unset, so an older
router still fails closed.

The PR body describes manual kind-cluster checks. The fork does not claim that
it added automated E2E coverage. The local review could not repeat these
kind-cluster checks.

## Checks

Focused checks run on the fork branch:

- `go test ./sandbox-router/authz -count=1`
- `go test ./sandbox-router/... -count=1`
- `go test -race ./sandbox-router/authz -count=1`
- `go vet ./sandbox-router/authz`
- `make lint-go`
- `git diff --check`

## Unresolved work

- Prow checks need the upstream `ok-to-test` label.
- EasyCLA reports that the co-author has not signed the CLA.
- The upstream PR body and corrective commits need explicit user confirmation
  before any upstream update.
