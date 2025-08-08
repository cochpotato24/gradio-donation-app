import gradio as gr
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import os
from datetime import datetime
import pandas as pd

# 인증 설정
scope = [
    'https://www.googleapis.com/auth/spreadsheets',
    'https://www.googleapis.com/auth/drive',
]
credentials = ServiceAccountCredentials.from_json_keyfile_name(
    '/etc/secrets/service_account.json', scope
)
gc = gspread.authorize(credentials)

# 스프레드시트 정보 및 헤더 자동 삽입
SPREADSHEET_NAME = os.environ['SPREADSHEET_NAME']
worksheet = gc.open(SPREADSHEET_NAME).sheet1
HEADER = ["round","ID","기부액","개인계정","공공계정","최종수익","응답시간"]
if worksheet.row_values(1) != HEADER:
    worksheet.insert_row(HEADER, index=1)

# 설정 값
NUM_PARTICIPANTS = 4  # 라운드당 참여자 수
TOTAL_ROUNDS = 3      # 총 라운드 수

# 전역 상태
current_round = 1
# 각 라운드별 참여자 기록 (ID, 기부금)
donors_by_round = {r: [] for r in range(1, TOTAL_ROUNDS+1)}

# 시트에서 전체 테이블 가져오기
def get_table_data():
    records = worksheet.get_all_records()
    df = pd.DataFrame(records)
    return df.values.tolist()

# 참여자 수 및 현재 라운드 계산 (전역 상태 사용)
def donate(user_id, amount):
    global current_round, donors_by_round
    table = get_table_data()

    # 이미 모든 라운드 완료
    if current_round > TOTAL_ROUNDS:
        return "모든 라운드가 완료되었습니다.", table, "실험 종료"

    # 중복 참여 방지
    if any(d['ID'] == user_id for d in donors_by_round[current_round]):
        return f"{user_id}님은 이미 {current_round}라운드에 참여하셨습니다.", table, f"현재 {current_round}라운드 참여 중"

    # 2~N라운드는 1라운드 참여자만 허용
    if current_round > 1:
        allowed = [d['ID'] for d in donors_by_round[1]]
        if user_id not in allowed:
            return (
                f"{user_id}님은 이 실험의 참여자가 아닙니다. 1라운드 참여자: {', '.join(allowed)}",
                table,
                f"현재 {current_round}라운드 참여 중"
            )

    # 기부 정보 저장
    donors_by_round[current_round].append({'ID': user_id, '기부액': amount})
    count = len(donors_by_round[current_round])

    # 참여 대기 안내
    if count < NUM_PARTICIPANTS:
        return (
            f"{user_id}님 기부 감사합니다! 아직 {NUM_PARTICIPANTS - count}명이 남았습니다 (라운드 {current_round}).",
            table,
            f"현재 {current_round}라운드 참여 중"
        )

    # 라운드 완료: 계산 및 시트 기록
    total_donation = sum(d['기부액'] for d in donors_by_round[current_round])
    public_account = total_donation * 2
    public_per_person = public_account / NUM_PARTICIPANTS

    result_text = f"❤️ {current_round}라운드 최종 기부 결과 ❤️\n"
    for d in donors_by_round[current_round]:
        personal_account = 10000 - d['기부액']
        final_earning = personal_account + public_per_person
        response_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        # 구글 시트에 기록
        worksheet.append_row([
            current_round,
            d['ID'],
            d['기부액'],
            personal_account,
            round(public_per_person, 3),
            round(final_earning, 3),
            response_time
        ])
        result_text += f"{d['ID']}님의 최종수익: {int(final_earning)}원\n"

    # 다음 라운드로 이동
    current_round += 1
    table = get_table_data()
    if current_round <= TOTAL_ROUNDS:
        round_msg = f"{current_round}라운드 참여하실 수 있습니다."
    else:
        round_msg = "모든 라운드가 완료되었습니다. 최종 결과를 확인하세요."

    return result_text, table, round_msg

# 결과 새로고침 함수
def refresh_results():
    table = get_table_data()
    # 완료된 라운드까지 결과 요약
    summary = "❤️ 라운드별 최종 기부 결과 ❤️\n"
    for r in range(1, min(current_round, TOTAL_ROUNDS+1)):
        summary += f"\n<{r}라운드>\n"
        for row in table:
            if row[0] == r:
                summary += f"{row[1]}님의 최종수익: {int(row[5])}원\n"

    if current_round > TOTAL_ROUNDS:
        round_msg = "실험 종료"
    else:
        round_msg = f"현재 {current_round}라운드 참여 중"

    return summary, table, round_msg

# Gradio 인터페이스 구성
with gr.Blocks() as app:
    gr.Markdown("## 🎁 기부 실험\n10000원 중 얼마를 기부하시겠습니까?")
    current_round_text = gr.Markdown(f"현재 {current_round}라운드 참여 중")
    user_id = gr.Textbox(label="ID")
    amount = gr.Slider(0, 10000, step=500, label="기부 금액 (₩)")
    output_text = gr.Textbox(label="결과", lines=12)
    table = gr.Dataframe(
        headers=HEADER,
        datatype=["number","str","number","number","number","number","str"],
        interactive=False,
        row_count=NUM_PARTICIPANTS * TOTAL_ROUNDS
    )

    donate_btn = gr.Button("기부하기")
    refresh_btn = gr.Button("🔄 새로고침하여 결과 보기")

    donate_btn.click(donate, inputs=[user_id, amount], outputs=[output_text, table, current_round_text])
    refresh_btn.click(refresh_results, outputs=[output_text, table, current_round_text])

app.launch(server_name="0.0.0.0", server_port=10000)
