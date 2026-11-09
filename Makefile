# dijun（小米 15S Pro / XRING O1 / 25042PN24C）内核设备树构建入口
#
# 基线：
#   V 基线  dts/                       官方开源 DTS（Android V / 6.6.30），cpp+dtc 可编
#   B 基线  dts-reconstructed/6.6.118-os3   设备 OS3 分区二进制无损还原
#   B 基线  dts-reconstructed/6.18.21-os4   设备 OS4 分区二进制无损还原
#
# 常用目标：
#   make all            编 V 与 B 两代 base dtb + O2S overlay
#   make b              只编 B 两代（不需要内核树）
#   make verify         离线验收：回编哈希、结构 diff、容器同构
#   make dtboimg        用 OS3 的 8 个 entry 重打 dtbo.img
#   make dtboimg-os4    用 OS4 的 8 个 entry 重打 dtbo.img
#   make vendor_boot    用 B 基线 dtb 重打 vendor_boot
#   make kbuild-v KDIR=<内核树>   用内核树自身 kbuild 编（dtstree= 外部设备树）

ROOT     := $(abspath $(dir $(lastword $(MAKEFILE_LIST))))
B        := $(ROOT)/build
BASELINE := $(ROOT)/baseline
KERNEL   ?=
DTC      ?= dtc
CPP      ?= cpp
JOBS     ?= 8

CPPFLAGS := -nostdinc -undef -D__DTS__ -x assembler-with-cpp \
            -I$(ROOT)/include -I$(ROOT)/dts \
            -I$(KERNEL)/include -I$(KERNEL)/arch/arm64/include

V_SRCS := $(shell find $(ROOT)/dts -name '*.dts' -o -name '*.dtsi' -o -name '*.dtso')
V_BASE := $(B)/v/O1_basic.dtb
V_OVL  := $(B)/v/o2s_phone_overlay.dtbo

B3 := 6.6.118-os3
B4 := 6.18.21-os4
B_TARGETS := $(B)/b/$(B3)/base.dtb $(B)/b/$(B3)/o2s_phone_overlay.dtbo \
             $(B)/b/$(B4)/base.dtb $(B)/b/$(B4)/o2s_phone_overlay.dtbo

.PHONY: all v b dtboimg dtboimg-os4 vendor_boot verify kbuild-v kbuild-b clean help
.DEFAULT_GOAL := all

all: v b
v: $(V_BASE) $(V_OVL)
b: $(B_TARGETS)

$(B)/v/O1_basic.dtb: $(V_SRCS)
	@test -n "$(KERNEL)" || { echo "需要 KERNEL=<内核源码树>（仅取 include/dt-bindings）"; exit 2; }
	@mkdir -p $(@D)
	$(CPP) $(CPPFLAGS) $(ROOT)/dts/soc/O1_basic.dts -o $@.pp
	$(DTC) -q -@ -I dts -O dtb -o $@ $@.pp 2>$@.dtc.log

$(B)/v/o2s_phone_overlay.dtbo: $(V_SRCS)
	@test -n "$(KERNEL)" || { echo "需要 KERNEL=<内核源码树>（仅取 include/dt-bindings）"; exit 2; }
	@mkdir -p $(@D)
	$(CPP) $(CPPFLAGS) $(ROOT)/dts/overlay/product/phone/phone_o2s/o2s_phone_overlay.dtso -o $@.pp
	$(DTC) -q -@ -I dts -O dtb -o $@ $@.pp 2>$@.dtc.log

$(B)/b/$(B3)/base.dtb: $(ROOT)/dts-reconstructed/$(B3)/base.dts
	@mkdir -p $(@D)
	$(DTC) -q -@ -I dts -O dtb -o $@ $< 2>$@.dtc.log

$(B)/b/$(B3)/o2s_phone_overlay.dtbo: $(ROOT)/dts-reconstructed/$(B3)/o2s_phone_overlay.dts
	@mkdir -p $(@D)
	$(DTC) -q -@ -I dts -O dtb -o $@ $< 2>$@.dtc.log

$(B)/b/$(B4)/base.dtb: $(ROOT)/dts-reconstructed/$(B4)/base.dts
	@mkdir -p $(@D)
	$(DTC) -q -@ -I dts -O dtb -o $@ $< 2>$@.dtc.log

$(B)/b/$(B4)/o2s_phone_overlay.dtbo: $(ROOT)/dts-reconstructed/$(B4)/o2s_phone_overlay.dts
	@mkdir -p $(@D)
	$(DTC) -q -@ -I dts -O dtb -o $@ $< 2>$@.dtc.log

# dtbo.img：用某个基线的 8 个 entry 重打，验证容器同构
dtboimg:
	unset PYTHONHOME PYTHONPATH && python3 $(ROOT)/tools/mkdtboimg.py --out $(B)/dtbo-$(B3).img \
	  $(foreach f,$(sort $(wildcard $(BASELINE)/$(B3)/dtbo/*.dtbo)),--entry $(f))

dtboimg-os4:
	unset PYTHONHOME PYTHONPATH && python3 $(ROOT)/tools/mkdtboimg.py --out $(B)/dtbo-$(B4).img \
	  $(foreach f,$(sort $(wildcard $(BASELINE)/$(B4)/dtbo/*.dtbo)),--entry $(f))

vendor_boot:
	DTB=$(B)/b/$(B3)/base.dtb bash $(ROOT)/scripts/pack-vendor_boot.sh

verify:
	bash $(ROOT)/scripts/verify.sh

kbuild-v:
	@test -n "$(KDIR)" || { echo "用法: make kbuild-v KDIR=<内核树>"; exit 2; }
	@set -e; unset PYTHONHOME PYTHONPATH; \
	O=$$(mktemp -d $${TMPDIR:-/var/tmp}/dijun-dts-kbuild.XXXXXX); \
	D=$$(mktemp -d $${TMPDIR:-/var/tmp}/dijun-dts-ext.XXXXXX); \
	cp -a $(ROOT)/dts $$D/dts; cp -a $(ROOT)/include $$D/include; \
	make -C $(KDIR) O=$$O ARCH=arm64 LLVM=1 olddefconfig; \
	make -C $(KDIR) O=$$O ARCH=arm64 LLVM=1 dtstree=$$D/dts \
	  DTC_INCLUDE="$$D/include $(KDIR)/scripts/dtc/include-prefixes" dtbs -j$(JOBS); \
	echo "产物在 $$D/dts，O=$$O"

help:
	@grep -E '^#   ' Makefile
