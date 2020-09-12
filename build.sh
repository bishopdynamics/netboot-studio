#!/bin/bash
# Netboot Studio artifact build script

#    This file is part of Netboot Studio, a system for managing netboot clients
#    Copyright (C) 2019 James Bishop (jamesbishop2006@gmail.com)

#   build ipxe binaries

# common functions
source ./common.sh

###################################################################################################################
#######################  constants
###################################################################################################################
IPXE_URL="git://git.ipxe.org/ipxe.git"

MAKE_ARGS="-j4"

# list of ipxe targets to build
# wont build: 
#   bin-i386-efi/ipxe.iso
#   bin-x86_64-efi/ipxe.iso
# but both will build .usb, which can be substitued in most cases
BUILD_TARGET_LIST="
bin-x86_64-pcbios/ipxe.pxe
bin-x86_64-pcbios/ipxe.iso
bin-x86_64-pcbios/ipxe.usb
bin-x86_64-efi/ipxe.efi
bin-x86_64-efi/ipxe.usb
bin-i386-efi/ipxe.efi
bin-i386-efi/ipxe.usb
bin-i386-pcbios/ipxe.pxe
bin-i386-pcbios/ipxe.usb
bin-i386-pcbios/ipxe.iso
"

CURRENT_DIR=$(pwd)
# warning, does not like the spaces in the full path
MENU_FILE="${CURRENT_DIR}/netboot-studio-stage1.ipxe"
BUILD_DIR="${CURRENT_DIR}/dist" # where binaries end up at end of this build

###################################################################################################################
#######################  setup workspce
###################################################################################################################

announce "Preparing to build"

check_deps "make git sed grep mformat perl genisoimage"

# temp workspace for build
WORKSPACE=$(mktemp -d)
cd "${WORKSPACE}"

###################################################################################################################
#######################  We are now in temp workspace, and will stay here until build is complete
###################################################################################################################


###################################################################################################################
#######################  fetch prebuilt wimboot binary
###################################################################################################################
announce "fetching latest wimboot"

wget http://git.ipxe.org/releases/wimboot/wimboot-latest.zip
unzip wimboot-latest.zip
WIMBOOT_FOLDER=$(find . -type d -name 'wimboot-*')
cd_to "${WIMBOOT_FOLDER}"
do_cmd cp "wimboot" "${WORKSPACE}/wimboot"
cd "${WORKSPACE}"


###################################################################################################################
#######################  build ipxe binaries
###################################################################################################################

# clone ipxe latest source always
echo "cloning ipxe git repo"
do_cmd git clone "$IPXE_URL"
cd_to ipxe/src

# fix for stupid PIE GCC bug: http://lists.ipxe.org/pipermail/ipxe-devel/2018-January/006008.html
echo  "CFLAGS   += -fno-pie" >> arch/x86/Makefile.pcbios || exit 1
echo  "LDFLAGS    += -no-pie" >> arch/x86/Makefile.pcbios || exit 1


function enable_build_option {
  # apparently this is the right way to do this: http://ipxe.org/gsoc/nfs
  local OPTION_NAME="$1"
  local FILE_NAME="$2"
  echo "Applying option: $OPTION_NAME in $FILE_NAME"
  echo "#define ${OPTION_NAME}" >> config/local/${FILE_NAME}
}


announce "applying build options"

enable_build_option "DOWNLOAD_PROTO_HTTPS" "general.h"
enable_build_option "DOWNLOAD_PROTO_NFS" "general.h"
enable_build_option "PCI_CMD" "general.h"
enable_build_option "IMAGE_PNG" "general.h"
enable_build_option "CONSOLE_CMD" "general.h"
enable_build_option "IPSTAT_CMD" "general.h"
enable_build_option "PING_CMD" "general.h"
enable_build_option "NSLOOKUP_CMD" "general.h"

enable_build_option "CONSOLE_FRAMEBUFFER" "console.h"

announce "building all targets"

for TARGET in $BUILD_TARGET_LIST; do
    announce_step "Building target: $TARGET"
    do_cmd make ${MAKE_ARGS} "$TARGET" "EMBED=${MENU_FILE}"
done

announce_step "grabbing all the files"
# clear build dir only after successful build
rm -r "${BUILD_DIR}" 2>/dev/null
mkdir -p "$BUILD_DIR"
# put all the built files where we want them
do_cmd cp "${WORKSPACE}/wimboot" "${BUILD_DIR}/wimboot"
do_cmd cp "${WORKSPACE}/ipxe/src/bin-x86_64-pcbios/ipxe.pxe" "${BUILD_DIR}/ipxe-64bit-bios.pxe"
do_cmd cp "${WORKSPACE}/ipxe/src/bin-x86_64-pcbios/ipxe.iso" "${BUILD_DIR}/ipxe-64bit-bios.iso"
do_cmd cp "${WORKSPACE}/ipxe/src/bin-x86_64-pcbios/ipxe.usb" "${BUILD_DIR}/ipxe-64bit-bios.usb"
do_cmd cp "${WORKSPACE}/ipxe/src/bin-x86_64-efi/ipxe.efi" "${BUILD_DIR}/ipxe-64bit-efi.efi"
do_cmd cp "${WORKSPACE}/ipxe/src/bin-x86_64-efi/ipxe.usb" "${BUILD_DIR}/ipxe-64bit-efi.usb"
do_cmd cp "${WORKSPACE}/ipxe/src/bin-i386-efi/ipxe.efi" "${BUILD_DIR}/ipxe-32bit-efi.efi"
do_cmd cp "${WORKSPACE}/ipxe/src/bin-i386-efi/ipxe.usb" "${BUILD_DIR}/ipxe-32bit-efi.usb"
do_cmd cp "${WORKSPACE}/ipxe/src/bin-i386-pcbios/ipxe.pxe" "${BUILD_DIR}/ipxe-32bit-bios.pxe"
do_cmd cp "${WORKSPACE}/ipxe/src/bin-i386-pcbios/ipxe.iso" "${BUILD_DIR}/ipxe-32bit-bios.iso"
do_cmd cp "${WORKSPACE}/ipxe/src/bin-i386-pcbios/ipxe.usb" "${BUILD_DIR}/ipxe-32bit-bios.usb"

announce_step "going back and building nomenu.usb"

do_cmd make ${MAKE_ARGS} bin-x86_64-efi/ipxe.usb
announce_step "grabbing nomenu file"
do_cmd cp "${WORKSPACE}/ipxe/src/bin-x86_64-efi/ipxe.usb" "${BUILD_DIR}/ipxe-64bit-efi-nomenu.usb"

do_cmd cp "${CURRENT_DIR}/VERSION" "${BUILD_DIR}/"

announce_step "calculating md5sums"
cd_to "$BUILD_DIR"
for FILE_NAME in $(ls -1); do 
    md5sum $FILE_NAME |awk '{print $1}' > "${FILE_NAME}.md5"
done

cd_to "$CURRENT_DIR"
announce "done building images"
