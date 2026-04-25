"""
Paper Assignment Manager — Streamlit Web App
학생별 읽을 논문 목록 관리 (Google Sheets backend + 2-tier auth)
"""

import json, re, io
from datetime import datetime, date

import streamlit as st

from auth import gate, logout_button
from db import load_data, save_data, load_journals, save_journals


# ══════════════════════════════════════════════════════════════════════════════
#  TXT Export / Import (순수 로직, 파일 I/O 아님)
# ══════════════════════════════════════════════════════════════════════════════
def export_txt_str(data: dict) -> str:
    buf = io.StringIO()
    buf.write("=" * 64 + "\n")
    buf.write("  Paper Reading Assignment\n")
    buf.write(f"  Generated : {datetime.now().strftime('%Y-%m-%d %H:%M')}\n")
    buf.write("=" * 64 + "\n\n")
    for student, papers in data.items():
        buf.write(f"▶  {student}\n")
        buf.write("-" * 44 + "\n")
        if papers:
            for i, p in enumerate(papers, 1):
                yr = f" ({p['year']})" if p.get("year") else ""
                buf.write(f"  [{i}] {p.get('title','')}{yr}\n")
                for key, label in [
                    ("author",       "Author      "),
                    ("journal",      "Journal     "),
                    ("added",        "Added       "),
                    ("assigned_to",  "Assigned    "),
                    ("reviewer",     "Reviewer    "),
                    ("assigned_date","Assign Date "),
                    ("due_date",     "Due Date    "),
                ]:
                    if p.get(key):
                        buf.write(f"       {label}: {p[key]}\n")
        else:
            buf.write("  (논문 없음)\n")
        buf.write("\n")
    return buf.getvalue()


def parse_txt(content: str) -> dict:
    data = {}
    current_student = None
    current_paper   = None

    def save_paper():
        nonlocal current_paper
        if current_paper and current_student is not None:
            data[current_student].append(current_paper)
        current_paper = None

    for raw_line in content.splitlines():
        line = raw_line.rstrip()
        m = re.match(r'^[▶>]\s+(.+)', line)
        if m:
            save_paper()
            current_student = m.group(1).strip()
            if current_student not in data:
                data[current_student] = []
            continue

        m = re.match(r'^\s+\[(\d+)\]\s+(.+)', line)
        if m:
            save_paper()
            raw_title = m.group(2).strip()
            yr_m  = re.search(r'\((\d{4})\)\s*$', raw_title)
            year  = int(yr_m.group(1)) if yr_m else ""
            title = re.sub(r'\s*\(\d{4}\)\s*$', '', raw_title).strip()
            current_paper = {"title": title, "author": "", "journal": "",
                             "year": year, "added": "", "assigned_to": "",
                             "reviewer": "", "assigned_date": "", "due_date": ""}
            continue

        if current_paper:
            for key, aliases in [
                ("author",       ["Author"]),
                ("journal",      ["Journal"]),
                ("added",        ["Added"]),
                ("assigned_to",  ["Assigned"]),
                ("reviewer",     ["Reviewer"]),
                ("assigned_date",["Assign Date"]),
                ("due_date",     ["Due Date", "Due"]),
            ]:
                pat = r'^\s+(?:' + '|'.join(aliases) + r')\s*:\s*(.+)'
                m2 = re.match(pat, line, re.IGNORECASE)
                if m2:
                    current_paper[key] = m2.group(1).strip()
                    break

    save_paper()
    return data


# ══════════════════════════════════════════════════════════════════════════════
#  세션 상태 & 저장 헬퍼
# ══════════════════════════════════════════════════════════════════════════════
def init_state():
    # DB-backed: reload every rerun so students see admin's updates.
    # ttl=1 cache in db.py amortizes multiple calls within one rerun.
    st.session_state.data     = load_data()
    st.session_state.journals = load_journals()

    st.session_state.setdefault("filter_student", "")
    st.session_state.setdefault("filter_journal", "")
    st.session_state.setdefault("search_kw",      "")


def save_state():
    save_data(st.session_state.data)
    save_journals(st.session_state.journals)
    # Invalidate read caches so the next rerun sees our write.
    load_data.clear()
    load_journals.clear()


# ══════════════════════════════════════════════════════════════════════════════
#  논문 필터링
# ══════════════════════════════════════════════════════════════════════════════
def get_filtered_papers():
    fs = st.session_state.filter_student
    fj = st.session_state.filter_journal
    kw = st.session_state.search_kw.lower()

    if fs:
        rows = [(fs, p) for p in st.session_state.data.get(fs, [])]
    else:
        seen = set(); rows = []
        for student, papers in st.session_state.data.items():
            for p in papers:
                key = (p.get("title",""), p.get("journal",""), p.get("added",""))
                if key not in seen:
                    seen.add(key); rows.append((student, p))

    if fj:
        rows = [(s,p) for s,p in rows if p.get("journal","") == fj]
    if kw:
        rows = [(s,p) for s,p in rows if kw in p.get("title","").lower()]
    return rows


# ══════════════════════════════════════════════════════════════════════════════
#  Streamlit 앱
# ══════════════════════════════════════════════════════════════════════════════
st.set_page_config(page_title="Paper Manager", layout="wide", page_icon="📚")

# 로그인 게이트: 미인증 시 st.stop() 으로 아래 전체 차단
role = gate()
is_admin = (role == "admin")

with st.sidebar:
    logout_button()

init_state()

st.title("📚 Paper Assignment Manager")
st.caption("학생별 읽을 논문 목록 관리")

# ── 레이아웃 ──────────────────────────────────────────────────────────────────
col_L, col_R = st.columns([1, 2.8], gap="large")

# ════════════════════════════════════════════════════════════════════════════
#  왼쪽: 학생 & 저널 관리
# ════════════════════════════════════════════════════════════════════════════
with col_L:

    # ── 학생 목록 ─────────────────────────────────────────────────────────────
    st.subheader("👤 학생 목록")

    stu_search = st.text_input("학생 검색", placeholder="이름 입력…",
                               label_visibility="collapsed")

    students = list(st.session_state.data.keys())
    filtered_students = [s for s in students
                         if stu_search.lower() in s.lower()] if stu_search else students

    # 학생 버튼 (클릭 → 필터)
    current_filter = st.session_state.filter_student
    for name in filtered_students:
        n_papers = len(st.session_state.data.get(name, []))
        label = f"{'▶ ' if name==current_filter else '   '}{name}  ({n_papers}편)"
        if st.button(label, key=f"stu_{name}", use_container_width=True):
            if st.session_state.filter_student == name:
                st.session_state.filter_student = ""   # 토글
            else:
                st.session_state.filter_student = name
                st.session_state.filter_journal = ""
            st.rerun()

    # 전체 보기
    if st.button("📋 전체 논문 보기", use_container_width=True):
        st.session_state.filter_student = ""
        st.session_state.filter_journal = ""
        st.rerun()

    # ── 관리자 전용: 학생 추가/삭제 ────────────────────────────────────────────
    if is_admin:
        with st.expander("+ 학생 추가"):
            new_stu = st.text_input("이름", key="new_stu_inp")
            if st.button("추가", key="add_stu"):
                if new_stu.strip():
                    if new_stu.strip() in st.session_state.data:
                        st.warning("이미 있는 이름입니다.")
                    else:
                        st.session_state.data[new_stu.strip()] = []
                        save_state()
                        st.success(f"'{new_stu.strip()}' 추가됨.")
                        st.rerun()

        if students:
            with st.expander("🗑 학생 삭제"):
                del_stu = st.selectbox("삭제할 학생", students, key="del_stu_sel")
                if st.button("삭제 확인", key="del_stu_btn", type="primary"):
                    del st.session_state.data[del_stu]
                    if st.session_state.filter_student == del_stu:
                        st.session_state.filter_student = ""
                    save_state()
                    st.rerun()

    st.divider()

    # ── 저널 관리 ─────────────────────────────────────────────────────────────
    st.subheader("📰 저널 목록")

    journals = sorted(st.session_state.journals)
    for j in journals:
        col1, col2 = st.columns([4, 1])
        active = (st.session_state.filter_journal == j)
        col1.markdown(f"{'**▶** ' if active else ''}{j}")
        if col2.button("필터", key=f"jfil_{j}"):
            if st.session_state.filter_journal == j:
                st.session_state.filter_journal = ""
            else:
                st.session_state.filter_journal = j
                st.session_state.filter_student = ""
            st.rerun()

    # ── 관리자 전용: 저널 추가 ────────────────────────────────────────────────
    if is_admin:
        with st.expander("+ 저널 추가"):
            new_j = st.text_input("저널명", key="new_j_inp")
            if st.button("추가", key="add_j"):
                if new_j.strip() and new_j.strip() not in st.session_state.journals:
                    st.session_state.journals.append(new_j.strip())
                    save_state()
                    st.rerun()

    st.divider()

    # ── Import / Export ───────────────────────────────────────────────────────
    st.subheader("💾 데이터")

    # TXT Export  (뷰어도 본인 읽을 목록 다운로드 가능)
    txt_data = export_txt_str(st.session_state.data)
    st.download_button(
        "📄 TXT로 내보내기",
        data=txt_data,
        file_name=f"paper_assignments_{datetime.now().strftime('%Y%m%d')}.txt",
        mime="text/plain",
        use_container_width=True,
    )

    # JSON Export (뷰어도 가능)
    json_data = json.dumps(st.session_state.data,
                           ensure_ascii=False, indent=2)
    st.download_button(
        "📦 JSON 백업",
        data=json_data,
        file_name=f"paper_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json",
        mime="application/json",
        use_container_width=True,
    )

    # ── 관리자 전용: TXT 가져오기 ─────────────────────────────────────────────
    if is_admin:
        uploaded = st.file_uploader("📥 TXT 가져오기",
                                    type=["txt"], key="txt_upload")
        if uploaded:
            try:
                content = uploaded.read().decode("utf-8", errors="replace")
                imported = parse_txt(content)
                if imported:
                    n_s = len(imported)
                    n_p = sum(len(v) for v in imported.values())
                    st.info(f"발견: 학생 {n_s}명, 논문 {n_p}편")
                    mode = st.radio("가져오기 방식",
                                    ["현재 데이터에 추가", "전체 교체"],
                                    key="import_mode")
                    if st.button("가져오기 실행", key="do_import"):
                        if mode == "전체 교체":
                            st.session_state.data = {}
                        added_s = added_p = 0
                        for stu, papers in imported.items():
                            if stu not in st.session_state.data:
                                st.session_state.data[stu] = []
                                added_s += 1
                            for p in papers:
                                dup = any(ep.get("title") == p.get("title")
                                          for ep in st.session_state.data[stu])
                                if not dup:
                                    st.session_state.data[stu].append(p)
                                    added_p += 1
                            for p in papers:
                                jn = p.get("journal","").strip()
                                if jn and jn not in st.session_state.journals:
                                    st.session_state.journals.append(jn)
                        save_state()
                        st.success(f"학생 {added_s}명, 논문 {added_p}편 추가됨")
                        st.rerun()
            except Exception as e:
                st.error(f"파싱 오류: {e}")


# ════════════════════════════════════════════════════════════════════════════
#  오른쪽: 논문 목록 & 추가 / 편집
# ════════════════════════════════════════════════════════════════════════════
with col_R:

    # ── 현재 필터 표시 ────────────────────────────────────────────────────────
    fs = st.session_state.filter_student
    fj = st.session_state.filter_journal
    if fs:
        st.subheader(f"Reading material for  {fs}")
    elif fj:
        st.subheader(f"Journal: {fj}")
    else:
        st.subheader("All papers")

    # ── 검색 ─────────────────────────────────────────────────────────────────
    st.session_state.search_kw = st.text_input(
        "🔍 제목 검색", value=st.session_state.search_kw,
        placeholder="검색어 입력…", label_visibility="collapsed")

    rows = get_filtered_papers()
    st.caption(f"총 {len(rows)}편")

    # ── 논문 테이블 ───────────────────────────────────────────────────────────
    if rows:
        today = date.today()
        table_rows = []
        for student, p in rows:
            due = p.get("due_date","")
            due_disp = due
            if due:
                try:
                    d = date.fromisoformat(due)
                    if d < today:
                        due_disp = f"🔴 {due}"
                    elif (d - today).days <= 7:
                        due_disp = f"🟡 {due}"
                    else:
                        due_disp = f"🟢 {due}"
                except ValueError:
                    pass

            yr = str(p.get("year","")) if p.get("year") else ""
            table_rows.append({
                "제목":      p.get("title",""),
                "저자":      p.get("author",""),
                "저널":      p.get("journal",""),
                "연도":      yr,
                "추가날짜":  p.get("added",""),
                "배정일":    p.get("assigned_date",""),
                "마감일":    due_disp,
                "Reviewer":  p.get("reviewer",""),
                "배정 학생": p.get("assigned_to",""),
            })

        st.dataframe(table_rows, use_container_width=True,
                     hide_index=True, height=300)

    else:
        st.info("논문이 없습니다.")

    # ── 관리자 전용: 논문 추가/수정/삭제 ──────────────────────────────────────
    if is_admin:
        st.divider()

        # ── 논문 추가 폼 ──────────────────────────────────────────────────────
        with st.expander("➕ 논문 추가", expanded=True):
            with st.form("add_paper_form", clear_on_submit=True):
                title  = st.text_input("제목 *")
                c1, c2 = st.columns(2)
                author = c1.text_input("저자")
                year   = c2.number_input("게재연도", min_value=0,
                                         max_value=datetime.now().year+5,
                                         value=0, format="%d",
                                         help="0 = 미입력")

                j_opts = [""] + sorted(st.session_state.journals)
                journal_sel = st.selectbox("저널 (목록 선택)", j_opts)
                journal_inp = st.text_input("저널 직접 입력 (위 선택 우선)",
                                            placeholder="없으면 여기 입력")
                journal = journal_sel if journal_sel else journal_inp.strip()

                stu_opts = list(st.session_state.data.keys())
                assigned = st.multiselect("배정 학생",
                                          stu_opts,
                                          default=[fs] if fs and fs in stu_opts else [])

                submitted = st.form_submit_button("논문 추가", type="primary",
                                                  use_container_width=True)
                if submitted:
                    if not title.strip():
                        st.error("제목을 입력하세요.")
                    elif not assigned:
                        st.error("학생을 한 명 이상 선택하세요.")
                    else:
                        now = datetime.now().strftime("%Y-%m-%d")
                        if journal and journal not in st.session_state.journals:
                            st.session_state.journals.append(journal)
                        paper = {
                            "title":         title.strip(),
                            "author":        author.strip(),
                            "journal":       journal,
                            "year":          int(year) if year else "",
                            "added":         now,
                            "assigned_date": "",
                            "due_date":      "",
                            "reviewer":      "",
                            "assigned_to":   "; ".join(assigned),
                        }
                        for stu in assigned:
                            st.session_state.data[stu].append(paper.copy())
                        save_state()
                        st.success(f"추가됨: {title[:50]}")
                        st.rerun()

        # ── 논문 수정 ─────────────────────────────────────────────────────────
        if rows:
            with st.expander("✏️ 논문 수정 / 삭제"):
                paper_titles = [f"[{i+1}] {p.get('title','')[:60]}"
                                for i,(_, p) in enumerate(rows)]
                sel_idx = st.selectbox("수정할 논문 선택", range(len(rows)),
                                       format_func=lambda i: paper_titles[i])

                sel_student, sel_paper = rows[sel_idx]

                with st.form("edit_paper_form"):
                    e_title  = st.text_input("제목 *",
                                             value=sel_paper.get("title",""))
                    ec1, ec2 = st.columns(2)
                    e_author = ec1.text_input("저자",
                                              value=sel_paper.get("author",""))
                    e_yr_val = sel_paper.get("year",0)
                    e_year   = ec2.number_input("게재연도",
                                                min_value=0,
                                                max_value=datetime.now().year+5,
                                                value=int(e_yr_val) if e_yr_val else 0)

                    j_opts2   = [""] + sorted(st.session_state.journals)
                    cur_j     = sel_paper.get("journal","")
                    j_def     = j_opts2.index(cur_j) if cur_j in j_opts2 else 0
                    e_journal = st.selectbox("저널", j_opts2, index=j_def)

                    ed1, ed2 = st.columns(2)
                    e_adate  = ed1.text_input("배정일 (YYYY-MM-DD)",
                                               value=sel_paper.get("assigned_date",""))
                    e_due    = ed2.text_input("마감일 (YYYY-MM-DD)",
                                               value=sel_paper.get("due_date",""))

                    e_reviewer = st.text_input("Reviewer",
                                               value=sel_paper.get("reviewer",""))

                    stu_opts2   = list(st.session_state.data.keys())
                    cur_assigned = [s.strip() for s in
                                    sel_paper.get("assigned_to","").split(";")
                                    if s.strip()]
                    e_assigned  = st.multiselect("배정 학생", stu_opts2,
                                                  default=[s for s in cur_assigned
                                                           if s in stu_opts2])

                    ec1b, ec2b = st.columns(2)
                    save_edit  = ec1b.form_submit_button("💾 저장",
                                                          use_container_width=True)
                    del_paper  = ec2b.form_submit_button("🗑 삭제",
                                                          type="primary",
                                                          use_container_width=True)

                if save_edit:
                    new_paper = {
                        "title":         e_title.strip(),
                        "author":        e_author.strip(),
                        "journal":       e_journal,
                        "year":          int(e_year) if e_year else "",
                        "added":         sel_paper.get("added",""),
                        "assigned_date": e_adate.strip(),
                        "due_date":      e_due.strip(),
                        "reviewer":      e_reviewer.strip(),
                        "assigned_to":   "; ".join(e_assigned),
                    }
                    old_assigned = set(s.strip() for s in
                                       sel_paper.get("assigned_to","").split(";")
                                       if s.strip())
                    new_assigned = set(e_assigned)
                    title_key = sel_paper.get("title","").strip().lower()
                    added_key  = sel_paper.get("added","").strip()

                    for st_name in list(st.session_state.data.keys()):
                        for i, p in enumerate(st.session_state.data[st_name]):
                            if (p.get("title","").strip().lower() == title_key and
                                    p.get("added","").strip() == added_key):
                                if st_name in new_assigned:
                                    st.session_state.data[st_name][i] = dict(new_paper)
                                else:
                                    st.session_state.data[st_name].pop(i)
                                break

                    for st_name in new_assigned - old_assigned:
                        if st_name not in st.session_state.data:
                            st.session_state.data[st_name] = []
                        st.session_state.data[st_name].append(dict(new_paper))

                    if e_journal and e_journal not in st.session_state.journals:
                        st.session_state.journals.append(e_journal)

                    save_state()
                    st.success("수정됨.")
                    st.rerun()

                if del_paper:
                    title_key = sel_paper.get("title","").strip().lower()
                    added_key  = sel_paper.get("added","").strip()
                    for st_name in list(st.session_state.data.keys()):
                        st.session_state.data[st_name] = [
                            p for p in st.session_state.data[st_name]
                            if not (p.get("title","").strip().lower() == title_key
                                    and p.get("added","").strip() == added_key)
                        ]
                    save_state()
                    st.success("삭제됨.")
                    st.rerun()
