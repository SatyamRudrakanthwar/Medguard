# MedGuard — Demo Recording Script

**Target duration: 2 minutes 45 seconds – 3 minutes**

---

## Before You Start

Have these open and ready:

| Tab | What |
|---|---|
| Editor tab 1 | `backend/app/graph/graph.py` |
| Editor tab 2 | `backend/app/models/state.py` |
| Editor tab 3 | `backend/app/mcp/tools/drug_information.py` |
| Editor tab 4 | `backend/app/graph/nodes/validate_evidence.py` |
| Terminal | Backend running on :8000, frontend on :5173 |
| Browser tab | Frontend with the demo case already typed in |
| Browser tab | Langfuse → Tracing |

**Demo case — type this in the frontend before you start recording, do not submit yet:**

```
Medications : Warfarin  /  Aspirin  /  Ibuprofen
Age         : 72
Conditions  : atrial fibrillation, hypertension
Question    : Are there any bleeding risks with this combination?
```

> This combination guarantees multiple high-severity findings and is likely to trigger the evidence retry loop — the most interesting thing to show live.

Do **not** show the React UI components, Tailwind, Docker setup, or PostgreSQL schema. The goal is to show the orchestration logic.

---

## 0:00 – 0:20 · Introduction + Architecture

**Screen:** `backend/app/graph/graph.py` — the docstring at the top is your diagram.

**Say:**

> "I built MedGuard — a medication-safety research platform.
>
> It uses LangGraph to orchestrate the workflow, MCP for controlled tool access, RAG for evidence retrieval, and Langfuse for observability.
>
> The important part is that this isn't a single LLM call. It's a stateful workflow with dedicated reasoning and validation stages."

*(point at the flow comment in the docstring)*

> "The flow is: validate, normalize, analyze the case, create a research plan, execute research, validate the evidence, analyze risk, generate the report."

---

## 0:20 – 0:50 · LangGraph State + Orchestration

**Screen:**
1. `backend/app/models/state.py` — show `MedicationReviewState` TypedDict
2. Back to `backend/app/graph/graph.py` — scroll to `build_graph()`, show `add_node` and `add_edge` calls
3. Highlight the two `add_conditional_edges` calls

**Say:**

> "I maintain a single typed state — `MedicationReviewState` — that every node reads from and writes back to.
>
> Each stage is a LangGraph node. The edges define the execution order."

*(point at `add_conditional_edges`)*

> "The workflow structure is defined in code, not by the LLM. The LLM reasons inside each node, but LangGraph decides which node executes next.
>
> This gives me explicit control over branching and retries instead of delegating that to the model."

---

## 0:50 – 1:25 · MCP Tool Orchestration

**Screen:**
1. `backend/app/mcp/server.py` — show tool registration
2. `backend/app/mcp/tools/drug_information.py` — show `get_drug_information()`, the RxNorm + OpenFDA calls
3. Briefly flash the `tools/` folder in the file explorer to show the other tools

**Say:**

> "The research stage doesn't call external APIs directly. It goes through MCP tools built with FastMCP.
>
> I have tools for drug information via RxNorm and OpenFDA, interaction checking, PubMed literature search, and vector retrieval from Qdrant."

*(point at the tool implementations)*

> "The LLM never touches these external systems directly. It calls structured tools through the MCP interface.
>
> The research stage fans out across multiple sources, then the results come back into the shared workflow state."

---

## 1:25 – 1:55 · Live Execution

**Screen:** Switch to the frontend — demo case already filled in. Click Submit, then immediately switch to the terminal to show backend logs streaming.

**Say:**

> "Let me show an actual execution."

*(as logs appear)*

> "Input is validated, medication names are normalized through RxNorm.
>
> The case is analyzed, a research plan is created.
>
> Now the research stage is running — you can see the individual MCP tool calls rather than just getting a final answer."

*(let tool calls sit visible for a few seconds)*

---

## 1:55 – 2:20 · Evidence Validation + Retry Loop

**Screen:**
1. `backend/app/graph/nodes/validate_evidence.py`
2. Back to `backend/app/graph/graph.py` — show `_route_after_validation()` and the `add_conditional_edges` for `validate_evidence`

**Say:**

> "After research, the workflow doesn't immediately generate the report. It first evaluates whether the collected evidence is sufficient."

*(point at the two branches)*

> "If sufficient, execution continues to risk analysis.
>
> If not, LangGraph routes back into research for another iteration — up to two retries."

> "So the agent has a real feedback loop: retrieve evidence, evaluate it, decide whether to retrieve again."

**If the demo case triggered a retry live:** show it and say "here you can see it retry."

**If not:** say "this conditional branch is what allows the workflow to retry research when evidence is judged insufficient" and move on.

```
validate_evidence
    │
    ├── sufficient = True  ──► analyze_risk ──► generate_report
    │
    └── sufficient = False ──► research_again ──► aggregate_evidence ──► (back to validate_evidence)
```

---

## 2:20 – 2:40 · Safety Architecture

**Screen:** File explorer showing `backend/app/safety/` folder — `policy_engine.py`, `rate_limiter.py`. 15 seconds max.

**Say:**

> "Because this is a medical domain, safety controls are separated from LLM reasoning.
>
> Input validation and prompt-injection detection run deterministically before any LLM call. The LLM handles reasoning — safety-critical checks are not delegated to the model."

---

## 2:40 – 2:55 · Langfuse Observability

**Screen:** Langfuse dashboard → click the trace for the execution you just ran. Expand the tree to show child spans: `node:normalize_medications`, `node:execute_research`, `node:validate_evidence`, etc. Click one span to show its input/output.

**Say:**

> "I instrumented the full workflow with Langfuse. Each graph node is a span with its input, output, and duration — all in a single execution trace.
>
> This makes it straightforward to debug where a workflow failed or where latency came from."

---

## 2:55 – 3:00 · Closing

**Screen:** Return to `backend/app/graph/graph.py`

**Say:**

> "LangGraph controls the workflow, MCP provides controlled tool access, RAG provides evidence, deterministic components handle safety and validation, and Langfuse gives end-to-end observability.
>
> That was a quick look at the orchestration logic behind MedGuard."

---

## Three Things the Viewer Must See

### 1 — LangGraph flow
```
validate_input
    ↓
normalize_medications
    ↓
analyze_case
    ↓
create_plan
    ↓
execute_research
    ↓
aggregate_evidence
    ↓
validate_evidence
    ↓
analyze_risk
    ↓
generate_report
```

### 2 — MCP stack
```
LangGraph node (execute_research)
    ↓
MCP client  (app/mcp/client.py)
    ↓
FastMCP server  (app/mcp/server.py)
    ↓
RxNorm / OpenFDA / PubMed / Qdrant
```

### 3 — Conditional retry loop
```
validate_evidence
    │
    ├── sufficient ──────────────► analyze_risk
    │
    └── insufficient + retries < 2
                 ↓
           research_again
                 ↓
        aggregate_evidence  (loops back ↑)
```

---

## If You Get Nervous

> "LangGraph controls the workflow, MCP controls tool access, RAG provides evidence, deterministic components handle safety and validation, and Langfuse provides observability."

---

## Do NOT Show

- React components or Tailwind CSS
- API endpoint implementation details
- Docker / Nginx setup
- PostgreSQL schema or Alembic migrations
- Every individual MCP tool
- Every node implementation one by one
- The README

---

## Recording Order

**graph.py → state.py → mcp/tools → live execution → validate_evidence retry loop → Langfuse trace → graph.py (closing)**
