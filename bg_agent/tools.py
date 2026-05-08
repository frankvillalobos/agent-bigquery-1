def get_tools(project_id: str, dataset_id: str) -> list:
    return [
        {
            "name": "get_schema",
            "description": (
                "Obtiene el esquema del dataset de BigQuery: tablas y columnas disponibles. "
                "Llamar esto PRIMERO antes de generar cualquier SQL."
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
                "Ejecuta una query SQL en BigQuery y retorna los resultados. "
                f"El proyecto es `{project_id}` y el dataset es `{dataset_id}`."
            ),
            "input_schema": {
                "type": "object",
                "properties": {
                    "sql": {
                        "type": "string",
                        "description": "Query SQL válida para BigQuery Standard SQL."
                    }
                },
                "required": ["sql"]
            }
        }
    ]