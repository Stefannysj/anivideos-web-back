#!/bin/sh
set -eu
TEST_DB="${POSTGRES_DB}_test"
psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" <<SQL
CREATE DATABASE "$TEST_DB";
SQL
