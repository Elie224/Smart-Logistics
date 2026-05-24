-- Migration : ajout de la colonne city dans traffic_data
-- Exécuter une seule fois sur une DB existante

ALTER TABLE traffic_data ADD COLUMN IF NOT EXISTS city VARCHAR(100);

-- Nettoyer les anciennes données Paris→Lille qui n'ont plus de sens
-- (optionnel : conserver en commentaire si on veut garder l'historique)
-- DELETE FROM traffic_data WHERE route_name = 'Paris -> Lille';

-- Recréer les vues analytiques avec la nouvelle logique
\i /docker-entrypoint-initdb.d/002_analytics_views.sql
