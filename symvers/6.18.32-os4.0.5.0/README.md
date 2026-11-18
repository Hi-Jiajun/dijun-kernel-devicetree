# 6.18.32 / OS4.0.5.0 & `hmos-opt2` 只读符号表 SDK（外部模块与 KABI 门禁基准）

本目录保存与 `OS4.0.5.0.XODCNXM` 模块池及现役真机内核 `6.18.32-hmos-opt2`（`6.18.32-4k`）逐符号对应的纯文本 `Module.symvers`，供 `scripts/build-extmod.sh` 与 `tools/abi-gate.py` 直接使用，**避免反复重编完整内核或因误复制硬编码 `KBUILD_OUTPUT` 的构建目录导致 `module_layout` CRC 漂移** `[已验证]`。

| 文件 | 行数 | SHA-256（前 16 位） | 说明与核心常量 |
| --- | ---: | --- | --- |
| `vmlinux-pure.symvers` | 3,642 | `6ef00833f3647df9…` | 纯净 `6.18.32` × `OS4.0.5.0`（白名单 4,951 条）内核导出表；`module_layout` = `0x60801db3` |
| `vmlinux-hmos.symvers` | 3,646 | `93c05ae06c830c8c…` | 叠加 `patches/6.18/hmos`（白名单 4,955 条）内核导出表；`module_layout` = `0x60801db3`，`dijun_hmos_ipc_api_v2` = `0xcf4c0200` |
| `vmlinux-hmos-opt2.symvers` | 3,655 | `ba8c381229924f2b…` | **现役 `6.18.32-hmos-opt2` 主交付内核导出表**（叠加 `fragments/hmos-opt2.config`：Tier 1 优化 + `.fs-verity` 内建签名根 + `CONFIG_USER_NS=y`）；相对 `vmlinux-hmos` 仅新增 4 个 `LZ4_*HC` 与 5 个 `make_kuid`/`from_kuid*` 符号，**已有 3,646 条符号 `0` CRC 漂移**，`module_layout` = `0x60801db3`，`dijun_hmos_ipc_api_v2` = `0xcf4c0200` |
| `vendor-modules.symvers` | 2,518 | `72982df6f6bb5798…` | 使用 `tools/export-mod-symvers.py` 从 `OS4.0.5.0` 原厂 `vendor_boot`（139 个）+ `vendor_dlkm`（193 个）共 332 个 `.ko` 提取的模块导出 CRC 表；与 `OS4.0.4.0` **逐字节 100% 一致**（`OS4.0.5.0` 仅重编 `cfg80211.ko` BTF 节与 `wlan_drv_gen4m_eap_6639.ko` 时间戳，导入/导出符号与 CRC 零变化） |

## `6.18.32-hmos-opt2` KABI 实证边界摘要

1. **零 CRC 漂移合入项（`fragments/hmos-opt2.config`）** `[已验证]`：
   - `CONFIG_TMPFS_POSIX_ACL=y`、`CONFIG_TMPFS_XATTR=y`、`CONFIG_PID_NS=y`、`CONFIG_EROFS_FS_ZIP_LZMA=y`、`CONFIG_EROFS_FS_ZIP_DEFLATE=y`、`CONFIG_OVERLAY_FS_XINO_AUTO=y`、`CONFIG_ZRAM_BACKEND_LZ4HC=y`、`CONFIG_DEFAULT_BBR=y`、`CONFIG_FS_VERITY_BUILTIN_SIGNATURES=y`、`CONFIG_USER_NS=y`。
   - `include/linux/{cred,projid,seq_file,uidgid,user_namespace}.h` 中 `#ifdef CONFIG_USER_NS` 仅切换函数声明/内联桩，不改变任何内核结构体内存布局；对 `OS4.0.5.0` 全量 `332`（`vb+vdlkm`）、`437`（含同源 `rust_binder.ko`）及扩展 `342` 模块池均通过 `abi-gate.py`（`kernel_crc_mismatch=0, module_crc_mismatch=0, unresolved=0`）。
2. **`SYSVIPC + POSIX_MQUEUE` KABI 实验边界** `[已验证]`：
   - 原生开启 `CONFIG_SYSVIPC=y` 会在 `struct task_struct` 中部插入 `sysvsem`/`sysvshm`（`last_switch_count` 偏移 `+24` B、`thread` 偏移 `+32` B），导致 `2,540` 个符号 CRC 突变（`module_layout` 变为 `0x5140551a`）。
   - 如确需开启 `SYSVIPC`，必须通过 `ANDROID_KABI_USE(2, struct sysv_sem sysvsem)` 与 `ANDROID_KABI_USE(3, struct sysv_shm *sysvshm)`（在 `newseg()`/`exit_shm()` 按需动态分配）置入 `task_struct` 尾部保留槽，并导出 `init_ipc_ns`/`put_ipc_ns` 供 `rust_binder.ko` 解析，方可保持 `task_struct` `4,736` B 零偏移变化及 C 导出符号 `0` CRC 漂移。
3. **`CONFIG_CGROUP_DEVICE=y` 禁用结论** `[已验证]`：
   - 开启后 `CGROUP_SUBSYS_COUNT` 从 `9` 增至 `10`（`struct css_set` `472 -> 496` B），破坏 `1,581` 个符号 CRC；现役内核已开启 `CONFIG_CGROUP_BPF=y` 满足 cgroup v2 设备访问控制，严禁开启旧 v1 `CGROUP_DEVICE`。

> 注意：仓库内仅保存纯文本符号与 CRC 清单，不含任何原厂闭源 `.ko` 二进制。
