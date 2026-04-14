from __future__ import annotations

from app.nl2sql.schema_context.models import (
    ColumnDetail,
    SchemaCatalog,
    SchemaContextFormat,
    TableDetail,
)


def format_schema_context(catalog: SchemaCatalog, fmt: SchemaContextFormat) -> str:
    if fmt == SchemaContextFormat.compact_ddl:
        return format_compact_ddl(catalog)
    if fmt == SchemaContextFormat.structured_catalog:
        return format_structured_catalog(catalog)
    if fmt == SchemaContextFormat.concise_notation:
        return format_concise_notation(catalog)
    raise ValueError(f"Unknown schema context format: {fmt}")


def format_compact_ddl(catalog: SchemaCatalog) -> str:
    blocks: list[str] = []
    relationships: list[str] = []

    for table in catalog.tables:
        blocks.append(_compact_ddl_for_table(table))
        for fk in table.foreign_keys:
            left = _qualified_column(table.schema_name, table.name, fk.column_name)
            right = _qualified_column(fk.referenced_schema, fk.referenced_table, fk.referenced_column or "")
            suffix = ""
            if fk.referenced_table == table.name and (fk.referenced_schema in (None, table.schema_name)):
                suffix = " (self-referencing)"
            relationships.append(f"-- {left} -> {right}{suffix}")

    output = "\n\n".join(blocks)
    if relationships:
        output = f"{output}\n\n-- Relationships:\n" + "\n".join(relationships)
    return output


def _compact_ddl_for_table(table: TableDetail) -> str:
    lines = [f"CREATE TABLE {table.qualified_name} ("]
    pk_cols = [col.name for col in table.columns if col.is_primary_key]
    inline_pk = len(pk_cols) == 1

    col_lines: list[str] = []
    fk_by_column = {fk.column_name: fk for fk in table.foreign_keys}

    for col in table.columns:
        col_lines.append(_compact_ddl_column_line(col, inline_pk, fk_by_column.get(col.name)))

    if not inline_pk and pk_cols:
        col_lines.append(f"  PRIMARY KEY ({', '.join(pk_cols)})")

    lines.append(",\n".join(col_lines))
    lines.append(");")
    if table.description:
        lines.insert(0, f"-- {table.description}")
    return "\n".join(lines)


def _compact_ddl_column_line(
    col: ColumnDetail,
    inline_pk: bool,
    fk,  # ForeignKeyInfo | None
) -> str:
    parts = [f"  {col.name}", col.data_type or "TEXT"]
    if col.is_primary_key and inline_pk:
        parts.append("PRIMARY KEY")
    if col.nullable is False and not (col.is_primary_key and inline_pk):
        parts.append("NOT NULL")
    if fk is not None:
        ref_table = f"{fk.referenced_schema}.{fk.referenced_table}" if fk.referenced_schema else fk.referenced_table
        ref_col = fk.referenced_column or ""
        ref = f"{ref_table}({ref_col})" if ref_col else ref_table
        parts.append(f"REFERENCES {ref}")
    return " ".join(parts)


def format_structured_catalog(catalog: SchemaCatalog) -> str:
    blocks: list[str] = []
    for table in catalog.tables:
        header = f"### {table.qualified_name}"
        if table.description:
            header += f" — {table.description}"
        lines = [header, "", "| Column | Type | PK | FK | Nullable | Description |", "|---|---|---|---|---|---|"]
        fk_by_col = {fk.column_name: fk for fk in table.foreign_keys}
        for col in table.columns:
            pk = "✓" if col.is_primary_key else ""
            fk = fk_by_col.get(col.name)
            fk_text = ""
            if fk is not None:
                ref_table = (
                    f"{fk.referenced_schema}.{fk.referenced_table}" if fk.referenced_schema else fk.referenced_table
                )
                fk_text = f"→ {ref_table}.{fk.referenced_column or ''}".rstrip(".")
            nullable = "" if col.nullable is None else ("Y" if col.nullable else "N")
            desc = col.description or ""
            lines.append(f"| {col.name} | {col.data_type or ''} | {pk} | {fk_text} | {nullable} | {desc} |")
        blocks.append("\n".join(lines))
    return "\n\n".join(blocks)


def format_concise_notation(catalog: SchemaCatalog) -> str:
    lines: list[str] = []
    for table in catalog.tables:
        fk_by_col = {fk.column_name: fk for fk in table.foreign_keys}
        col_parts: list[str] = []
        for col in table.columns:
            entry = col.name
            if col.is_primary_key:
                entry += "*"
            fk = fk_by_col.get(col.name)
            if fk is not None:
                ref_table = (
                    f"{fk.referenced_schema}.{fk.referenced_table}" if fk.referenced_schema else fk.referenced_table
                )
                entry += f"->{ref_table}"
            if col.data_type:
                entry += f":{col.data_type.lower()}"
            col_parts.append(entry)
        lines.append(f"{table.qualified_name}({', '.join(col_parts)})")
    return "\n".join(lines)


def _qualified_column(schema: str | None, table: str, column: str) -> str:
    qualified_table = f"{schema}.{table}" if schema else table
    return f"{qualified_table}.{column}" if column else qualified_table


def estimate_tokens(text: str) -> int:
    """Rough GPT-style token estimate: 1 token ≈ 4 chars."""
    return len(text) // 4
