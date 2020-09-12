#!/usr/local/bin/python3
# Netboot Studio service - CreateImage functions

#    This file is part of Netboot Studio, a system for managing netboot clients
#    Copyright (C) 2019 James Bishop (jamesbishop2006@gmail.com)

# ignore rules:
#   docstring
#   snakecasevars
#   too-broad-exception
#   line-too-long
#   too-many-branches
#   too-many-statements
#pylint: disable=C0111,C0103,W0703,C0301,R0912,R0915

import os
import time
import subprocess

HTTP_PORT = 6161
HTTP_SERVER = 'http://192.168.1.188'
LOCAL_STORAGE_FOLDER = '/opt/tftp-root'

ISO_FOLDER = '%s/iso' % LOCAL_STORAGE_FOLDER
IMAGES_FOLDER = '%s/images' % LOCAL_STORAGE_FOLDER
JOB_STATUS_FOLDER = '/tmp/netboot-studio-jobs'
LOG_FILE = '/tmp/netboot-studio.log'

def logmessage(msg):
    timestamp = time.asctime()
    print('%s - %s' % (timestamp, msg))
    with open(LOG_FILE, 'at', encoding='utf-8') as f:
        f.write('%s - %s\n' % (timestamp, msg))

# helper for testing
def WriteJobProgress(job_id, progress):
    job_folder = '%s/%s' % (JOB_STATUS_FOLDER, job_id)
    job_file_progress = '%s/progress' % (job_folder)
    with open(job_file_progress, 'wt', encoding='utf-8') as f:
        f.write('%s' % progress)


def CreateImage_Windows(job_id, input_data):
    logmessage('creating a windows image')
    try:
        if not os.path.exists('%s/%s' % (ISO_FOLDER, input_data['iso'])):
            logmessage('ERROR: iso does not exist: %s/%s' % (ISO_FOLDER, input_data['iso']))
            return
        job_folder = '%s/%s' % (JOB_STATUS_FOLDER, job_id)
        script_file = '%s/jobscript.sh' % job_folder
        progress_file = '%s/progress' % job_folder
        log_file_stdout = '%s/log-stdout.txt' % job_folder
        log_file_stderr = '%s/log-stderr.txt' % job_folder
        script_content = '''

########################### vars populated by runner
OPT_NAME="%s"
OPT_ISO="%s"
OPT_CREATE_UNATTENDED="%s"
OPT_IMAGE_TYPE="%s"
IMAGES_FOLDER="%s"
ISO_FOLDER="%s"
PROGRESS_FILE="%s"

function status {
    echo "$1" > ${PROGRESS_FILE}
}

function status_fail {
    echo " [ FAIL ]"
    exit 1
}

function do_cmd {
    local COMMAND
    COMMAND="$@"
    echo "${COMMON_PREFIX} Running command: $COMMAND"
    $COMMAND || status_fail
    echo "${COMMON_PREFIX} Done"
}

ISO_FILE="${ISO_FOLDER}/${OPT_ISO}"
IMAGE_NAME="$OPT_NAME"

STORAGE_SERVER="192.168.1.188"
PERMS_USER="james"
PERMS_GROUP="dialout"

# various root folders
IMAGES_FOLDER="/opt/tftp-root/images"
# have to escape both \\ chars at beginning
SMB_FOLDER="\\\\\\\\${STORAGE_SERVER}\\netboot\\images"
FULL_SMB_PATH="${SMB_FOLDER}\\\\${IMAGE_NAME}"

TIMESTAMP=$(date '+%%Y-%%m-%%d_%%H:%%M:%%S')
DEST_FOLDER="${IMAGES_FOLDER}/${IMAGE_NAME}"
SCRIPT_FULL_PATH="${DEST_FOLDER}/netboot.ipxe"
SCRIPT_UNATTENDED_FULL_PATH="${DEST_FOLDER}/netboot-unattended.ipxe"

METADATA_FULL_PATH="${DEST_FOLDER}/metadata.yaml"


if [ -d "$DEST_FOLDER" ]; then
    # folder exists, no refresh flag
    echo "desination folder already exists, please delete it and try again"
    echo "folder: $DEST_FOLDER"
    exit 1
fi

echo "$TIMESTAMP - Preparing an image for netboot"

#################################### extract iso using 7z
echo "extracting [$ISO_FILE] to [$DEST_FOLDER]"
status 0
do_cmd mkdir -p "$DEST_FOLDER"
do_cmd 7z x -o"$DEST_FOLDER" "$ISO_FILE"


#################################### create mount.cmd and winpeshl.ini
echo "generating winpeshl.ini and mount.cmd"

# note that we call cmd.exe after mount.cmd, as a fallback shell in case something fails
# if startnet.cmd hangs and we close the window, then mount.cmd will fail and close, and then a prompt will appear
# if mount.cmd hangs and we close the window, then a prompt will appear
# if mount.cmd works as intended, cmd.exe never gets a chance to run

status 60

cat << 'END_WINPESHLINI' > "${DEST_FOLDER}/winpeshl.ini"
[LaunchApps]
"startnet.cmd"
"mount.cmd"
"cmd.exe"
END_WINPESHLINI

status 65

cat << END_STARTNETCMD > "${DEST_FOLDER}/startnet.cmd"
@echo off
echo if wpeinit fails, you will be dropped to a command prompt
echo this might take a minute...
@echo on
wpeinit
END_STARTNETCMD

status 70

cat << END_MOUNTCMD > "${DEST_FOLDER}/mount.cmd"
ipconfig
@echo off
echo
echo
echo if any of this fails, you will be dropped to a command prompt
echo this might take a minute...
@echo on
net use s: ${FULL_SMB_PATH} foo /user:bar
@echo off
echo checking for unattend.xml
if exist x:\\windows\\system32\\unattend.xml (
    echo using x:\\windows\\system32\\unattend.xml
    echo this might take a minute...
    @echo on
    s:\\sources\\setup.exe /unattend:x:\\windows\\system32\\unattend.xml
) else (
    echo unattend.xml does not exist
    echo this might take a minute...    
    @echo on
    s:\\sources\\setup.exe
)

END_MOUNTCMD

#################################### Set permissions

status 75

echo "correcting file permissions"
# for windows installer to work, all dll & exe files need to be marked executable

pushd "$DEST_FOLDER"
# this is obnoxious, but without x nothing is reachable in apache
do_cmd find . -exec chmod a+rx {} \\;
popd
# make sure tftp-root has correct perms after all this
# TODO username and group are hardcoded
do_cmd sudo chmod 777 "$DEST_FOLDER"
do_cmd sudo chown -R ${PERMS_USER}:${PERMS_GROUP} "$DEST_FOLDER"


#################################### generate the ipxe script

status 80

echo "Generating ipxe boot script: $SCRIPT_FULL_PATH"

# header, resolve variables now
cat << END_HEAD > "$SCRIPT_FULL_PATH"
#!ipxe
# Auto-Generated ipxe script for windows installer
# Image: $DEST_FOLDER
# Source ISO: $ISO_FILE
# Created: $TIMESTAMP
# Image Type: $OPT_IMAGE_TYPE
# Unattended: False

set wim-image-name $IMAGE_NAME
END_HEAD

status 85

# body, dont resolve any variables
cat << 'END_BODY' >> "$SCRIPT_FULL_PATH"

set http-server http://${next-server}
set full-image-path ${http-server}/images/${wim-image-name}

imgload ${http-server}/wimboot || goto failed
imgfetch ${full-image-path}/boot/fonts/segmono_boot.ttf  segmono_boot.ttf ||
imgfetch ${full-image-path}/boot/fonts/segoe_slboot.ttf  segoe_slboot.ttf ||
imgfetch ${full-image-path}/boot/fonts/segoen_slboot.ttf segoen_slboot.ttf ||
imgfetch ${full-image-path}/boot/fonts/wgl4_boot.ttf     wgl4_boot.ttf ||
imgfetch ${full-image-path}/startnet.cmd startnet.cmd || goto failed
imgfetch ${full-image-path}/mount.cmd mount.cmd || goto failed
imgfetch ${full-image-path}/winpeshl.ini winpeshl.ini|| goto failed
imgfetch ${full-image-path}/boot/bcd BCD || goto failed
imgfetch ${full-image-path}/boot/boot.sdi boot.sdi || goto failed
imgfetch -n boot.wim ${full-image-path}/sources/boot.wim boot.wim || goto failed
imgexec || goto failed

:failed
echo Something failed, hopefully errors are printed above this
prompt Press any key to reboot
reboot
END_BODY


if [ "$OPT_CREATE_UNATTENDED" = "True" ]; then
#################################### generate the ipxe script for unattended

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

set wim-image-name $IMAGE_NAME
END_U_HEAD

# body, dont resolve any variables
cat << 'END_U_BODY' >> "$SCRIPT_UNATTENDED_FULL_PATH"

set http-server http://${next-server}
set full-image-path ${http-server}/images/${wim-image-name}

imgload ${http-server}/wimboot || goto failed
imgfetch ${full-image-path}/boot/fonts/segmono_boot.ttf  segmono_boot.ttf ||
imgfetch ${full-image-path}/boot/fonts/segoe_slboot.ttf  segoe_slboot.ttf ||
imgfetch ${full-image-path}/boot/fonts/segoen_slboot.ttf segoen_slboot.ttf ||
imgfetch ${full-image-path}/boot/fonts/wgl4_boot.ttf     wgl4_boot.ttf ||
imgfetch http://${next-server}:6161/unattend.xml?macaddress=${mac} unattend.xml || goto failed
imgfetch ${full-image-path}/startnet.cmd startnet.cmd || goto failed
imgfetch ${full-image-path}/mount.cmd mount.cmd || goto failed
imgfetch ${full-image-path}/winpeshl.ini winpeshl.ini|| goto failed
imgfetch ${full-image-path}/boot/bcd BCD || goto failed
imgfetch ${full-image-path}/boot/boot.sdi boot.sdi || goto failed
imgfetch -n boot.wim ${full-image-path}/sources/boot.wim boot.wim || goto failed
imgexec || goto failed

:failed
echo Something failed, hopefully errors are printed above this
prompt Press any key to reboot
reboot
END_U_BODY
fi

status 95
echo "Generating metadata.yaml"

cat << END_M >> "$METADATA_FULL_PATH"
source_iso: "${ISO_FILE}"
created: "${TIMESTAMP}"
image_type: "${OPT_IMAGE_TYPE}"
description: "Auto-Generated image for ${OPT_IMAGE_TYPE}"
END_M

status 100

echo "Done"
        ''' % (input_data['name'], input_data['iso'], input_data['create_unattended'], input_data['image_type'], IMAGES_FOLDER, ISO_FOLDER, progress_file)
        with open(script_file, 'wt', encoding='utf-8') as f:
            f.write(script_content)
        with open(log_file_stdout, "wb") as out, open(log_file_stderr, "wb") as err:
            subprocess.run(["/bin/bash", script_file], stdout=out, stderr=err)

    except Exception as e:
        logmessage('Unexpected exception while running CreateImage_Windows: %s' % e)



def CreateImage_DebianNetboot(job_id, input_data):
    # {
    #   'name': 'My-Debian_Image',
    #   'release_debian': 'buster',
    #   'arch_debian': '64bit',
    #   'kernel_arguments': 'ipv6.disable=1 IPV6_DISABLE=1 net.ifnames=0 biosdevname=0',
    #   'create_unattended': True,
    #   'image_type': 'debian-netboot-web'
    # }
    try:
        job_folder = '%s/%s' % (JOB_STATUS_FOLDER, job_id)
        script_file = '%s/jobscript.sh' % job_folder
        progress_file = '%s/progress' % job_folder
        log_file_stdout = '%s/log-stdout.txt' % job_folder
        log_file_stderr = '%s/log-stderr.txt' % job_folder
        script_content = '''
########################### vars populated by runner
OPT_NAME="%s"
OPT_RELEASE_DEBIAN="%s"
OPT_ARCH_DEBIAN="%s"
OPT_KERNEL_ARGUMENTS="%s"
OPT_CREATE_UNATTENDED="%s"
OPT_IMAGE_TYPE="%s"
IMAGES_FOLDER="%s"
PROGRESS_FILE="%s"

function status {
    echo "$1" > ${PROGRESS_FILE}
}

############################################## vars calculated at runtime
TIMESTAMP=$(date '+%%Y-%%m-%%d_%%H:%%M:%%S')
DEST_FOLDER="${IMAGES_FOLDER}/${OPT_NAME}"
SCRIPT_FULL_PATH="${DEST_FOLDER}/netboot.ipxe"
SCRIPT_UNATTENDED_FULL_PATH="${DEST_FOLDER}/netboot-unattended.ipxe"
METADATA_FULL_PATH="${DEST_FOLDER}/metadata.yaml"
IMAGE_SOURCE_URL="http://http.us.debian.org/debian/dists/${OPT_RELEASE_DEBIAN}/main/installer-${OPT_ARCH_DEBIAN}/current/images/netboot/debian-installer/${OPT_ARCH_DEBIAN}"

mkdir -p "$DEST_FOLDER"
status 15

#################################### generate the ipxe script
echo "Generating ipxe boot script: $SCRIPT_FULL_PATH"

# header, resolve variables now
cat << END_HEAD > "$SCRIPT_FULL_PATH"
#!ipxe
# Auto-Generated ipxe script for ${OPT_IMAGE_TYPE}
# Image: ${DEST_FOLDER}
# Created: ${TIMESTAMP}
# Image Type: ${OPT_IMAGE_TYPE}
# Unattended: False

set image-source-url $IMAGE_SOURCE_URL
set extra-kernel-args $OPT_KERNEL_ARGUMENTS
END_HEAD

# body, dont resolve any variables
cat << 'END_BODY' >> "$SCRIPT_FULL_PATH"

set this-image-base ${image-source-url}
set this-image-kernel linux
set this-image-initrd initrd.gz
set this-image-args initrd=${this-image-initrd} vga=788 debian-installer/locale=en_US keymap=us hw-detect/load_firmware=false --- ${extra-kernel-args}

set this-full-kernel-uri ${this-image-base}/${this-image-kernel}
set this-full-initrd-uri ${this-image-base}/${this-image-initrd}
imgfree
imgfetch ${this-full-kernel-uri} || goto boot-failed
imgfetch ${this-full-initrd-uri} || goto boot-failed
imgload ${this-image-kernel} || goto boot-failed
imgargs ${this-image-kernel} ${this-image-args} || goto boot-failed
imgexec || goto boot-failed

:failed
echo Something failed, hopefully errors are printed above this
prompt Press any key to reboot
goto reboot

:boot-failed
echo Failed to boot! hopefully errors are printed above this
echo   make sure that you use the correct architecture
prompt Press any key to reboot
goto reboot

:reboot
reboot
END_BODY

status 50

if [ "$OPT_CREATE_UNATTENDED" = "True" ]; then
#################################### generate the ipxe script for unattended
echo "Generating ipxe boot script: $SCRIPT_UNATTENDED_FULL_PATH"

# header, resolve variables now
cat << END_U_HEAD > "$SCRIPT_UNATTENDED_FULL_PATH"
#!ipxe
# Auto-Generated ipxe script for ${OPT_IMAGE_TYPE}
# Image: ${DEST_FOLDER}
# Created: ${TIMESTAMP}
# Image Type: ${OPT_IMAGE_TYPE}
# Unattended: True

set image-source-url $IMAGE_SOURCE_URL
set extra-kernel-args $OPT_KERNEL_ARGUMENTS
END_U_HEAD

# body, dont resolve any variables
cat << 'END_U_BODY' >> "$SCRIPT_UNATTENDED_FULL_PATH"

set this-preseed-file http://${netboot-server}/unattended.cfg?macaddress=${mac}

set this-image-base ${image-source-url}
set this-image-kernel linux
set this-image-initrd initrd.gz
set this-image-args initrd=${this-image-initrd} vga=788 debian-installer/locale=en_US keymap=us hw-detect/load_firmware=false auto url=${this-preseed-file} --- ${extra-kernel-args}

set this-full-kernel-uri ${this-image-base}/${this-image-kernel}
set this-full-initrd-uri ${this-image-base}/${this-image-initrd}
imgfree
imgfetch ${this-full-kernel-uri} || goto boot-failed
imgfetch ${this-full-initrd-uri} || goto boot-failed
imgload ${this-image-kernel} || goto boot-failed
imgargs ${this-image-kernel} ${this-image-args} || goto boot-failed
imgexec || goto boot-failed

:failed
echo Something failed, hopefully errors are printed above this
prompt Press any key to reboot
goto reboot

:boot-failed
echo Failed to boot! hopefully errors are printed above this
echo   make sure that you use the correct architecture
prompt Press any key to reboot
goto reboot

:reboot
reboot
END_U_BODY
fi
status 75
echo "Generating metadata.yaml"

cat << END_M >> "$METADATA_FULL_PATH"
created: "${TIMESTAMP}"
image_type: ${OPT_IMAGE_TYPE}
description: "Auto-Generated image for ${OPT_IMAGE_TYPE}"
release: ${OPT_RELEASE_DEBIAN}
arch: ${OPT_ARCH_DEBIAN}
END_M

echo "done generating image"
status 100

        ''' % (input_data['name'], input_data['release_debian'], input_data['arch_debian'], input_data['kernel_arguments'], input_data['create_unattended'], input_data['image_type'], IMAGES_FOLDER, progress_file)

        with open(script_file, 'wt', encoding='utf-8') as f:
            f.write(script_content)
        with open(log_file_stdout, "wb") as out, open(log_file_stderr, "wb") as err:
            subprocess.run(["/bin/bash", script_file], stdout=out, stderr=err)

    except Exception as e:
        logmessage('Unexpected exception while running CreateImage_DebianNetboot: %s' % e)



def CreateImage_UbuntuNetboot(job_id, input_data):
    # {
    #   'name': 'My-Debian_Image',
    #   'release_ubuntu': 'xenial',
    #   'arch_debian': 'amd64',
    #   'kernel_arguments': 'ipv6.disable=1 IPV6_DISABLE=1 net.ifnames=0 biosdevname=0',
    #   'create_unattended': True,
    #   'image_type': 'ubuntu-netboot-web'
    # }
    try:
        job_folder = '%s/%s' % (JOB_STATUS_FOLDER, job_id)
        script_file = '%s/jobscript.sh' % job_folder
        progress_file = '%s/progress' % job_folder
        log_file_stdout = '%s/log-stdout.txt' % job_folder
        log_file_stderr = '%s/log-stderr.txt' % job_folder
        script_content = '''
########################### vars populated by runner
OPT_NAME="%s"
OPT_RELEASE_UBUNTU="%s"
OPT_ARCH_DEBIAN="%s"
OPT_KERNEL_ARGUMENTS="%s"
OPT_CREATE_UNATTENDED="%s"
OPT_IMAGE_TYPE="%s"
IMAGES_FOLDER="%s"
PROGRESS_FILE="%s"

function status {
    echo "$1" > ${PROGRESS_FILE}
}

############################################## vars calculated at runtime
TIMESTAMP=$(date '+%%Y-%%m-%%d_%%H:%%M:%%S')
DEST_FOLDER="${IMAGES_FOLDER}/${OPT_NAME}"
SCRIPT_FULL_PATH="${DEST_FOLDER}/netboot.ipxe"
SCRIPT_UNATTENDED_FULL_PATH="${DEST_FOLDER}/netboot-unattended.ipxe"
METADATA_FULL_PATH="${DEST_FOLDER}/metadata.yaml"
IMAGE_SOURCE_URL="http://archive.ubuntu.com/ubuntu/dists/${OPT_RELEASE_UBUNTU}/main/installer-${OPT_ARCH_DEBIAN}/current/images/netboot/ubuntu-installer/${OPT_ARCH_DEBIAN}"

mkdir -p "$DEST_FOLDER"
status 15

#################################### generate the ipxe script
echo "Generating ipxe boot script: $SCRIPT_FULL_PATH"

# header, resolve variables now
cat << END_HEAD > "$SCRIPT_FULL_PATH"
#!ipxe
# Auto-Generated ipxe script for ${OPT_IMAGE_TYPE}
# Image: ${DEST_FOLDER}
# Created: ${TIMESTAMP}
# Image Type: ${OPT_IMAGE_TYPE}
# Unattended: False

set image-source-url $IMAGE_SOURCE_URL
set extra-kernel-args $OPT_KERNEL_ARGUMENTS
END_HEAD

# body, dont resolve any variables
cat << 'END_BODY' >> "$SCRIPT_FULL_PATH"

set this-image-base ${image-source-url}
set this-image-kernel linux
set this-image-initrd initrd.gz
set this-image-args initrd=${this-image-initrd} vga=788 debian-installer/locale=en_US keymap=us hw-detect/load_firmware=false --- ${extra-kernel-args}

set this-full-kernel-uri ${this-image-base}/${this-image-kernel}
set this-full-initrd-uri ${this-image-base}/${this-image-initrd}
imgfree
imgfetch ${this-full-kernel-uri} || goto boot-failed
imgfetch ${this-full-initrd-uri} || goto boot-failed
imgload ${this-image-kernel} || goto boot-failed
imgargs ${this-image-kernel} ${this-image-args} || goto boot-failed
imgexec || goto boot-failed

:failed
echo Something failed, hopefully errors are printed above this
prompt Press any key to reboot
goto reboot

:boot-failed
echo Failed to boot! hopefully errors are printed above this
echo   make sure that you use the correct architecture
prompt Press any key to reboot
goto reboot

:reboot
reboot
END_BODY

status 50

if [ "$OPT_CREATE_UNATTENDED" = "True" ]; then
#################################### generate the ipxe script for unattended
echo "Generating ipxe boot script: $SCRIPT_UNATTENDED_FULL_PATH"

# header, resolve variables now
cat << END_U_HEAD > "$SCRIPT_UNATTENDED_FULL_PATH"
#!ipxe
# Auto-Generated ipxe script for ${OPT_IMAGE_TYPE}
# Image: ${DEST_FOLDER}
# Created: ${TIMESTAMP}
# Image Type: ${OPT_IMAGE_TYPE}
# Unattended: True

set image-source-url $IMAGE_SOURCE_URL
set extra-kernel-args $OPT_KERNEL_ARGUMENTS
END_U_HEAD

# body, dont resolve any variables
cat << 'END_U_BODY' >> "$SCRIPT_UNATTENDED_FULL_PATH"

set this-preseed-file http://${netboot-server}/unattended.cfg?macaddress=${mac}

set this-image-base ${image-source-url}
set this-image-kernel linux
set this-image-initrd initrd.gz
set this-image-args initrd=${this-image-initrd} vga=788 debian-installer/locale=en_US keymap=us hw-detect/load_firmware=false auto url=${this-preseed-file} --- ${extra-kernel-args}

set this-full-kernel-uri ${this-image-base}/${this-image-kernel}
set this-full-initrd-uri ${this-image-base}/${this-image-initrd}
imgfree
imgfetch ${this-full-kernel-uri} || goto boot-failed
imgfetch ${this-full-initrd-uri} || goto boot-failed
imgload ${this-image-kernel} || goto boot-failed
imgargs ${this-image-kernel} ${this-image-args} || goto boot-failed
imgexec || goto boot-failed

:failed
echo Something failed, hopefully errors are printed above this
prompt Press any key to reboot
goto reboot

:boot-failed
echo Failed to boot! hopefully errors are printed above this
echo   make sure that you use the correct architecture
prompt Press any key to reboot
goto reboot

:reboot
reboot
END_U_BODY
fi
status 75
echo "Generating metadata.yaml"

cat << END_M >> "$METADATA_FULL_PATH"
created: "${TIMESTAMP}"
image_type: ${OPT_IMAGE_TYPE}
description: "Auto-Generated image for ${OPT_IMAGE_TYPE}"
release: ${OPT_RELEASE_UBUNTU}
arch: ${OPT_ARCH_DEBIAN}
END_M

echo "done generating image"
status 100

        ''' % (input_data['name'], input_data['release_ubuntu'], input_data['arch_debian'], input_data['kernel_arguments'], input_data['create_unattended'], input_data['image_type'], IMAGES_FOLDER, progress_file)

        with open(script_file, 'wt', encoding='utf-8') as f:
            f.write(script_content)
        with open(log_file_stdout, "wb") as out, open(log_file_stderr, "wb") as err:
            subprocess.run(["/bin/bash", script_file], stdout=out, stderr=err)

    except Exception as e:
        logmessage('Unexpected exception while running CreateImage_UbuntuNetboot: %s' % e)


def CreateImage_UbuntuLive(job_id, input_data):
# {
    #   'name': 'My-Debian_Image',
    #   'iso': 'vmware-something.iso',
    #   'create_unattended': True,
    #   'image_type': 'ubuntu-netboot-web'
    # }
    try:
        job_folder = '%s/%s' % (JOB_STATUS_FOLDER, job_id)
        script_file = '%s/jobscript.sh' % job_folder
        progress_file = '%s/progress' % job_folder
        log_file_stdout = '%s/log-stdout.txt' % job_folder
        log_file_stderr = '%s/log-stderr.txt' % job_folder
        script_content = '''
########################### vars populated by runner
OPT_NAME="%s"
OPT_ISO="%s"
OPT_KERNEL_ARGUMENTS="%s"
OPT_IMAGE_TYPE="%s"
IMAGES_FOLDER="%s"
ISO_FOLDER="%s"
PROGRESS_FILE="%s"

function status {
    echo "$1" > ${PROGRESS_FILE}
}


############################################## vars calculated at runtime
TIMESTAMP=$(date '+%%Y-%%m-%%d_%%H:%%M:%%S')
DEST_FOLDER="${IMAGES_FOLDER}/${OPT_NAME}"
SCRIPT_FULL_PATH="${DEST_FOLDER}/netboot.ipxe"
SCRIPT_UNATTENDED_FULL_PATH="${DEST_FOLDER}/netboot-unattended.ipxe"
METADATA_FULL_PATH="${DEST_FOLDER}/metadata.yaml"
ISO_FILE="${ISO_FOLDER}/${OPT_ISO}"

mkdir -p "$DEST_FOLDER"
status 15

############################################## Extract ISO

7z x -o"$DEST_FOLDER" "$ISO_FILE"

pushd "$DEST_FOLDER" || exit
find . -type d -exec chmod a+rx {} \\;
popd || exit

##################################################################### create netboot.ipxe
status 80
echo "Generating ipxe boot script: $SCRIPT_FULL_PATH"

# header, resolve variables now
cat << END_HEAD > "$SCRIPT_FULL_PATH"
#!ipxe
# Auto-Generated ipxe script for ${OPT_IMAGE_TYPE}
# Image: ${DEST_FOLDER}
# Source ISO: ${ISO_FILE}
# Created: ${TIMESTAMP}
# Image Type: ${OPT_IMAGE_TYPE}
# Unattended: False

set image-name ${OPT_NAME}
set images-folder ${IMAGES_FOLDER}
set extra-kernel-args ${OPT_KERNEL_ARGUMENTS}

END_HEAD

status 85

# body, dont resolve any variables
cat << 'END_BODY' >> "$SCRIPT_FULL_PATH"

# NOTES: 
#   this requires an NFS server, pointed at same root (readonly) as other storages services
#   remember to fix /etc/interfaces during post-install http://ipxe.org/appnote/ubuntu_live

# with nfs, you have to specify the full path. note initial slash, but no trailing slash
set nfs-path ${images-folder}/${image-name}

# for fetching kernel and initrd
set nfs-base nfs://${next-server}

# for kernel arg only
set nfs-root ${next-server}:${nfs-path}

imgload ${nfs-base}${nfs-path}/casper/vmlinuz || goto failed
imgfetch ${nfs-base}${nfs-path}/casper/initrd || goto failed
imgargs vmlinuz initrd=initrd root=/dev/nfs boot=casper netboot=nfs nfsroot=${nfs-root} ip=dhcp systemd.mask=tmp.mount rw toram -- ${extra-kernel-args} || goto failed
imgexec || goto failed

:failed
echo Something failed, hopefully errors are printed above this
prompt Press any key to reboot
reboot

END_BODY


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

        ''' % (input_data['name'], input_data['iso'], input_data['kernel_arguments'], input_data['image_type'], IMAGES_FOLDER, ISO_FOLDER, progress_file)

        with open(script_file, 'wt', encoding='utf-8') as f:
            f.write(script_content)
        with open(log_file_stdout, "wb") as out, open(log_file_stderr, "wb") as err:
            subprocess.run(["/bin/bash", script_file], stdout=out, stderr=err)

    except Exception as e:
        logmessage('Unexpected exception while running CreateImage_UbuntuLive: %s' % e)


def CreateImage_VMware(job_id, input_data):
    # {
    #   'name': 'My-Debian_Image',
    #   'iso': 'vmware-something.iso',
    #   'create_unattended': True,
    #   'image_type': 'ubuntu-netboot-web'
    # }
    try:
        job_folder = '%s/%s' % (JOB_STATUS_FOLDER, job_id)
        script_file = '%s/jobscript.sh' % job_folder
        progress_file = '%s/progress' % job_folder
        log_file_stdout = '%s/log-stdout.txt' % job_folder
        log_file_stderr = '%s/log-stderr.txt' % job_folder
        script_content = '''
########################### vars populated by runner
OPT_NAME="%s"
OPT_ISO="%s"
OPT_CREATE_UNATTENDED="%s"
OPT_IMAGE_TYPE="%s"
IMAGES_FOLDER="%s"
ISO_FOLDER="%s"
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


############################################## Extract ISO

7z x -o"$DEST_FOLDER" "$ISO_FILE"
status 50

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
# so apache sees dirs
find . -type d -exec chmod a+rx {} \\;
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

set image-name $OPT_NAME

END_HEAD


# body, dont resolve any variables
cat << 'END_BODY' >> "$SCRIPT_FULL_PATH"

set image-root http://${next-server}/images/${image-name}

imgfetch ${image-root}/efi/BOOT/BOOTX64.EFI || goto failed
imgexec BOOTX64.EFI -c ${image-root}/netboot.cfg || goto failed

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
status 85
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

set image-name $OPT_NAME
END_U_HEAD

# body, dont resolve any variables
cat << 'END_U_BODY' >> "$SCRIPT_UNATTENDED_FULL_PATH"

set image-root http://${next-server}/images/${image-name}

imgfetch ${image-root}/efi/BOOT/BOOTX64.EFI || goto failed
imgexec BOOTX64.EFI -c ${image-root}/netboot-unattended.cfg || goto failed

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
status 90

NEW_PREFIX="prefix=${HTTP_SERVER}/images/${OPT_NAME}"
NEW_KERNELOPT="kernelopt=runweasel netdevice=vmnic0 bootproto=dhcp ks=${HTTP_SERVER}:${HTTP_PORT}/unattended.cfg"

CFG_ORIGINAL="${DEST_FOLDER}/efi/BOOT/BOOT.CFG"
if [ ! -f "$CFG_ORIGINAL" ]; then
    echo "cant find original BOOT.CFG!"
    exit 1
fi

echo "${NEW_PREFIX}" > "${CFG_FULL_PATH}"
cat "$CFG_ORIGINAL" |sed 's/\\///g' >> "${CFG_FULL_PATH}"


############################################## create netboot-unattended.cfg
if [ "$OPT_CREATE_UNATTENDED" = "True" ]; then
    echo "Generating unattended bootscript"
    echo "${NEW_KERNELOPT}" > "${CFG_UNATTENDED_FULL_PATH}"
    cat "${CFG_FULL_PATH}" |grep -v 'kernelopt' >> "${CFG_UNATTENDED_FULL_PATH}"
fi


############################################## create metadata.yaml
status 95
echo "Generating metadata.yaml"

cat << END_M >> "$METADATA_FULL_PATH"
created: "${TIMESTAMP}"
image_type: ${OPT_IMAGE_TYPE}
description: "Auto-Generated image for ${OPT_IMAGE_TYPE}"
END_M


############################################## Done
echo "done generating image"
status 100

        ''' % (input_data['name'], input_data['iso'], input_data['create_unattended'], input_data['image_type'], IMAGES_FOLDER, ISO_FOLDER, progress_file, HTTP_SERVER, HTTP_PORT)

        with open(script_file, 'wt', encoding='utf-8') as f:
            f.write(script_content)
        with open(log_file_stdout, "wb") as out, open(log_file_stderr, "wb") as err:
            subprocess.run(["/bin/bash", script_file], stdout=out, stderr=err)

    except Exception as e:
        logmessage('Unexpected exception while running CreateImage_VMware: %s' % e)

def CreateImage_GParted(job_id, input_data):
# {
    #   'name': 'My-Debian_Image',
    #   'iso': 'vmware-something.iso',
    #   'create_unattended': True,
    #   'image_type': 'ubuntu-netboot-web'
    # }
    try:
        job_folder = '%s/%s' % (JOB_STATUS_FOLDER, job_id)
        script_file = '%s/jobscript.sh' % job_folder
        progress_file = '%s/progress' % job_folder
        log_file_stdout = '%s/log-stdout.txt' % job_folder
        log_file_stderr = '%s/log-stderr.txt' % job_folder
        script_content = '''
########################### vars populated by runner
OPT_NAME="%s"
OPT_ISO="%s"
OPT_KERNEL_ARGUMENTS="%s"
OPT_IMAGE_TYPE="%s"
IMAGES_FOLDER="%s"
ISO_FOLDER="%s"
PROGRESS_FILE="%s"

function status {
    echo "$1" > ${PROGRESS_FILE}
}


############################################## vars calculated at runtime
TIMESTAMP=$(date '+%%Y-%%m-%%d_%%H:%%M:%%S')
DEST_FOLDER="${IMAGES_FOLDER}/${OPT_NAME}"
SCRIPT_FULL_PATH="${DEST_FOLDER}/netboot.ipxe"
SCRIPT_UNATTENDED_FULL_PATH="${DEST_FOLDER}/netboot-unattended.ipxe"
METADATA_FULL_PATH="${DEST_FOLDER}/metadata.yaml"
ISO_FILE="${ISO_FOLDER}/${OPT_ISO}"

mkdir -p "$DEST_FOLDER"
status 15

############################################## Extract ISO

7z x -o"$DEST_FOLDER" "$ISO_FILE"

pushd "$DEST_FOLDER" || exit
find . -type d -exec chmod a+rx {} \\;
popd || exit

##################################################################### create netboot.ipxe
status 80
echo "Generating ipxe boot script: $SCRIPT_FULL_PATH"

# header, resolve variables now
cat << END_HEAD > "$SCRIPT_FULL_PATH"
#!ipxe
# Auto-Generated ipxe script for ${OPT_IMAGE_TYPE}
# Image: ${DEST_FOLDER}
# Source ISO: ${ISO_FILE}
# Created: ${TIMESTAMP}
# Image Type: ${OPT_IMAGE_TYPE}
# Unattended: False

set image-name ${OPT_NAME}
set extra-kernel-args ${OPT_KERNEL_ARGUMENTS}

END_HEAD

status 85

# body, dont resolve any variables
cat << 'END_BODY' >> "$SCRIPT_FULL_PATH"

set http-server http://${next-server}
set images-root ${http-server}/images

set this-image-base ${images-root}/${image-name}/live
set this-image-kernel vmlinuz
set this-image-initrd initrd.img
set this-image-args initrd=initrd.img boot=live config components union=overlay username=user noswap noeject ip= vga=788 fetch=${this-image-base}/filesystem.squashfs --- ${extra-kernel-args}
show this-image-base
show this-image-kernel
show this-image-initrd
set this-full-kernel-uri ${this-image-base}/${this-image-kernel}
set this-full-initrd-uri ${this-image-base}/${this-image-initrd}
echo xxxxxxxxxxx  starting xxxxxxxxxxx
imgfree
imgfetch ${this-full-kernel-uri} || goto boot-failed
imgfetch ${this-full-initrd-uri} || goto boot-failed
imgload ${this-image-kernel} || goto boot-failed
imgargs ${this-image-kernel} ${this-image-args} || goto boot-failed
imgexec || goto boot-failed


:failed
echo Something failed, hopefully errors are printed above this
prompt Press any key to reboot
goto reboot

:boot-failed
echo Failed to boot! hopefully errors are printed above this
echo   make sure that you use the correct architecture
prompt Press any key to reboot
goto reboot

:reboot
reboot

END_BODY


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

        ''' % (input_data['name'], input_data['iso'], input_data['kernel_arguments'], input_data['image_type'], IMAGES_FOLDER, ISO_FOLDER, progress_file)

        with open(script_file, 'wt', encoding='utf-8') as f:
            f.write(script_content)
        with open(log_file_stdout, "wb") as out, open(log_file_stderr, "wb") as err:
            subprocess.run(["/bin/bash", script_file], stdout=out, stderr=err)

    except Exception as e:
        logmessage('Unexpected exception while running CreateImage_GParted: %s' % e)


def CreateImage_Custom(job_id, input_data):
    logmessage('i am fake jobid: %s' % job_id)
    time.sleep(4)
    WriteJobProgress(job_id, 20)
    time.sleep(2)
    WriteJobProgress(job_id, 25)
    time.sleep(2)
    WriteJobProgress(job_id, 50)
    time.sleep(2)
    WriteJobProgress(job_id, 75)
    time.sleep(2)
    logmessage(input_data)
    WriteJobProgress(job_id, 100)
