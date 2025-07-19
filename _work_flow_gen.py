import json
import os
from dotenv import load_dotenv
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import SystemMessage, HumanMessage

load_dotenv()

# Load system prompt and function registry once
with open("sys_prompt_temp.txt", 'r') as f:
    sys_prompt_temp = f.read()

with open("function_registry.json") as f:
    function_registry = json.load(f)

llm = ChatGoogleGenerativeAI(model="gemini-2.5-flash",api_key=os.getenv("GOOGLE_API_KEY"))

def generate_workflow(user_prompt: str):
    messages = [
        SystemMessage(content=sys_prompt_temp),
        HumanMessage(content=user_prompt)
    ]
    res = llm.invoke(messages)
    content = res.content.lstrip("```json").rstrip("```")
    try:
        parsed = json.loads(content)
        return parsed
    except json.JSONDecodeError as e:
        raise ValueError(f"Invalid JSON from LLM: {content}") from e

print(generate_workflow("land cover map of Chennai with low level of elevation"))


    
