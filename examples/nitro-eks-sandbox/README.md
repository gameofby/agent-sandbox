# AWS Nitro Sandbox on Amazon EKS

## Overview

This example runs VS Code in the browser ([code-server](https://github.com/coder/code-server)) inside an Agent Sandbox. The Agent Sandbox uses an [AWS Nitro Sandbox](https://docs.aws.amazon.com/eks/latest/userguide/sandboxing.html) on an [Amazon EKS Auto Mode](https://docs.aws.amazon.com/eks/latest/userguide/automode.html) cluster. AWS Nitro Sandbox starts selected pods in a lightweight VM with its own kernel and hardware isolation. Use `kubectl port-forward` to open code-server.

When a pod sets `runtimeClassName: isolated-sandbox`, AWS Nitro Sandbox starts a VM with its own kernel. The Nitro Hypervisor isolates the VM's CPU and memory. The pod keeps its containers, image, and spec. The kubelet still sees an ordinary pod. As a result, `kubectl exec`, `logs`, and `port-forward` work for this pod.

EKS Auto Mode provides the rest of the configuration. A new Auto Mode cluster includes the `isolated-sandbox` RuntimeClass. Auto Mode also launches a node for a sandboxed pod when the pod requests one. You do not need to create a node pool, install a DaemonSet, or register the RuntimeClass.

## Prerequisites

1. [Install](https://docs.aws.amazon.com/cli/latest/userguide/getting-started-install.html) the AWS CLI and configure it for your account.
2. [Install eksctl](https://eksctl.io/installation/) and [kubectl](https://kubernetes.io/docs/tasks/tools/).
3. Review the Nitro Sandbox requirements in the [Amazon EKS documentation](https://docs.aws.amazon.com/eks/latest/userguide/sandboxing.html).

## Step 1: Create an EKS Auto Mode cluster

> **Note:** this command creates billable AWS resources. It creates an EKS cluster, its VPC, and the EC2 instances that Auto Mode launches for your pods. See [Cleanup](#cleanup) to remove them.

```shell
eksctl create cluster --name nitro-sandbox-demo --region us-east-1 --version 1.37 --enable-auto-mode
```

Run this command to check the Nitro Sandbox runtime classes on the cluster:

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

Follow the [Installation Guide](../../README.md#installation) to install the Agent Sandbox controller. Then wait for the controller to become ready:

```shell
kubectl -n agent-sandbox-system rollout status deploy/agent-sandbox-controller
```

## Step 3: Deploy VS Code in an Agent Sandbox

The manifest below (`sandbox-nitro-eks.yaml`) defines a `Sandbox` that runs code-server and requests the `isolated-sandbox` RuntimeClass. That field is the only Nitro-specific value.

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
        ports:
        - containerPort: 8080
        resources:
          requests:
            cpu: "1"
            memory: 2Gi
```

Clone the repository and enter this example directory. Run these commands to apply the manifest and wait for the sandbox to become ready:

```shell
git clone https://github.com/kubernetes-sigs/agent-sandbox.git
cd agent-sandbox/examples/nitro-eks-sandbox
kubectl apply -f sandbox-nitro-eks.yaml
kubectl wait --for=condition=Ready sandbox/vscode-nitro --timeout=5m
kubectl get sandbox vscode-nitro
```

```text
NAME           READY   REASON              AGE
vscode-nitro   True    DependenciesReady   25s
```

## Step 4: Verify the isolation

Run these commands to compare the kernel inside the sandbox with the kernel on the node:

```shell
# Kernel inside the sandbox (the Nitro Sandbox's own kernel)
kubectl exec vscode-nitro -- uname -r

# Kernel on the node hosting the sandbox
SANDBOX_NODE="$(kubectl get pod vscode-nitro -o jsonpath='{.spec.nodeName}')"
kubectl get node "${SANDBOX_NODE}" -o jsonpath='{.status.nodeInfo.kernelVersion}'
```

```text
6.18.54
6.18.56
```

Read the two kernel versions in the command output. A different version shows that the sandbox boots its own kernel. Run these commands to compare the sandbox uptime with the node uptime:

```shell
# Uptime inside the sandbox
kubectl exec vscode-nitro -- cat /proc/uptime

# Uptime of the node hosting the sandbox
kubectl debug node/"${SANDBOX_NODE}" \
  --image=busybox:1.36 \
  --profile=sysadmin \
  -- chroot /host cat /proc/uptime

# Product name reported by the sandbox VM
kubectl exec vscode-nitro -- cat /sys/class/dmi/id/product_name
```

```text
45.59 43.62
45983.17 183927.40
m8a.enclave
```

The first number in each uptime output is the number of seconds since that system booted. The sandbox value starts when AWS Nitro Sandbox starts the VM. The node value starts when the node boots. Compare the two values. Different values show separate boot times. When `kubectl debug` prints the name of the debug pod, delete that pod.

## Step 5: Open VS Code

Run this command to forward a local port to the sandbox pod. The pod has the same name as the `Sandbox`:

```shell
kubectl port-forward pod/vscode-nitro 8080:8080
```

Run this command in another terminal to read the password that code-server generated:

```shell
kubectl exec vscode-nitro -- cat /home/coder/.config/code-server/config.yaml
```

Open http://localhost:8080 in your browser. Sign in with the password. You now have VS Code and a terminal inside the sandbox. If port 8080 is already in use on your machine, choose another local port. For example, run `kubectl port-forward pod/vscode-nitro 18080:8080`.

The example does not create a Service of type LoadBalancer, a NodePort, or an Ingress. Users outside the cluster cannot reach code-server through those resources. Because code-server listens on `0.0.0.0:8080`, other pods can connect to the pod IP. Password authentication still applies. Add a NetworkPolicy if the sandbox must accept connections only from the `kubectl port-forward` session.

## Cleanup

Stop the port-forward with `Ctrl+C`. Then run this command to delete the sandbox:

```shell
kubectl delete -f sandbox-nitro-eks.yaml
```

Run this command to remove the demo cluster:

```shell
eksctl delete cluster --name nitro-sandbox-demo --region us-east-1
```

## Learn more

- [Amazon EKS documentation for Nitro Sandboxes](https://docs.aws.amazon.com/eks/latest/userguide/sandboxing.html)
- [AWS Nitro Sandbox Blueprints](https://aws-samples.github.io/sample-eks-nitro-sandbox): more Agent Sandbox examples on Amazon EKS, including warm pools, coding agents, storage, and EKS Pod Identity.
