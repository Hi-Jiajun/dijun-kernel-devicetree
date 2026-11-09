# 运行记录 2026-11-09：自编 6.18 内核真机首测（失败并已回滚）

## 结论

自编 6.18.21 内核**能启动到 Android 用户态**（adb 在线、292 个模块加载、binder_gki/millet 正常），但 **Android 框架没有完成开机**：卡在 "Xiaomi HyperOS" 开机动画 3 分钟以上，`sys.boot_completed` 一直为空、`init.svc.bootanim=running`，系统明显发热。已回滚原厂 boot_a，设备恢复正常（`uname -r` 回到 `6.18.21-android17-5-g1d099fcb35e0-abogki538445360-4k`，`sys.boot_completed=1`）。

## 操作

1. 预检：设备在线、`current-slot=a`、`uptime` 约 1700 s、load 4.1（每核 0.26）。
2. 只读备份当前 `boot_a`：sha256 `8563cbf6…`，与 OS4 包 `images/boot.img` **完全一致**。
3. 用 `out618_rust3/arch/arm64/boot/Image`（42,084,864 B，sha256 `4930dfe2…`）+ `mkbootimg --header_version 4 --ramdisk 空 --cmdline ''` 生成 `boot-618-selftest.img`，解包校验 kernel sha 一致。
4. `adb reboot bootloader` → 两次 `getvar product` 均为 `product: dijun` → `fastboot flash boot_a` → `fastboot reboot`。
5. 启动后 `adb` 在约 40 s 可用，`uname -r` 显示 `6.18.21-4k-g5a4f1906ff98`（自编），`lsmod` 292 项，`binder_gki`、`millet_binder` 正常；`rust_binder` 未加载（预期，crate 哈希不同）。
6. 等 3 分钟仍未进桌面：`sys.boot_completed` 空、bootanim 一直 running，logcat 里 camera provider 有 tombstone，系统发热。
7. 回滚：`fastboot flash boot_a stock-boot_a-current.img` → 重启后 `sys.boot_completed=1`，恢复正常。

## 判读

- 不是 bootloader/AVB 问题：内核被加载并执行，adb 与模块都起来了。
- 不是模块 ABI 问题：292 个模块加载成功（CRC gate 已证明 0 条不符），只有 `rust_binder` 未加载。
- 更像是**内核行为与厂商树不一致**：AOSP 6.18.21 缺厂商补丁（如 `XIAOMI_ENHANCED_IOSTAT`、`F2FS_VIP_FILE` 等）以及可能的 vendor hook 调用点；CRC 只保证符号存在，保证不了这些补丁带来的运行时行为。camera provider 的 tombstone 可能是这一差异的表象。
- 另一个待排查项：我们 config 里 `rust_binder` 用自编模块替换，但本次测试没换模块（仍是原厂模块），它加载失败是否影响 SystemServer 需要确认（设备上它 refcount 0，理论上不影响）。

## 下次实验要点

1. 卡住时**先抓日志再回滚**：`adb shell dmesg`、`adb logcat -d`、`getprop`、`lsmod`，这次因设备发烫被取消，没抓到。
2. 优先用 USB ACM 串口抓早期日志（`dijun-usb-serial` 技能），这样即使 framework 起不来也有输出。
3. 对照实验：把 `rust_binder` 换成自编模块再测一次，排除模块加载失败的影响。
4. 若要继续，建议先补厂商配置差异（`F2FS_VIP_FILE`、`XIAOMI_*`）——但这些在 AOSP 树里没有实现，属于厂商补丁，短期只能等源码或逆向。
