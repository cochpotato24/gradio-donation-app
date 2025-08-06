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
    log_df = pd.DataFrame(columns=["이름", "기부액", "개인계정", "공공계정", "최종수익", "응답시간"])

# ✅ Google Sheets 인증 (환경변수 또는 로컬 파일 활용)
scope = [
    "https://spreadsheets.google.com/feeds",
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive.file",
    "https://www.googleapis.com/auth/drive"
]

# Render 환경에서는 환경변수에서 JSON을 불러와 처리
if os.getenv("GOOGLE_APPLICATION_CREDENTIALS_JSON"):
    import json
    creds_json = os.environ.get("GOOGLE_APPLICATION_CREDENTIALS_JSON")
    creds_dict = json.loads(creds_json)
    creds = Credentials.from_service_account_info(creds_dict, scopes=scope)
else:
    creds = Credentials.from_service_account_file("service_account.json", scopes=scope)

client = gspread.authorize(creds)
sheet = client.open("donation_log").sheet1

# ✅ Gradio 입력 처리 함수
def donation_app(name, donation):
    global log_df

    if not name.strip():
        return "❗ 이름을 입력해주세요."
    if not 0 <= donation <= 10000:
        return "⚠️ 기부액은 0~10,000 사이의 숫자여야 합니다."

    total_budget = 10000
    time_now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # 새로운 응답 추가 전 기부 총합과 참여자 수 계산을 위해 잠시 추가해 놓음
    temp_df = pd.concat([log_df, pd.DataFrame([{"이름": name, "기부액": donation}])], ignore_index=True)

    total_donation = temp_df["기부액"].sum()
    num_participants = temp_df.shape[0]

    public_account = (total_donation * 2) / num_participants
    private_account = total_budget - donation
    final_income = private_account + public_account

    # 새로운 행 구성
    new_row = pd.DataFrame([{
        "이름": name,
        "기부액": donation,
        "개인계정": private_account,
        "공공계정": public_account,
        "최종수익": final_income,
        "응답시간": time_now
    }])

    log_df = pd.concat([log_df, new_row], ignore_index=True)
    log_df.to_csv(CSV_FILE, index=False, encoding='utf-8-sig')

    try:
        sheet.append_row([name, donation, private_account, public_account, final_income, time_now])
    except Exception as e:
        print("❌ Google Sheets 저장 실패:", e)

    return f"💰 {name}님, 당신의 최종수익은 {int(final_income):,}원입니다."

# 로그 확인용 함수
def show_log():
    if log_df.empty:
        return "📭 아직 응답이 없습니다."
    return log_df

# ✅ Gradio UI 구성
with gr.Blocks() as demo:
    gr.Markdown("## 💬 10,000원 중 얼마를 기부하시겠습니까?")
    gr.Markdown("📌 응답은 0~10,000 사이 숫자로 입력하세요.")

    with gr.Row():
        name_input = gr.Textbox(label="이름", placeholder="예: 김철수")
        donation_slider = gr.Slider(0, 10000, step=100, label="기부액 (원)")

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
