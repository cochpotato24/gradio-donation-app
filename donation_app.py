import gradio as gr
import pandas as pd
from datetime import datetime
import os
import gspread
from google.oauth2.service_account import Credentials

# CSV 파일명
CSV_FILE = "donation_log.csv"

# CSV 로컬 로그 불러오기 또는 생성
if os.path.exists(CSV_FILE):
    log_df = pd.read_csv(CSV_FILE)
else:
    log_df = pd.DataFrame(columns=["이름", "기부액", "수익", "누적수익", "응답시간"])

import jason 
# ✅ Google Sheets 인증 (Render 환경 변수 사용)
scope = [
    "https://spreadsheets.google.com/feeds",
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive.file",
    "https://www.googleapis.com/auth/drive"
]

# 환경 변수로부터 JSON 인증 정보 읽기
creds_json = os.environ.get("GOOGLE_APPLICATION_CREDENTIALS_JSON")
creds_dict = json.loads(creds_json)

creds = Credentials.from_service_account_info(creds_dict, scopes=scope)
client = gspread.authorize(creds)
sheet = client.open("donation_log").sheet1  # ✅ Google Sheet 문서명 정확히 일치해야 함

# ✅ Gradio 입력 처리 함수
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

    # 새로운 행 추가 (로컬 CSV용)
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

# 로그 확인용 함수
def show_log():
    if log_df.empty:
        return "📭 아직 응답이 없습니다."
    return log_df

# ✅ Gradio UI 구성
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

# ✅ Render 호환을 위한 실행 설정
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 7860))
    print(f"✅ Gradio 앱 실행 중... 포트: {port}")
    demo.launch(server_name="0.0.0.0", server_port=port, inbrowser=False)
