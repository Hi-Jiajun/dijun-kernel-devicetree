# dijun 内核设备树与 GKI/KMI 兼容性

对象：小米 15S Pro（`dijun`，XRING O1，25042PN24C），Android 16 / 内核 6.6.118 线。
本仓库只做**离线**的设备树工程与 ABI 兼容性验证，不包含刷机步骤、不提供设备分区镜像。

## 结论摘要

1. 设备树分两段：base DT 在 `vendor_boot` 的 dtb 段（180,674 B），板级差异在 `dtbo` 分区（8 个 overlay，按 `board_id` 选择；本机命中 `0x090f0000` = O2S PHONE）。`boot.img` 里没有 dtb。
2. 设备当前这代（6.6.118）的 base DT 与 O2S overlay 可以从分区二进制**无损还原为可编译 DTS**：回编结果与设备二进制逐字节相同（sha256 一致）。见 `dts-b/`。
3. 官方开源 DTS（`dts/`，Android V / 6.6.30）是另一代：base 命名 `Franklin1`、reserved-memory 与面板时序都不同，不能直接配 6.6.118 内核。
4. **保持原厂配置重编 ACK 6.6.118 时，导出符号集与 symbol CRC 与原厂 100% 一致**（9,090/9,090），KCFI 836/836 相同；586 个原厂模块里只有 2 个仍缺 2 个符号（推测在未取的 `system_dlkm`）。"开源 ACK/GKI + 原厂闭源模块"在离线层面成立。
5. 功能开关要逐项验证：`PID_NS=y` 对 ABI 无影响；`CGROUP_PIDS=y` 会让 28,356 条模块期望符号里的 7,027 条 CRC 不符（调整枚举顺序也救不回来），不能只改 config 打开。

## 仓库结构

```
dts/       官方开源 DTS（Android V / 6.6.30），cpp+dtc 可编
dts-b/     由设备 vendor_boot dtb 与 dtbo_a 的 O2S entry 反编译得到的 B 基线（回编字节一致）
include/   补齐的 xring dt-bindings（platform-specific 映射）
stock/     原厂 base.dtb 与 8 个 dtbo entry（二进制，仅作回归基线）
tools/     fdtdiff / mkdtboimg / kmi-check / module-inventory / btf-diff / 打包与验收脚本
docs/      调研、结论、运行记录与逐项报告
Makefile   V 与 B 两套产物的构建入口
```

## 复现

```bash
unset PYTHONHOME PYTHONPATH
make all            # 编 V 与 B 两套 base dtb + O2S overlay
make verify         # 离线验收：回编哈希、结构 diff、dtbo/vendor_boot 容器同构
make dtboimg        # 用 8 个 entry 重打 dtbo.img，与设备容器逐字节比较
```

`KERNEL` 默认指向本地 ACK 6.6.118 源码树，仅用于取通用 `include/dt-bindings`。

ABI 兼容性检查（需要原厂 `Module.symvers` 与模块集合，按需自备）：

```bash
python3 tools/module-inventory.py --kernel-symvers <原厂 symvers> \
  --tree vendor_boot:<dir> --tree vendor_dlkm:<dir> --out report/inventory.md
python3 tools/kmi-check.py --stock-symvers <原厂 symvers> --our-symvers <自编 vmlinux.symvers> \
  --vmlinux <自编 vmlinux> --kmi <abi_gki_aarch64> --kmi <abi_gki_aarch64_xiaomi_xring> \
  --modules <vendor_dlkm 目录> --out report/kmi.md
```

## 关键方法学

- 判据优先看**模块 `__versions` 里的期望 CRC 与实际内核导出的差异条数**（基线 0），全量 CRC 百分比只作诊断。
- 不要关"看似无关"的配置：`DEBUG_INFO_BTF` 决定 `__user` 是否展开成 `btf_type_tag` 注解，genksyms 会把属性算进类型字符串，一关就掉 77% 的 CRC。
- 模块集合必须完整（`vendor_boot` 的早期驱动 + `vendor_dlkm` + `system_dlkm`），否则会把"没找到提供方"误判成"驱动缺失"。

## 边界与未验证

- 未做真机刷写与启动验证；`PANIC_ON_OOPS=y`、verity enforcing，写坏引导相关分区后没有 BROM 救砖通道。
- `system_dlkm` 未纳入；KCFI 只比对共有 typeid，不代表全部间接调用通过。
- `docs/` 里的路径与序列号已做占位符脱敏。

## 来源与许可

- `dts/`、`include/` 来自小米开源 `dijun-v-oss` 树（GPL-2.0 / MIT，见各文件 SPDX）。
- `dts-b/` 与 `stock/` 由自有设备分区的二进制反编译/提取得到，属于 GPL-2.0 内核的衍生产物，仅用于自有设备研究。
- `tools/` 为本仓库自写脚本，MIT。
- 社区参考：`lolipuru/android_device_xiaomi_dijun`、`android_device_xiaomi_O1_asic-common`、`android_device_xiaomi_dijun-kernel`（均非本仓库内容）。
