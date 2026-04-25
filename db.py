"""
db.py
=====
Supabase (PostgreSQL) backed data layer. Drop-in replacement for sheets.py.

Tables required (create once via Supabase SQL Editor):

    create table students (
      id bigserial primary key,
      name text unique not null
    );

    create table papers (
      id bigserial primary key,
      student text not null,
      title text, author text, journal text, year text,
      added text, assigned_date text, due_date text,
      reviewer text, assigned_to text
    );

    create table journals (name text primary key);

    alter table students disable row level security;
    alter table papers   disable row level security;
    alter table journals disable row level security;
"""

import streamlit as st
from supabase import create_client, Client


PAPER_COLS = [
    "title", "author", "journal", "year",
    "added", "assigned_date", "due_date", "reviewer", "assigned_to",
]


@st.cache_resource
def _client() -> Client:
    return create_client(
        st.secrets["supabase_url"],
        st.secrets["supabase_service_key"],
    )


# ---- papers : dict {student: [paper_dict, ...]} ----------------------------
def load_data():
    client = _client()
    # Students (including ones with no papers yet) — ordered by insertion
    student_rows = client.table("students").select("name").order("id").execute().data
    data = {r["name"]: [] for r in student_rows if r.get("name")}

    # Papers grouped by student
    paper_rows = client.table("papers").select("*").order("id").execute().data
    for r in paper_rows:
        student = (r.get("student") or "").strip()
        if not student:
            continue
        clean = {k: r[k] for k in PAPER_COLS
                 if r.get(k) not in ("", None)}
        data.setdefault(student, []).append(clean)
    return data


def save_data(data):
    client = _client()

    # Sync students table: delete all + insert current keys
    client.table("students").delete().neq("id", -1).execute()
    if data:
        client.table("students").insert(
            [{"name": s} for s in data.keys()]
        ).execute()

    # Papers: delete all + insert flattened
    client.table("papers").delete().neq("id", -1).execute()
    rows = []
    for student, papers in data.items():
        for p in papers:
            row = {"student": student}
            for k in PAPER_COLS:
                v = p.get(k, "")
                row[k] = str(v) if v != "" else ""
            rows.append(row)
    if rows:
        client.table("papers").insert(rows).execute()


# ---- journals : list[str] --------------------------------------------------
def load_journals():
    rows = _client().table("journals").select("name").execute().data
    return [r["name"] for r in rows if r.get("name")]


def save_journals(journals):
    client = _client()
    client.table("journals").delete().neq("name", "__nonexistent__").execute()
    if journals:
        client.table("journals").insert([{"name": j} for j in journals]).execute()


# 1-second cache so multiple reads inside one rerun don't hit the API.
load_data     = st.cache_data(ttl=1)(load_data)
load_journals = st.cache_data(ttl=1)(load_journals)
