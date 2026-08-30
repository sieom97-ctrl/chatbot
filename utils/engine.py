"""독립기념관 챗봇의 비UI 로직 (데이터 로딩, RAG 파싱, 검색, 답변 생성).

이 모듈은 Streamlit UI 코드를 포함하지 않는다(오류 표시용 예외는 호출부에서 처리).
app_pages/ 아래 각 페이지가 이 모듈의 함수를 가져다 쓴다.
"""

import json
import math
import re
import uuid
from datetime import date, datetime
from difflib import SequenceMatcher
from pathlib import Path

import numpy as np

ROOT_DIR = Path(__file__).resolve().parent.parent
DATA_PATH = ROOT_DIR / "data" / "knowledge_base.json"
WIDGET_SETTINGS_PATH = ROOT_DIR / "data" / "widget_settings.json"
API_SETTINGS_PATH = ROOT_DIR / "data" / "api_settings.json"
USAGE_PATH = ROOT_DIR / "data" / "rag_usage.json"
UNANSWERED_PATH = ROOT_DIR / "data" / "unanswered_questions.json"
QA_LOG_PATH = ROOT_DIR / "data" / "qa_log.jsonl"
# 독립기념관 공식 심볼(CI). 출처: https://i815.or.kr/2018/introduction/ci.do (색상 #06348B)
SYMBOL_PATH = ROOT_DIR / "assets" / "ci_symbol.png"
QA_LOG_MAX_LINES = 5000
RAG_DIR = ROOT_DIR / "RAG"
REPORT_PATH = RAG_DIR / "99_사용현황_리포트.md"

CATEGORIES = ["관람 안내", "전시관 소개", "행사/교육 프로그램", "역사 정보", "오시는 길", "기타"]

DEFAULT_DATA = [
    {
        "id": str(uuid.uuid4()),
        "category": "관람 안내",
        "question": "독립기념관 관람 시간과 휴관일은 언제인가요?",
        "answer": "독립기념관은 계절에 따라 관람 시간이 다르며, 매주 월요일은 정기 휴관일입니다. "
        "정확한 시간은 관리자가 최신 정보로 갱신해 주세요.",
    },
    {
        "id": str(uuid.uuid4()),
        "category": "오시는 길",
        "question": "독립기념관은 어디에 있나요?",
        "answer": "독립기념관은 충청남도 천안시 동남구 목천읍 흑성산 자락에 위치해 있습니다.",
    },
    {
        "id": str(uuid.uuid4()),
        "category": "전시관 소개",
        "question": "독립기념관에는 어떤 전시관이 있나요?",
        "answer": "겨레의 집을 중심으로 제1관(겨레의 뿌리)부터 제7관(새로운 나라)까지 주제별 상설 전시관이 있습니다.",
    },
]

DEFAULT_WIDGET_SETTINGS = {
    # 문구
    "panel_title": "독립이2",
    "greeting": "안녕하세요! 독립기념관 안내 챗봇입니다. 관람 시간, 전시관, 오시는 길 등이 궁금하시면 물어봐 주세요.",
    "fab_label": "독립기념관 챗봇",
    "chat_placeholder": "궁금한 점을 물어보세요",
    "fallback_message": (
        "현재 시스템 내 해당 내용이 없습니다. 다음 업데이트(약 5일 소요) 시 반영하겠습니다."
    ),
    # 위치 (화면 모서리 + 여백) — 실제 i815.or.kr 위젯(makebot.ai, 우측하단 30px 여백)과 동일
    "position": "bottom-right",  # bottom-right | bottom-left | top-right | top-left
    "margin_x": 30,
    "margin_y": 30,
    # 디자인 — 기본값 자체를 "독립기념관 공식 스타일"(340x700px, 모서리 10px, 네이비)에 맞춘다.
    # 다른 느낌을 원하면 위젯 설정에서 "기본형 (레드)" 등 다른 프리셋으로 바꿀 수 있다.
    "panel_width": 340,
    "panel_height": 700,
    "messages_height": 520,
    "border_radius": 10,
    "accent_color": "#1B3A6B",
    "panel_bg_color": "#FFFFFF",
    "panel_opacity": 1.0,  # 0.0(완전 투명)~1.0(불투명)
    "shadow_strength": 55,  # 0(그림자 없음)~100(진한 그림자)
    # 검색 동작
    "top_k": 3,
    "score_threshold": 0.12,
    "default_open": False,
}

# "디자인 프리셋" — 위치/모양 값 한 세트를 한 번에 적용하기 위한 미리 정의된 조합.
# "독립기념관 공식 스타일"은 실제 i815.or.kr에 임베드된 위젯(makebot.ai, 340x700px,
# border-radius 10px, 우측하단 30px 여백)의 배치·크기를 그대로 재현한 것이다.
# (특정 마스코트 이미지나 로고 등 브랜드 자산은 복제하지 않고, 배치·크기·색감만 근사한다.)
THEME_PRESETS = {
    "기본형 (레드)": {
        "position": "bottom-right",
        "margin_x": 24,
        "margin_y": 24,
        "panel_width": 380,
        "panel_height": 640,
        "border_radius": 16,
        "accent_color": "#C0392B",
        "panel_bg_color": "#FFFFFF",
        "panel_opacity": 1.0,
        "shadow_strength": 50,
    },
    "독립기념관 공식 스타일": {
        "position": "bottom-right",
        "margin_x": 30,
        "margin_y": 30,
        "panel_width": 340,
        "panel_height": 700,
        "border_radius": 10,
        "accent_color": "#1B3A6B",
        "panel_bg_color": "#FFFFFF",
        "panel_opacity": 1.0,
        "shadow_strength": 55,
    },
    "글래스 (반투명)": {
        "position": "bottom-right",
        "margin_x": 24,
        "margin_y": 24,
        "panel_width": 380,
        "panel_height": 640,
        "border_radius": 24,
        "accent_color": "#7048E8",
        "panel_bg_color": "#FFFFFF",
        "panel_opacity": 0.82,
        "shadow_strength": 40,
    },
    "미니멀 (좌측하단)": {
        "position": "bottom-left",
        "margin_x": 20,
        "margin_y": 20,
        "panel_width": 360,
        "panel_height": 600,
        "border_radius": 12,
        "accent_color": "#495057",
        "panel_bg_color": "#FFFFFF",
        "panel_opacity": 1.0,
        "shadow_strength": 30,
    },
}

DEFAULT_API_SETTINGS = {
    "provider": "openai",
    "model": "gpt-4o-mini",
    "temperature": 0.3,
    "use_llm": False,
}

# 제공자별 사용 가능 모델 목록. 새 모델이 출시되면 이 표만 갱신하면 된다.
PROVIDER_LABELS = {
    "openai": "OpenAI (ChatGPT)",
    "anthropic": "Anthropic (Claude)",
}
PROVIDER_MODELS = {
    "openai": ["gpt-5", "gpt-5-mini", "gpt-4.1", "gpt-4.1-mini", "gpt-4o", "gpt-4o-mini"],
    "anthropic": ["claude-opus-5", "claude-sonnet-5", "claude-haiku-4-5-20251001", "claude-fable-5"],
}

# ----------------------------- 설정 저장/불러오기 -----------------------------


def _load_json(path: Path, default: dict) -> dict:
    if path.exists():
        try:
            loaded = json.loads(path.read_text(encoding="utf-8"))
            merged = dict(default)
            merged.update(loaded)
            return merged
        except (json.JSONDecodeError, OSError):
            return dict(default)
    return dict(default)


def _save_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def load_widget_settings() -> dict:
    return _load_json(WIDGET_SETTINGS_PATH, DEFAULT_WIDGET_SETTINGS)


# ----------------------------- 위젯 위치/디자인 CSS 계산 -----------------------------


def hex_to_rgba(hex_color: str, opacity: float) -> str:
    """'#RRGGBB' 형태의 색상과 0.0~1.0 투명도를 CSS rgba(...) 문자열로 변환한다."""
    hex_color = hex_color.lstrip("#")
    if len(hex_color) != 6:
        hex_color = "FFFFFF"
    r, g, b = (int(hex_color[i : i + 2], 16) for i in (0, 2, 4))
    opacity = max(0.0, min(1.0, opacity))
    return f"rgba({r}, {g}, {b}, {opacity:.2f})"


def position_css(position: str, margin_x: int, margin_y: int) -> str:
    """위젯이 붙는 화면 모서리에 따라 top/bottom/left/right CSS 선언을 만든다."""
    vertical = "top" if position.startswith("top") else "bottom"
    horizontal = "left" if position.endswith("left") else "right"
    return f"{vertical}: {margin_y}px; {horizontal}: {margin_x}px;"


def shadow_css(strength: int) -> str:
    """0~100 하나의 슬라이더 값을 box-shadow의 흐림 정도·짙기로 환산한다."""
    strength = max(0, min(100, strength))
    if strength == 0:
        return "none"
    blur = 20 + strength * 0.6
    opacity = 0.12 + (strength / 100) * 0.35
    return f"0 6px {blur:.0f}px 0 rgba(81, 99, 120, {opacity:.2f})"


def save_widget_settings(settings: dict) -> None:
    _save_json(WIDGET_SETTINGS_PATH, settings)


def load_api_settings() -> dict:
    return _load_json(API_SETTINGS_PATH, DEFAULT_API_SETTINGS)


def save_api_settings(settings: dict) -> None:
    # 절대 API 키 자체는 이 파일에 저장하지 않는다 — 세션에서만 보관한다.
    safe = {k: v for k, v in settings.items() if k != "api_key"}
    _save_json(API_SETTINGS_PATH, safe)


# ----------------------------- 지식베이스(JSON) 데이터 저장/불러오기 -----------------------------


def load_data() -> list[dict]:
    if DATA_PATH.exists():
        try:
            return json.loads(DATA_PATH.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return [dict(item) for item in DEFAULT_DATA]
    return [dict(item) for item in DEFAULT_DATA]


def save_data(data: list[dict]) -> None:
    DATA_PATH.parent.mkdir(parents=True, exist_ok=True)
    DATA_PATH.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


# ----------------------------- RAG 마크다운 문서 로딩 -----------------------------

SYNONYM_TAG_RE = re.compile(r"^\*\(관련\s*검색어\s*[:：]\s*(.+?)\)\*$")
USAGE_TAG_RE = re.compile(r"^\*\(참조\s*횟수.*\)\*$")


def extract_heading(stripped_line: str) -> str | None:
    """'## 제목' 또는 '### 제목' 형태의 줄에서 제목만 뽑는다. 헤더가 아니면 None."""
    if stripped_line.startswith("### "):
        return stripped_line[4:].strip()
    if stripped_line.startswith("## "):
        return stripped_line[3:].strip()
    return None


def chunk_key(category: str, question: str) -> str:
    """사용량 카운트를 파일 내용 변경(줄바꿈 등)과 무관하게 추적하기 위한 식별자."""
    return f"{category}::{question}"


def parse_markdown_chunks(text: str, category: str) -> list[dict]:
    """`##`/`###` 헤더 단위로 마크다운을 청크 분리한다.

    각 헤더 아래 본문이 하나의 청크가 되며, `*(관련 검색어: ...)*` 줄은 검색용
    동의어로만 사용하고, `*(참조 횟수: ...)*` 줄(자동 갱신되는 사용량 표시)은
    둘 다 사용자에게 보여줄 답변 본문에서는 제외한다.
    """
    chunks: list[dict] = []
    h2 = h3 = None
    buffer: list[str] = []

    def flush() -> None:
        heading = h3 or h2
        if not heading:
            buffer.clear()
            return
        synonyms: list[str] = []
        content_lines: list[str] = []
        for line in buffer:
            stripped_line = line.strip()
            match = SYNONYM_TAG_RE.match(stripped_line)
            if match:
                synonyms.append(match.group(1))
            elif USAGE_TAG_RE.match(stripped_line):
                continue
            else:
                content_lines.append(line)
        answer = "\n".join(content_lines).strip()
        if answer:
            chunks.append(
                {
                    "category": category,
                    "question": heading,
                    "answer": answer,
                    "search_text": f"{heading} {' '.join(synonyms)} {answer}",
                }
            )
        buffer.clear()

    for raw_line in text.replace("\r\n", "\n").split("\n"):
        stripped = raw_line.strip()
        if stripped.startswith("### "):
            flush()
            h3 = stripped[4:].strip()
        elif stripped.startswith("## "):
            flush()
            h2 = stripped[3:].strip()
            h3 = None
        elif stripped.startswith("# ") or stripped.startswith(">") or stripped == "---":
            continue
        else:
            buffer.append(raw_line)
    flush()
    return chunks


def load_rag_chunks(rag_dir: Path = RAG_DIR) -> list[dict]:
    chunks: list[dict] = []
    if not rag_dir.exists():
        return chunks
    for path in sorted(rag_dir.glob("*.md")):
        # 00(인덱스), 06(동의어 사전), 99(자동 생성 사용현황 리포트)는
        # 검색 청크가 아니라 메타 문서이므로 제외한다.
        if path.stem.startswith(("00_", "06_", "99_")):
            continue
        category = re.sub(r"^\d+_", "", path.stem).replace("_", " ")
        chunks.extend(parse_markdown_chunks(path.read_text(encoding="utf-8"), category))
    return chunks


def load_synonym_dict(rag_dir: Path = RAG_DIR) -> dict[str, list[str]]:
    synonyms: dict[str, list[str]] = {}
    synonym_files = list(rag_dir.glob("06_*.md")) if rag_dir.exists() else []
    if not synonym_files:
        return synonyms

    in_table = False
    for line in synonym_files[0].read_text(encoding="utf-8").split("\n"):
        stripped = line.strip()
        if stripped.startswith("| 대표 키워드"):
            in_table = True
            continue
        if not in_table:
            continue
        if not stripped.startswith("|"):
            if stripped == "":
                continue
            break
        if stripped.startswith("|---"):
            continue
        parts = [p.strip() for p in stripped.strip("|").split("|")]
        if len(parts) >= 2 and parts[0]:
            terms = [t.strip() for t in parts[1].split(",") if t.strip()]
            if terms:
                synonyms[parts[0]] = terms
    return synonyms


# ----------------------------- PDF 문서 수집 (rag.py 방식 참고) -----------------------------
#
# 관리자가 조사한 자료가 PDF 형태일 때, 손으로 옮겨 적지 않고도 지식베이스로
# 바로 편입할 수 있도록 한다. 청킹 방식(문장 경계 + 길이 제한 + 겹침)은 일반적인
# RAG 구축 관례를 따른다 — 문장을 중간에 자르지 않고, 청크 사이에 약간의 겹침을
# 두어 문맥이 잘리는 것을 줄인다.


def extract_pdf_text(file_bytes: bytes) -> str:
    """PDF 바이트에서 페이지별 텍스트를 추출해 하나의 문자열로 합친다."""
    import pymupdf

    with pymupdf.open(stream=file_bytes, filetype="pdf") as doc:
        pages = [page.get_text("text") for page in doc]
    return "\n".join(p for p in pages if p.strip())


def clean_text(text: str) -> str:
    text = re.sub(r"\n{3,}", "\n\n", text)
    return re.sub(r"[ \t]+", " ", text).strip()


def chunk_text(text: str, size: int = 400, overlap: int = 80) -> list[str]:
    """문장 경계를 존중하면서 최대 `size`자 단위로 나누고, 각 청크 앞에 이전 청크의
    끝부분(`overlap`자)을 이어 붙여 문맥이 급격히 끊기지 않게 한다."""
    sentences = re.split(r"(?<=[.!?。！？\n])\s*", text)
    sentences = [s.strip() for s in sentences if s.strip()]
    chunks, current = [], ""
    for sent in sentences:
        if len(current) + len(sent) + 1 <= size:
            current = (current + " " + sent).strip() if current else sent
        else:
            if current:
                chunks.append(current)
            tail = current[-overlap:] if len(current) > overlap else current
            current = (tail + " " + sent).strip() if tail else sent
    if current:
        chunks.append(current)
    return chunks


def pdf_to_kb_entries(file_bytes: bytes, filename: str, category: str) -> list[dict]:
    """PDF 하나를 파싱·정제·청킹해 지식베이스(kb_data)에 바로 추가 가능한
    {id, category, question, answer} 레코드 목록으로 변환한다."""
    text = clean_text(extract_pdf_text(file_bytes))
    chunks = chunk_text(text)
    return [
        {
            "id": str(uuid.uuid4()),
            "category": category,
            "question": f"{filename} — 발췌 {i + 1}/{len(chunks)}",
            "answer": chunk,
        }
        for i, chunk in enumerate(chunks)
    ]


# ----------------------------- 검색 -----------------------------


def similarity(a: str, b: str) -> float:
    return SequenceMatcher(None, a, b).ratio()


def char_bigrams(text: str) -> set[str]:
    """한국어는 조사가 단어 뒤에 그대로 붙어(예: '안내견도') 공백 기준 토큰화로는
    어간이 잘 안 잡히므로, 공백을 제거한 문자 2-그램 집합으로 비교한다.
    이렇게 하면 '안내견도'와 '안내견'처럼 어미만 다른 표현도 상당 부분 겹친다."""
    compact = re.sub(r"\s+", "", text.lower())
    if len(compact) < 2:
        return {compact} if compact else set()
    return {compact[i : i + 2] for i in range(len(compact) - 1)}


def dice_similarity(a: str, b: str) -> float:
    set_a, set_b = char_bigrams(a), char_bigrams(b)
    if not set_a or not set_b:
        return 0.0
    return 2 * len(set_a & set_b) / (len(set_a) + len(set_b))


# 거의 모든 문장에 등장해 키워드 신호를 흐리는 한국어 기능어/조사 결합형.
# (예: "가지고"가 "킥보드"와 우연히 같은 빈도로 나타나 핵심 키워드처럼 취급되는 문제 방지)
KOREAN_STOPWORDS = {
    "되나요", "돼요", "됩니다", "되요", "있나요", "있어요", "있습니다",
    "하나요", "합니다", "해요", "해도", "가요", "가지고", "가진",
    "어떻게", "무엇", "무슨", "언제", "어디", "어디서", "어디에", "누구", "왜",
    "그럼", "그래서", "그런데", "인가요", "인지", "이에요", "예요", "나요",
    "좀", "혹시", "저기", "여기", "거기", "같아요", "같은데", "같습니다",
}


def tokenize(text: str) -> list[str]:
    return [
        t
        for t in re.findall(r"\w+", text.lower())
        if len(t) >= 2 and t not in KOREAN_STOPWORDS
    ]


def build_idf(data: list[dict]) -> dict[str, float]:
    """'되나요/어떻게/있나요'처럼 거의 모든 FAQ 문장에 등장하는 흔한 어미·표현은
    가중치를 낮추고, '드론'처럼 소수 항목에만 등장하는 단어는 가중치를 높인다."""
    doc_freq: dict[str, int] = {}
    for item in data:
        text = item.get("search_text") or f"{item['question']} {item.get('answer', '')}"
        for token in set(tokenize(text)):
            doc_freq[token] = doc_freq.get(token, 0) + 1
    total_docs = len(data) or 1
    return {token: math.log((total_docs + 1) / (df + 1)) + 1 for token, df in doc_freq.items()}


def expand_query(query: str, synonym_dict: dict[str, list[str]]) -> str:
    """질문에 등록된 동의어가 포함되어 있으면 대표 키워드를 덧붙여 검색을 보강한다.

    완전 일치 부분문자열뿐 아니라, 한 글자 오타(예: '전동킷보드' vs '전동킥보드')도
    바이그램 유사도로 잡아내 대표 키워드를 붙여준다."""
    query_tokens = tokenize(query)
    extra_terms = []
    for canonical, terms in synonym_dict.items():
        all_terms = [canonical, *terms]
        matched = any(term in query for term in all_terms)
        if not matched:
            matched = any(
                len(term) >= 2 and len(token) >= 2 and dice_similarity(term, token) >= 0.5
                for term in all_terms
                for token in query_tokens
            )
        if matched:
            extra_terms.append(canonical)
    return f"{query} {' '.join(extra_terms)}" if extra_terms else query


def score_all(
    query: str,
    data: list[dict],
    synonym_dict: dict[str, list[str]] | None = None,
) -> list[tuple[float, dict]]:
    """모든 후보를 점수와 함께 반환한다(임계값/개수 제한 없음). 관리자 디버그 화면용."""
    original = query.strip()
    if not original or not data:
        return []

    expanded = expand_query(original, synonym_dict or {})
    query_tokens = set(tokenize(expanded))
    idf = build_idf(data)
    query_weight = sum(idf.get(t, 1.0) for t in query_tokens) or 1.0

    scored = []
    for item in data:
        question = item["question"]
        answer = item.get("answer", "")
        search_text = item.get("search_text") or f"{question} {answer}"

        # 질문 헤더와의 바이그램 유사도가 가장 강한 신호, 답변 본문(동의어 포함)과의
        # 유사도가 보조 신호, IDF 가중 토큰 일치율로 "드론"처럼 드물고 구체적인
        # 단어의 일치를 "되나요"처럼 흔한 어미보다 훨씬 높게 평가한다.
        question_score = dice_similarity(expanded, question)
        body_score = dice_similarity(expanded, search_text)
        item_tokens = set(tokenize(search_text))
        matched_weight = sum(idf.get(t, 1.0) for t in query_tokens & item_tokens)
        token_overlap = matched_weight / query_weight

        score = question_score * 0.35 + body_score * 0.25 + token_overlap * 0.4
        if original and (original in question or original in answer):
            score += 0.2
        scored.append((score, item))

    scored.sort(key=lambda pair: pair[0], reverse=True)
    return scored


def search_knowledge_base(
    query: str,
    data: list[dict],
    synonym_dict: dict[str, list[str]] | None = None,
    top_k: int = 3,
    score_threshold: float = 0.12,
) -> list[dict]:
    scored = score_all(query, data, synonym_dict)
    return [item for score, item in scored[:top_k] if score > score_threshold]


# ----------------------------- 답변 생성 -----------------------------


ANSWER_SYSTEM_PROMPT = (
    "너는 독립기념관 안내 챗봇이다. 아래 참고 자료만 근거로 삼아 "
    "친절하고 간결한 한국어로 답변하라. 참고 자료에 없는 내용은 "
    "추측하지 말고 모른다고 답하라."
)


def _call_openai(api_key: str, model: str, temperature: float, system: str, user_content: str) -> str:
    from openai import OpenAI

    client = OpenAI(api_key=api_key)
    completion = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": user_content},
        ],
        temperature=temperature,
    )
    return completion.choices[0].message.content.strip()


def _call_anthropic(api_key: str, model: str, temperature: float, system: str, user_content: str) -> str:
    import anthropic

    # Claude 5 세대 Messages API는 temperature 파라미터를 더 이상 받지 않는다
    # (설치된 anthropic SDK의 messages.create 시그니처에 해당 인자가 없음 — 넘기면
    # "unexpected keyword argument 'temperature'" 오류가 난다). 온도 슬라이더는
    # OpenAI 제공자에서만 의미가 있으므로 여기서는 그냥 무시한다.
    del temperature
    client = anthropic.Anthropic(api_key=api_key)
    response = client.messages.create(
        model=model,
        max_tokens=1024,
        system=system,
        messages=[{"role": "user", "content": user_content}],
    )
    return "".join(block.text for block in response.content if block.type == "text").strip()


def generate_answer(
    query: str,
    matches: list[dict],
    api_key: str | None,
    api_settings: dict | None = None,
    fallback_message: str | None = None,
) -> str:
    if not matches:
        return fallback_message or DEFAULT_WIDGET_SETTINGS["fallback_message"]

    settings = api_settings or DEFAULT_API_SETTINGS
    if api_key and settings.get("use_llm", False):
        provider = settings.get("provider", "openai")
        model = settings.get("model") or PROVIDER_MODELS[provider][0]
        temperature = settings.get("temperature", 0.3)
        context = "\n\n".join(
            f"[{m['category']}] Q: {m['question']}\nA: {m['answer']}" for m in matches
        )
        user_content = f"참고 자료:\n{context}\n\n질문: {query}"
        try:
            if provider == "anthropic":
                return _call_anthropic(api_key, model, temperature, ANSWER_SYSTEM_PROMPT, user_content)
            return _call_openai(api_key, model, temperature, ANSWER_SYSTEM_PROMPT, user_content)
        except Exception as exc:  # noqa: BLE001
            return f"⚠️ API 호출 중 오류가 발생하여 검색 결과로 답변합니다: {exc}\n\n{matches[0]['answer']}"

    return matches[0]["answer"]


def test_api_connection(api_key: str, model: str, provider: str = "openai") -> tuple[bool, str]:
    """입력된 API 키/모델로 최소한의 호출을 시도해 연결 가능 여부를 확인한다."""
    if not api_key:
        return False, "API 키를 입력해주세요."
    try:
        if provider == "anthropic":
            import anthropic

            client = anthropic.Anthropic(api_key=api_key)
            client.messages.create(
                model=model,
                max_tokens=1,
                messages=[{"role": "user", "content": "ping"}],
            )
        else:
            from openai import OpenAI

            client = OpenAI(api_key=api_key)
            client.chat.completions.create(
                model=model,
                messages=[{"role": "user", "content": "ping"}],
                max_tokens=1,
            )
        provider_label = PROVIDER_LABELS.get(provider, provider)
        return True, f"연결 성공 — {provider_label} 모델 '{model}'을(를) 정상적으로 호출했습니다."
    except Exception as exc:  # noqa: BLE001
        return False, f"연결 실패: {exc}"


# ----------------------------- RAG 사용량 추적 / 자기 참조 최적화 -----------------------------
#
# 연결된 LLM 성능이 낮을 수 있다는 전제 하에, 가능한 한 RAG 검색 결과 자체의
# 품질에 의존하도록 설계한다. 이를 위해 (1) 어떤 RAG 청크가 실제로 자주
# 쓰이는지 매 질의응답마다 기록하고, (2) 그 사용량을 원본 .md 파일의 헤더
# 바로 아래에 자동으로 표시(자기 참조)하며, (3) 하루 단위로 이 정보를
# 종합한 리포트 .md 파일을 새로 생성/갱신하고, (4) RAG에 없어 답하지 못한
# 질문은 관리자가 검토할 수 있도록 별도로 쌓아둔다.


def load_usage() -> dict:
    return _load_json(USAGE_PATH, {"chunks": {}, "_meta": {"total_queries": 0, "last_optimized": None}})


def save_usage(usage: dict) -> None:
    _save_json(USAGE_PATH, usage)


def record_usage(matches: list[dict]) -> None:
    """검색되어 답변에 실제로 사용된 청크들의 참조 횟수를 1씩 올린다."""
    if not matches:
        return
    usage = load_usage()
    today = date.today().isoformat()
    for item in matches:
        key = chunk_key(item["category"], item["question"])
        record = usage["chunks"].setdefault(key, {"count": 0, "last_used": None})
        record["count"] += 1
        record["last_used"] = today
    save_usage(usage)


def load_unanswered() -> list[dict]:
    if UNANSWERED_PATH.exists():
        try:
            return json.loads(UNANSWERED_PATH.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return []
    return []


def save_unanswered(items: list[dict]) -> None:
    UNANSWERED_PATH.parent.mkdir(parents=True, exist_ok=True)
    UNANSWERED_PATH.write_text(json.dumps(items, ensure_ascii=False, indent=2), encoding="utf-8")


UNANSWERED_DEDUP_THRESHOLD = 0.6


def record_unanswered(query: str) -> None:
    """RAG에서 답을 찾지 못한 질문을 관리자 검토용으로 쌓아둔다.

    조사 하나 차이("시어비는 어디있어?" vs "시어비 어디있어?")처럼 표현만 살짝 다른
    반복 질문이 별개 항목으로 계속 쌓여 검토 목록이 지저분해지는 것을 막기 위해,
    완전 일치가 아니라 문자 바이그램 유사도가 높은 기존 항목을 찾아 횟수만 올린다.
    """
    normalized = query.strip()
    if not normalized:
        return
    items = load_unanswered()
    today = date.today().isoformat()

    best_item, best_score = None, 0.0
    for item in items:
        if item["status"] != "open":
            continue
        score = dice_similarity(item["question"].strip(), normalized)
        if score > best_score:
            best_item, best_score = item, score

    if best_item is not None and best_score >= UNANSWERED_DEDUP_THRESHOLD:
        best_item["count"] += 1
        best_item["last_asked"] = today
        save_unanswered(items)
        return

    items.append(
        {
            "id": str(uuid.uuid4()),
            "question": normalized,
            "count": 1,
            "first_asked": today,
            "last_asked": today,
            "status": "open",
        }
    )
    save_unanswered(items)


def resolve_unanswered(item_id: str, status: str = "resolved") -> None:
    items = load_unanswered()
    for item in items:
        if item["id"] == item_id:
            item["status"] = status
    save_unanswered(items)


def append_qa_log(query: str, matched: bool, matches: list[dict]) -> None:
    """매 질의응답을 한 줄씩 남긴다. 일일 최적화 시 이 로그를 근거로 리포트를 만든다."""
    QA_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    entry = {
        "timestamp": datetime.now().isoformat(timespec="seconds"),
        "query": query,
        "matched": matched,
        "matched_questions": [m["question"] for m in matches],
    }
    with QA_LOG_PATH.open("a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")


def read_qa_log() -> list[dict]:
    if not QA_LOG_PATH.exists():
        return []
    entries = []
    for line in QA_LOG_PATH.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            entries.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return entries


def trim_qa_log(max_lines: int = QA_LOG_MAX_LINES) -> int:
    """로그가 무한정 커지지 않도록 오래된 줄을 정리한다. 정리된 줄 수를 반환한다."""
    entries = read_qa_log()
    if len(entries) <= max_lines:
        return 0
    trimmed = entries[-max_lines:]
    dropped = len(entries) - len(trimmed)
    QA_LOG_PATH.write_text(
        "\n".join(json.dumps(e, ensure_ascii=False) for e in trimmed) + "\n", encoding="utf-8"
    )
    return dropped


def record_interaction(query: str, matches: list[dict]) -> None:
    """위젯/챗봇 테스트가 응답 하나를 만들 때마다 호출하는 단일 진입점.

    사용량 카운트, 미응답 질문 적재, 질의응답 로그 기록을 한 번에 처리한다.
    """
    usage = load_usage()
    usage["_meta"]["total_queries"] = usage["_meta"].get("total_queries", 0) + 1
    save_usage(usage)

    record_usage(matches)
    append_qa_log(query, matched=bool(matches), matches=matches)
    if not matches:
        record_unanswered(query)


def get_usage_stats(rag_chunks: list[dict]) -> tuple[list[dict], list[dict]]:
    """(자주 참조된 순서로 정렬된 목록, 한 번도 참조되지 않은 목록)을 반환한다."""
    usage = load_usage()["chunks"]
    used, unused = [], []
    for chunk in rag_chunks:
        key = chunk_key(chunk["category"], chunk["question"])
        record = usage.get(key)
        if record and record.get("count", 0) > 0:
            used.append({**chunk, "count": record["count"], "last_used": record.get("last_used")})
        else:
            unused.append(chunk)
    used.sort(key=lambda c: c["count"], reverse=True)
    return used, unused


# ----------------------------- RAG 분석/시각화 -----------------------------


def bow_pca_2d(chunks: list[dict], max_vocab: int = 300) -> np.ndarray:
    """청크들을 단어 등장 여부(bag-of-words) 벡터로 만들고, 2차원으로 투영한다.

    실제 문장 임베딩 모델(sentence-transformers 등) 없이도 "의미가 비슷한 청크끼리
    가까이 모이는" 대략적인 분포를 보여주기 위한 경량 대체 방식이다. 특징으로는
    이미 검색에 쓰이는 `tokenize()` 결과를 그대로 재사용하고, numpy의 SVD로 직접
    주성분(PCA)을 계산해 별도 머신러닝 라이브러리 없이 동작한다.
    """
    n = len(chunks)
    if n < 2:
        return np.zeros((n, 2), dtype="float32")

    texts = [c.get("search_text") or f"{c['question']} {c.get('answer', '')}" for c in chunks]
    token_lists = [tokenize(t) for t in texts]

    doc_freq: dict[str, int] = {}
    for tokens in token_lists:
        for t in set(tokens):
            doc_freq[t] = doc_freq.get(t, 0) + 1
    vocab = [w for w, _ in sorted(doc_freq.items(), key=lambda kv: kv[1], reverse=True)[:max_vocab]]
    if not vocab:
        return np.zeros((n, 2), dtype="float32")
    index = {w: i for i, w in enumerate(vocab)}

    matrix = np.zeros((n, len(vocab)), dtype="float32")
    for row, tokens in enumerate(token_lists):
        for t in tokens:
            col = index.get(t)
            if col is not None:
                matrix[row, col] += 1

    centered = matrix - matrix.mean(axis=0, keepdims=True)
    try:
        u, s, _vt = np.linalg.svd(centered, full_matrices=False)
    except np.linalg.LinAlgError:
        return np.zeros((n, 2), dtype="float32")

    comps = min(2, s.shape[0])
    coords = np.zeros((n, 2), dtype="float32")
    coords[:, :comps] = u[:, :comps] * s[:comps]
    return coords


def update_md_usage_annotations(rag_dir: Path = RAG_DIR) -> int:
    """각 RAG .md 파일의 헤더 바로 아래에 `*(참조 횟수: N회 · ...)*` 줄을 자동으로
    삽입/갱신한다. 이미 붙어 있는 줄은 값만 새로 고치고, 참조 기록이 없어진
    항목은 줄을 지운다(파일 원본을 최소한으로만 건드리는 멱등적 동작).
    """
    usage_data = load_usage()
    usage = usage_data["chunks"]
    total_queries = max(usage_data["_meta"].get("total_queries", 0), 1)
    updated_files = 0

    for path in sorted(rag_dir.glob("*.md")):
        if path.stem.startswith(("00_", "06_", "99_")):
            continue
        category = re.sub(r"^\d+_", "", path.stem).replace("_", " ")
        lines = path.read_text(encoding="utf-8").replace("\r\n", "\n").split("\n")
        out: list[str] = []
        changed = False
        i, n = 0, len(lines)
        while i < n:
            line = lines[i]
            out.append(line)
            heading = extract_heading(line.strip())
            if heading:
                key = chunk_key(category, heading)
                record = usage.get(key)
                has_existing_tag = (i + 1 < n) and bool(USAGE_TAG_RE.match(lines[i + 1].strip()))
                if record and record.get("count", 0) > 0:
                    pct = record["count"] / total_queries * 100
                    tag_line = (
                        f"*(참조 횟수: {record['count']}회 · 참조율: {pct:.1f}% "
                        f"· 마지막 참조: {record.get('last_used', '-')})*"
                    )
                    if has_existing_tag:
                        if lines[i + 1].strip() != tag_line:
                            changed = True
                        out.append(tag_line)
                        i += 1
                    else:
                        out.append(tag_line)
                        changed = True
                elif has_existing_tag:
                    changed = True
                    i += 1
            i += 1
        if changed:
            path.write_text("\n".join(out), encoding="utf-8")
            updated_files += 1

    return updated_files


def generate_daily_report(rag_chunks: list[dict]) -> Path:
    """오늘까지의 사용량/미응답 질문을 종합한 리포트 .md 파일을 새로 만든다.

    이 파일 자체는 검색 청크로 로드되지 않는다(파일명이 99_로 시작).
    """
    usage_data = load_usage()
    total_queries = usage_data["_meta"].get("total_queries", 0)
    used, unused = get_usage_stats(rag_chunks)

    log_entries = read_qa_log()
    today = date.today().isoformat()
    today_entries = [e for e in log_entries if e["timestamp"].startswith(today)]
    today_matched = sum(1 for e in today_entries if e["matched"])
    today_unmatched = len(today_entries) - today_matched

    unanswered = [u for u in load_unanswered() if u["status"] == "open"]
    unanswered.sort(key=lambda u: u["count"], reverse=True)

    lines = [
        "# RAG 사용 현황 리포트 (자동 생성)",
        "",
        f"> 이 파일은 `run_daily_optimization()`이 자동으로 생성/갱신합니다. 직접 수정하지 마세요. "
        f"마지막 생성: {datetime.now().isoformat(timespec='seconds')}",
        "",
        "## 오늘의 질의응답",
        "",
        f"- 오늘 전체 질문 수: {len(today_entries)}건",
        f"- 그 중 RAG 매칭 성공: {today_matched}건 / 매칭 실패(미응답): {today_unmatched}건",
        f"- 누적 전체 질문 수: {total_queries}건",
        "",
        "## 자주 참조된 항목 TOP 10",
        "",
    ]
    if used:
        for chunk in used[:10]:
            lines.append(f"- **[{chunk['category']}] {chunk['question']}** — {chunk['count']}회")
    else:
        lines.append("- 아직 참조된 항목이 없습니다.")

    lines += ["", "## 한 번도 참조되지 않은 항목", ""]
    if unused:
        for chunk in unused[:20]:
            lines.append(f"- [{chunk['category']}] {chunk['question']}")
        if len(unused) > 20:
            lines.append(f"- ...외 {len(unused) - 20}건 더 (RAG 관리 > 사용 현황 탭에서 전체 확인)")
    else:
        lines.append("- 모든 항목이 최소 한 번 이상 참조되었습니다.")

    lines += ["", "## 처리 대기 중인 미응답 질문", ""]
    if unanswered:
        for u in unanswered[:10]:
            lines.append(f"- ({u['count']}회) {u['question']}")
        if len(unanswered) > 10:
            lines.append(f"- ...외 {len(unanswered) - 10}건 더")
        lines.append("")
        lines.append("→ RAG 관리 > 미응답 질문 탭에서 답변을 등록하면 다음 검색부터 즉시 반영됩니다.")
    else:
        lines.append("- 없음")

    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return REPORT_PATH


def run_daily_optimization(rag_chunks: list[dict], force: bool = False) -> dict:
    """하루 1회, RAG .md 파일에 사용량을 반영하고 현황 리포트를 새로 생성한다.

    Streamlit 앱 자체는 상시 백그라운드 프로세스가 아니므로, 앱이 계속 켜져
    있지 않아도 매일 최적화가 이뤄지길 원한다면 `scripts/daily_optimize.py`를
    OS 스케줄러(Windows 작업 스케줄러, cron 등)에 등록해 실행하는 것을 권장한다.
    """
    usage_data = load_usage()
    today = date.today().isoformat()
    if not force and usage_data["_meta"].get("last_optimized") == today:
        return {"ran": False, "reason": "이미 오늘 실행되었습니다.", "date": today}

    updated_files = update_md_usage_annotations()
    report_path = generate_daily_report(rag_chunks)
    dropped_log_lines = trim_qa_log()

    usage_data = load_usage()
    usage_data["_meta"]["last_optimized"] = today
    save_usage(usage_data)

    return {
        "ran": True,
        "date": today,
        "updated_files": updated_files,
        "report_path": str(report_path),
        "dropped_log_lines": dropped_log_lines,
    }


def maybe_run_daily_optimization(rag_chunks: list[dict]) -> dict | None:
    """오늘 아직 실행되지 않았다면 최적화를 한 번 실행한다. 세션마다 최대 1회 호출되도록
    호출부(main.py)에서 session_state로 감싸는 것을 전제로 한다."""
    usage_data = load_usage()
    if usage_data["_meta"].get("last_optimized") == date.today().isoformat():
        return None
    return run_daily_optimization(rag_chunks)
