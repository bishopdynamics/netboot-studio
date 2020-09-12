#!/bin/bash

########################### vars populated by runner
OPT_NAME="%s"
OPT_ISO="%s"
OPT_CREATE_UNATTENDED="%s"
OPT_IMAGE_TYPE="%s"
IMAGES_FOLDER="%s"
PROGRESS_FILE="%s"
HTTP_SERVER="%s"
HTTP_PORT="%s"

function status {
    echo "$1" > ${PROGRESS_FILE}
}


############################################## vars calculated at runtime
TIMESTAMP=$(date '+%%Y-%%m-%%d_%%H:%%M:%%S')
DEST_FOLDER="${IMAGES_FOLDER}/${OPT_NAME}"
SCRIPT_FULL_PATH="${DEST_FOLDER}/netboot.ipxe"
SCRIPT_UNATTENDED_FULL_PATH="${DEST_FOLDER}/netboot-unattended.ipxe"

CFG_FULL_PATH="${DEST_FOLDER}/netboot.cfg"
CFG_UNATTENDED_FULL_PATH="${DEST_FOLDER}/netboot-unattended.cfg"

METADATA_FULL_PATH="${DEST_FOLDER}/metadata.yaml"
ISO_FILE="${ISO_FOLDER}/${OPT_ISO}"

mkdir -p "$DEST_FOLDER"
status 15

############################################## Extract ISO

7z x -o"$DEST_FOLDER" "$ISO_FILE"

# we have to rename everything to lowercase
pushd "$DEST_FOLDER" || exit
FILE_LIST=$(find . -type f)
FOLDER_LIST=$(find . -type d)

for FILE_UPPER in $FILE_LIST; do
	if [ "$FILE_UPPER" != "." ] && [ "$FILE_UPPER" != '..' ]; then
		FILE_LOWER=$(echo "$FILE_UPPER" | tr '[:upper:]' '[:lower:]')
		echo "moving $FILE_UPPER -> $FILE_LOWER"
		mv "$FILE_UPPER" "$FILE_LOWER"
	fi
done

for FOLDER_UPPER in $FOLDER_LIST; do
	if [ "$FOLDER_UPPER" != "." ] && [ "$FOLDER_UPPER" != '..' ]; then
	    FOLDER_LOWER=$(echo "$FOLDER_UPPER" | tr '[:upper:]' '[:lower:]') 
	    echo "moving $FOLDER_UPPER -> $FOLDER_LOWER"
	    mv "$FOLDER_UPPER" "$FOLDER_LOWER"
	fi
done
popd || exit

##################################################################### create netboot.ipxe
status 80
echo "Generating ipxe boot script: $SCRIPT_FULL_PATH"

# header, resolve variables now
cat << END_HEAD > "$SCRIPT_FULL_PATH"
#!ipxe
# Auto-Generated ipxe script for $OPT_IMAGE_TYPE
# Image: $DEST_FOLDER
# Source ISO: $ISO_FILE
# Created: $TIMESTAMP
# Image Type: $OPT_IMAGE_TYPE
# Unattended: False

set image-name $IMAGE_NAME

END_HEAD

status 85

# body, dont resolve any variables
cat << 'END_BODY' >> "$SCRIPT_FULL_PATH"

set image-root http://${next-server}/images/${image-name}

imgfetch ${image-root}/efi/boot/bootx64.efi || goto failed
imgexec bootx64.efi -c ${image-root}/netboot.cfg || goto failed

:failed
echo Failed to boot! hopefully errors are printed above this
echo   make sure that you use the correct architecture
prompt Press any key to reboot
goto reboot

:reboot
reboot
END_BODY


##################################################################### create netboot-unattended.ipxe
if [ "$OPT_CREATE_UNATTENDED" = "True" ]; then
status 87
echo "Generating ipxe boot script: $SCRIPT_UNATTENDED_FULL_PATH"

# header, resolve variables now
cat << END_U_HEAD > "$SCRIPT_UNATTENDED_FULL_PATH"
#!ipxe
# Auto-Generated ipxe script for windows installer
# Image: $DEST_FOLDER
# Source ISO: $ISO_FILE
# Created: $TIMESTAMP
# Image Type: $OPT_IMAGE_TYPE
# Unattended: True

set image-name $IMAGE_NAME
END_U_HEAD

# body, dont resolve any variables
cat << 'END_U_BODY' >> "$SCRIPT_UNATTENDED_FULL_PATH"

set image-root http://${next-server}/images/${image-name}

imgfetch ${image-root}/efi/boot/bootx64.efi || goto failed
imgexec bootx64.efi -c ${image-root}/netboot-unattended.cfg || goto failed

:failed
echo Failed to boot! hopefully errors are printed above this
echo   make sure that you use the correct architecture
prompt Press any key to reboot
goto reboot

:reboot
reboot
END_U_BODY
fi


############################################## create netboot.cfg

NEW_PREFIX="prefix=${HTTP_SERVER}/images/${OPT_NAME}"
NEW_KERNELOPT="kernelopt=runweasel netdevice=vmnic0 bootproto=dhcp ks=${HTTP_SERVER}:${HTTP_PORT}/unattended.cfg"

CFG_ORIGINAL="${DEST_FOLDER}/efi/boot/boot.cfg"


echo "${NEW_PREFIX}" > "${CFG_FULL_PATH}"
cat "$CFG_ORIGINAL" |sed 's/\///g' >> "${CFG_FULL_PATH}"

if [ "$OPT_CREATE_UNATTENDED" = "True" ]; then
	echo "Generating unattended bootscript"
	echo "${NEW_KERNELOPT}" > "${CFG_UNATTENDED_FULL_PATH}"
	cat "${CFG_FULL_PATH}" |grep -v 'kernelopt' >> "${CFG_UNATTENDED_FULL_PATH}"
fi


############################################## create metadata.yaml
status 75
echo "Generating metadata.yaml"

cat << END_M >> "$METADATA_FULL_PATH"
created: "${TIMESTAMP}"
image_type: ${OPT_IMAGE_TYPE}
description: "Auto-Generated image for ${OPT_IMAGE_TYPE}"
END_M


############################################## Done
echo "done generating image"
status 100
