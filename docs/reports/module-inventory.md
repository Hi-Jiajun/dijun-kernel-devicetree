# 原厂模块需求集与依赖图

模块总数 586；内核导出符号（原厂 Module.symvers）9090；模块间导出符号 3044。

来源分布：os3-vendor_boot=385，vendor_dlkm=201


## 1. 解析结果
- 有无法解析导入符号的模块：**2 / 586**
- 跨模块依赖边（导入→模块导出）：4385
- 模块 `__versions` 与原厂内核符号表 CRC 不一致的条目：0

## 2. 无法解析清单（按缺失数量排序）
- `os3-vendor_boot/6.6.118-android15-8-4k/extra/xring-modules/drivers/modem/mediatek/wwan/pwrctl/common/wwan_gpio_pwrctl.ko`（os3-vendor_boot）缺 2：mtk_pwrctl_slt_gpio_init, mtk_pwrctl_slt_gpio_uninit
- `vendor_dlkm/wwan_gpio_pwrctl.ko`（vendor_dlkm）缺 2：mtk_pwrctl_slt_gpio_init, mtk_pwrctl_slt_gpio_uninit

## 3. 依赖层级（被最多模块依赖的导出符号）
- `__cfg80211_alloc_event_skb` ← 2 个模块（例：os3-vendor_boot/6.6.118-android15-8-4k/kernel/net/wireless/cfg80211.ko, vendor_dlkm/cfg80211.ko）
- `__cfg80211_alloc_reply_skb` ← 2 个模块（例：os3-vendor_boot/6.6.118-android15-8-4k/kernel/net/wireless/cfg80211.ko, vendor_dlkm/cfg80211.ko）
- `__cfg80211_get_bss` ← 2 个模块（例：os3-vendor_boot/6.6.118-android15-8-4k/kernel/net/wireless/cfg80211.ko, vendor_dlkm/cfg80211.ko）
- `__cfg80211_radar_event` ← 2 个模块（例：os3-vendor_boot/6.6.118-android15-8-4k/kernel/net/wireless/cfg80211.ko, vendor_dlkm/cfg80211.ko）
- `__cfg80211_send_event_skb` ← 2 个模块（例：os3-vendor_boot/6.6.118-android15-8-4k/kernel/net/wireless/cfg80211.ko, vendor_dlkm/cfg80211.ko）
- `bridge_tunnel_header` ← 2 个模块（例：os3-vendor_boot/6.6.118-android15-8-4k/kernel/net/wireless/cfg80211.ko, vendor_dlkm/cfg80211.ko）
- `cfg80211_any_usable_channels` ← 2 个模块（例：os3-vendor_boot/6.6.118-android15-8-4k/kernel/net/wireless/cfg80211.ko, vendor_dlkm/cfg80211.ko）
- `cfg80211_assoc_comeback` ← 2 个模块（例：os3-vendor_boot/6.6.118-android15-8-4k/kernel/net/wireless/cfg80211.ko, vendor_dlkm/cfg80211.ko）
- `cfg80211_assoc_failure` ← 2 个模块（例：os3-vendor_boot/6.6.118-android15-8-4k/kernel/net/wireless/cfg80211.ko, vendor_dlkm/cfg80211.ko）
- `cfg80211_auth_timeout` ← 2 个模块（例：os3-vendor_boot/6.6.118-android15-8-4k/kernel/net/wireless/cfg80211.ko, vendor_dlkm/cfg80211.ko）
- `cfg80211_background_cac_abort` ← 2 个模块（例：os3-vendor_boot/6.6.118-android15-8-4k/kernel/net/wireless/cfg80211.ko, vendor_dlkm/cfg80211.ko）
- `cfg80211_bss_color_notify` ← 2 个模块（例：os3-vendor_boot/6.6.118-android15-8-4k/kernel/net/wireless/cfg80211.ko, vendor_dlkm/cfg80211.ko）
- `cfg80211_bss_flush` ← 2 个模块（例：os3-vendor_boot/6.6.118-android15-8-4k/kernel/net/wireless/cfg80211.ko, vendor_dlkm/cfg80211.ko）
- `cfg80211_bss_iter` ← 2 个模块（例：os3-vendor_boot/6.6.118-android15-8-4k/kernel/net/wireless/cfg80211.ko, vendor_dlkm/cfg80211.ko）
- `cfg80211_cac_event` ← 2 个模块（例：os3-vendor_boot/6.6.118-android15-8-4k/kernel/net/wireless/cfg80211.ko, vendor_dlkm/cfg80211.ko）

## 4. 说明
- 解析范围只包含给出的目录；本地没有 system_dlkm 镜像，未纳入。
- 内核侧只提供 **原厂** 导出符号表；自编内核的导出情况需另做比对。
- `__versions` 的 CRC 与原厂内核表一致，说明该符号表与这批模块同代。
