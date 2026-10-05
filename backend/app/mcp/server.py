"""
MedGuard MCP Server
All medication safety tools exposed via the Model Context Protocol.
LangGraph agents connect to this server to execute tool calls.
"""
from fastmcp import FastMCP

from app.mcp.tools.drug_information import get_drug_information
from app.mcp.tools.interaction_check import check_drug_interaction, check_multiple_interactions
from app.mcp.tools.literature_search import search_medical_literature
from app.mcp.tools.guideline_search import search_guidelines
from app.mcp.tools.evidence_retrieval import retrieve_evidence

mcp = FastMCP(
    name="MedGuard Medication Safety Server",
    instructions=(
        "You are a medication safety research assistant. "
        "Use these tools to retrieve factual medication information, check drug interactions, "
        "search medical literature, and retrieve clinical guidelines. "
        "Always cite sources. Never provide treatment recommendations or diagnoses."
    ),
)

# Register all tools
mcp.add_tool(get_drug_information)
mcp.add_tool(check_drug_interaction)
mcp.add_tool(check_multiple_interactions)
mcp.add_tool(search_medical_literature)
mcp.add_tool(search_guidelines)
mcp.add_tool(retrieve_evidence)


def get_mcp_server() -> FastMCP:
    return mcp


if __name__ == "__main__":
    mcp.run(transport="stdio")
