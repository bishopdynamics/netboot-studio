# What works 

## Windows Desktop
* windows 7 32bit bios - no, cant find install media
* windows 7 64bit bios - no, doesnt seem to run mount.bat, no network drivers for vmware 
* windows 7 64bit efi - no, cant find bootx64.efi or bootmgfw.efi (iso i have doesnt do efi at all)
* windows 10 64bit efi - yes
* windows 10 64bit efi unattended install using unattend.xml - yes
* windows 10 64bit bios - almost, doesn't seem to run mount.bat, but manually running it does

# Windows Server
* windows server 2012 bios x64 - no, cant find install media
* windows server 2012 efi x64 - yes
* windows server 2016 bios x64 - no, cant find install media, not supported anyway?
* windows server 2016 efi x64 - yes
* windows server 2019 efi x64 - yes, but setup loads very slowly

## Debian netinstall via internet-hosted files (no local files needed)
* debian 64bit bios - yes
* debian 64bit efi - yes
* debian 32bit bios - yes
* debian (all flavors) unattended install using preseed file - yes

## Ubuntu
* Ubuntu Xenial 64bit efi - yes
* Ubuntu Xenial 64bit bios - yes
* ubuntu Bionic 64bit efi - yes

## Utilities
* ubuntu 18.04 desktop LIVE 64bit efi - yes
* ubuntu 19.04 desktop LIVE 64bit efi - yes
* gparted live 32bit bios - yes
* gparted live 64bit bios - yes
* gparted live 64bit efi - yes

## VMWare
Tested EFI only, 6.0 thru 7.0, all working, including unattended install using kickstart.cfg
