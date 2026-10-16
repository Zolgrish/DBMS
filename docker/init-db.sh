#!/usr/bin/env bash
set -Eeuo pipefail

DB_HOST="${DB_HOST:-sqlserver}"
DB_PORT="${DB_PORT:-1433}"
DB_SERVER="${DB_HOST},${DB_PORT}"
DB_DIR="/opt/qldsv/database"

if [[ -z "${MSSQL_SA_PASSWORD:-}" ]]; then
  echo "[db-init] MSSQL_SA_PASSWORD is required." >&2
  exit 1
fi

if [[ -x /opt/mssql-tools18/bin/sqlcmd ]]; then
  SQLCMD=/opt/mssql-tools18/bin/sqlcmd
elif [[ -x /opt/mssql-tools/bin/sqlcmd ]]; then
  SQLCMD=/opt/mssql-tools/bin/sqlcmd
else
  echo "[db-init] sqlcmd was not found in the SQL Server image." >&2
  exit 1
fi

sqlcmd_sa() {
  "$SQLCMD" \
    -S "$DB_SERVER" \
    -U sa \
    -C \
    -b \
    "$@"
}

# sqlcmd consumes SQLCMDPASSWORD without putting the SA password in argv.
export SQLCMDPASSWORD="$MSSQL_SA_PASSWORD"

run_security() {
  # sqlcmd substitutes variables before SQL parsing. Encode input as UTF-16LE
  # hex literals so quotes, $, brackets and SQL text cannot escape the value.
  # Environment substitution also keeps the Admin password out of argv/logs.
  sql_hex() {
    printf '0x'
    printf '%s' "$1" | iconv -f UTF-8 -t UTF-16LE | od -An -v -tx1 | tr -d ' \n'
  }
  export QLDSV_ADMIN_LOGIN_HEX="$(sql_hex "${QLDSV_ADMIN_LOGIN:-GV00000001}")"
  export QLDSV_ADMIN_PASSWORD_HEX="$(sql_hex "${QLDSV_ADMIN_PASSWORD:-}")"
  export QLDSV_STUDENT_LOGIN_HEX="$(sql_hex "${QLDSV_STUDENT_LOGIN:-SV00000001}")"
  run_sql_file "Security.sql"
  unset QLDSV_ADMIN_PASSWORD_HEX QLDSV_ADMIN_PASSWORD
}

run_sql_file() {
  local filename="$1"
  local path="$DB_DIR/$filename"

  if [[ ! -f "$path" ]]; then
    echo "[db-init] Missing required SQL file: $filename" >&2
    exit 1
  fi

  echo "[db-init] Running $filename"
  sqlcmd_sa -i "$path"
}

run_optional_sql_file() {
  local filename="$1"
  local path="$DB_DIR/$filename"

  if [[ -f "$path" ]]; then
    echo "[db-init] Running optional $filename"
    sqlcmd_sa -i "$path"
  else
    echo "[db-init] Optional $filename not present yet; skipping."
  fi
}

echo "[db-init] Waiting for SQL Server at $DB_SERVER ..."
for attempt in $(seq 1 60); do
  if sqlcmd_sa -Q "SELECT 1" >/dev/null 2>&1; then
    break
  fi

  if [[ "$attempt" -eq 60 ]]; then
    echo "[db-init] SQL Server did not become ready in time." >&2
    exit 1
  fi

  sleep 2
done

db_exists="$(sqlcmd_sa -h -1 -W -Q "SET NOCOUNT ON; SELECT CASE WHEN DB_ID(N'QLDSV') IS NULL THEN 0 ELSE 1 END;" | tr -d '\r[:space:]')"

if [[ "$db_exists" == "0" ]]; then
  run_sql_file "Database_QLDSV.sql"
else
  echo "[db-init] Database QLDSV already exists; preserving existing data."

  core_ok="$(sqlcmd_sa -d QLDSV -h -1 -W -Q "SET NOCOUNT ON; SELECT CASE WHEN OBJECT_ID(N'dbo.Lop', N'U') IS NOT NULL AND OBJECT_ID(N'dbo.Sinhvien', N'U') IS NOT NULL AND OBJECT_ID(N'dbo.Giangvien', N'U') IS NOT NULL AND OBJECT_ID(N'dbo.Monhoc', N'U') IS NOT NULL AND OBJECT_ID(N'dbo.Diem', N'U') IS NOT NULL THEN 1 ELSE 0 END;" | tr -d '\r[:space:]')"

  if [[ "$core_ok" != "1" ]]; then
    echo "[db-init] QLDSV exists but the 5 core tables are incomplete." >&2
    echo "[db-init] Refusing to drop or overwrite existing data automatically." >&2
    echo "[db-init] For a clean development reset run: docker compose down -v" >&2
    exit 1
  fi
fi

# Repository extension used for lecturer/class/subject assignment.
# This is intentionally initialized in addition to the 5 core tables.
run_sql_file "CreatePhanCong.sql"

# These scripts are safe to run again: common SPs are recreated and seed data
# uses IF NOT EXISTS guards.
run_sql_file "storedProcedure.sql"
run_sql_file "seedData.sql"

# Epic 1.3 is required; security SPs remain optional until Epic 1.4.
run_security
run_optional_sql_file "StoredProcedures_Security.sql"

echo "[db-init] Verifying QLDSV objects ..."
sqlcmd_sa -d QLDSV -Q "SET NOCOUNT ON; SELECT name AS TableName FROM sys.tables WHERE name IN (N'Lop',N'Sinhvien',N'Giangvien',N'Monhoc',N'Diem',N'PhanCong') ORDER BY name; SELECT name AS ProcedureName FROM sys.procedures WHERE name LIKE N'sp[_]%' ORDER BY name;"

echo "[db-init] QLDSV initialization completed successfully."
