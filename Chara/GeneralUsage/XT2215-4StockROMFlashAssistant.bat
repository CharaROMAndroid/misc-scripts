fastboot getvar max-sparse-size
fastboot oem fb_mode_set
fastboot flash partition gpt.bin
fastboot flash bootloader bootloader.img
fastboot flash vbmeta vbmeta.img
fastboot flash vbmeta_system vbmeta_system.img
fastboot flash radio radio.img
fastboot flash bluetooth BTFM.bin
fastboot flash dsp dspso.bin
fastboot flash logo logo.bin
fastboot flash boot boot.img
fastboot flash vendor_boot vendor_boot.img
fastboot flash dtbo dtbo.img
fastboot flash super super.img_sparsechunk.0
fastboot flash super super.img_sparsechunk.1
fastboot flash super super.img_sparsechunk.2
fastboot flash super super.img_sparsechunk.3
fastboot flash super super.img_sparsechunk.4
fastboot flash super super.img_sparsechunk.5
fastboot flash super super.img_sparsechunk.6
fastboot flash super super.img_sparsechunk.7
fastboot flash super super.img_sparsechunk.8
fastboot flash super super.img_sparsechunk.9
fastboot flash super super.img_sparsechunk.10
fastboot flash super super.img_sparsechunk.11
fastboot flash super super.img_sparsechunk.12
fastboot flash super super.img_sparsechunk.13
fastboot flash super super.img_sparsechunk.14
fastboot flash super super.img_sparsechunk.15
fastboot flash super super.img_sparsechunk.16
fastboot flash super super.img_sparsechunk.17
fastboot erase carrier
fastboot erase userdata
fastboot erase metadata
fastboot erase ddr
fastboot oem fb_mode_clear