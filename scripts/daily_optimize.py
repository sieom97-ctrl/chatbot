"""RAG 사용량 최적화를 매일 한 번 실행하기 위한 독립 실행 스크립트.

Streamlit 앱은 상시 실행되는 백그라운드 프로세스가 아니라, 누군가 접속했을 때만
동작한다. 앱이 켜져 있는 동안에는 main.py가 세션당 최대 1회 같은 로직을
opportunistic하게 실행하지만, 아무도 접속하지 않는 날에는 그 실행 기회 자체가
없다. 이 스크립트를 Windows 작업 스케줄러(또는 Linux cron)에 등록해 매일 한 번
실행하면, 앱 접속 여부와 무관하게 최적화가 누락되지 않는다.

사용 예 (Windows 작업 스케줄러의 "동작"에 등록):
    프로그램: python
    인수: C:\\Users\\user\\Desktop\\Chatbot\\scripts\\daily_optimize.py
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from utils.engine import RAG_DIR, load_rag_chunks, run_daily_optimization

if __name__ == "__main__":
    rag_chunks = load_rag_chunks(RAG_DIR)
    result = run_daily_optimization(rag_chunks)
    if result["ran"]:
        print(
            f"[daily_optimize] {result['date']} 최적화 완료 — "
            f"{result['updated_files']}개 파일 갱신, 리포트: {result['report_path']}"
        )
    else:
        print(f"[daily_optimize] 건너뜀 — {result['reason']}")
