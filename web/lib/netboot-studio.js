/* Netboot Studio Web UI javascript

    This file is part of Netboot Studio, a system for managing netboot clients
    Copyright (C) 2019 James Bishop (jamesbishop2006@gmail.com)

info about CodeMirror (js code editor): https://codemirror.net/doc/manual.html#fromTextArea
info about ipxe: http://ipxe.org/
info about materialize: https://materializecss.com/getting-started.html
*/

// linter options 
/*jshint esversion: 6 */


// static vars
var BUILT_IN_IMAGE_DEFAULT_NAME = 'standby-loop';
var BUILT_IN_UNATTENDED_DEFAULT_NAME = 'blank.cfg';
var STORAGE_FOLDER = '/opt/tftp-root';
// in seconds. 10m = 600
var AUTH_TOKEN_RENEW_CYCLE = 600;
// in seconds
var FETCH_STATUS_CYCLE = 4;
var WEBSOCKET_PORT = 6162;


// other vars
var CLIENT_LIST;
var IMAGE_LIST;
var UNATTENDED_LIST;
var ISO_LIST;
var WEBSOCKET;
var WIZARD_DATA;
var AUTH_TOKEN;

var EDITOR_IMAGEFILE_IMAGENAME;
var EDITOR_IMAGEFILE_FILENAME;
var EDITOR_UNATTENDED_FILENAME;
var EDITOR_IMAGEFILE = null;
var EDITOR_UNATTENDED = null;

var ISO_FOLDER = STORAGE_FOLDER + '/iso';
var IMAGES_FOLDER = STORAGE_FOLDER + '/images';
var UNATTENDED_FOLDER = STORAGE_FOLDER + '/unattended';

var HOST_NAME = window.location.hostname;
var WEBSOCKET_URI = 'ws://' + HOST_NAME + ':' + WEBSOCKET_PORT;

// files within an image folder, which we support editing
var SUPPORTED_FILES = [
    'netboot.ipxe',
    'netboot-unattended.ipxe',
    'winpeshl.ini',
    'startnet.cmd',
    'mount.cmd',
    'netboot.cfg',
    'netboot-unattended.cfg'
];

// metadata keys we show in ui
IMAGE_METADATA_DISPLAY_KEYS = [
    'source_iso',
    'image_type',
    'created',
    'description'
];


// Functions

function CreateClientsTab() {
    // populate #clients-tab
    // console.log('creating Clients tab');
    try {
        var local_client_list = CLIENT_LIST;
        var target_div = document.getElementById('clients-tab');
        var tab_html = '<ul class="collapsible popout">';
        for (var client_macaddress in local_client_list){
            var obj = local_client_list[client_macaddress];
            var client_ipaddress = obj.ipaddress;
            var client_hostname = obj.hostname;
            var client_image = obj.image;
            var client_unattended = obj.unattended;
            var client_arch = obj.arch;
            var client_platform = obj.platform;
            var client_manufacturer = obj.manufacturer;
            var client_do_unattended = obj.do_unattended;
            var dropdown_images = CreateDropdownImages(client_macaddress);
            var dropdown_unattendeds = CreateDropdownUnattendeds(client_macaddress);
            tab_html += '<li>';
            tab_html += '<div class="collapsible-header">' + client_macaddress + ' - ' + client_ipaddress + ' - ' + client_hostname + '</div>';
            tab_html += '<div class="collapsible-body"><span>';
            tab_html += '<p><label>Hostname:</label>' + client_hostname + '</p>';
            tab_html += '<p><label>IP Address:</label>' + client_ipaddress + '</p>';
            tab_html += '<p><label>MAC Address:</label>' + client_macaddress + '</p>';
            tab_html += '<p><label>Architecture:</label>' + client_arch + '</p>';
            tab_html += '<p><label>Platform:</label>' + client_platform + '</p>';
            tab_html += '<p><label>Manufacturer:</label>' + client_manufacturer + '</p>';
            tab_html += '<p><div id="select_images_' + client_macaddress + '"><label>Image:</label>' + dropdown_images + '</div></p>';
            var checkbox_onchange = '(function(event){HandleCheckboxChange_DoUnattended("' + client_macaddress + '", event.checked)})(this)';
            if (client_do_unattended) {
                tab_html += '<label id="checkbox_container_dounattended_' + client_macaddress + '">';
                tab_html += '<input id="checkbox_dounattended_' + client_macaddress + '" type="checkbox" class="filled-in" checked="checked" onchange=\'' + checkbox_onchange + '\'/>';
                tab_html += '<span>Perform Unattended Install</span></label>';
                tab_html += '<p><div id="select_unattendeds_' + client_macaddress + '"><label>Unattended Answer File:</label>' + dropdown_unattendeds + '</div></p>';
            } else {
                tab_html += '<label id="checkbox_container_dounattended_' + client_macaddress + '">';
                tab_html += '<input id="checkbox_dounattended_' + client_macaddress + '" type="checkbox" class="filled-in" onchange=\'' + checkbox_onchange + '\'/>';
                tab_html += '<span>Perform Unattended Install</span></label>';
                tab_html += '<p><div id="select_unattendeds_' + client_macaddress + '" class="hide"><label>Unattended Answer File:</label>' + dropdown_unattendeds + '</div></p>';
            }
            tab_html += '<p>&nbsp;</p></span></div>';
            tab_html += '</li>';
        }
        tab_html += '</ul>';
        target_div.innerHTML = tab_html;
    } catch(e) {
        console.error('error while creating clients tab: ' + e.message);
    }
}

function CreateImagesTab() {
    // opulate #images-tab
    // console.log('creating Images tab');
    try {    
        var local_image_list = IMAGE_LIST;
        var target_div = document.getElementById('images-tab');
        var tab_html = '<ul class="collapsible popout">';
        tab_html += '<p><a onclick="ShowWizard_NewImage();" class="btn">Create New Image</a></p>';
        for (var image_name in local_image_list) {
            var obj = local_image_list[image_name];
            var image_display = image_name.replace(/_/g, ' ').replace(/-/g, ' ');
            var image_path = IMAGES_FOLDER + '/' + image_name + '/';
            if (image_name == BUILT_IN_IMAGE_DEFAULT_NAME) {
                image_path = '[built-in]';
                image_display += ' [built-in]';
            }
            if (local_image_list[image_name]['has_netboot-unattended.ipxe']) {
                image_display += ' [Supports Unattended Install]';
            }
            tab_html += '<li><div class="collapsible-header">' + image_display + '</div>';
            tab_html += '<div class="collapsible-body"><span>';
            // actual content
            tab_html += '<p>Info:</p>';
            tab_html += '<p><label>image path:</label>' + image_path + '</p>';
            for (var key_num in IMAGE_METADATA_DISPLAY_KEYS) {
                var this_key = IMAGE_METADATA_DISPLAY_KEYS[key_num];
                if (this_key in local_image_list[image_name]) {
                    var this_value = local_image_list[image_name][this_key];
                    var this_key_display = this_key.replace(/_/g, ' ').replace(/-/g, ' ');
                    tab_html += '<p><label>' + this_key_display + ':</label>' + this_value + '</p>';
                }
            }
            if (image_name != BUILT_IN_IMAGE_DEFAULT_NAME) {
                tab_html += '<p>Files:</p>';
                for (var file_num in SUPPORTED_FILES) {
                    var this_file = SUPPORTED_FILES[file_num];
                    if (local_image_list[image_name]['has_' + this_file]) {
                        tab_html += '<a onclick="ShowImageFileEditor(\'' + image_name + '\', \'' + this_file + '\')" class="btn">Edit ' + this_file + '</a>&nbsp;';
                    }
                }
            }
            tab_html += '</span></div></li>';
        }
        tab_html += '</ul>';
        target_div.innerHTML = tab_html;
    } catch(e) {
        console.error('error while creating images tab: ' + e.message);
    }
}

function CreateUnattendedsTab() {
    // populate #unattendeds-tab
    // console.log('creating Unattendeds tab');
    try {
        var local_unattended_list = UNATTENDED_LIST;
        var target_div = document.getElementById('unattendeds-tab');
        var tab_html = '<ul class="collapsible popout">';
        tab_html += '<p><a onclick="ShowNewUnattendedDialog();" class="btn">Create Blank Answer File</a>&nbsp;<a onclick="ShowWizard_Unattended();" class="btn">Answer File Wizard</a></p>';
        for (var unattended_num in local_unattended_list) {
            var file_name = local_unattended_list[unattended_num];
            var file_display = file_name;
            var file_path = UNATTENDED_FOLDER + '/' + file_name;
            if (file_name == BUILT_IN_UNATTENDED_DEFAULT_NAME) {
                file_display += ' [built-in]';
                file_path = '[built-in]';
            }
            tab_html += '<li><div class="collapsible-header">' + file_display + '</div>';
            tab_html += '<div class="collapsible-body"><span>';
            tab_html += 'Path: ' + file_path;
            tab_html += '<p>';
            if (file_name != BUILT_IN_UNATTENDED_DEFAULT_NAME) {
                tab_html += '<a onclick="ShowUnattendedEditor(\'' + file_name + '\')" class="btn">Edit</a>&nbsp;';
            }
            tab_html += '<a onclick="M.toast({html: \'Copied ' + file_name + '\'})" class="btn">Copy</a>';
            tab_html += '</p>';
            tab_html += '</span></div></li>';

        }
        tab_html += '</ul>';
        target_div.innerHTML = tab_html;
    } catch(e) {
        console.error('error while creating unattendeds tab: ' + e.message);
    }
}

function CreateISOsTab() {
    // populate #isos-tab
    // console.log('creating ISOs tab');
    try {
        var local_iso_list = ISO_LIST;
        var target_div = document.getElementById('isos-tab');
        var tab_html = '<ul class="collapsible popout">';
        tab_html += '<p><a onclick="ShowUploadISODialog();" class="btn">Upload ISO</a></p>';
        for (var file_num in local_iso_list) {
            var file_name = local_iso_list[file_num];
            var file_display = file_name;
            var file_path = ISO_FOLDER + '/' + file_name;
            tab_html += '<li><div class="collapsible-header">' + file_display + '</div>';
            tab_html += '<div class="collapsible-body"><span>';
            tab_html += 'Path: ' + file_path;
            tab_html += '</span></div></li>';

        }
        tab_html += '</ul>';
        target_div.innerHTML = tab_html;
    } catch(e) {
        console.error('error while creating isos tab: ' + e.message);
    }
}

function CreateTableTab() {
    // populate #table-tab
    // console.log('creating Table tab');
    try {
        var local_client_list = CLIENT_LIST;
        var target_div = document.getElementById('table-tab');
        var tab_html = '<div><table class="striped">';
        tab_html += '<thead><tr><th>MAC</th><th>IP</th><th>Hostname</th><th>Image</th><th>Answer File</th><th>Do Unattended</th></tr></thead>';
        tab_html += '<tbody>';
        for (var client_macaddress in local_client_list){
            var obj = local_client_list[client_macaddress];
            var client_ipaddress = obj.ipaddress;
            var client_hostname = obj.hostname;
            var client_do_unattended = obj.do_unattended;
            var dropdown_images = CreateDropdownImages(client_macaddress);
            var dropdown_unattendeds = CreateDropdownUnattendeds(client_macaddress);
            var checkbox_onchange = '(function(event){HandleCheckboxChange_DoUnattended("' + client_macaddress + '", event.checked)})(this)';
            var checkbox;
            if (local_client_list[client_macaddress].do_unattended) {
                checkbox = '<center><label><input type="checkbox" class="filled-in" checked="checked"';
                checkbox += ' onchange=\'' + checkbox_onchange + '\'/><span></span></label></center>';
            } else {
                checkbox = '<center><label><input type="checkbox" class="filled-in"';
                checkbox += ' onchange=\'' + checkbox_onchange + '\'/><span></span></label></center>';
            }
            tab_html += '<tr><td>' + client_macaddress+ '</td><td>' + client_ipaddress + '</td>';
            tab_html += '<td>' + client_hostname + '</td><td>' + dropdown_images + '</td>';
            tab_html += '<td>' + dropdown_unattendeds + '</td><td>' + checkbox + '</td></tr>';
        }
        tab_html += '</tbody></table></div>';
        target_div.innerHTML = tab_html;
    } catch(e) {
        console.error('error while creating table tab: ' + e.message);
    }
}

function CreateLogTab() {
    // populate #log-tab
    // console.log('creating Log tab');
    try {
        var target_div = document.getElementById('log-tab');
        var tab_html = '<div>';
        tab_html += '<textarea style="height:70vh;" readonly>' + LOG_FILE_CONTENT + '</textarea>';
        tab_html += '</div>';
        target_div.innerHTML = tab_html;
    } catch(e) {
        console.error('error while creating table tab: ' + e.message);
    }
}

function HideUnattended(client_macaddress){
    console.log('hiding unattended options for: ' + client_macaddress);
    var unattendeds_dropdown_id = 'select_unattendeds_' + client_macaddress;
    var checkbox_container_id = 'checkbox_container_dounattended_' + client_macaddress;
    var checkbox_id = 'checkbox_dounattended_' + client_macaddress;
    if (document.getElementById(checkbox_id).checked) {
        document.getElementById(checkbox_id).click();
    }
    document.getElementById(unattendeds_dropdown_id).classList.add("hide");
    document.getElementById(checkbox_container_id).classList.add("hide");
}

function ShowUnattended(client_macaddress){
    console.log('showing unattended options for: ' + client_macaddress);
    var checkbox_container_id = 'checkbox_container_dounattended_' + client_macaddress;
    document.getElementById(checkbox_container_id).classList.remove("hide");
}

function HandleDropdownChange_Images(client_macaddress, image){
    // console.log('Handling onchange for an Images dropdown for macaddress: ' + client_macaddress);
    if(IMAGE_LIST[image]['has_netboot-unattended.ipxe']) {
        ShowUnattended(client_macaddress);
    } else {
        HideUnattended(client_macaddress);
    }
    var req_obj = {};
    req_obj.macaddress = client_macaddress;
    req_obj.image = image;
    var req_content = JSON.stringify(req_obj);
    var response = FetchWithAuthToken("editclient", req_content);
    if (response !== false) {
        M.toast({html: "Image for [" + client_macaddress + "] set to: [" + image + "]"});
    } else {
        M.toast({html: "Failed to set Image for [" + client_macaddress + "] to: [" + image + "]"});
    }
}

function HandleDropdownChange_Unattended(client_macaddress, unattended){
    // console.log('Handling onchange for an Unattended dropdown for macaddress: ' + client_macaddress);
    var req_obj = {};
    req_obj.macaddress = client_macaddress;
    req_obj.unattended = unattended;
    var req_content = JSON.stringify(req_obj);
    var response = FetchWithAuthToken("editclient", req_content);
    if (response !== false) {
        M.toast({html: "Unattended for [" + client_macaddress + "] set to: [" + unattended + "]"});
    } else {
        M.toast({html: "Failed to set Unattended for [" + client_macaddress + "] to: [" + unattended + "]"});
    }
}

function HandleCheckboxChange_DoUnattended(client_macaddress, do_unattended){
    // console.log('Handling onchange for an do_unattended checkbox for macaddress: ' + client_macaddress);
    var unattendeds_dropdown_id = 'select_unattendeds_' + client_macaddress;
    if (do_unattended) {
        document.getElementById(unattendeds_dropdown_id).classList.remove("hide");
    } else {
        document.getElementById(unattendeds_dropdown_id).classList.add("hide");
    }
    var req_obj = {};
    req_obj.macaddress = client_macaddress;
    req_obj.do_unattended = do_unattended;
    var req_content = JSON.stringify(req_obj);
    var response = FetchWithAuthToken("editclient", req_content);
    if (response !== false) {
        M.toast({html: "do_unattended for [" + client_macaddress + "] set to: [" + do_unattended + "]"});
    } else {
        M.toast({html: "Failed to set do_unattended for [" + client_macaddress + "] to: [" + do_unattended + "]"});
    }
}

function CreateDropdownImages(client_macaddress) {
    var onchange = '(function(event){HandleDropdownChange_Images("' + client_macaddress + '", event.value)})(this)';
    var dropdown_html = '<div class="input-field col s12"><select onchange=\'' + onchange + '\'>';
    for (var image_name in IMAGE_LIST) {
        var image_display = image_name.replace(/_/g, ' ').replace(/-/g, ' ');
        if (IMAGE_LIST[image_name]['has_netboot-unattended.ipxe'] == true) {
            image_display += ' [Supports Unattended Install]';
        }
        if (image_name == CLIENT_LIST[client_macaddress].image) {
            dropdown_html += '<option value="' + image_name + '" selected>' + image_display + '</option>';
        } else {
            dropdown_html += '<option value="' + image_name + '">' + image_display + '</option>';
        }
    }
    dropdown_html += '</select></div>';
    return dropdown_html;
}

function CreateDropdownUnattendeds(client_macaddress) {
    var onchange = '(function(event){HandleDropdownChange_Unattended("' + client_macaddress + '", event.value)})(this)';
    var dropdown_html = '<div class="input-field col s12"><select onchange=\'' + onchange + '\'>';
    for (var item_num in UNATTENDED_LIST) {
        var unattended_name = UNATTENDED_LIST[item_num];
        if (unattended_name == CLIENT_LIST[client_macaddress].unattended) {
            dropdown_html += '<option value="' + unattended_name + '" selected>' + unattended_name + '</option>';
        } else {
            dropdown_html += '<option value="' + unattended_name + '">' + unattended_name + '</option>';
        }
    }
    dropdown_html += '</select></div>';
    return dropdown_html;
}

function ShowImageFileEditor(image_name, file_name){
    EDITOR_IMAGEFILE_IMAGENAME = image_name;
    EDITOR_IMAGEFILE_FILENAME = file_name;
    document.getElementById('modal_editor_imagefile_name').innerHTML = image_name + '/' + file_name;
    var modal_instance = M.Modal.getInstance(document.getElementById("modal_editor_imagefile"));
    modal_instance.open();
    if (EDITOR_IMAGEFILE == null){
        EDITOR_IMAGEFILE = CodeMirror.fromTextArea(document.getElementById("editor_imagefile"), {
          lineNumbers: true,
          theme: "material",
        });
    }
    var response = FetchWithAuthToken("getimagefile?imagename=" + image_name + '&filename=' + file_name);
    if (response) {
        // console.log('Succesfully loaded:' + image_name + '/' + file_name);
        M.toast({html: 'Succesfully loaded:' + image_name + '/' + file_name});
        EDITOR_IMAGEFILE.setValue(response);
    } else {
        console.error('Failed to load:' + image_name + '/' + file_name);
        M.toast({html: 'Failed to load:' + image_name + '/' + file_name});
        modal_instance.close();
    }
}

function SaveImageFileEditor(){
    var image_name = EDITOR_IMAGEFILE_IMAGENAME;
    var file_name = EDITOR_IMAGEFILE_FILENAME;
    // console.log('saving image file: '+ image_name + '/' + file_name);
    var modal_instance = M.Modal.getInstance(document.getElementById("modal_editor_imagefile"));
    var response = FetchWithAuthToken("saveimagefile?imagename=" + image_name + '&filename=' + file_name, EDITOR_IMAGEFILE.getValue());
    if (response !== false) {
        console.log('Successfully saved:' + image_name + '/' + file_name);
        M.toast({html: 'Successfully saved:' + image_name + '/' + file_name});
        modal_instance.close();
    } else {
        console.error('Failed to save:' + image_name + '/' + file_name);
        M.toast({html: 'Failed to save:' + image_name + '/' + file_name});
    }
}

function ShowNewUnattendedDialog(){
    var modal_instance = M.Modal.getInstance(document.getElementById("modal_dialog_newunattended"));
    modal_instance.open();
}

function CreateNewUnattended(){
    // validate file name, then call /newunattended
    var valid = true;
    var file_name = document.getElementById('new_unattedned_file_name').value;
    if (file_name == BUILT_IN_UNATTENDED_DEFAULT_NAME){
        M.toast({html: 'Cannot overwrite built-in ' + file_name });
        valid = false;
    }
    if (UNATTENDED_LIST.includes(file_name)){
        M.toast({html: 'An answer file named  ' + file_name + ' already exists'});
        valid = false;
    }
    if (file_name.indexOf(' ') >= 0){
        M.toast({html: 'File name may not contain spaces'});
        valid = false;
    }
    if (!file_name.endsWith('.cfg') && !file_name.endsWith('.xml')){
        M.toast({html: 'An answer file should end in .cfg or .xml'});
        valid = false;
    }
    var modal_instance = M.Modal.getInstance(document.getElementById("modal_dialog_newunattended"));
    
    if (valid) {
        var response = FetchWithAuthToken('/newunattended?unattended=' + file_name);
        if(response !== false){
            M.toast({html: 'Created ' + file_name });
            modal_instance.close();
        } else {
            M.toast({html: 'Failed to create ' + file_name });
        }
    }
}

function ShowUploadISODialog(){
    var modal_instance = M.Modal.getInstance(document.getElementById("modal_dialog_uploadiso"));
    modal_instance.open();
}

function UploadISO(){
    var valid = true;
    var file_object = document.getElementById('upload_iso_file_picker').files[0];
    // firefox 3.5 does it different
    var file_name = file_object.name || file_object.fileName;
    var file_size = file_object.size;
    if (ISO_LIST.includes(file_name)){
        M.toast({html: 'An ISO named  ' + file_name + ' already exists'});
        valid = false;
    }
    if (!file_name.endsWith('.iso')){
        M.toast({html: 'An ISO file should end with .iso'});
        valid = false;
    }
    if (file_name.indexOf(' ') >= 0){
        M.toast({html: 'File name may not contain spaces'});
        valid = false;
    }
    var modal_instance = M.Modal.getInstance(document.getElementById("modal_dialog_uploadiso"));
    
    if (valid) {
        var response = UploadWithAuthToken('/uploadiso', file_object);
        if(response === true){
            modal_instance.close();
        } else {
            M.toast({html: 'Failed to upload ' + file_name + ' response: ' + response });
        }
    }
}

function ShowUnattendedEditor(file_name){
    EDITOR_UNATTENDED_FILENAME = file_name;
    document.getElementById('modal_editor_unattended_name').innerHTML = file_name;
    var modal_instance = M.Modal.getInstance(document.getElementById("modal_editor_unattended"));
    modal_instance.open(); 
    if (EDITOR_UNATTENDED == null){
        EDITOR_UNATTENDED = CodeMirror.fromTextArea(document.getElementById("editor_unattended"), {
          lineNumbers: true,
          theme: "material",
        });
    }
    var response = FetchWithAuthToken("getunattended?unattended=" + file_name);
    if (response) {
        // console.log('Succesfully loaded:' + file_name);
        M.toast({html: 'Succesfully loaded:' + file_name});
        EDITOR_UNATTENDED.setValue(response);
        modal_instance.open();
    } else {
        console.error('Failed to load:' + file_name);
        M.toast({html: 'Failed to load:' + file_name});
        modal_instance.close();
    }
}

function SaveUnattendedEditor(){
    var file_name = EDITOR_UNATTENDED_FILENAME;
    // console.log('saving unattended: '+ file_name);
    var modal_instance = M.Modal.getInstance(document.getElementById("modal_editor_unattended"));
    var response = FetchWithAuthToken("saveunattended?unattended=" + file_name, EDITOR_UNATTENDED.getValue());
    if (response !== false) {
        // console.log('Succesfully saved:' + file_name);
        M.toast({html: 'Successfully saved:' + file_name});
        modal_instance.close();
    } else {
        console.error('Failed to save:' + file_name);
        M.toast({html: 'Failed to save:' + file_name});
    }
}

function FetchWithAuthToken(url, content=null){
    var xmlHttp = new XMLHttpRequest(); 
    try {
        // create headers with auth-token here
        xmlHttp.open( "POST", url, false);
        xmlHttp.setRequestHeader('auth_token', AUTH_TOKEN);
        xmlHttp.send(content); 
        if (xmlHttp.status === 200) {
            // console.log('Successfully fetched: ' + url);
            return xmlHttp.responseText;
        } else {
            console.error('Failed to do authenticated request to: ' + url);
            return false;
        }
    } catch(e) {
        console.error('Exception while doing authenticated request: ' + e);
        return false;
    }
}

function UploadWithAuthToken(url, file_object){
    var file_name = file_object.name || file_object.fileName;
    var file_size = file_object.size;
    console.log('Uploading file: ' + file_name + ' , size: ' + file_size);
    var xmlHttp = new XMLHttpRequest(); 
    try {
        // create headers with auth-token here
        xmlHttp.upload.addEventListener('progress', UploadProgressHandler, false);
        xmlHttp.open( "POST", url, true);
        xmlHttp.setRequestHeader('auth_token', AUTH_TOKEN);
        xmlHttp.setRequestHeader('file_name', file_name);
        xmlHttp.setRequestHeader("Content-Type", "application/octet-stream");
        if ('getAsBinary' in file_object) {
            // Firefox 3.5
            xmlHttp.sendAsBinary(file_object.getAsBinary());
        }
        else {
            // W3C-blessed interface
            xmlHttp.send(file_object);
        }
        if (xmlHttp.status === 201 || xmlHttp.status === 200 || xmlHttp.status === 0) {
            console.log('Successfully uploaded: ' + file_name);
            return true;
        } else {
            // console.log('xxmlHttp.status: ' + xmlHttp.status);
            console.error('Failed to do authenticated request to: ' + url);
            return xmlHttp.responseText;
        }
    } catch(e) {
        console.error('Exception while doing authenticated request: ' + e);
        return false;
    }
}

function UploadProgressHandler(evt) {
    var job_progress = (evt.loaded/evt.total) * 100;
    var this_job = 'file_upload';
    console.log('Upload progress: ' + job_progress + '%');
    var toast_class = 'toast_status_job_' + this_job;
    var range_class = 'progress_job_' + this_job;
    var toast_container_id = 'toast_container_job_' + this_job;
    var toast_instance;
    try {
        var instance = M.Toast.getInstance(document.querySelector('.' + toast_class));
        toast_instance = instance;
    } catch(e) {
        toast_instance = false;
    }
    var toastHTML = '';
    var toast_button_dismiss_onclick = '(M.Toast.getInstance(document.querySelector(\'.' + toast_class + '\')).dismiss())';
    var toast_button_abort_onclick = '(FetchWithAuthToken(\'/canceljob?job=' + this_job + '\'))';

    toastHTML += '<div style="min-width:300px;">';
    if (job_progress == 0){
        toastHTML += '<span>Uploading... </span>';
        toastHTML += '<div class="progress"><div class="indeterminate"></div></div>';
    } else if (job_progress == 100){
        toastHTML += '<span>Upload Complete</span>';
    } else {
        toastHTML += '<span>Uploading... </span>';
        toastHTML += '<div class="progress"><div class="determinate" style="width: ' + job_progress + '%"></div></div>';
    }
    
    toastHTML += '</div>';

    if (toast_instance){
        // replace existing div
        var container = document.getElementById(toast_container_id);
        container.innerHTML = toastHTML;
    } else {
        // create it
        var actual_html = '<div id="' + toast_container_id + '" >' + toastHTML + '</div>';
        M.toast({html: actual_html, classes: toast_class});
    }
}

// generate a uuid4 string
function uuid4() {
  return 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, function(c) {
    var r = Math.random() * 16 | 0, v = c == 'x' ? r : (r & 0x3 | 0x8);
    return v.toString(16);
  });
}

function RenewAuthToken(){
    if (sessionStorage.getItem('auth_token') !== null){
        // console.log('got token from session storage');
        AUTH_TOKEN = sessionStorage.getItem('auth_token');
    }
    if (AUTH_TOKEN) {
        console.log('Renewing auth token');
        try {
            var xmlHttp = new XMLHttpRequest();
            xmlHttp.open( "POST", '/auth', false);
            xmlHttp.send('{"auth_token": "' + AUTH_TOKEN + '"}'); 
            if (xmlHttp.status === 200) {
                var obj = JSON.parse(xmlHttp.responseText);
                if ('auth_token' in obj) {
                    AUTH_TOKEN = obj.auth_token;
                    sessionStorage.setItem('auth_token', obj.auth_token);
                    return true;
                } else {
                    console.error('Failed to renew auth token. status: 200, but no auth_token in response');
                    return false;
                }
            } else {
                console.error('Failed to renew auth token. status: ' + xmlHttp.status);
                AUTH_TOKEN = null;
                return false;
            }
        } catch(e) {
            console.error('Exception while renewing auth token: ' + e);
            AUTH_TOKEN = null;
            return false;
        }
    }
}

function FetchData_Clients(){
    var fetch_url = './clients';
    var fetch_options = {
        method: 'POST',
        headers: {
            'auth_token': AUTH_TOKEN
        },
    };
    fetch(fetch_url, fetch_options)
        .then(response => {
            return response.json();
        })
        .then(data => {
            CLIENT_LIST = data;
            CreateClientsTab();
            // CreateTableTab();
            M.AutoInit();
        })
        .catch(err => {
            console.error('error while fetching ' + fetch_url);
        });
}

function FetchData_Images(){
    var fetch_url = './images';
    var fetch_options = {
        method: 'POST',
        headers: {
            'auth_token': AUTH_TOKEN
        },
    };
    fetch(fetch_url, fetch_options)
        .then(response => {
            return response.json();
        })
        .then(data => {
           IMAGE_LIST = data;
            CreateImagesTab();
            CreateClientsTab();
            // CreateTableTab();
            M.AutoInit();
        })
        .catch(err => {
            console.error('error while fetching ' + fetch_url);
        });
}

function FetchData_Unattendeds(){
    var fetch_url = './unattendeds';
    var fetch_options = {
        method: 'POST',
        headers: {
            'auth_token': AUTH_TOKEN
        },
    };
    fetch(fetch_url, fetch_options)
        .then(response => {
            return response.json();
        })
        .then(data => {
            UNATTENDED_LIST = data;
            CreateUnattendedsTab();
            CreateClientsTab();
            // CreateTableTab();
            M.AutoInit();
        })
        .catch(err => {
            console.error('error while fetching ' + fetch_url);
        });
}

function FetchData_ISOs(){
    var fetch_url = './isos';
    var fetch_options = {
        method: 'POST',
        headers: {
            'auth_token': AUTH_TOKEN
        },
    };
    fetch(fetch_url, fetch_options)
        .then(response => {
            return response.json();
        })
        .then(data => {
            ISO_LIST = data;
            CreateISOsTab();
            M.AutoInit();
        })
        .catch(err => {
            console.error('error while fetching ' + fetch_url);
        });
}

function FetchData_WizardData(){
    var fetch_url = './wizard-data.json';
    var fetch_options = {
        method: 'POST',
        headers: {
            'auth_token': AUTH_TOKEN
        },
    };
    fetch(fetch_url, fetch_options)
        .then(response => {
            return response.json();
        })
        .then(data => {
            WIZARD_DATA = data;
            CreateWizard_NewImage();
            CreateWizard_Unattended();
            M.AutoInit();
        })
        .catch(err => {
            console.error('error while fetching ' + fetch_url);
        });
}

function FetchData_Log(){
    var fetch_url = './getlog';
    var fetch_options = {
        method: 'POST',
        headers: {
            'auth_token': AUTH_TOKEN
        },
    };
    fetch(fetch_url, fetch_options)
        .then(response => {
            return response.text();
        })
        .then(data => {
            LOG_FILE_CONTENT = data;
            CreateLogTab();
            M.AutoInit();
        })
        .catch(err => {
            console.error('error while fetching ' + fetch_url);
        });
}

function FetchData(){
    // fetch data from each of our endpoints
    // implies rebuild of associated tabs
    console.log('Fetching data');
    FetchData_Clients();
    FetchData_Images();
    FetchData_Unattendeds();
    FetchData_ISOs();
    FetchData_WizardData();
    FetchData_Log();
    M.AutoInit();
}

function FetchStatus(){
    if (AUTH_TOKEN) {
        var report = FetchWithAuthToken('/getjobstatus');
        if (report !== false){
            report_obj = JSON.parse(report);
            for (var this_job in report_obj){
                var job_name = report_obj[this_job].name;
                var job_status = report_obj[this_job].status;
                var job_progress = report_obj[this_job].progress;
                var toast_class = 'toast_status_job_' + this_job;
                var range_class = 'progress_job_' + this_job;
                var toast_container_id = 'toast_container_job_' + this_job;
                var toast_instance;
                try {
                    var instance = M.Toast.getInstance(document.querySelector('.' + toast_class));
                    toast_instance = instance;
                } catch(e) {
                    toast_instance = false;
                }
                var toastHTML = '';
                var toast_button_dismiss_onclick = '(M.Toast.getInstance(document.querySelector(\'.' + toast_class + '\')).dismiss())';
                var toast_button_abort_onclick = '(FetchWithAuthToken(\'/canceljob?job=' + this_job + '\'))';

                toastHTML += '<div style="min-width:300px;">';
                if (job_status === 'done'){
                    toastHTML += '<span>' + job_name + ' is ready</span>';
                    toastHTML += '<span><button class="btn-flat toast-action" onclick="' + toast_button_dismiss_onclick + '">Dismiss</button></span>';
                } else {
                    toastHTML += '<span>Creating: ' + job_name + '</span>';
                    toastHTML += '<span><button class="btn-flat toast-action" onclick="' + toast_button_abort_onclick + '">Abort</button></span>';
                    if (job_progress == 0){
                        toastHTML += '<div class="progress"><div class="indeterminate"></div></div>';
                    } else {
                        toastHTML += '<div class="progress"><div class="determinate" style="width: ' + job_progress + '%"></div></div>';
                    }
                }
                toastHTML += '</div>';

                if (toast_instance){
                    // replace existing div
                    var container = document.getElementById(toast_container_id);
                    container.innerHTML = toastHTML;
                } else {
                    // create it
                    var actual_html = '<div id="' + toast_container_id + '" >' + toastHTML + '</div>';
                    M.toast({html: actual_html, classes: toast_class, displayLength: Infinity});
                }
                
            }
        } else {
            console.error('failed to fetch status!');
            // TODO is this right?
            AUTH_TOKEN = null;
        }
    }
}

// websocket stuff

function onWebSocketOpen(evt) {
    console.log("websocket opened");
}

function onWebSocketClose(evt) {
    console.log("websocket closed");
}

function onWebSocketError(evt) {
    console.error('websocket error: ' + evt.data);
}

function onWebSocketMessage(evt) {
    console.log("websocket message received: " + evt.data);
}

function initiateWebSocketConnection() {
    try {
        WEBSOCKET = new WebSocket(WEBSOCKET_URI);
        console.log('setting up connection to: ' + WEBSOCKET_URI);
        WEBSOCKET.onopen = function (evt) { onWebSocketOpen(evt); };
        WEBSOCKET.onclose = function (evt) { onWebSocketClose(evt); };
        WEBSOCKET.onmessage = function (evt) { onWebSocketMessage(evt); };
        WEBSOCKET.onerror = function (evt) { onWebSocketError(evt); };
    } catch(e) {
        console.error('Unexpected Exception while initiating WebSocket connection: ' + e);
    }
}

function sendWebSocketMessage(message){
    console.log('sending message: ' + message);
    WEBSOCKET.send(message);
}


// General setup for everything
function Setup(){
    try {
        // initiateWebSocketConnection();
        FetchData();
        setInterval(RenewAuthToken, (AUTH_TOKEN_RENEW_CYCLE * 1000));
        setInterval(FetchStatus, (FETCH_STATUS_CYCLE * 1000));
    } catch(e) {
        console.error('Unexpected Exception while Setting Up: ' + e);
    }
}

document.addEventListener('DOMContentLoaded', function() {
    if (! RenewAuthToken()){
        window.location.href = '/login';
    } else {
        M.toast({html: "Successfully Authorized"});
        Setup();
    }
});
