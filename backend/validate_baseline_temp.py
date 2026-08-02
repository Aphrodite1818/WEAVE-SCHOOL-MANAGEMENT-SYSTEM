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

    for args in [
        [sys.executable, '-m', 'alembic', 'upgrade', 'head'],
        [sys.executable, '-m', 'alembic', 'current'],
        [sys.executable, '-m', 'alembic', 'check'],
    ]:
        result = subprocess.run(args, cwd=BACKEND_DIR, env=env, capture_output=True, text=True)
        print('$', ' '.join(args))
        print('returncode', result.returncode)
        print(result.stdout)
        if result.stderr:
            print(result.stderr)
        print('---')

asyncio.run(main())
