import streamlit as st
import json, os
from datetime import datetime, timedelta, timezone

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

# 포인트 계산
def update_points(data, date, status):
    yesterday = (datetime.now(KST) - timedelta(days=1)).strftime("%Y-%m-%d")
    total = data["total_points"]

    if status == "T":
        total += 0.3
        if data["days"].get(yesterday, {}).get("status") == "T":
            total += 0.2
        elif data["days"].get(yesterday, {}).get("status") == "F":
            total -= 0.1
    elif status == "F":
        total -= 0.3

    data["total_points"] = round(total, 2)
    data["days"][date]["status"] = status
    data["days"][date]["points"] = data["total_points"]
    save_data(data)

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

# T/F 판정
if all(task["done"] for task in today_data["tasks"]) and today_data["tasks"]:
    if today_data["status"] != "T":
        update_points(data, today, "T")
        st.success("✅ 모든 항목 완료! 오늘은 T로 기록되었습니다.")
else:
    if datetime.now(KST).hour == 0 and today_data["status"] != "T":
        update_points(data, today, "F")
        st.error("❌ 오늘 미완료 항목 존재. F로 처리되었습니다.")

# 저장
data["days"][today] = today_data
save_data(data)

st.markdown("---")
st.write(f"📅 오늘 날짜: {today}")
st.write(f"🏆 총합 포인트: **{data['total_points']}pt**")
