import json
import os
import threading
import logging

import uvicorn
from fastapi import FastAPI, Request
from datetime import datetime

from prometheus_abnormal_metric import obtain_exceptions_in_times
from get_slow_queries import obtain_slow_queries


app = FastAPI()


@app.get('/test')
async def test():
    return {
        "code": 0,
        "msg": "success",
        "data": "prometheus service is running"
    }


@app.post('/alert')
async def alert(request: Request):
    """
    return add alert
    :return:
    """
    args = await request.json()
    with open("alert_history.txt", "a") as f:
        f.write(json.dumps(args) + "\n")

    try:
        if args["status"] == "resolved":
            thread = threading.Thread(target=gen_diagnostic_file, args=(args,))
            thread.start()
    except Exception as e:
        logging.error(e)

    return {
        "code": 0,
        "msg": "success",
        "data": ""
    }


def gen_diagnostic_file(args):
    alerts = args.get("alerts", [])

    alert_time = alerts[0].get("startsAt")
    alert_time = alert_time[:-4] + 'Z'
    alert_time = datetime.strptime(alert_time, "%Y-%m-%dT%H:%M:%S.%fZ")

    start_seconds = alert_time.timestamp() - 60 * 5
    end_seconds = alert_time.timestamp() + 60

    exceptions = obtain_exceptions_in_times(start_seconds, end_seconds)
    slow_queries = obtain_slow_queries(start_seconds, end_seconds)

    diagnostic_file_data = {
        "start_time": start_seconds,
        "end_time": end_seconds,
        "start_timestamp": datetime.fromtimestamp(start_seconds).strftime("%Y-%m-%d %H:%M:%S"),
        "end_timestamp": datetime.fromtimestamp(end_seconds).strftime("%Y-%m-%d %H:%M:%S"),
        "alerts": [alerts],
        "workload": [],
        "slow_queries": slow_queries,
        "exceptions": exceptions
    }

    path = './gen_diagnostic_files'
    if not os.path.exists(path):
        os.makedirs(path)

    filename = 'alert_time_' + datetime.fromtimestamp(start_seconds).strftime("%Y-%m-%d-%H-%M-%S") + '.json'
    with open(os.path.join(path, filename), 'w') as f:
        json.dump(diagnostic_file_data, f)


if __name__ == "__main__":
    uvicorn.run(
        app=app,
        host="0.0.0.0",
        port=8023
    )
