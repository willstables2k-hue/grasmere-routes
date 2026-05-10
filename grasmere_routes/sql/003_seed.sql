-- Seed config + depot. Safe to re-run.

INSERT INTO config (id) VALUES (1) ON CONFLICT (id) DO NOTHING;

INSERT INTO depot (name, address, lat, lng)
SELECT 'Grasmere Farm, Bourne', 'Bourne, Lincolnshire, UK', 52.7691, -0.3819
WHERE NOT EXISTS (SELECT 1 FROM depot);

-- A sensible default fleet so /plan can solve before vehicles are configured manually
INSERT INTO vehicles (name, capacity_kg, capacity_crates, mpg, refrigerated)
SELECT 'Van ' || g, 1200, 80, 25, true
FROM generate_series(1, 7) g
WHERE NOT EXISTS (SELECT 1 FROM vehicles);
