import asyncio
import os
import subprocess
import sys
from pathlib import Path

import asyncpg

DB_NAME = 'weave_baseline_tmp'
POSTGRES_DSN = 'postgresql://postgres:252236@localhost:5433/postgres'
BACKEND_DIR = Path(r'D:\DEVELOPMENT FOLDER\weave\backend')

async def main() -> None:
    conn = await asyncpg.connect(dsn=POSTGRES_DSN)
    try:
        await conn.execute(f'DROP DATABASE IF EXISTS {DB_NAME}')
        await conn.execute(f'CREATE DATABASE {DB_NAME}')
    finally:
        await conn.close()

    env = os.environ.copy()
    env['DATABASE_URL'] = f'postgresql+asyncpg://postgres:252236@localhost:5433/{DB_NAME}'
    env['PYTHONPATH'] = str(BACKEND_DIR)

    result = subprocess.run(
        [sys.executable, '-m', 'alembic', 'stamp', '20260731_clean_baseline'],
        cwd=BACKEND_DIR,
        env=env,
        capture_output=True,
        text=True,
    )
    print('stamp returncode', result.returncode)
    print('stamp stdout:\n', result.stdout)
    print('stamp stderr:\n', result.stderr)

    result = subprocess.run(
        [sys.executable, '-m', 'alembic', 'revision', '--autogenerate', '-m', 'tmp_baseline_generation'],
        cwd=BACKEND_DIR,
        env=env,
        capture_output=True,
        text=True,
    )
    print('revision returncode', result.returncode)
    print('revision stdout:\n', result.stdout)
    print('revision stderr:\n', result.stderr)

    versions_dir = BACKEND_DIR / 'alembic' / 'versions'
    generated_files = sorted(p for p in versions_dir.glob('*tmp_baseline_generation.py'))
    for path in generated_files:
        print('generated', path.name)
        print(path.read_text(encoding='utf-8'))

asyncio.run(main())
