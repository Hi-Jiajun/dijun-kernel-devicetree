# dijun（小米 15S Pro / XRING O1 / 25042PN24C）设备树工程
#
# 两条基线：
#   V 基线  dts/    官方开源 OSS（Android V，common 6.6.30）的 DTS 源码，可 cpp+dtc 直接编
#   B 基线  dts-b/  设备实际运行（Android 16 / 6.6.118）的分区二进制无损还原出的 DTS
#
# 常用目标：
#   make all            编出 V 与 B 两套 base dtb + O2S phone overlay
#   make kbuild-v KDIR=...   用内核树自己的 kbuild 编（dtstree= 外部设备树）
#   make dtboimg        打 dtbo.img（Android dtbo 容器）
#   make vendor_boot    重打 vendor_boot（DT 实际所在分区）
#   make verify         跑离线验收：回编哈希、结构 diff、容器同构

ROOT    := $(abspath $(dir $(lastword $(MAKEFILE_LIST))))
B       := $(ROOT)/build
STOCK   := $(ROOT)/stock
KERNEL  ?= <home>/ack-66118/src
DTC     ?= dtc
CPP     ?= cpp
JOBS    ?= 8

# cpp：dtc 的预处理约定；通用 dt-bindings 从内核树取，xring 绑定在本工程 include/
CPPFLAGS := -nostdinc -undef -D__DTS__ -x assembler-with-cpp \
            -I$(ROOT)/include -I$(ROOT)/dts \
            -I$(KERNEL)/include -I$(KERNEL)/arch/arm64/include

V_SRCS := $(shell find $(ROOT)/dts -name '*.dts' -o -name '*.dtsi' -o -name '*.dtso')
V_BASE := $(B)/v/O1_basic.dtb
V_OVL  := $(B)/v/o2s_phone_overlay.dtbo
B_BASE := $(B)/b/base.dtb
B_OVL  := $(B)/b/o2s_phone_overlay.dtbo

.PHONY: all v b dtboimg vendor_boot verify kbuild-v kbuild-b clean help
.DEFAULT_GOAL := all

all: v b
v: $(V_BASE) $(V_OVL)
b: $(B_BASE) $(B_OVL)

$(B)/v/O1_basic.dtb: $(V_SRCS)
	@mkdir -p $(@D)
	$(CPP) $(CPPFLAGS) $(ROOT)/dts/soc/O1_basic.dts -o $@.pp
	$(DTC) -q -@ -I dts -O dtb -o $@ $@.pp 2>$@.dtc.log

$(B)/v/o2s_phone_overlay.dtbo: $(V_SRCS)
	@mkdir -p $(@D)
	$(CPP) $(CPPFLAGS) $(ROOT)/dts/overlay/product/phone/phone_o2s/o2s_phone_overlay.dtso -o $@.pp
	$(DTC) -q -@ -I dts -O dtb -o $@ $@.pp 2>$@.dtc.log

# B 基线是从二进制还原的单文件 DTS，没有 include 依赖
$(B)/b/base.dtb: $(ROOT)/dts-b/base.dts
	@mkdir -p $(@D)
	$(DTC) -q -@ -I dts -O dtb -o $@ $< 2>$@.dtc.log

$(B)/b/o2s_phone_overlay.dtbo: $(ROOT)/dts-b/o2s_phone_overlay.dts
	@mkdir -p $(@D)
	$(DTC) -q -@ -I dts -O dtb -o $@ $< 2>$@.dtc.log

# dtbo.img：默认用设备 dtbo_a 里 8 个条目原样重打，验证容器同构
dtboimg:
	unset PYTHONHOME PYTHONPATH && python3 $(ROOT)/scripts/mkdtboimg.py \
	  --out $(B)/dtbo-repacked.img \
	  $(foreach f,$(sort $(wildcard $(STOCK)/dtbo-device/*.dtbo)),--entry $(f))

# 保留其余 7 个 entry，只把 dijun 命中的 0x090f0000 换成我们重编的那份
dtboimg-b:
	@set -e; unset PYTHONHOME PYTHONPATH; args=""; \
	for f in $(STOCK)/dtbo-device/*.dtbo; do \
	  case "$$f" in *090f0000*) f=$(B)/b/o2s_phone_overlay.dtbo;; esac; \
	  args="$$args --entry $$f"; done; \
	python3 $(ROOT)/scripts/mkdtboimg.py --out $(B)/dtbo-b.img $$args

vendor_boot:
	DTB=$(B)/b/base.dtb bash $(ROOT)/scripts/pack-vendor_boot.sh

# 用内核树自身的 kbuild 编（外部设备树，不改内核树）
kbuild-v:
	@test -n "$(KDIR)" || { echo "用法: make kbuild-v KDIR=<内核树>"; exit 2; }
	@set -e; unset PYTHONHOME PYTHONPATH; \
	O=$$(mktemp -d <home>/dijun-dts-kbuild.XXXXXX); \
	D=$$(mktemp -d <home>/dijun-dts-ext.XXXXXX); \
	cp -a $(ROOT)/dts $$D/dts; cp -a $(ROOT)/include $$D/include; \
	make -C $(KDIR) O=$$O ARCH=arm64 LLVM=1 olddefconfig; \
	make -C $(KDIR) O=$$O ARCH=arm64 LLVM=1 dtstree=$$D/dts \
	  DTC_INCLUDE="$$D/include $(KDIR)/scripts/dtc/include-prefixes" dtbs -j$(JOBS); \
	echo "内核树产物在 $$D/dts（外部 dtstree 的 obj=src），O=$$O"; \
	find $$D/dts \( -name '*.dtb' -o -name '*.dtbo' \) -printf '%s %p\n'

kbuild-b:
	@test -n "$(KDIR)" || { echo "用法: make kbuild-b KDIR=<内核树>"; exit 2; }
	@set -e; unset PYTHONHOME PYTHONPATH; \
	O=$$(mktemp -d <home>/dijun-dts-kbuild.XXXXXX); \
	D=$$(mktemp -d <home>/dijun-dts-ext.XXXXXX); \
	cp -a $(ROOT)/dts-b $$D/dts; \
	make -C $(KDIR) O=$$O ARCH=arm64 LLVM=1 olddefconfig; \
	make -C $(KDIR) O=$$O ARCH=arm64 LLVM=1 dtstree=$$D/dts \
	  DTC_INCLUDE="$(KDIR)/scripts/dtc/include-prefixes" dtbs -j$(JOBS); \
	echo "内核树产物在 $$D/dts，O=$$O"; \
	find $$D/dts \( -name '*.dtb' -o -name '*.dtbo' \) -printf '%s %p\n'

verify:
	bash $(ROOT)/scripts/verify.sh

help:
	@grep -E '^#   ' Makefile
