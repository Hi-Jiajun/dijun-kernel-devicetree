# 增量设备树补丁层（`.dtso`）

日常做硬件适配或调试改造时，**不要直接修改上万行的反编译文件 `dts-reconstructed/*/base.dts`**，而是将最小增量写成几十行的 `.dtso` 放在本目录：

1. 编译基线与自定义 overlay：
   ```bash
   unset PYTHONHOME PYTHONPATH
   make b overlays
   ```
2. 用 `fdtoverlay` 叠加到目标 `base.dtb`（示例以 `6.18.21-os4.0.5.0` 为基线）：
   ```bash
   fdtoverlay -i build/b/6.18.21-os4.0.5.0/base.dtb \
     -o build/base-patched.dtb \
     build/overlays/chosen-diag-example.dtbo
   ```
3. 用 `fdtdiff.py` 复核净变更，确保只改动预期节点与属性：
   ```bash
   python3 tools/fdtdiff.py baseline/6.18.21-os4.0.5.0/base.dtb build/base-patched.dtb --max-diff 20
   ```

若修改需要写回 `dtbo` 分区的板级入口（如 O2S PHONE `entry05`），也可把需要叠加的 fragment 合并或通过 `mkdtboimg.py` 替换对应槽位。
