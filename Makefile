# dijun（小米 15S Pro / XRING O1 / 25042PN24C）内核设备树构建入口
#
# 基线：
#   V 基线  dts-oss/6.6.30-android15-v         官方开源参考 DTS（Android V / 6.6.30）
#   B 基线  dts-reconstructed/6.6.118-os3      设备 OS3 分区二进制无损还原
#   B 基线  dts-reconstructed/6.18.21-os4.0.0.19  设备 OS4.0.0.19 分区二进制无损还原
#   B 基线  dts-reconstructed/6.18.21-os4.0.4.0   设备 OS4.0.4.0 分区二进制无损还原（当前基线 dts-current）
#   增量层  overlays/custom/*.dtso             基于现行基线的增量 overlay 补丁
#
# 常用目标：
#   make all            编 V 与全部三代 B 基线 + 自定义 overlays
#   make b              编全部三代 B 基线（base.dtb + 全部 8 个 dtbo，不需要内核树）
#   make overlays       编 overlays/custom/*.dtso -> build/overlays/*.dtbo
#   make verify         离线全量验收（回编哈希、结构 diff、fdtoverlay 合并、容器重打、脚本与工具自检）
#   make dtboimg        用 OS3 的 8 个 entry 重打 dtbo.img
#   make dtboimg-os4-4019  用 OS4.0.0.19 的 8 个 entry 重打 dtbo.img
#   make dtboimg-os4    用 OS4.0.4.0 的 8 个 entry 重打 dtbo.img
#   make vendor_boot    需配合 STOCK_VENDOR_BOOT=<stock.img> 调用 pack-vendor_boot.sh
#   make audit          运行公开合规与 Git 历史脱敏审计门禁
#   make kbuild-v KDIR=<内核树>   用内核树自身 kbuild 编 V 基线（dtstree= 外部设备树）
#   make kbuild-b KDIR=<内核树> [BVER=6.18.21-os4.0.4.0]  用内核树编指定 B 基线
#   make clean          清理 build/ 目录

ROOT     := $(abspath $(dir $(lastword $(MAKEFILE_LIST))))
B        := $(ROOT)/build
BASELINE := $(ROOT)/baseline
V_DIR    := $(ROOT)/dts-oss/6.6.30-android15-v
KERNEL   ?=
BVER     ?= 6.18.21-os4.0.4.0
DTC      ?= dtc
CPP      ?= cpp
JOBS     ?= 8

CPPFLAGS := -nostdinc -undef -D__DTS__ -x assembler-with-cpp \
            -I$(ROOT)/include -I$(V_DIR) \
            -I$(KERNEL)/include -I$(KERNEL)/arch/arm64/include
OVL_CPPFLAGS := -nostdinc -undef -D__DTS__ -x assembler-with-cpp -I$(ROOT)/include

V_SRCS := $(shell find $(V_DIR) -name '*.dts' -o -name '*.dtsi' -o -name '*.dtso')
V_BASE := $(B)/v/O1_basic.dtb
V_OVL  := $(B)/v/o2s_phone_overlay.dtbo

B_VERS := 6.6.118-os3 6.18.21-os4.0.0.19 6.18.21-os4.0.4.0
B_BASES := $(foreach v,$(B_VERS),$(B)/b/$(v)/base.dtb)
B_DTBO_SRCS := $(foreach v,$(B_VERS),$(sort $(wildcard $(ROOT)/dts-reconstructed/$(v)/dtbo/*.dts)))
B_DTBOS := $(patsubst $(ROOT)/dts-reconstructed/%.dts,$(B)/b/%.dtbo,$(B_DTBO_SRCS))
B_O2S_LINKS := $(foreach v,$(B_VERS),$(B)/b/$(v)/o2s_phone_overlay.dtbo)
B_TARGETS := $(B_BASES) $(B_DTBOS) $(B_O2S_LINKS)

OVL_SRCS := $(sort $(wildcard $(ROOT)/overlays/custom/*.dtso))
OVL_TARGETS := $(patsubst $(ROOT)/overlays/custom/%.dtso,$(B)/overlays/%.dtbo,$(OVL_SRCS))

.PHONY: all v b overlays dtboimg dtboimg-os3 dtboimg-os4-4019 dtboimg-os4 vendor_boot verify audit kbuild-v kbuild-b clean help
.DEFAULT_GOAL := all

all: v b overlays
v: $(V_BASE) $(V_OVL)
b: $(B_TARGETS)
overlays: $(OVL_TARGETS)

$(B)/v/O1_basic.dtb: $(V_SRCS)
	@test -n "$(KERNEL)" || { echo "需要 KERNEL=<内核源码树>（仅取 include/dt-bindings）"; exit 2; }
	@mkdir -p $(@D)
	$(CPP) $(CPPFLAGS) $(V_DIR)/soc/O1_basic.dts -o $@.pp
	$(DTC) -q -@ -I dts -O dtb -o $@ $@.pp 2>$@.dtc.log

$(B)/v/o2s_phone_overlay.dtbo: $(V_SRCS)
	@test -n "$(KERNEL)" || { echo "需要 KERNEL=<内核源码树>（仅取 include/dt-bindings）"; exit 2; }
	@mkdir -p $(@D)
	$(CPP) $(CPPFLAGS) $(V_DIR)/overlay/product/phone/phone_o2s/o2s_phone_overlay.dtso -o $@.pp
	$(DTC) -q -@ -I dts -O dtb -o $@ $@.pp 2>$@.dtc.log

$(B)/b/%/base.dtb: $(ROOT)/dts-reconstructed/%/base.dts
	@mkdir -p $(@D)
	$(DTC) -q -@ -I dts -O dtb -o $@ $< 2>$@.dtc.log

$(B)/b/%.dtbo: $(ROOT)/dts-reconstructed/%.dts
	@mkdir -p $(@D)
	$(DTC) -q -@ -I dts -O dtb -o $@ $< 2>$@.dtc.log

$(B)/b/%/o2s_phone_overlay.dtbo: $(B)/b/%/dtbo/entry05_id090f0000_rev0.dtbo
	@mkdir -p $(@D)
	ln -sfn dtbo/entry05_id090f0000_rev0.dtbo $@

$(B)/overlays/%.dtbo: $(ROOT)/overlays/custom/%.dtso
	@mkdir -p $(@D)
	$(CPP) $(OVL_CPPFLAGS) $< -o $@.pp
	$(DTC) -q -@ -I dts -O dtb -o $@ $@.pp 2>$@.dtc.log

dtboimg: dtboimg-os3

dtboimg-os3:
	@mkdir -p $(B)
	unset PYTHONHOME PYTHONPATH && python3 $(ROOT)/tools/mkdtboimg.py --out $(B)/dtbo-6.6.118-os3.img \
	  $(foreach f,$(sort $(wildcard $(BASELINE)/6.6.118-os3/dtbo/*.dtbo)),--entry $(f))

dtboimg-os4-4019:
	@mkdir -p $(B)
	unset PYTHONHOME PYTHONPATH && python3 $(ROOT)/tools/mkdtboimg.py --out $(B)/dtbo-6.18.21-os4.0.0.19.img \
	  $(foreach f,$(sort $(wildcard $(BASELINE)/6.18.21-os4.0.0.19/dtbo/*.dtbo)),--entry $(f))

dtboimg-os4:
	@mkdir -p $(B)
	unset PYTHONHOME PYTHONPATH && python3 $(ROOT)/tools/mkdtboimg.py --out $(B)/dtbo-6.18.21-os4.0.4.0.img \
	  $(foreach f,$(sort $(wildcard $(BASELINE)/6.18.21-os4.0.4.0/dtbo/*.dtbo)),--entry $(f))

vendor_boot: $(B)/b/$(BVER)/base.dtb
	@test -n "$(STOCK_VENDOR_BOOT)" || { echo "需要 STOCK_VENDOR_BOOT=<原厂 vendor_boot.img>"; exit 2; }
	bash $(ROOT)/scripts/pack-vendor_boot.sh --stock-img "$(STOCK_VENDOR_BOOT)" --dtb "$(B)/b/$(BVER)/base.dtb"

verify:
	bash $(ROOT)/scripts/verify.sh

audit:
	bash $(ROOT)/scripts/audit-public-ready.sh --check-history

kbuild-v:
	@test -n "$(KDIR)" || { echo "用法: make kbuild-v KDIR=<内核树>"; exit 2; }
	@set -e; unset PYTHONHOME PYTHONPATH; \
	TMP_BASE="$${TMPDIR:-$${XDG_CACHE_HOME:-$$HOME/.cache}/dsh-tmp}"; mkdir -p "$$TMP_BASE"; \
	O=$$(mktemp -d -p "$$TMP_BASE" dijun-dts-kbuild.XXXXXX); \
	D=$$(mktemp -d -p "$$TMP_BASE" dijun-dts-ext.XXXXXX); \
	cp -a $(V_DIR) $$D/dts; cp -a $(ROOT)/include $$D/include; \
	make -C $(KDIR) O=$$O ARCH=arm64 LLVM=1 olddefconfig; \
	make -C $(KDIR) O=$$O ARCH=arm64 LLVM=1 dtstree=$$D/dts \
	  DTC_INCLUDE="$$D/include $(KDIR)/scripts/dtc/include-prefixes" dtbs -j$(JOBS); \
	echo "产物在 $$D/dts，O=$$O"

kbuild-b:
	@test -n "$(KDIR)" || { echo "用法: make kbuild-b KDIR=<内核树> [BVER=6.18.21-os4.0.4.0]"; exit 2; }
	@set -e; unset PYTHONHOME PYTHONPATH; \
	TMP_BASE="$${TMPDIR:-$${XDG_CACHE_HOME:-$$HOME/.cache}/dsh-tmp}"; mkdir -p "$$TMP_BASE"; \
	O=$$(mktemp -d -p "$$TMP_BASE" dijun-dts-kbuild-b.XXXXXX); \
	D=$$(mktemp -d -p "$$TMP_BASE" dijun-dts-ext-b.XXXXXX); \
	cp -a $(ROOT)/dts-reconstructed/$(BVER) $$D/dts; \
	make -C $(KDIR) O=$$O ARCH=arm64 LLVM=1 olddefconfig; \
	make -C $(KDIR) O=$$O ARCH=arm64 LLVM=1 dtstree=$$D/dts dtbs -j$(JOBS); \
	echo "产物在 $$D/dts，O=$$O"

clean:
	unset PYTHONHOME PYTHONPATH && python3 -c "import os, shutil; p='$(B)'; os.path.isdir(p) and shutil.rmtree(p)"

help:
	@grep -E '^#   ' Makefile
