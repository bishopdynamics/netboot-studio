#!/bin/bash
# Netboot Studio artifact deployment script

#    This file is part of Netboot Studio, a system for managing netboot clients
#    Copyright (C) 2019 James Bishop (jamesbishop2006@gmail.com)

# put ipxe binaries and assets in tftp root

# source common functions
source ./common.sh

announce "deploying most recent build to tftp-root"

CURRENT_DIR=$(pwd)
BUILD_DIR="${CURRENT_DIR}/dist"
TFTP_ROOT="/opt/tftp-root"

announce_step "copying files from build stage"
do_cmd mkdir -p "$TFTP_ROOT"
do_cmd cp "${BUILD_DIR}/wimboot" "${TFTP_ROOT}/"
do_cmd cp "${BUILD_DIR}/ipxe-64bit-bios.pxe" "${TFTP_ROOT}/"
do_cmd cp "${BUILD_DIR}/ipxe-64bit-efi.efi" "${TFTP_ROOT}/"
do_cmd cp "${BUILD_DIR}/ipxe-32bit-efi.efi" "${TFTP_ROOT}/"
do_cmd cp "${BUILD_DIR}/ipxe-32bit-bios.pxe" "${TFTP_ROOT}/"

# in most cases the .usb works fine as .iso so we copy as both for convenience
do_cmd cp "${BUILD_DIR}/ipxe-64bit-efi.usb" "${TFTP_ROOT}/"
do_cmd cp "${BUILD_DIR}/ipxe-64bit-efi.usb" "${TFTP_ROOT}/ipxe-64bit-efi.iso"
do_cmd cp "${BUILD_DIR}/ipxe-32bit-efi.usb" "${TFTP_ROOT}/"
do_cmd cp "${BUILD_DIR}/ipxe-32bit-efi.usb" "${TFTP_ROOT}/ipxe-32bit-efi.iso"
do_cmd cp "${BUILD_DIR}/ipxe-32bit-bios.iso" "${TFTP_ROOT}/"
do_cmd cp "${BUILD_DIR}/ipxe-32bit-bios.usb" "${TFTP_ROOT}/"
do_cmd cp "${BUILD_DIR}/ipxe-64bit-efi-nomenu.usb" "${TFTP_ROOT}/"
do_cmd cp "${CURRENT_DIR}/VERSION" "${TFTP_ROOT}/"
do_cmd cp -r "${CURRENT_DIR}/boot-images" "${TFTP_ROOT}/"

announce_step "setting file permissions"
# make sure files that need to be served are 666
do_cmd sudo chmod 666 "${TFTP_ROOT}/ipxe-64bit-bios.pxe"
do_cmd sudo chmod 666 "${TFTP_ROOT}/ipxe-64bit-efi.efi"
do_cmd sudo chmod 666 "${TFTP_ROOT}/ipxe-32bit-efi.efi"
do_cmd sudo chmod 666 "${TFTP_ROOT}/ipxe-32bit-bios.pxe"

# make sure all files are world-readable in tftp-root
pushd "$TFTP_ROOT"
do_cmd find . -exec chmod a+r {} \;
popd

do_cmd sudo chmod 777 "$TFTP_ROOT"
do_cmd sudo chown -R james:www-data "$TFTP_ROOT"

announce_step "restarting tftp server"
do_cmd sudo systemctl restart tftpd-hpa.service 

announce "done deploying"