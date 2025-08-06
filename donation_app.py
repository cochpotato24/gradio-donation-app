import gradio as gr
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import os
from datetime import datetime

# 인증 설정
scope = [
    'https://www.googleapis.com/auth/spreadsheets',
    'https://www.googleapis.com/auth/drive',
]
credentials = ServiceAccountCredentials.from_json_keyfile_name(
    '/etc/secrets/service_account.json', scope
)
gc = gspread.authorize(credentials)

# 스프레드시트 정보
SPREADSHEET_NAME = os.environ['SPREADSHEET_NAME']
worksheet = gc.open(SPREADSHEET_NAME).sheet1

# 기부자 데이터 저장
donors = []

# 실시간 기부 정보 저장 함수
def donate(name, amount):
    donors.append({"이름": name, "기부금": amount})

    if len(donors) < 3:
        return f"{name}님 기부 감사합니다! 아직 {3 - len(donors)}명의 참여가 더 필요합니다."

    # 3명 도달 시 계산
    total_donation = sum(d['기부금'] for d in donors)
    public_account = total_donation * 2
    public_per_person = public_account / 3

    result_text = "❤️ 최종 기부 결과 ❤️\n"
    for d in donors:
        personal_account = 10000 - d['기부금']
        final_earning = personal_account + public_per_person
        response_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

        # Google Sheets 저장
        worksheet.append_row([
            d['이름'],                     # A: 이름
            d['기부금'],                   # B: 기부액
            personal_account,             # C: 개인계정
            round(public_per_person, 3),  # D: 공공계정
            round(final_earning, 3),      # E: 최종수익
            response_time                 # F: 응답시간
        ])

        result_text += f"{d['이름']}님의 최종수익: {int(final_earning)}원\n"

    donors.clear()
    return result_text

# 새로고침 버튼 동작 - Google Sheets에서 마지막 3명 정보 불러오기
def refresh_results():
    records = worksheet.get_all_records()
    if len(records) < 3:
        return "아직 기부자가 3명 이상이 아닙니다. 기부가 완료되면 최종수익이 표시됩니다."

    last_three = records[-3:]
    result_text = "❤️ 최종 기부 결과 ❤️\n"
    for record in last_three:
        name = record['이름']
        final_earning = int(float(record['최종수익']))
        result_text += f"{name}님의 최종수익: {final_earning}원\n"

    return result_text

# Gradio 인터페이스
with gr.Blocks() as app:
    gr.Markdown("## 🎁 기부 실험\n10000원 중 얼마를 기부하시겠습니까?")
    name = gr.Textbox(label="이름")
    amount = gr.Slider(0, 10000, step=500, label="기부 금액 (₩)")
    output = gr.Textbox(label="결과", lines=6)
    
    donate_btn = gr.Button("기부하기")
    refresh_btn = gr.Button("🔄 새로고침하여 최종결과 보기")

    donate_btn.click(donate, inputs=[name, amount], outputs=output)
    refresh_btn.click(refresh_results, outputs=output)

app.launch(server_name="0.0.0.0", server_port=10000)
