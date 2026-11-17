# 6.18.32 / OS4.0.4.0 只读符号表 SDK（外部模块构建基准）

本目录保存与真机现行内核 `6.18.32-4k` 逐符号对应的纯文本 `Module.symvers`，供 `scripts/build-extmod.sh` 与 `tools/abi-gate.py` 直接使用，**避免反复重编完整内核或因误复制硬编码 `KBUILD_OUTPUT` 的构建目录导致 `module_layout` CRC 漂移**。

| 文件 | 行数 | SHA-256（前 16 位） | 说明与核心常量 |
| --- | ---: | --- | --- |
| `vmlinux-pure.symvers` | 3,642 | `6ef00833f3647df9…` | 纯净 `6.18.32` × `OS4.0.4.0`（白名单 4,951 条）内核导出表；`module_layout` = `0x60801db3` |
| `vmlinux-hmos.symvers` | 3,646 | `93c05ae06c830c8c…` | 同上叠加 `patches/6.18/hmos`（白名单 4,955 条）内核导出表；`module_layout` = `0x60801db3`，`dijun_hmos_ipc_api_v2` = `0xcf4c0200` |
| `vendor-modules.symvers` | 2,518 | `72982df6f6bb5798…` | 使用 `tools/export-mod-symvers.py` 从 OS4.0.4.0 原厂 `vendor_boot` + `vendor_dlkm` 共 332 个 `.ko` 提取的模块导出 CRC 表（含 `edr_drv_submit_api_sync` `0x39bc4e1a`、`mdr_system_error` `0xf382c69a`、`snprintf_s` `0x3b2821fa` 等） |

> 注意：
> 1. 仓库内仅保存纯文本符号与 CRC 清单，不含任何原厂闭源 `.ko` 二进制。
> 2. 任一导出表仅在对应基线有效；重编内核时若增删符号或改换内核提交，须重新导出对应 `vmlinux-*.symvers`。
