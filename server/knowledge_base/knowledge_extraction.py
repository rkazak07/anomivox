from subprocess import Popen, PIPE
from fastapi import File, UploadFile
from configs import (logger, ORIGINAL_KNOWLEDGE_FILES_PATH, )
from typing import Iterator
import threading
from server.utils import BaseResponse, save_file

current_task = {"thread": None, "output": ""}

def run_knowledge_extraction_script(file_path: str) -> Iterator[str]:
    try:
        process = Popen(["python3", "run_diagnose.py", "--anomaly_file", file_path], stdout=PIPE, text=True)
        current_task["output"] = ""
        while True:
            output = process.stdout.readline()
            if process.poll() is not None and output == '':
                break
            if output:
                print('Diagnosis output:', output.strip())
                current_task["output"] += f"{output.strip()}\n"
    except Exception as e:
        error_message = f"Error executing task: {e}"
        logger.error(error_message)
        current_task["output"] += error_message


def run_knowledge_extraction(file: UploadFile = File(..., description="Upload file, supports multiple files")):
    if current_task["thread"] and current_task["thread"].is_alive():
        return BaseResponse(code=400, msg="A task is already running")
    save_file_result = save_file(ORIGINAL_KNOWLEDGE_FILES_PATH, file, True)
    file_path = save_file_result["data"]["file_path"]

    current_task["thread"] = threading.Thread(target=run_knowledge_extraction_script, args=(file_path,), name='KnowledgeExtraction')
    current_task["thread"].start()
    current_task["thread"].join(5)

    if current_task["thread"].is_alive():
        return BaseResponse(code=200, msg="Success")
    else:
        error_message = current_task["output"] if current_task["output"] else "An unknown error occurred."
        return BaseResponse(code=500, msg=error_message)


def get_knowledge_extraction_output():
    is_alive = current_task["thread"] and current_task["thread"].is_alive()
    msg = "Success" if is_alive else "No task is running"
    return BaseResponse(code=200, msg=msg, data={"is_alive": is_alive, "output": current_task["output"]})

