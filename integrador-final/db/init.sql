-- Base de datos para registro de interesados (proyecto integrador final)
CREATE TABLE IF NOT EXISTS registros (
    id SERIAL PRIMARY KEY,
    nombre VARCHAR(255) NOT NULL,
    comuna SMALLINT NOT NULL CHECK (comuna >= 1 AND comuna <= 10),
    fecha_ingreso DATE NOT NULL,
    carrera VARCHAR(64) NOT NULL CHECK (
        carrera IN ('Medicina', 'Ingeniería', 'Abogacía', 'Licenciatura')
    ),
    creado_en TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_registros_comuna ON registros (comuna);
CREATE INDEX IF NOT EXISTS idx_registros_carrera ON registros (carrera);
