import anthropic
import json
from bigquery_client import BigQueryClient
from tools import get_tools

def run_agent(user_question: str, project_id: str, dataset_id: str):
    client = anthropic.Anthropic()
    bq = BigQueryClient(project_id)
    tools = get_tools(project_id, dataset_id)

    system_prompt = f"""Eres un experto en análisis de datos inmobiliarios en BigQuery.
Dataset disponible: project `{project_id}`, dataset `{dataset_id}`.

Proceso que SIEMPRE debes seguir:
1. Llamar `get_schema` para ver las tablas disponibles.
2. Construir la query SQL correcta en base al schema.
3. Llamar `run_sql_query` con ese SQL.
4. En tu respuesta final, SIEMPRE incluey:
   - La query SQL generada en un bloque de código SQL

Usa BigQuery estándar SQL con los nombres de las tablas correctamente: 
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
                        result = "Error: La query contiene operaciones no permitidas"
                    else:
                        rows = bq.run_query(sql)
                        result = json.dumps(rows[:50], default=str)
                        print(f"📊 Rows obtained: {len(rows)}")
                except Exception as e:
                    result = f"Error ejecutando SQL: {e}"
            else:
                result = f"Unknown tool: {tool_name}"

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
        "¿Cuántos leads se generaron en Buenos Aires el mes pasado?",
    ]

    for pregunta in preguntas:
        run_agent(pregunta, PROJECT_ID, DATASET_ID)