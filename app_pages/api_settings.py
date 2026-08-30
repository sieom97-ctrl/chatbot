"""API 연결 — 챗봇 답변을 다듬어주는 LLM API 연결을 설정하고 테스트한다.

API 키는 세션에만 보관하고 디스크에는 저장하지 않는다(보안). 모델·온도 등
비밀이 아닌 설정만 data/api_settings.json에 저장되어 다음 실행에도 유지된다.
"""

import streamlit as st

from utils.engine import PROVIDER_LABELS, PROVIDER_MODELS, save_api_settings, test_api_connection

st.title("🔑 API 연결")
st.caption(
    "여기서 연결한 API는 챗봇이 검색된 RAG 데이터를 근거로 더 자연스러운 문장을 "
    "생성할 때 사용됩니다. 연결하지 않아도 챗봇은 동작하며, 이 경우 검색된 데이터의 "
    "답변 원문을 그대로 보여줍니다."
)

with st.expander("❓ 이 페이지는 무엇인가요?"):
    st.markdown(
        "- 챗봇의 검색 자체는 이 API와 무관하게 항상 동작합니다. 여기서는 검색된 결과를 "
        "**더 자연스러운 문장으로 다듬어줄지**만 결정합니다.\n"
        "- 아래 **'LLM으로 답변 다듬기 사용'**을 꺼두면 API 키가 있어도 RAG 원문 그대로 답합니다 — "
        "연결된 LLM 성능이 낮다면 이 방식이 더 정확할 수 있습니다.\n"
        "- API 키는 **이 브라우저 세션에서만** 기억되며 파일로 저장되지 않으니, 앱을 다시 켤 때마다 "
        "다시 입력해야 합니다."
    )

settings = st.session_state.api_settings

status_ok = bool(st.session_state.api_key) and settings.get("use_llm", False)
st.container(border=True).markdown(
    f"**현재 상태:** {':green[🟢 연결됨 — LLM으로 답변을 다듬습니다]' if status_ok else ':gray[⚪ 미사용 — 검색 결과 원문으로 답변합니다]'}"
)

# 제공자는 폼 바깥에 두어, 고르는 즉시 아래 모델 목록이 그 제공자의 것으로 바로 바뀌게 한다.
# (폼 안에 있으면 '저장'을 누르기 전까지 목록이 갱신되지 않아 헷갈릴 수 있다.)
provider = st.selectbox(
    "제공자",
    list(PROVIDER_LABELS.keys()),
    index=list(PROVIDER_LABELS.keys()).index(settings.get("provider", "openai"))
    if settings.get("provider") in PROVIDER_LABELS
    else 0,
    format_func=lambda k: PROVIDER_LABELS[k],
    help="ChatGPT(OpenAI)와 Claude(Anthropic) 중 사용할 제공자를 고르세요. 고른 뒤 아래 모델 목록이 바로 바뀝니다.",
)

with st.form("api_settings_form"):
    model_options = PROVIDER_MODELS[provider]
    saved_model = settings.get("model")
    model = st.selectbox(
        "모델",
        model_options,
        index=model_options.index(saved_model) if saved_model in model_options else 0,
        help="더 가볍고 저렴한 모델일수록 빠르지만 답변 품질은 낮을 수 있습니다. 앞쪽에 있을수록 더 성능이 좋은 모델입니다.",
    )
    if provider == "anthropic":
        st.caption("ℹ️ Claude(Anthropic) 모델은 현재 온도(temperature) 조절을 지원하지 않아 이 값은 사용되지 않습니다.")
        temperature = settings.get("temperature", 0.3)
    else:
        temperature = st.slider(
            "온도(temperature)",
            min_value=0.0,
            max_value=1.0,
            value=float(settings.get("temperature", 0.3)),
            step=0.1,
            help="낮을수록 사실 기반의 일관된 답변, 높을수록 다양하고 자유로운 표현.",
        )
    api_key = st.text_input(
        "API 키",
        value=st.session_state.api_key,
        type="password",
        help="이 값은 브라우저 세션에만 보관되며 파일에 저장되지 않습니다. 앱을 껐다 켜면 다시 입력해야 합니다.",
    )
    use_llm = st.toggle(
        "LLM으로 답변 다듬기 사용",
        value=settings.get("use_llm", False),
        help="끄면 API 키가 있어도 검색된 데이터의 답변 원문을 그대로 보여줍니다.",
    )

    submitted = st.form_submit_button("저장", type="primary")
    if submitted:
        st.session_state.api_key = api_key
        new_settings = {
            "provider": provider,
            "model": model,
            "temperature": temperature,
            "use_llm": use_llm,
        }
        st.session_state.api_settings = new_settings
        save_api_settings(new_settings)
        st.success("설정을 저장했습니다. (API 키는 이번 세션에서만 사용됩니다)")
        st.rerun()

st.divider()
st.subheader("연결 테스트")
st.caption("저장된 키로 실제 API를 한 번 호출해 연결이 되는지 확인합니다.")
if st.button(
    "연결 테스트 실행",
    icon=":material/wifi_tethering:",
    help="입력한 API 키로 아주 짧은 메시지 하나를 실제로 보내봅니다. 요금이 극히 소액 발생할 수 있습니다.",
):
    if not st.session_state.api_key:
        st.warning("먼저 위에서 API 키를 입력하고 저장해주세요.")
    else:
        with st.spinner("연결 확인 중..."):
            ok, message = test_api_connection(
                st.session_state.api_key,
                st.session_state.api_settings.get("model", "gpt-4o-mini"),
                st.session_state.api_settings.get("provider", "openai"),
            )
        if ok:
            st.success(message)
        else:
            st.error(message)
