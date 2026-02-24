import streamlit as st

from webui_pages.diagnose import diagnose_page
from webui_pages.reports.resports import reports_page
from webui_pages.utils import *
from streamlit_option_menu import option_menu
from webui_pages.dialogue.dialogue import dialogue_page
from webui_pages.knowledge_base import knowledge_base_page
from webui_pages.translations import get_text

import os
import sys
from configs import VERSION
from server.utils import api_address


api = ApiRequest(base_url=api_address())

if __name__ == "__main__":
    is_lite = "lite" in sys.argv

    st.set_page_config(
        "Anomivox",
        os.path.join("img", "chat_icon_blue_square_v2.png"),
        layout="wide",
        initial_sidebar_state="expanded"
    )

    if "language" not in st.session_state:
        st.session_state.language = "en"

    lang = st.session_state.language

    css = """
    <style>
        .block-container {
            padding-left: 20px !important;
            padding-right: 20px !important;
            padding-top: 40px !important;
            padding-bottom: 40px !important;
        }
        /* Modern UI Enhancements */
        .stApp {
            background-color: #f8f9fa;
        }
        .css-1d391kg {
            background-color: #ffffff;
            border-right: 1px solid #e9ecef;
        }
        .stButton>button {
            border-radius: 8px;
            font-weight: 600;
            transition: all 0.3s ease;
        }
        .stButton>button:hover {
            transform: translateY(-2px);
            box-shadow: 0 4px 6px rgba(0,0,0,0.1);
        }
        .stSelectbox>div>div {
            border-radius: 8px;
        }
        .stTextInput>div>div>input {
            border-radius: 8px;
        }
        .sidebar-logo {
            text-align: center;
            padding: 20px 0;
            margin-bottom: 20px;
            border-bottom: 1px solid #e9ecef;
        }
        .sidebar-logo h1 {
            color: #2c3e50;
            font-size: 24px;
            font-weight: 700;
            margin: 0;
            background: linear-gradient(135deg, #1e3c72 0%, #2a5298 100%);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
        }
        .sidebar-logo p {
            color: #6c757d;
            font-size: 12px;
            margin: 5px 0 0 0;
        }
    </style>
    """
    st.write(css, unsafe_allow_html=True)

    pages = {
        get_text(lang, "knowledge_base"): {
            "icon": "hdd-stack",
            "func": knowledge_base_page,
        },
        get_text(lang, "chat"): {
            "icon": "chat",
            "func": dialogue_page,
        },
        get_text(lang, "diagnosis"): {
            "icon": "heart-pulse",
            "func": diagnose_page,
        },
        get_text(lang, "history"): {
            "icon": "file-earmark-text",
            "func": reports_page,
        }
    }

    with st.sidebar:
        st.markdown(f"""
            <div class="sidebar-logo">
                <h1>Anomivox</h1>
                <p>{get_text(lang, "description")}</p>
            </div>
        """, unsafe_allow_html=True)
        
        # Language Selector
        lang_options = {"en": "English", "tr": "Türkçe"}
        selected_lang_name = st.selectbox(
            get_text(lang, "select_language"),
            options=list(lang_options.values()),
            index=list(lang_options.keys()).index(st.session_state.language)
        )
        
        # Update language if changed
        new_lang = [k for k, v in lang_options.items() if v == selected_lang_name][0]
        if new_lang != st.session_state.language:
            st.session_state.language = new_lang
            st.rerun()

        st.divider()

        options = list(pages)
        icons = [x["icon"] for x in pages.values()]

        default_index = 0
        selected_page = option_menu(
            "",
            options=options,
            icons=icons,
            default_index=default_index,
            styles={
                "container": {"padding": "0!important", "background-color": "transparent"},
                "icon": {"color": "#2c3e50", "font-size": "18px"}, 
                "nav-link": {"font-size": "16px", "text-align": "left", "margin":"0px", "--hover-color": "#e9ecef", "color": "#495057", "border-radius": "8px"},
                "nav-link-selected": {"background-color": "#e9ecef", "color": "#1e3c72", "font-weight": "600"},
            }
        )
        
        st.divider()
        st.caption(
            f"""<p align="center" style="color: #adb5bd;">{get_text(lang, "version")}：{VERSION}</p>""",
            unsafe_allow_html=True,
        )

    if selected_page in pages:
        pages[selected_page]["func"](api=api, is_lite=is_lite)
