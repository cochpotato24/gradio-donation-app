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

# 상태 저장
current_round = 1
# 각 라운드별 기부자 목록 저장
donors_by_round = {r: [] for r in range(1, TOTAL_ROUNDS+1)}

# 실시간 기부 함수
def donate(user_id, amount):
    global current_round
    # 모든 라운드 완료 시
    if current_round > TOTAL_ROUNDS:
        return "이미 모든 라운드가 완료되었습니다.", None

    # 중복 ID 방지 (현재 라운드)
    if any(d['id'] == user_id for d in donors_by_round[current_round]):
        return f"{user_id}님은 이미 {current_round}라운드에 참여하셨습니다.", None

    # 기부자 추가
    donors_by_round[current_round].append({"id": user_id, "기부금": amount})
    count = len(donors_by_round[current_round])

    # 다음 기부자 대기
    if count < NUM_PARTICIPANTS:
        return f"{user_id}님 기부 감사합니다! 아직 {NUM_PARTICIPANTS - count}명의 참여가 남았습니다 (라운드 {current_round}).", None

    # 라운드 완료: 계산 및 시트 기록
    total_donation = sum(d['기부금'] for d in donors_by_round[current_round])
    public_account = total_donation * 2
    public_per_person = public_account / NUM_PARTICIPANTS

    result_text = f"❤️ {current_round}라운드 최종 기부 결과 ❤️\n"
    for d in donors_by_round[current_round]:
        personal_account = 10000 - d['기부금']
        final_earning = personal_account + public_per_person
        response_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        # 구글 시트에 행 추가
        worksheet.append_row([
            current_round,
            d['id'],
            d['기부금'],
            personal_account,
            round(public_per_person, 3),
            round(final_earning, 3),
            response_time
        ])
        result_text += f"{d['id']}님의 최종수익: {int(final_earning)}원\n"

    # 다음 라운드로 이동
    current_round += 1
    return result_text, refresh_table()

# 결과 새로고침 함수
def refresh_results():
    # 전체 기록 가져오기
    records = worksheet.get_all_records()
    if not records:
        return "아직 기록된 결과가 없습니다.", None

    df = pd.DataFrame(records)
    text = "❤️ 라운드별 최종 기부 결과 ❤️\n"
    # 현 라운드 이전까지(완료된) 라운드 결과
    max_round = min(current_round - 1, TOTAL_ROUNDS)
    for r in range(1, max_round + 1):
        text += f"\n<{r}라운드>\n"
        sub = df[df['round'] == r]
        for _, row in sub.iterrows():
            text += f"{row['id']}님의 최종수익: {int(row['최종수익'])}원\n"

    return text, df

# 테이블 새로고침
def refresh_table():
    records = worksheet.get_all_records()
    df = pd.DataFrame(records)
    return df

# Gradio 인터페이스
with gr.Blocks() as app:
    gr.Markdown("## 🎁 기부 실험\n10000원 중 얼마를 기부하시겠습니까?")
    user_id = gr.Textbox(label="ID")
    amount = gr.Slider(0, 10000, step=500, label="기부 금액 (₩)")
    output_text = gr.Textbox(label="결과", lines=12)
    table = gr.Dataframe(
        headers=["round", "ID", "기부액", "개인계정", "공공계정", "최종수익", "응답시간"],
        datatype=["number", "str", "number", "number", "number", "number", "str"],
        interactive=False,
        row_count=NUM_PARTICIPANTS * TOTAL_ROUNDS
    )
    donate_btn = gr.Button("기부하기")
    refresh_btn = gr.Button("🔄 새로고침하여 결과 보기")

    donate_btn.click(donate, inputs=[user_id, amount], outputs=[output_text, table])
    refresh_btn.click(refresh_results, outputs=[output_text, table])

app.launch(server_name="0.0.0.0", server_port=10000)
