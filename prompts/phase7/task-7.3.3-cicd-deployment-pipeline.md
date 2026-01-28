# Task 7.3.3: CI/CD - Deployment Pipeline

## Context

You are setting up CI/CD for ASWA at `/.github/workflows/`. Testing pipelines are complete. Now we need deployment pipelines for all environments.

## Objective

Create deployment pipelines that:
1. Deploy to staging automatically
2. Support production deployments with approval
3. Implement rollback capabilities
4. Handle database migrations
5. Provide deployment notifications

## Requirements

### 1. Create `/.github/workflows/deploy-staging.yaml`
```yaml
name: Deploy to Staging

on:
  push:
    branches: [main]
  workflow_dispatch:

permissions:
  contents: read
  packages: write
  id-token: write

concurrency:
  group: staging-deployment
  cancel-in-progress: false

jobs:
  build:
    name: Build Images
    uses: ./.github/workflows/build-images.yaml
    with:
      environment: staging
      tag: staging-${{ github.sha }}
    secrets: inherit

  deploy:
    name: Deploy to Staging
    runs-on: ubuntu-latest
    needs: build
    environment:
      name: staging
      url: https://app.staging.aswa.io
    steps:
      - uses: actions/checkout@v4

      - name: Configure AWS credentials
        uses: aws-actions/configure-aws-credentials@v4
        with:
          role-to-assume: ${{ secrets.AWS_ROLE_ARN_STAGING }}
          aws-region: us-east-1

      - name: Set up kubectl
        uses: azure/setup-kubectl@v4
        with:
          version: 'v1.28.0'

      - name: Configure kubectl
        run: |
          aws eks update-kubeconfig --name aswa-staging --region us-east-1

      - name: Run database migrations
        run: |
          kubectl run migration-${{ github.run_id }} \
            --namespace aswa-staging \
            --image=${{ needs.build.outputs.images.api-gateway }} \
            --restart=Never \
            --env="DATABASE_URL=${{ secrets.DATABASE_URL }}" \
            --command -- python -m alembic upgrade head

          kubectl wait --for=condition=complete \
            --timeout=300s \
            job/migration-${{ github.run_id }} \
            -n aswa-staging

      - name: Deploy with Helm
        run: |
          helm upgrade --install aswa infrastructure/helm/charts/aswa \
            --namespace aswa-staging \
            --create-namespace \
            --values infrastructure/helm/charts/aswa/values-staging.yaml \
            --set image.tag=staging-${{ github.sha }} \
            --set apiGateway.image.tag=staging-${{ github.sha }} \
            --set ingestionService.image.tag=staging-${{ github.sha }} \
            --set queryService.image.tag=staging-${{ github.sha }} \
            --set insightService.image.tag=staging-${{ github.sha }} \
            --set webDashboard.image.tag=staging-${{ github.sha }} \
            --wait \
            --timeout 10m

      - name: Verify deployment
        run: |
          kubectl rollout status deployment/aswa-api-gateway -n aswa-staging --timeout=300s
          kubectl rollout status deployment/aswa-ingestion -n aswa-staging --timeout=300s
          kubectl rollout status deployment/aswa-query -n aswa-staging --timeout=300s
          kubectl rollout status deployment/aswa-insight -n aswa-staging --timeout=300s
          kubectl rollout status deployment/aswa-web -n aswa-staging --timeout=300s

      - name: Run smoke tests
        run: |
          # Wait for services to be ready
          sleep 30

          # Test health endpoints
          API_URL="https://api.staging.aswa.io"

          response=$(curl -s -o /dev/null -w "%{http_code}" "$API_URL/health")
          if [ "$response" != "200" ]; then
            echo "Health check failed with status $response"
            exit 1
          fi

          echo "Smoke tests passed"

      - name: Notify on failure
        if: failure()
        uses: slackapi/slack-github-action@v1
        with:
          channel-id: ${{ secrets.SLACK_CHANNEL_DEPLOYMENTS }}
          payload: |
            {
              "text": "🚨 Staging deployment failed",
              "blocks": [
                {
                  "type": "section",
                  "text": {
                    "type": "mrkdwn",
                    "text": "*Staging Deployment Failed*\n\nWorkflow: ${{ github.workflow }}\nCommit: ${{ github.sha }}\nActor: ${{ github.actor }}\n\n<${{ github.server_url }}/${{ github.repository }}/actions/runs/${{ github.run_id }}|View Workflow>"
                  }
                }
              ]
            }
        env:
          SLACK_BOT_TOKEN: ${{ secrets.SLACK_BOT_TOKEN }}

  e2e-tests:
    name: E2E Tests
    needs: deploy
    uses: ./.github/workflows/e2e-tests.yaml
    with:
      environment: staging
    secrets: inherit

  notify:
    name: Notify Success
    runs-on: ubuntu-latest
    needs: [deploy, e2e-tests]
    if: success()
    steps:
      - name: Send Slack notification
        uses: slackapi/slack-github-action@v1
        with:
          channel-id: ${{ secrets.SLACK_CHANNEL_DEPLOYMENTS }}
          payload: |
            {
              "text": "✅ Staging deployment successful",
              "blocks": [
                {
                  "type": "section",
                  "text": {
                    "type": "mrkdwn",
                    "text": "*Staging Deployment Successful*\n\nVersion: staging-${{ github.sha }}\nActor: ${{ github.actor }}\n\n<https://app.staging.aswa.io|Open Staging> | <${{ github.server_url }}/${{ github.repository }}/actions/runs/${{ github.run_id }}|View Workflow>"
                  }
                }
              ]
            }
        env:
          SLACK_BOT_TOKEN: ${{ secrets.SLACK_BOT_TOKEN }}
```

### 2. Create `/.github/workflows/deploy-production.yaml`
```yaml
name: Deploy to Production

on:
  workflow_dispatch:
    inputs:
      version:
        description: 'Version to deploy (e.g., v1.2.3)'
        required: true
      skip_e2e:
        description: 'Skip E2E tests (emergency only)'
        type: boolean
        default: false

permissions:
  contents: read
  packages: write
  id-token: write

concurrency:
  group: production-deployment
  cancel-in-progress: false

jobs:
  validate:
    name: Validate Version
    runs-on: ubuntu-latest
    outputs:
      image_tag: ${{ steps.validate.outputs.image_tag }}
    steps:
      - uses: actions/checkout@v4

      - name: Validate version format
        id: validate
        run: |
          VERSION="${{ github.event.inputs.version }}"

          # Validate version format
          if ! [[ "$VERSION" =~ ^v[0-9]+\.[0-9]+\.[0-9]+(-[a-zA-Z0-9]+)?$ ]]; then
            echo "Invalid version format: $VERSION"
            echo "Expected format: v1.2.3 or v1.2.3-rc1"
            exit 1
          fi

          echo "image_tag=$VERSION" >> $GITHUB_OUTPUT

      - name: Check image exists
        run: |
          docker manifest inspect ghcr.io/${{ github.repository_owner }}/aswa/api-gateway:${{ steps.validate.outputs.image_tag }}

  approval:
    name: Approval Gate
    runs-on: ubuntu-latest
    needs: validate
    environment:
      name: production-approval
    steps:
      - name: Approval received
        run: echo "Deployment approved"

  create-backup:
    name: Create Backup
    runs-on: ubuntu-latest
    needs: approval
    steps:
      - uses: actions/checkout@v4

      - name: Configure AWS credentials
        uses: aws-actions/configure-aws-credentials@v4
        with:
          role-to-assume: ${{ secrets.AWS_ROLE_ARN_PROD }}
          aws-region: us-east-1

      - name: Set up kubectl
        uses: azure/setup-kubectl@v4
        with:
          version: 'v1.28.0'

      - name: Configure kubectl
        run: |
          aws eks update-kubeconfig --name aswa-prod --region us-east-1

      - name: Create database backup
        run: |
          # Trigger backup job
          kubectl create job db-backup-${{ github.run_id }} \
            --from=cronjob/volume-backup \
            -n aswa-prod

          # Wait for backup to complete
          kubectl wait --for=condition=complete \
            --timeout=600s \
            job/db-backup-${{ github.run_id }} \
            -n aswa-prod

          echo "Database backup completed"

      - name: Record current version
        id: current
        run: |
          CURRENT_VERSION=$(kubectl get deployment aswa-api-gateway \
            -n aswa-prod \
            -o jsonpath='{.spec.template.spec.containers[0].image}' | \
            cut -d: -f2)

          echo "current_version=$CURRENT_VERSION" >> $GITHUB_OUTPUT
          echo "Current version: $CURRENT_VERSION"

    outputs:
      current_version: ${{ steps.current.outputs.current_version }}

  deploy:
    name: Deploy to Production
    runs-on: ubuntu-latest
    needs: [validate, create-backup]
    environment:
      name: production
      url: https://app.aswa.io
    steps:
      - uses: actions/checkout@v4

      - name: Configure AWS credentials
        uses: aws-actions/configure-aws-credentials@v4
        with:
          role-to-assume: ${{ secrets.AWS_ROLE_ARN_PROD }}
          aws-region: us-east-1

      - name: Set up kubectl
        uses: azure/setup-kubectl@v4
        with:
          version: 'v1.28.0'

      - name: Configure kubectl
        run: |
          aws eks update-kubeconfig --name aswa-prod --region us-east-1

      - name: Run database migrations
        run: |
          kubectl run migration-${{ github.run_id }} \
            --namespace aswa-prod \
            --image=ghcr.io/${{ github.repository_owner }}/aswa/api-gateway:${{ needs.validate.outputs.image_tag }} \
            --restart=Never \
            --env="DATABASE_URL=${{ secrets.DATABASE_URL }}" \
            --command -- python -m alembic upgrade head

          kubectl wait --for=condition=complete \
            --timeout=300s \
            pod/migration-${{ github.run_id }} \
            -n aswa-prod

      - name: Deploy with Helm (Canary)
        run: |
          # Deploy canary (10% traffic)
          helm upgrade --install aswa-canary infrastructure/helm/charts/aswa \
            --namespace aswa-prod \
            --values infrastructure/helm/charts/aswa/values-prod.yaml \
            --set image.tag=${{ needs.validate.outputs.image_tag }} \
            --set apiGateway.replicaCount=1 \
            --set ingestionService.replicaCount=1 \
            --set queryService.replicaCount=1 \
            --set insightService.replicaCount=1 \
            --set nameOverride=aswa-canary \
            --wait \
            --timeout 10m

      - name: Verify canary deployment
        run: |
          kubectl rollout status deployment/aswa-canary-api-gateway -n aswa-prod --timeout=300s

          # Health check
          sleep 30
          response=$(curl -s -o /dev/null -w "%{http_code}" "https://api.aswa.io/health")
          if [ "$response" != "200" ]; then
            echo "Canary health check failed"
            exit 1
          fi

      - name: Promote to full deployment
        run: |
          helm upgrade --install aswa infrastructure/helm/charts/aswa \
            --namespace aswa-prod \
            --values infrastructure/helm/charts/aswa/values-prod.yaml \
            --set image.tag=${{ needs.validate.outputs.image_tag }} \
            --wait \
            --timeout 15m

          # Remove canary
          helm uninstall aswa-canary -n aswa-prod || true

      - name: Verify full deployment
        run: |
          kubectl rollout status deployment/aswa-api-gateway -n aswa-prod --timeout=300s
          kubectl rollout status deployment/aswa-ingestion -n aswa-prod --timeout=300s
          kubectl rollout status deployment/aswa-query -n aswa-prod --timeout=300s
          kubectl rollout status deployment/aswa-insight -n aswa-prod --timeout=300s
          kubectl rollout status deployment/aswa-web -n aswa-prod --timeout=300s

  e2e-tests:
    name: Production E2E Tests
    needs: deploy
    if: ${{ github.event.inputs.skip_e2e != 'true' }}
    uses: ./.github/workflows/e2e-tests.yaml
    with:
      environment: production
    secrets: inherit

  notify-success:
    name: Notify Success
    runs-on: ubuntu-latest
    needs: [deploy, e2e-tests]
    if: success()
    steps:
      - name: Send Slack notification
        uses: slackapi/slack-github-action@v1
        with:
          channel-id: ${{ secrets.SLACK_CHANNEL_DEPLOYMENTS }}
          payload: |
            {
              "text": "🚀 Production deployment successful",
              "blocks": [
                {
                  "type": "section",
                  "text": {
                    "type": "mrkdwn",
                    "text": "*Production Deployment Successful*\n\nVersion: ${{ github.event.inputs.version }}\nActor: ${{ github.actor }}\nPrevious: ${{ needs.create-backup.outputs.current_version }}\n\n<https://app.aswa.io|Open Production> | <${{ github.server_url }}/${{ github.repository }}/actions/runs/${{ github.run_id }}|View Workflow>"
                  }
                }
              ]
            }
        env:
          SLACK_BOT_TOKEN: ${{ secrets.SLACK_BOT_TOKEN }}

  notify-failure:
    name: Notify Failure
    runs-on: ubuntu-latest
    needs: [deploy]
    if: failure()
    steps:
      - name: Send Slack notification
        uses: slackapi/slack-github-action@v1
        with:
          channel-id: ${{ secrets.SLACK_CHANNEL_DEPLOYMENTS }}
          payload: |
            {
              "text": "🚨 Production deployment failed - rollback may be needed",
              "blocks": [
                {
                  "type": "section",
                  "text": {
                    "type": "mrkdwn",
                    "text": "*Production Deployment Failed*\n\n⚠️ Rollback may be required!\n\nAttempted Version: ${{ github.event.inputs.version }}\nPrevious Version: ${{ needs.create-backup.outputs.current_version }}\nActor: ${{ github.actor }}\n\n<${{ github.server_url }}/${{ github.repository }}/actions/runs/${{ github.run_id }}|View Workflow>"
                  }
                }
              ]
            }
        env:
          SLACK_BOT_TOKEN: ${{ secrets.SLACK_BOT_TOKEN }}
```

### 3. Create `/.github/workflows/rollback.yaml`
```yaml
name: Rollback

on:
  workflow_dispatch:
    inputs:
      environment:
        description: 'Environment to rollback'
        required: true
        type: choice
        options:
          - staging
          - production
      version:
        description: 'Version to rollback to'
        required: true

permissions:
  contents: read
  id-token: write

jobs:
  rollback:
    name: Rollback Deployment
    runs-on: ubuntu-latest
    environment: ${{ github.event.inputs.environment }}
    steps:
      - uses: actions/checkout@v4

      - name: Configure AWS credentials
        uses: aws-actions/configure-aws-credentials@v4
        with:
          role-to-assume: ${{ github.event.inputs.environment == 'production' && secrets.AWS_ROLE_ARN_PROD || secrets.AWS_ROLE_ARN_STAGING }}
          aws-region: us-east-1

      - name: Set up kubectl
        uses: azure/setup-kubectl@v4
        with:
          version: 'v1.28.0'

      - name: Configure kubectl
        run: |
          CLUSTER_NAME="aswa-${{ github.event.inputs.environment == 'production' && 'prod' || 'staging' }}"
          aws eks update-kubeconfig --name $CLUSTER_NAME --region us-east-1

      - name: Verify version exists
        run: |
          docker manifest inspect ghcr.io/${{ github.repository_owner }}/aswa/api-gateway:${{ github.event.inputs.version }}

      - name: Record current version
        id: current
        run: |
          NAMESPACE="aswa-${{ github.event.inputs.environment == 'production' && 'prod' || 'staging' }}"
          CURRENT=$(kubectl get deployment aswa-api-gateway -n $NAMESPACE \
            -o jsonpath='{.spec.template.spec.containers[0].image}' | cut -d: -f2)
          echo "current_version=$CURRENT" >> $GITHUB_OUTPUT

      - name: Rollback deployment
        run: |
          NAMESPACE="aswa-${{ github.event.inputs.environment == 'production' && 'prod' || 'staging' }}"
          VALUES_FILE="values-${{ github.event.inputs.environment == 'production' && 'prod' || 'staging' }}.yaml"

          helm upgrade --install aswa infrastructure/helm/charts/aswa \
            --namespace $NAMESPACE \
            --values infrastructure/helm/charts/aswa/$VALUES_FILE \
            --set image.tag=${{ github.event.inputs.version }} \
            --wait \
            --timeout 10m

      - name: Verify rollback
        run: |
          NAMESPACE="aswa-${{ github.event.inputs.environment == 'production' && 'prod' || 'staging' }}"

          kubectl rollout status deployment/aswa-api-gateway -n $NAMESPACE --timeout=300s
          kubectl rollout status deployment/aswa-ingestion -n $NAMESPACE --timeout=300s
          kubectl rollout status deployment/aswa-query -n $NAMESPACE --timeout=300s
          kubectl rollout status deployment/aswa-insight -n $NAMESPACE --timeout=300s

      - name: Notify rollback
        uses: slackapi/slack-github-action@v1
        with:
          channel-id: ${{ secrets.SLACK_CHANNEL_DEPLOYMENTS }}
          payload: |
            {
              "text": "⏪ Rollback completed",
              "blocks": [
                {
                  "type": "section",
                  "text": {
                    "type": "mrkdwn",
                    "text": "*Rollback Completed*\n\nEnvironment: ${{ github.event.inputs.environment }}\nRolled back to: ${{ github.event.inputs.version }}\nPrevious: ${{ steps.current.outputs.current_version }}\nActor: ${{ github.actor }}"
                  }
                }
              ]
            }
        env:
          SLACK_BOT_TOKEN: ${{ secrets.SLACK_BOT_TOKEN }}
```

### 4. Create `/.github/workflows/release.yaml`
```yaml
name: Release

on:
  push:
    tags:
      - 'v*'

permissions:
  contents: write
  packages: write
  id-token: write

jobs:
  build:
    name: Build Release Images
    uses: ./.github/workflows/build-images.yaml
    with:
      environment: production
      tag: ${{ github.ref_name }}
    secrets: inherit

  create-release:
    name: Create GitHub Release
    runs-on: ubuntu-latest
    needs: build
    steps:
      - uses: actions/checkout@v4
        with:
          fetch-depth: 0

      - name: Generate changelog
        id: changelog
        run: |
          # Get previous tag
          PREV_TAG=$(git describe --tags --abbrev=0 HEAD^ 2>/dev/null || echo "")

          if [ -z "$PREV_TAG" ]; then
            echo "changelog=Initial release" >> $GITHUB_OUTPUT
          else
            CHANGELOG=$(git log --pretty=format:"- %s (%h)" $PREV_TAG..HEAD)
            echo "changelog<<EOF" >> $GITHUB_OUTPUT
            echo "$CHANGELOG" >> $GITHUB_OUTPUT
            echo "EOF" >> $GITHUB_OUTPUT
          fi

      - name: Create Release
        uses: softprops/action-gh-release@v1
        with:
          tag_name: ${{ github.ref_name }}
          name: Release ${{ github.ref_name }}
          body: |
            ## Changes

            ${{ steps.changelog.outputs.changelog }}

            ## Docker Images

            - `ghcr.io/${{ github.repository_owner }}/aswa/api-gateway:${{ github.ref_name }}`
            - `ghcr.io/${{ github.repository_owner }}/aswa/ingestion-service:${{ github.ref_name }}`
            - `ghcr.io/${{ github.repository_owner }}/aswa/query-service:${{ github.ref_name }}`
            - `ghcr.io/${{ github.repository_owner }}/aswa/insight-service:${{ github.ref_name }}`
            - `ghcr.io/${{ github.repository_owner }}/aswa/web-dashboard:${{ github.ref_name }}`

            ## Deployment

            To deploy this release:
            ```bash
            gh workflow run deploy-production.yaml -f version=${{ github.ref_name }}
            ```
          draft: false
          prerelease: ${{ contains(github.ref_name, '-rc') || contains(github.ref_name, '-beta') }}
```

## Verification

1. Test staging deployment: Push to main branch
2. Test production deployment: Create a tag and trigger workflow
3. Verify rollback works correctly
4. Check Slack notifications are received
5. Verify database migrations run successfully
