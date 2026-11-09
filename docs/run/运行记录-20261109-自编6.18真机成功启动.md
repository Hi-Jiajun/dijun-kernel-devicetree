# 运行记录 2026-11-09：自编 6.18 内核真机成功启动（最终版）

## 结果

设备运行自编内核 `6.18.21-4k-g5a4f1906ff98`，**正常完成开机**：`sys.boot_completed=1`、`init.svc.bootanim=stopped`，当前前台是系统设置界面；`lsmod` 294 个模块，`mali_kbase`、`xr_isp`、`shub_*`、`binder_gki`、`millet_binder` 均正常；**本次启动没有产生新的 tombstone**（上一版失败时 camera-provider / hwcomposer-3 反复 SIGSEGV）。

## 构建参数（与失败版的差别）

- clang：`clang-r584948c`（Android 15323222 / clang 22.0.1），与设备 `CONFIG_CC_VERSION_TEXT` 逐字一致；失败版用的是 `r584948`（22.0.0）。
- Rust：`1.91.1.p3`（build 15551131）+ 自编 `rust_binder.ko`；`CONFIG_WERROR=y`（失败版是关的）。
- config：直接取设备原始 `/proc/config.gz`，只把 `UNUSED_KSYMS_WHITELIST` 指向模块导入符号清单；`KBUILD_GENDWARFKSYMS_STABLE=1`。
- 产物：`Image` sha256 `ebb541c1…`（42,084,864 B），boot 镜像 `boot-618-final.img`；网关 gate 结果 542 模块、CRC 0 条不符（仅死模块 `xr_pmonitor` 缺符号）。

## 过程

1. `fastboot flash boot_a boot-618-final.img` → 重启；
2. 约 35 s 后 adb 在线，`sys.boot_completed=1`，桌面正常；
3. 验证模块：294 个，`rust_binder` 加载成功（Live、refcnt 0）；
4. 自编 `rust_binder.ko` 一开始 `insmod` 报 Permission denied，dmesg 显示 `Cannot use protected symbol`——因为 `UNUSED_KSYMS_WHITELIST` 同时被 `kernel/module/Makefile` 当作 KMI 保护名单，未签名模块不能引用这些符号。用构建出的 `out618_final/scripts/sign-file` 加 `certs/signing_key.pem/x509` 签名后 `insmod` 成功（临时 `setenforce 0`，之后已恢复 `Enforcing`）。

## 判读

上一版卡开机动画的原因基本可以锁定为**工具链/CONFIG 不对齐**（clang 22.0.0 vs 22.0.1、WERROR 关闭、config 经过一轮归一化），而不是缺厂商补丁；换成与厂商完全一致的 clang 并保留原始 config 后，同一份 AOSP 6.18.21 源码可以直接带起 OS4。

## 仍待确认

- 相机、WiFi 等具体硬件功能尚未逐项验证（本次 WiFi 处于关闭状态，未做开关测试；camera provider 的 service 名需要再确认）。
- 我们的 `rust_binder` 目前只在 `/data/local/tmp` 手动加载，未做持久化；且需要签名才能过 protected symbol 检查。
- 回滚镜像：`stock-boot_a-current.img`（sha256 `8563cbf6…`，与 OS4 包 `images/boot.img` 一致）。
