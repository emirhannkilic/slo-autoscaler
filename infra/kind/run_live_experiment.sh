#!/usr/bin/env bash
# Run one live autoscaling experiment on an ephemeral kind cluster.
#
#   bash infra/kind/run_live_experiment.sh <policy> <output_dir>
#     policy      : hpa | predictive
#     output_dir  : where CSV/JSON/diagnostics are written
#
# Fails fast on missing tools or a stalled rollout. Collects diagnostics and
# deletes the cluster on EVERY exit -- never relies on a later CI step.

set -euo pipefail

POLICY="${1:?usage: run_live_experiment.sh <hpa|predictive> <output_dir>}"
OUTPUT_DIR="${2:?usage: run_live_experiment.sh <hpa|predictive> <output_dir>}"
CLUSTER_NAME="autoscaler-lab"
IMAGE="autoscaler-load-target:ci"
METRICS_SERVER_VERSION="v0.7.2"
NAMESPACE="default"
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
KIND_DIR="${REPO_ROOT}/infra/kind"
POLL_SECONDS=15

case "$POLICY" in
  hpa|predictive) ;;
  *) echo "unknown policy: $POLICY (expected hpa or predictive)" >&2; exit 2 ;;
esac

mkdir -p "$OUTPUT_DIR"
CONTROLLER_PID=""

require() {
  command -v "$1" >/dev/null 2>&1 || { echo "missing required tool: $1" >&2; exit 3; }
}

collect_and_cleanup() {
  local code=$?
  echo "--- collecting diagnostics (exit $code) ---"
  [[ -n "$CONTROLLER_PID" ]] && kill "$CONTROLLER_PID" 2>/dev/null || true
  {
    kubectl get deployment,pods,hpa -o wide -n "$NAMESPACE" || true
    echo "=== events ==="
    kubectl get events --sort-by=.lastTimestamp -n "$NAMESPACE" || true
  } > "$OUTPUT_DIR/k8s_state.txt" 2>&1 || true
  kubectl logs -l app=load-target --tail=500 -n "$NAMESPACE" \
    > "$OUTPUT_DIR/pod_logs.txt" 2>&1 || true
  kubectl describe hpa load-target -n "$NAMESPACE" \
    > "$OUTPUT_DIR/hpa_describe.txt" 2>&1 || true
  kind delete cluster --name "$CLUSTER_NAME" || true
  echo "--- cleanup done ---"
  exit "$code"
}
trap collect_and_cleanup EXIT

require kind
require docker
require kubectl
require locust

echo "--- creating cluster ---"
kind create cluster --name "$CLUSTER_NAME" --config "${KIND_DIR}/cluster.yaml" --wait 120s

echo "--- building and loading image ---"
docker build -t "$IMAGE" -f "${REPO_ROOT}/service/Dockerfile" "$REPO_ROOT"
kind load docker-image "$IMAGE" --name "$CLUSTER_NAME"

echo "--- installing metrics-server ${METRICS_SERVER_VERSION} ---"
kubectl apply -f "https://github.com/kubernetes-sigs/metrics-server/releases/download/${METRICS_SERVER_VERSION}/components.yaml"
kubectl patch deployment metrics-server -n kube-system --type=json -p \
  '[{"op":"add","path":"/spec/template/spec/containers/0/args/-","value":"--kubelet-insecure-tls"}]'
kubectl rollout status deployment/metrics-server -n kube-system --timeout=120s

echo "--- applying manifests ---"
kubectl apply -f "${KIND_DIR}/deployment.yaml"
kubectl apply -f "${KIND_DIR}/service.yaml"
if [[ "$POLICY" == "hpa" ]]; then
  kubectl apply -f "${KIND_DIR}/hpa.yaml"
fi
kubectl rollout status deployment/load-target -n "$NAMESPACE" --timeout=120s

if [[ "$POLICY" == "predictive" ]]; then
  echo "--- starting predictive controller ---"
  python3 -m autoscaler_lab.controller \
    --namespace "$NAMESPACE" --deployment load-target --selector app=load-target \
    --interval "$POLL_SECONDS" \
    --output "$OUTPUT_DIR/controller.jsonl" &
  CONTROLLER_PID=$!
fi

echo "--- polling replicas every ${POLL_SECONDS}s ---"
echo "timestamp,replicas,cpu_millicores_total" > "$OUTPUT_DIR/replicas.csv"
poll_replicas() {
  set +e  # a failed kubectl call must not kill this background loop
  while true; do
    ts="$(date -u +%FT%TZ)"
    replicas="$(kubectl get deployment load-target -n "$NAMESPACE" \
      -o jsonpath='{.status.replicas}' 2>/dev/null)"
    cpu="$(kubectl top pods -l app=load-target -n "$NAMESPACE" --no-headers 2>/dev/null \
      | awk '{gsub(/m/,"",$2); s+=$2} END {print s+0}')"
    echo "${ts},${replicas:-0},${cpu:-0}" >> "$OUTPUT_DIR/replicas.csv"
    sleep "$POLL_SECONDS"
  done
}
poll_replicas &
POLL_PID=$!

echo "--- running locust (4 cycles x 4 x 90s stages = 24m) ---"
locust -f "${REPO_ROOT}/experiments/locustfile.py" --headless \
  --host http://localhost:18080 \
  --csv "$OUTPUT_DIR/locust" \
  --run-time 25m --stop-timeout 10 || true

kill "$POLL_PID" 2>/dev/null || true
[[ -n "$CONTROLLER_PID" ]] && kill "$CONTROLLER_PID" 2>/dev/null || true
CONTROLLER_PID=""

echo "--- acceptance checks ---"
test -s "$OUTPUT_DIR/locust_stats.csv"

if [[ "$POLICY" == "hpa" ]]; then
  test -s "$OUTPUT_DIR/replicas.csv"
  awk -F, 'NR > 1 && $2 > 1 {found=1} END {exit !found}' "$OUTPUT_DIR/replicas.csv" \
    || { echo "HPA never scaled above one replica" >&2; exit 4; }
else
  # the predictive controller records active_replicas itself
  test -s "$OUTPUT_DIR/controller.jsonl"
  grep -q '"active_replicas": [2-9]' "$OUTPUT_DIR/controller.jsonl" \
    || { echo "predictive controller never scaled above one replica" >&2; exit 4; }
  non_fallback="$(grep -c '"fallback_used": false' "$OUTPUT_DIR/controller.jsonl" || true)"
  echo "controller ticks with a trained model: ${non_fallback}"
  [[ "${non_fallback:-0}" -ge 20 ]] \
    || { echo "predictive run had <20 non-fallback decisions -- model never warmed up" >&2; exit 5; }
fi

echo "--- experiment ok ---"
