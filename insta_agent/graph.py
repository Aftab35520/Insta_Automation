from insta_agent.agent import AgentCall
from langgraph.graph import StateGraph,START,END
from insta_agent.state import State
from langgraph.checkpoint.memory import InMemorySaver
from insta_agent.tool import Generate_image,Upload_to_instagram
from langgraph.prebuilt import ToolNode,tools_condition
from pymongo import MongoClient
from langgraph.checkpoint.mongodb import MongoDBSaver
uri = "mongodb+srv://Aftab355201:Aftab355201@cluster0.cn5rpym.mongodb.net/?appName=Cluster0"
import certifi
client = MongoClient(
    uri,
    tls=True,
    tlsCAFile=certifi.where(),
    serverSelectionTimeoutMS=10000
)


checkpointer = MongoDBSaver(
    client=client,
    db_name="Insta_memory_real"
)


graph=StateGraph(State)




graph.add_node("AgentCall",AgentCall)
graph.add_node("tools",ToolNode([Generate_image,Upload_to_instagram]))

graph.add_edge(START,"AgentCall")
graph.add_conditional_edges(
    "AgentCall",
    tools_condition
)
graph.add_edge("tools","AgentCall")
graph=graph.compile(checkpointer=checkpointer)






