import gradio as gr
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import os
import gspread

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

# UI 함수
def donate(name, amount):
    donors.append({"이름": name, "기부금": amount})
    
    if len(donors) < 3:
        return f"{name}님 기부 감사합니다! 아직 {3 - len(donors)}명의 참여가 더 필요합니다."
    
    total = sum(d['기부금'] for d in donors)
    public_account = total * 2
    per_person = public_account / 3
    
    result_text = "💗 최종 기부 결과 💗\n"
    for d in donors:
        result_text += f"{d['이름']}님의 수익 배분액: {per_person:.0f}원\n"
    
    # Google Sheets에 기록
    for d in donors:
        worksheet.append_row([d['이름'], d['기부금'], per_person])
    
    donors.clear()
    return result_text

# Gradio 인터페이스
with gr.Blocks() as app:
    gr.Markdown("## 🎁 기부 실험\n10000원 중 얼마를 기부하시겠습니까?")
    name = gr.Textbox(label="이름")
    amount = gr.Slider(0, 10000, step=500, label="기부 금액 (₩)")
    output = gr.Textbox(label="결과")
    btn = gr.Button("기부하기")
    btn.click(donate, inputs=[name, amount], outputs=output)

app.launch(server_name="0.0.0.0", server_port=10000)
