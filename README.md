# marble-q706f-mmc

给 **Lenovo Xiaoxin Pad Pro 12.6 / Tab P12 Pro (TB-Q706F, SM8250-AC 骁龙870)**
用的 mainline Linux 内核 CI 构建，唯一目的是**修复 SD 卡不可见**。

## 问题

`silime/ArchLinux-Packages` 于 **2026-07-19** 的提交 `46db6581`
（"linux-sm8250: track silime 7.1 and generate boot image"）中，
配置出现了回归：

```diff
- CONFIG_MMC=y
- CONFIG_MMC_BLOCK=y
- CONFIG_MMC_SDHCI=y
- CONFIG_MMC_SDHCI_MSM=y
+ # CONFIG_MMC is not set
```

后果：内核里**整个 MMC 子系统不存在**，SD 卡槽完全不可见，
`sdhci-msm` 驱动不会 probe，`/dev/mmcblk*` 永不出现。

而 `ArchlinuxARM-qcom-aarch64/devices.yaml` 里 q706f 仍写着
`SDCARD_IMAGE: true` —— 上游配置与实际能力自相矛盾。

### 证据

| 检查 | 结果 |
|---|---|
| `config` 第 6100 行 | `# CONFIG_MMC is not set` |
| 解压 `Image` 后 `strings \| grep mmcblk` | 0 次 |
| 解压 `Image` 后 `strings \| grep sdhci` | 0 次 |
| initramfs 内模块 | 仅 `uas.ko` / `usb-storage.ko` / `hid-generic.ko` |
| DTB `sm8250-lenovo-q706f.dtb` | `mmc@8804000`、`qcom,sdhci-msm-v5` **全在** |

结论：**硬件有、DTB 有、驱动没编进去。**

## 修复

`scripts/enable-mmc.py` 只把 MMC 系列符号打开，其余配置一个字节不动：

```
CONFIG_MMC=y
CONFIG_MMC_BLOCK=y
CONFIG_MMC_BLOCK_MINORS=8
CONFIG_MMC_SDHCI=y
CONFIG_MMC_SDHCI_IO_ACCESSORS=y
CONFIG_MMC_SDHCI_PLTFM=y
CONFIG_MMC_SDHCI_MSM=y
CONFIG_MMC_CQHCI=y
```

## 版本串必须锁死

Arch rootfs 里的模块目录是 `7.1.0-1-gd5f7815e9a86`。
`vermagic` 必须一字不差，否则模块拒绝加载。

```
Makefile  VERSION=7 PATCHLEVEL=1 SUBLEVEL=0
          EXTRAVERSION=-1              ← 本仓库 sed 写入
config    CONFIG_LOCALVERSION="-gd5f7815e9a86"
───────────────────────────────────────────
kernelrelease 7.1.0-1-gd5f7815e9a86   ← 与 rootfs 完全一致
```

CI 里有硬断言（`if [ "$REL" != "$TARGET_TRIPLE" ]`），版本串不符直接失败。

因为 `CONFIG_MODVERSIONS` 与 `CONFIG_MODULE_SIG` 都没开，
**rootfs 里现有的 `.ko` 可以直接加载**，不需要重新编译模块
（可选的 `build_modules` 输入用于需要时备份/替换）。

## boot.img 打包：以出厂 header 为模板

`q706f` 是 secure boot 机型，bootloader 对 boot.img header 结构敏感。
因此 `scripts/mkboot.py` **不重新构造 header**，而是以出厂
`header-template.bin` 为底，只覆盖必然变化的 4 个字段：

| 字段 | 偏移 | 是否更新 |
|---|---|---|
| `kernel_size` | 0x08 | ✅ |
| `ramdisk_size` | 0x10 | ✅ |
| `cmdline` | 0x40..0x240 | ✅ |
| `dtb_size` | 0x670 | ✅ |
| `name` | 0x30 | 标记为 `q706f-mmc` |
| 其余（`second_addr`, `id`, `os_version`, 各段地址） | — | **原样保留** |

### 复现验证

用模板 + 出厂 kernel/ramdisk/dtb + 出厂 cmdline 重新打包，
与出厂 `boot.img` 对比：

```
原版 30408704  重打 30408704  ✅ 等长
差异字节: 9 区间 0x30..0x38      ← 只有 name 段
name字段外差异: 0
```

**除 name 段外逐字节一致。**

## 用法

Actions → **Build Q706F kernel (MMC enabled)** → Run workflow

| 输入 | 说明 |
|---|---|
| `kernel_ref` | silime/linux 的 commit / tag，默认 `d5f7815e9a86` |
| `cmdline` | 默认带 `loglevel=8 console=tty0 fbcon=nodefer`（诊断友好） |
| `build_modules` | 是否连模块一起编（默认 true） |

产物（artifact + Release）：

```
boot.img                      ← 直接 fastboot flash boot_a
kernel.img                    ← 裸 Image.gz
dtb
modules-7.1.0-1-gd5f7815e9a86.tar.gz
SHA256SUMS
```

## 刷入

```bash
fastboot flash boot_a boot.img
fastboot erase dtbo_a
fastboot --set-active=a
fastboot reboot
```

插上 SD 卡后应能看到：

```
mmc1: SDHCI controller on 8804000.sdhci
mmc1: new ultra high speed SDR104 SDXC card at address 0001
mmcblk2: mmc1:0001 <card-id> 29.3 GiB
```

## 文件

| 路径 | 作用 |
|---|---|
| `config-lenovo-q706f.aarch64` | 出厂 config（含 `# CONFIG_MMC is not set`，未改动） |
| `scripts/enable-mmc.py` | 运行时开启 MMC |
| `scripts/mkboot.py` | 用出厂 header 模板重打 boot.img |
| `scripts/verify-bootimg.sh` | 结构校验 |
| `header-template.bin` | 出厂 boot.img 的前 1660 字节 |
| `ramdisk.img` | 出厂 ramdisk（16,242,334 字节） |

## 参考

- 内核源码：https://github.com/silime/linux
- Arch 包：https://github.com/silime/ArchLinux-Packages (`linux-sm8250`)
- 镜像仓库：https://github.com/silime/ArchlinuxARM-qcom-aarch64
- postmarketOS 设备页：https://wiki.postmarketos.org/wiki/Lenovo_Xiaoxin_Pad_Pro_12.6_(lenovo-q706f)
