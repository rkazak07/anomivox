from langchain.prompts import PromptTemplate
from langchain.chains import LLMMathChain
from server.agent import model_container
from pydantic import BaseModel, Field

_PROMPT_TEMPLATE = """
```text
```
...numexpr.evaluate(query)...
```output
```
Answer: ${{Answer}}


Question: What is 37593 * 67?
```text
37593 * 67
```
...numexpr.evaluate("37593 * 67")...
```output
2518731

Answer: 2518731

```text
37593**(1/5)
```
...numexpr.evaluate("37593**(1/5)")...
```output
8.222831614237718

Answer: 8.222831614237718


```text
2 ** 2
```
...numexpr.evaluate("2 ** 2")...
```output
4

Answer: 4


Question: {question}
"""

PROMPT = PromptTemplate(
    input_variables=["question"],
    template=_PROMPT_TEMPLATE,
)


class CalculatorInput(BaseModel):
    query: str = Field()

def calculate(query: str):
    model = model_container.MODEL
    llm_math = LLMMathChain.from_llm(model, verbose=True, prompt=PROMPT)
    ans = llm_math.run(query)
    return ans

if __name__ == "__main__":
    result = calculate("What is 2 to the power of 3?")
    print("Answer:", result)



