"""Optional live model connectivity check using a fixed, non-sensitive prompt."""
import argparse
from dataclasses import replace

from app.model_provider import CompatibleChatProvider, ModelConfig, ModelError


def main(argv=None):
    parser = argparse.ArgumentParser(description="Check configured AI connectivity with one short paid request.")
    parser.add_argument("--run", action="store_true", help="send one real request")
    args = parser.parse_args(argv)
    if not args.run:
        print("未发送请求。使用 --run 执行一次真实连通检查。")
        return 0
    try:
        config = ModelConfig.from_environment()
        config = replace(config, max_output_tokens=min(config.max_output_tokens, 128))
        CompatibleChatProvider(config).generate_chat([{"role": "user", "content": "请简短回复：连接正常。"}])
    except ModelError as exc:
        print(f"AI 连通检查失败：{exc.code}")
        return 1
    print("AI 连通检查成功，已收到非空回复。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
