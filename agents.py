from langgraph.graph import StateGraph, END
from langchain_openai import ChatOpenAI
from dotenv import load_dotenv
import os
from typing import TypedDict

load_dotenv()


# Define the state schema

class AgentState(TypedDict):
    input: str
    response: str
    next_agent: str


# Base models
supervisor_llm = ChatOpenAI(
    model="gpt-4.1", api_key=os.getenv("OPENAI_API_KEY"))
worker_llm = ChatOpenAI(model="gpt-4.1-mini",
                        api_key=os.getenv("OPENAI_API_KEY"))

# --- Worker agent functions ---


def ordering_agent(state: AgentState) -> AgentState:
    user_input = state["input"]
    current_response = state.get("response", "")
    prompt = f"You are an ordering agent. Handle food orders. User said: {user_input}"
    reply = worker_llm.invoke(prompt)
    return {"response": current_response + "\nOrdering Agent: " + reply.content}


def menu_agent(state: AgentState) -> AgentState:
    user_input = state["input"]
    current_response = state.get("response", "")
    prompt = f"You are a menu suggestion agent. Suggest dishes or desserts. User said: {user_input}"
    reply = worker_llm.invoke(prompt)
    return {"response": current_response + "\nMenu Agent: " + reply.content}


def grievance_agent(state: AgentState) -> AgentState:
    user_input = state["input"]
    current_response = state.get("response", "")
    prompt = f"You are a grievance agent. Handle any complaints or concerns or issues politely. User said: {user_input}"
    reply = worker_llm.invoke(prompt)
    return {"response": current_response + "\nGrievance Agent: " + reply.content}

# --- Supervisor agent function ---


def supervisor_agent(state: AgentState) -> AgentState:
    user_input = state["input"]
    current_response = state.get("response", "")
    prompt = (
        "You are a supervisor agent. Decide which agents to call next based on the query. "
        "Options: ordering, menu, grievance, or done. "
        "Reply with just ONE of these: 'ordering', 'menu', 'grievance', or 'done'. "
        f"User said: {user_input}\nSo far response: {current_response}"
    )
    decision = supervisor_llm.invoke(prompt).content.strip().lower()
    return {"response": current_response + f"\nSupervisor decision: {decision}", "next_agent": decision}


# --- Build orchestration graph ---
workflow = StateGraph(AgentState)

workflow.add_node("ordering", ordering_agent)
workflow.add_node("menu", menu_agent)
workflow.add_node("grievance", grievance_agent)
workflow.add_node("supervisor", supervisor_agent)

workflow.set_entry_point("supervisor")

# Conditional routing from supervisor


def route_supervisor(state: AgentState):
    decision = state.get("next_agent", "").lower()
    if "ordering" in decision:
        return "ordering"
    elif "menu" in decision:
        return "menu"
    elif "grievance" in decision:
        return "grievance"
    else:
        return END


workflow.add_conditional_edges("supervisor", route_supervisor)

# Route workers back to supervisor
workflow.add_edge("ordering", "supervisor")
workflow.add_edge("menu", "supervisor")
workflow.add_edge("grievance", "supervisor")

app_graph = workflow.compile()
