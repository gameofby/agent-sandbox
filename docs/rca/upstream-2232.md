# Root cause analysis (RCA): kwokctl release download exhausts its retry budget

Status: The fork contains a corrective patch based on upstream PR #2234.

Upstream issue: https://github.com/kubernetes-sigs/agent-sandbox/issues/2232

Upstream fix PR: https://github.com/kubernetes-sigs/agent-sandbox/pull/2234

Original PR base: `5a3450263cbea2400abca5c3214f84a25b9d6c9d`

Original PR head: `c9b8dde79435872f880b5accac80d59e157cf471`

Run summary date: 2026-11-10 03:45 CST

## Symptoms

Two runs of `presubmit-agent-sandbox-test-e2e-scalability-kwok` failed before
the tests started.

The runs were `#2189` at 05:41 UTC and `#2194` at 05:54 UTC. The GitHub
release download returned HTTP 504 six times in a row. The original curl
command stopped after about thirty seconds.

## Reproduction and verification

The linked Prow runs provide the failure evidence. I did not wait for another
GitHub outage.

I tested the retry helper with a fake curl binary. The test records the full
argument list and checks the exit-code path. It failed before the helper
existed and passes after the correction.

The test command is:

```console
python3 dev/ci/presubmits/shared/test_download_with_retry.py
```

## Cause

Curl retried a transient HTTP status, but its default backoff ended after
about thirty seconds. The observed outage lasted longer.

The original PR also used one cache guard for both KWOK binaries. If
`kwokctl` was executable and `kwok` was absent, the script skipped both
downloads. A later cluster command could then fail before the tests ran.

The PR description promised a five-minute window. `--retry 8` with a 15 second
delay provides about two minutes of retry scheduling for immediate 504
responses.

## Scope

The defect affects the cold-cache setup of the scalability presubmit. It does
not affect test code or controller behavior.

## Fix

The fork patch adds a tested shared download helper. It uses 19 retries with
a 15 second delay and a 300 second retry limit. Immediate 504 responses can
therefore use almost the full five-minute window. Curl owns the wait loop.
The test checks the complete curl policy and does not wait through a simulated
outage.

The fork patch also adds a shared installer. The installer checks `kwokctl`
and `kwok` independently. Each binary uses the same retry policy.

The patch preserves the original PR commit and its authorship. The corrective
commit appears after `c9b8dde`.

## Compatibility

The helper uses curl options that the runner supports. A successful download
does not wait. The helper returns the curl failure code for permanent errors.

The change adds two small executables under `dev/ci/shared/`.
The existing shared CI test suite discovers the two test files.

## Review

Fresh Standards and Spec reviews found:

- no regression test;
- a partial-download guard;
- an inaccurate five-minute claim;
- repeated retry options.

The correction addresses all four findings.

## Regression coverage

The test suite covers:

- the exact retry policy;
- the destination arguments;
- propagation of a curl failure;
- a cold cache that installs both binaries;
- a warm `kwokctl` cache that installs only the missing `kwok` binary.

## Checks

Local:

- `python3 dev/ci/presubmits/shared/test_download_with_retry.py`: 2 passed.
- `python3 dev/ci/presubmits/shared/test_install_kwok.py`: 2 passed.
- `bash -n dev/ci/shared/download-with-retry`: passed.
- `bash -n dev/ci/shared/install-kwok`: passed.
- `bash -n dev/ci/presubmits/test-e2e-scalability-kwok`: passed.
- `git diff --check`: passed.

Repository-wide checks are pending. The current macOS environment does not
provide the Go toolchain that `make all` invokes.

## Remaining work

- Finish the second two-axis review of the corrective patch.
- Push the fork branch and verify the remote SHA.
- Run repository-required checks in an environment with the full toolchain.
- Obtain explicit user confirmation before any upstream PR update.
