from dotenv import load_dotenv
load_dotenv()

import streamlit as st
import json
from openai import OpenAI
from bigquery_client import BigQueryClient
from tools import get_tools

# ── Configuración ────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Agente BigQuery",
    page_icon="🔍",
    layout="wide"
)

PROJECT_ID = "uean-493522"
DATASET_ID = "dataset_demand"

st.title("🔍 Agente de consultas BigQuery")
st.caption("Hacé preguntas en español y el agente genera y ejecuta el SQL por vos.")

# ── Historial de chat ────────────────────────────────────────────────────────
if "messages" not in st.session_state:
    st.session_state.messages = []

if "api_messages" not in st.session_state:
    st.session_state.api_messages = []

for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

# ── Función del agente ───────────────────────────────────────────────────────
def run_agent(user_question: str) -> str:
    client = OpenAI()  # lee OPENAI_API_KEY del .env automáticamente
    bq = BigQueryClient(PROJECT_ID)
    tools = get_tools_openai(PROJECT_ID, DATASET_ID)

    system_prompt = f"""Eres un analista de datos experto en BigQuery.
Dataset disponible: proyecto `{PROJECT_ID}`, dataset `{DATASET_ID}`.

Proceso que SIEMPRE debes seguir:
1. Llama a get_schema para ver las tablas disponibles.
2. Construye la SQL correcta basándote en el esquema.
3. Llama a run_sql_query con esa SQL.
4. En tu respuesta final incluí SIEMPRE:
   - La query SQL generada en un bloque de código SQL
   - Los resultados explicados en lenguaje natural y claro

Usa Standard SQL de BigQuery con nombres completos:
`{PROJECT_ID}.{DATASET_ID}.nombre_tabla`"""

    st.session_state.api_messages.append({
        "role": "user",
        "content": user_question
    })

    messages = [
        {"role": "system", "content": system_prompt}
    ] + st.session_state.api_messages

    with st.status("⚙️ El agente está trabajando...", expanded=True) as status:

        while True:
            response = client.chat.completions.create(
                model="gpt-5.4-nano",   # o "gpt-4-turbo" si preferís
                messages=messages,
                tools=tools,
                tool_choice="auto"
            )

            msg = response.choices[0].message

            # El modelo terminó — no quiere usar más herramientas
            if not msg.tool_calls:
                status.update(
                    label="✅ Listo",
                    state="complete",
                    expanded=False
                )
                return msg.content or ""

            # El modelo quiere usar herramientas
            # Agregamos su respuesta al historial
            messages.append(msg)

            for tool_call in msg.tool_calls:
                fn = getattr(tool_call, "function", None)
                if fn is None:
                        continue
                tool_name = fn.name
                tool_input = json.loads(fn.arguments)

                if tool_name == "get_schema":
                    st.write("📋 Leyendo esquema del dataset...")
                    result = bq.get_schema(DATASET_ID)

                elif tool_name == "run_sql_query":
                    sql = tool_input.get("sql", "")
                    st.write("🚀 Ejecutando query en BigQuery...")
                    st.code(sql, language="sql")

                    try:
                        if not BigQueryClient.is_safe_query(sql):
                            result = "Error: query no permitida."
                            st.error(result)
                        else:
                            rows = bq.run_query(sql)
                            result = json.dumps(rows[:50], default=str)
                            st.write(f"📊 {len(rows)} filas obtenidas.")
                    except Exception as e:
                        result = f"Error al ejecutar SQL: {e}"
                        st.error(result)
                else:
                    result = f"Herramienta desconocida: {tool_name}"

                # Agregar resultado de la herramienta al historial
                messages.append({
                    "role": "tool",
                    "tool_call_id": tool_call.id,
                    "content": result
                })

    return ""

# ── Formato de tools para OpenAI ─────────────────────────────────────────────
def get_tools_openai(project_id: str, dataset_id: str) -> list:
    return [
        {
            "type": "function",
            "function": {
                "name": "get_schema",
                "description": (
                    "Obtiene el esquema del dataset de BigQuery: tablas y columnas. "
                    "Llamar esto PRIMERO antes de generar cualquier SQL."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {},
                    "required": []
                }
            }
        },
        {
            "type": "function",
            "function": {
                "name": "run_sql_query",
                "description": (
                    f"Ejecuta una query SQL en BigQuery. "
                    f"Proyecto: `{project_id}`, dataset: `{dataset_id}`."
                ),
                "parameters": {
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
        }
    ]

# ── Input del usuario ────────────────────────────────────────────────────────
if prompt := st.chat_input("Ej: ¿Cuáles son los 5 productos más vendidos?"):

    with st.chat_message("user"):
        st.markdown(prompt)

    st.session_state.messages.append({
        "role": "user",
        "content": prompt
    })

    with st.chat_message("assistant"):
        answer = run_agent(prompt)
        st.markdown(answer)

    st.session_state.messages.append({
        "role": "assistant",
        "content": answer
    })

# ── Sidebar ──────────────────────────────────────────────────────────────────
with st.sidebar:
    st.header("⚙️ Configuración")
    st.info(f"**Proyecto:** {PROJECT_ID}\n\n**Dataset:** {DATASET_ID}")

    st.divider()
    st.markdown("**Ejemplos de preguntas:**")
    st.markdown("- ¿Cuántas ventas hubo este mes?")
    st.markdown("- ¿Cuál es el producto más caro?")
    st.markdown("- ¿Qué región vende más?")

    st.divider()
    if st.button("🗑️ Limpiar conversación"):
        st.session_state.messages = []
        st.session_state.api_messages = []
        st.rerun()