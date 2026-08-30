"""위젯 미리보기 — 실제 독립기념관 홈페이지 위에 우리 챗봇 위젯을 얹어서 보여준다.

배경은 인터넷에서 실시간으로 불러온 실제 독립기념관 홈페이지(i815.or.kr)이며,
우측 하단에는 실제 사이트에 원래 있는 makebot.ai 챗봇 위젯 대신 우리가 만든
위젯이 항상 위에 그려진다. iframe은 교차 출처(cross-origin)라 원본 사이트의
위젯을 DOM에서 직접 제거할 수는 없지만, 같은 모서리에 더 높은 z-index로
우리 위젯을 그려서 화면상으로는 원래 위젯을 완전히 가리고 대체한 것처럼 보인다.
"""

import streamlit as st

from utils.engine import (
    SYMBOL_PATH,
    generate_answer,
    hex_to_rgba,
    position_css,
    record_interaction,
    search_knowledge_base,
    shadow_css,
)

REAL_SITE_URL = "https://i815.or.kr"

# 방문자가 위젯 안에서 직접 조절하는 값(글자 크기·창 크기·위치). 관리자가 챗봇설정에서
# 정하는 기본값과는 별개로, 이 브라우저 세션에서만 적용되는 개인화 설정이다(실제
# 공공기관 챗봇 위젯의 "글자 크게/작게" 접근성 기능과 같은 개념).
FONT_SIZE_STEPS = {"작게": 13, "보통": 14, "크게": 17}
PANEL_SIZE_STEPS = {"작게": 0.85, "보통": 1.0, "크게": 1.15}
POSITION_LABELS = {
    "bottom-right": "오른쪽 아래",
    "bottom-left": "왼쪽 아래",
    "top-right": "오른쪽 위",
    "top-left": "왼쪽 위",
}

settings = st.session_state.widget_settings

st.session_state.setdefault("widget_font_choice", "보통")
st.session_state.setdefault("widget_size_choice", "보통")
st.session_state.setdefault("widget_position_override", settings["position"])


def _reset_widget_prefs(default_position: str) -> None:
    """'기본값으로' 버튼의 on_click 콜백. 위젯이 다시 그려지기 전에 실행되므로,
    이미 인스턴스화된 위젯과 같은 키를 안전하게 재설정할 수 있다."""
    st.session_state.widget_font_choice = "보통"
    st.session_state.widget_size_choice = "보통"
    st.session_state.widget_position_override = default_position

# ----------------------------- 실제 홈페이지 (실시간 임베드) -----------------------------

st.caption(
    "아래는 실제 독립기념관 홈페이지(i815.or.kr)를 인터넷에서 그대로 불러온 화면입니다. "
    "원래 사이트에 있는 챗봇 위젯 자리에, 우측 하단에 떠 있는 우리 챗봇 위젯이 항상 위에 "
    "그려져 실제 위젯을 대체합니다. 위젯의 문구·위치·디자인은 관리자 챗봇설정 > 위젯 설정에서 바꿀 수 있습니다."
)
st.iframe(REAL_SITE_URL, height=900)


# ----------------------------- 플로팅 챗봇 위젯 -----------------------------

# position:fixed로 띄운 패널은 정상 문서 흐름을 벗어나므로, 배경이 투명하면 뒤쪽
# 홈페이지 콘텐츠가 패널 안으로 비쳐 보인다(Streamlit 컨테이너는 기본적으로 배경이
# 투명하고 body의 흰 배경에 의존하기 때문). 위젯 설정에서 지정한 배경색·투명도를
# 명시적으로 적용한다.
#
# 위치·창 크기는 관리자 기본값을, 방문자가 위젯 안에서 직접 바꾼 값이 있으면 그것을
# 우선한다. Streamlit 기본 폰트(16px 기준)는 340px 너비의 좁은 패널 안에서는 상대적으로
# 커 보이므로, 실제 위젯처럼 조금 더 작은 크기를 기본값으로 하고 방문자가 조절할 수
# 있게 한다.
# segmented_control은 이미 선택된 항목을 다시 누르면 선택이 풀려 None이 될 수 있으므로
# (required=True를 줘도 마찬가지), 조회 시점에 안전하게 기본값으로 되돌린다.
effective_position = st.session_state.widget_position_override or settings["position"]
size_scale = PANEL_SIZE_STEPS.get(st.session_state.widget_size_choice, PANEL_SIZE_STEPS["보통"])
font_px = FONT_SIZE_STEPS.get(st.session_state.widget_font_choice, FONT_SIZE_STEPS["보통"])
panel_width = round(settings["panel_width"] * size_scale)
panel_height = round(settings["panel_height"] * size_scale)
messages_height = round(settings["messages_height"] * size_scale)

accent = settings["accent_color"]
corner_css = position_css(effective_position, settings["margin_x"], settings["margin_y"])
panel_bg = hex_to_rgba(settings["panel_bg_color"], settings["panel_opacity"])
radius = settings["border_radius"]
shadow = shadow_css(settings["shadow_strength"])
vertical_edge = "top" if effective_position.startswith("top") else "bottom"

st.html(
    f"""
    <style>
    .st-key-chat_fab {{ position: fixed; {corner_css} z-index: 999999; }}
    .st-key-chat_fab button {{
        border-radius: 999px !important;
        padding: 0.9rem 1.5rem !important;
        box-shadow: 0 8px 28px rgba(0, 0, 0, 0.28) !important;
        font-weight: 600 !important;
        background-color: {accent} !important;
        border-color: {accent} !important;
        color: #ffffff !important;
    }}
    .st-key-chat_panel {{
        position: fixed !important;
        {corner_css}
        width: {panel_width}px !important;
        max-width: calc(100vw - 32px);
        z-index: 999999;
        border-radius: {radius}px !important;
        overflow: hidden;
        background-color: {panel_bg} !important;
        backdrop-filter: blur({6 if settings["panel_opacity"] < 1.0 else 0}px);
        border: 1px solid rgba(49, 51, 63, 0.1) !important;
        box-shadow: {shadow};
        transition: width 0.15s ease, height 0.15s ease;
    }}
    /* 방문자가 "글자 크게/작게"로 조절하는 값 — 헤더 제목은 그대로 두고, 실제 대화
       내용(메시지 영역)과 입력창 글자 크기만 바꾼다. 실제 위젯도 헤더는 도드라지고
       본문 텍스트만 작고 컴팩트한 구조다. */
    .st-key-chat_messages_area p,
    .st-key-chat_messages_area span,
    .st-key-chat_messages_area li,
    .st-key-chat_messages_area div[data-testid="stMarkdownContainer"] {{
        font-size: {font_px}px !important;
        line-height: 1.5 !important;
    }}
    .st-key-chat_panel div[data-testid="stChatInput"] textarea {{
        font-size: {font_px}px !important;
    }}
    /* 헤더의 설정(톱니바퀴) 버튼 — 테두리를 없애 아이콘만 보이게 하고, 컬럼 안에서
       가운데로 오도록 정렬한다. */
    .st-key-chat_settings_popover {{
        display: flex !important;
        justify-content: center !important;
    }}
    .st-key-chat_settings_popover button {{
        border: none !important;
        background: transparent !important;
        box-shadow: none !important;
        padding: 0.25rem !important;
    }}
    @media (max-width: 480px) {{
        .st-key-chat_panel {{
            right: 12px !important;
            left: 12px;
            {vertical_edge}: 12px;
            width: auto !important;
            max-width: none;
        }}
    }}
    </style>
    """
)

if not st.session_state.widget_open:
    if st.button(
        settings["fab_label"],
        key="chat_fab",
        type="primary",
        icon=":material/chat:",
        help="독립기념관에 대해 궁금한 점을 물어보세요",
    ):
        st.session_state.widget_open = True
        st.rerun()
else:
    with st.container(key="chat_panel", height=panel_height, border=True, width=panel_width):
        header_left, header_settings, header_close = st.columns([4, 1, 1], vertical_alignment="center")
        with header_left:
            with st.container(horizontal=True, vertical_alignment="center", gap="small"):
                st.image(str(SYMBOL_PATH), width=22)
                st.markdown(f"**{settings['panel_title']}**")
        with header_settings:
            with st.popover(
                " ",
                icon=":material/settings:",
                width="stretch",
                key="chat_settings_popover",
                help="글자 크기·창 크기·화면 위치를 이 대화창에서 바로 바꿀 수 있습니다.",
            ):
                st.markdown("**보기 설정**")
                st.caption("이 브라우저에서만 적용되며, 대화 내용에는 영향을 주지 않습니다.")

                st.segmented_control(
                    "글자 크기", list(FONT_SIZE_STEPS.keys()), key="widget_font_choice", required=True
                )
                st.segmented_control(
                    "창 크기", list(PANEL_SIZE_STEPS.keys()), key="widget_size_choice", required=True
                )
                st.segmented_control(
                    "화면 위치",
                    list(POSITION_LABELS.keys()),
                    format_func=lambda k: POSITION_LABELS[k],
                    key="widget_position_override",
                    required=True,
                )
                # 이미 선택된 항목을 다시 누르면 선택이 풀려 None이 될 수 있다(위쪽의
                # 안전한 기본값 치환으로 화면 계산은 문제없다). Streamlit은 위젯이 그려진
                # 뒤 같은 키의 session_state를 스크립트 본문에서 직접 대입하는 것은
                # 금지하지만, 위젯이 다시 그려지기 "전에" 실행되는 on_click 콜백 안에서는
                # 허용하므로 초기화 버튼은 콜백으로 처리한다.
                st.button(
                    "기본값으로",
                    key="widget_prefs_reset",
                    width="stretch",
                    on_click=_reset_widget_prefs,
                    args=(settings["position"],),
                )
        with header_close:
            if st.button("✕", key="chat_close", help="닫기"):
                st.session_state.widget_open = False
                st.rerun()

        messages_area = st.container(height=messages_height, key="chat_messages_area")

        user_input = st.chat_input(settings["chat_placeholder"])
        if user_input:
            st.session_state.chat_history.append({"role": "user", "content": user_input})

            combined_data = st.session_state.kb_data + st.session_state.rag_chunks
            matches = search_knowledge_base(
                user_input,
                combined_data,
                st.session_state.synonym_dict,
                top_k=settings["top_k"],
                score_threshold=settings["score_threshold"],
            )
            record_interaction(user_input, matches)
            answer = generate_answer(
                user_input,
                matches,
                st.session_state.api_key,
                st.session_state.api_settings,
                fallback_message=settings["fallback_message"],
            )

            st.session_state.chat_history.append(
                {"role": "assistant", "content": answer, "matches": matches}
            )

        with messages_area:
            for msg in st.session_state.chat_history:
                avatar = str(SYMBOL_PATH) if msg["role"] == "assistant" else None
                with st.chat_message(msg["role"], avatar=avatar):
                    st.markdown(msg["content"])
                    if msg.get("matches"):
                        with st.expander("참고한 데이터 보기"):
                            for m in msg["matches"]:
                                st.markdown(f"- **[{m['category']}] {m['question']}**: {m['answer']}")
