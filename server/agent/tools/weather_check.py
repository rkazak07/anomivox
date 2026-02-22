from __future__ import annotations

import sys
import os

sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

import re
import warnings
from typing import Dict

from langchain.callbacks.manager import (
    AsyncCallbackManagerForChainRun,
    CallbackManagerForChainRun,
)
from langchain.chains.base import Chain
from langchain.chains.llm import LLMChain
from langchain.pydantic_v1 import Extra, root_validator
from langchain.schema import BasePromptTemplate
from langchain.schema.language_model import BaseLanguageModel
import requests
from typing import List, Any, Optional
from datetime import datetime
from langchain.prompts import PromptTemplate
from server.agent import model_container
from pydantic import BaseModel, Field

KEY = "ac880e5a877042809ac7ffdd19d95b0d"


_PROMPT_TEMPLATE = """
For example, if the user's question is: What is the weather in Shanghai Pudong in the next 1 hour?
Then the extracted city and district are: Shanghai Pudong
If the user's question is: What is the weather in Shanghai in the next 1 hour?
Then the extracted city and district are: Shanghai None
Please note the following:
1. If you cannot find the district, you must use None instead, otherwise the program cannot run
2. If the user has not specified a city, return missing information directly

Question: ${{User's question}}

Your answer format should follow the content below. Note that markers like ```text must be output, as they are used to extract answers.
```text

${{Split city and district, separated by space}}
```
... weathercheck(city district)...
```output

${{Extracted answer}}
```
Answer: ${{Answer}}



Question: What is the weather in Shanghai Pudong in the next 1 hour?


```text
```
...weathercheck(Shanghai Pudong)...

```output
Forecast time: 1 hour later
Specific time: Today 18:00
Temperature: 24°C
Weather: Cloudy
Wind direction: Southwest
Wind speed: Level 7
Humidity: 88%
Precipitation probability: 16%

Answer: The weather in Shanghai Pudong in one hour will be cloudy.


Question: {question}
"""
PROMPT = PromptTemplate(
    input_variables=["question"],
    template=_PROMPT_TEMPLATE,
)


def get_city_info(location, adm, key):
    base_url = 'https://geoapi.qweather.com/v2/city/lookup?'
    params = {'location': location, 'adm': adm, 'key': key}
    response = requests.get(base_url, params=params)
    data = response.json()
    return data


def format_weather_data(data, place):
    hourly_forecast = data['hourly']
    formatted_data = f"\n Weather information for {place} in the next 24 hours: \n"
    for forecast in hourly_forecast:
        forecast_time = datetime.strptime(forecast['fxTime'], '%Y-%m-%dT%H:%M%z')
        forecast_tz = forecast_time.tzinfo
        now = datetime.now(forecast_tz)
        days_diff = (forecast_time.date() - now.date()).days
        if days_diff == 0:
            forecast_date_str = 'Today'
        elif days_diff == 1:
            forecast_date_str = 'Tomorrow'
        elif days_diff == 2:
            forecast_date_str = 'Day after tomorrow'
        else:
            forecast_date_str = str(days_diff) + ' days later'
        forecast_time_str = forecast_date_str + ' ' + forecast_time.strftime('%H:%M')
        time_diff = forecast_time - now
        hours_diff = time_diff.total_seconds() // 3600
        if hours_diff < 1:
            hours_diff_str = 'In 1 hour'
        elif hours_diff >= 24:
            days_diff = hours_diff // 24
            hours_diff_str = str(int(days_diff)) + ' days'
        else:
            hours_diff_str = str(int(hours_diff)) + ' hours'
        formatted_data += 'Forecast time: ' + forecast_time_str + '  From now: ' + hours_diff_str + '\n'
        formatted_data += 'Temperature: ' + forecast['temp'] + '°C\n'
        formatted_data += 'Weather: ' + forecast['text'] + '\n'
        formatted_data += 'Wind direction: ' + forecast['windDir'] + '\n'
        formatted_data += 'Wind speed: ' + forecast['windSpeed'] + ' level\n'
        formatted_data += 'Humidity: ' + forecast['humidity'] + '%\n'
        formatted_data += 'Precipitation probability: ' + forecast['pop'] + '%\n'
        formatted_data += '\n'
    return formatted_data


def get_weather(key, location_id, place):
    url = "https://devapi.qweather.com/v7/weather/24h?"
    params = {
        'location': location_id,
        'key': key,
    }
    response = requests.get(url, params=params)
    data = response.json()
    return format_weather_data(data, place)


def split_query(query):
    parts = query.split()
    adm = parts[0]
    if len(parts) == 1:
        return adm, adm
    location = parts[1] if parts[1] != 'None' else adm
    return location, adm


def weather(query):
    location, adm = split_query(query)
    key = KEY
    if key == "":
        return "Please enter the QWeather API Key in the code first"
    try:
        city_info = get_city_info(location=location, adm=adm, key=key)
        location_id = city_info['location'][0]['id']
        place = adm + " " + location

        weather_data = get_weather(key=key, location_id=location_id, place=place)
        return weather_data + "The above is the retrieved weather information.\n"
    except KeyError:
        try:
            city_info = get_city_info(location=adm, adm=adm, key=key)
            location_id = city_info['location'][0]['id']
            place = adm
            weather_data = get_weather(key=key, location_id=location_id, place=place)
            return weather_data + "Important notice: The district information provided by the user does not exist or has a typo. This information is about the city's weather.\n"
        except KeyError:
            return "The entered region does not exist, unable to provide weather forecast"


class LLMWeatherChain(Chain):
    llm_chain: LLMChain
    llm: Optional[BaseLanguageModel] = None
    """[Deprecated] LLM wrapper to use."""
    prompt: BasePromptTemplate = PROMPT
    """[Deprecated] Prompt to use to translate to python if necessary."""
    input_key: str = "question"  #: :meta private:
    output_key: str = "answer"  #: :meta private:

    class Config:
        """Configuration for this pydantic object."""

        extra = Extra.forbid
        arbitrary_types_allowed = True

    @root_validator(pre=True)
    def raise_deprecation(cls, values: Dict) -> Dict:
        if "llm" in values:
            warnings.warn(
                "Directly instantiating an LLMWeatherChain with an llm is deprecated. "
                "Please instantiate with llm_chain argument or using the from_llm "
                "class method."
            )
            if "llm_chain" not in values and values["llm"] is not None:
                prompt = values.get("prompt", PROMPT)
                values["llm_chain"] = LLMChain(llm=values["llm"], prompt=prompt)
        return values

    @property
    def input_keys(self) -> List[str]:
        """Expect input key.

        :meta private:
        """
        return [self.input_key]

    @property
    def output_keys(self) -> List[str]:
        """Expect output key.

        :meta private:
        """
        return [self.output_key]

    def _evaluate_expression(self, expression: str) -> str:
        try:
            output = weather(expression)
        except Exception as e:
            output = "Invalid input, please try again"
        return output

    def _process_llm_result(
            self, llm_output: str, run_manager: CallbackManagerForChainRun
    ) -> Dict[str, str]:

        run_manager.on_text(llm_output, color="green", verbose=self.verbose)

        llm_output = llm_output.strip()
        text_match = re.search(r"^```text(.*?)```", llm_output, re.DOTALL)
        if text_match:
            expression = text_match.group(1)
            output = self._evaluate_expression(expression)
            run_manager.on_text("\nAnswer: ", verbose=self.verbose)
            run_manager.on_text(output, color="yellow", verbose=self.verbose)
            answer = "Answer: " + output
        elif llm_output.startswith("Answer:"):
            answer = llm_output
        elif "Answer:" in llm_output:
            answer = "Answer: " + llm_output.split("Answer:")[-1]
        else:
            return {self.output_key: f"Invalid input format: {llm_output}, should be (city district) combination"}
        return {self.output_key: answer}

    async def _aprocess_llm_result(
            self,
            llm_output: str,
            run_manager: AsyncCallbackManagerForChainRun,
    ) -> Dict[str, str]:
        await run_manager.on_text(llm_output, color="green", verbose=self.verbose)
        llm_output = llm_output.strip()
        text_match = re.search(r"^```text(.*?)```", llm_output, re.DOTALL)

        if text_match:
            expression = text_match.group(1)
            output = self._evaluate_expression(expression)
            await run_manager.on_text("\nAnswer: ", verbose=self.verbose)
            await run_manager.on_text(output, color="yellow", verbose=self.verbose)
            answer = "Answer: " + output
        elif llm_output.startswith("Answer:"):
            answer = llm_output
        elif "Answer:" in llm_output:
            answer = "Answer: " + llm_output.split("Answer:")[-1]
        else:
            raise ValueError(f"unknown format from LLM: {llm_output}")
        return {self.output_key: answer}

    def _call(
            self,
            inputs: Dict[str, str],
            run_manager: Optional[CallbackManagerForChainRun] = None,
    ) -> Dict[str, str]:
        _run_manager = run_manager or CallbackManagerForChainRun.get_noop_manager()
        _run_manager.on_text(inputs[self.input_key])
        llm_output = self.llm_chain.predict(
            question=inputs[self.input_key],
            stop=["```output"],
            callbacks=_run_manager.get_child(),
        )
        return self._process_llm_result(llm_output, _run_manager)

    async def _acall(
            self,
            inputs: Dict[str, str],
            run_manager: Optional[AsyncCallbackManagerForChainRun] = None,
    ) -> Dict[str, str]:
        _run_manager = run_manager or AsyncCallbackManagerForChainRun.get_noop_manager()
        await _run_manager.on_text(inputs[self.input_key])
        llm_output = await self.llm_chain.apredict(
            question=inputs[self.input_key],
            stop=["```output"],
            callbacks=_run_manager.get_child(),
        )
        return await self._aprocess_llm_result(llm_output, _run_manager)

    @property
    def _chain_type(self) -> str:
        return "llm_weather_chain"

    @classmethod
    def from_llm(
            cls,
            llm: BaseLanguageModel,
            prompt: BasePromptTemplate = PROMPT,
            **kwargs: Any,
    ) -> LLMWeatherChain:
        llm_chain = LLMChain(llm=llm, prompt=prompt)
        return cls(llm_chain=llm_chain, **kwargs)


def weathercheck(query: str):
    model = model_container.MODEL
    llm_weather = LLMWeatherChain.from_llm(model, verbose=True, prompt=PROMPT)
    ans = llm_weather.run(query)
    return ans


class WhetherSchema(BaseModel):
    location: str = Field(description="Should be a region name, separated by space, e.g.: Shanghai Pudong. If there is no district info, you can just enter Shanghai")

if __name__ == '__main__':
    result = weathercheck("Is it hot in Suzhou Gusu District tonight?")
