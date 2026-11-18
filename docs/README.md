# 文档索引

## 设备树

- [2026-11-09-research-device-tree.md](device-tree/2026-11-09-research-device-tree.md) — dijun 设备树现状、V/B 两代差异、主流做法与选型、跨内核可移植性
- [2026-11-09-build-and-verify.md](device-tree/2026-11-09-build-and-verify.md) — 从分区取件到回编、打包、验收的运行记录
- [2026-11-17-os4-4.0.4.0-dt-baseline.md](device-tree/2026-11-17-os4-4.0.4.0-dt-baseline.md) — OS4.0.4.0 设备树基线、全 8 个 DTBO 还原、目录防误判重构、`fdtdiff.py` 修复与 `.dtso` 增量开发流
- [2026-11-18-os4-4.0.5.0-dt-and-opt2-sync.md](device-tree/2026-11-18-os4-4.0.5.0-dt-and-opt2-sync.md) — OS4.0.5.0 设备树基线无损同步、4.0.4.0 vs 4.0.5.0 全量 0 差异对比与 `6.18.32-hmos-opt2` KABI 对齐

## 内核兼容与构建 SDK

- [2026-11-09-gki-kmi-alignment.md](kernel-compat/2026-11-09-gki-kmi-alignment.md) — 6.6.118 与 6.18.21 的 GKI/KMI 对齐、根因与功能开关结论
- [2026-11-09-os4-6.18-bringup.md](kernel-compat/2026-11-09-os4-6.18-bringup.md) — OS4 6.18.21 自编内核全过程、工具链、真机结果
- [2026-11-09-kernel-update-process.md](kernel-compat/2026-11-09-kernel-update-process.md) — 6.18 内核基线、AOSP 更新流程与门禁
- [2026-11-09-kernel-comparison.md](kernel-compat/2026-11-09-kernel-comparison.md) — 自编内核与官方内核的差异对比
- [2026-11-10-compat-baseline-and-feature-gates.md](kernel-compat/2026-11-10-compat-baseline-and-feature-gates.md) — 兼容基线与功能开关的构建记录
- [2026-11-17-extmod-sdk-and-profiles.md](kernel-compat/2026-11-17-extmod-sdk-and-profiles.md) — 6.18.32-4k 双契约（`vermagic` + `module_layout`）、`symvers` SDK、`build-extmod.sh` 与多线 Profile 构建

## 板级与模块硬件契约

- [hardware-contracts/README.md](hardware-contracts/README.md) — `dijun` 板级硬约束总索引（全部基于实测与原厂模块离线分析）
- [hardware-contracts/platform-and-partitions.md](hardware-contracts/platform-and-partitions.md) — 三层身份命名（`O1_asic` / `dijun` / `0x090f0000`）、UFS A/B 物理分区映射与 L1/L2 刷写红线
- [hardware-contracts/soc-and-kernel-constraints.md](hardware-contracts/soc-and-kernel-constraints.md) — CPU 四簇跳号拓扑（`policy0/2/4/8`）、G925/DPU 真值、`# CONFIG_DEVTMPFS is not set`、`pstore/ramoops`
- [hardware-contracts/module-closures-os4.0.5.0.md](hardware-contracts/module-closures-os4.0.5.0.md) — OS4.0.5.0 Safe63 零 USB 抖动充电闭包 vs 4 个 Type-C 模块边界、GPU Stage 0 v2 7 模块闭包与音频/触觉 12/20 模块两阶段闭包
- [hardware-contracts/module-closures-os4.0.4.0.md](hardware-contracts/module-closures-os4.0.4.0.md) — OS4.0.4.0 五大子系统加载闭包（UFS/USB/显示触控/电源/GPU）与 `hwid.ko` 参数硬契约

## 真机运行记录

- [2026-11-09-selfbuild-first-boot-failure.md](runbooks/2026-11-09-selfbuild-first-boot-failure.md) — 首测卡开机动画与回滚
- [2026-11-09-selfbuild-boot-success.md](runbooks/2026-11-09-selfbuild-boot-success.md) — 成功启动、rust_binder 签名加载与 PID_NS 验证

## 原始报告

- [reports/](reports/) — gate、结构 diff、OS4.0.0.19→OS4.0.4.0 变更报告、模块盘点等原始输出
