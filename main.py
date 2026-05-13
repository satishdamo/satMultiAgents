import logging
from fastapi import FastAPI
from fastapi.responses import FileResponse
from pydantic import BaseModel
from agents import app_graph, workflow
from pathlib import Path
import json
from datetime import datetime
from mermaid import Mermaid
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI()


# Allow your frontend origin
app.add_middleware(
    CORSMiddleware,
    # React dev server
    allow_origins=["https://multi-agent-restaurant-assistant.vercel.app"],
    allow_credentials=True,
    allow_methods=["*"],  # or ["POST", "GET"]
    allow_headers=["*"],
)


class UserRequest(BaseModel):
    query: str


# Create execution traces directory
traces_dir = Path("execution_traces")
traces_dir.mkdir(exist_ok=True)

# Create execution traces directory
workflow_diagram_dir = Path("workflow_diagrams")
workflow_diagram_dir.mkdir(exist_ok=True)


@app.post("/chat")
async def chat(request: UserRequest):
    # Run the orchestration graph with user input
    initial_state = {
        "input": request.query,
        "response": "",
        "next_agent": ""
    }
    result = app_graph.invoke(initial_state)

    # Save execution trace
    trace = {
        "timestamp": datetime.now().isoformat(),
        "query": request.query,
        "path_taken": extract_path(result.get("response", "")),
        "final_response": result["response"],
        "next_agent_decision": result.get("next_agent", "")
    }

    # save_trace(trace)

    return {"response": result["response"]}


@app.post("/download_workflow_image")
async def download_workflow_image():
    """Generate Mermaid diagram exactly like the desired source, but workers dynamic."""

    mermaid_lines = [
        "---",
        "config:",
        "  flowchart:",
        "    curve: linear",
        "---",
        "graph TD;",
        "__start__([Start])",
        # Hardcoded supervisor node
        'supervisor(["🎯 Supervisor Agent<br/>(Decision Router)"])',
        "__end__([End])"
    ]

    # Worker node labels
    node_labels = {
        "ordering": "📋 Ordering Agent<br/>(Handle Orders)",
        "menu": "🍽️ Menu Agent<br/>(Suggest Dishes)",
        "grievance": "⚠️ Grievance Agent<br/>(Handle Complaints)"
    }

    # Styles
    styles = {
        "supervisor": "fill:#4CAF50,stroke:#2E7D32,color:#fff,stroke-width:3px",
        "ordering": "fill:#2196F3,stroke:#1565C0,color:#fff,stroke-width:2px",
        "menu": "fill:#FF9800,stroke:#E65100,color:#fff,stroke-width:2px",
        "grievance": "fill:#F44336,stroke:#C62828,color:#fff,stroke-width:2px",
        "__start__": "fill:#90EE90,stroke:#228B22,color:#000,stroke-width:2px",
        "__end__": "fill:#FFB6C1,stroke:#8B0000,color:#000,stroke-width:2px"
    }

    # Add worker nodes dynamically
    for node in workflow.nodes.keys():
        if node != "supervisor":
            label = node_labels.get(node, f"{node.title()} Agent")
            mermaid_lines.append(f'{node}(["{label}"])')

    mermaid_lines.append("__start__ --> supervisor")

    for node in workflow.nodes.keys():
        if node != "supervisor":
            mermaid_lines.append(f'supervisor -->|{node}| {node}')

    mermaid_lines.append("supervisor -->|done| __end__")

    for node in workflow.nodes.keys():
        if node != "supervisor":
            mermaid_lines.append(f'{node} --> supervisor')

    # Styles
    for node, style in styles.items():
        mermaid_lines.append(f"style {node} {style}")

    diagram_text = "\n".join(mermaid_lines)

    # Save Mermaid source to .txt
    txt_file = Path(
        f"{workflow_diagram_dir}/workflow_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt")
    txt_file.write_text(diagram_text, encoding="utf-8")

    # Render to SVG
    svg_file = txt_file.with_suffix(".svg")
    mmd = Mermaid(diagram_text)
    mmd.to_svg(str(svg_file))

    try:
        return FileResponse(
            path=svg_file,
            filename=svg_file.name,
            media_type="image/svg+xml"
        )
    except Exception as e:
        print(f"Error occurred while creating FileResponse: {e}")
        raise


def extract_path(response: str) -> list:
    """Extract the agent path from response."""
    path = []
    if "Supervisor decision:" in response:
        # Parse agent calls from response
        lines = response.split("\n")
        for line in lines:
            if "Agent:" in line or "decision:" in line:
                path.append(line.strip())
    return path


def save_trace(trace: dict):
    """Save execution trace to JSON file."""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    trace_file = traces_dir / f"trace_{timestamp}.json"

    with open(trace_file, "w") as f:
        json.dump(trace, f, indent=2)

    print(f"Execution trace saved to: {trace_file}")
