import streamlit as st
from datetime import datetime, timedelta, timezone, date
import json
from supabase import create_client, Client

KST = timezone(timedelta(hours=9))


# -------------------------------------------
# Supabase Client
# -------------------------------------------
@st.cache_resource
def get_supabase_client() -> Client:
    url = st.secrets["SUPABASE_URL"]
    key = st.secrets["SUPABASE_KEY"]
    return create_client(url, key)


supabase = get_supabase_client()


# -------------------------------------------
# Config Helpers (total_points 저장용)
# -------------------------------------------
def load_total_points():
    res = supabase.table("config").select("*").eq("key", "study_total_points").execute()
    rows = res.data or []
    if not rows:
        return 0.0
    try:
        return float(rows[0]["value"])
    except:
        return 0.0


def save_total_points(v: float):
    supabase.table("config").upsert({"key": "study_total_points", "value": str(v)}).execute()


# -------------------------------------------
# Date Helpers
# -------------------------------------------
def to_date(s: str) -> date:
    return datetime.strptime(s, "%Y-%m-%d").date()


def to_str(d: date) -> str:
    return d.strftime("%Y-%m-%d")


# -------------------------------------------
# DB Helpers
# -------------------------------------------
def load_day(date_str: str):
    res = supabase.table("study_records").select("*").eq("date", date_str).execute()
    rows = res.data or []
    if rows:
        return rows[0]

    new_row = {
        "date": date_str,
        "tasks": [],
        "status": "미확정",
        "points": None
    }
    supabase.table("study_records").insert(new_row).execute()
    return new_row


def save_day(date_str: str, data: dict):
    supabase.table("study_records").upsert({
        "date": date_str,
        "tasks": data.get("tasks", []),
        "status": data.get("status", "미확정"),
        "points": data.get("points")
    }).execute()


def load_all_days():
    res = supabase.table("study_records").select("*").execute()
    return res.data or []


# -------------------------------------------
# 잠수방지 기능: 직전 T ~ 오늘 사이 모두 F 처리
# -------------------------------------------
def fill_missing_days_as_F(today_str):
    all_days = load_all_days()
    today_d = to_date(today_str)

    # 과거 T 날짜들 찾기
    t_dates = [
        to_date(row["date"])
        for row in all_days
        if row.get("status") == "T" and to_date(row["date"]) < today_d
    ]

    if not t_dates:
        # 과거에 T 없으면 → 단순히 오늘 바로 전날까지만 캘린더로 채움
        last_t_date = today_d - timedelta(days=1)
    else:
        last_t_date = max(t_dates)

    # 캘린더 기준으로 last_t_date+1 ~ today-1 까지 모두 F 처리
    cur = last_t_date + timedelta(days=1)
    end = today_d - timedelta(days=1)

    total = load_total_points()

    while cur <= end:
        d_str = to_str(cur)

        # row가 없더라도 강제로 생성함
        row = load_day(d_str)

        # 이미 T/F가 아니라면 F로 확정
        if row.get("status") not in ["T", "F"]:
            total -= 0.3
            row["status"] = "F"
            row["points"] = round(total, 2)
            save_day(d_str, row)
            save_total_points(total)

        cur += timedelta(days=1)



# -------------------------------------------
# 최근 T 이전 날짜 싹 삭제
# -------------------------------------------
def prune_before_last_T():
    all_days = load_all_days()
    if not all_days:
        return

    t_dates = [
        to_date(row["date"])
        for row in all_days
        if row.get("status") == "T"
    ]
    if not t_dates:
        return

    last_t = max(t_dates)
    cutoff = to_str(last_t)

    supabase.table("study_records").delete().lt("date", cutoff).execute()


# -------------------------------------------
# 포인트 계산 및 T/F 저장
# -------------------------------------------
def update_status_and_points(date_str, new_status):
    today_row = load_day(date_str)
    total = load_total_points()

    today_d = to_date(date_str)
    y_str = to_str(today_d - timedelta(days=1))

    # 어제 row
    all_rows = load_all_days()
    y_rows = [r for r in all_rows if r["date"] == y_str]
    prev_status = y_rows[0].get("status") if y_rows else None

    if new_status == "T":
        total += 0.3
        if prev_status == "T":
            total += 0.2
        elif prev_status == "F":
            total -= 0.1
    else:
        total -= 0.3

    total = round(total, 2)
    save_total_points(total)

    today_row["status"] = new_status
    today_row["points"] = total
    save_day(date_str, today_row)


# -------------------------------------------
# UI
# -------------------------------------------
today = datetime.now(KST).strftime("%Y-%m-%d")

st.title("📘 공부 프로젝트 출석 관리기")
today_data = load_day(today)
tasks = today_data.get("tasks", [])


# -------------------------------------------
# 오늘의 공부 계획
# -------------------------------------------
st.subheader("오늘의 공부 계획")

with st.form("add_task_form"):
    new_task = st.text_input("새 항목 추가 (최대 10개)")
    submitted = st.form_submit_button("항목 추가")
    if submitted and new_task and len(tasks) < 10:
        tasks.append({"name": new_task, "done": False})
        today_data["tasks"] = tasks
        save_day(today, today_data)
        st.rerun()


# -------------------------------------------
# 체크박스 + 수정/삭제 UI
# -------------------------------------------
done_list = []

st.markdown("### ✏️ 항목 관리")

for i, task in enumerate(tasks):
    col1, col2, col3 = st.columns([5, 3, 2])

    with col1:
        done = st.checkbox(task["name"], value=task["done"], key=f"task_{i}")
        tasks[i]["done"] = done

    with col2:
        new_name = st.text_input(
            f"edit_{i}",
            value=task["name"],
            label_visibility="collapsed",
        )

    with col3:
        if st.button("삭제", key=f"del_{i}"):
            tasks.pop(i)
            today_data["tasks"] = tasks
            save_day(today, today_data)
            st.rerun()

    # 이름 수정 반영
    if new_name != task["name"]:
        tasks[i]["name"] = new_name

    done_list.append(done)

today_data["tasks"] = tasks
save_day(today, today_data)


# -------------------------------------------
# 모든 항목 완료 → T 처리
# -------------------------------------------
all_done = len(tasks) > 0 and all(done_list)

if all_done:
    fill_missing_days_as_F(today)
    if today_data.get("status") != "T":
        update_status_and_points(today, "T")
    prune_before_last_T()

     # ★ 추가
    today_data = load_day(today)

    st.success("✅ 모든 항목 완료! 오늘은 T로 기록되었습니다.")


# -------------------------------------------
# 오늘 정보 표시 + 상태 표시 추가
# -------------------------------------------
st.markdown("---")

# 상태 문구 추가된 부분
if today_data.get("status") == "미확정":
    st.info("오늘은 아직 F입니다.")
elif today_data.get("status") == "T":
    st.success("오늘은 T로 기록되었습니다.")

st.write(f"📅 오늘 날짜: {today}")
st.write(f"🏆 총합 포인트: **{load_total_points()}pt**")
