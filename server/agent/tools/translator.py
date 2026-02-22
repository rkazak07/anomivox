from langchain.prompts import PromptTemplate
from langchain.chains import LLMChain
from server.agent import model_container
from pydantic import BaseModel, Field

_PROMPT_TEMPLATE = '''


Question: {question}

'''

PROMPT = PromptTemplate(
    input_variables=["question"],
    template=_PROMPT_TEMPLATE,
)


def translate(query: str):
    model = model_container.MODEL
    llm_translate = LLMChain(llm=model, prompt=PROMPT)
    ans = llm_translate.run(query)
    return ans

class TranslateInput(BaseModel):
    location: str = Field(description="Content to be translated")

if __name__ == "__main__":
    result = translate("Can Love remember the question and the answer? How to translate this sentence poetically into Chinese?")
    print("Answer:", result)
