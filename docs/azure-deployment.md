# Deployment Azure - Smart Logistics

Ce guide deploie la plateforme sur Azure avec:
- Azure Container Registry (ACR)
- Azure Container Apps (API + Frontend)
- Azure Database for PostgreSQL Flexible Server

Il est adapte a ce repository (FastAPI + React/Nginx).

## 1) Prerequis

- Azure CLI installe
- Docker (ou utilisation de `az acr build`)
- Compte Azure connecte

```powershell
az login
az account set --subscription "<SUBSCRIPTION_NAME_OR_ID>"
```

## 2) Variables (PowerShell)

```powershell
$LOC        = "francecentral"
$RG         = "rg-smart-logistics-prod"
$ENV        = "cae-smart-logistics"
$ACR        = "acrsmartlog" # minuscule, unique global
$API_APP    = "api-smart-logistics"
$WEB_APP    = "web-smart-logistics"
$PG_SERVER  = "pg-smart-logistics-prod" # unique global
$PG_DB      = "smart_logistics"
$PG_ADMIN   = "pgadmin"
$PG_PASS    = "<MOT_DE_PASSE_FORT>"
$OPENAI_KEY = "<OPENAI_API_KEY>"
$MAPBOX_KEY = "<MAPBOX_API_KEY>"
```

## 3) Ressources Azure de base

```powershell
az group create --name $RG --location $LOC

az acr create --resource-group $RG --name $ACR --sku Basic --admin-enabled true

az containerapp env create --name $ENV --resource-group $RG --location $LOC

az postgres flexible-server create `
  --resource-group $RG `
  --name $PG_SERVER `
  --location $LOC `
  --admin-user $PG_ADMIN `
  --admin-password $PG_PASS `
  --sku-name Standard_B1ms `
  --tier Burstable `
  --version 16 `
  --storage-size 32 `
  --public-access 0.0.0.0

az postgres flexible-server db create --resource-group $RG --server-name $PG_SERVER --database-name $PG_DB
```

## 4) Build et push des images vers ACR

Depuis la racine du projet:

```powershell
az acr build --registry $ACR --image smartlog-api:1.0.0 --file api/Dockerfile .
az acr build --registry $ACR --image smartlog-web:1.0.0 --file frontend/Dockerfile frontend
```

## 5) Initialiser le schema SQL (obligatoire)

Options:
- Option A: ouvrir Azure Data Studio/psql et executer les scripts `infra/sql/001_init.sql` puis `infra/sql/002_analytics_views.sql` puis `infra/sql/004_ml_dataset.sql`.
- Option B: automatiser plus tard via migration pipeline (recommande en prod).

Connexion PostgreSQL:
- Host: `$PG_SERVER.postgres.database.azure.com`
- Port: `5432`
- Database: `$PG_DB`
- User: `$PG_ADMIN`
- SSL mode: `require`

## 6) Deployer l'API sur Container Apps

```powershell
$ACR_SERVER = "$ACR.azurecr.io"
$API_IMAGE  = "$ACR_SERVER/smartlog-api:1.0.0"
$PG_HOST    = "$PG_SERVER.postgres.database.azure.com"

az containerapp create `
  --name $API_APP `
  --resource-group $RG `
  --environment $ENV `
  --image $API_IMAGE `
  --target-port 8000 `
  --ingress external `
  --registry-server $ACR_SERVER `
  --registry-identity system `
  --cpu 1.0 --memory 2.0Gi `
  --min-replicas 1 --max-replicas 3 `
  --secrets pg-password=$PG_PASS openai-api-key=$OPENAI_KEY mapbox-api-key=$MAPBOX_KEY `
  --env-vars `
    POSTGRES_HOST=$PG_HOST `
    POSTGRES_PORT=5432 `
    POSTGRES_DB=$PG_DB `
    POSTGRES_USER=$PG_ADMIN `
    POSTGRES_SSLMODE=require `
    POSTGRES_PASSWORD=secretref:pg-password `
    OPENAI_API_KEY=secretref:openai-api-key `
    MAPBOX_API_KEY=secretref:mapbox-api-key
```

Recuperer l'URL publique API:

```powershell
$API_FQDN = az containerapp show --name $API_APP --resource-group $RG --query properties.configuration.ingress.fqdn -o tsv
$API_URL = "https://$API_FQDN"
$API_URL
```

## 7) Deployer le frontend sur Container Apps

```powershell
$WEB_IMAGE = "$ACR_SERVER/smartlog-web:1.0.0"

az containerapp create `
  --name $WEB_APP `
  --resource-group $RG `
  --environment $ENV `
  --image $WEB_IMAGE `
  --target-port 80 `
  --ingress external `
  --registry-server $ACR_SERVER `
  --registry-identity system `
  --cpu 0.5 --memory 1.0Gi `
  --min-replicas 1 --max-replicas 2 `
  --env-vars API_UPSTREAM=$API_URL
```

Recuperer l'URL frontend:

```powershell
$WEB_FQDN = az containerapp show --name $WEB_APP --resource-group $RG --query properties.configuration.ingress.fqdn -o tsv
"https://$WEB_FQDN"
```

## 8) Autoriser Container Apps a pull depuis ACR

Si le pull d'image echoue, attribuer le role `AcrPull` a chaque app:

```powershell
$ACR_ID = az acr show -g $RG -n $ACR --query id -o tsv

$API_MI = az containerapp show -n $API_APP -g $RG --query identity.principalId -o tsv
$WEB_MI = az containerapp show -n $WEB_APP -g $RG --query identity.principalId -o tsv

az role assignment create --assignee-object-id $API_MI --assignee-principal-type ServicePrincipal --role AcrPull --scope $ACR_ID
az role assignment create --assignee-object-id $WEB_MI --assignee-principal-type ServicePrincipal --role AcrPull --scope $ACR_ID
```

Puis redemarrer les revisions:

```powershell
az containerapp revision restart --name $API_APP --resource-group $RG
az containerapp revision restart --name $WEB_APP --resource-group $RG
```

## 9) Verification

- API health: `https://<API_FQDN>/api/v1/health`
- Frontend: `https://<WEB_FQDN>`
- WebSocket live: `wss://<WEB_FQDN>/api/v1/ws/live` (via le proxy Nginx frontend)

## 10) Services optionnels (n8n, Metabase, workers)

Une fois API + frontend stables, deployer les autres services:
- n8n et Metabase en Container Apps separes (avec ingress selon besoin)
- workers (traffic collector, transit simulator, ml trainer) en Container Apps sans ingress

Recommande ensuite:
- domaine custom + TLS gere
- Azure Key Vault pour secrets
- CI/CD GitHub Actions (build ACR + update containerapp)
- monitoring Application Insights + Log Analytics

## 11) Hardening applique (etat courant)

Ces actions ont ete appliquees sur l'environnement:

- `POSTGRES_PASSWORD` de `api-smart-logistics` est passe en `secretref` (`postgres-password`)
- firewall PostgreSQL limite a `AllowAzureServices` (`0.0.0.0 -> 0.0.0.0`)
- frontend mis a jour en image `smartlog-web:1.0.1`
- proxy Nginx frontend corrige pour TLS upstream (SNI) afin d'eviter les `502` intermittents:
  - `proxy_ssl_server_name on;`
  - `proxy_ssl_name $proxy_host;`
  - `proxy_set_header Host $proxy_host;`

Verification rapide apres correction:

```powershell
$base = "https://web-smart-logistics.mangofield-e7b0deb0.francecentral.azurecontainerapps.io"
foreach ($p in @('/api/v1/health','/api/v1/kpis','/api/v1/business/overview','/api/v1/transit/lines','/api/v1/predictions/ml-delay-risk','/static/map.html')) {
  (Invoke-WebRequest -Uri ($base + $p) -TimeoutSec 60).StatusCode
}
```

## 12) n8n - relance et automatisation (local ops)

Relance n8n + PostgreSQL local:

```powershell
docker compose up -d postgres n8n
```

Import des workflows du repository:

```powershell
.\import-workflows.ps1
```

Activation forcee des workflows d'ingestion critiques:

```powershell
docker exec smart-logistics-postgres psql -U postgres -d smart_logistics -c "UPDATE workflow_entity SET active = true WHERE name IN ('Weather Ingestion Every 30 Minutes - Paris & Lille','Traffic Ingestion Every 30 Minutes','Transit Ingestion Every 30 Minutes - 5 Cities','GPS Webhook Ingestion');"
```

## 13) Domaine personnalise (prerequis DNS)

Valeurs de verification actuelles:

- verification id: `E4A79BC551E40CAB1F82E68B00AB9FA0DD298ECF1040ACF3F249A8652856805C`
- web FQDN: `web-smart-logistics.mangofield-e7b0deb0.francecentral.azurecontainerapps.io`
- api FQDN: `api-smart-logistics.mangofield-e7b0deb0.francecentral.azurecontainerapps.io`

Exemple pour binder un sous-domaine web (`app.example.com`):

1. Creer le DNS record CNAME `app -> web-smart-logistics.mangofield-e7b0deb0.francecentral.azurecontainerapps.io`
2. Creer le TXT `asuid.app` avec la valeur de verification id
3. Attacher le domaine sur la container app:

```powershell
az containerapp hostname bind \
  --resource-group rg-smart-logistics-7512 \
  --name web-smart-logistics \
  --hostname app.example.com \
  --validation-method CNAME
```

Meme logique pour l'API (`api.example.com`) en pointant vers `api-smart-logistics...`.
