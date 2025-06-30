// Builds inventory-api, pushes the image to ECR and deploys it with Helm.
//
// Needs on the agent: docker, helm, the AWS CLI. Jenkins credentials:
//   aws-ci          AWS credentials (AWS Credentials plugin) that can push to ECR
//   kubeconfig-dev  secret file: kubeconfig for the dev cluster
// and a global environment variable AWS_ACCOUNT_ID.

pipeline {
  agent any

  options {
    timestamps()
    disableConcurrentBuilds()
    buildDiscarder(logRotator(numToKeepStr: '30'))
    timeout(time: 45, unit: 'MINUTES')
  }

  environment {
    AWS_REGION   = 'ap-south-1'
    ECR_REGISTRY = "${env.AWS_ACCOUNT_ID}.dkr.ecr.ap-south-1.amazonaws.com"
    IMAGE        = "${ECR_REGISTRY}/inventory-api"
    CHART        = 'chart/inventory-api'
  }

  stages {
    stage('Test') {
      steps {
        sh '''
          python3 -m venv .venv
          . .venv/bin/activate
          pip install --quiet -r app/requirements.txt -r app/requirements-dev.txt
          cd app
          ruff check .
          python -m pytest -q
        '''
      }
    }

    stage('Lint chart') {
      steps {
        sh '''
          for env in dev prod; do
            helm lint "$CHART" -f "deploy/values-$env.yaml"
          done
        '''
      }
    }

    stage('Build image') {
      steps {
        script {
          env.IMAGE_TAG = sh(script: 'git rev-parse --short=12 HEAD', returnStdout: true).trim()
        }
        sh 'docker build --pull --build-arg APP_VERSION="$IMAGE_TAG" -t "$IMAGE:$IMAGE_TAG" .'
      }
    }

    stage('Push to ECR') {
      when { branch 'main' }
      steps {
        withCredentials([[$class: 'AmazonWebServicesCredentialsBinding', credentialsId: 'aws-ci']]) {
          sh '''
            aws ecr get-login-password --region "$AWS_REGION" \
              | docker login --username AWS --password-stdin "$ECR_REGISTRY"
            docker push "$IMAGE:$IMAGE_TAG"
          '''
        }
      }
    }

    stage('Deploy to dev') {
      when { branch 'main' }
      steps {
        withCredentials([file(credentialsId: 'kubeconfig-dev', variable: 'KUBECONFIG')]) {
          // --atomic rolls the release back if the new pods never become ready.
          sh '''
            helm upgrade --install inventory-api "$CHART" \
              --namespace inventory --create-namespace \
              -f deploy/values-dev.yaml \
              --set image.repository="$IMAGE" \
              --set image.tag="$IMAGE_TAG" \
              --atomic --wait --timeout 5m
          '''
        }
      }
    }
  }

  post {
    always {
      sh 'if [ -n "$IMAGE_TAG" ]; then docker image rm "$IMAGE:$IMAGE_TAG" || true; fi'
    }
  }
}
