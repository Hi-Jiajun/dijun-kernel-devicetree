# SPDX-License-Identifier: GPL-2.0

# O1 basic
dtb-y += soc/O1_basic.dtb

# ASIC Overlay Resurce
dtb-y += overlay/product/phone/phone_o2s/o2s_phone_overlay.dtbo
dtb-y += overlay/product/pad/pad_o80/o80_pad_overlay.dtbo

# kbuild 默认不给 base dtb 加 -@；overlay 依赖 base 的 __symbols__，故显式打开
DTC_FLAGS += -@
