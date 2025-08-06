import gradio as gr
import pandas as pd
import os
from datetime import datetime

# 참여자 수 기준 설정 (필요 시 이 숫자만 수정)
REQUIRED_PARTICIPANTS = 3

donation_log_path = "donation_log.csv"

def donate(name, donation_amount):
    # 새로 참여한 사람의 기부 데이터를 초기화
    new_entry = {
        "이름": name,
        "기부액": donation_amount,
        "개인계정": 10000 - donation_amount,
        "공공계정": 0,
        "최종수익": 0,
        "응답시간": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    }

    # 기존 기록 불러오기 또는 새로 생성
    if os.path.exists(donation_log_path):
        df = pd.read_csv(donation_log_path)
    else:
        df = pd.DataFrame(columns=["이름", "기부액", "개인계정", "공공계정", "최종수익", "응답시간"])

    # 새로운 응답 추가
    df = pd.concat([df, pd.DataFrame([new_entry])], ignore_index=True)

    # 아직 참여자 수 부족 → 저장만 하고 안내 메시지 출력
    if len(df) < REQUIRED_PARTICIPANTS:
        df.to_csv(donation_log_path, index=False)
        return f"{name}님, 응답이 저장되었습니다. 총 {REQUIRED_PARTICIPANTS}명이 참여해야 결과가 공개됩니다. (현재: {len(df)}명)", df

    # 참여자 수 도달 → 공공계정 및 최종수익 계산
    total_donation = df["기부액"].sum()
    public_account = (total_donation * 2) / REQUIRED_PARTICIPANTS

    df["공공계정"] = public_account
    df["최종수익"] = df["개인계정"] + df["공공계정"]

    # 결과 저장 및 각자에게 최종수익 안내 메시지
    df.to_csv(donation_log_path, index=False)
    result_message = df[df["이름"] == name]["최종수익"].values[0]
    return f"{name}님, 당신의 최종수익은 {int(result_message)}원입니다.", df

# Gradio UI 구성
with gr.Blocks() as demo:
    gr.Markdown("🪙 **10,000원 중 얼마를 기부하시겠습니까?**")
    gr.Markdown("🔴 응답은 0~10,000 사이 숫자로 입력하세요.")

    with gr.Row():
        name = gr.Textbox(label="이름")
        donation_amount = gr.Slider(0, 10000, step=100, label="기부액 (원)", value=5000)

    submit_btn = gr.Button("응답 제출")
    result_text = gr.Textbox(label="결과")

    with gr.Accordion("📊 응답 로그 보기", open=False):
        log_view = gr.Dataframe(headers=["이름", "기부액", "개인계정", "공공계정", "최종수익", "응답시간"])

    submit_btn.click(fn=donate, inputs=[name, donation_amount], outputs=[result_text, log_view])

# 실행
if __name__ == "__main__":
    demo.launch()
