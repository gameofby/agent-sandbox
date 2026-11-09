# Root cause analysis (RCA): transient artifact fetch failures become infra verdicts

Status: The fork contains a corrective patch based on upstream PR #2233.

Upstream issue: https://github.com/kubernetes-sigs/agent-sandbox/issues/2231

Upstream fix PR: https://github.com/kubernetes-sigs/agent-sandbox/pull/2233

Original PR base: `5a3450263cbea2400abca5c3214f84a25b9d6c9d`

Original PR head: `4548f98f7c561a149f23469e8077f9cafa2f37cc`

Run summary date: 2026-11-10 03:45 CST

## Symptoms

The flake report can produce different infrastructure counts for the same
TestGrid window when the reporter host has a network problem.

On 2026-11-09, one report run counted 1 infrastructure run for
`presubmit-test-e2e`. A later run counted 18. The unit lane also reported 6
infrastructure runs and 23 pre-test failures in the first run. A healthy run
did not reproduce those counts.

## Reproduction and verification

The report used DNS and connection failures from the upstream issue as the
test input. I wrote focused unit tests that make the artifact fetch fail. The
tests failed before the correction and pass after it.

The test command is:

```console
python3 -m unittest discover -s dev/tools -p 'flake_report_test.py'
```

I did not reproduce the full DNS outage against live TestGrid data. That
network state is not deterministic. The unit tests drive the same fetch and
classification boundaries with deterministic failures.

## Cause

The original PR converted transport failures into `FetchUnavailable`. It did
not preserve the HTTP status for non-transient failures.

`curl -f` returned exit code 22 for every HTTP error. `fetch_text` raised a
plain `RuntimeError`. `make_artifact_fetcher` caught every `RuntimeError` and
returned `None`.

The classifier interpreted `None` as an absent artifact. HTTP 403, 429, 500,
and malformed JSON could therefore produce a run verdict. The issue requires
HTTP 404 to be the only absent-artifact signal.

## Scope

The defect affects:

- artifact retry and HTTP status handling;
- run classification;
- infra, pass, and flake counts;
- report rendering for unknown runs;
- flake and infra issue updates;
- issue updates that merge findings across tabs.

It does not affect TestGrid status decoding or GitHub issue deduplication
when all evidence is available.

## Fix

The fork patch keeps the complete HTTP response status from curl.

It maps HTTP 404 to `FetchNotFound`, which means the artifact is absent. It
maps transport failures, non-404 HTTP responses, and malformed JSON to
`FetchUnavailable`, which means the run is unknown.

Unknown columns do not count as failures, passes, retest flips, infra runs, or
flake runs. The report lists every unknown run, including a run whose Overall
cell did not turn red. Flake and infra issue updates wait for a clean rerun.

The patch preserves the original PR commit and its authorship. The corrective
commit appears after `4548f98`.

## Compatibility

The change preserves the successful HTTP response body and the existing retry
limits. It changes the internal fetch contract. Every classifier caller still
receives `None` only for HTTP 404.

The report text changes "red run(s) could not be classified" to "run(s) could
not be classified". This wording covers runs whose Overall cell remains green
while one test row fails.

## Review

Fresh Standards and Spec reviews found the HTTP-status bug and code-style
issues in the original PR head.

The upstream CodeRabbit review also found that unknown columns could affect
pass and retest counts and that issue updates could use incomplete evidence.
The fork correction covers those cases with regression tests.

## Regression coverage

The test suite covers:

- retry of transport failures;
- no retry for an HTTP response;
- HTTP 404 as the only absent signal;
- HTTP 503 as an unavailable artifact;
- a malformed successful pointer response as an unavailable run;
- malformed JSON and malformed artifact shapes as unavailable artifacts;
- exclusion of unknown failures and passes from flake counts;
- reporting of unknown runs with a green Overall cell;
- no issue update while evidence is incomplete.

## Checks

Local:

- `python3 -m unittest discover -s dev/tools -p 'flake_report_test.py'`: 68 passed.
- `git diff --check`: passed.

Repository-wide checks are pending. The current macOS environment does not
provide the Go toolchain that `make all` invokes.

## Remaining work

- Finish the second two-axis review of the corrective patch.
- Push the fork branch and verify the remote SHA.
- Run repository-required checks in an environment with the full toolchain.
- Obtain explicit user confirmation before any upstream PR update.
