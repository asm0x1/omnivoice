#!/usr/bin/env python3
import os
import time
from pathlib import Path

from omnivoice import OmniVoice
import soundfile as sf
import torch


def list_voices():
    """列出 voice_sample 目录下所有可用的声音"""
    voice_sample_path = Path("voice_sample")
    if not voice_sample_path.exists():
        return []

    voices = []
    for item in sorted(voice_sample_path.iterdir()):
        if item.is_dir():
            # 自动匹配：文件夹下第一个音频文件 + 第一个文本文件
            audio_files = list(item.glob("*.mp3")) + list(item.glob("*.wav")) + list(item.glob("*.flac"))
            text_files = list(item.glob("*.txt"))
            if audio_files:
                voices.append({
                    "name": item.name,
                    "audio": str(audio_files[0]),
                    "text": str(text_files[0]) if text_files else None,
                })
    return voices


def select_voice(voices):
    """让用户选择声音"""
    if not voices:
        print("没有找到可用的声音样本！")
        print("请在 voice_sample 目录下添加声音样本文件夹。")
        return None

    print("\n可用声音列表：")
    for i, voice in enumerate(voices, 1):
        print(f"  {i}. {voice['name']}")

    while True:
        try:
            choice = input("\n请选择声音编号 (1-{})：".format(len(voices)))
            idx = int(choice) - 1
            if 0 <= idx < len(voices):
                return voices[idx]
            print("无效选择，请重新输入。")
        except ValueError:
            print("请输入数字。")


def open_txt(file_path):
    """读取文件内容并返回字符串"""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            return f.read().strip()
    except Exception as e:
        print(f"读取文件失败: {e}")
        return ""


def main():
    import argparse
    parser = argparse.ArgumentParser(description="OmniVoice TTS")
    parser.add_argument("--device", default="cpu", help="Device: cpu, cuda:0, mps, auto")
    parser.add_argument("--text", "-t", help="Text to synthesize (skip interactive mode)")
    parser.add_argument("--voice", help="Voice folder name (use with --text)")
    parser.add_argument("--output", "-o", help="Output WAV file path (use with --text)")
    parser.add_argument("--language", help="Language, e.g. Chinese, English")
    parser.add_argument("--speed", type=float, default=1.0, help="Speaking speed (default: 1.0)")
    args = parser.parse_args()

    # Auto-detect device
    if args.device == "auto":
        if torch.cuda.is_available():
            device = "cuda:0"
        elif hasattr(torch.backends, 'mps') and torch.backends.mps.is_available():
            device = "mps"
        else:
            device = "cpu"
    else:
        device = args.device

    dtype = torch.float16 if device.startswith("cuda") or device == "mps" else torch.float32

    # Load model
    print(f"正在加载模型 (device={device}, dtype={dtype})...")
    model = OmniVoice.from_pretrained(
        "k2-fsa/OmniVoice",
        device_map=device,
        dtype=dtype
    )

    # Batch mode: --text + --voice
    if args.text and args.voice:
        voice_map = {v['name']: v for v in list_voices()}
        selected = voice_map.get(args.voice)
        if not selected:
            print(f"错误: 未找到声音 '{args.voice}'")
            print(f"可用声音: {list(voice_map.keys())}")
            return 1

        ref_text = open_txt(selected['text']) if selected['text'] else None
        print(f"使用声音: {selected['name']}")
        print(f"参考音频: {selected['audio']}")

        output_path = args.output or f"./outputs/{time.strftime('%Y%m%d%H%M%S', time.localtime())}.wav"
        print(f"正在生成语音...")
        audio = model.generate(
            text=args.text,
            ref_audio=selected['audio'],
            ref_text=ref_text,
            language=args.language,
            speed=args.speed,
        )
        sf.write(output_path, audio[0], 24000)
        print(f"语音生成完成，已保存到 {output_path}")
        return 0

    # Interactive mode
    voices = list_voices()
    selected = select_voice(voices)
    if not selected:
        return

    print(f"\n已选择: {selected['name']}")
    print(f"音频: {selected['audio']}")
    if selected['text']:
        ref_text = open_txt(selected['text'])
        print(f"文本: {ref_text}")
    else:
        ref_text = None
        print("文本: (将使用 Whisper 自动转录)")

    while True:
        print("\n" + "=" * 50)
        input_text = input("请输入要生成的文字 (输入 q 退出)：\n")
        if input_text.lower() == 'q':
            print("再见！")
            break

        if not input_text.strip():
            print("输入不能为空")
            continue

        print("正在生成语音，请稍候...")
        audio = model.generate(
            text=input_text,
            ref_audio=selected['audio'],
            ref_text=ref_text,
        )

        output_path = f"./outputs/{time.strftime('%Y%m%d%H%M%S', time.localtime())}.wav"
        sf.write(output_path, audio[0], 24000)
        print(f"语音生成完成，已保存到 {output_path}")


if __name__ == "__main__":
    main()