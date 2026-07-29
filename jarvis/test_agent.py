import json
from app.agent.graph import jarvis_agent
from langchain_core.messages import HumanMessage

def test_agent():
    print("TEST 1: Email Intent")
    state = {
        "session_id": "test_session_id",
        "messages": [HumanMessage(content="Show me my latest emails.")]
    }
    result = jarvis_agent.invoke(state)
    last_msg = result["messages"][-1]
    print("Model selected tools:", getattr(last_msg, 'tool_calls', []))
    print("-" * 50)

    print("TEST 2: Email Draft Intent")
    state = {
        "session_id": "test_session_id",
        "messages": [HumanMessage(content="Draft an email to ali@example.com saying I will join tomorrow.")]
    }
    result = jarvis_agent.invoke(state)
    last_msg = result["messages"][-1]
    print("Model selected tools:", getattr(last_msg, 'tool_calls', []))
    print("-" * 50)
    
    print("TEST 3: Send Email Intent (Safety Test)")
    state = {
        "session_id": "test_session_id",
        "messages": [HumanMessage(content="Send an email to Ali.")]
    }
    result = jarvis_agent.invoke(state)
    last_msg = result["messages"][-1]
    print("Model selected tools:", getattr(last_msg, 'tool_calls', []))
    print("Response text:", last_msg.content)
    print("-" * 50)

if __name__ == "__main__":
    test_agent()
