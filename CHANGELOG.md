# Changelog

## 2026-11-17 (`v2026.11-os4.0.4.0-sdk`)

### 设备树基线与结构防误判
- 将顶层 `dts/` 重命名为 `dts-oss/6.6.30-android15-v/` 并新增说明，消除把 6.6.30 OSS 误当 OS4 现行设备树的风险；新增 `dts-current` 软链指向 `dts-reconstructed/6.18.21-os4.0.4.0/`。
- 新增 `OS4.0.4.0` 基线（`base.dtb` 221,460 B + 全部 8 个 `.dtbo`），并补齐 `6.6.118-os3`、`6.18.21-os4.0.0.19`、`6.18.21-os4.0.4.0` 三代全部 24 个 `.dtbo` 的无损反编译 DTS（宿主 `dtc 1.8.1` 回编 100% 字节一致）。
- 新增 `overlays/custom/` 增量设备树补丁层（`chosen-diag-example.dtso` 与实验性 `panthor-g925-experimental.dtso`）及 `Makefile` `overlays` / `kbuild-b` / `clean` 目标。

### 工具链与门禁升级
- 修复 `tools/fdtdiff.py`：默认忽略节点自 phandle、按提供方 `#*-cells` 解析引用元组、移除 `opp-` 误匹配、支持 `/__fixups__` 解析与多 fragment 同目标消歧；生成 `OS4.0.0.19` → `OS4.0.4.0` 权威差异报告。
- 新增 `tools/_elfmod.py` 与 `tools/export-mod-symvers.py`（纯 Python ELF64 符号与 CRC 提取）。
- 升级 `tools/abi-gate.py`：过滤 `vmlinux` 列、按 `<label>:<relpath>` 隔离同名模块、校验模块间导出 CRC、支持 `--replace`、`--allow-dead-module`、`--expect-vermagic`、`--protected-list`、`--json`。
- 修复 `scripts/demo-patch.sh`、重写 `scripts/pack-vendor_boot.sh`（动态继承原镜像头参数与 cmdline）、新增 `scripts/pack-boot.sh`；升级 `scripts/verify.sh` 与 GitHub Actions CI。

### 6.18.32-4k 外部模块 SDK 与多线 Profile
- 同步 `OS4.0.4.0` 配置（`dijun-os4.0.4.0.config`）、白名单（`os4.0.4.0` 4,951 条、`hmos` 4,955 条）、配置片段 `configs/6.18/fragments/` 与场景化 `baselines/*.env`，固化 `vermagic` + `module_layout=0x60801db3` 双契约。
- 归档只读符号 SDK `symvers/6.18.32-os4.0.4.0/`（`vmlinux-pure`、`vmlinux-hmos`、`vendor-modules`），新增 `scripts/build-extmod.sh` 实现外部 `.ko` 隔离构建与四重门禁。
- 收纳 `patches/6.18/hmos/0001-dijun-hmos-ipc-readonly-typed-api-v2.patch` 与 `patches/6.18/panthor/` 规划，升级 `scripts/build-kernel.sh` 支持 `--profile` 且锁死 `LOCALVERSION=""` 不再吞掉门禁错误。

## 2026-11-09

### dijun 内核设备树基线
- 从设备 `vendor_boot` / `dtbo` 无损还原 6.6.118 基础 DT 与 O2S overlay（回编字节一致）。
- 建立 V 基线（官方 OSS 6.6.30 DTS）与 B 基线（设备二进制还原）双基线工程。
- `dtbo.img` / `vendor_boot` 重打与设备镜像逐字节一致。

### GKI/KMI 兼容性
- 6.6.118：保持原厂 config 重编，导出符号 9,090/9,090、CRC 全等；`PID_NS` ABI 安全，cgroup 控制器会破坏 ABI。
- 6.18.21：AOSP 公开源码 + 厂商同款 clang/Rust 工具链可复现原厂模块 CRC（`KBUILD_GENDWARFKSYMS_STABLE=1`）。

### 设备树基线
- 新增 OS4 / 6.18.21 基线：`dts-reconstructed/6.18.21-os4/` 与 `baseline/6.18.21-os4/`（回编字节一致）。
- 两代 B 基线按版本分目录，`make b` 同时构建。

### 内核基线与更新流程
- 固定 6.18.32（AOSP `android17-6.18-2026-09`）为当前设备基线，新增 `docs/kernel-compat/2026-11-09-kernel-update-process.md` 与 `configs/6.18/baseline.env`。

### 构建工程化
- 新增 `configs/6.18/`（设备原始 config、模块导入符号白名单）与 `scripts/build-kernel.sh`，把工具链、`KBUILD_GENDWARFKSYMS_STABLE=1`、保护列表、模块签名和 ABI 门固化下来。

### 真机
- 自编 6.18.21 内核在 OS4 上成功启动，功能基本可用；`CONFIG_PID_NS=y` 变体验证通过。
