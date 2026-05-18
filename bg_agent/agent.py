import anthropic
import json
from bigquery_client import BigQueryClient
from tools import get_tools

def run_agent(user_question: str, project_id: str, dataset_id: str):
    client = anthropic.Anthropic()
    bq = BigQueryClient(project_id)
    tools = get_tools(project_id, dataset_id)

    system_prompt = f"""You are an expert data analyst in BigQuery.
Dataset available: project `{project_id}`, dataset `{dataset_id}`.

Process you should ALWAYS follow:
1. Call `get_schema` to see the available tables.
2. Build the correct SQL based on the schema.
3. Call `run_sql_query` with that SQL.
4. In your final answer, ALWAYS include:
   - The SQL query generated in a block of SQL code
   - The results explained in natural and clear language

Use BigQuery Standard SQL with fully qualified table names:
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
                        result = "Error: The query contains disallowed operations."
                    else:
                        rows = bq.run_query(sql)
                        result = json.dumps(rows[:50], default=str)
                        print(f"📊 Rows obtained: {len(rows)}")
                except Exception as e:
                    result = f"Error executing SQL: {e}"
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
        "What percentage of annual quota has each country achieved through closed-won deals?",
    ]

    for pregunta in preguntas:
        run_agent(pregunta, PROJECT_ID, DATASET_ID)