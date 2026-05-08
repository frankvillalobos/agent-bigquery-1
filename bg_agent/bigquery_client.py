from google.cloud import bigquery

class BigQueryClient:

    def __init__(self, project_id: str):
        self.client = bigquery.Client(project=project_id)
        self.project_id = project_id

    # ✅ @staticmethod: pertenece a la clase pero no necesita self
    @staticmethod
    def is_safe_query(sql: str) -> bool:
        forbidden = ["DROP", "DELETE", "UPDATE", "INSERT", "ALTER"]
        return not any(kw in sql.upper() for kw in forbidden)

    def get_schema(self, dataset_id: str) -> str:
        tables = self.client.list_tables(dataset_id)
        schema_text = []
        for table_ref in tables:
            table = self.client.get_table(table_ref)
            fields = ", ".join(
                f"{f.name} ({f.field_type})" for f in table.schema
            )
            schema_text.append(f"Tabla `{table.table_id}`: {fields}")
        return "\n".join(schema_text)

    def run_query(self, sql: str) -> list[dict]:
        query_job = self.client.query(sql)
        results = query_job.result()
        return [dict(row) for row in results]