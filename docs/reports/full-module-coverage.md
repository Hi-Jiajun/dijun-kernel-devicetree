# 全量模块覆盖检查（586 模块 ÷ vendor_boot + vendor_dlkm）

- 模块总数 586，内核导出 9090，模块导出 3044，并集 12134
- 仍有无法解析导入的模块：2
  - os3-vendor_boot/6.6.118-android15-8-4k/extra/xring-modules/drivers/modem/mediatek/wwan/pwrctl/common/wwan_gpio_pwrctl.ko 缺 2：mtk_pwrctl_slt_gpio_init, mtk_pwrctl_slt_gpio_uninit
  - vendor_dlkm/wwan_gpio_pwrctl.ko 缺 2：mtk_pwrctl_slt_gpio_init, mtk_pwrctl_slt_gpio_uninit

## KCFI
- 模块与内核共有 typeid 条目：836，值不同：0
