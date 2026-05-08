import anthropic
import json
from bigquery_client import BigQueryClient
from tools import get_tools

def run_agent(user_question: str, project_id: str, dataset_id: str):
    client = anthropic.Anthropic()
    bq = BigQueryClient(project_id)
    tools = get_tools(project_id, dataset_id)

    system_prompt = f"""Eres un analista de datos experto en BigQuery.
Dataset disponible: proyecto `{project_id}`, dataset `{dataset_id}`.

Proceso que SIEMPRE debes seguir:
1. Llama a `get_schema` para ver las tablas disponibles.
2. Construye la SQL correcta basándote en el esquema.
3. Llama a `run_sql_query` con esa SQL.
4. En tu respuesta final incluí SIEMPRE:
   - La query SQL generada en un bloque de código SQL
   - Los resultados explicados en lenguaje natural y claro

Usa Standard SQL de BigQuery con nombres completos de tabla:
`{project_id}.{dataset_id}.nombre_tabla`"""

    # ✅ Tipo correcto: list de MessageParam en lugar de list de dict genérico
    messages: list[anthropic.types.MessageParam] = [
        {"role": "user", "content": user_question}
    ]

    print(f"\n🤔 Pregunta: {user_question}\n")

    while True:
        response = client.messages.create(
            model="claude-opus-4-5",
            max_tokens=4096,
            system=system_prompt,
            tools=tools,
            messages=messages
        )

        if response.stop_reason == "end_turn":
            final_text = next(
                b.text for b in response.content if b.type == "text"
            )
            print(f"\n✅ Respuesta: {final_text}")
            return final_text

        tool_results = []
        for block in response.content:
            if block.type != "tool_use":
                continue

            tool_name = block.name
            tool_input = block.input

            if tool_name == "get_schema":
                result = bq.get_schema(dataset_id)

            elif tool_name == "run_sql_query":
                # ✅ Cast explícito a str para que Pylance no se queje
                sql = str(tool_input.get("sql", ""))
                try:
                    if not bq.is_safe_query(sql):
                        result = "Error: la query contiene operaciones no permitidas."
                    else:
                        rows = bq.run_query(sql)
                        result = json.dumps(rows[:50], default=str)
                        print(f"📊 Filas obtenidas: {len(rows)}")
                except Exception as e:
                    result = f"Error al ejecutar SQL: {e}"
            else:
                result = f"Herramienta desconocida: {tool_name}"

            tool_results.append({
                "type": "tool_result",
                "tool_use_id": block.id,
                "content": result
            })

        # ✅ Tipos correctos para el historial
        messages.append({
            "role": "assistant",
            "content": response.content  # lista de ContentBlock, no str
        })
        messages.append({
            "role": "user",
            "content": tool_results  # lista de tool_result dicts
        })


if __name__ == "__main__":
    PROJECT_ID = "uean-493522"
    DATASET_ID = "dataset_demand"

    preguntas = [
        "¿Cuáles son los 5 productos más vendidos este mes?",
    ]

    for pregunta in preguntas:
        run_agent(pregunta, PROJECT_ID, DATASET_ID)