import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from configs import LLM_MODELS, TEMPERATURE
from server.utils import get_ChatOpenAI
from langchain.chains import LLMChain
from langchain.agents import LLMSingleActionAgent, AgentExecutor
from server.agent.tools import tools, tool_names
from langchain.memory import ConversationBufferWindowMemory

memory = ConversationBufferWindowMemory(k=5)
model = get_ChatOpenAI(
        model_name=LLM_MODELS[0],
        temperature=TEMPERATURE,
    )
from server.agent.custom_template import CustomOutputParser, prompt

output_parser = CustomOutputParser()
llm_chain = LLMChain(llm=model, prompt=prompt)
agent = LLMSingleActionAgent(
    llm_chain=llm_chain,
    output_parser=output_parser,
    stop=["\nObservation:"],
    allowed_tools=tool_names
)

agent_executor = AgentExecutor.from_agent_and_tools(agent=agent, tools=tools, memory=memory, verbose=True)

import pytest
@pytest.mark.parametrize("text_prompt",
                          ["Calculate (2 + 2312312)/4 = ?",
                          "Translate this sentence into Chinese: Life is the art of drawing sufficient conclusions form insufficient premises."]
)
def test_different_agent_function(text_prompt):
    try:
        text_answer = agent_executor.run(text_prompt)
        assert text_answer is not None
    except Exception as e:
        pytest.fail(f"agent_function failed with {text_prompt}, error: {str(e)}")
