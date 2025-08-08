import os
from datetime import datetime
import pandas as pd
import gradio as gr
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from gspread.exceptions import WorksheetNotFound

# -----------------------------
# 1) Google Sheets 인증
# -----------------------------
scope = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]
credentials = ServiceAccountCredentials.from_json_keyfile_name(
    "/etc/secrets/service_account.json", scope
)
gc = gspread.authorize(credentials)

SPREADSHEET_NAME = os.environ["SPREADSHEET_NAME"]
spreadsheet = gc.open(SPREADSHEET_NAME)
worksheet = spreadsheet.sheet1

HEADER_BASE = ["round", "ID", "기부액", "개인계정", "공공계정", "최종수익", "응답시간"]
FULL_HEADER = HEADER_BASE + ["세션"]

def ensure_headers():
    header = worksheet.row_values(1)
    if not header:
        worksheet.insert_row(FULL_HEADER, index=1)
        return
    if "세션" not in header:
        # 이건 여전히 안전하게 동작합니다.
        worksheet.update_cell(1, len(header) + 1, "세션")

ensure_headers()

# -----------------------------
# 2) 세션 관리 (Meta 시트)
# -----------------------------
def get_or_create_meta():
    try:
        meta = spreadsheet.worksheet("Meta")
    except WorksheetNotFound:
        meta = spreadsheet.add_worksheet(title="Meta", rows=10, cols=2)
        # *** 변경: update(values=..., range_name=...) 사용 ***
        meta.update(values=[["CURRENT_SESSION"]], range_name="A1")
        meta.update(values=[[datetime.now().strftime("%Y%m%d-%H%M%S")]], range_name="B1")
    return meta

meta_ws = get_or_create_meta()

def get_current_session_id():
    sid = meta_ws.acell("B1").value
    if not sid:
        sid = datetime.now().strftime("%Y%m%d-%H%M%S")
        # *** 변경: update(values=..., range_name=...) 사용 ***
        meta_ws.update(values=[["CURRENT_SESSION", sid]], range_name="A1:B1")
    return sid

def set_new_session_id():
    new_id = datetime.now().strftime("%Y%m%d-%H%M%S")
    # *** 변경: update(values=..., range_name=...) 사용 ***
    meta_ws.update(values=[["CURRENT_SESSION", new_id]], range_name="A1:B1")
    return new_id

SESSION_ID = get_current_session_id()

# -----------------------------
# 3) 실험 설정 & 상태
# -----------------------------
NUM_PARTICIPANTS = 4
TOTAL_ROUNDS = 3

current_round = 1
donors_by_round = {r: [] for r in range(1, TOTAL_ROUNDS + 1)}

# -----------------------------
# 4) 시트 I/O (현재 세션만)
# -----------------------------
def get_table_df():
    records = worksheet.get_all_records()
    if not records:
        return pd.DataFrame(columns=FULL_HEADER)

    df = pd.DataFrame(records)
    if "세션" not in df.columns:
        return pd.DataFrame(columns=FULL_HEADER)

    df = df[df["세션"] == SESSION_ID].copy()

    for col in ["round", "기부액", "개인계정", "공공계정", "최종수익"]:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")
    if "응답시간" in df.columns:
        df["응답시간"] = df["응답시간"].astype(str)

    df = df.sort_values(by=["round", "응답시간"], ignore_index=True)
    return df

def get_table_data():
    df = get_table_df()
    if "세션" in df.columns:
        df = df[HEADER_BASE]
    return df.values.tolist()

def append_row_for_session(row_values):
    worksheet.append_row(row_values + [SESSION_ID])

# -----------------------------
# 5) 시트 → 앱 상태 복구 (앱 시작 시 자동 실행)
# -----------------------------
def rebuild_state_from_sheet():
    global current_round, donors_by_round
    df = get_table_df()
    donors_by_round = {r: [] for r in range(1, TOTAL_ROUNDS + 1)}
    current_round = 1
    if df.empty:
        return
    last_round = int(df["round"].max())
    counts = df.groupby("round")["ID"].count().to_dict()
    if counts.get(last_round, 0) < NUM_PARTICIPANTS:
        current_round = last_round
        sub = df[df["round"] == last_round]
        for _, row in sub.iterrows():
            donors_by_round[last_round].append({"ID": row["ID"], "기부액": float(row["기부액"])})
    else:
        current_round = last_round + 1 if last_round < TOTAL_ROUNDS else TOTAL_ROUNDS + 1

rebuild_state_from_sheet()

# -----------------------------
# 6) 상태 텍스트
# -----------------------------
def round_status_text():
    return "실험 종료" if current_round > TOTAL_ROUNDS else f"현재 {current_round}라운드 참여 중"

def session_status_text():
    return f"현재 세션: **{SESSION_ID}**"

# -----------------------------
# 7) 자동 새 세션 시작(완주 후 다음 사용자 진입 시)
# -----------------------------
def _auto_start_new_session():
    global SESSION_ID, current_round, donors_by_round
    SESSION_ID = set_new_session_id()
    current_round = 1
    donors_by_round = {r: [] for r in range(1, TOTAL_ROUNDS + 1)}

# -----------------------------
# 8) donate (자동 롤링 포함, 동기화 버튼 제거)
# -----------------------------
def donate(user_id, amount):
    global current_round, donors_by_round, SESSION_ID

    # 이전 실험 완주된 상태면 다음 사용자 진입 시 자동 새 세션 시작
    if current_round > TOTAL_ROUNDS:
        _auto_start_new_session()

    # 2~N 라운드는 1라운드 참여자만 허용
    if current_round > 1:
        allowed = [d["ID"] for d in donors_by_round[1]]
        if user_id not in allowed:
            return (
                f"{user_id}님은 이 실험의 참여자가 아닙니다. 1라운드 참여자: {', '.join(allowed)}",
                get_table_data(),
                round_status_text(),
                session_status_text(),
            )

    # 해당 라운드 중복 참여 방지
    if any(d["ID"] == user_id for d in donors_by_round[current_round]):
        return (
            f"{user_id}님은 이미 {current_round}라운드에 참여하셨습니다.",
            get_table_data(),
            round_status_text(),
            session_status_text(),
        )

    # 임시 저장
    donors_by_round[current_round].append({"ID": user_id, "기부액": amount})
    count = len(donors_by_round[current_round])

    if count < NUM_PARTICIPANTS:
        return (
            f"{user_id}님 기부 감사합니다! 아직 {NUM_PARTICIPANTS - count}명이 남았습니다 (라운드 {current_round}).",
            get_table_data(),
            round_status_text(),
            session_status_text(),
        )

    # 라운드 마감: 계산 및 시트 기록
    total_donation = sum(d["기부액"] for d in donors_by_round[current_round])
    public_account = total_donation * 2
    public_per_person = public_account / NUM_PARTICIPANTS

    result_text = f"❤️ {current_round}라운드 최종 기부 결과 ❤️\n"
    for d in donors_by_round[current_round]:
        personal = 10000 - d["기부액"]
        final = personal + public_per_person
        ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        append_row_for_session([
            current_round, d["ID"], d["기부액"], personal,
            round(public_per_person, 3), round(final, 3), ts
        ])
        result_text += f"{d['ID']}님의 최종수익: {int(final)}원\n"

    # 다음 라운드 or 완주
    current_round += 1
    return result_text, get_table_data(), round_status_text(), session_status_text()

def refresh_results():
    df = get_table_df()
    table = get_table_data()
    summary = "❤️ 라운드별 최종 기부 결과 (현재 세션) ❤️\n"
    if not df.empty:
        for r in sorted(df["round"].unique()):
            summary += f"\n<{int(r)}라운드>\n"
            for _, row in df[df["round"] == r].iterrows():
                summary += f"{row['ID']}님의 최종수익: {int(row['최종수익'])}원\n"
    return summary, table, round_status_text(), session_status_text()

# -----------------------------
# 9) Gradio UI (동기화 버튼 없음)
# -----------------------------
with gr.Blocks() as app:
    gr.Markdown("## 🎁 기부 실험\n10000원 중 얼마를 기부하시겠습니까?")
    current_round_text = gr.Markdown(round_status_text())
    current_session_text = gr.Markdown(session_status_text())

    with gr.Row():
        user_id = gr.Textbox(label="ID", placeholder="예: 홍길동")
        amount = gr.Slider(0, 10000, step=500, label="기부 금액 (₩)", value=0)

    output_text = gr.Textbox(label="결과", lines=12)
    table = gr.Dataframe(
        headers=HEADER_BASE,
        datatype=["number", "str", "number", "number", "number", "number", "str"],
        interactive=False,
        row_count=NUM_PARTICIPANTS * TOTAL_ROUNDS,
    )

    with gr.Row():
        donate_btn = gr.Button("기부하기", variant="primary")
        refresh_btn = gr.Button("🔄 새로고침하여 결과 보기")

    donate_btn.click(
        donate,
        inputs=[user_id, amount],
        outputs=[output_text, table, current_round_text, current_session_text],
    )
    refresh_btn.click(
        refresh_results,
        outputs=[output_text, table, current_round_text, current_session_text],
    )

app.launch(server_name="0.0.0.0", server_port=10000)
