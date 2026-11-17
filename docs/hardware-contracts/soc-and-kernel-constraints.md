# XRING O1 / dijun SoC 拓扑与内核运行期契约

## 1. CPU 四簇 10 核跳号 `cpufreq` 拓扑

XRING O1 采用 4 簇 10 核 ARMv9.2-A 架构。**实测设备的 `cpufreq` policy 编号按 `0 / 2 / 4 / 8` 跳号排列，并非连续的 `0..3`**（以每个簇的起始 CPU 核号命名）：

| sysfs 目录 | `affected_cpus` | 微架构与核数 | 实测 `cpuinfo_max_freq` (kHz) |
| --- | --- | --- | ---: |
| `/sys/devices/system/cpu/cpufreq/policy0` | `0 1` | 2× Cortex-A520 | `1,795,200` (1.795 GHz) |
| `/sys/devices/system/cpu/cpufreq/policy2` | `2 3` | 2× Cortex-A725 | `1,891,200` (1.891 GHz) |
| `/sys/devices/system/cpu/cpufreq/policy4` | `4 5 6 7` | 4× Cortex-A725 | `3,398,400` (3.398 GHz) |
| `/sys/devices/system/cpu/cpufreq/policy8` | `8 9` | 2× Cortex-X925 | `3,897,600` (3.898 GHz) |

> **工程约束**：编写限频或温控守护逻辑时，必须通过通配枚举 `policy*` 遍历全部 4 个簇；若写成 `for (p = 0; p < 4; p++)` 拼接 `policy%d`，将完全遗漏功耗与发热量最大的中大核簇 `policy4` 与超大核簇 `policy8`。

---

## 2. GPU 与显示控制器硬件真值

- **GPU 架构**：ARM **Immortalis-G925 MC16**（硬件寄存器 `GPU_ID = 0x0D080300`，对应 `PAN_PROD_ID(13, 8, 0)`，Mesa 架构代际 **Valhall CSF v13**）。
  - 注意原厂 DT 中某些节点兼容串仍写作 `arm,mali-midgard`，这只是闭源 `mali_kbase.ko` 历史驱动匹配写法，**不可据此误判为 Midgard/Panfrost**。
  - 若评估主线开源 `drm/panthor`：因 Android GKI/XRing 内核未向模块导出 `drm_dev_enter` 等内部 DRM 符号，`panthor` 无法以树外 `.ko` 加载，必须通过 `CONFIG_DRM_PANTHOR=y`（见 [`configs/6.18/fragments/panthor-builtin.config`](../../configs/6.18/fragments/panthor-builtin.config)）内建并配合增量 `.dtso` 适配 CSF 兼容串与中断命名。
- **显示硬件**：XRing 自研 DPU/DSI（`xring,dpu-kms`，内核模块 `xring-drm.ko`），非高通 `msm/dpu1`。
  - 实测主屏能力：`1440×3200@120Hz`（DSI 连接器），提供 **32 个 DRM plane**（3× `PRIMARY` + 29× `OVERLAY`）。
  - 注意设备出厂 OLED 高分辨率与高刷特性，调试常亮画面时须通过 `brightness` 节点做定时熄屏与低亮度保护。

---

## 3. 内核关键配置与崩溃诊断区约束

对照现行 [`configs/6.18/dijun-os4.0.4.0.config`](../../configs/6.18/dijun-os4.0.4.0.config) 与 [`dts-current`](../../dts-current)：

| 契约项 | 真实取值 | 对早期启动与驱动开发的影响 |
| --- | --- | --- |
| **`CONFIG_DEVTMPFS`** | `# CONFIG_DEVTMPFS is not set` | 内核不会在 `/dev` 自动生成设备节点（`CONFIG_DEVTMPFS_MOUNT` 亦未开）。若自定义第一阶段用户态或调试容器未启动完整的 `ueventd`，所有 `/dev/dri/card0`、`/dev/dma_heap/system`、`/dev/input/event*`、`/dev/console`、`/dev/kmsg` 均需按 sysfs `dev` 主次设备号由 init 显式 `mknod` |
| **`CONFIG_PANIC_ON_OOPS`** | `CONFIG_PANIC_ON_OOPS=y` | 任何内核 Oops（例如驱动空指针解引用）将立即触发整机 `panic` 重启，不会静默恢复 |
| **`CONFIG_DPM_WATCHDOG`** | `CONFIG_DPM_WATCHDOG=y`（OS4.0.4.0 新增） | 电源管理挂起/恢复路径超时将触发看门狗复位 |
| **模块 ABI 契约** | `CONFIG_MODVERSIONS=y` + `CONFIG_EXTENDED_MODVERSIONS=y` + `CONFIG_DEBUG_INFO_BTF_MODULES=y` | 所有树外模块必须严格匹配 `VERMAGIC="6.18.32-4k SMP preempt mod_unload modversions aarch64"` 与 `module_layout=0x60801db3`（统一由 [`scripts/build-extmod.sh`](../../scripts/build-extmod.sh) 保证） |
| **`pstore` / `ramoops`** | `base.dts` 中 `rsv_mem_pstore@a0000000`：`reg = <0x00 0xa0000000 0x00 0x100000>`（1 MiB） | DTBO 中对 `&pstore` 启用 `compatible = "ramoops"`：`record-size = <0x40000>`（256 KiB）、`console-size = <0x80000>`（512 KiB）、`pmsg-size = <0x40000>`（256 KiB），跨软重启提取崩溃现场 `/sys/fs/pstore/console-ramoops-0` |
| **系统调用号与工具** | `toybox` 环境（设备侧） | 注意设备上 `grep` 不支持 GNU 基础正则分支 `\|`，脚本内一律使用 `grep -E "A\|B"` |
