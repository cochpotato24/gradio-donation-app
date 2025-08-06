import os
import gradio as gr
import pandas as pd
from datetime import datetime
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from dotenv import load_dotenv

# 환경변수 로드
load_dotenv()

# 구글 시트 인증 설정
scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
credentials = ServiceAccountCredentials.from_json_keyfile_name(os.getenv("GOOGLE_SHEETS_SECRET_JSON"), scope)
client = gspread.authorize(credentials)
spreadsheet = client.open(os.getenv("SPREADSHEET_NAME"))
worksheet = spreadsheet.sheet1

# 참여자 데이터 초기화
participants = {}

def calculate_payouts():
    global participants
    if len(participants) < 3:
        return None

    total_donation = sum(participants.values())
    public_account = total_donation * 2
    equal_share = public_account / 3

    results = {}
    for name, donation in participants.items():
        private_account = 10000 - donation
        final_earning = private_account + equal_share
        results[name] = {
            "기부액": donation,
            "개인계정": private_account,
            "공공계정": equal_share,
            "최종수익": final_earning
        }

        # Google Sheets에 기록
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        worksheet.append_row([name, donation, private_account, equal_share, final_earning, now])

    participants = {}  # 초기화
    return results

def participate(name, donation_amount):
    name = name.strip()
    if not name:
        return "⚠️ 이름을 입력하세요."
    if not (0 <= donation_amount <= 10000):
        return "⚠️ 기부액은 0원 이상 10000원 이하로 입력해야 합니다."
    if name in participants:
        return f"⚠️ '{name}'님은 이미 참여하셨습니다."
    if len(participants) >= 3:
        return "⚠️ 이미 3명의 참여자가 등록되었습니다."

    participants[name] = donation_amount
    if len(participants) == 3:
        results = calculate_payouts()
        table = pd.DataFrame(results).T.reset_index()
        table.columns = ['이름', '기부액', '개인계정', '공공계정', '최종수익']
        return table
    else:
        return f"'{name}'님이 성공적으로 참여하셨습니다. 현재 {len(participants)}/3명 참여 완료되었습니다."

# Gradio UI 구성
with gr.Blocks(title="기부 실험 프로그램") as demo:
    gr.Markdown("🎁 **기부 실험 프로그램**")
    gr.Markdown("10000원 중 얼마를 기부하시겠습니까?")
    gr.Markdown("응답은 **만원 단위로서 0~10000 사이 숫자**로 입력하세요. (3명까지 참여 가능)")

    with gr.Row():
        name_input = gr.Textbox(label="이름", placeholder="이름 입력")
        donation_input = gr.Slider(minimum=0, maximum=10000, step=1000, label="기부액 (0~10000원)", value=0)

    output_box = gr.Textbox(label="결과 안내", lines=2)
    table_output = gr.DataFrame(label="📊 최종 결과표", interactive=False)

    submit_btn = gr.Button("🎯 참여하기")

    submit_btn.click(
        fn=participate,
        inputs=[name_input, donation_input],
        outputs=[output_box | table_output]
    )

    gr.Markdown("📌 참여자는 언제든 접속하여 자신이 받은 최종수익을 확인할 수 있습니다.")
    gr.Markdown("✅ 아래 스프레드시트 또는 테이블이 자동으로 최신 상태로 유지됩니다.")

if __name__ == "__main__":
    demo.launch(server_name="0.0.0.0", server_port=10000)
