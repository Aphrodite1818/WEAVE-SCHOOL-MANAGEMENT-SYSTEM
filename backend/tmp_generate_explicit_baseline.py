from __future__ import annotations

from pathlib import Path
from typing import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

import app.models  # noqa: F401
from app.shared.base_model import Base

OUTPUT_PATH = Path(r"D:\DEVELOPMENT FOLDER\weave\backend\alembic\versions\20260731_clean_baseline.py")


def render_type(type_obj: sa.types.TypeEngine) -> str:
    if isinstance(type_obj, postgresql.ENUM):
        items = [repr(item) for item in type_obj.enums]
        return f"postgresql.ENUM({', '.join(items)}, name={type_obj.name!r}, schema='public')"
    if isinstance(type_obj, sa.Enum):
        items = [repr(item) for item in type_obj.enums]
        return f"sa.Enum({', '.join(items)}, name={type_obj.name!r}, schema='public')"
    if isinstance(type_obj, postgresql.UUID):
        return "postgresql.UUID(as_uuid=True)"
    if isinstance(type_obj, postgresql.JSONB):
        return "postgresql.JSONB()"
    if isinstance(type_obj, postgresql.JSON):
        return "postgresql.JSON()"
    if isinstance(type_obj, sa.ARRAY):
        return f"sa.ARRAY({render_type(type_obj.item_type)})"
    if isinstance(type_obj, sa.String):
        return f"sa.String(length={type_obj.length})" if type_obj.length else "sa.String()"
    if isinstance(type_obj, sa.Text):
        return "sa.Text()"
    if isinstance(type_obj, sa.Integer):
        return "sa.Integer()"
    if isinstance(type_obj, sa.BigInteger):
        return "sa.BigInteger()"
    if isinstance(type_obj, sa.SmallInteger):
        return "sa.SmallInteger()"
    if isinstance(type_obj, sa.Boolean):
        return "sa.Boolean()"
    if isinstance(type_obj, sa.Date):
        return "sa.Date()"
    if isinstance(type_obj, sa.DateTime):
        return "sa.DateTime(timezone=True)" if type_obj.timezone else "sa.DateTime()"
    if isinstance(type_obj, sa.Numeric):
        args = []
        if type_obj.precision is not None:
            args.append(f"precision={type_obj.precision}")
        if type_obj.scale is not None:
            args.append(f"scale={type_obj.scale}")
        return "sa.Numeric(" + ", ".join(args) + ")" if args else "sa.Numeric()"
    if isinstance(type_obj, sa.Uuid):
        return "sa.Uuid()"
    if isinstance(type_obj, sa.JSON):
        return "sa.JSON()"
    return repr(type_obj)


def render_default(default_obj: object | None) -> str | None:
    if default_obj is None:
        return None
    if hasattr(default_obj, "arg"):
        arg = default_obj.arg
    else:
        arg = default_obj
    if isinstance(arg, sa.sql.elements.TextClause):
        return f"sa.text({arg.text!r})"
    if isinstance(arg, sa.sql.elements.ClauseElement):
        return f"sa.text({str(arg)!r})"
    if isinstance(arg, sa.sql.elements.BindParameter):
        return repr(arg)
    if isinstance(arg, str):
        return repr(arg)
    if callable(arg):
        return "sa.text('NULL')"
    return repr(arg)


def render_column(column: sa.Column) -> str:
    exprs = [f"sa.Column({column.name!r}, {render_type(column.type)}"]
    if not column.nullable:
        exprs.append("nullable=False")
    if column.primary_key:
        exprs.append("primary_key=True")
    if column.unique:
        exprs.append("unique=True")
    if column.server_default is not None:
        default_expr = render_default(column.server_default)
        if default_expr is not None:
            exprs.append(f"server_default={default_expr}")
    if column.default is not None and column.server_default is None:
        default_expr = render_default(column.default)
        if default_expr is not None:
            exprs.append(f"default={default_expr}")
    if column.comment is not None:
        exprs.append(f"comment={column.comment!r}")
    exprs.append(")")
    return "        " + ", ".join(exprs)


def render_constraint_lines(table: sa.Table) -> list[str]:
    lines: list[str] = []
    for constraint in table.constraints:
        if isinstance(constraint, sa.CheckConstraint):
            lines.append(
                f"        sa.CheckConstraint({constraint.sqltext!r}, name={constraint.name!r}),"
            )
        elif isinstance(constraint, sa.UniqueConstraint):
            columns = ", ".join(repr(col.name) for col in constraint.columns)
            lines.append(
                f"        sa.UniqueConstraint({columns}, name={constraint.name!r}),"
            )
    return lines


lines: list[str] = []
lines.append('"""Frozen production baseline for Weave."""')
lines.append('')
lines.append('from __future__ import annotations')
lines.append('')
lines.append('from typing import Sequence')
lines.append('')
lines.append('import sqlalchemy as sa')
lines.append('from alembic import op')
lines.append('from sqlalchemy.dialects import postgresql')
lines.append('')
lines.append('revision: str = "20260731_clean_baseline"')
lines.append('down_revision: str | Sequence[str] | None = None')
lines.append('branch_labels: str | Sequence[str] | None = None')
lines.append('depends_on: str | Sequence[str] | None = None')
lines.append('')
lines.append('')
lines.append('def upgrade() -> None:')
lines.append('    bind = op.get_bind()')
lines.append('    if bind.dialect.name != "postgresql":')
lines.append('        raise RuntimeError("This baseline migration requires PostgreSQL")')
lines.append('')

seen_enum_names: set[str] = set()
for table in Base.metadata.sorted_tables:
    for column in table.columns:
        type_obj = column.type
        if isinstance(type_obj, (sa.Enum, postgresql.ENUM)) and type_obj.name and type_obj.name not in seen_enum_names:
            seen_enum_names.add(type_obj.name)
            enum_values = [repr(v) for v in getattr(type_obj, "enums", [])]
            lines.append(f"    op.execute(sa.text(\"CREATE TYPE {type_obj.name} AS ENUM ({', '.join(enum_values)} )\"))")
            lines.append('')

for table in Base.metadata.sorted_tables:
    if table.name == 'alembic_version':
        continue
    lines.append("    op.create_table(")
    lines.append(f"        {table.name!r},")
    for column in table.columns:
        lines.append(render_column(column) + ",")
    for constraint_line in render_constraint_lines(table):
        lines.append(constraint_line)
    lines.append("    )")
    lines.append('')

for table in Base.metadata.sorted_tables:
    if table.name == 'alembic_version':
        continue
    for index in table.indexes:
        columns = ", ".join(repr(col.name) for col in index.columns)
        lines.append(f"    op.create_index({index.name!r}, {table.name!r}, [{columns}], unique={str(index.unique).lower()})")
    lines.append('')

for table in Base.metadata.sorted_tables:
    if table.name == 'alembic_version':
        continue
    for constraint in table.foreign_key_constraints:
        if not constraint.elements:
            continue
        local_columns = ", ".join(repr(col.name) for col in constraint.columns)
        remote_column = constraint.elements[0].column.name
        remote_table = constraint.elements[0].column.table.name
        ondelete = repr(constraint.elements[0].ondelete or "NO ACTION")
        onupdate = repr(constraint.elements[0].onupdate or "NO ACTION")
        lines.append(
            f"    op.create_foreign_key({constraint.name!r}, {table.name!r}, {remote_table!r}, [{local_columns}], [{remote_column!r}], ondelete={ondelete}, onupdate={onupdate})"
        )
    lines.append('')

lines.append('')
lines.append('def downgrade() -> None:')
lines.append('    raise RuntimeError(')
lines.append('        "Downgrading below the initial Weave production baseline is not "')
lines.append('        "supported. Restore a backup or recreate the database explicitly."')
lines.append('    )')

OUTPUT_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")
print(f"Wrote {OUTPUT_PATH}")
