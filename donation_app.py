import gradio as gr
import pandas as pd
import gspread
import json
import os
from google.oauth2 import service_account
from datetime import datetime

# Google Sheets 연동 설정
SCOPES = ['https://www.googleapis.com/auth/spreadsheets']
SECRET_PATH = '/etc/secrets/service_account.json'  # Render Secret Files 위치
SPREADSHEET_NAME = 'donation_log'

credentials = service_account.Credentials.from_service_account_file(
    SECRET_PATH, scopes=SCOPES
)
gc = gspread.authorize(credentials)
spreadsheet = gc.open(SPREADSHEET_NAME)
worksheet = spreadsheet.sheet1

MAX_PARTICIPANTS = 3

def get_current_data():
    data = worksheet.get_all_records()
    return data

def calculate_income(data):
    total_private_donation = sum(row['기부액'] for row in data)
    total_public = total_private_donation * 2
    per_person_public = total_public / MAX_PARTICIPANTS
    result = []
    for row in data:
        개인수익 = 10000 - row['기부액']
        최종수익 = 개인수익 + per_person_public
        result.append({'이름': row['이름'], '기부액': row['기부액'], '최종수익': round(최종수익)})
    return result

def donate(name, donation):
    data = get_current_data()
    if any(row['이름'] == name for row in data):
        return f"❌ {name}님은 이미 참여하셨습니다.", pd.DataFrame(data)
    if len(data) >= MAX_PARTICIPANTS:
        return "❌ 이미 최대 3명이 참여하여 실험이 종료되었습니다.", pd.DataFrame(data)

    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    worksheet.append_row([name, donation, now])

    updated_data = get_current_data()
    if len(updated_data) < MAX_PARTICIPANTS:
        return f"✅ {name}님 참여 완료! 나머지 {MAX_PARTICIPANTS - len(updated_data)}명 대기 중입니다.", pd.DataFrame(updated_data)
    else:
        result_data = calculate_income(updated_data)
        worksheet.clear()
        worksheet.append_row(["이름", "기부액", "최종수익", "입력시간"])
        for r in result_data:
            worksheet.append_row([r['이름'], r['기부액'], r['최종수익'], now])
        return "✅ 실험 완료! 아래에서 결과를 확인하세요.", pd.DataFrame(result_data)

# 인터페이스 구성
with gr.Blocks() as demo:
    gr.Markdown("🎁 **기부 실험 프로그램**")
    gr.Markdown("아래에 이름과 기부액을 입력하세요. (3명까지 참여 가능)")

    with gr.Row():
        name_input = gr.Textbox(label="이름")
        donation_input = gr.Slider(0, 10000, step=1000, label="10000원 중 얼마를 기부하시겠습니까?")

    result_output = gr.Textbox(label="결과 안내", interactive=False)
    result_table = gr.Dataframe(headers=["이름", "기부액", "최종수익"], interactive=False)

    donate_btn = gr.Button("참여하기")

    donate_btn.click(fn=donate, inputs=[name_input, donation_input], outputs=[result_output, result_table])

    gr.Markdown("📌 참여자는 언제든 접속하여 자신이 받은 최종수익을 확인할 수 있습니다.")
    gr.Markdown("✅ 아래 스프레드시트 또는 테이블이 자동으로 최신 상태로 유지됩니다.")

demo.launch()
