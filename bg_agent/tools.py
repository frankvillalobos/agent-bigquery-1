def get_tools(project_id: str, dataset_id: str) -> list:
    return [
        {
            "name": "get_schema",
            "description": (
                "Gets the BigQuery dataset schema: available tables and columns."
                "Call this FIRST before generating any SQL."
            ),
            "input_schema": {
                "type": "object",
                "properties": {},
                "required": []
            }
        },
        {
            "name": "run_sql_query",
            "description": (
                "Execute an SQL query in BigQuery and return the results."
                f"The Project is `{project_id}` and the dataset is `{dataset_id}`."
            ),
            "input_schema": {
                "type": "object",
                "properties": {
                    "sql": {
                        "type": "string",
                        "description": "Valid SQL query for BigQuery Standard SQL."
                    }
                },
                "required": ["sql"]
            }
        }
    ]