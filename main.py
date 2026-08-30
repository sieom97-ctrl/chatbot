"""독립기념관 챗봇 관리 콘솔 — 진입점.

- "위젯 미리보기": 외부 방문자가 실제 홈페이지에서 보게 될 화면(배경 페이지 + 우측 하단
  플로팅 챗봇 위젯)을 그대로 재현한 화면이다.
- "관리자 챗봇설정" 그룹: 관리자가 위젯의 동작(API 연결, 위젯 문구/동작 설정)과 RAG 지식베이스를
  관리하고, 위젯을 열지 않고도 챗봇 응답을 테스트해볼 수 있는 화면들이다.

공유 데이터(지식베이스, RAG 청크, 설정 등)는 여기서 한 번만 세션 상태에 로드하고,
각 페이지는 st.session_state를 통해 이를 읽고 쓴다.
"""

import streamlit as st

from utils.engine import (
    RAG_DIR,
    load_api_settings,
    load_data,
    load_rag_chunks,
    load_synonym_dict,
    load_widget_settings,
    maybe_run_daily_optimization,
)

st.set_page_config(page_title="독립기념관 챗봇 관리 콘솔", page_icon="🏛️", layout="wide")


def init_shared_state() -> None:
    if "kb_data" not in st.session_state:
        st.session_state.kb_data = load_data()
    if "rag_chunks" not in st.session_state:
        st.session_state.rag_chunks = load_rag_chunks(RAG_DIR)
    if "synonym_dict" not in st.session_state:
        st.session_state.synonym_dict = load_synonym_dict(RAG_DIR)
    if "widget_settings" not in st.session_state:
        st.session_state.widget_settings = load_widget_settings()
    if "api_settings" not in st.session_state:
        st.session_state.api_settings = load_api_settings()
    if "api_key" not in st.session_state:
        # 보안을 위해 API 키는 세션에만 보관하고 파일에는 절대 저장하지 않는다.
        st.session_state.api_key = ""
    if "widget_open" not in st.session_state:
        st.session_state.widget_open = st.session_state.widget_settings.get("default_open", False)
    if "chat_history" not in st.session_state:
        st.session_state.chat_history = [
            {"role": "assistant", "content": st.session_state.widget_settings["greeting"]}
        ]
    if "test_chat_history" not in st.session_state:
        st.session_state.test_chat_history = [
            {
                "role": "assistant",
                "content": "관리자 테스트 콘솔입니다. 질문을 입력하면 위젯과 동일한 로직으로 답변합니다.",
            }
        ]
    if "daily_optimization_checked" not in st.session_state:
        # 앱은 상시 백그라운드 프로세스가 아니므로, 하루 중 처음 열리는 세션이
        # 그날의 RAG 사용량 최적화를 opportunistic하게 대신 실행한다(세션당 최대 1회).
        # 완전히 무인 자동화가 필요하면 scripts/daily_optimize.py를 OS 스케줄러에 등록한다.
        st.session_state.daily_optimization_checked = True
        st.session_state.last_optimization_result = maybe_run_daily_optimization(
            st.session_state.rag_chunks
        )


init_shared_state()

page = st.navigation(
    {
        "": [
            st.Page(
                "app_pages/widget_preview.py",
                title="위젯 미리보기 (사용자 화면)",
                icon=":material/chat_bubble:",
                default=True,
            ),
        ],
        "관리자 챗봇설정": [
            st.Page("app_pages/chatbot_test.py", title="챗봇 테스트", icon=":material/quiz:"),
            st.Page("app_pages/api_settings.py", title="API 연결", icon=":material/key:"),
            st.Page("app_pages/widget_settings.py", title="위젯 설정", icon=":material/tune:"),
            st.Page("app_pages/rag_management.py", title="RAG 관리", icon=":material/database:"),
        ],
    },
    position="sidebar",
)
page.run()
