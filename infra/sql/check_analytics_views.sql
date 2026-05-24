SELECT * FROM latest_weather_by_city ORDER BY city;

SELECT * FROM latest_vehicle_positions ORDER BY vehicle_id;

SELECT * FROM latest_traffic_by_route ORDER BY route_name;

SELECT * FROM deliveries_status_summary ORDER BY status;

SELECT * FROM logistics_kpis;

SELECT * FROM ingestion_status ORDER BY source;

SELECT reference, risk_score, risk_level, predicted_delay_minutes, recommendation
FROM delivery_risk_predictions ORDER BY risk_score DESC;

SELECT vehicle_id, license_plate, driver_name, vehicle_status, delivery_reference,
       risk_score, risk_level FROM dispatch_control_board ORDER BY vehicle_id;

SELECT * FROM business_control_tower;
