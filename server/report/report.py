import logging
from datetime import datetime
import json
import os
from fastapi import Body, Request
from server.utils import BaseResponse
from configs import DIAGNOSTIC_RESULTS_PATH, DIAGNOSE_LLM_MODEL_LIST


def histories(start: str = Body(default=None, description="Diagnosis file start time"),
              end: str = Body(default=None, description="Diagnosis file end time"),
              model: str = Body("GPT4-0613", description="Diagnosis model")):
    folder_path = os.path.join(DIAGNOSTIC_RESULTS_PATH, model)
    if not os.path.exists(folder_path):
        return BaseResponse(code=404, msg="No diagnosis folder for this model")
    file_list = os.listdir(folder_path)
    file_list = sorted(file_list, reverse=True)
    json_list = []
    for file_name in file_list:
        if file_name.endswith(".json") or file_name.endswith(".jsonl"):
            file_path = os.path.join(folder_path, file_name)
            timestamp = int(os.path.splitext(file_name)[0])
            if start and timestamp < int(start):
                continue
            if end and timestamp > int(end):
                continue
            with open(file_path, "r") as file:
                try:
                    json_data = json.load(file)
                    json_data["time"] = datetime.fromtimestamp(int(json_data.get("time", ""))).strftime("%Y-%m-%d %H:%M:%S")
                    json_data["file_name"] = file_name
                    json_list.append(json_data)
                except Exception as e:
                    logging.error(f"Failed to read JSON file {file_path}: {e}")
                    continue
    return BaseResponse(code=200, msg="Success", data=json_list)


def history_detail(file: str = Body(..., description="Diagnosis file name"),
                   model: str = Body("GPT4-0613", description="Diagnosis model")):
    file_path = f"{DIAGNOSTIC_RESULTS_PATH}/{model}/{file}"
    if not os.path.exists(file_path):
        return BaseResponse(code=404, msg="No corresponding diagnosis file")
    if file_path.endswith(".json") or file_path.endswith(".jsonl"):
        with open(file_path, "r") as file:
            json_data = json.load(file)
            json_data["time"] = datetime.fromtimestamp(int(json_data.get("time", ""))).strftime("%Y-%m-%d %H:%M:%S")
            return BaseResponse(code=200, msg="Success", data=json_data)
    else:
        return BaseResponse(code=400, msg="No corresponding file")


def diagnose_llm_model_list():
    return BaseResponse(code=200, msg="Success", data=DIAGNOSE_LLM_MODEL_LIST)

