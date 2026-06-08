$ErrorActionPreference = "Stop"

Write-Host "Starting Podman machine..."
podman machine stop podman-machine-default

podman machine start podman-machine-default

Write-Host "Using Podman provider for KinD..."
$env:KIND_EXPERIMENTAL_PROVIDER = "podman"

Write-Host "Deleting old MVD cluster if it exists..."
kind delete cluster -n mvd

Write-Host "Creating fresh MVD cluster..."
kind create cluster -n mvd

Write-Host "Checking node..."
kubectl get nodes

Write-Host "Switching to repo..."
cd "C:\Users\SEM\Documents\AM2Scale\MinimumViableDataspace"

Write-Host "Building local EDC launchers..."
.\gradlew.bat :launchers:controlplane:shadowJar :launchers:dataplane:shadowJar

Write-Host "Building local Controlplane image..."
podman build `
  -t mvd-controlplane-local:latest `
  -f .\launchers\controlplane\src\main\docker\Dockerfile `
  --build-arg JAR=launchers/controlplane/build/libs/controlplane.jar `
  .

Write-Host "Building local Dataplane image..."
podman build `
  -t mvd-dataplane-local:latest `
  -f .\launchers\dataplane\src\main\docker\Dockerfile `
  --build-arg JAR=launchers/dataplane/build/libs/dataplane.jar `
  .

Write-Host "Loading local images into KinD..."
podman save -o .\mvd-controlplane-local.tar localhost/mvd-controlplane-local:latest
podman save -o .\mvd-dataplane-local.tar localhost/mvd-dataplane-local:latest
kind load image-archive .\mvd-controlplane-local.tar --name mvd
kind load image-archive .\mvd-dataplane-local.tar --name mvd
Remove-Item .\mvd-controlplane-local.tar, .\mvd-dataplane-local.tar -ErrorAction SilentlyContinue

Write-Host "Updating Helm repo..."
helm repo add traefik https://traefik.github.io/charts --force-update
helm repo update

Write-Host "Installing Gateway API..."
kubectl apply --server-side --force-conflicts `
  -f https://github.com/kubernetes-sigs/gateway-api/releases/download/v1.4.1/experimental-install.yaml

Write-Host "Installing Traefik..."
helm upgrade --install --namespace traefik traefik traefik/traefik `
  --create-namespace `
  -f values.yaml

kubectl rollout status deployment/traefik -n traefik --timeout=180s

Write-Host "Deploying MVD..."
kubectl apply -k k8s

if (Test-Path ".\data\foto.png") {
  Write-Host "Deploying custom photo API for asset-3..."
  kubectl delete configmap custom-photo -n provider --ignore-not-found
  kubectl create configmap custom-photo -n provider --from-file=foto.png=.\data\foto.png
  kubectl apply -f .\k8s\custom-photo-api.yaml
} else {
  Write-Warning "data\foto.png not found. Skipping custom photo API for asset-3."
}

Write-Host "Waiting for deployments..."
kubectl wait -A `
  --for=condition=available deployment --all `
  --timeout=10m

Write-Host "Waiting for seed jobs..."
kubectl wait -A `
  --selector=type=edc-job `
  --for=condition=complete job --all `
  --timeout=15m

Write-Host "Final status:"
kubectl get deployments -A
kubectl get jobs -A
kubectl get pods -A

Write-Host ""
Write-Host "MVD is ready."
Write-Host "Now open an Administrator PowerShell and run:"
Write-Host "kubectl port-forward svc/traefik 80:80 -n traefik"
