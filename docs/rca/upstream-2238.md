# AWS Nitro Sandbox on EKS example review

## Report

Upstream issue: https://github.com/kubernetes-sigs/agent-sandbox/issues/2238

Upstream pull request: https://github.com/kubernetes-sigs/agent-sandbox/pull/2239

The issue asks for an Amazon EKS example that runs code-server in an
AWS Nitro Sandbox. The example must follow the existing Kata examples. It must
show how to check the guest kernel and uptime. It must also show how to reach
code-server with `kubectl port-forward` and how to remove the resources.

## Revision

- PR base reference: `67e670b3e4a0cc1c26fef561cb8243ac389bfccf`
- Review merge base: `993fd4aa9f576b8374b8810ef45e7305ed2dd95d`
- Original PR head: `4356627acf280a81bfda4ee71bca57b62ee6d2f0`
- Corrective commit: `ce540553`
- Original PR commit count: 1

The original commit remains unchanged. The correction appends a second commit
to branch `codex/issue-2238`.

## Verification

Source review confirmed that the original PR adds these items:

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

CodeRabbit requested changes for three documentation defects.

1. The rendered documentation did not tell readers how to obtain
   `sandbox-nitro-eks.yaml`.
2. The guide ran `/proc/uptime` only inside the sandbox. It never read the node
   uptime, so readers could not perform the requested comparison.
3. The guide said that only the `kubectl` session reached code-server. The
   pod IP remained reachable to other cluster pods because no NetworkPolicy
   restricted that traffic.

The first standards review also found passive voice, chained sentences,
term-order problems, and an unclear YAML comment. The first specification review
found the missing node uptime comparison.

## Correction

The corrective commit makes these changes:

- It adds repository clone and directory-change commands before
  `kubectl apply`.
- It uses `kubectl debug` on the hosting node to read the node uptime from
  `/proc/uptime`.
- It tells readers to compare the first uptime value from the sandbox and the
  node.
- It describes pod-IP reachability and the password and NetworkPolicy controls.
- It rewrites affected prose for active voice and one idea per sentence.
- It identifies `isolated-sandbox` as a RuntimeClass.

The correction preserves the one-command cluster setup, the single Sandbox
manifest, direct port-forward access, password authentication, and cleanup
steps.

## Compatibility

The correction changes documentation and comments only. It does not change the
Sandbox API, the manifest behavior, or the site route. Existing users see the
same code-server image and port. The added `kubectl debug` step uses an AWS
EKS managed node and creates a temporary debug pod. The guide tells the reader
to delete that pod.

## Reviews

The final fresh standards review found no remaining documented-standard
violations or Fowler smells. The final fresh specification review found no
missing or incorrect functional requirement. This RCA is a required
fork-tracker artifact. It is outside the upstream pull request scope.

## Checks

The following checks pass:

- `git diff --check`
- Ruby YAML parse of `sandbox-nitro-eks.yaml`
- Semantic comparison of the embedded README manifest and the YAML file
- Relative Markdown link check

The example README and documentation-site card mount into the Hugo site. Hugo
is unavailable in this environment, so the rendered-preview check did not run.

The host has no Go executable, so these repository checks did not run:

- `make all`
- `make test-unit`
- `make toc-verify`

## Open work

- Repeat the EKS end-to-end run in an AWS account if reviewers require new
  runtime evidence.
- Run `make all`, `make test-unit`, and `make toc-verify` on a host with the
  repository Go toolchain.
- Obtain explicit user confirmation before any update to upstream PR #2239.
