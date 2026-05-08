from google.cloud import bigquery
from google.oauth2 import service_account
import streamlit as st

class BigQueryClient:

    def __init__(self, project_id: str):
        if "gcp_service_account" in st.secrets:
            credentials = service_account.Credentials.from_service_account_info(
                st.secrets["gcp_service_account"]
            )
            self.client = bigquery.Client(
                project=project_id,
                credentials=credentials
            )
        else:
            self.client = bigquery.Client(project=project_id)

        self.project_id = project_id

    @staticmethod
    def is_safe_query(sql: str) -> bool:
        forbidden = ["DROP", "DELETE", "UPDATE", "INSERT", "ALTER"]
        return not any(kw in sql.upper() for kw in forbidden)

    def get_schema(self, dataset_id: str) -> str:
        tables = self.client.list_tables(dataset_id)
        schema_text = []

        for table_ref in tables:
            table = self.client.get_table(table_ref)
            table_desc = f" — {table.description}" if table.description else ""
            schema_text.append(f"\nTabla `{table.table_id}`{table_desc}:")

            for field in table.schema:
                col_desc = f" → {field.description}" if field.description else ""
                schema_text.append(
                    f"  - {field.name} ({field.field_type}){col_desc}"
                )

        return "\n".join(schema_text)

    def run_query(self, sql: str) -> list[dict]:
        query_job = self.client.query(sql)
        results = query_job.result()
        return [dict(row) for row in results]