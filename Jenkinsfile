pipeline {
  agent none

  environment {
    DOCKER_IMAGE       = "manohar122/todoflow"
    AWS_REGION         = "ap-south-1"
    ECR_REGISTRY       = "588738615324.dkr.ecr.ap-south-1.amazonaws.com"
    PROMETHEUS_URL     = "http://host.docker.internal:9090"
    K8S_NAMESPACE_DEV  = "todoflow-dev"
    K8S_NAMESPACE_PROD = "todoflow-prod"
    BLUE_WEIGHT        = "90"
    GREEN_WEIGHT       = "10"
  }

  stages {

    // ──────────────────────────────────────────────────────────────
    // Stage 1: Checkout source code and tag the build
    // ──────────────────────────────────────────────────────────────
    stage('Checkout') {
      agent { docker { image 'alpine/git:latest' } }
      steps {
        git branch: 'main', url: 'https://github.com/ManoharKonala/dev-todo'
        script {
          env.GIT_COMMIT_SHORT = sh(script: "git rev-parse --short HEAD", returnStdout: true).trim()
          env.BUILD_TAG = "${BUILD_NUMBER}-${env.GIT_COMMIT_SHORT}"
        }
      }
    }

    // ──────────────────────────────────────────────────────────────
    // Stage 2: Pre-deploy health gate — query Prometheus BEFORE deploy
    //          Refuse to deploy if current env is already degraded
    // ──────────────────────────────────────────────────────────────
    stage('Pre-deploy health gate') {
      agent { docker { image 'curlimages/curl:latest' } }
      steps {
        script {
          def errorRate = sh(
            script: """
              curl -sf '${PROMETHEUS_URL}/api/v1/query' \
                --data-urlencode 'query=rate(http_requests_total{status=~"5.."}[5m])' \
              | python3 -c "import sys,json; d=json.load(sys.stdin); v=d['data']['result']; print(float(v[0]['value'][1]) if v else 0)"
            """,
            returnStdout: true
          ).trim().toFloat()
          if (errorRate > 0.05) {
            error("Pre-deploy gate FAILED: current error rate ${errorRate} > 5%. Fix live issues before deploying.")
          }
          echo "Pre-deploy gate PASSED: error rate ${errorRate}"
        }
      }
    }

    // ──────────────────────────────────────────────────────────────
    // Stage 3: Run unit tests with pytest
    // ──────────────────────────────────────────────────────────────
    stage('Test') {
      agent { docker { image 'python:3.11-slim' } }
      steps {
        sh 'pip install -r app/requirements.txt -q'
        sh 'pytest tests/ -v --tb=short --junit-xml=test-results.xml'
      }
      post {
        always {
          junit 'test-results.xml'
        }
      }
    }

    // ──────────────────────────────────────────────────────────────
    // Stage 4: Static Application Security Testing (SAST) — Bandit
    // ──────────────────────────────────────────────────────────────
    stage('SAST — Bandit') {
      agent { docker { image 'python:3.11-slim' } }
      steps {
        sh 'pip install bandit -q'
        sh 'bandit -r app/ -ll -f json -o bandit-report.json || true'
        sh '''
          HIGH=$(python3 -c "import json; d=json.load(open('bandit-report.json')); print(len([i for i in d['results'] if i['issue_severity']=='HIGH']))")
          echo "HIGH severity issues: $HIGH"
          if [ "$HIGH" -gt "0" ]; then exit 1; fi
        '''
      }
    }

    // ──────────────────────────────────────────────────────────────
    // Stage 5: Docker multi-stage build with cache optimization
    // ──────────────────────────────────────────────────────────────
    stage('Docker build') {
      agent any
      steps {
        sh """
          docker build \
            --build-arg BUILD_NUMBER=${BUILD_TAG} \
            --build-arg DEPLOY_COLOR=green \
            --cache-from ${DOCKER_IMAGE}:latest \
            -t ${DOCKER_IMAGE}:${BUILD_TAG} \
            -t ${DOCKER_IMAGE}:green-latest \
            .
        """
      }
    }

    // ──────────────────────────────────────────────────────────────
    // Stage 6: Container image vulnerability scanning — Trivy
    // ──────────────────────────────────────────────────────────────
    stage('Trivy scan') {
      agent any
      steps {
        sh """
          which trivy || (curl -sfL https://raw.githubusercontent.com/aquasecurity/trivy/main/contrib/install.sh | sh -s -- -b /usr/local/bin)
          trivy image \
            --exit-code 1 \
            --severity HIGH,CRITICAL \
            --no-progress \
            --format table \
            ${DOCKER_IMAGE}:${BUILD_TAG}
        """
      }
    }

    // ──────────────────────────────────────────────────────────────
    // Stage 7: Push image to AWS ECR
    // ──────────────────────────────────────────────────────────────
    stage('Push to ECR') {
      agent any
      steps {
        withCredentials([[$class: 'AmazonWebServicesCredentialsBinding', credentialsId: 'aws-credentials']]) {
          sh """
            aws ecr get-login-password --region ${AWS_REGION} \
              | docker login --username AWS --password-stdin ${ECR_REGISTRY}
            docker tag ${DOCKER_IMAGE}:${BUILD_TAG} ${ECR_REGISTRY}/todoflow:${BUILD_TAG}
            docker tag ${DOCKER_IMAGE}:${BUILD_TAG} ${ECR_REGISTRY}/todoflow:green-latest
            docker push ${ECR_REGISTRY}/todoflow:${BUILD_TAG}
            docker push ${ECR_REGISTRY}/todoflow:green-latest
          """
        }
      }
    }

    // ──────────────────────────────────────────────────────────────
    // Stage 8: Terraform — infrastructure provisioning check
    // ──────────────────────────────────────────────────────────────
    stage('Terraform — infra check') {
      agent { docker { image 'hashicorp/terraform:1.8' } }
      steps {
        dir('terraform') {
          sh 'terraform init -input=false'
          sh 'terraform plan -detailed-exitcode -input=false || true'
          sh 'terraform apply -auto-approve -input=false'
        }
      }
    }

    // ──────────────────────────────────────────────────────────────
    // Stage 9: Deploy green to DEV namespace
    // ──────────────────────────────────────────────────────────────
    stage('Deploy to DEV (green)') {
      agent any
      steps {
        sh """
          sed -i "s|IMAGE_TAG|${BUILD_TAG}|g" k8s/deployment-green.yaml
          kubectl apply -f k8s/namespace-dev.yaml
          kubectl apply -f k8s/configmap-dev.yaml -n ${K8S_NAMESPACE_DEV}
          kubectl apply -f k8s/deployment-green.yaml -n ${K8S_NAMESPACE_DEV}
          kubectl rollout status deployment/todoflow-green -n ${K8S_NAMESPACE_DEV} --timeout=120s
        """
      }
    }

    // ──────────────────────────────────────────────────────────────
    // Stage 10: Automated rollback gate
    //           Wait 90s then query Prometheus — if error rate
    //           elevated, auto-rollback and fail the build
    // ──────────────────────────────────────────────────────────────
    stage('Automated rollback gate') {
      agent { docker { image 'curlimages/curl:latest' } }
      steps {
        script {
          echo "Waiting 90 seconds for metrics to stabilise..."
          sleep(90)
          def errorRate = sh(
            script: """
              curl -sf '${PROMETHEUS_URL}/api/v1/query' \
                --data-urlencode 'query=rate(http_requests_total{status=~"5..", deploy_color="green"}[1m])' \
              | python3 -c "import sys,json; d=json.load(sys.stdin); v=d['data']['result']; print(float(v[0]['value'][1]) if v else 0)"
            """,
            returnStdout: true
          ).trim().toFloat()

          if (errorRate > 0.01) {
            echo "ERROR RATE ${errorRate} EXCEEDS THRESHOLD — initiating auto-rollback"
            sh "bash scripts/rollback.sh ${K8S_NAMESPACE_DEV}"
            error("Deployment automatically rolled back. Error rate: ${errorRate}")
          }
          echo "Rollback gate PASSED: error rate ${errorRate}. Green deployment is healthy."
        }
      }
    }

    // ──────────────────────────────────────────────────────────────
    // Stage 11: Human-in-the-loop — manual prod promotion approval
    // ──────────────────────────────────────────────────────────────
    stage('Promote to PROD — manual approval') {
      agent none
      steps {
        timeout(time: 30, unit: 'MINUTES') {
          input message: "Green deployment is healthy in DEV. Promote to PROD?",
                ok: "Promote to production",
                submitter: "admin"
        }
      }
    }

    // ──────────────────────────────────────────────────────────────
    // Stage 12: Deploy to PROD — blue-green atomic cutover
    // ──────────────────────────────────────────────────────────────
    stage('Deploy to PROD — blue-green cutover') {
      agent any
      steps {
        sh """
          kubectl apply -f k8s/namespace-prod.yaml
          kubectl apply -f k8s/configmap-prod.yaml -n ${K8S_NAMESPACE_PROD}
          kubectl apply -f k8s/deployment-green.yaml -n ${K8S_NAMESPACE_PROD}
          kubectl rollout status deployment/todoflow-green -n ${K8S_NAMESPACE_PROD} --timeout=120s
          # Switch service selector from blue to green (atomic cutover)
          bash scripts/promote.sh ${K8S_NAMESPACE_PROD} green
          echo "Traffic switched to GREEN. Blue is now idle (instant rollback available)."
        """
      }
    }

    // ──────────────────────────────────────────────────────────────
    // Stage 13: Post-deploy health verification
    // ──────────────────────────────────────────────────────────────
    stage('Post-deploy health check') {
      agent { docker { image 'curlimages/curl:latest' } }
      steps {
        retry(3) {
          sh '''
            sleep 10
            curl -f http://$(minikube ip):30080/health
            curl -f http://$(minikube ip):30080/version
          '''
        }
      }
    }
  }

  post {
    success {
      echo "Pipeline SUCCESS — build ${BUILD_TAG} promoted to production on GREEN"
      echo "Blue deployment remains idle for instant rollback"
    }
    failure {
      echo "Pipeline FAILED — running auto-rollback"
      sh 'bash scripts/rollback.sh todoflow-dev || true'
      sh 'bash scripts/rollback.sh todoflow-prod || true'
    }
    always {
      echo "Build duration: ${currentBuild.durationString}"
    }
  }
}
