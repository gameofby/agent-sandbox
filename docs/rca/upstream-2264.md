# Root cause analysis: generated-file failures look like infrastructure failures

## Summary

Issue #2264 reported that the nightly flake report counted failures from
`presubmit-test-autogen-up-to-date` as infrastructure failures.

That presubmit writes no JUnit results. A pull request with stale generated
files therefore gives TestGrid the same shape as a pod that dies before a test
runs. Only the build log contains the cause.

Pull request #2265 adds build-log classification. This fork correction makes
that classification reach the JUnit-less presubmit path and keeps temporary
artifact-server failures unknown.

## Symptoms and impact

The flake report can file a false infrastructure issue for an author-actionable
generated-file failure. Maintainers then inspect the wrong system, and the
pull request owner can miss the required regeneration.

## Verification

Issue #2264 records 11 reported infrastructure failures for this lane. The
author inspected all 13 red runs and 4 aborted runs in a 229-run interval:

- Seven runs printed `ERROR: Generated files out-of-date`.
- Five runs had stale pull request merge conflicts.
- One pull request failed inside `dev/tools/fix-go-generate`.
- None failed before the job started its own check.

The upstream correction had two gaps:

1. `analyze_tab` read artifacts only when test rows existed. This lane has only
   job-level rows, so the new build-log classification did not run.
2. `fetch_text` treated HTTP server errors as definite missing artifacts. The
   report then classified a temporary outage as infrastructure.

## Cause

The report treated "no JUnit" as the only signal from a JUnit-less presubmit.
It did not read the build log for this lane.

The artifact fetcher also combined network failures and HTTP responses. It did
not distinguish a missing file from a temporary server error.

## Fix

The flake report now reads the build log when the generated-files presubmit
has no test result and no clone failure. It classifies a run with the gate
error as pre-test pull request breakage. It keeps the remaining unclassified
runs in the infrastructure bucket, as the issue and pull request describe.

The fetcher retries temporary HTTP statuses. After the retries fail, the
fetcher reports the artifact as unavailable. The classifier returns `unknown`
for that run. A definite HTTP client error still means that the artifact is
absent.

## Compatibility

The report keeps its existing categories, issue markers, and command-line
interface. A generated-file failure now appears in the pre-test breakage count
instead of the infrastructure count. A temporary fetch failure now produces an
`unknown` run and prevents an infrastructure issue for that tab until the
report can classify it. Definite missing files keep their existing behavior.

## Provenance

- Issue: https://github.com/kubernetes-sigs/agent-sandbox/issues/2264
- Pull request: https://github.com/kubernetes-sigs/agent-sandbox/pull/2265
- Original pull request base: `980c109a2be555f63fdc02e616d8f7dc803ee6ff`
- Original pull request head: `6689c6feeac20d8b95b68fef610e79bdb80d5a71`
- Actual merge base: `5b69e0b99b20e6a3b38177a48a8aeed4a55e97f7`
- Rebased upstream base: `13470fedf66b31c178c51f33830ba1f17431529a`
- Fork branch: `codex/issue-2264-rev2`

The original pull request base would show 1,894 unrelated deleted or reverted
lines against current upstream main. The fork branch therefore rebuilds the
original change on the current upstream base. Commit `8914b38c` preserves the
original author and patch identity (`08cd2208ff26a6433b8d028ed4ab8ead59e652d2`).
Its committer differs from the original head. The corrective commit follows
the rebuilt original change.

## Review findings

The initial independent Spec review found two defects:

- The new classification did not run on the JUnit-less presubmit.
- The fetcher could treat temporary HTTP server errors as missing artifacts.

The initial independent Standards review found documentation defects and
duplicated generated-file classification. The corrections use active voice,
scope the build-log read to the generated-file lane, and keep retry, run
classification, and generated-file classification in focused helpers.

## Regression coverage

The tests cover:

- A generated-files error on a JUnit-less presubmit.
- An unexplained JUnit-less failure that remains in the infrastructure count.
- A missing build-log error marker.
- An unavailable build log.
- Retry of temporary HTTP server errors.
- Retry of partial-transfer and HTTP/2 transport errors.
- No retry for a definite HTTP client error.
- No build-log request on unrelated JUnit-less lanes.

## Checks

- `PYTHONDONTWRITEBYTECODE=1 python3 -m unittest dev/tools/flake_report_test.py`
  passed 92 tests.
- `python3 -m py_compile dev/tools/flake_report_test.py
  dev/tools/flake-report` passed.
- The whitespace check found no error.

The fork tracking issue records repository-wide checks and final review
results.
