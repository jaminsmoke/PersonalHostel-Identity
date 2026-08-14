SELECT 'CREATE DATABASE identity_camareros'
WHERE NOT EXISTS (SELECT FROM pg_database WHERE datname = 'identity_camareros')\gexec

SELECT 'CREATE DATABASE identity_negocio'
WHERE NOT EXISTS (SELECT FROM pg_database WHERE datname = 'identity_negocio')\gexec

SELECT 'CREATE DATABASE identity_camareros_test'
WHERE NOT EXISTS (SELECT FROM pg_database WHERE datname = 'identity_camareros_test')\gexec

SELECT 'CREATE DATABASE identity_negocio_test'
WHERE NOT EXISTS (SELECT FROM pg_database WHERE datname = 'identity_negocio_test')\gexec
