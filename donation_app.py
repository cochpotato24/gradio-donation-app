import gradio as gr
import pandas as pd
from datetime import datetime
import os
import gspread
from google.oauth2.service_account import Credentials


CSV_FILE = "donation_log.csv"

if os.path.exists(CSV_FILE):
    log_df = pd.read_csv(CSV_FILE)
else:
    log_df = pd.DataFrame(columns=["이름", "기부액", "수익", "누적수익", "응답시간"])

# ✅ 이 아래에 Google Sheets 연동 코드 삽입!
scope = ["https://spreadsheets.google.com/feeds",
         "https://www.googleapis.com/auth/spreadsheets",
         "https://www.googleapis.com/auth/drive.file",
         "https://www.googleapis.com/auth/drive"]

creds = Credentials.from_service_account_file("service_account.json", scopes=scope)
client = gspread.authorize(creds)
sheet = client.open("donation_log").sheet1


def donation_app(name, donation):
    global log_df

    if not name.strip():
        return "❗ 이름을 입력해주세요."
    if not 0 <= donation <= 1000:
        return "⚠️ 기부액은 0~1000 사이의 숫자여야 합니다."

    income = donation * 5
    time_now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    prev_total = log_df[log_df["이름"] == name]["수익"].sum()
    new_total = prev_total + income

    new_row = pd.DataFrame([{
        "이름": name,
        "기부액": donation,
        "수익": income,
        "누적수익": new_total,
        "응답시간": time_now
    }])
    log_df = pd.concat([log_df, new_row], ignore_index=True)
    log_df.to_csv(CSV_FILE, index=False, encoding='utf-8-sig')
# ✅ Google Sheets에도 저장
try:
    sheet.append_row([name, donation, income, new_total, time_now])
except Exception as e:
    print("❌ Google Sheets 저장 실패:", e)

    return f"💰 {name}님, 이번 수익은 {income}만원이며, 누적 수익은 {new_total}만원입니다."

def show_log():
    if log_df.empty:
        return "📭 아직 응답이 없습니다."
    return log_df

with gr.Blocks() as demo:
    gr.Markdown("## 💬 1000만원 중 얼마를 기부하시겠습니까?")
    gr.Markdown("📌 응답은 만원 단위로서 0~1000 사이 숫자로 입력하세요.")

    with gr.Row():
        name_input = gr.Textbox(label="이름", placeholder="예: 김철수")
        donation_slider = gr.Slider(0, 1000, step=1, label="기부액 (만원)")

    submit_btn = gr.Button("응답 제출")
    output_text = gr.Textbox(label="결과", lines=2)

    submit_btn.click(fn=donation_app, inputs=[name_input, donation_slider], outputs=output_text)

    gr.Markdown("---")
    gr.Markdown("### 📊 응답 로그 보기")
    log_btn = gr.Button("전체 로그 불러오기")
    log_output = gr.Dataframe(label="응답 기록", interactive=False)

    log_btn.click(fn=show_log, inputs=[], outputs=log_output)

if __name__ == "__main__":
    import os
    port = int(os.environ.get("PORT", 7860))  # Render가 할당한 포트를 자동으로 사용
    print(f"✅ Gradio 앱 실행 중... 포트: {port}")
    demo.launch(server_name="0.0.0.0", server_port=port, inbrowser=False)

import gradio as gr
import csv
import os
from datetime import datetime

# CSV 파일명
CSV_FILE = "donation_data.csv"

# CSV 헤더 작성 (파일이 없을 때만)
if not os.path.exists(CSV_FILE):
    with open(CSV_FILE, mode="w", newline="", encoding="utf-8") as file:
        writer = csv.writer(file)
        writer.writerow(["Timestamp", "Name", "Donation Amount", "Comment"])

# 사용자가 입력하면 이 함수가 실행됨
def record_donation(name, amount, comment):
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # CSV에 저장
    with open(CSV_FILE, mode="a", newline="", encoding="utf-8") as file:
        writer = csv.writer(file)
        writer.writerow([timestamp, name, amount, comment])

    return f"감사합니다, {name}님! {amount}원을 기부해주셨습니다."

# Gradio 인터페이스
with gr.Blocks() as demo:
    gr.Markdown("## 기부 실험 프로그램")

    name = gr.Textbox(label="이름")
    amount = gr.Number(label="기부 금액")
    comment = gr.Textbox(label="남기고 싶은 말")

    submit_btn = gr.Button("기부하기")
    output = gr.Textbox(label="결과 메시지")

    submit_btn.click(fn=record_donation, inputs=[name, amount, comment], outputs=output)

# Render 호환을 위해 host와 port 지정
demo.launch(server_name="0.0.0.0", server_port=10000)

import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime

# [1] 인증 범위 정의
scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]

# [2] 서비스 계정 키 파일 경로 지정 (여기서 your_key.json은 실제 파일명으로 바꿔야 함)
creds = ServiceAccountCredentials.from_json_keyfile_name("gradio-donation-bot.json", scope)

# [3] 구글 시트 클라이언트 인증
client = gspread.authorize(creds)

# [4] 스프레드시트 열기
sheet = client.open("donation_log").sheet1  # 시트 제목이 "donation_log"일 경우

def save_to_sheet(name, amount):
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    amount = int(amount)

    # 현재 데이터 가져오기
    data = sheet.get_all_records()
    total = amount
    if data:
        last_row = data[-1]
        prev_total = last_row.get("Total", 0)
        try:
            total += int(prev_total)
        except:
            pass

    # 시트에 행 추가
    sheet.append_row([timestamp, name, amount, total])

import os
import json

# GitHub Actions 환경에서 JSON 키를 문자열로 가져와 파일로 저장
gcp_json = os.environ.get("GOOGLE_APPLICATION_CREDENTIALS_JSON")

with open("gcp_key.json", "w") as f:
    f.write(gcp_json)

# 환경변수로 인증 파일 경로 설정
os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = "gcp_key.json"

import os
import json
import gspread
from oauth2client.service_account import ServiceAccountCredentials

# GitHub Secrets에서 가져오기
creds_json = os.getenv("GOOGLE_APPLICATION_CREDENTIALS_JSON")
creds_dict = json.loads(creds_json)

scope = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
credentials = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
gc = gspread.authorize(credentials)
sheet = gc.open_by_key("your_google_sheet_id").sheet1

# 예시 - 시트에 기록
sheet.append_row([timestamp, name, donation, total])

import gspread
from google.oauth2.service_account import Credentials

# Google Sheets 인증
scope = ["https://spreadsheets.google.com/feeds",'https://www.googleapis.com/auth/spreadsheets',
         "https://www.googleapis.com/auth/drive.file","https://www.googleapis.com/auth/drive"]
creds = Credentials.from_service_account_file("gcp_key.json", scopes=scope)
client = gspread.authorize(creds)

# 시트 열기
sheet = client.open("donation_log").sheet1

# 응답 기록 예시
sheet.append_row([timestamp, name, donation, total])

import gspread
from google.oauth2.service_account import Credentials

# Google Sheets 인증 설정
scope = ["https://spreadsheets.google.com/feeds",
         "https://www.googleapis.com/auth/spreadsheets",
         "https://www.googleapis.com/auth/drive.file",
         "https://www.googleapis.com/auth/drive"]

creds = Credentials.from_service_account_file("gcp_key.json", scopes=scope)
client = gspread.authorize(creds)

# 시트 열기 (시트 이름이 정확히 일치해야 함)
sheet = client.open("donation_log").sheet1


def record_donation(name, amount, comment):
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # CSV 저장
    with open(CSV_FILE, mode="a", newline="", encoding="utf-8") as file:
        writer = csv.writer(file)
        writer.writerow([timestamp, name, amount, comment])

    # ✅ Google Sheets에도 저장
    try:
        sheet.append_row([timestamp, name, amount, comment])
    except Exception as e:
        print("Google Sheets 저장 실패:", e)

    return f"감사합니다, {name}님! {amount}원을 기부해주셨습니다."
import os
print("현재 경로 파일 목록:", os.listdir())
print("gcp_key.json 존재 여부:", os.path.exists("gcp_key.json"))









