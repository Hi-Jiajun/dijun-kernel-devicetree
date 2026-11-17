# HarmonyOS 外部 IPC 内核补丁集 (`patches/6.18/hmos`)

## 用途与归属

- 补丁 `0001-dijun-hmos-ipc-readonly-typed-api-v2.patch` 在干净 AOSP `android17-6.18`（`6.18.32`）内核的 `drivers/android/` 下新增只读类型化导出表 `dijun_hmos_ipc_api_v2`（符号 CRC `0xcf4c0200`，协议魔数 `DIJUNIPC` / `0x4350494e554a4944`，版本 `2`）。
- 上游设计源于开源项目 `AnyHarmonyOSNext/anyhmos_xiaomi_sheng` 6.6 适配草稿，现已完成 6.18.32 适配并统一使用 `dijun` 命名归属。
- 内核侧**不包含** token 设备或 HarmonyOS binder 实现，仅向经过 CFI 类型校验的外部模块提供 20 项安全/MM 只读函数指针。

## 关键构建约束（不可跳过）

1. **必须同时启用 `configs/6.18/fragments/hmos-ipc.config` 与 `configs/6.18/ksym-whitelist-hmos.txt`**：
   - 虽然补丁源码已带 `__section(".no_trim_symbol")`，但当 `CONFIG_TRIM_UNUSED_KSYMS=y` 与 `CONFIG_MODULE_SIG_PROTECT=y` 同时开启时，`-u` 白名单以外的符号仍可能被导出成 `KSYM_FLAG_PROTECTED`，导致未签名的外部模块加载报 `-EACCES`。
   - `ksym-whitelist-hmos.txt` 已在 4,951 条 `OS4.0.4.0` 基线上补齐 `dijun_hmos_ipc_api_v2`、`get_task_pid`、`pid_nr_ns`、`task_active_pid_ns` 共 4 个符号（合计 4,955 条）。
2. **禁止与旧版 `sheng_hmos_ipc*` 模块混用**：协议魔数与导出符号已成对切换为 `dijun_hmos_ipc_api_v2` / `DIJUNIPC`。
