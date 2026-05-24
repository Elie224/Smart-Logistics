SELECT
    id,
    city,
    temperature,
    humidity,
    weather,
    wind_speed,
    created_at
FROM weather_data
ORDER BY created_at DESC;
