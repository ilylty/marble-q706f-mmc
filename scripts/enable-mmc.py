#!/usr/bin/env python3
"""
给 arch/arm64 config 开启 MMC / SDHCI 子系统。

背景：silime/ArchLinux-Packages 在 2026-07-19 的 "track silime 7.1" 提交里
把整个 MMC 子系统从 config 中丢掉了（`# CONFIG_MMC is not set`），
导致 TB-Q706F 的 SD 卡槽在 Linux 下完全不可见。

本脚本只做一件事：把 CONFIG_MMC* 系列打开，其余一个字节不动。
"""
import re
import sys

# 必须开启的符号（顺序按 Kconfig 依赖自顶向下）
WANT = {
    "CONFIG_MMC": "y",
    "CONFIG_MMC_BLOCK": "y",
    "CONFIG_MMC_BLOCK_MINORS": "8",
    "CONFIG_MMC_SDHCI": "y",
    "CONFIG_MMC_SDHCI_IO_ACCESSORS": "y",
    "CONFIG_MMC_SDHCI_PLTFM": "y",
    "CONFIG_MMC_SDHCI_MSM": "y",
    "CONFIG_MMC_CQHCI": "y",
}


def main(path: str) -> int:
    src = open(path, encoding="utf-8").read()
    before = re.search(r"(?m)^# CONFIG_MMC is not set$", src)
    if before is None:
        cur = re.search(r"(?m)^CONFIG_MMC=(.*)$", src)
        if cur and cur.group(1) == "y":
            print(f"[=] CONFIG_MMC 已经是 y，无需改动: {path}")
            return 0
        print(f"[!] 找不到 MMC 相关行，config 结构异常: {path}", file=sys.stderr)
        return 1

    for sym, val in WANT.items():
        # 删掉已有的赋值 / not set 行（避免 override warning）
        src = re.sub(rf"(?m)^(?:# )?{re.escape(sym)}(?: is not set)?=.*\n", "", src)
    src = src.rstrip("\n") + "\n"
    for sym, val in WANT.items():
        src += f"{sym}={val}\n"

    open(path, "w", encoding="utf-8").write(src)

    print(f"[+] 已开启 MMC 子系统: {path}")
    for sym, val in WANT.items():
        print(f"    {sym}={val}")
    return 0


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print(f"用法: {sys.argv[0]} <config 文件>", file=sys.stderr)
        raise SystemExit(2)
    raise SystemExit(main(sys.argv[1]))
