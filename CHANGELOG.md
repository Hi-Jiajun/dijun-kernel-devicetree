# Changelog

## 2026-11-09

### dijun 内核设备树基线
- 从设备 `vendor_boot` / `dtbo` 无损还原 6.6.118 基础 DT 与 O2S overlay（回编字节一致）。
- 建立 V 基线（官方 OSS 6.6.30 DTS）与 B 基线（设备二进制还原）双基线工程。
- `dtbo.img` / `vendor_boot` 重打与设备镜像逐字节一致。

### GKI/KMI 兼容性
- 6.6.118：保持原厂 config 重编，导出符号 9,090/9,090、CRC 全等；`PID_NS` ABI 安全，cgroup 控制器会破坏 ABI。
- 6.18.21：AOSP 公开源码 + 厂商同款 clang/Rust 工具链可复现原厂模块 CRC（`KBUILD_GENDWARFKSYMS_STABLE=1`）。

### 构建工程化
- 新增 `configs/6.18/`（设备原始 config、模块导入符号白名单）与 `scripts/build-kernel.sh`，把工具链、`KBUILD_GENDWARFKSYMS_STABLE=1`、保护列表、模块签名和 ABI 门固化下来。

### 真机
- 自编 6.18.21 内核在 OS4 上成功启动，功能基本可用；`PID_NS` 变体验证通过。
