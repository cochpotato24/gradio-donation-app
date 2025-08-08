import gradio as gr
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import os
from datetime import datetime
import pandas as pd

# ─────────────────────────────────────────
# Google Sheets 인증
# ─────────────────────────────────────────
scope = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]
credentials = ServiceAccountCredentials.from_json_keyfile_name(
    "/etc/secrets/service_account.json", scope
)
gc = gspread.authorize(credentials)

# 스프레드시트 & 헤더
SPREADSHEET_NAME = os.environ["SPREADSHEET_NAME"]
worksheet = gc.open(SPREADSHEET_NAME).sheet1
HEADER = ["round", "ID", "기부액", "개인계정", "공공계정", "최종수익", "응답시간"]
if worksheet.row_values(1) != HEADER:
    worksheet.insert_row(HEADER, index=1)

# ─────────────────────────────────────────
# 실험 파라미터
# ─────────────────────────────────────────
NUM_PARTICIPANTS = 4     # 라운드당 인원
TOTAL_ROUNDS = 3         # 총 라운드 수
AUTO_RESET_ON_FINISH = True  # 모든 라운드 완료 후 다음 입력이 오면 자동 리셋

# ─────────────────────────────────────────
# 전역 상태
# ─────────────────────────────────────────
def _new_state():
    """라운드별 기부 임시 보관용 상태 초기화"""
    return {r: [] for r in range(1, TOTAL_ROUNDS + 1)}

current_round = 1
donors_by_round = _new_state()

# ─────────────────────────────────────────
# 유틸
# ─────────────────────────────────────────
def get_table_data():
    """시트 전체를 DataFrame -> list[list]로 반환(그리디오 테이블에 쓰기 용)"""
    records = worksheet.get_all_records()  # header 기반 dict 리스트
    if not records:
        return []
    df = pd.DataFrame(records)
    return df.values.tolist()

def reset_state():
    """새 세션 시작(전역 상태 초기화)"""
    global current_round, donors_by_round
    current_round = 1
    donors_by_round = _new_state()

def latest_session_summary():
    """
    '최근 세션'의 라운드별 결과 요약 문자열 생성.
    - 최근 세션 = 시트의 마지막 (TOTAL_ROUNDS*NUM_PARTICIPANTS) 행 블록
    - 미완성 세션이면 있는 라운드만 요약
    """
    block_size = TOTAL_ROUNDS * NUM_PARTICIPANTS
    records = worksheet.get_all_records()
    if not records:
        return "아직 기록이 없습니다."

    # 최근 블록(완성/미완성 포함)
    last_block = records[-block_size:] if len(records) >= block_size else records[:]

    # round별 묶기
    by_round = {}
    for row in last_block:
        r = row.get("round")
        if isinstance(r, int):
            by_round.setdefault(r, []).append(row)

    # 정렬된 라운드 순서로 요약
    summary = "❤️ 최근 세션 라운드별 최종 기부 결과 ❤️\n"
    for r in sorted(by_round.keys()):
        summary += f"\n<{r}라운드>\n"
        for row in by_round[r]:
            try:
                final_earning = int(float(row["최종수익"]))
            except Exception:
                final_earning = row["최종수익"]
            summary += f"{row['ID']}님의 최종수익: {final_earning}원\n"
    return summary

# ─────────────────────────────────────────
# 핵심 로직
# ─────────────────────────────────────────
def donate(user_id, amount):
    global current_round, donors_by_round

    # 모든 라운드 완료 상태에서 자동 리셋 옵션이면 새 세션으로 초기화
    if current_round > TOTAL_ROUNDS:
        if AUTO_RESET_ON_FINISH:
            reset_state()
        else:
            table = get_table_data()
            return (
                "모든 라운드가 완료되었습니다. '🔁 새 실험 시작(Reset)' 버튼으로 새 세션을 시작하세요.",
                table,
                "실험 종료",
            )

    table = get_table_data()

    # ID 중복 방지(해당 라운드에 이미 참여했는지)
    if any(d["ID"] == user_id for d in donors_by_round[current_round]):
        return (
            f"{user_id}님은 이미 {current_round}라운드에 참여하셨습니다.",
            table,
            f"현재 {current_round}라운드 참여 중",
        )

    # 2~N 라운드는 1라운드 참여자만 허용
    if current_round > 1:
        allowed = [d["ID"] for d in donors_by_round[1]]
        if user_id not in allowed:
            return (
                f"{user_id}님은 이 실험의 참여자가 아닙니다. 1라운드 참여자: {', '.join(allowed)}",
                table,
                f"현재 {current_round}라운드 참여 중",
            )

    # 기부 저장
    donors_by_round[current_round].append({"ID": user_id, "기부액": amount})
    count = len(donors_by_round[current_round])

    # 참여 대기
    if count < NUM_PARTICIPANTS:
        return (
            f"{user_id}님 기부 감사합니다! 아직 {NUM_PARTICIPANTS - count}명이 남았습니다 (라운드 {current_round}).",
            table,
            f"현재 {current_round}라운드 참여 중",
        )

    # 라운드 완료 → 계산 & 시트 기록
    total_donation = sum(d["기부액"] for d in donors_by_round[current_round])
    public_account = total_donation * 2
    public_per_person = public_account / NUM_PARTICIPANTS

    result_text = f"❤️ {current_round}라운드 최종 기부 결과 ❤️\n"
    for d in donors_by_round[current_round]:
        personal_account = 10000 - d["기부액"]
        final_earning = personal_account + public_per_person
        response_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        worksheet.append_row(
            [
                current_round,
                d["ID"],
                d["기부액"],
                personal_account,
                round(public_per_person, 3),
                round(final_earning, 3),
                response_time,
            ]
        )
        result_text += f"{d['ID']}님의 최종수익: {int(final_earning)}원\n"

    # 다음 라운드로
    current_round += 1
    table = get_table_data()
    if current_round <= TOTAL_ROUNDS:
        round_msg = f"{current_round}라운드 참여하실 수 있습니다."
    else:
        round_msg = "모든 라운드가 완료되었습니다. 다음 입력 시 새 세션을 시작합니다." if AUTO_RESET_ON_FINISH \
                    else "모든 라운드 완료. 'Reset' 버튼으로 새 세션을 시작하세요."

    return result_text, table, round_msg

def refresh_results():
    table = get_table_data()
    summary = latest_session_summary()
    if current_round > TOTAL_ROUNDS:
        round_msg = "실험 종료(완료됨)"
    else:
        round_msg = f"현재 {current_round}라운드 참여 중"
    return summary, table, round_msg

def reset_experiment():
    reset_state()
    table = get_table_data()
    return "새 세션을 시작했습니다. 1라운드부터 참여하세요.", table, f"현재 {current_round}라운드 참여 중"

# ─────────────────────────────────────────
# Gradio UI
# ─────────────────────────────────────────
with gr.Blocks() as app:
    gr.Markdown("## 🎁 기부 실험\n10000원 중 얼마를 기부하시겠습니까?")
    current_round_text = gr.Markdown(f"현재 {current_round}라운드 참여 중")

    with gr.Row():
        user_id = gr.Textbox(label="ID", scale=2)
        amount = gr.Slider(0, 10000, step=500, label="기부 금액 (₩)", value=0, scale=3)

    output_text = gr.Textbox(label="결과", lines=12)
    table = gr.Dataframe(
        headers=HEADER,
        datatype=["number", "str", "number", "number", "number", "number", "str"],
        interactive=False,
        row_count=NUM_PARTICIPANTS * TOTAL_ROUNDS,
    )

    with gr.Row():
        donate_btn = gr.Button("기부하기", variant="primary")
        refresh_btn = gr.Button("🔄 새로고침하여 결과 보기")
        reset_btn = gr.Button("🔁 새 실험 시작(Reset)", variant="secondary")

    donate_btn.click(donate, inputs=[user_id, amount], outputs=[output_text, table, current_round_text])
    refresh_btn.click(refresh_results, outputs=[output_text, table, current_round_text])
    reset_btn.click(reset_experiment, outputs=[output_text, table, current_round_text])

app.launch(server_name="0.0.0.0", server_port=10000)
