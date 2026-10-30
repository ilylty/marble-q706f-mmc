#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
从 boot_orig.img 派生 boot_fsck.img
只改 cmdline：在 audit=0 后面插入 fsck.repair=yes fsck.mode=force
其余所有字节（kernel/ramdisk/dtb/带 id）原样保留。
"""
import hashlib
import os
import shutil
import struct
import sys

#
# 用法:
#   python3 tools/mk-fsck-bootimg.py <输入 boot.img> [输出目录]
#
# 产出同目录下:
#   boot_orig.img   —— 输入原样副本
#   boot_fsck.img   —— 仅 cmdline 加 fsck.repair=yes fsck.mode=force
#
import argparse

CMDLINE_OFF = 64
CMDLINE_LEN = 512

OLD = "audit=0 slot_suffix="
INSERT = "fsck.repair=yes fsck.mode=force "


def sha(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def main():
    ap = argparse.ArgumentParser(description="从 boot.img 派生带 fsck 的 boot_fsck.img")
    ap.add_argument("src", help="输入 boot.img")
    ap.add_argument("outdir", nargs="?", default=None, help="输出目录（默认与输入同目录）")
    args = ap.parse_args()

    global DST_ORIG, DST_FSCK, NEW
    src = os.path.abspath(args.src)
    outdir = args.outdir or os.path.dirname(src)
    os.makedirs(outdir, exist_ok=True)
    DST_ORIG = os.path.join(outdir, "boot_orig.img")
    DST_FSCK = os.path.join(outdir, "boot_fsck.img")

    if not os.path.exists(DST_ORIG):
        shutil.copy2(src, DST_ORIG)
        print(f"已建立 boot_orig.img (副本)   sha256={sha(DST_ORIG)}")
    else:
        print(f"boot_orig.img 已存在           sha256={sha(DST_ORIG)}")

    d = bytearray(open(DST_ORIG, "rb").read())

    # --- 读现有 cmdline ---
    cur = bytes(d[CMDLINE_OFF:CMDLINE_OFF + CMDLINE_LEN]).split(b"\0")[0].decode()
    print(f"\n原 cmdline ({len(cur)} 字符):")
    print(f"  {cur}")

    if "fsck.repair=yes" in cur:
        print("\n!! cmdline 已含 fsck.repair，本镜像已打过补丁")
        sys.exit(1)

    if "audit=0 " not in cur:
        print(f"\n!! 警告: cmdline 里找不到 'audit=0 '，将追加到末尾")
        new = cur.rstrip() + " " + INSERT.strip()
    elif "slot_suffix=" in cur:
        new = cur.replace("slot_suffix=", INSERT + "slot_suffix=", 1)
    else:
        new = cur.rstrip() + " " + INSERT.strip()
    NEW = new
    nb = new.encode()
    if len(nb) >= CMDLINE_LEN:
        sys.exit(f"cmdline 过长: {len(nb)} >= {CMDLINE_LEN}")
    print(f"\n新 cmdline ({len(nb)} 字符, 上限 {CMDLINE_LEN-1}):")
    print(f"  {new}")

    # --- 写入（整段清零后再写，避免残留旧内容）---
    d[CMDLINE_OFF:CMDLINE_OFF + CMDLINE_LEN] = b"\0" * CMDLINE_LEN
    d[CMDLINE_OFF:CMDLINE_OFF + len(nb)] = nb

    open(DST_FSCK, "wb").write(bytes(d))
    print(f"\n已写出 boot_fsck.img  {len(d)} 字节")

    # --- 用相同长度保证 ---
    if len(open(DST_FSCK, "rb").read()) != os.path.getsize(DST_ORIG):
        sys.exit("!! 输出文件长度与原文件不一致，逻辑错误")

    # --- 反读验证 ---
    v = open(DST_FSCK, "rb").read()
    got = v[CMDLINE_OFF:CMDLINE_OFF + CMDLINE_LEN].split(b"\0")[0].decode()
    print(f"\n回读 cmdline: {got}")
    assert got == new, "回读不一致！"

    # --- 确认除 cmdline 外无其他差异 ---
    a = open(DST_ORIG, "rb").read()
    b = v
    assert len(a) == len(b)
    diffs = [i for i in range(len(a)) if a[i] != b[i]]
    in_range = all(CMDLINE_OFF <= i < CMDLINE_OFF + CMDLINE_LEN for i in diffs)
    print(f"\n差异字节数: {len(diffs)}  范围 {min(diffs)}..{max(diffs)}  "
          f"{'✓ 全部落在 cmdline 区内' if in_range else '✗ 有越界差异！'}")
    if not in_range:
        sys.exit(1)

    # --- 校验 kernel/ramdisk/dtb 段完好 ---
    pages = struct.unpack_from('<I', d, 8 + 7 * 4)[0]
    ks = struct.unpack_from('<I', d, 8)[0]
    rs = struct.unpack_from('<I', d, 8 + 2 * 4)[0]
    dtbs = struct.unpack_from('<I', d, 1648)[0]
    np = lambda n: (n + pages - 1) // pages
    o1 = pages
    o2 = o1 + np(ks) * pages
    o3 = o2 + np(rs) * pages
    o4 = o3 + np(0) * pages
    for nm, off, ln in (("kernel", o1, ks), ("ramdisk", o2, rs), ("dtb", o4, dtbs)):
        same = a[off:off + ln] == b[off:off + ln]
        print(f"  {nm:8s} @{off:>9} {ln:>9}B  一致={same}")

    print(f"\nboot_orig.img  sha256={sha(DST_ORIG)}")
    print(f"boot_fsck.img  sha256={sha(DST_FSCK)}")


if __name__ == "__main__":
    main()
