import os
import requests

prometheus_api_url = os.environ.get("PROMETHEUS_URL", "http://prometheus:9090") + "/api/v1/query"

cpu_query = '100 - (avg by (instance) (irate(node_cpu_seconds_total{instance="node_exporter:9100",mode="idle"}[5m])) * 100)'

memory_query = '(node_memory_MemTotal_bytes{instance="node_exporter:9100"} - node_memory_MemAvailable_bytes{instance="node_exporter:9100"}) / node_memory_MemTotal_bytes{instance="node_exporter:9100"} * 100'

def query_prometheus(query):
    response = requests.get(prometheus_api_url, params={'query': query})
    if response.status_code == 200:
        print(response)
        return response.json()
    else:
        return f"Error: {response.status_code}"

def restart_decision():
    cpu_usage = query_prometheus(cpu_query)
    memory_usage = query_prometheus(memory_query)

    print("cpu_usage: ", cpu_usage, " memory_usage: ", memory_usage)
    cpu_usage_value = cpu_usage['data']['result'][0]['value'][1] 
    cpu=int(float(cpu_usage_value))
    memory_usage_value = memory_usage['data']['result'][0]['value'][1] 
    mem=int(float(memory_usage_value))
    print("CPU Usage:", cpu_usage_value, "%")
    print("Memory Usage:", memory_usage_value, "%")

    return cpu,mem


restart_decision()  
