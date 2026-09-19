from dotenv import load_dotenv
load_dotenv()

import streamlit as st
import json
from openai import OpenAI
from bigquery_client import BigQueryClient

# ── Configuración de página ───────────────────────────────────────────────────
st.set_page_config(
    page_title="Asistente de SQL",
    page_icon="🔍",
    layout="wide"
)

# ── CSS personalizado ─────────────────────────────────────────────────────────
st.markdown("""
    <style>
        /* Texto del sidebar en negro (sobreescribe el blanco global) */
        [data-testid="stSidebar"] * {
            color: #000000 !important;
        }
        /* Texto del input del chat en negro */
        [data-testid="stChatInput"] textarea {
            color: #000000 !important;
        }
        /* Respuesta del asistente en blanco */
        [data-testid="stChatMessage"] p {
            color: #FFFFFF !important;
        }
    </style>
""", unsafe_allow_html=True)

# ── Logo y título  ←  AQUÍ, fuera del set_page_config ────────────────────────
col1, col2 = st.columns([1, 5])
with col1:
    st.image("bg_agent/assets/logo-zpa.webp", width=120)
with col2:
    st.title("Asistente de SQL")
    st.caption("Te ayudaré a escribir un código SQL!")

PROJECT_ID = "uean-493522"
DATASET_ID = "dataset_demand"

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
    client = OpenAI()
    bq = BigQueryClient(PROJECT_ID)
    tools = get_tools_openai(PROJECT_ID, DATASET_ID)

    system_prompt = f"""You are an expert data analyst in BigQuery.
Available dataset: project `{PROJECT_ID}`, dataset `{DATASET_ID}`.

Proceso que SIEMPRE debes seguir:
1. Llamar `get_schema` para ver las tablas disponibles.
2. Construir la query SQL correcta en base al schema.
3. Llamar `run_sql_query` con ese SQL.
4. En tu respuesta final, SIEMPRE incluey:
   - La query SQL generada en un bloque de código SQL

Usa BigQuery estándar SQL con los nombres de las tablas correctamente: 
`{PROJECT_ID}.{DATASET_ID}.table_name`"""

    st.session_state.api_messages.append({
        "role": "user",
        "content": user_question
    })

    messages = [
        {"role": "system", "content": system_prompt}
    ] + st.session_state.api_messages

    with st.status("⚙️ Agent is working...", expanded=True) as status:

        while True:
            response = client.chat.completions.create(
                model="gpt-4o",
                messages=messages,
                tools=tools,
                tool_choice="auto"
            )

            msg = response.choices[0].message

            if not msg.tool_calls:
                status.update(label="✅ Done", state="complete", expanded=False)
                return msg.content or ""

            messages.append(msg)

            for tool_call in msg.tool_calls:
                fn = getattr(tool_call, "function", None)
                if fn is None:
                    continue
                tool_name = fn.name
                tool_input = json.loads(fn.arguments)

                if tool_name == "get_schema":
                    st.write("📋 Reading dataset schema...")
                    result = bq.get_schema(DATASET_ID)

                elif tool_name == "run_sql_query":
                    sql = tool_input.get("sql", "")
                    st.write("🚀 Running query in BigQuery...")
                    st.code(sql, language="sql")

                    try:
                        if not BigQueryClient.is_safe_query(sql):
                            result = "Error: query not allowed."
                            st.error(result)
                        else:
                            rows = bq.run_query(sql)
                            result = json.dumps(rows[:50], default=str)
                            st.write(f"📊 {len(rows)} rows retrieved.")
                    except Exception as e:
                        result = f"Error running SQL: {e}"
                        st.error(result)
                else:
                    result = f"Unknown tool: {tool_name}"

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
                    "Gets the BigQuery dataset schema: tables and columns. "
                    "Call this FIRST before generating any SQL."
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
                    f"Executes a SQL query in BigQuery. "
                    f"Project: `{project_id}`, dataset: `{dataset_id}`."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "sql": {
                            "type": "string",
                            "description": "Valid BigQuery Standard SQL query."
                        }
                    },
                    "required": ["sql"]
                }
            }
        }
    ]

# ── Input del usuario ────────────────────────────────────────────────────────
if prompt := st.chat_input("Ejemplo: ¿Cuántos leads se generaron en Buenos Aires en enero?"):

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
    st.divider()
    st.markdown("**Ejemplos:**")
    st.markdown("- ¿Cómo calcular el Conversion Rate?")
    st.markdown("- ¿En qué ciudades hay más leads?")


    st.divider()
    if st.button("🗑️ Clear conversation"):
        st.session_state.messages = []
        st.session_state.api_messages = []
        st.rerun()