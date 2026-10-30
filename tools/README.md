# tools

## mk-fsck-bootimg.py

从 CI 产出的 `boot.img` 派生一个带强制 fsck 的版本，用于修复 rootfs 文件系统错误。

```bash
python3 tools/mk-fsck-bootimg.py <输入 boot.img> [输出目录]
```

产出：

| 文件 | 说明 |
|---|---|
| `boot_orig.img` | 输入镜像原样副本 |
| `boot_fsck.img` | 只把 cmdline 改成 `... audit=0 fsck.repair=yes fsck.mode=force slot_suffix=_a` |

### 原理

Android boot image (header v2) 的布局：

```
0       ANDROID! magic
8       10 个 u32: kernel_size, kernel_addr, ramdisk_size, ramdisk_addr,
                  second_size, second_addr, tags_addr, page_size,
                  header_version, os_version
48      name[16]
64      cmdline[512]          ← 只改这里
576     id[8]                 ← 不动（bootloader 不校验）
1648    dtb_size (v2)
1652    dtb_addr (v2, u64)
```

脚本只覆写 `cmdline[512]` 这一段字节，并把整段先清零再写入，
kernel / ramdisk / dtb 三段逐字节比对确认无改动。

### 安全校验

脚本内置以下检查，任一失败即非零退出：

- 新 cmdline 长度 < 512
- 输出文件大小与输入完全一致
- 回读 cmdline 与预期逐字符相等
- 差异字节全部落在 `64..576` 区间内
- kernel / ramdisk / dtb 三段与原始镜像完全一致
- 输入镜像的 cmdline 若已含 `fsck.repair=yes`，直接报错退出（防重复打补丁）

### 使用注意

`fsck.mode=force` 会在每次启动时强制检查 rootfs，**修完就该换回 `boot_orig.img`**，
否则每次开机都要跑一遍全盘 fsck，SD 卡上可能要好几分钟。
