from __future__ import annotations
import time
from pydantic import Field
from typing import List
from multiagents.message import SolverMessage, Message
from multiagents.agents import agent_registry
from multiagents.agents.base import BaseAgent
from multiagents.prompt_templates.report_prompts import (
    ANOMALY_DESC_PROMPT, ANOMALY_TITLE_PROMPT,
    ANOMALY_DESC_PROMPT_zh, ANOMALY_TITLE_PROMPT_zh
)
from multiagents.utils.interact import add_display_message

@agent_registry.register("reporter") # solver is also tool agent by default
class ReporterAgent(BaseAgent):
    class Config:
        arbitrary_types_allowed = True

    verbose: bool = Field(default=False)
    name: str = Field(default="ChiefDBA")
    start_time: str = ""
    max_history: int = 3
    alert_str: str = ""
    alert_dict: dict = {}
    anomaly_desc_prompt: str = ANOMALY_DESC_PROMPT
    anomaly_title_prompt: str = ANOMALY_TITLE_PROMPT
    messages: List[dict] = []

    report: dict = {"title": "", "anomaly date": "", "anomaly description": "", "root cause": "", "labels": "", "diagnosis process": "", "solutions": ""}

    record: dict = {"anomalyAnalysis": {"RoleAssigner":{"messages":[]},"Solver":{"messages":[]}}, "brainstorming": {"messages":[]}, "report":{}, "title":"alert name", "time":"alert time", "topMetrics": []} # type: bar / line

    def initialize_report(self):
        if self.language == 'zh':
            self.anomaly_desc_prompt = ANOMALY_DESC_PROMPT_zh
            self.anomaly_title_prompt = ANOMALY_TITLE_PROMPT_zh

        seconds = int(self.start_time)
        start_date = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(seconds))
        self.report["anomaly date"] = start_date
        self.record["time"] = self.start_time

        if self.alert_str == "":
            return
        

        anomaly_desc_prompt = self.anomaly_desc_prompt.replace("{anomaly_str}", self.alert_str)
        anomaly_desc_message = self.llm._construct_messages(anomaly_desc_prompt)

        self.llm.change_messages(self.role_description, anomaly_desc_message)

        anomaly_desc = self.llm.parse(role=self.name, task='desc')
        anomaly_desc = anomaly_desc['content']
        self.report["anomaly description"] = anomaly_desc

        anomaly_title_prompt = self.anomaly_title_prompt.replace("{anomaly_str}", self.alert_str)
        anomaly_title_message = self.llm._construct_messages(anomaly_title_prompt)
        self.llm.change_messages(self.role_description, anomaly_title_message)
        anomaly_title = self.llm.parse(role=self.name, task='title')
        anomaly_title = anomaly_title['content']
        self.report["title"] = anomaly_title.replace('\\"','')
        self.report["title"] = anomaly_title.replace('"','')
        self.record["title"] = anomaly_title.replace('\\"','')
        self.record["title"] = anomaly_title.replace('"','')

        self.record["severity"] = []
        self.record["status"] = []
        alert_names = []
        for alert in self.alert_dict:

            if isinstance(alert, dict):
                alert_names.append({"alert_name": alert['alert_name'],
                                "alert_status": alert['alert_status'],
                                "alert_level": alert['alert_level']})

            # self.record["severity"].append(alert['alert_level'])
            # self.record["status"].append(alert['alert_status'])

            # if isinstance(alert, dict) and  'alert_name' in alert:
            #     alert_names.append(alert['alert_name'])

        self.report["alerts"] = alert_names
        self.record["alerts"] = alert_names

    def update_diagnosis(self):
        if self.language == 'zh':
            prompt = f'''You are writing a fault diagnosis report and need to provide the final root cause analysis. Please refer to the review suggestions above and the following root cause analysis:\n{self.report["root cause"]} \nNote:\n1. Output must be in markdown format, but do not say things like "this is markdown format".\n2. Only provide root cause analysis, do not mention anything related to solutions.\n'''
        else:
            prompt = "You are writing a report. Please give the refined root cause analysis based on the above review advice. The root cause analysis is as follows:\n" + self.report["root cause"] + "\n ===== \n Note 1. the output should be in markdown format.\n2. do not any additional content like 'Sure' and 'I will refine the anomaly diagnosis description based on the above advice. 3. Do not add anything about solutions!!!'\n"

        prompt_message = {"role": "user", "content": prompt, "time": time.strftime("%H:%M:%S", time.localtime())}

        # self.messages.append(prompt_message)

        self.llm.change_messages(self.role_description, self.messages + [prompt_message])
        if self.enable_feedback():
            add_display_message('reportGeneration', self.name, '\n\n'.join([m['content'] for m in self.messages] + [prompt]), prompt_message['time'], flag=False)
        new_message = self.llm.parse(role=self.name, task='refine_root_cause')

        if isinstance(new_message, dict):
            self.report["root cause"] = new_message["content"]
        else:
            self.report["root cause"] = new_message.content

    def add_diagnosis_labels(self):
        root_causes = {
            "INSERT_LARGE_DATA": ["highly concurrent commits or highly concurrent inserts"],
            "LOCK_CONTENTION": ["highly concurrent updates"],
            "VACUUM": ["highly deletes"],
            "REDUNDANT_INDEX": ["too many indexes"],
            "MISSING_INDEXES": ["missing indexes"],
            "INSERT_LARGE_DATA,IO_CONTENTION": ["INSERT_LARGE_DATA","IO_CONTENTION"],
            "FETCH_LARGE_DATA,CORRELATED_SUBQUERY": ["FETCH_LARGE_DATA","CORRELATED SUBQUERY"],
            "POOR_JOIN_PERFORMANCE,CPU_CONTENTION": ["POOR JOIN PERFORMANCE","CPU CONTENTION"],
        }

        labels = []

        for cause in root_causes:
            labels += root_causes[cause]

        if self.language == 'zh':
            prompt = f"""The following is a root cause analysis process:\n{self.report["root cause"]}\nThe following are labels for some root causes listed:\n{labels}\nBased on the description of the root cause analysis process, select the corresponding labels.\nNote:\n1. Output must be in list format, do not add any extra content.\n2. Output should strictly exclude labels not mentioned in the root cause analysis.\n3. If there are no relevant labels, return None.\n"""
        else:
            prompt = "Based on the description\n" + self.report["root cause"] + "\n\n Output all the labels mentioned in the description. The available labels are  \n" + str(labels) + "===== \n Note 1. the output should be in list format. And do not output any additional information (output \"None\" if no label mentioned in the description)\n2. the output should strictly exclude labels not mentioned in the description."

        prompt_message = {"role": "user", "content": prompt, "time": time.strftime("%H:%M:%S", time.localtime())}

        self.llm.change_messages(self.role_description, self.messages + [prompt_message])
        new_message = self.llm.parse(role=self.name, task="label")
        
        if isinstance(new_message, dict):
            self.report["labels"] = new_message["content"]
        else:
            self.report["labels"] = new_message.content

        


    def update_solutions(self):
        if self.language == 'zh':
            prompt = f"""You are writing a fault diagnosis report and need to provide the final solution. Please refer to the review suggestions above and the following solutions:\n{self.report["solutions"]} \nNote:\n1. Output must be in markdown format, but do not say things like "this is markdown format".\n2. Only provide solutions, do not mention anything related to root cause analysis.\n"""
        else:
            prompt = "You are writing a report. Please optimize the following solutions based on the above review advice. The solutions are:\n" + self.report["solutions"] + "\n ===== \n Note 1. the output should be in markdown format.\n2. do not any additional content like 'Sure' and 'I will refine the solutions based on the above advice'. 3. Do not add anything about root causes!!!\n"

        prompt_message = {"role": "user", "content": prompt, "time": time.strftime("%H:%M:%S", time.localtime())}

        # self.messages.append(prompt_message)

        self.llm.change_messages(self.role_description, self.messages + [prompt_message])
        if self.enable_feedback():
            add_display_message('reportGeneration', self.name, '\n\n'.join([m['content'] for m in self.messages] + [prompt]), prompt_message['time'], flag=False)
        new_message = self.llm.parse(role=self.name, task="refine_solution")

        if isinstance(new_message, dict):
            self.report["solutions"] = new_message["content"]
        else:
            self.report["solutions"] = new_message.content


    async def step(
        self, former_solution: str, advice: str, task_description: str = "", **kwargs
    ):
        pass

    async def astep(self, env_description: str = "") -> SolverMessage:
        """Asynchronous version of step"""
        pass

    def _fill_prompt_template(
        self, env_description: str = "", tool_observation: List[str] = []):
        pass
    
    def add_message_to_memory(self, messages: List[Message]) -> None:
        self.memory.add_message(messages)

    def reset(self) -> None:
        """Reset the agent"""
        self.memory.reset()
        # TODO: reset receiver