"""챗봇 테스트 — 위젯을 열지 않고도 관리자가 응답 품질을 확인하는 콘솔.

위젯 미리보기와 동일한 검색/답변 로직을 그대로 사용하지만, 전체 폭 레이아웃과
후보 점수 디버그 정보를 함께 제공해 튜닝(동의어 사전, 임계값 등)에 활용할 수 있다.
"""

import streamlit as st

from utils.engine import generate_answer, score_all, search_knowledge_base

st.title("🧪 챗봇 테스트")
st.caption(
    "위젯과 동일한 검색·답변 로직을 사용하는 관리자용 테스트 콘솔입니다. "
    "RAG 문서나 위젯 설정을 바꾼 뒤 여기서 바로 결과를 확인해보세요. "
    "단, 여기서의 질문은 실제 방문자 통계(RAG 관리 > 사용 현황)에는 반영되지 않습니다."
)

with st.expander("❓ 이 페이지는 무엇인가요?"):
    st.markdown(
        "- 위젯을 열지 않고도 **똑같은 검색·답변 로직**으로 질문에 답해봅니다. RAG 문서나 "
        "위젯 설정(검색 민감도 등)을 바꾼 직후 바로 테스트하기 좋습니다.\n"
        "- **'검색 후보 점수 보기'**를 켜면 어떤 항목이 왜 선택/탈락했는지 점수와 함께 볼 수 있어, "
        "동의어 사전이나 유사도 임계값을 조정할 때 유용합니다.\n"
        "- 여기서의 대화는 실제 방문자 통계에 섞이지 않으니 마음껏 테스트해도 됩니다."
    )

settings = st.session_state.widget_settings

with st.container(horizontal=True, horizontal_alignment="right"):
    show_debug = st.toggle(
        "검색 후보 점수 보기",
        value=False,
        key="test_show_debug",
        help="켜면 각 답변 아래에 상위 8개 후보와 점수를 함께 표시합니다.",
    )
    if st.button("대화 초기화", icon=":material/refresh:", help="이 테스트 콘솔의 대화 내용만 지웁니다."):
        st.session_state.test_chat_history = [
            {
                "role": "assistant",
                "content": "관리자 테스트 콘솔입니다. 질문을 입력하면 위젯과 동일한 로직으로 답변합니다.",
            }
        ]
        st.rerun()

messages = st.container(height=480, border=True)

user_input = st.chat_input("테스트할 질문을 입력하세요")
if user_input:
    st.session_state.test_chat_history.append({"role": "user", "content": user_input})

    combined_data = st.session_state.kb_data + st.session_state.rag_chunks
    matches = search_knowledge_base(
        user_input,
        combined_data,
        st.session_state.synonym_dict,
        top_k=settings["top_k"],
        score_threshold=settings["score_threshold"],
    )
    answer = generate_answer(
        user_input,
        matches,
        st.session_state.api_key,
        st.session_state.api_settings,
        fallback_message=settings["fallback_message"],
    )

    debug_scores = None
    if show_debug:
        debug_scores = score_all(user_input, combined_data, st.session_state.synonym_dict)[:8]

    st.session_state.test_chat_history.append(
        {"role": "assistant", "content": answer, "matches": matches, "debug_scores": debug_scores}
    )

with messages:
    for msg in st.session_state.test_chat_history:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])
            if msg.get("matches"):
                with st.expander("참고한 데이터 보기"):
                    for m in msg["matches"]:
                        st.markdown(f"- **[{m['category']}] {m['question']}**: {m['answer']}")
            if msg.get("debug_scores"):
                with st.expander("🔍 검색 후보 점수 (상위 8개)"):
                    for score, item in msg["debug_scores"]:
                        used = "✅" if item in (msg.get("matches") or []) else "—"
                        st.markdown(f"{used} `{score:.3f}` [{item['category']}] {item['question']}")
