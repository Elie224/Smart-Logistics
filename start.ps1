# ============================================================
#  Smart Logistics — Script de démarrage
# ============================================================

Set-Location $PSScriptRoot

Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "   Smart Logistics — Démarrage" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# --- 1. Vérifier que Docker est en cours d'exécution --------
Write-Host "[1/4] Vérification de Docker..." -ForegroundColor Yellow
try {
    docker info 2>&1 | Out-Null
    if ($LASTEXITCODE -ne 0) { throw }
    Write-Host "      Docker OK" -ForegroundColor Green
} catch {
    Write-Host "      Docker n'est pas démarré. Lance Docker Desktop puis relance ce script." -ForegroundColor Red
    Read-Host "Appuie sur Entrée pour quitter"
    exit 1
}

# --- 2. Build + démarrage de tous les services --------------
Write-Host ""
Write-Host "[2/4] Démarrage des containers (docker compose up)..." -ForegroundColor Yellow
docker compose up -d --build
if ($LASTEXITCODE -ne 0) {
    Write-Host "      Erreur lors du docker compose up." -ForegroundColor Red
    Read-Host "Appuie sur Entrée pour quitter"
    exit 1
}

# --- 3. Attendre que PostgreSQL soit healthy ----------------
Write-Host ""
Write-Host "[3/4] Attente que PostgreSQL soit prêt..." -ForegroundColor Yellow
$maxWait = 60
$elapsed = 0
do {
    Start-Sleep -Seconds 3
    $elapsed += 3
    $health = docker inspect --format "{{.State.Health.Status}}" smart-logistics-postgres 2>$null
    Write-Host "      [$elapsed s] Statut postgres: $health" -ForegroundColor DarkGray
} while ($health -ne "healthy" -and $elapsed -lt $maxWait)

if ($health -ne "healthy") {
    Write-Host "      PostgreSQL n'est pas prêt après $maxWait secondes." -ForegroundColor Red
} else {
    Write-Host "      PostgreSQL prêt !" -ForegroundColor Green
}

# --- 4. Résumé des URLs -------------------------------------
Write-Host ""
Write-Host "[4/4] Services disponibles :" -ForegroundColor Yellow
Write-Host ""
Write-Host "   Frontend    http://localhost:3004" -ForegroundColor Cyan
Write-Host "   API         http://localhost:8001/docs" -ForegroundColor Cyan
Write-Host "   n8n         http://localhost:5679   (admin / admin123)" -ForegroundColor Cyan
Write-Host "   pgAdmin     http://localhost:5050   (admin@smartlogistics.com / admin123)" -ForegroundColor Cyan
Write-Host "   Metabase    http://localhost:3003" -ForegroundColor Cyan
Write-Host ""
Write-Host "========================================" -ForegroundColor Green
Write-Host "   Tout est lancé !" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Green
Write-Host ""

# Ouvrir le frontend dans le navigateur par défaut
Start-Process "http://localhost:3004"
