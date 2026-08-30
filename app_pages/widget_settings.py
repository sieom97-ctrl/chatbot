"""위젯 설정 — 외부 사용자에게 노출되는 챗봇 위젯의 문구·위치·디자인·동작을 관리한다.

여기서 저장한 값은 '위젯 미리보기' 페이지와 실제 배포 시 위젯 렌더링에
그대로 반영된다. data/widget_settings.json에 저장되어 다음 실행에도 유지된다.
"""

import streamlit as st

from utils.engine import (
    DEFAULT_WIDGET_SETTINGS,
    THEME_PRESETS,
    hex_to_rgba,
    position_css,
    save_widget_settings,
    shadow_css,
)

st.title("🎛️ 위젯 설정")
st.caption("문구·위치·디자인을 바꾼 뒤 '위젯 미리보기'에서 실제로 어떻게 보이는지 바로 확인해보세요.")

with st.expander("❓ 이 페이지는 무엇인가요? (처음 사용하신다면 먼저 읽어보세요)"):
    st.markdown(
        "- 여기서 바꾸는 값은 방문자가 실제로 보게 될 **챗봇 위젯(우측 하단 등 화면 모서리에 떠 있는 채팅창)**의 "
        "모양과 문구입니다.\n"
        "- 맨 위 **디자인 프리셋**을 고르면 위치·색상·크기가 한 번에 바뀝니다. 그 아래 폼에서 세부적으로 더 조정할 수 있습니다.\n"
        "- 각 항목 옆의 물음표(❓) 아이콘에 마우스를 올리면 짧은 설명이 말풍선으로 나타납니다.\n"
        "- 저장 후에는 왼쪽 메뉴의 **'위젯 미리보기'**로 이동해 실제 화면에서 확인하세요."
    )

settings = st.session_state.widget_settings

# ----------------------------- 디자인 프리셋 -----------------------------

st.markdown("### 디자인 프리셋")
st.caption(
    "미리 만들어둔 디자인 조합을 한 번에 적용합니다. 기본값 자체가 '독립기념관 공식 스타일'로 "
    "설정되어 있어, 실제 독립기념관 홈페이지에 있는 챗봇 위젯과 배치·크기·모서리 둥글기가 거의 "
    "동일합니다. 다른 느낌을 원하면 아래에서 다른 프리셋으로 바꿔보세요."
)
preset_cols = st.columns([2, 1])
with preset_cols[0]:
    preset_name = st.selectbox(
        "프리셋 선택",
        list(THEME_PRESETS.keys()),
        help="선택만으로는 아무 것도 바뀌지 않습니다. 오른쪽 '프리셋 적용' 버튼을 눌러야 실제로 반영됩니다.",
        label_visibility="collapsed",
    )
with preset_cols[1]:
    if st.button("✨ 프리셋 적용", width="stretch", help="선택한 프리셋의 위치·색상·크기 값을 아래 폼에 채워 넣고 저장합니다."):
        merged = {**settings, **THEME_PRESETS[preset_name]}
        st.session_state.widget_settings = merged
        save_widget_settings(merged)
        st.success(f"'{preset_name}' 프리셋을 적용했습니다.")
        st.rerun()

st.divider()

# ----------------------------- 세부 설정 폼 -----------------------------

with st.form("widget_settings_form"):
    st.markdown("**문구**")
    panel_title = st.text_input(
        "패널 제목", value=settings["panel_title"], help="위젯을 펼쳤을 때 상단 헤더에 표시되는 이름입니다."
    )
    fab_label = st.text_input(
        "접힌 버튼(FAB) 문구",
        value=settings["fab_label"],
        help="위젯이 접혀 있을 때 화면 모서리에 보이는 버튼에 쓰일 문구입니다. FAB = Floating Action Button(떠 있는 버튼).",
    )
    greeting = st.text_area(
        "첫 인사말", value=settings["greeting"], height=80, help="위젯을 처음 열었을 때 챗봇이 먼저 보내는 메시지입니다."
    )
    chat_placeholder = st.text_input(
        "입력창 안내 문구", value=settings["chat_placeholder"], help="사용자가 아직 아무것도 입력하지 않았을 때 입력창에 흐리게 보이는 문구입니다."
    )
    fallback_message = st.text_area(
        "검색 결과가 없을 때 보여줄 메시지",
        value=settings["fallback_message"],
        height=80,
        help="RAG 데이터에서 답을 찾지 못했을 때 사용자에게 보여줄 문구입니다. 이 경우 질문은 자동으로 'RAG 관리 > 미응답 질문'에 쌓입니다.",
    )

    st.markdown("**위치** — 위젯이 화면 어느 모서리에 붙을지 정합니다.")
    col_pos1, col_pos2, col_pos3 = st.columns(3)
    with col_pos1:
        position_labels = {
            "bottom-right": "오른쪽 아래",
            "bottom-left": "왼쪽 아래",
            "top-right": "오른쪽 위",
            "top-left": "왼쪽 위",
        }
        position = st.selectbox(
            "화면 모서리",
            list(position_labels.keys()),
            index=list(position_labels.keys()).index(settings.get("position", "bottom-right")),
            format_func=lambda k: position_labels[k],
            help="위젯 버튼과 패널이 항상 같은 모서리에 표시됩니다. 실제 홈페이지들은 보통 오른쪽 아래를 사용합니다.",
        )
    with col_pos2:
        margin_x = st.number_input(
            "가로 여백(px)", min_value=0, max_value=100, value=settings.get("margin_x", 24),
            help="선택한 모서리에서 좌우 방향으로 얼마나 떨어뜨릴지입니다.",
        )
    with col_pos3:
        margin_y = st.number_input(
            "세로 여백(px)", min_value=0, max_value=100, value=settings.get("margin_y", 24),
            help="선택한 모서리에서 상하 방향으로 얼마나 떨어뜨릴지입니다.",
        )

    st.markdown("**디자인** — 크기, 색상, 모서리, 투명도, 그림자를 조정합니다.")
    col1, col2 = st.columns(2)
    with col1:
        panel_width = st.number_input(
            "패널 너비(px)", min_value=280, max_value=600, value=settings["panel_width"], step=10,
            help="위젯을 펼쳤을 때 채팅창의 가로 폭입니다.",
        )
        messages_height = st.number_input(
            "메시지 영역 높이(px)", min_value=200, max_value=800, value=settings["messages_height"], step=10,
            help="대화 내용이 표시되는 영역의 높이입니다. 패널 전체 높이보다 작아야 합니다(헤더·입력창 공간 제외).",
        )
        border_radius = st.slider(
            "모서리 둥글기(px)", min_value=0, max_value=32, value=settings.get("border_radius", 16),
            help="0이면 각진 사각형, 값이 클수록 더 둥근 카드 모양이 됩니다. 실제 독립기념관 위젯은 10px입니다.",
        )
    with col2:
        panel_height = st.number_input(
            "패널 전체 높이(px)", min_value=400, max_value=900, value=settings["panel_height"], step=10,
            help="위젯을 펼쳤을 때 채팅창 전체(헤더+대화+입력창)의 세로 높이입니다.",
        )
        accent_color = st.color_picker(
            "강조 색상", value=settings["accent_color"], help="접힌 버튼과 헤더 등 포인트로 쓰이는 색상입니다.",
        )
        panel_bg_color = st.color_picker(
            "패널 배경색", value=settings.get("panel_bg_color", "#FFFFFF"),
            help="채팅창 전체의 바탕색입니다. 너무 어두운 색은 글자가 잘 안 보일 수 있으니 아래 미리보기로 꼭 확인하세요.",
        )

    col3, col4 = st.columns(2)
    with col3:
        panel_opacity_pct = st.slider(
            "패널 투명도(%)", min_value=30, max_value=100, value=int(settings.get("panel_opacity", 1.0) * 100),
            help="100%는 완전히 불투명, 값이 낮을수록 뒤쪽 페이지가 은은하게 비치는 '유리(글래스)' 느낌이 됩니다.",
        )
    with col4:
        shadow_strength = st.slider(
            "그림자 세기", min_value=0, max_value=100, value=settings.get("shadow_strength", 50),
            help="0이면 그림자가 없어 페이지에 납작하게 붙어 보이고, 값이 클수록 떠 있는 느낌이 강해집니다.",
        )

    st.markdown("**검색 동작**")
    col5, col6 = st.columns(2)
    with col5:
        top_k = st.slider(
            "최대 검색 결과 수", min_value=1, max_value=5, value=settings["top_k"],
            help="한 번의 질문에 대해 최대 몇 개의 RAG 항목을 참고 자료로 함께 보여줄지입니다.",
        )
    with col6:
        score_threshold = st.slider(
            "유사도 임계값", min_value=0.0, max_value=0.5, value=settings["score_threshold"], step=0.01,
            help="이 값보다 점수가 낮은 검색 결과는 '모른다'는 답으로 처리합니다. 낮추면 더 적극적으로 답하고, 높이면 더 신중하게 답합니다.",
        )

    default_open = st.checkbox(
        "페이지 진입 시 위젯을 기본으로 펼쳐두기", value=settings["default_open"],
        help="켜두면 방문자가 버튼을 누르지 않아도 채팅창이 처음부터 열려 있는 상태로 보입니다.",
    )

    submitted = st.form_submit_button("저장", type="primary")
    if submitted:
        new_settings = {
            "panel_title": panel_title,
            "fab_label": fab_label,
            "greeting": greeting,
            "chat_placeholder": chat_placeholder,
            "fallback_message": fallback_message,
            "position": position,
            "margin_x": int(margin_x),
            "margin_y": int(margin_y),
            "panel_width": int(panel_width),
            "panel_height": int(panel_height),
            "messages_height": int(messages_height),
            "border_radius": int(border_radius),
            "accent_color": accent_color,
            "panel_bg_color": panel_bg_color,
            "panel_opacity": panel_opacity_pct / 100,
            "shadow_strength": int(shadow_strength),
            "top_k": int(top_k),
            "score_threshold": float(score_threshold),
            "default_open": default_open,
        }
        st.session_state.widget_settings = new_settings
        save_widget_settings(new_settings)
        st.success("위젯 설정을 저장했습니다.")
        st.rerun()

if st.button("기본값으로 초기화", help="모든 위젯 설정을 처음 상태로 되돌립니다. 되돌릴 수 없으니 신중히 눌러주세요."):
    st.session_state.widget_settings = dict(DEFAULT_WIDGET_SETTINGS)
    save_widget_settings(st.session_state.widget_settings)
    st.success("기본값으로 되돌렸습니다.")
    st.rerun()

# ----------------------------- 미니 미리보기 -----------------------------

st.divider()
st.markdown("**모서리 스타일 미니 미리보기**")
st.caption("실제 크기·위치는 반영하지 않고, 색상·모서리 둥글기·투명도·그림자 조합만 빠르게 확인하는 용도입니다.")

preview_bg = hex_to_rgba(settings.get("panel_bg_color", "#FFFFFF"), settings.get("panel_opacity", 1.0))
preview_shadow = shadow_css(settings.get("shadow_strength", 50))
st.html(
    f"""
    <div style="position:relative; height:160px; background:
        repeating-linear-gradient(45deg, #eef0f3, #eef0f3 10px, #e4e7eb 10px, #e4e7eb 20px);
        border-radius:8px; overflow:hidden;">
      <div style="position:absolute; {position_css(settings.get('position','bottom-right'), 12, 12)}
          width:120px; height:80px; border-radius:{settings.get('border_radius', 16)}px;
          background:{preview_bg}; box-shadow:{preview_shadow};
          border:1px solid rgba(49,51,63,0.15);
          display:flex; align-items:center; justify-content:center;
          font-size:12px; color:#31333F;">
        미리보기
      </div>
    </div>
    """
)