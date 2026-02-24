import copy
import json
import time
import re
import streamlit as st
from streamlit.components.v1 import declare_component
import os
from webui_pages.utils import *
from server.knowledge_base.utils import DIAGNOSE_FILE_DICT
from webui_pages.translations import get_text

def get_node_data(lang):
    return {
        'nodes': [
            {
                'id': 'A',
                'userData': {
                    'title': get_text(lang, 'init_expert_role'),
                    'content': '',
                    'messages': [],
                    'isCompleted': False,
                    'isRuning': False
                },
                'render': 'titleContentNode',
                'top': 20,
                'left': 120,
                'endpoints': [
                    {
                        'id': 'bottom',
                        'orientation': [0, 1]
                    }
                ]
            },
            {
                'id': 'B',
                'userData': {
                    'title': get_text(lang, 'init_diagnosis_report'),
                    'content': '',
                    'messages': [],
                    'isCompleted': False,
                    'isRuning': False
                },
                'render': 'titleContentNode',
                'top': 150,
                'left': 120,
                'endpoints': [
                    {
                        'id': 'top',
                        'orientation': [0, -1]
                    },
                    {
                        'id': 'bottom',
                        'orientation': [0, 1]
                    }
                ]
            },
            {
                'id': 'C',
                'userData': {
                    'title': get_text(lang, 'assign_experts'),
                    'content': '',
                    'messages': [],
                    'isCompleted': False,
                    'isRuning': False
                },
                'render': 'titleContentNode',
                'top': 280,
                'left': 120,
                'endpoints': [
                    {
                        'id': 'top',
                        'orientation': [0, -1]
                    },
                    {
                        'id': 'bottom',
                        'orientation': [0, 1]
                    }
                ]
            },
            {
                'id': 'D',
                'userData': {
                    'title': get_text(lang, 'expert_diagnosis'),
                    'content': '',
                    'isCompleted': False,
                    'isRuning': False,
                    'expertData': []
                },
                'render': 'agentGroupNode',
                'top': 410,
                'left': 40,
                'endpoints': [
                    {
                        'id': 'top',
                        'orientation': [0, -1]
                    },
                    {
                        'id': 'bottom',
                        'orientation': [0, 1]
                    }
                ]
            },
            {
                'id': 'E',
                'userData': {
                    'title': get_text(lang, 'roundtable_discussion'),
                    'content': '',
                    'messages': [],
                    'isCompleted': False,
                    'isRuning': False,
                    'expertData': []
                },
                'render': 'titleContentNode',
                'top': 620,
                'left': 120,
                'endpoints': [
                    {
                        'id': 'top',
                        'orientation': [0, -1]
                    },
                    {
                        'id': 'bottom',
                        'orientation': [0, 1]
                    }
                ]
            },
            {
                'id': 'F',
                'userData': {
                    'title': get_text(lang, 'report_generation'),
                    'content': '',
                    'messages': '',
                    'isCompleted': False,
                    'isRuning': False
                },
                'render': 'titleContentNode',
                'top': 750,
                'left': 120,
                'endpoints': [
                    {
                        'id': 'top',
                        'orientation': [0, -1]
                    }
                ]
            }
        ],
        'edges': [
            {
                'id': '1',
                'source': 'bottom',
                'target': 'top',
                'sourceNode': 'A',
                'targetNode': 'B',
                'type': 'endpoint'
            },
            {
                'id': '2',
                'source': 'bottom',
                'target': 'top',
                'sourceNode': 'B',
                'targetNode': 'C',
                'type': 'endpoint'
            },
            {
                'id': '3',
                'source': 'bottom',
                'target': 'top',
                'sourceNode': 'C',
                'targetNode': 'D',
                'type': 'endpoint'
            },
            {
                'id': '4',
                'source': 'bottom',
                'target': 'top',
                'sourceNode': 'D',
                'targetNode': 'E',
                'type': 'endpoint'
            },
            {
                'id': '5',
                'source': 'bottom',
                'target': 'top',
                'sourceNode': 'E',
                'targetNode': 'F',
                'type': 'endpoint'
            }
        ],
        'isDiagnosing': False
    }

def diagnose_page(api: ApiRequest, is_lite: bool = None):
    lang = st.session_state.get("language", "en")
    NODE_DATA = get_node_data(lang)
    
    if 'diagnosing' not in st.session_state:
        st.session_state['diagnosing'] = False

    if 'diagnose_api' not in st.session_state:
        st.session_state['diagnose_api'] = None

    if 'diagnose_file' not in st.session_state:
        st.session_state['diagnose_file'] = None

    if 'diagnose_file_content' not in st.session_state:
        st.session_state['diagnose_file_content'] = {}

    if 'task_output' not in st.session_state:
        st.session_state['task_output'] = ''

    if 'diagnose_component' not in st.session_state:
        st.session_state['diagnose_component'] = False

    if 'node_data' not in st.session_state:
        st.session_state['node_data'] = NODE_DATA

    col1, col2 = st.columns([2, 3])

    with col1:
        diagnose_component = declare_component('my_component', path=os.path.join(os.path.dirname(__file__), 'streamlit-vue-flow/build_dist'))
        # diagnose_component = declare_component('my_component', url='http://localhost:3001')
        args = {'width': '500px', 'height': '860px', 'nodeData': st.session_state['node_data']}
        diagnose_component(args=args)

    with col2:

        st.session_state['diagnose_file'] = st.file_uploader(get_text(lang, 'upload_anomaly_file'), [i for ls in DIAGNOSE_FILE_DICT.values() for i in ls], accept_multiple_files=False, disabled=st.session_state['diagnosing'])
        if st.session_state['diagnose_file']:
            with st.status(label=get_text(lang, 'anomaly_file_content'), expanded=False):
                with st.container(height=400):
                    content_container = st.empty()
                    file_bytes_data = st.session_state['diagnose_file'].read()
                    file_str_data = file_bytes_data.decode()
                    try:
                        json_data = json.loads(file_str_data)
                        content_container.code(json.dumps(json_data, indent=4), language='json')
                    except ValueError:
                        content_container.warning(get_text(lang, 'invalid_json'))

        if st.session_state['diagnosing']:
            if st.session_state['diagnosing']:
                if st.button(get_text(lang, 'stop_diagnosis')):
                    resp = api.stop_diagnose()
                    if msg := check_error_msg(resp):
                        st.error(msg)
                    else:
                        st.session_state['diagnosing'] = False
        else:
            if st.session_state['diagnose_file']:
                if st.button(get_text(lang, 'upload_and_diagnosis')):
                    filename = st.session_state['diagnose_file'].name
                    st.session_state['diagnose_file'].seek(0)
                    file_content = st.session_state['diagnose_file'].read()
                    resp = api.diagnose_file(filename, file_content)
                    if msg := check_error_msg(resp):
                        st.error(msg)
                    st.session_state['diagnosing'] = True
                    deal_node_data(NODE_DATA)


        diagnose_process(api, NODE_DATA)

def extract_flows(log_text):
    pattern = r'<flow>(.*?)</flow>'
    matches = re.findall(pattern, log_text)

    flow_jsons = []
    for match in matches:
        # match = match.replace("'", '"')
        try:
            flow_json = json.loads(match)
            flow_jsons.append(flow_json)
        except json.JSONDecodeError as error:
            print(error)
            print(f"Could not decode string to json: {match[0: 100]}")

    return flow_jsons

def remove_duplicates(flows):
    """
    """
    temp_dict = {}
    for flow in flows:
        title = flow['title']
        temp_dict[title] = flow
    unique_flows = list(temp_dict.values())
    return unique_flows

def deal_node_data(NODE_DATA):
    text = st.session_state['task_output']
    flows = extract_flows(text)
    flows = remove_duplicates(flows)
    if not flows:
        if st.session_state['node_data'] != NODE_DATA:
            st.session_state['node_data'] = copy.deepcopy(NODE_DATA)
            st.rerun()
    else:
        new_node_data = copy.deepcopy(NODE_DATA)
        for (index, node) in enumerate(new_node_data['nodes']):
            user_data = node['userData']
            for flow in flows:
                if user_data.get('title') == flow.get("title"):
                    node['userData'] = flow
                    # print(node['userData'].get('messages', []))
                    new_node_data['nodes'][index] = node
        
        if st.session_state['node_data'] != new_node_data:
            st.session_state['node_data'] = new_node_data
            st.rerun()

def diagnose_process(r_api, NODE_DATA):
    lang = st.session_state.get("language", "en")
    with (st.status(label=get_text(lang, 'diagnosing'), expanded=True) as status):
        with st.container(height=500):
            code_placeholder = st.empty()
            while True:
                status_response = r_api.diagnose_status()
                if msg := check_error_msg(status_response):
                    st.error(msg)
                if not status_response['is_alive']:
                    st.session_state['diagnosing'] = False
                    status.update(label=get_text(lang, 'no_diagnosis_task'), expanded=True, state='complete')
                else:
                    st.session_state['diagnosing'] = True

                response = r_api.diagnose_output()
                if msg := check_error_msg(response):
                    st.error(msg)
                st.session_state['task_output'] = str(response['output'])
                code_placeholder.code(st.session_state['task_output'], language='powershell')
                deal_node_data(NODE_DATA)

                if not st.session_state['diagnosing']:
                    break
                time.sleep(2)

