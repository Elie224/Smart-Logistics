# ============================================================
#  Smart Logistics — Import des workflows n8n
# ============================================================
#  Usage : .\import-workflows.ps1
#  Importe les 4 fichiers JSON dans le container n8n en cours.
# ============================================================

Set-Location $PSScriptRoot

$CONTAINER   = "smart-logistics-n8n"
$WORKFLOWS_DIR = Join-Path $PSScriptRoot "n8n\workflows"

Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "   Import des workflows n8n" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# --- Vérifier que le container tourne ----------------------
$running = docker inspect --format "{{.State.Running}}" $CONTAINER 2>$null
if ($running -ne "true") {
    Write-Host "Le container '$CONTAINER' n'est pas démarré." -ForegroundColor Red
    Write-Host "Lance d'abord : docker compose up -d" -ForegroundColor Yellow
    Read-Host "Appuie sur Entrée pour quitter"
    exit 1
}
Write-Host "Container $CONTAINER : OK" -ForegroundColor Green
Write-Host ""

# --- Liste des fichiers à importer -------------------------
$files = Get-ChildItem -Path $WORKFLOWS_DIR -Filter "*.json" | Sort-Object Name

if ($files.Count -eq 0) {
    Write-Host "Aucun fichier JSON trouvé dans $WORKFLOWS_DIR" -ForegroundColor Red
    exit 1
}

Write-Host "Fichiers à importer :" -ForegroundColor Yellow
$files | ForEach-Object { Write-Host "  - $($_.Name)" -ForegroundColor DarkGray }
Write-Host ""

# --- Import de chaque workflow ------------------------------
$success = 0
$failed  = 0

foreach ($file in $files) {
    $dest = "/tmp/$($file.Name)"

    Write-Host "Import : $($file.Name) ..." -NoNewline

    # Copie du fichier dans le container
    docker cp $file.FullName "${CONTAINER}:${dest}" 2>&1 | Out-Null

    # Import via CLI n8n
    $result = docker exec $CONTAINER n8n import:workflow --input=$dest 2>&1
    docker exec $CONTAINER rm -f $dest 2>&1 | Out-Null   # nettoyage

    if ($result -match "imported" -or $result -match "success" -or $LASTEXITCODE -eq 0) {
        Write-Host " OK" -ForegroundColor Green
        $success++
    } else {
        Write-Host " ERREUR" -ForegroundColor Red
        Write-Host "  $result" -ForegroundColor DarkRed
        $failed++
    }
}

# --- Statut final ------------------------------------------
Write-Host ""
Write-Host "----------------------------------------" -ForegroundColor DarkGray
Write-Host "  Importés : $success / $($files.Count)" -ForegroundColor $(if ($failed -eq 0) { "Green" } else { "Yellow" })
if ($failed -gt 0) {
    Write-Host "  Échecs   : $failed" -ForegroundColor Red
}

# --- Afficher les workflows actifs dans n8n DB -------------
Write-Host ""
Write-Host "Workflows actifs en base :" -ForegroundColor Yellow
docker exec smart-logistics-postgres psql -U postgres -d smart_logistics `
    -c "SELECT id, name, active FROM workflow_entity ORDER BY active DESC, id;" `
    2>$null

Write-Host ""
Write-Host "n8n : http://localhost:5679  (admin / admin123)" -ForegroundColor Cyan
Write-Host ""
