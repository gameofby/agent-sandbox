# AWS Nitro Sandbox on EKS example review

## Report

Upstream issue: https://github.com/kubernetes-sigs/agent-sandbox/issues/2238

Upstream pull request: https://github.com/kubernetes-sigs/agent-sandbox/pull/2239

The issue asks for an Amazon EKS example that runs code-server in an
AWS Nitro Sandbox. The example must follow the existing Kata examples. It must
show how to check the guest kernel and uptime against the hosting node. It
must also show how to reach code-server with `kubectl port-forward` and how to
remove the resources.

## Revision

- PR base reference: `67e670b3e4a0cc1c26fef561cb8243ac389bfccf`
- Review merge base: `993fd4aa9f576b8374b8810ef45e7305ed2dd95d`
- Original reviewed PR head: `4356627acf280a81bfda4ee71bca57b62ee6d2f0`
- Current upstream PR head: `87ef7815bf3f0882bee7138b859c7de9c87dd772`
- Corrective branch: `codex/issue-2238-rev2`
- Reviewed example correction head:
  `17541ef6206e58b8269e0118d89cbfb0d4ef99b0`
- Example corrective commits after the current upstream head:
  - `590665c68d7f01bb59807ed831d93179a9f26d20`
  - `10915c3c5a0276ede6ef859043936d43fd570450`
  - `3df91cf872e1d608296a3702fe53109173dccfd3`
  - `eae61cbfbfde957e91371135da2ebb8f834c68f7`
  - `73bae4a8c6e563ce891920d542bd6874f5ecd01a`
  - `17541ef6206e58b8269e0118d89cbfb0d4ef99b0`

The branch preserves the upstream commits and appends corrective commits. It
does not rewrite upstream history.

## Verification

Source review confirmed that PR #2239 adds these items:

- `examples/nitro-eks-sandbox/`
- A Sandbox manifest with `runtimeClassName: isolated-sandbox`
- An examples index entry
- A documentation-site card
- Cluster creation, access, isolation, and cleanup steps

The PR author reports an end-to-end run on an Amazon EKS Auto Mode cluster
running Kubernetes 1.37 with Agent Sandbox v1.0.10. The author covered
controller installation, Sandbox startup, kernel checks, port-forward access,
password sign-in, and cleanup.

This review environment has no Kubernetes cluster or AWS credentials. It did
not repeat the EKS end-to-end test.

## Findings

CodeRabbit requested changes for documentation defects in the original head.

1. The guide ran `/proc/uptime` only inside the sandbox. It never read the node
   uptime, so readers could not perform the requested comparison.
2. The guide did not make the manifest easy to obtain from the rendered
   documentation site.
3. The guide said that only the `kubectl` session reached code-server. Other
   cluster pods could still connect by pod IP because no NetworkPolicy
   restricted that traffic.
4. The guide did not identify where Nitro Sandbox is available.

The first Matt Standards review also found passive voice, chained sentences,
documentation-site prose defects, and comments that restated the manifest.
The first Matt Spec review found the missing node uptime comparison.

## Correction

The corrective commits make these changes:

- Use `kubectl debug` on the hosting node to read `/proc/uptime`.
- Attach to the debug container with `--stdin` so the command returns the node
  uptime.
- Tell readers to compare the boot-time value from the sandbox and the node.
- Describe pod-IP reachability and the password authentication control.
- Rewrite affected prose for active voice and one idea per sentence.
- State that Nitro Sandbox requires EKS 1.36 or later.
- Link readers to the authoritative Region availability documentation.
- Make the YAML comments explain why the RuntimeClass and pinned image matter.
- Link the manifest from the documentation and show how to delete the temporary
  node debug pod named in the `kubectl debug` output.
- Apply and delete the manifest from its canonical raw URL so the guide does
  not require a local file.
- Add a cleanup command for the named debug pod.
- Add the requested node uptime check and keep the existing kernel check.
- Remove the product-name check because the issue asks for kernel and uptime
  comparisons only.

The correction preserves the one-command cluster setup, the single Sandbox
manifest, direct port-forward access, code-server password authentication, and
cleanup steps.

## Compatibility

The correction changes documentation and comments only. It does not change the
Sandbox API, the manifest behavior, or the site route. Existing users see the
same code-server image and port. The new `kubectl debug` step runs a temporary
debug pod on the hosting node. The guide tells the reader to delete that pod.

## Reviews

Separate fresh-context reviews checked the issue contract and repository
standards after the first corrective set.

- The initial Standards review found passive voice, chained sentences,
  documentation-site prose defects, and comments that restated the manifest.
- The initial Spec review found the missing node uptime comparison.
- The first final Standards review passed after those corrections.
- The first final Spec review passed after those corrections.
- A later Standards review found that the guide did not link its manifest and
  did not give a complete debug-pod cleanup action.
- Later corrections add the link and a cleanup command for the named debug pod.
- A later Spec review found that `kubectl debug` did not attach to the command
  and that the product-name check was outside the requested scope.
- The latest correction adds `--stdin` and removes the product-name check.

The reviewers kept the raw upstream commit messages out of the correction set.
Rewriting those messages would alter preserved upstream history. The reviewers
accepted the inline manifest copy as a documentation pattern.

## Checks

The following checks pass:

- `git diff --check`
- Ruby YAML parse of `sandbox-nitro-eks.yaml`
- Semantic comparison of the embedded README manifest and the YAML file
- Relative Markdown link check
- `make toc-verify`
- Hugo Extended 0.163.3 rendered preview

The Hugo build rendered 228 pages. The rendered Nitro page includes the
manifest link, node uptime comparison, access command, and pod-IP reachability
description.

`make all` completed generation, build, Go lint, API lint, and most Go unit
tests. The suite then failed in seven PTY timing subtests and in Python test
setup because Python 3.9 cannot install `anyio==4.14.2`. The counterpart issue
records the exact result.

## Open work

- Run the EKS end-to-end procedure in an AWS account if reviewers request new
  runtime evidence.
- Run the full suite on a supported Linux host with a compatible Python
  version.
- Obtain explicit user confirmation before an update to upstream PR #2239 or
  any other upstream submission.
