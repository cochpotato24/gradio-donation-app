import os
import json
import gradio as gr
from datetime import datetime
from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build

# 구글 시트 설정
SCOPES = ['https://www.googleapis.com/auth/spreadsheets']
SHEET_ID = '여기에_당신의_스프레드시트_ID_입력'
SHEET_RANGE = 'A2:F'

# 🔑 Secret 파일에서 자격 증명 로드
JSON_KEYFILE = "/etc/secrets/service_account.json"
credentials = Credentials.from_service_account_file(JSON_KEYFILE, scopes=SCOPES)
service = build('sheets', 'v4', credentials=credentials)
sheet = service.spreadsheets()

# 참여자 목록 가져오기
def read_sheet():
    result = sheet.values().get(spreadsheetId=SHEET_ID, range=SHEET_RANGE).execute()
    return result.get('values', [])

# 시트에 데이터 추가
def append_to_sheet(data):
    sheet.values().append(
        spreadsheetId=SHEET_ID,
        range=SHEET_RANGE,
        valueInputOption='USER_ENTERED',
        body={'values': [data]}
    ).execute()

# 참여 처리 함수
def process_donation(name, amount):
    amount = int(amount)
    existing = read_sheet()

    # 참여 인원 3명 이상이면 입력 차단
    if len(existing) >= 3:
        return "참여 인원이 모두 찼습니다. 더 이상 참여할 수 없습니다."

    # 응답시간 기록
    response_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

    # 최종 참여자일 경우 계산 시작
    if len(existing) == 2:  # 이번이 3번째 참여자라면
        # 기존 참여자 정보
        names = [row[0] for row in existing]
        donations = [int(row[1]) for row in existing]
        total_donation = sum(donations) + amount

        # 공공계정 총합 = 기부총액 * 2
        public_fund = total_donation * 2
        shared_fund = public_fund // 3  # 모든 참여자에게 균등하게 배분

        # 기존 참여자 각각 계산 후 업데이트
        for i, row in enumerate(existing):
            donor_name = row[0]
            donor_amount = int(row[1])
            private_amount = total_donation - donor_amount
            final_income = private_amount + shared_fund
            existing[i] = [donor_name, donor_amount, private_amount, shared_fund, final_income, row[5] if len(row) > 5 else '']

        # 마지막 참여자 정보도 계산
        private_amount = total_donation - amount
        final_income = private_amount + shared_fund
        new_row = [name, amount, private_amount, shared_fund, final_income, response_time]

        # 시트 업데이트
        for i in range(2):
            sheet.values().update(
                spreadsheetId=SHEET_ID,
                range=f"A{2 + i}:F{2 + i}",
                valueInputOption='USER_ENTERED',
                body={'values': [existing[i]]}
            ).execute()

        append_to_sheet(new_row)

        return "✅ 세 번째 참여가 완료되어 모든 참여자의 최종수익이 계산되었습니다. 아래에서 확인하세요."

    else:
        # 최종 계산 전까지는 개인계정만 계산하여 기록
        other_amount = sum([int(row[1]) for row in existing])
        private_amount = other_amount
        shared_fund = ""
        final_income = ""
        append_to_sheet([name, amount, private_amount, shared_fund, final_income, response_time])
        return f"☑️ {len(existing)+1}번째 참여 완료! 총 3명이 참여해야 최종 수익이 계산됩니다.\n잠시만 기다려주세요."

# 인터페이스 구성
with gr.Blocks() as app:
    gr.Markdown("## 🎁 기부 실험 프로그램")
    gr.Markdown("아래에 이름과 기부액을 입력하세요. (3명까지 참여 가능)")

    with gr.Row():
        name = gr.Textbox(label="이름", placeholder="예: 김철수")
        amount = gr.Number(label="기부액", precision=0)

    output = gr.Textbox(label="결과 안내")

    submit_btn = gr.Button("참여하기")
    submit_btn.click(fn=process_donation, inputs=[name, amount], outputs=output)

    gr.Markdown("📌 참여자는 언제든 접속하여 자신이 받은 **최종수익**을 확인할 수 있습니다.")
    gr.Markdown("✅ 아래 스프레드시트 또는 테이블이 자동으로 최신 상태로 유지됩니다.")

app.launch()
