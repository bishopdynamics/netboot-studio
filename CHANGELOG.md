# Change Log

## 0.1.5
	* Moved wizard-data to a yaml file
	* Added wizard for generating unattended files
	* Change UI color to something non-default
	* Custom image type now works
## 0.1.4
	* Create Image Wizard - all image types work!
## 0.1.3
	* added create image wizard
## 0.1.2
	* skipped version to match up with what i put on youtube videos
## 0.1.1
	* added basic auth and login page, most requests require auth_token now
## 0.1.0
	* material ui is at parity
	* webui rendering moved to client side
	* changed to images paradigm instead of scripts
## 0.0.9
	* initial material design ui is almost at parity
	* default script and unattended files are now build-in virtual files
## 0.0.8
	* swap next-phase for roadmap
	* got ubuntu live images to work, new dependency on NFS server
	* tightened up stage1 timing
## 0.0.7
	* added hostname lookup
	* sorted dropdowns
	* added editor for unattended answer files
	* better fallback response and logging
## 0.0.6
	* mostly cleanup and add license
## 0.0.5
	* vmware esxi installer now working
	* added support for vmware esxi unattend (kickstart.cfg)
	* for requests for unattended.cfg (or variants), macaddress urlaram now optional
		- requests for stage2.ipxe still require macaddress urlparam
	* ipaddress, arch, manufacturer, and platform now stored in clientlist and shown in admin
## 0.0.4
	* added support for unattend.xml for windows installers
## 0.0.3
	* pre-changelog