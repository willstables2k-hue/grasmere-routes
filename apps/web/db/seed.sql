-- Single-row config with spec defaults.
INSERT INTO config (id, diesel_price_pence_per_litre, default_mpg, default_driver_hourly_rate_pence,
                    avg_speed_kmh, service_time_min_per_stop, depot_loading_time_min,
                    vehicle_fixed_cost_per_day_pence, driver_max_shift_hours,
                    default_gross_margin_pct, dormancy_threshold_days, working_delivery_days)
VALUES (1, 188, 25.00, 1600, 50.00, 8, 30, 2500, 8.00, 0.280, 180, ARRAY[1,3,4]::int[])
ON CONFLICT (id) DO NOTHING;

-- Depot row for Grasmere Farm, Bourne (env defaults DEPOT_LAT/LNG match).
INSERT INTO depot (name, address, lat, lng, opening_time, closing_time)
SELECT 'Grasmere Farm, Bourne', 'Bourne, Lincolnshire, UK', 52.7691, -0.3819, '06:00', '18:00'
WHERE NOT EXISTS (SELECT 1 FROM depot);
