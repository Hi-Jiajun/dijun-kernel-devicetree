# dijun 板级与模块硬件契约（Hardware Contracts）

本目录沉淀小米 15S Pro（设备代号 `dijun`，SoC `XRING O1`，硬件型号 `25042PN24C`）在内核构建、设备树改造、早期启动栈与外部模块集成过程中实测确认的**板级硬约束**。

全部条目均基于设备只读实测、`baseline/` / `configs/` / `dts-reconstructed/` 与 `tools/module-inventory.py` 对 OS4.0.4.0 / OS4.0.5.0 原厂模块的离线 ELF64 分析整理，不含任何本地主机路径、设备序列号或私有安全材料。

## 目录索引

| 文档 | 内容 |
| --- | --- |
| [`platform-and-partitions.md`](platform-and-partitions.md) | 平台/设备/单板三层身份边界、UFS A/B 物理分区表映射、只读引导红线 |
| [`soc-and-kernel-constraints.md`](soc-and-kernel-constraints.md) | CPU 四簇跳号拓扑（`policy0/2/4/8`）、GPU/DPU 真值、`# CONFIG_DEVTMPFS is not set`、`PANIC_ON_OOPS=y`、`pstore/ramoops` |
| [`module-closures-os4.0.5.0.md`](module-closures-os4.0.5.0.md) | **现行 `OS4.0.5.0` 契约**：Safe63 零 USB 抖动充电安全闭包 vs 4 个 Type-C 动态重枚举模块边界、GPU Stage 0 v2 7 模块解耦闭包、音频/`CS40L26A` 马达 12/20 模块两阶段闭包及早期 USB `peripheral` DTBO 硬前提 |
| [`module-closures-os4.0.4.0.md`](module-closures-os4.0.4.0.md) | OS4.0.4.0 五大核心子系统（UFS/HWID、USB/UDC、显示/触控、电量计/充电、GPU `mali_kbase`）拓扑加载闭包与 `.modinfo` 参数契约 |
