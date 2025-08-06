import gradio as gr
import pandas as pd
from datetime import datetime
import os

GOOGLE_SHEET_PATH = "donation_log.csv"
REQUIRED_PARTICIPANTS = 3

# 최초 파일이 없다면 생성
if not os.path.exists(GOOGLE_SHEET_PATH):
    df = pd.DataFrame(columns=["이름", "기부액", "개인계정", "공공계정", "최종수익", "응답시간"])
    df.to_csv(GOOGLE_SHEET_PATH, index=False)

def 기부응답처리(name, donation):
    df = pd.read_csv(GOOGLE_SHEET_PATH)

    personal_amount = 10000 - donation
    public_amount = df["기부액"].sum() + donation
    total_profit = personal_amount + public_amount

    new_row = {
        "이름": name,
        "기부액": donation,
        "개인계정": personal_amount,
        "공공계정": public_amount,
        "최종수익": total_profit,
        "응답시간": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    }

    df = pd.concat([df, pd.DataFrame([new_row])], ignore_index=True)
    df.to_csv(GOOGLE_SHEET_PATH, index=False)

    if len(df) >= REQUIRED_PARTICIPANTS:
        # 모든 참여자에게 각자의 최종수익 결과 보여줌
        result_text = f"{name}님, 당신의 최종수익은 {int(total_profit):,}원입니다."
    else:
        result_text = f"{name}님, 응답이 저장되었습니다. 총 {REQUIRED_PARTICIPANTS}명이 참여해야 결과가 공개됩니다. (현재: {len(df)}명)"

    return result_text, df

# Gradio 인터페이스 구성
name_input = gr.Textbox(label="이름")
donation_slider = gr.Slider(minimum=0, maximum=10000, step=100, label="기부액 (원)")

app = gr.Interface(
    fn=기부응답처리,
    inputs=[name_input, donation_slider],
    outputs=["text", "dataframe"],
    title="10,000원 중 얼마를 기부하시겠습니까?",
    description="응답은 0~10,000 사이 숫자로 입력하세요."
)

if __name__ == "__main__":
    app.launch(server_name="0.0.0.0", server_port=10000)
