#!/usr/bin/env bash
set -euo pipefail

baseline="alembic/versions/20260731_clean_baseline.py"

if ! grep -Eq 'Base\.metadata|create_all\(' "$baseline"; then
  echo "Baseline is already explicit; no generation required."
  exit 0
fi

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
  echo "Generated baseline still depends on live application metadata."
  exit 1
fi

rm -f \
  generate_explicit_baseline.py \
  tmp_generate_baseline.py \
  tmp_generate_explicit_baseline.py \
  validate_baseline_temp.py

uv run --with alembic alembic heads
uv run --with alembic alembic upgrade head
uv run --with alembic alembic current
uv run --with alembic alembic check

uv run python - <<'PY'
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
