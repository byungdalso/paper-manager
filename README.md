# Paper Assignment Manager

학생별 읽을 논문 목록 관리 웹앱

## 기능
- 학생 추가 / 삭제 / 검색
- 논문 추가 / 수정 / 삭제
- 저널 목록 관리 (필터)
- 마감일 색상 표시 (🔴 지남 / 🟡 7일 이내 / 🟢 여유)
- TXT / JSON 내보내기 & TXT 가져오기

## ⚠️ Streamlit Cloud 데이터 저장 주의

Streamlit Cloud는 재배포 시 데이터가 초기화됩니다.
**정기적으로 JSON 백업을 다운로드**하고, 필요시 TXT로 복원하세요.

## 로컬 실행
```bash
pip install -r requirements.txt
streamlit run app.py
```

## Streamlit Cloud 배포
1. 이 repo를 GitHub에 push
2. share.streamlit.io 접속 → Create app
3. repo 선택 → app.py → Deploy
