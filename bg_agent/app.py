from dotenv import load_dotenv
load_dotenv()

import streamlit as st
import json
from openai import OpenAI
from bigquery_client import BigQueryClient

# ── Configuración de página ───────────────────────────────────────────────────
st.set_page_config(
    page_title="RevOps Agent",
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
    st.image("bg_agent/assets/jeeves_logo.png", width=120)
with col2:
    st.title("RevOps Query Assistant Agent")
    st.caption("I'll help you write a SQL Query")

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

Process you MUST ALWAYS follow:
1. Call get_schema to see the available tables.
2. Build the correct SQL based on the schema.
3. Call run_sql_query with that SQL.
4. In your final response ALWAYS include:
   - The SQL query generated in a SQL code block
   - The results explained in clear natural language

Use BigQuery Standard SQL with full table names:
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
if prompt := st.chat_input("Ex: What '%' of annual quota has each country achieved through closed-won deals?"):

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
    st.markdown("**Example Queries:**")
    st.markdown("- What % of annual quota has each country achieved through closed-won deals?")
    st.markdown("- Which channel closes the highest percentage of deals?")
    st.markdown("- Columns available: deal_id, country, segment, channel, rep_name, hire_date, partner_type, deal_stage, close_date, create_date, sales_cycle_days, acv_usd, tpv_usd, is_won, lost_reason, quarter, month, monthly_quota_usd, annual_quota_usd, ramp_factor")

    st.divider()
    if st.button("🗑️ Clear conversation"):
        st.session_state.messages = []
        st.session_state.api_messages = []
        st.rerun()