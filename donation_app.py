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

# 스프레드시트 정보
SPREADSHEET_NAME = os.environ['SPREADSHEET_NAME']
worksheet = gc.open(SPREADSHEET_NAME).sheet1

# 설정 값
NUM_PARTICIPANTS = 4    # 참여자 수
TOTAL_ROUNDS = 3        # 총 라운드 수

# 상태 저장 초기화
def init_state():
    return {
        'current_round': 1,
        'donors_by_round': {r: [] for r in range(1, TOTAL_ROUNDS+1)}
    }

# 시트에서 테이블 데이터 가져오기
def get_table_data():
    records = worksheet.get_all_records()
    df = pd.DataFrame(records)
    return df.values.tolist()

# 실시간 기부 함수
def donate(user_id, amount, state):
    current_round = state['current_round']
    donors_by_round = state['donors_by_round']
    table = get_table_data()

    # 모든 라운드 완료 시
    if current_round > TOTAL_ROUNDS:
        text = "이미 모든 라운드가 완료되었습니다."
        round_msg = "실험 종료"
        return text, table, round_msg, state

    # 2라운드 이상 참여자 제한: 1라운드 참가자만
    if current_round > 1:
        allowed = [d['ID'] for d in donors_by_round[1]]
        if user_id not in allowed:
            text = f"{user_id}님은 해당 실험의 참여자가 아닙니다. 참가자는 {', '.join(allowed)} 입니다."
            round_msg = f"현재 {current_round}라운드 참여 중"
            return text, table, round_msg, state

    # 중복 ID 방지 (현재 라운드)
    if any(d['ID'] == user_id for d in donors_by_round[current_round]):
        text = f"{user_id}님은 이미 {current_round}라운드에 참여하셨습니다."
        round_msg = f"현재 {current_round}라운드 참여 중"
        return text, table, round_msg, state

    # 기부자 추가
    donors_by_round[current_round].append({'ID': user_id, '기부액': amount})
    count = len(donors_by_round[current_round])

    # 대기 안내
    if count < NUM_PARTICIPANTS:
        text = f"{user_id}님 기부 감사합니다! 아직 {NUM_PARTICIPANTS - count}명이 남았습니다 (라운드 {current_round})."
        round_msg = f"현재 {current_round}라운드 참여 중"
        return text, table, round_msg, state

    # 라운드 완료: 계산 및 시트 기록
    total_donation = sum(d['기부액'] for d in donors_by_round[current_round])
    public_account = total_donation * 2
    public_per_person = public_account / NUM_PARTICIPANTS

    text = f"❤️ {current_round}라운드 최종 기부 결과 ❤️\n"
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
        text += f"{d['ID']}님의 최종수익: {int(final_earning)}원\n"

    # 다음 라운드 준비
    state['current_round'] += 1
    next_round = state['current_round']
    if next_round <= TOTAL_ROUNDS:
        round_msg = f"{next_round}라운드 참여하실 수 있습니다."
    else:
        round_msg = "모든 라운드가 완료되었습니다. 최종 결과를 확인하세요."

    table = get_table_data()
    return text, table, round_msg, state

# 결과 새로고침 함수
def refresh_results(state):
    records = worksheet.get_all_records()
    if not records:
        text = "아직 기록된 결과가 없습니다."
        table = []
        round_msg = f"현재 {state['current_round']}라운드 참여 중"
        return text, table, round_msg

    df = pd.DataFrame(records)
    text = "❤️ 라운드별 최종 기부 결과 ❤️\n"
    max_round = min(state['current_round'] - 1, TOTAL_ROUNDS)
    for r in range(1, max_round + 1):
        text += f"\n<{r}라운드>\n"
        sub = df[df['round'] == r]
        for _, row in sub.iterrows():
            text += f"{row['ID']}님의 최종수익: {int(row['최종수익'])}원\n"
    table = get_table_data()
    round_msg = f"현재 {state['current_round']}라운드 참여 중"
    return text, table, round_msg

# Gradio 인터페이스
with gr.Blocks() as app:
    state = gr.State(init_state)
    gr.Markdown("## 🎁 기부 실험\n10000원 중 얼마를 기부하시겠습니까?")
    current_round_text = gr.Markdown(f"현재 1라운드 참여 중")
    user_id = gr.Textbox(label="ID")
    amount = gr.Slider(0, 10000, step=500, label="기부 금액 (₩)")
    output_text = gr.Textbox(label="결과", lines=12)
    table = gr.Dataframe(
        headers=["round","ID","기부액","개인계정","공공계정","최종수익","응답시간"],
        datatype=["number","str","number","number","number","number","str"],
        interactive=False,
        row_count=NUM_PARTICIPANTS * TOTAL_ROUNDS
    )

    donate_btn = gr.Button("기부하기")
    refresh_btn = gr.Button("🔄 새로고침하여 결과 보기")

    donate_btn.click(
        fn=donate,
        inputs=[user_id, amount, state],
        outputs=[output_text, table, current_round_text, state]
    )
    refresh_btn.click(
        fn=refresh_results,
        inputs=[state],
        outputs=[output_text, table, current_round_text]
    )

app.launch(server_name="0.0.0.0", server_port=10000)
