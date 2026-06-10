"""
app.py — Kira, AI-powered SRE assistant for your GKE boutique cluster.

Architecture:
    Streamlit UI  →  Gemini on Vertex AI (brain, decides what to investigate)
                       ├── fetch_logs()    → GCP Cloud Logging
                       ├── fetch_metrics() → Prometheus on GKE
                       └── fetch_health()  → Kubernetes pod/node API

Auth model:
    - No Gemini API key is required.
    - Uses GCP Application Default Credentials (ADC):
            gcloud auth application-default login

Run:
  streamlit run app.py
Then open: http://localhost:8501
"""

import os
import streamlit as st
from dotenv import load_dotenv
import vertexai
from vertexai.generative_models import GenerativeModel, Tool, FunctionDeclaration, Part

from tools import fetch_logs, fetch_metrics, fetch_health

# ─────────────────────────────────────────────────────────────────────────────
# Load .env file (GCP_PROJECT_ID, GCP_REGION, PROMETHEUS_URL)
# ─────────────────────────────────────────────────────────────────────────────
load_dotenv(override=True)  # override=True ensures .env always wins

GCP_PROJECT_ID = os.environ.get("GCP_PROJECT_ID", "")
GCP_REGION     = os.environ.get("GCP_REGION", "us-central1")
PROMETHEUS_URL = os.environ.get("PROMETHEUS_URL", "http://localhost:9090")
GEMINI_MODEL   = os.environ.get("GEMINI_MODEL", "gemini-2.5-flash")

VERTEX_READY = False
VERTEX_INIT_ERROR = ""

if GCP_PROJECT_ID:
    try:
        vertexai.init(project=GCP_PROJECT_ID, location=GCP_REGION)
        VERTEX_READY = True
    except Exception as e:
        VERTEX_INIT_ERROR = str(e)

# ─────────────────────────────────────────────────────────────────────────────
# System prompt — tells Gemini who it is and how to behave
# ─────────────────────────────────────────────────────────────────────────────
SYSTEM_PROMPT = """You are Kira, an expert Site Reliability Engineer (SRE) AI assistant.
You specialize in diagnosing and fixing production incidents on Google Kubernetes Engine (GKE).

The system you monitor is a boutique e-commerce app with these 7 microservices:
  - frontend      : React UI
  - gateway       : Routes all incoming requests to backend services
  - auth          : Handles login and user authentication
  - product-service : Product catalog and inventory
  - order-service : Shopping cart and checkout
  - orders        : Order history and management
  - user-service  : User profiles and account data
  - boutique-postgres : PostgreSQL database (stores auth_db, products_db, orders_db, users_db)

All services run in the 'boutique' namespace on GKE.

You have 3 tools available:
  1. fetch_logs    — Read application logs from GCP Cloud Logging
  2. fetch_metrics — Query Prometheus for CPU, memory, HTTP error rates
  3. fetch_health  — Check Kubernetes pod and node health status

HOW TO RESPOND:
  - ALWAYS use your tools to gather real data before answering
  - Call multiple tools when needed to get the full picture
  - After gathering data, structure your answer as:
      🔎 Root Cause: (what went wrong)
      📋 Evidence: (specific data from logs/metrics/pods)
      🔧 Fix: (exact steps to resolve it)
  - Reference actual pod names, error messages, and values from the data
  - Be concise and actionable — engineers need answers fast during incidents

If a tool returns an error (e.g., Prometheus unreachable), mention it clearly but
still answer using the data you have from the other tools.
"""

# ─────────────────────────────────────────────────────────────────────────────
# Tool schema — tells Gemini what tools it can call and what arguments they take
# ─────────────────────────────────────────────────────────────────────────────
TOOL_SCHEMA = Tool(
    function_declarations=[

        FunctionDeclaration(
            name="fetch_logs",
            description=(
                "Fetch recent application logs from GCP Cloud Logging for the boutique app on GKE. "
                "Use this to investigate errors, crashes, 5xx HTTP responses, exceptions, "
                "database connection issues, or any unexpected behavior in the services."
            ),
            parameters={
                "type": "object",
                "properties": {
                    "service_name": {
                        "type": "string",
                        "description": (
                            "Name of the service to filter logs. "
                            "One of: gateway, auth, product-service, order-service, orders, user-service, frontend. "
                            "Leave empty to fetch logs from ALL services."
                        ),
                    },
                    "minutes": {
                        "type": "integer",
                        "description": "How many minutes back to search. Default: 60",
                    },
                    "severity": {
                        "type": "string",
                        "description": "Minimum log severity: ERROR, WARNING, or INFO. Default: ERROR",
                    },
                },
            },
        ),

        FunctionDeclaration(
            name="fetch_metrics",
            description=(
                "Fetch real-time metrics from Prometheus running on GKE. "
                "Use this to check CPU usage, memory consumption, HTTP request rates, "
                "error rates, response times, and pod resource utilization. "
                "Provide an empty query for a full health overview."
            ),
            parameters={
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": (
                            "PromQL query string. "
                            "Example: 'sum(rate(http_requests_total[5m])) by (service)'. "
                            "Leave empty for a default overview across all boutique services."
                        ),
                    },
                },
            },
        ),

        FunctionDeclaration(
            name="fetch_health",
            description=(
                "Check the real-time health status of all pods and nodes in the boutique GKE namespace. "
                "Use this to find crashing pods, OOMKilled containers, CrashLoopBackOff errors, "
                "pending pods, high restart counts, or node capacity issues. "
                "This is the first thing to check when something seems down."
            ),
            parameters={"type": "object", "properties": {}},
        ),

    ]
)

# Map function names to actual Python functions
TOOL_MAP = {
    "fetch_logs":    fetch_logs,
    "fetch_metrics": fetch_metrics,
    "fetch_health":  fetch_health,
}


def execute_tool(name: str, args: dict) -> str:
    """Call the right tool function with the args Gemini decided to pass."""
    fn = TOOL_MAP.get(name)
    if not fn:
        return f"Unknown tool: {name}"
    try:
        return fn(**args)
    except TypeError as e:
        return f"Tool call error ({name}): {str(e)}"
    except Exception as e:
        return f"Tool error ({name}): {type(e).__name__}: {str(e)}"


def run_kira(user_question: str, chat_history: list) -> tuple[str, list]:
    """
    Main agent loop:
      1. Send user question to Gemini
      2. If Gemini calls a tool → execute it → send result back
      3. Repeat until Gemini returns a text answer
      4. Return (final_answer, updated_history)
    """
    if not GCP_PROJECT_ID:
        return (
            "❌ **GCP_PROJECT_ID not set.**\n\n"
            "1. Add this to `aiops-gcp-assistant/.env`:\n"
            "   ```\n   GCP_PROJECT_ID=your-project-id\n   GCP_REGION=us-central1\n   ```\n"
            "2. Run `gcloud auth application-default login` (no API key needed)\n"
            "3. Restart the app.",
            chat_history,
        )

    if not VERTEX_READY:
        return (
            "❌ **Vertex AI initialization failed.**\n\n"
            f"Error: `{VERTEX_INIT_ERROR or 'Unknown error'}`\n\n"
            "Check:\n"
            "1. `GCP_PROJECT_ID` and `GCP_REGION` in `.env`\n"
            "2. `gcloud auth application-default login`\n"
            "3. Vertex AI API is enabled in your GCP project",
            chat_history,
        )


    model = GenerativeModel(
        model_name=GEMINI_MODEL,
        tools=[TOOL_SCHEMA],
        system_instruction=SYSTEM_PROMPT,
    )

    chat = model.start_chat()

    # Track which tools were called (shown in UI)
    tool_calls_log = []

    # Send the user message
    try:
        if chat_history:
            compact_history = "\n".join(
                [f"{m['role'].upper()}: {m['content']}" for m in chat_history[-6:]]
            )
            prompt = f"Conversation so far:\n{compact_history}\n\nNew question:\n{user_question}"
        else:
            prompt = user_question

        response = chat.send_message(prompt)
    except Exception as e:
        err = str(e)
        if "429" in err or "quota" in err.lower() or "rate" in err.lower() or "resource_exhausted" in err.lower():
            return (
                f"⚠️ **Gemini/Vertex quota exceeded** (model currently in use: `{GEMINI_MODEL}`).\n\n"
                f"**Try this in `.env` first:**\n"
                f"```\n"
                f"GEMINI_MODEL=gemini-1.5-flash-002\n"
                f"# or\n"
                f"GEMINI_MODEL=gemini-2.0-flash-001\n"
                f"```\n\n"
                f"After saving `.env`, restart: `Ctrl+C` then `streamlit run app.py`",
                chat_history,
            )
        return f"❌ Gemini/Vertex API error: {err}", chat_history

    # ── Agentic loop ──────────────────────────────────────────────────────────
    # Gemini may call tools multiple times before giving a final text answer.
    # We keep looping until there are no more function calls.
    max_iterations = 6
    for _ in range(max_iterations):
        response_parts_raw = []
        if getattr(response, "candidates", None):
            if response.candidates and response.candidates[0].content:
                response_parts_raw = response.candidates[0].content.parts or []

        function_calls = [
            part.function_call
            for part in response_parts_raw
            if getattr(part, "function_call", None) and part.function_call.name
        ]

        if not function_calls:
            break  # Gemini returned a final text answer

        # Execute every function call Gemini requested
        response_parts = []
        for fc in function_calls:
            tool_name = fc.name
            tool_args = dict(fc.args) if fc.args else {}

            # Log for display
            args_str = ", ".join(f"{k}={repr(v)}" for k, v in tool_args.items())
            tool_calls_log.append(f"🔍 `{tool_name}({args_str or ''})`")

            # Run the tool
            result = execute_tool(tool_name, tool_args)

            response_parts.append(Part.from_function_response(name=tool_name, response={"result": result}))

        # Send all tool results back to Gemini
        response = chat.send_message(response_parts)

    # ── Extract final text ────────────────────────────────────────────────────
    final_text_chunks = []
    if getattr(response, "candidates", None):
        if response.candidates and response.candidates[0].content:
            for part in (response.candidates[0].content.parts or []):
                if getattr(part, "text", None):
                    final_text_chunks.append(part.text)

    final_text = "".join(final_text_chunks)

    if not final_text:
        final_text = "I wasn't able to generate a response. Please try again."

    # Prepend tool call summary so users can see what Kira checked
    if tool_calls_log:
        tool_summary = "**Kira checked:**\n" + "\n".join(tool_calls_log) + "\n\n---\n\n"
        final_text = tool_summary + final_text

    updated_history = chat_history + [
        {"role": "user",      "content": user_question},
        {"role": "assistant", "content": final_text},
    ]

    return final_text, updated_history


# ─────────────────────────────────────────────────────────────────────────────
# Streamlit UI
# ─────────────────────────────────────────────────────────────────────────────

st.set_page_config(
    page_title="Kira — GKE AIOps",
    page_icon="🤖",
    layout="wide",
)

st.title("🤖 Kira — GKE AIOps Assistant")
st.caption("AI-powered SRE for your Boutique app on GKE  |  Powered by Gemini on Vertex AI")

# ── Sidebar ───────────────────────────────────────────────────────────────────
with st.sidebar:
    st.header("⚙️ Status")

    # Show config health at a glance
    st.write("**Vertex Auth:**",     "✅ Ready" if VERTEX_READY else "❌ Not ready")
    st.write("**GCP Project:**",     f"✅ `{GCP_PROJECT_ID}`" if GCP_PROJECT_ID else "❌ Not set")
    st.write("**GCP Region:**",      f"`{GCP_REGION}`")
    st.write("**Prometheus URL:**",  f"`{PROMETHEUS_URL}`")
    st.write("**Model:**",           f"`{GEMINI_MODEL}`")

    if not GCP_PROJECT_ID or not VERTEX_READY:
        st.warning(
            "Set `.env` and Vertex auth, then restart.\n\n"
            "1. `GCP_PROJECT_ID` and `GCP_REGION` in `.env`\n"
            "2. `gcloud auth application-default login`"
        )

    st.divider()
    st.header("💬 Try asking...")

    example_questions = [
        "Are all pods healthy?",
        "Check everything — give me a full health report",
        "Why are users seeing errors?",
        "Any pods crashing or restarting?",
        "What is the CPU and memory usage?",
        "Check the gateway service logs",
        "Is the database healthy?",
        "What's the HTTP error rate right now?",
        "Why is the product page not loading?",
    ]

    for q in example_questions:
        if st.button(q, use_container_width=True, key=f"btn_{q[:20]}"):
            st.session_state["pending_question"] = q

    st.divider()
    if st.button("🗑️ Clear chat", use_container_width=True):
        st.session_state.messages = []
        st.session_state.history = []
        st.rerun()

# ── Session state init ────────────────────────────────────────────────────────
if "messages" not in st.session_state:
    st.session_state.messages = []
if "history" not in st.session_state:
    st.session_state.history = []

# ── Display existing messages ─────────────────────────────────────────────────
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

# ── Handle sidebar button OR typed input ─────────────────────────────────────
pending = st.session_state.pop("pending_question", None)
user_input = st.chat_input("Ask Kira about your GKE cluster...") or pending

if user_input:
    # Show user message immediately
    with st.chat_message("user"):
        st.markdown(user_input)
    st.session_state.messages.append({"role": "user", "content": user_input})

    # Call the agent and stream the response
    with st.chat_message("assistant"):
        with st.spinner("Kira is investigating your cluster..."):
            answer, new_history = run_kira(user_input, st.session_state.history)
        st.markdown(answer)

    st.session_state.messages.append({"role": "assistant", "content": answer})
    st.session_state.history = new_history
