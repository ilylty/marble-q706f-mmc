#!/usr/bin/env bash
# 校验 CI 产物与自己写的 mkboot.py 生成的 boot.img 一致（防手工错误）
set -euo pipefail

img="${1:?boot.img path}"
test -f "$img"

python3 - "$img" <<'PY'
import struct, sys
p = sys.argv[1]
d = open(p, 'rb').read()
assert d[:8] == b'ANDROID!', "magic 不对"
hver = struct.unpack_from('<I', d, 40)[0]
psize = struct.unpack_from('<I', d, 36)[0]
ksz = struct.unpack_from('<I', d, 8)[0]
rsz = struct.unpack_from('<I', d, 16)[0]
hsz = struct.unpack_from('<I', d, 1644)[0]
dsz = struct.unpack_from('<I', d, 1648)[0]
raddr = struct.unpack_from('<Q', d, 1652)[0]
clen = len(d[64:576].split(b'\0')[0])
assert hver == 2, f"header_version={hver}"
assert psize == 0x1000, f"page_size={psize:#x}"
assert hsz == 1660, f"header_size={hsz}"
assert raddr == 0x1f00000, f"dtb_addr={raddr:#x}"
assert dsz > 0 and ksz > 0 and rsz > 0, "段长度为 0"
# dtb 段 magic 检查
def npg(n): return (n + psize - 1) // psize
off = npg(hsz) * psize + npg(ksz) * psize + npg(rsz) * psize
assert d[off:off + 4] == b'\xd0\x0d\xfe\xed', f"dtb magic 异常: {d[off:off+4].hex()}"
model = b''
i = d.find(b'Lenovo', off, off + dsz)
if i > 0:
    model = d[i:i+40].split(b'\0')[0]
print(f"  header_version={hver} page_size={psize:#x} header_size={hsz}")
print(f"  kernel={ksz} ramdisk={rsz} dtb={dsz} dtb_addr={raddr:#x}")
print(f"  cmdline({clen}): {d[64:64+clen].decode(errors='replace')}")
print(f"  dtb model: {model.decode(errors='replace')}")
print("  [OK] boot.img 结构校验通过")
PY
