#!/usr/bin/env python3
"""
把 kernel Image + 原版 ramdisk + DTB 打回 Android boot.img (header v2)。

设计：**以出厂 header 为模板**，只覆盖长度/cmdline 这类必然变化的字段，
其余（second_addr、id、os_version、各段地址）全部原样保留。
这样生成的镜像与出厂 boot.img 除了必要的字段外逐字节一致，最大程度降低
bootloader 拒收的风险（q706f 是 secure boot 机型，对 header 结构敏感）。

用法:
  mkboot.py <header-template.bin> <kernel> <ramdisk> <dtb> <cmdline> <out.img>
"""
import struct
import sys

PAGE = 0x1000


def pad(data: bytes) -> bytes:
    rem = len(data) % PAGE
    return data + b"\0" * (PAGE - rem) if rem else data


def main() -> int:
    if len(sys.argv) != 7:
        print(__doc__, file=sys.stderr)
        return 2
    tpl_path, kernel_path, ramdisk_path, dtb_path, cmdline, out_path = sys.argv[1:]

    tpl = open(tpl_path, "rb").read()
    kernel = open(kernel_path, "rb").read()
    ramdisk = open(ramdisk_path, "rb").read()
    dtb = open(dtb_path, "rb").read()
    cmd = cmdline.encode()

    dtb_size = len(dtb)  # 记录真实长度，稍后才补齐存储

    assert tpl[:8] == b"ANDROID!", "模板不是 boot image"
    assert struct.unpack_from("<I", tpl, 40)[0] == 2, "模板不是 header v2"
    assert len(cmd) < 512, f"cmdline 太长: {len(cmd)}"

    hdr = bytearray(tpl)

    # 只有这些字段必须随内容更新
    struct.pack_into("<I", hdr, 8, len(kernel))    # kernel_size
    struct.pack_into("<I", hdr, 16, len(ramdisk))  # ramdisk_size
    struct.pack_into("<I", hdr, 1648, dtb_size)    # dtb_size
    hdr[64:576] = cmd.ljust(512, b"\0")            # cmdline

    # name 段留作可追溯标记（不影响校验）
    hdr[48:64] = b"q706f-mmc"[:16].ljust(16, b"\0")

    img = pad(bytes(hdr)) + pad(kernel) + pad(ramdisk) + pad(dtb)  # dtb 仅存储时补齐
    open(out_path, "wb").write(img)

    f = struct.unpack_from("<10I", hdr, 8)
    print(f"[+] 输出: {out_path}  ({len(img)} bytes)")
    print(f"    kernel_size = {f[0]}   kernel_addr = {f[1]:#x}")
    print(f"    ramdisk_size= {f[2]}   ramdisk_addr= {f[3]:#x}")
    print(f"    second_size = {f[4]}   second_addr = {f[5]:#x}  (沿用模板)")
    print(f"    tags_addr   = {f[6]:#x}  page_size   = {f[7]:#x}")
    print(f"    hdr_version = {f[8]}   os_version  = {f[9]:#x}")
    print(f"    dtb_size    = {dtb_size}")
    print(f"    cmdline({len(cmd)}): {cmdline}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
