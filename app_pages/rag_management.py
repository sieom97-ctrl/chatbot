"""RAG 관리 — 자동 로드된 RAG 문서 현황을 확인하고, 보충 지식베이스를 관리한다.

- "RAG 문서 현황": RAG/*.md 에서 자동 파싱된 청크를 검색/열람하고 다시 불러온다.
- "RAG 분석": 특정 RAG 항목(또는 전체)을 선택하면 청크 수·길이 분포·분포도를 시각화한다.
- "보충 데이터 관리": 관리자가 직접 추가하는 Q&A(JSON/PDF)로, RAG 문서에 없는 내용을 보완한다.
- "동의어 사전": 06_동의어사전_변경이력.md 에서 파싱된 쿼리 확장용 동의어 표를 보여준다.
- "사용 현황 & 최적화": 실제 방문자 질의에서 어떤 RAG 항목이 자주 쓰였는지 보고, 그 결과를
  원본 .md 파일과 자동 생성 리포트에 반영하는 "자기 참조" 최적화를 수동/자동으로 실행한다.
- "미응답 질문": RAG에서 답을 찾지 못한 실제 질문을 검토하고, 조사한 내용을 등록한다.
"""

import uuid

import pandas as pd
import streamlit as st

from utils.engine import (
    CATEGORIES,
    RAG_DIR,
    bow_pca_2d,
    get_usage_stats,
    load_rag_chunks,
    load_synonym_dict,
    load_unanswered,
    load_usage,
    pdf_to_kb_entries,
    resolve_unanswered,
    run_daily_optimization,
    save_data,
)

st.title("🗂️ RAG 관리")
st.caption("위젯과 챗봇 테스트가 참조하는 지식베이스를 이 화면에서 관리합니다.")

with st.expander("❓ 이 페이지는 무엇인가요? (탭별 안내)"):
    st.markdown(
        "- **RAG 문서 현황**: RAG 폴더의 `.md` 파일에서 자동으로 읽어온 항목을 검색·열람합니다. "
        "내용을 고치려면 `.md` 파일을 직접 편집한 뒤 '다시 불러오기'를 누르세요.\n"
        "- **RAG 분석**: 특정 RAG 항목(또는 전체)을 골라 청크 수, 길이 분포, 항목 간 유사도 분포를 "
        "그래프로 확인합니다.\n"
        "- **보충 데이터 관리**: `.md` 파일 없이 화면에서 바로 Q&A를 추가/삭제하거나, PDF를 올려 "
        "자동으로 나눠 등록합니다.\n"
        "- **동의어 사전**: 표현이 달라도 같은 의미로 인식시키는 규칙을 확인합니다(읽기 전용).\n"
        "- **사용 현황 & 최적화**: 어떤 항목이 실제로 자주 쓰이는지 확인하고, 그 결과를 문서에 반영합니다.\n"
        "- **미응답 질문**: 챗봇이 답하지 못한 실제 질문을 확인하고 답변을 등록합니다."
    )

tab_docs, tab_analysis, tab_extra, tab_synonyms, tab_usage, tab_unanswered = st.tabs(
    ["RAG 문서 현황", "RAG 분석", "보충 데이터 관리", "동의어 사전", "사용 현황 & 최적화", "미응답 질문"]
)

# ----------------------------- RAG 문서 현황 -----------------------------

with tab_docs:
    st.markdown(f"RAG 폴더의 `.md` 문서에서 자동으로 불러온 항목 **{len(st.session_state.rag_chunks)}건**")
    st.caption("내용을 바꾸려면 RAG 폴더의 해당 .md 파일을 직접 편집한 뒤 아래 버튼으로 다시 불러오세요.")

    if st.button("🔄 RAG 문서 다시 불러오기", help="RAG 폴더의 .md 파일들을 다시 읽어 최신 내용으로 갱신합니다."):
        st.session_state.rag_chunks = load_rag_chunks(RAG_DIR)
        st.session_state.synonym_dict = load_synonym_dict(RAG_DIR)
        st.success("RAG 문서를 다시 불러왔습니다.")
        st.rerun()

    counts: dict[str, int] = {}
    for chunk in st.session_state.rag_chunks:
        counts[chunk["category"]] = counts.get(chunk["category"], 0) + 1

    if counts:
        cols = st.container(horizontal=True)
        for category, count in counts.items():
            with cols.container(border=True, width=160):
                st.metric(category, f"{count}건")

    st.divider()
    keyword = st.text_input("질문/답변/카테고리로 검색", placeholder="예: 안내견, 주차, 드론")
    rows = st.session_state.rag_chunks
    if keyword:
        needle = keyword.strip().lower()
        rows = [
            r
            for r in rows
            if needle in r["question"].lower()
            or needle in r["answer"].lower()
            or needle in r["category"].lower()
        ]
    st.caption(f"{len(rows)}건 표시 중")
    if rows:
        df = pd.DataFrame(
            [{"카테고리": r["category"], "질문": r["question"], "답변": r["answer"]} for r in rows]
        )
        st.dataframe(df, height=420, column_config={"답변": st.column_config.TextColumn(width="large")})
    else:
        st.info("검색 결과가 없습니다.")


# ----------------------------- RAG 분석 -----------------------------

with tab_analysis:
    st.caption("기존에 등록된 RAG 항목 중 하나(또는 전체)를 골라 구성을 분석합니다.")

    all_chunks = st.session_state.rag_chunks
    if not all_chunks:
        st.info("분석할 RAG 항목이 없습니다. 먼저 'RAG 문서 현황' 탭에서 문서를 불러오세요.")
    else:
        analysis_categories = sorted({c["category"] for c in all_chunks})
        selected_source = st.selectbox(
            "분석할 RAG 항목 선택",
            ["전체"] + analysis_categories,
            help="특정 RAG 파일(카테고리)을 고르면 그 항목만, '전체'를 고르면 로드된 모든 RAG 항목을 분석합니다.",
        )
        analysis_chunks = (
            all_chunks if selected_source == "전체" else [c for c in all_chunks if c["category"] == selected_source]
        )

        df_a = pd.DataFrame(
            [
                {"카테고리": c["category"], "질문": c["question"], "답변": c["answer"], "길이": len(c["answer"])}
                for c in analysis_chunks
            ]
        )

        m1, m2, m3, m4 = st.columns(4)
        m1.metric("청크 수", f"{len(df_a):,}")
        m2.metric("카테고리 수", f"{df_a['카테고리'].nunique()}")
        m3.metric("평균 길이", f"{int(df_a['길이'].mean()):,}자" if len(df_a) else "0자")
        m4.metric("최대 길이", f"{df_a['길이'].max():,}자" if len(df_a) else "0자")

        st.divider()
        chart_col1, chart_col2 = st.columns(2)
        with chart_col1:
            if selected_source == "전체":
                st.markdown("**카테고리별 청크 수**")
                st.caption("RAG 항목(카테고리)마다 청크가 몇 개씩 있는지 보여줍니다.")
                by_cat = df_a.groupby("카테고리").size().rename("청크 수")
                st.bar_chart(by_cat, horizontal=True)
            else:
                st.markdown("**질문 길이 vs 답변 길이**")
                st.caption("각 청크의 질문(헤더) 길이 대비 답변 길이입니다. 점이 오른쪽 아래에 몰려 있으면 헤더는 짧고 내용은 긴 전형적인 FAQ 구조입니다.")
                scatter_df = pd.DataFrame(
                    {"질문 길이": [len(c["question"]) for c in analysis_chunks], "답변 길이": [len(c["answer"]) for c in analysis_chunks]}
                )
                st.scatter_chart(scatter_df, x="질문 길이", y="답변 길이")
        with chart_col2:
            st.markdown("**답변 길이 분포**")
            st.caption("너무 짧은 청크는 정보가 부족하고, 너무 긴 청크는 검색 정확도가 떨어질 수 있습니다.")
            bins = pd.cut(df_a["길이"], bins=min(10, max(1, df_a["길이"].nunique())))
            hist = bins.value_counts().sort_index()
            hist.index = [f"{int(i.left)}~{int(i.right)}자" for i in hist.index]
            st.caption("가로축은 글자 수 구간, 값은 그 구간에 속하는 청크 개수입니다.")
            st.bar_chart(hist)

        st.markdown("**항목 간 분포도 (2D)**")
        st.caption(
            "실제 문장 임베딩 모델 없이, 자주 쓰이는 단어 조합만으로 청크 간 대략적인 거리를 계산해 2차원에 흩뿌린 것입니다. "
            "가까이 모인 점들은 비슷한 단어를 많이 공유한다는 뜻이며, 정밀한 의미 분석은 아닙니다."
        )
        if len(analysis_chunks) >= 3:
            coords = bow_pca_2d(analysis_chunks)
            pca_df = pd.DataFrame(
                {
                    "PC1": coords[:, 0],
                    "PC2": coords[:, 1],
                    "카테고리": [c["category"] for c in analysis_chunks],
                    "질문": [c["question"] for c in analysis_chunks],
                }
            )
            st.scatter_chart(pca_df, x="PC1", y="PC2", color="카테고리")
        else:
            st.info("분포도를 그리려면 청크가 3개 이상 필요합니다.")

        with st.expander(f"청크 목록 보기 ({len(analysis_chunks)}건)"):
            st.dataframe(
                df_a[["카테고리", "질문", "답변"]],
                height=350,
                column_config={"답변": st.column_config.TextColumn(width="large")},
            )


# ----------------------------- 보충 데이터 관리 -----------------------------

with tab_extra:
    st.caption("RAG 문서에 없는 내용을 보완할 때 사용합니다. 여기서 추가한 데이터는 위젯/챗봇 테스트 검색에 함께 포함됩니다.")

    with st.expander("➕ 새 데이터 추가", expanded=True):
        with st.form("add_entry_form", clear_on_submit=True):
            category = st.selectbox("카테고리", CATEGORIES, help="목록·검색 화면에서 분류로 사용됩니다.")
            question = st.text_input("예상 질문", help="사용자가 실제로 물어볼 법한 문장 그대로 적어주세요.")
            answer = st.text_area("답변 내용", help="이 항목이 검색되면 사용자에게 그대로(또는 LLM이 다듬어) 보여집니다.")
            submitted = st.form_submit_button("추가하기")
            if submitted:
                if question.strip() and answer.strip():
                    st.session_state.kb_data.append(
                        {
                            "id": str(uuid.uuid4()),
                            "category": category,
                            "question": question.strip(),
                            "answer": answer.strip(),
                        }
                    )
                    save_data(st.session_state.kb_data)
                    st.success("데이터가 추가되었습니다.")
                else:
                    st.warning("질문과 답변을 모두 입력해 주세요.")

    with st.expander("📥 CSV/JSON 파일로 일괄 업로드"):
        st.caption("CSV: category, question, answer 열 필요 / JSON: 동일한 키를 가진 객체 배열")
        uploaded = st.file_uploader("파일 선택", type=["csv", "json"])
        if uploaded is not None and st.button(
            "업로드한 파일 반영", help="선택한 파일의 각 행을 보충 데이터 목록에 추가합니다."
        ):
            try:
                if uploaded.name.endswith(".json"):
                    import json

                    records = json.loads(uploaded.read().decode("utf-8"))
                else:
                    df = pd.read_csv(uploaded)
                    records = df.to_dict(orient="records")

                added = 0
                for rec in records:
                    q = str(rec.get("question", "")).strip()
                    a = str(rec.get("answer", "")).strip()
                    if q and a:
                        st.session_state.kb_data.append(
                            {
                                "id": str(uuid.uuid4()),
                                "category": str(rec.get("category", "기타")).strip() or "기타",
                                "question": q,
                                "answer": a,
                            }
                        )
                        added += 1
                save_data(st.session_state.kb_data)
                st.success(f"{added}건의 데이터를 추가했습니다.")
            except Exception as exc:  # noqa: BLE001
                st.error(f"파일 처리 중 오류: {exc}")

    with st.expander("📑 PDF 업로드로 보완"):
        st.caption(
            "조사한 자료가 PDF라면 손으로 옮겨 적지 않아도 됩니다. 문장 단위로 자동으로 나눠 "
            "보충 데이터에 등록하며, 문맥이 끊기지 않도록 조각 사이를 살짝 겹쳐서 나눕니다."
        )
        pdf_category = st.selectbox(
            "카테고리", CATEGORIES, key="pdf_category", help="이 PDF에서 추출된 모든 조각에 공통으로 적용될 분류입니다."
        )
        pdf_file = st.file_uploader("PDF 파일 선택", type=["pdf"], key="pdf_uploader")

        if pdf_file is not None and st.button(
            "PDF 내용 미리 나눠보기", help="아직 등록되지 않습니다. 몇 개 조각으로 나뉘는지 먼저 확인합니다."
        ):
            try:
                entries = pdf_to_kb_entries(pdf_file.read(), pdf_file.name, pdf_category)
                if entries:
                    st.session_state.pdf_pending_entries = entries
                    st.success(f"{len(entries)}개 조각으로 나뉘었습니다. 아래에서 확인 후 등록하세요.")
                else:
                    st.session_state.pdf_pending_entries = []
                    st.warning("PDF에서 텍스트를 추출하지 못했습니다. 스캔 이미지로만 된 PDF는 지원하지 않습니다.")
            except Exception as exc:  # noqa: BLE001
                st.error(f"PDF 처리 중 오류: {exc}")

        pending = st.session_state.get("pdf_pending_entries") or []
        if pending:
            st.markdown(f"**미리보기 — {len(pending)}개 조각**")
            for entry in pending[:5]:
                st.caption(f"[{entry['question']}] {entry['answer'][:80]}...")
            if len(pending) > 5:
                st.caption(f"...외 {len(pending) - 5}개 더")

            col_add, col_cancel = st.columns(2)
            with col_add:
                if st.button("✅ 이 내용 모두 등록", type="primary", key="pdf_confirm_add"):
                    st.session_state.kb_data.extend(pending)
                    save_data(st.session_state.kb_data)
                    st.session_state.pdf_pending_entries = []
                    st.success(f"{len(pending)}개 조각을 보충 데이터에 등록했습니다.")
                    st.rerun()
            with col_cancel:
                if st.button("취소", key="pdf_confirm_cancel"):
                    st.session_state.pdf_pending_entries = []
                    st.rerun()

    with st.expander(f"📋 등록된 데이터 목록 ({len(st.session_state.kb_data)}건)", expanded=True):
        for item in list(st.session_state.kb_data):
            st.markdown(f"**[{item['category']}] {item['question']}**")
            st.caption(item["answer"])
            if st.button("삭제", key=f"del_{item['id']}", help="이 보충 데이터 항목을 목록에서 영구히 삭제합니다."):
                st.session_state.kb_data = [
                    d for d in st.session_state.kb_data if d["id"] != item["id"]
                ]
                save_data(st.session_state.kb_data)
                st.rerun()
            st.divider()


# ----------------------------- 동의어 사전 -----------------------------

with tab_synonyms:
    st.caption(
        "06_동의어사전_변경이력.md 에서 파싱된 표입니다. 사용자 질문에 이 표의 동의어가 포함되어 "
        "있으면 검색 전에 대표 키워드를 덧붙여 검색 정확도를 높입니다. 이 표는 읽기 전용이며, "
        "수정하려면 RAG 폴더의 .md 파일을 편집한 뒤 'RAG 문서 현황' 탭에서 다시 불러오세요."
    )
    synonym_dict = st.session_state.synonym_dict
    if synonym_dict:
        syn_df = pd.DataFrame(
            [{"대표 키워드": k, "동의어": ", ".join(v)} for k, v in synonym_dict.items()]
        )
        st.dataframe(syn_df, height=420, width="stretch")
    else:
        st.info("동의어 사전을 찾을 수 없습니다.")


# ----------------------------- 사용 현황 & 최적화 -----------------------------

with tab_usage:
    st.caption(
        "연결된 LLM 성능에 기대지 않고도 정확히 답하려면, 실제로 자주 쓰이는 RAG 항목이 "
        "무엇인지 파악하고 그 정보를 원본 문서에 남겨두는 것이 중요합니다. 위젯에서 방문자가 "
        "질문할 때마다 참조된 항목의 횟수를 기록하고, 하루 한 번 그 결과를 RAG .md 파일 헤더 "
        "바로 아래에 자동으로 반영(자기 참조)하며 종합 리포트를 새로 만듭니다."
    )

    usage_data = load_usage()
    meta = usage_data["_meta"]
    col1, col2, col3 = st.columns(3)
    col1.metric("누적 질문 수", f"{meta.get('total_queries', 0)}건")
    col2.metric("마지막 최적화", meta.get("last_optimized") or "아직 실행 안 됨")
    open_unanswered = [u for u in load_unanswered() if u["status"] == "open"]
    col3.metric("미응답 질문(처리 대기)", f"{len(open_unanswered)}건")

    if st.button("🛠️ 지금 최적화 실행 (강제)", help="오늘 이미 실행되었어도 다시 실행합니다."):
        with st.spinner("RAG 문서에 사용량을 반영하고 리포트를 생성하는 중..."):
            result = run_daily_optimization(st.session_state.rag_chunks, force=True)
        st.session_state.rag_chunks = load_rag_chunks(RAG_DIR)
        st.success(
            f"완료: {result['updated_files']}개 파일에 사용량을 반영하고, "
            f"리포트({result['report_path']})를 갱신했습니다."
        )
        st.rerun()

    st.caption(
        "참고: 이 앱은 상시 실행되는 서버가 아니라서, 아무도 열지 않은 날은 위 버튼(또는 앱 접속 시 "
        "자동 1회 실행)이 실행되지 않습니다. 앱 실행 여부와 무관하게 매일 자동 실행되길 원한다면 "
        "`scripts/daily_optimize.py`를 Windows 작업 스케줄러 등에 등록하세요."
    )

    st.divider()
    used, unused = get_usage_stats(st.session_state.rag_chunks)

    st.markdown(f"**자주 참조된 항목 TOP 20** (총 {len(used)}건 참조 이력 있음)")
    if used:
        used_df = pd.DataFrame(
            [
                {"카테고리": c["category"], "질문": c["question"], "참조 횟수": c["count"], "마지막 참조": c["last_used"]}
                for c in used[:20]
            ]
        )
        st.dataframe(used_df, height=300, width="stretch")
    else:
        st.info("아직 참조 기록이 없습니다. 위젯에서 질문을 몇 개 해보세요.")

    with st.expander(f"한 번도 참조되지 않은 항목 ({len(unused)}건)"):
        if unused:
            unused_df = pd.DataFrame(
                [{"카테고리": c["category"], "질문": c["question"]} for c in unused]
            )
            st.dataframe(unused_df, height=300, width="stretch")
        else:
            st.caption("모든 항목이 최소 한 번 이상 참조되었습니다.")

    report_path = RAG_DIR / "99_사용현황_리포트.md"
    if report_path.exists():
        with st.expander("📄 자동 생성된 리포트 원문 보기 (99_사용현황_리포트.md)"):
            st.markdown(report_path.read_text(encoding="utf-8"))


# ----------------------------- 미응답 질문 -----------------------------

with tab_unanswered:
    st.caption(
        "RAG에서 답을 찾지 못해 '모른다'고 답했던 실제 질문 목록입니다. 인터넷 검색 등으로 "
        "직접 조사한 뒤 아래에서 답변을 등록하면, 다음 질문부터는 검색 결과에 포함됩니다."
    )

    unanswered = load_unanswered()
    open_items = [u for u in unanswered if u["status"] == "open"]
    open_items.sort(key=lambda u: u["count"], reverse=True)

    if not open_items:
        st.success("현재 처리 대기 중인 미응답 질문이 없습니다.")
    else:
        st.caption(f"{len(open_items)}건 대기 중 (질문 빈도순 정렬)")
        for item in open_items:
            with st.expander(f"({item['count']}회 · 최근 {item['last_asked']}) {item['question']}"):
                with st.form(f"resolve_form_{item['id']}"):
                    category = st.selectbox("카테고리", CATEGORIES, key=f"cat_{item['id']}")
                    answer = st.text_area(
                        "조사한 답변 내용",
                        key=f"ans_{item['id']}",
                        help="인터넷 검색 등으로 확인한 정확한 정보를 입력하세요.",
                    )
                    col_a, col_b = st.columns(2)
                    with col_a:
                        register = st.form_submit_button("✅ 답변 등록", type="primary")
                    with col_b:
                        dismiss = st.form_submit_button("🗑️ 무시(답변 없이 종료)")

                    if register:
                        if answer.strip():
                            st.session_state.kb_data.append(
                                {
                                    "id": str(uuid.uuid4()),
                                    "category": category,
                                    "question": item["question"],
                                    "answer": answer.strip(),
                                }
                            )
                            save_data(st.session_state.kb_data)
                            resolve_unanswered(item["id"], status="resolved")
                            st.success("답변을 등록하고 미응답 목록에서 제거했습니다.")
                            st.rerun()
                        else:
                            st.warning("답변 내용을 입력해주세요.")
                    if dismiss:
                        resolve_unanswered(item["id"], status="dismissed")
                        st.rerun()
