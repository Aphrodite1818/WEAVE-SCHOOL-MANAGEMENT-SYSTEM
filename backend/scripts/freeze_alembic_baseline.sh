#!/usr/bin/env bash
set -euo pipefail

baseline="alembic/versions/20260731_clean_baseline.py"
original_baseline="/tmp/20260731_clean_baseline.original.py"
diagnostic_file="validate_baseline_temp.py"
diagnostic_log="/tmp/baseline-freeze-diagnostic.log"

if ! grep -Eq 'Base\.metadata|create_all\(' "$baseline"; then
  echo "Baseline is already explicit; no generation required."
  exit 0
fi

cp "$baseline" "$original_baseline"

record_failure() {
  local stage="$1"

  cp "$original_baseline" "$baseline"

  BASELINE_FAILURE_STAGE="$stage" \
  BASELINE_FAILURE_LOG="$diagnostic_log" \
  uv run python - <<'PY'
import base64
import os
from pathlib import Path

stage = os.environ["BASELINE_FAILURE_STAGE"]
log_path = Path(os.environ["BASELINE_FAILURE_LOG"])
log = log_path.read_bytes() if log_path.exists() else b"No diagnostic output was captured."
encoded = base64.b64encode(log).decode("ascii")

Path("validate_baseline_temp.py").write_text(
    "# Temporary CI diagnostic. Remove after fixing the baseline freeze.\n"
    f"DIAGNOSTIC_STAGE = {stage!r}\n"
    f"DIAGNOSTIC_LOG_BASE64 = {encoded!r}\n",
    encoding="utf-8",
)
PY

  echo "Baseline freeze failed during: $stage"
  cat "$diagnostic_log" || true
  echo "The original baseline was restored and the diagnostic was recorded."
  exit 0
}

run_stage() {
  local stage="$1"
  shift

  set +e
  "$@" >"$diagnostic_log" 2>&1
  local status=$?
  set -e

  cat "$diagnostic_log"
  if [[ $status -ne 0 ]]; then
    record_failure "$stage"
  fi
}

uv run python - <<'PY'
import app.models  # noqa: F401
from app.shared.base_model import Base

expected = "public.user_guide_states"
if expected not in Base.metadata.tables:
    raise RuntimeError(f"ORM registry is incomplete: {expected} is not registered.")
print(f"Registered ORM tables: {len(Base.metadata.tables)}")
PY

rm "$baseline"

uv run alembic revision \
  --autogenerate \
  --rev-id 20260731_clean_baseline \
  -m "initial production baseline"

generated_file="$(find alembic/versions -maxdepth 1 -type f -name '20260731_clean_baseline*.py' -print -quit)"
test -n "$generated_file"

if [[ "$generated_file" != "$baseline" ]]; then
  mv "$generated_file" "$baseline"
fi

uv run python - <<'PY'
from pathlib import Path

path = Path("alembic/versions/20260731_clean_baseline.py")
text = path.read_text(encoding="utf-8")
downgrade_marker = "def downgrade() -> None:"
if downgrade_marker not in text:
    raise RuntimeError("Generated baseline has no downgrade function")

prefix = text.split(downgrade_marker, 1)[0].rstrip()
text = prefix + '''


def downgrade() -> None:
    """Never erase the complete Weave schema through Alembic."""

    raise RuntimeError(
        "Downgrading below the initial Weave production baseline is not "
        "supported. Restore a backup or recreate the database explicitly."
    )
'''
text = text.replace(
    '"""initial production baseline\n\nRevision ID:',
    '"""Frozen initial production baseline for Weave.\n\nRevision ID:',
    1,
)
path.write_text(text, encoding="utf-8")
PY

uv run --with ruff ruff format "$baseline"

if grep -Eq 'Base\.metadata|create_all\(|import app\.models' "$baseline"; then
  printf '%s\n' "Generated baseline still depends on live application metadata." >"$diagnostic_log"
  record_failure "dynamic-metadata guard"
fi

run_stage "alembic heads" uv run --with alembic alembic heads
run_stage "alembic upgrade head" uv run --with alembic alembic upgrade head
run_stage "alembic current" uv run --with alembic alembic current
run_stage "alembic check" uv run --with alembic alembic check

cat > /tmp/assert_baseline_tables.py <<'PY'
import asyncio

from sqlalchemy import inspect

from app.config.database import engine


async def main() -> None:
    async with engine.begin() as connection:
        tables = await connection.run_sync(
            lambda sync_connection: inspect(sync_connection).get_table_names(
                schema="public"
            )
        )
        if "user_guide_states" not in tables:
            raise RuntimeError("Frozen baseline omitted user_guide_states")
    await engine.dispose()


asyncio.run(main())
PY
run_stage \
  "required-table assertion" \
  env PYTHONPATH="$PWD" uv run python /tmp/assert_baseline_tables.py

rm -f \
  generate_explicit_baseline.py \
  tmp_generate_baseline.py \
  tmp_generate_explicit_baseline.py \
  validate_baseline_temp.py
