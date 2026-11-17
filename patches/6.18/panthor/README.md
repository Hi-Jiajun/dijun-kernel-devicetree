# ARM Immortalis-G925 (`panthor`) 内建适配规划 (`patches/6.18/panthor`)

## 为什么不能编成外部 `panthor.ko`

`dijun` 当前 OS4.0.4.0 `6.18.32-4k` 内核开启了 `CONFIG_DRM=y`（内建），`drivers/gpu/drm/` 并未导出 `drm_sched_*`、`drm_gpuvm_*`、`drm_exec_*`、`drm_dev_enter` 等核心符号，外部模块 `panthor.ko` 在 modpost 阶段必然出现 241 个未解析符号而无法加载。

因此 `panthor` 必须走**内建进 `Image`** 路线：

1. 内核配置合并 `configs/6.18/fragments/panthor-builtin.config`（`CONFIG_DRM_PANTHOR=y`）。
2. 设备树叠加 `overlays/custom/panthor-g925-experimental.dtso`（`compatible = "arm,mali-valhall-csf"`、小写 `interrupt-names = "job", "mmu", "gpu"`、`mali-supply = <&gpu_subsys>`；正式启用前还需处理 `operating-points-v2` 与 `clk_sys_gpu` 时钟）。
3. 提供从设备 `/vendor/firmware/mali_csffw.bin` 提取的 CSF 固件至 `/lib/firmware/arm/mali/arch13.8/mali_csffw.bin`。
4. **互斥约束**：不得与闭源 `mali_kbase.ko` 同时加载或匹配同一 `gpu@E9F80000` 节点。

## 待补齐源码桥接（下一阶段入口）

- `gpu@E9F80000` 在原厂 DT 中只有 `clock-names = "clk_sys_gpu"` 而无标准 `clocks` phandle（频率控制走 `gpufreq` / `vote_mng`）。后续需在本目录补入一个最小内核 `clk_hw` provider 桥接补丁（或安全频点桩）供 `panthor` 调用 `devm_clk_get(dev, NULL)`。
