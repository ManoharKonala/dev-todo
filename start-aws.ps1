# start-aws.ps1
Write-Host "========================================="
Write-Host "Starting TodoFlow AWS Deployment..."
Write-Host "========================================="

# Configuration
$AWS_REGION = "ap-south-1"
$AWS_ACCOUNT_ID = "588738615324" # Account ID from Jenkinsfile
$ECR_REGISTRY = "${AWS_ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com"
$IMAGE_NAME = "todoflow"

# 1. Start Minikube if not running
Write-Host "`n[1/6] Checking Minikube status..."
$minikubeStatus = (minikube status --format='{{.Host}}' 2>$null)
if ($minikubeStatus -ne "Running") {
    Write-Host "Starting Minikube..."
    minikube start
}

# 2. Run Terraform via Docker (since local terraform is not installed)
Write-Host "`n[2/6] Provisioning AWS ECR with Terraform..."
docker run --rm -v "${PWD}/terraform:/workspace" -v "${HOME}/.aws:/root/.aws" -w /workspace hashicorp/terraform:1.8 init
docker run --rm -v "${PWD}/terraform:/workspace" -v "${HOME}/.aws:/root/.aws" -w /workspace hashicorp/terraform:1.8 apply -auto-approve

# 3. Authenticate with AWS ECR via Dockerized AWS CLI
Write-Host "`n[3/6] Authenticating with AWS ECR..."
docker run --rm -v "${HOME}/.aws:/root/.aws" amazon/aws-cli ecr get-login-password --region $AWS_REGION | docker login --username AWS --password-stdin $ECR_REGISTRY

# 4. Build Docker Image
Write-Host "`n[4/6] Building Docker Image..."
$GIT_COMMIT = (git rev-parse --short HEAD 2>$null)
if (-not $GIT_COMMIT) { $GIT_COMMIT = "local" }
$BUILD_TAG = "local-${GIT_COMMIT}"

docker build --build-arg BUILD_NUMBER=$BUILD_TAG --build-arg DEPLOY_COLOR=green -t ${IMAGE_NAME}:${BUILD_TAG} .

# 5. Push to AWS ECR
Write-Host "`n[5/6] Pushing to AWS ECR..."
docker tag ${IMAGE_NAME}:${BUILD_TAG} ${ECR_REGISTRY}/${IMAGE_NAME}:${BUILD_TAG}
docker tag ${IMAGE_NAME}:${BUILD_TAG} ${ECR_REGISTRY}/${IMAGE_NAME}:green-latest

docker push ${ECR_REGISTRY}/${IMAGE_NAME}:${BUILD_TAG}
docker push ${ECR_REGISTRY}/${IMAGE_NAME}:green-latest

# 6. Deploy to Minikube using Kubernetes manifests
Write-Host "`n[6/6] Deploying to Kubernetes (DEV namespace)..."
$tempDeployFile = "k8s/deployment-green-temp.yaml"
(Get-Content k8s/deployment-green.yaml) -replace "IMAGE_TAG", $BUILD_TAG | Set-Content $tempDeployFile

kubectl apply -f k8s/namespace-dev.yaml
kubectl apply -f k8s/configmap-dev.yaml -n todoflow-dev
kubectl apply -f $tempDeployFile -n todoflow-dev
kubectl apply -f k8s/service.yaml -n todoflow-dev

Write-Host "Waiting for deployment to become ready..."
kubectl rollout status deployment/todoflow-green -n todoflow-dev --timeout=120s

Remove-Item $tempDeployFile

Write-Host "`n========================================="
Write-Host "Deployment Complete!"
Write-Host "Access the app with this URL:"
minikube service todoflow-svc -n todoflow-dev --url
Write-Host "========================================="
