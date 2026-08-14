SELECT 'CREATE DATABASE identity_camareros'
WHERE NOT EXISTS (SELECT FROM pg_database WHERE datname = 'identity_camareros')\gexec

SELECT 'CREATE DATABASE identity_negocio'
WHERE NOT EXISTS (SELECT FROM pg_database WHERE datname = 'identity_negocio')\gexec
