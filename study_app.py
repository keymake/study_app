import streamlit as st
import json, os
from datetime import datetime, timedelta, timezone, date

st.set_page_config(
    page_title="성진 공부 프로젝트",
    page_icon="📘",
)

KST = timezone(timedelta(hours=9))  # 한국 표준시


# JSON 파일 로드
def load_data():
    if not os.path.exists("records.json"):
        return {"total_points": 0, "days": {}}
    with open("records.json", "r", encoding="utf-8") as f:
        return json.load(f)

def save_data(data):
    with open("records.json", "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

# 날짜 헬퍼
def to_date(s: str) -> date:
    return datetime.strptime(s, "%Y-%m-%d").date()

def to_str(d: date) -> str:
    return d.strftime("%Y-%m-%d")

# 포인트 계산 (해당 날짜 기준으로 어제 참조)
def update_points(data, date_str, status):
    date_obj = to_date(date_str)
    yesterday_str = to_str(date_obj - timedelta(days=1))

    total = data["total_points"]

    if status == "T":
        total += 0.3
        prev_status = data["days"].get(yesterday_str, {}).get("status")
        if prev_status == "T":
            total += 0.2   # 연속 T 보너스
        elif prev_status == "F":
            total -= 0.1   # 전날 F 페널티
    elif status == "F":
        total -= 0.3

    data["total_points"] = round(total, 2)

    day = data["days"].get(date_str, {"tasks": [], "status": "미확정"})
    day["status"] = status
    day["points"] = data["total_points"]
    data["days"][date_str] = day

    save_data(data)

# 잠수 방지: 직전 T ~ 오늘 사이 빈 날 F 처리
def fill_missing_days_as_F(data, today_str):
    if not data["days"]:
        return data

    today_d = to_date(today_str)

    # 오늘보다 이전의 T 날짜들 중 가장 최근
    t_dates = [
        to_date(d)
        for d, info in data["days"].items()
        if info.get("status") == "T" and to_date(d) < today_d
    ]
    if not t_dates:
        return data  # 이전에 T가 없으면 잠수 정산할 구간 없음

    last_t_date = max(t_dates)

    cur = last_t_date + timedelta(days=1)
    end = today_d - timedelta(days=1)

    while cur <= end:
        d_str = to_str(cur)
        info = data["days"].get(d_str, {"tasks": [], "status": "미확정"})

        # 아직 확정 안 된 날만 잠수 F로 처리
        if info.get("status") not in ["T", "F"]:
            data["days"][d_str] = info
            update_points(data, d_str, "F")

        cur += timedelta(days=1)

    return data

# 🔥 최근 T 이전 날짜 싹 삭제
def prune_before_last_T(data):
    # T가 아예 없으면 아무 것도 안 지움
    t_dates = [
        to_date(d)
        for d, info in data["days"].items()
        if info.get("status") == "T"
    ]
    if not t_dates:
        return data

    last_t_date = max(t_dates)  # "가장 최근 T 날짜"
    new_days = {
        d: info
        for d, info in data["days"].items()
        if to_date(d) >= last_t_date
    }
    data["days"] = new_days
    return data

# 오늘 날짜
today = datetime.now(KST).strftime("%Y-%m-%d")

st.title("📘 공부 프로젝트 출석 관리기")
data = load_data()
today_data = data["days"].get(today, {"tasks": [], "status": "미확정"})

# 항목 추가
st.subheader("오늘의 공부 계획")
new_task = st.text_input("새 항목 추가 (최대 10개)", "")
if st.button("항목 추가") and len(today_data["tasks"]) < 10 and new_task:
    today_data["tasks"].append({"name": new_task, "done": False})
    data["days"][today] = today_data
    save_data(data)
    st.rerun()

# 항목 표시
for i, task in enumerate(today_data["tasks"]):
    done = st.checkbox(task["name"], value=task["done"], key=i)
    today_data["tasks"][i]["done"] = done

all_done = all(task["done"] for task in today_data["tasks"]) and today_data["tasks"]

if all_done:
    # 오늘 데이터 일단 저장
    data["days"][today] = today_data

    # 1) 잠수방지: 직전 T ~ 오늘 사이 빈 날 F 처리
    data = fill_missing_days_as_F(data, today)

    # 2) 오늘 T로 확정 & 포인트 계산
    if today_data["status"] != "T":
        update_points(data, today, "T")

    # 3) 최근 T 이전 날짜들 싹 삭제 (네가 말한 그 부분)
    data = prune_before_last_T(data)

    # 4) 오늘 데이터 다시 꺼내오기
    today_data = data["days"][today]
    save_data(data)
    st.success("✅ 모든 항목 완료! 오늘은 T로 기록되었습니다.")

# 저장
data["days"][today] = today_data
save_data(data)

st.markdown("---")
st.write(f"📅 오늘 날짜: {today}")
st.write(f"🏆 총합 포인트: **{data['total_points']}pt**")
