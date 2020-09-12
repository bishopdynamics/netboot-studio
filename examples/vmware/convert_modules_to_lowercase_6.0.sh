#!/bin/bash
# Netboot Studio
# by James Bishop (jamesbishop2006@gmail.com)

# this is specifically for esxi 6.0
# rename kernel and all modules from boot.cfg to lowercase

FILE_LIST="tboot.b00
b.b00
jumpstrt.gz
useropts.gz
k.b00
chardevs.b00
a.b00
user.b00
uc_intel.b00
uc_amd.b00
sb.v00
s.v00
mtip32xx.v00
ata_pata.v00
ata_pata.v01
ata_pata.v02
ata_pata.v03
ata_pata.v04
ata_pata.v05
ata_pata.v06
ata_pata.v07
block_cc.v00
ehci_ehc.v00
elxnet.v00
emulex_e.v00
weaselin.t00
esx_dvfi.v00
ima_qla4.v00
ipmi_ipm.v00
ipmi_ipm.v01
ipmi_ipm.v02
lpfc.v00
lsi_mr3.v00
lsi_msgp.v00
lsu_hp_h.v00
lsu_lsi_.v00
lsu_lsi_.v01
lsu_lsi_.v02
lsu_lsi_.v03
lsu_lsi_.v04
misc_cni.v00
misc_dri.v00
net_bnx2.v00
net_bnx2.v01
net_cnic.v00
net_e100.v00
net_e100.v01
net_enic.v00
net_forc.v00
net_igb.v00
net_ixgb.v00
net_mlx4.v00
net_mlx4.v01
net_nx_n.v00
net_tg3.v00
net_vmxn.v00
nmlx4_co.v00
nmlx4_en.v00
nmlx4_rd.v00
nvme.v00
ohci_usb.v00
qlnative.v00
rste.v00
sata_ahc.v00
sata_ata.v00
sata_sat.v00
sata_sat.v01
sata_sat.v02
sata_sat.v03
sata_sat.v04
scsi_aac.v00
scsi_adp.v00
scsi_aic.v00
scsi_bnx.v00
scsi_bnx.v01
scsi_fni.v00
scsi_hps.v00
scsi_ips.v00
scsi_meg.v00
scsi_meg.v01
scsi_meg.v02
scsi_mpt.v00
scsi_mpt.v01
scsi_mpt.v02
scsi_qla.v00
uhci_usb.v00
xhci_xhc.v00
tools.t00
xorg.v00
net55-r8.t00
imgdb.tgz
imgpayld.tgz"

for FILE_LOWER in $FILE_LIST; do
	FILE_UPPER="${FILE_LOWER^^}"
	echo "moving $FILE_UPPER -> $FILE_LOWER"
	mv "$FILE_UPPER" "$FILE_LOWER"
done


