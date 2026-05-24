# Smart Logistics Platform

Cette base de projet traduit la feuille de route en un premier socle technique exploitable.

## Vision generale

Le projet complet vise une plateforme data/IA de transport et logistique capable de :

- collecter des donnees temps reel,
- stocker et historiser les flux,
- automatiser les integrations,
- exposer les KPIs dans des dashboards,
- preparer des cas d'usage prediction et assistant IA.

L'architecture cible issue de la feuille de route est la suivante :

```text
APIs temps reel (meteo, trafic, GPS)
        -> n8n (collecte, ETL, automatisation)
        -> PostgreSQL (stockage)
        -> Metabase (analytics)
        -> IA / ML / assistant
```

## Ce que couvre cette phase 1

Cette premiere phase pose la fondation indispensable :

- PostgreSQL pour le stockage,
- pgAdmin pour administrer la base,
- n8n pour l'automatisation,
- Metabase pour les dashboards,
- une premiere table `weather_data`,
- un workflow n8n de collecte OpenWeather sur 5 villes toutes les 1 heure.

Si cette phase fonctionne, alors tu valides deja la brique ingestion + ETL + stockage temps reel.

## Structure du repository

```text
.
|-- api/
|   |-- Dockerfile
|   |-- app/
|   |   |-- config.py
|   |   |-- database.py
|   |   `-- main.py
|   `-- requirements.txt
|-- .dockerignore
|-- .env.example
|-- docker-compose.yml
|-- infra/
|   `-- sql/
|       |-- 001_init.sql
|       |-- 002_analytics_views.sql
|       |-- check_analytics_views.sql
|       |-- check_gps_tracking.sql
|       |-- check_operations_data.sql
|       |-- check_traffic_data.sql
|       |-- seed_operations_demo.sql
|       `-- check_weather_data.sql
`-- n8n/
|   `-- workflows/
|       |-- gps_webhook_ingestion.json
|       |-- traffic_ingestion_mapbox.json
|       `-- weather_ingestion.json
`-- scripts/
        `-- gps_simulator.py
```

## Prerequis

- Docker Desktop
- un compte OpenWeather avec une cle API

Tu peux continuer a installer PostgreSQL, pgAdmin et n8n manuellement si tu preferes, mais dans ce repository le demarrage local est simplifie via Docker Compose.

## Demarrage rapide

### 1. Preparer les variables d'environnement

Sous PowerShell :

```powershell
Copy-Item .env.example .env
```

Puis remplace au minimum :

- `OPENWEATHER_API_KEY`
- `MAPBOX_API_KEY`
- `N8N_ENCRYPTION_KEY`
- les mots de passe par des valeurs robustes

Par defaut, le projet publie PostgreSQL sur le port hote `5433` pour eviter un conflit avec une installation locale deja presente sur `5432`.
Metabase est publie par defaut sur le port hote `3003` pour eviter les conflits frequents sur `3000`, `3001` et `3002` sur cette machine.

### 2. Lancer l'infrastructure

```powershell
docker compose up -d
```

Services disponibles :

- PostgreSQL : `localhost:5433`
- pgAdmin : `http://localhost:5050`
- n8n : `http://localhost:5679`
- Metabase : `http://localhost:3003`
- API FastAPI : `http://localhost:8001`

La valeur par defaut recommandee pour `PGADMIN_DEFAULT_EMAIL` est `admin@smartlogistics.com`.

Attention : `localhost:5433` est un port de base de donnees PostgreSQL, pas une interface web. Il faut l'utiliser avec `psql`, pgAdmin, Metabase ou l'API, mais pas directement dans le navigateur.
Pour ouvrir Metabase dans le navigateur, utilise `http://localhost:3003`.

### 3. Verifier la base

Le script [infra/sql/001_init.sql](infra/sql/001_init.sql) cree automatiquement les tables `weather_data`, `gps_tracking`, `vehicles` et `deliveries` au premier demarrage de PostgreSQL.

Tu peux verifier avec pgAdmin ou avec `psql` :

```sql
SELECT * FROM weather_data ORDER BY created_at DESC;
```

## Configuration du workflow n8n

Le fichier [n8n/workflows/weather_ingestion.json](n8n/workflows/weather_ingestion.json) sert de base importable ou de reference de configuration.

Workflow logique :

```text
Cron Trigger
        -> Prepare Cities (Paris, Lyon, Marseille, Lille, Toulouse)
        -> HTTP Request (OpenWeather)
      -> Set Weather Payload
      -> PostgreSQL
```

Dans n8n :

1. Cree une credential PostgreSQL pointee vers :
   - host : `postgres`
   - port : `5432`
   - database : `smart_logistics`
   - user : valeur `POSTGRES_USER`
   - password : valeur `POSTGRES_PASSWORD`
2. Importe le workflow JSON.
3. Remplace la credential `Postgres Smart Logistics` dans le noeud PostgreSQL.
4. Verifie que le noeud `Prepare Cities` envoie bien `Paris`, `Lyon`, `Marseille`, `Lille` et `Toulouse`.
5. Lance un test manuel du workflow.
6. Active le workflow quand le test est concluant.

Le workflow [n8n/workflows/weather_ingestion.json](n8n/workflows/weather_ingestion.json) collecte maintenant la meteo de 5 villes francaises toutes les 1 heure, puis enregistre chaque releve dans `weather_data`.

Par defaut, l'interface n8n est publiee sur `http://localhost:5679` pour eviter un conflit avec un service deja present sur `5678`.

## Validation attendue en fin de phase 1

Tu dois etre capable de confirmer :

- PostgreSQL demarre et contient la table `weather_data`
- n8n demarre et appelle OpenWeather
- cinq lignes sont inserees automatiquement toutes les 1 heure
- la requete [infra/sql/check_weather_data.sql](infra/sql/check_weather_data.sql) retourne des donnees
- la table `traffic_data` existe pour preparer la collecte trafic
- les tables `vehicles` et `deliveries` existent pour preparer la couche metier
- une API FastAPI peut lire les KPIs et les donnees metier

## API FastAPI

Une API FastAPI minimale est incluse pour exposer en lecture les objets principaux du projet.

### Fichiers API

- [api/app/main.py](api/app/main.py)
- [api/app/config.py](api/app/config.py)
- [api/app/database.py](api/app/database.py)
- [api/requirements.txt](api/requirements.txt)

### Endpoints disponibles

- `GET /`
- `GET /api/v1/health`
- `GET /api/v1/kpis`
- `GET /api/v1/ingestion-status`
- `GET /api/v1/business/overview`
- `GET /api/v1/business/dispatch-board`
- `GET /api/v1/business/alerts`
- `GET /api/v1/predictions/delivery-risks`
- `GET /api/v1/weather/latest`
- `GET /api/v1/traffic/latest`
- `GET /api/v1/vehicles`
- `GET /api/v1/deliveries`
- `GET /api/v1/operations`

### Lancer l'API localement

Quand Python sera disponible :

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r .\api\requirements.txt
uvicorn api.app.main:app --reload
```

L'API lira automatiquement les variables PostgreSQL depuis `.env` si ce fichier existe a la racine du projet.

Depuis l'hote Windows, elle peut aussi utiliser `POSTGRES_HOST_PORT=5433` pour viser le conteneur PostgreSQL sans entrer en conflit avec un PostgreSQL local.

L'endpoint `GET /api/v1/ingestion-status` expose l'etat de fraicheur des flux `weather`, `traffic` et `gps` avec le dernier horodatage collecte, le nombre total de lignes et un statut `fresh`, `stale` ou `missing`.

Les endpoints `GET /api/v1/business/overview`, `GET /api/v1/business/dispatch-board`, `GET /api/v1/business/alerts` et `GET /api/v1/predictions/delivery-risks` exposent maintenant la couche metier de pilotage hors Metabase : synthese du reseau, tableau de dispatch, alertes critiques et prediction de risque par livraison.

Pour que les endpoints analytics fonctionnent, il faudra avoir execute aussi :

```powershell
psql -h localhost -U postgres -d smart_logistics -f .\infra\sql\002_analytics_views.sql
```

### Lancer l'API avec Docker Compose

Le service `api` est maintenant inclus dans [docker-compose.yml](docker-compose.yml).

Une fois les images disponibles, l'API sera exposee sur `http://localhost:8000` et utilisera automatiquement PostgreSQL via le nom de service `postgres`.
Par defaut, le port hote utilise est `8001` pour eviter un conflit avec un service local deja present sur `8000`.

## Couche metier : vehicles et deliveries

Le schema metier minimal est deja inclus dans [infra/sql/001_init.sql](infra/sql/001_init.sql) avec :

- `vehicles` pour les ressources roulantes,
- `deliveries` pour les missions,
- des cles et index de base,
- une relation entre livraison et vehicule.

Pour verifier rapidement cette couche plus tard, tu peux utiliser :

- [infra/sql/check_operations_data.sql](infra/sql/check_operations_data.sql)
- [infra/sql/seed_operations_demo.sql](infra/sql/seed_operations_demo.sql)

### Seed de demonstration

Le script [infra/sql/seed_operations_demo.sql](infra/sql/seed_operations_demo.sql) ajoute quelques vehicules et livraisons de test sans dupliquer les lignes si tu le relances.

Exemple avec `psql` quand PostgreSQL sera disponible :

```powershell
psql -h localhost -U postgres -d smart_logistics -f .\infra\sql\seed_operations_demo.sql
```

Depuis l'hote Windows, ajoute `-p 5433` par defaut.

Puis controle les donnees avec :

```powershell
psql -h localhost -U postgres -d smart_logistics -f .\infra\sql\check_operations_data.sql
```

## Simulation GPS

Le script [scripts/gps_simulator.py](scripts/gps_simulator.py) permet d'envoyer des positions GPS de demonstration vers le webhook n8n.

Depuis Windows avec Python configure :

```powershell
python .\scripts\gps_simulator.py --vehicle-ids 1 2 3 --count 3 --interval 2
```

Depuis Docker, sans Python local :

```powershell
docker compose run --rm -e GPS_WEBHOOK_URL=http://n8n:5678/webhook/gps-tracking api python /app/scripts/gps_simulator.py --vehicle-ids 1 2 3 --count 3 --interval 2
```

Pour garder le flux `gps` automatiquement frais, le stack lance aussi desormais un service `gps-simulator` dans [docker-compose.yml](docker-compose.yml) qui emet en boucle des positions pour les vehicules 1, 2 et 3 vers n8n.

La frequence se regle avec `GPS_SIMULATOR_CYCLE_SECONDS` dans `.env`.

Tu peux ensuite verifier la fraicheur du flux avec :

```powershell
Invoke-RestMethod -Uri http://localhost:8001/api/v1/ingestion-status
```

## Dashboards Metabase

Metabase est maintenant inclus dans le stack Docker pour la visualisation rapide des donnees meteo et GPS.

### Premier acces

1. Ouvre `http://localhost:3003`.
2. Termine l'assistant de creation du compte administrateur.
3. Ajoute une base de donnees PostgreSQL.
4. Pointe Metabase vers la base `smart_logistics`.

Parametres de connexion a utiliser dans Metabase :

- host : `postgres` si tu configures depuis le conteneur Metabase dans le reseau Docker, ou `host.docker.internal` / `localhost` selon ton mode d'acces
- port : `5432` depuis les conteneurs, ou `5433` depuis l'hote Windows
- database : `smart_logistics`
- username : valeur `POSTGRES_USER`
- password : valeur `POSTGRES_PASSWORD`

### Questions utiles a creer tout de suite

- les derniers releves meteo par ville
- les positions GPS les plus recentes par vehicule
- le dernier temps de trajet par route suivie
- le nombre de points GPS recus par heure
- l'evolution de la temperature sur les dernieres 24 heures
- les livraisons par statut
- les vehicules disponibles vs en transit

Pour accelerer la creation du dashboard, tu peux reutiliser directement les requetes pretes dans [infra/sql/metabase_dashboard_queries.sql](infra/sql/metabase_dashboard_queries.sql).

### Vues SQL pretes pour Metabase

Le fichier [infra/sql/002_analytics_views.sql](infra/sql/002_analytics_views.sql) cree des vues directement consommables dans Metabase :

- `latest_weather_by_city`
- `latest_vehicle_positions`
- `latest_traffic_by_route`
- `deliveries_status_summary`
- `logistics_kpis`
- `ingestion_status`
- `delivery_risk_predictions`
- `dispatch_control_board`
- `business_control_tower`

Tu peux les verifier via [infra/sql/check_analytics_views.sql](infra/sql/check_analytics_views.sql).

Ces vues te donnent une base propre pour construire rapidement :

- une carte ou table des derniers points GPS par vehicule,
- une table des derniers temps de trajet par route,
- un resume des livraisons par statut,
- une prediction de risque par livraison,
- un tableau de dispatch priorise,
- des cartes KPI pour le parc et les retards,
- un resume meteo par ville.

### Pack SQL pret a coller dans Metabase

Le fichier [infra/sql/metabase_dashboard_queries.sql](infra/sql/metabase_dashboard_queries.sql) contient un pack de requetes SQL natives pour construire rapidement :

- une carte KPI globale,
- un suivi de fraicheur des flux `weather`, `traffic` et `gps`,
- une vue `Business Control Tower`,
- une table `Delivery Risk Predictions`,
- un tableau `Dispatch Control Board`,
- une table des derniers releves meteo par ville,
- une courbe d'historique meteo sur 24 heures,
- une table des dernieres positions GPS,
- un suivi horaire des points GPS recus,
- une table du dernier trafic par route,
- une courbe d'evolution du retard trafic,
- un resume des livraisons par statut.

### Bootstrap automatique du dashboard Metabase

Le script [scripts/metabase_bootstrap.py](scripts/metabase_bootstrap.py) permet de recreer automatiquement dans Metabase :

- la connexion a la base `Smart Logistics`,
- la collection `Smart Logistics`,
- le dashboard `Smart Logistics Overview`,
- les cartes KPI, statut d'ingestion, pilotage business, prediction, meteo, trafic, GPS et livraisons,
- les graphiques d'historique meteo, trafic et activite GPS.

Exemple d'execution :

```powershell
python .\scripts\metabase_bootstrap.py --username kouroumaelisee@gmail.com --password Admin12345A
```

Ou avec des variables d'environnement :

```powershell
$env:METABASE_ADMIN_EMAIL="kouroumaelisee@gmail.com"
$env:METABASE_ADMIN_PASSWORD="Admin12345A"
python .\scripts\metabase_bootstrap.py
```

Le script se base sur la pile locale actuelle et reconcilie la disposition du dashboard via l'API Metabase. Si la base `Smart Logistics` n'existe pas encore dans Metabase, il la cree automatiquement en pointant vers PostgreSQL avec `postgres:5432`.

## Extension immediate recommandee : trafic routier

La feuille de route mentionne Google Maps ou Mapbox pour integrer le trafic. Cette base inclut maintenant un premier workflow base sur Mapbox Directions.

### Table traffic_data

Le script [infra/sql/001_init.sql](infra/sql/001_init.sql) cree aussi la table `traffic_data` pour historiser les temps de trajet et le retard estime sur un trajet suivi.

Tu peux controler les donnees avec [infra/sql/check_traffic_data.sql](infra/sql/check_traffic_data.sql).

### Workflow n8n trafic

Le fichier [n8n/workflows/traffic_ingestion_mapbox.json](n8n/workflows/traffic_ingestion_mapbox.json) collecte toutes les 10 minutes un itineraire `Lyon -> Marseille` via Mapbox Directions API avec le profil `driving-traffic`.

Workflow logique :

```text
Cron Trigger
        -> HTTP Request (Mapbox Directions)
        -> Set Traffic Payload
        -> PostgreSQL
```

Dans n8n :

1. Renseigne `MAPBOX_API_KEY` dans `.env`.
2. Importe [n8n/workflows/traffic_ingestion_mapbox.json](n8n/workflows/traffic_ingestion_mapbox.json).
3. Reutilise la meme credential PostgreSQL que pour les autres workflows.
4. Lance un test manuel puis active le workflow.

Ce premier workflow peut ensuite etre duplique pour d'autres axes logistiques en modifiant les coordonnees de depart et d'arrivee.

## Extension immediate recommandee : GPS simule

La feuille de route proposait juste apres la meteo un flux GPS. Cette base inclut maintenant aussi cette brique.

### Table GPS

Le script [infra/sql/001_init.sql](infra/sql/001_init.sql) cree aussi la table `gps_tracking`.

Tu peux controler les positions stockees avec [infra/sql/check_gps_tracking.sql](infra/sql/check_gps_tracking.sql).

### Workflow n8n GPS

Le fichier [n8n/workflows/gps_webhook_ingestion.json](n8n/workflows/gps_webhook_ingestion.json) expose un webhook `POST /webhook/gps-tracking` qui :

```text
Webhook GPS
        -> Set GPS Payload
        -> PostgreSQL
        -> Webhook Response
```

Configuration dans n8n :

1. Importe [n8n/workflows/gps_webhook_ingestion.json](n8n/workflows/gps_webhook_ingestion.json).
2. Reutilise la meme credential PostgreSQL que pour le workflow meteo.
3. Active le workflow pour rendre le webhook disponible en URL de production.

### Simulateur Python GPS

Le script [scripts/gps_simulator.py](scripts/gps_simulator.py) envoie des positions GPS simulees a n8n sans dependance externe.

Exemple :

```powershell
python .\scripts\gps_simulator.py --count 10 --interval 5
```

Ce script envoie par defaut des points autour de Lyon vers :

```text
http://localhost:5679/webhook/gps-tracking
```

Tu peux changer l'URL, le vehicule, ou la frequence :

```powershell
python .\scripts\gps_simulator.py --vehicle-id 7 --interval 2 --count 20
```

### Validation GPS attendue

Tu dois pouvoir confirmer :

- le webhook n8n repond en `ok`
- les positions GPS arrivent dans `gps_tracking`
- la requete [infra/sql/check_gps_tracking.sql](infra/sql/check_gps_tracking.sql) retourne des lignes

## Modele metier minimal

La couche metier de base est maintenant prete pour la suite du projet.

### Table vehicles

Elle stocke le parc vehicule :

- plaque,
- chauffeur,
- capacite,
- statut.

### Table deliveries

Elle stocke les livraisons :

- reference,
- origine,
- destination,
- horaires prevus et reels,
- cout,
- retard,
- rattachement eventuel a un vehicule.

### Requete de controle metier

La requete [infra/sql/check_operations_data.sql](infra/sql/check_operations_data.sql) permet de verifier rapidement le lien vehicules/livraisons.

## Lecture produit de la feuille de route

La feuille 1 donne la cible globale : plateforme complete de pilotage logistique temps reel avec data, dashboards, prediction et IA.

La feuille 2 isole la meilleure entree projet : commencer par un flux externe simple mais reel, ici la meteo de Lyon. C'est le bon choix car cette brique valide tout de suite :

- connectivite API,
- transformation JSON,
- stockage SQL,
- orchestration n8n,
- supervision de bout en bout.

## Etat actuel de la phase

La base locale couvre maintenant :

1. la collecte meteo horaire sur 5 villes,
2. la collecte trafic via Mapbox,
3. l'ingestion GPS avec simulation manuelle et periodique,
4. les vues SQL de supervision et de prediction,
5. une API FastAPI analytics + business,
6. un dashboard Metabase reconstruisable automatiquement.