import os

DIAGNOSTIC_RESULTS_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "alert_results")

DIAGNOSE_LLM_MODEL_LIST = ["GPT4-0613", "Llama2-13b", "CodeLlama2-13b", "BaiChuan-13b", "Qwen1.5-14B-Chat"]

DIAGNOSTIC_FILES_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "diagnostic_files")
if not os.path.exists(DIAGNOSTIC_FILES_PATH):
    os.mkdir(DIAGNOSTIC_FILES_PATH)
DIAGNOSTIC_CONFIG_FILE = "config.yaml"

DIAGNOSE_RUN_LOG_PATH = "./diagnose_run_log.txt"
DIAGNOSE_RUN_PID_PATH = "./diagnose_run_pid.txt"
DIAGNOSE_USER_FEEDBACK_PATH = "./diagnose_user_feedback.txt"
DIAGNOSE_RUN_DATA_PATH = "./diagnose_run_data.jsonl"
DIAGNOSE_RUN_DATA_COPY_PATH = "./diagnose_run_data_copy.jsonl"

IS_FEEDBACK_BY_UI = True


POSTGRESQL_CONFIG = {
  "host": "182.XX.XX.XXX",
  "port": 5432,
  "user": "XXXX",
  "password": "XXXXX",
  "dbname": "postgres"
}

MYSQL_CONFIG = {
  "host": "166.XX.XX.XX",
  "port": 3306,
  "user": "XX",
  "password": "XXXXXX",
}