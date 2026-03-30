from pydantic import BaseModel


class ColumnInfo(BaseModel):
    column_name: str
    sample_values: list  # list of distinct non-null values, up to 3; empty list if none


class TableInfo(BaseModel):
    table_name: str
    row_count: int
    columns: list[ColumnInfo]


class SchemaInfoResponse(BaseModel):
    tables: list[TableInfo]
