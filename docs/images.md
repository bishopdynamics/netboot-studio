# Manually Creating Images aka: The Hard Way
There's a wizard for this, you dont have to do it the hard way. But we love documentation, so here's everything anyway.

Images are just folder, with the files you need inside, plus a few extras to facilitate netbooting. Image folders must have `netboot.ipxe` at bare minimum. To support unattended installation, `netboot-unattended.ipxe` is also needed. 
In the web ui Images tab, you can edit any supported files if they exist, from this list:

```
netboot.ipxe
netboot-unattended.ipxe
winpeshl.ini (windows)
startnet.cmd (windows)
mount.cmd (windows)
netboot.cfg (vmware)
netboot-unattended.cfg (vmware)
```

## Windows Installer Images

*Caveat: as of late March 2019, i haven't gotten Windows 7-era images to boot properly. Windows 10-era images work great!*
*I've also had most success with EFI booting windows images, and very little success with BIOS booting, I also dont care much about BIOS*

If you are having trouble with wpeinit stalling forever in a vmware vm, try changing the nic model in vmx file
https://communities.vmware.com/thread/602015

### Automatic
The script `prep/create_windows_image.sh` can be used to create netbootable windows installer images,
and the corresponding files needed, plus an ipxe script in `scripts/` to use it. You should read it first, and edit some early vars to match your setup; it is reliant on your setup matching ours.


### Manual Process 

Under `/opt/tftp-root/images/windows/wim/`, create folder like `Windows_10_64bit_Installer` and extract the iso into it.
This folder name cannot have spaces or special characters in it

you then need to add three more files:
- startnet.cmd
- mount.cmd
- winpeshl.ini

Contents of winpeshl.ini is the same for all versions of Windows (Win 7+). Calling cmd.exe last gives you a cmd prompt to work with if something fails:
```powershell
[LaunchApps]
"startnet.cmd"
"mount.cmd"
"cmd.exe"
```

Contents of startnet.cmd are constant:
````powershell
wpeinit
````

Contents of mount.cmd are specific to the folder it is in (`Windows_10_64bit_Installer` for example), and is also where our unattend logic is implemented:
```powershell
ipconfig
net use s: smb:\\192.168.1.188\images\windows\wim\Windows_10_64bit_Installer foo /user:bar
@echo off
echo checking for unattend.xml
if exist x:\windows\system32\unattend.xml (
    echo using x:\windows\system32\unattend.xml
    @echo on
    s:\sources\setup.exe /unattend:x:\windows\system32\unattend.xml
) else (
    echo unattend.xml does not exist
    @echo on
    s:\sources\setup.exe
)
```
Note above, we mount the share as user `bar` with password `foo`; as long as user `bar` does not exist on the server, this will force the client to try guest access instead. Yes its a little odd that user is a flag but password is just a positional argument.

Finally, make everything in that folder `Windows_10_64bit_Installer` world readable and executable (whaaat? yes, its needed, and not just for exe and dll). Also make sure it's owned by a user:group which apache can work with (like james:www-data).
TODO - rx might only be needed for folders, exe, dll

### Unattended Install
You can do an unattended install by adding to ipxe script:

`imgfetch http://${next-server}:6161/unattend.xml?macaddress=${mac} unattend.xml || goto failed`

For windows, we cannot pass the `/unattend:<file>` flag from within ipxe, because it is an argument to setup.exe, not the kernel. Instead we use a dead-drop, by having wimboot store it in the ramdisk. Once winpe is loaded, `unattend.xml` will end up in `x:\windows\system32\` and `mount.cmd` will find it, and invoke setup.exe with: 

`/unattend:x:\windows\system32\unattend.xml`

This is of course dependent on you using `mount.cmd` as shown above 

For creating unattend.xml, some notes:

* https://www.windowsafg.com/win10x86_x64_uefi.html
* arch: x86 or amd64
* there are a shitload of options available
* you have to provide a productkey?

## VMWare ESXi Installer Images

EFI netbooting a VMWare ESXi Installer over HTTP (not using tftp for any files), is totally do-able, but horribly documented. Most resources try to get you to use BIOS booting instead, and ask you to do lots of manual steps. 

I have found a simple method for EFI booting an image created from an ISO, with minimal changes needed. Preparing an ESXi installer image from ISO requires some work, so I've provided some examples for netboot.cfg and scripts to rename kernel and module files to lowercase. Note this setup is specifically for EFI booting. I havent messed with BIOS booting because I have no need for it

1. copy `<image-root>EFI/BOOT/BOOT.CFG` to `<image-root>/netboot.cfg`
2. edit netboot.cfg
    - add `prefix=http://192.168.1.188/images/linux/vmware/vmware-esxi-6.5-realtek` before kernel= line (edit path for your setup)
    - remove leading / from everything in
        - kernel=
        - modules=
    - you can also just use boot.cfg provided in examples/vmware/
3. rename all the actual files that are listed in modules= in boot.cfg, to be lowercase
    - no, you cannot just change them to uppercase in boot.cfg, it doesnt like that. you have to rename the actual files to be lowercase
        - this is because when fetched via tftp, case becomes irrelevant and everything works out, but http cares (file not found). the esxi kernel however, wants the files to be lowercase and throws "unexpected module" when loading them as uppercase. 
    - see [examples/vmware/convert_modules_to_lowercase_6.5.sh](examples/vmware/convert_modules_to_lowercase_6.5.sh)
    - see [examples/vmware/convert_modules_to_lowercase_6.0.sh](examples/vmware/convert_modules_to_lowercase_6.0.sh)
4. add rx permissions to all files in your esx image folder
    - find . -exec chmod a+rx {} \;
    - TODO - this might only need to be done to directories

Some resources: 

    - https://docs.vmware.com/en/VMware-vSphere/6.7/com.vmware.esxi.upgrade.doc/GUID-147D7509-EFB1-4391-973F-48B015B85C83.html
    - https://www.vmware.com/content/dam/digitalmarketing/vmware/en/pdf/techpaper/vsphere-esxi-vcenter-server-60-pxe-boot-esxi.pdf
    - https://www.scottishvmug.com/esxi-scripted-builds-via-pxe-kickstart/

see [scripts/vmware-esxi-65-efi.ipxe](scripts/vmware-esxi-65-efi.ipxe)

see [scripts/vmware-esxi-60-efi.ipxe](scripts/vmware-esxi-60-efi.ipxe)

see [examples/vmware/esx-6.5-realtek_netboot.cfg](examples/vmware/esx-6.5-realtek_netboot.cfg)

see [examples/vmware/esx-6.0-realtek_netboot.cfg](examples/vmware/esx-6.0-realtek_netboot.cfg)

### Unattended Install
For vmware, you cannot pass the unattended file to the kernel in iPXE. Instead we have to supply the unattended file as a kernelopt in netboot.cfg, but there we have no way to get the macaddress, to supply as urlparam. To get around this, if a request for unattended.cfg is made without the macaddress urlparam, netboot studio backend will use ip address to find entry in client list. You can do an unattended install by adding to kernelopt= in netboot.cfg:

`netdevice=vmnic0 bootproto=dhcp ks=http://192.168.1.188:6161/unattended.cfg`

I usually name that netboot-unattended.cfg, so that the image folder can be used for both. There is no way to 

see [scripts/vmware-esxi-65-efi-unattended.ipxe](scripts/vmware-esxi-65-efi-unattended.ipxe)

see [examples/vmware/esx-6.5-realtek_netboot_unattended.cfg](examples/vmware/esx-6.5-realtek_netboot_unattended.cfg)

## Debian Netinstall Images

Can be booted directly from debian archive servers over HTTP, there is no need to host any files yourself. 
See [scripts/debian9-64bit.ipxe](scripts/debian9-64bit.ipxe)

### Unattended Install
You can do an unattended install by adding to kernel arguments in ipxe script:

`auto url=http://${netboot-server}/unattended.cfg?macaddress=${mac}`

This should work for any debian-based distro installer

## Ubuntu Live Installer Images

This one is fun, kind of a pain in the ass to figure out, but ultimately really useful
extract ISO to folder, then use kernel and initrd like normal
the magic sauce is in the kernel arguments, and having the entire ISO contents available via an NFS share.
Unfortunately, this doesn't seem to be doable without NFS.

see [scripts/ubuntu-18.04-live.ipxe](scripts/ubuntu-18.04-live.ipxe)

Take note: if you use a netbooted live Ubuntu image to install ubuntu, the resulting installation will end up with what appears to be broken networking. Read the ipxe.org link below to understand more.

I have found that once the live image is booted, you can edit `/etc/network/interfaces`, putting the nic back to dhcp, and then renew dhcp lease: `sudo dhclient -r; sudo dhclient`. After that, install will work as normal.

the most useful resources i found were:

- http://ipxe.org/appnote/ubuntu_live
- https://askubuntu.com/questions/1029017/pxe-boot-of-18-04-iso


## Gparted Live Images

Similar, but simpler than booting ubuntu live images, you really just need to download and extrac the iso into a folder and then fetch & exec the right files. profit. 

See [scripts/gparted-64bit.ipxe](scripts/gparted-64bit.ipxe)

## Booting a generic ISO file directly

This is currently only possible on BIOS, not EFI. As such I immediately lost interest. It is possible that someday in the future someone will write and release a tool similar to wimboot that can make this work.

I plan to experiment with extracting ISO to folder and then converting it to a squashfs image to load just like other live images
Ideally, this would be a general-purpose script that could do this to any ISOLINUX/SYSLINUX based iso file or image. 

Coming soon...