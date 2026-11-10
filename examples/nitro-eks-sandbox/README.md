# AWS Nitro Sandbox on Amazon EKS

## Overview

This example runs VS Code in the browser ([code-server](https://github.com/coder/code-server)) inside an [AWS Nitro Sandbox](https://docs.aws.amazon.com/eks/latest/userguide/sandboxing.html) on an [Amazon EKS Auto Mode](https://docs.aws.amazon.com/eks/latest/userguide/automode.html) cluster. AWS Nitro Sandbox isolates the Agent Sandbox. Use `kubectl port-forward` to open VS Code.

When a pod sets `runtimeClassName: isolated-sandbox`, the Nitro Hypervisor starts a lightweight VM with its own kernel. The VM isolates the pod's CPU and memory at the hardware level. The pod keeps its containers, image, and spec. The kubelet still sees an ordinary pod, so `kubectl exec`, `logs`, and `port-forward` work.

EKS Auto Mode provides everything else. A new Auto Mode cluster includes the `isolated-sandbox` RuntimeClass. Auto Mode also launches a node when a pod requests a sandbox. The reader does not need to create a node pool, install a DaemonSet, or register the RuntimeClass.

## Prerequisites

1. [Install](https://docs.aws.amazon.com/cli/latest/userguide/getting-started-install.html) the AWS CLI and configure it for your account.
2. [Install eksctl](https://eksctl.io/installation/) and [kubectl](https://kubernetes.io/docs/tasks/tools/).
3. Review the Nitro Sandbox requirements in the [Amazon EKS documentation](https://docs.aws.amazon.com/eks/latest/userguide/sandboxing.html).

## Step 1: Create an EKS Auto Mode cluster

> **Note:** this command creates billable AWS resources. It creates an EKS cluster, its VPC, and the EC2 instances that Auto Mode launches for your pods. See [Cleanup](#cleanup) to remove them.

AWS supports Nitro Sandbox on Amazon EKS 1.36 or later. Check the [Amazon EKS documentation](https://docs.aws.amazon.com/eks/latest/userguide/sandboxing.html) for the supported Regions. Replace `<REGION>` and `<EKS VERSION>` below:

```shell
eksctl create cluster --name nitro-sandbox-demo --region <REGION> --version <EKS VERSION> --enable-auto-mode
```

Check that the cluster has the Nitro Sandbox runtime classes:

```shell
kubectl get runtimeclass
```

```text
NAME                   HANDLER                AGE
confidential-sandbox   confidential-sandbox   4d11h
isolated-sandbox       isolated-sandbox       4d11h
```

This example uses `isolated-sandbox`. The [Amazon EKS documentation](https://docs.aws.amazon.com/eks/latest/userguide/sandboxing.html) describes `confidential-sandbox`.

## Step 2: Install the Agent Sandbox Controller

Install the Agent Sandbox controller following the [Installation Guide](../../README.md#installation), then wait for it to be ready:

```shell
kubectl -n agent-sandbox-system rollout status deploy/agent-sandbox-controller
```

## Step 3: Deploy VS Code in an Agent Sandbox

The [example manifest](https://github.com/kubernetes-sigs/agent-sandbox/blob/main/examples/nitro-eks-sandbox/sandbox-nitro-eks.yaml)
defines a `Sandbox` that runs code-server and requests the `isolated-sandbox`
runtime. That one field is the only Nitro-specific line.

```yaml
apiVersion: agents.x-k8s.io/v1beta1
kind: Sandbox
metadata:
  name: vscode-nitro
spec:
  podTemplate:
    spec:
      runtimeClassName: isolated-sandbox
      containers:
      - name: code-server
        image: codercom/code-server:4.145.2
        securityContext:
          runAsNonRoot: true
        ports:
        - containerPort: 8080
        resources:
          requests:
            cpu: "1"
            memory: 2Gi
```

Apply it and wait for the sandbox to be ready:

```shell
kubectl apply -f sandbox-nitro-eks.yaml
kubectl wait --for=condition=Ready sandbox/vscode-nitro --timeout=5m
kubectl get sandbox vscode-nitro
```

```text
NAME           READY   REASON              AGE
vscode-nitro   True    DependenciesReady   25s
```

## Step 4: Verify the Isolation

Compare the kernel inside the sandbox with the kernel of the node it runs on:

```shell
kubectl exec vscode-nitro -- uname -r

SANDBOX_NODE="$(kubectl get pod vscode-nitro -o jsonpath='{.spec.nodeName}')"
kubectl get node "${SANDBOX_NODE}" -o jsonpath='{.status.nodeInfo.kernelVersion}'
```

```text
6.18.54
6.18.56
```

The two versions differ, so the sandbox boots its own kernel. Run these commands to compare its uptime with the node and to read the VM product name:

```shell
kubectl exec vscode-nitro -- cat /proc/uptime

kubectl debug node/"${SANDBOX_NODE}" \
  --image=busybox:1.36 \
  --profile=sysadmin \
  -- chroot /host cat /proc/uptime

kubectl exec vscode-nitro -- cat /sys/class/dmi/id/product_name
```

```text
45.59 43.62
45983.17 183927.40
m8a.enclave
```

The first value in each uptime output reports the number of seconds since that
system booted. The sandbox value starts when Nitro Sandbox starts the VM. The
node value starts when the node boots. Different values confirm separate boot
times. Delete the debug pod when you finish the check:

```shell
kubectl delete pods \
  --selector=app.kubernetes.io/managed-by=kubectl-debug \
  --field-selector="spec.nodeName=${SANDBOX_NODE}"
```

## Step 5: Open VS Code

Forward a local port to the sandbox's pod. The pod has the same name as the `Sandbox`:

```shell
kubectl port-forward pod/vscode-nitro 8080:8080
```

In another terminal, read the password that code-server generated:

```shell
kubectl exec vscode-nitro -- cat /home/coder/.config/code-server/config.yaml
```

Open http://localhost:8080 in your browser and sign in with the password. You now have VS Code and a terminal inside the sandbox. If another process uses local port 8080, choose another port. For example, run `kubectl port-forward pod/vscode-nitro 18080:8080`.

The example publishes no Service of type LoadBalancer, NodePort, or Ingress. Users outside the cluster cannot reach code-server through those resources. Inside the cluster, code-server listens on `0.0.0.0:8080`. Any other pod can reach the editor by the pod IP address. Password authentication still applies.

## Cleanup

Stop the port-forward with `Ctrl+C`, then delete the sandbox:

```shell
kubectl delete -f sandbox-nitro-eks.yaml
```

To remove the demo cluster entirely:

```shell
eksctl delete cluster --name nitro-sandbox-demo --region <REGION>
```

## Learn more

- [Amazon EKS documentation for Nitro Sandboxes](https://docs.aws.amazon.com/eks/latest/userguide/sandboxing.html)
- [AWS Nitro Sandbox Blueprints](https://aws-samples.github.io/sample-eks-nitro-sandbox) describes more Agent Sandbox examples on Amazon EKS, including warm pools, coding agents, storage, and EKS Pod Identity.
