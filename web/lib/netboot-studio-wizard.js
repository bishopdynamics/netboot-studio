/* Netboot Studio - New Image Wizard

    This file is part of Netboot Studio, a system for managing netboot clients
    Copyright (C) 2019 James Bishop (jamesbishop2006@gmail.com)

info about CodeMirror (js code editor): https://codemirror.net/doc/manual.html#fromTextArea
info about ipxe: http://ipxe.org/
info about materialize: https://materializecss.com/getting-started.html
*/

// linter options 
/*jshint esversion: 6 */


// Utility Functions

function blockSpecialChar(e){
    // block special characters, used for text-nospace input fields
    // modified from: https://stackoverflow.com/questions/24774367/how-to-validate-html-textbox-not-to-allow-special-characters-and-space
    var k;
    // console.log('validating key code: ' + e.keyCode);
    document.all ? k = e.keyCode : k = e.which;
    // below is what to allow
    return ((k > 64 && k < 91) || (k > 96 && k < 123) || k == 8 || k == 45 || k == 46 || k == 95 || (k >= 48 && k <= 57));
}

function HideElem(elem_id){
    var elem = document.getElementById(elem_id);
    elem.classList.add("hide");
}

function UnhideElem(elem_id){
    var elem = document.getElementById(elem_id);
    elem.classList.remove("hide");
}


// functions common to all wizards

function Wizard_CreateInputKey(key, prefix) {
    // input an input key, and prefix
    // return an appropriate input widget with id prefixed by prefix
    
    // var content = '<div class="row" style="padding:10px;">';
    var key_type = key.type;
    var key_description = key.description;
    var key_name = key.name;
    var key_display = key.display;
    var key_default = key.default;
    var key_advanced = key.advanced;
    var extra_class = '';
    if (key_advanced == true) {
        extra_class += ' wizard-input-advanced';
    }
    extra_class += ' card-panel hoverable';
    var content = '<div class="' + extra_class + '">';
    switch(key_type) {
        case 'iso':
            content += '<div class="input-field"><select id="' + prefix + key_name + '">';
            for (var item_num in ISO_LIST) {
                var iso_name = ISO_LIST[item_num];
                content += '<option value="' + iso_name + '">' + iso_name + '</option>';
            }
            content += '</select><label>' + key_display + '</label>';
            content += '<span class="helper-text">' + key_description + '</span>';
            break;
        case 'text':
            // create text input
            content += '<div class="input-field">';
            content += '<input id="' + prefix + key_name + '" type="text" value="' + key_default + '">';
            content += '<label for="' + prefix + key_name + '" class="active">' + key_display + '</label>';
            content += '<span class="helper-text">' + key_description + '</span>';
            break;
        case 'text-nospace':
            // create text input, allowing only a-Z,_,-,0-9
            content += '<div class="input-field">';
            content += '<input id="' + prefix + key_name + '" type="text" value="' + key_default + '" onkeypress="return blockSpecialChar(event)">';
            content += '<label for="' + prefix + key_name + '" class="active">' + key_display + '</label>';
            content += '<span class="helper-text">' + key_description + '</span>';
            break;
        case 'boolean':
            // create a checkbox
            content += '<div class="input-field" style="height:50px;">';
            content += '<label>';
            content += '<input id="' + prefix + key_name + '" type="checkbox" class="filled-in" ';
            if (key.default == true){
                content += 'checked="checked" />';
            } else {
                content += '/>';
            }
            content += '<span>' + key_display + '</span>';
            content += '<span class="helper-text">' + key_description + '</span>';
            content += '</label>';

            break;
        case 'select':
            var select_values = key.select_values;
            content += '<div class="input-field"><select id="' + prefix + key_name + '">';
            for (var item_value in select_values) {
                var item_display = select_values[item_value].display;
                if (item_value == key_default) {
                    content += '<option value="' + item_value + '" selected>' + item_display + '</option>';
                } else {
                    content += '<option value="' + item_value + '">' + item_display + '</option>';
                }
            }
            content += '</select>';
            content += '<label>' + key_display + '</label>';
            content += '<span class="helper-text">' + key_description + '</span>';
            break;
        default:
            console.error('Skip rendering key of type: ' + key_type);
    }
    // we leave div open within switch, thats why we close two here
    content += '</div></div>';
    return content;
}


// New Image Wizard Functions

function Wizard_NewImage_CreateImageTypeForm () {
    // return an html form with radio select buttons to pick image type
    var content = '';
    var image_types = WIZARD_DATA['wizard-newimage-image-types'];
    content += '<form action="#">';
    for (var image_type in image_types){
        var image_display = image_types[image_type].display;
        var image_required_input = image_types[image_type].required_input;
        content += '<p><label>';
        content += '<input class="with-gap" id="wizard_image_type_' + image_type + '" name="wizard_image_type" type="radio"';
        if (image_type == 'windows') {
            // windows is default, so something is checked
            content += ' checked />';
        } else {
            content += '/>';
        }
        content += '<span>' + image_display + '</span>';
        content += '</label></p>';
    }
    content += '</form>';
    return content;
}

function Wizard_NewImage_GetSelectedImageType () {
    // get selected image from imagetypeform in page1
    var selected_type;
    for (var image_type in WIZARD_DATA['wizard-newimage-image-types']){
        var elem = document.getElementById('wizard_image_type_' + image_type);
        if (elem.checked){
            selected_type = image_type;
            break;
        }
    }
    return selected_type;
}

function Wizard_NewImage_CreateInputForm(image_type) {
    // input image type from WIZARD_DATA['wizard-newimage-image-types']
    // return html form with needed fields
    var keys = WIZARD_DATA['wizard-newimage-image-types'][image_type].required_input;
    var image_display = WIZARD_DATA['wizard-newimage-image-types'][image_type].display;
    var content = '';
    content += '<form action="#" style="width:100%;">';
    content += '<h5>' + image_display + '</h5><p>&nbsp;</p>';
    for (var key_num in keys) {
        var key = keys[key_num];
        content += Wizard_CreateInputKey(WIZARD_DATA['wizard-newimage-input-keys'][key], 'wizard_newimage_input_key_');
    }
    content += '</form>';
    return content;
}

function Wizard_NewImage_GetAnswers(){
    // get value of all input fields
    // field ids are prefixed with: wizard_newimage_input_key_
    var selected_image_type = Wizard_NewImage_GetSelectedImageType();
    var keys = WIZARD_DATA['wizard-newimage-image-types'][selected_image_type].required_input;
    var data = {};
    for (var key_num in keys){
        var key_name = keys[key_num];
        var key_value;
        var elem = document.getElementById('wizard_newimage_input_key_' + key_name);
        if (elem.type == 'checkbox'){
            key_value = elem.checked;
        } else {
            key_value = elem.value;
        }
        if (key_name == 'iso' || key_name == 'name') {
            if (!key_value){
                M.toast({html: '"' + key_name + '" cannot be left blank!'});
                return false;
            }
        }
        data[key_name] = key_value;
    }
    data.image_type = selected_image_type;
    return data;
}

function Wizard_NewImage_NextPage(){
    // advance to page2
    var selected_image_type = Wizard_NewImage_GetSelectedImageType();
    HideElem('modal_wizard_newimage_nextbutton');
    UnhideElem('modal_wizard_newimage_backbutton');
    UnhideElem('modal_wizard_newimage_finishbutton');
    HideElem('modal_wizard_newimage_page1');
    UnhideElem('modal_wizard_newimage_page2');
    document.getElementById('modal_wizard_newimage_page2').innerHTML = Wizard_NewImage_CreateInputForm(selected_image_type);
    var elems = document.querySelectorAll('select');
    var instances = M.FormSelect.init(elems);
    M.updateTextFields();
}

function Wizard_NewImage_PrevPage(){
    // go back to page1
    UnhideElem('modal_wizard_newimage_nextbutton');
    HideElem('modal_wizard_newimage_backbutton');
    HideElem('modal_wizard_newimage_finishbutton');
    UnhideElem('modal_wizard_newimage_page1');
    HideElem('modal_wizard_newimage_page2');
}

function Wizard_NewImage_Finish(){
    // collect input data and send it to backend
    var modal_instance = M.Modal.getInstance(document.getElementById("modal_wizard_newimage"));
    var wizard_answers = Wizard_NewImage_GetAnswers();
    if (wizard_answers !== false){
        var response = FetchWithAuthToken('/createimage', JSON.stringify(wizard_answers));
        if (response !== false){
            // M.toast({html: "Started new CreateImage job"});
            FetchStatus();
            modal_instance.close();
            Wizard_NewImage_PrevPage();
        } else {
            M.toast({html: "Failed to start new CreateImage job"});
        }
    } else {
        console.warn('cannot proceed, check input fields');
    }
}

function CreateWizard_NewImage(){
    // populate the modal for new image wizard
    try {
        var target_div = document.getElementById('modal_wizard_newimage');
        var wizard_html = '';
        wizard_html += '<div class="modal-content"><h4>New Image</h4>';
        wizard_html += '<div id="modal_wizard_newimage_page1"class="modal_page">';
        wizard_html += Wizard_NewImage_CreateImageTypeForm();
        wizard_html += '</div>';
        wizard_html += '<div id="modal_wizard_newimage_page2" class="modal_page hide">';
        wizard_html += '</div>';
        wizard_html += '</div>';
        wizard_html += '<div class="modal-footer">';
        wizard_html += '<a href="#!" class="modal-close waves-effect waves-green btn-flat" onclick="Wizard_NewImage_PrevPage()">Cancel</a>';
        wizard_html += '<a href="#!" id="modal_wizard_newimage_backbutton" class="hide waves-effect waves-green btn-flat" onclick="Wizard_NewImage_PrevPage()">Back</a>';
        wizard_html += '<a href="#!" id="modal_wizard_newimage_nextbutton" class="waves-effect waves-green btn-flat" onclick="Wizard_NewImage_NextPage()">Next</a>';
        wizard_html += '<a href="#!" id="modal_wizard_newimage_finishbutton" class="hide waves-effect waves-green btn-flat" onclick="Wizard_NewImage_Finish()">Finish</a>';
        wizard_html += '</div>';
        target_div.innerHTML = wizard_html;
    } catch(e) {
        console.error('error while creating new image wizard: ' + e.message);
    }
}

function ShowWizard_NewImage(){
    // make the wizard visible
    var modal_instance = M.Modal.getInstance(document.getElementById("modal_wizard_newimage"));
    modal_instance.open();
}


// Unattended Wizard Functions

function Wizard_Unattended_CreateOSTypeForm () {
    // return an html form with radio select buttons to pick image type
    var content = '';
    var os_types = WIZARD_DATA['wizard-unattended-input-keys'];
    content += '<form action="#">';
    // text input for file name
    content += '<div class="input-field">';
    content += '<input id="wizard_unattended_input_key_filename" type="text" value="My-New-File.cfg" onkeypress="return blockSpecialChar(event)">';
    content += '<label for="wizard_unattended_input_key_filename" class="active">Unattended File Name</label>';
    content += '<span class="helper-text">Name your new unattended file (only 0-9 A-Z - _ .)</span>';
    content += '</div>';

    for (var os_type in os_types){
        var os_display = os_types[os_type].display;
        content += '<p><label>';
        content += '<input class="with-gap" id="wizard_os_type_' + os_type + '" name="wizard_os_type" type="radio"';
        if (os_type == 'windows') {
            // windows is default, so something is checked
            content += ' checked />';
        } else {
            content += '/>';
        }
        content += '<span>' + os_display + '</span>';
        content += '</label></p>';
    }
    content += '</form>';
    return content;
}

function Wizard_Unattended_GetSelectedOSType () {
    // get selected image from imagetypeform in page1
    var selected_type;
    for (var os_type in WIZARD_DATA['wizard-unattended-input-keys']){
        var elem = document.getElementById('wizard_os_type_' + os_type);
        if (elem.checked){
            selected_type = os_type;
            break;
        }
    }
    return selected_type;
}

function Wizard_Unattended_CreateInputForm(os_type) {
    // input os type from WIZARD_DATA['wizard-unattended-input-keys']
    // return html form with needed fields
    var keys = WIZARD_DATA['wizard-unattended-input-keys'][os_type];
    var os_display = keys.display;
    var content = '';
    var advanced_checkbox_onchange = '(function(event){HandleCheckboxChange_ShowAdvancedOptions(event.checked)})(this)';
    content += '<form action="#" style="width:100%;">';
    // content += '<h5>' + os_display + '</h5>';
    content += '<div class="input-field" style="height:50px;"><label>';
    content += '<input id="wizard_show_advanced_options" type="checkbox" class="filled-in" onchange="' + advanced_checkbox_onchange + '"/><span>Show Advanced Options</span>';
    content += '</label></div>';

    for (var key_name in keys) {
        var key = keys[key_name];
        // console.log('processing key_name: ' + key_name + ' which is: ' + key)
        if (key_name !== 'display') {
            content += Wizard_CreateInputKey(key, 'wizard_unattended_input_key_');
        }
    }
    content += '</form>';
    return content;
}

function Wizard_Unattended_GetAnswers(){
    // get value of all input fields
    // field ids are prefixed with: wizard_unattended_input_key_
    var selected_os_type = Wizard_Unattended_GetSelectedOSType();
    var keys = WIZARD_DATA['wizard-unattended-input-keys'][selected_os_type];
    var data = {};
    for (var key_name in keys){
        // console.log('getting value for key_name: ' + key_name);
        if (key_name == 'display') {
            continue;
        }
        var key_value;
        var elem = document.getElementById('wizard_unattended_input_key_' + key_name);
        if (elem.type == 'checkbox'){
            key_value = elem.checked;
        } else {
            key_value = elem.value;
        }
        data[key_name] = key_value;
    }
    data.filename = document.getElementById('wizard_unattended_input_key_filename').value;
    data.os_type = selected_os_type;
    return data;
}


function HandleCheckboxChange_ShowAdvancedOptions(new_value){
    if (new_value === true){
        Wizard_Show_Advanced();
    } else {
        Wizard_Hide_Advanced();
    }
}

function Wizard_Show_Advanced(){
    var elems = document.querySelectorAll('.wizard-input-advanced');
    for (i = 0; i < elems.length; i++) {
        var elem = elems[i];
        elem.classList.remove("hide");
    }
    var select_elems = document.querySelectorAll('select');
    var instances = M.FormSelect.init(select_elems);
    M.updateTextFields();
}

function Wizard_Hide_Advanced(){
    var elems = document.querySelectorAll('.wizard-input-advanced');
    for (i = 0; i < elems.length; i++) {
        var elem = elems[i];
        elem.classList.add("hide");
    }
    var select_elems = document.querySelectorAll('select');
    var instances = M.FormSelect.init(select_elems);
    M.updateTextFields();
}

function Wizard_Unattended_NextPage(){
    // advance to page2
    var selected_os_type = Wizard_Unattended_GetSelectedOSType();
    HideElem('modal_wizard_unattended_nextbutton');
    UnhideElem('modal_wizard_unattended_backbutton');
    UnhideElem('modal_wizard_unattended_finishbutton');
    HideElem('modal_wizard_unattended_page1');
    UnhideElem('modal_wizard_unattended_page2');
    document.getElementById('modal_wizard_unattended_page2').innerHTML = Wizard_Unattended_CreateInputForm(selected_os_type);
    Wizard_Hide_Advanced();
    var elems = document.querySelectorAll('select');
    var instances = M.FormSelect.init(elems);
    M.updateTextFields();
}

function Wizard_Unattended_Finish(){
    // collect input data and send it to backend
    var modal_instance = M.Modal.getInstance(document.getElementById("modal_wizard_unattended"));
    var wizard_answers = Wizard_Unattended_GetAnswers();
    if (wizard_answers !== false){
        var response = FetchWithAuthToken('/createunattended', JSON.stringify(wizard_answers));
        if (response !== false){
            // M.toast({html: "Started new CreateUnattended job"});
            FetchStatus();
            modal_instance.close();
            Wizard_Unattended_PrevPage();
        } else {
            M.toast({html: "Failed to start new CreateUnattended job"});
        }
    } else {
        console.warn('cannot proceed, check input fields');
    }
}

function Wizard_Unattended_PrevPage(){
    // go back to page1
    UnhideElem('modal_wizard_unattended_nextbutton');
    HideElem('modal_wizard_unattended_backbutton');
    HideElem('modal_wizard_unattended_finishbutton');
    UnhideElem('modal_wizard_unattended_page1');
    HideElem('modal_wizard_unattended_page2');
}

function CreateWizard_Unattended(){
    // populate the modal for new image wizard
    try {
        var target_div = document.getElementById('modal_wizard_unattended');
        var wizard_html = '';
        wizard_html += '<div class="modal-content"><h4>New Unattended Answer File</h4>';
        wizard_html += '<div id="modal_wizard_unattended_page1"class="modal_page">';
        wizard_html += Wizard_Unattended_CreateOSTypeForm();
        wizard_html += '</div>';
        wizard_html += '<div id="modal_wizard_unattended_page2" class="modal_page hide">';
        wizard_html += '</div>';
        wizard_html += '</div>';
        wizard_html += '<div class="modal-footer">';
        wizard_html += '<a href="#!" class="modal-close waves-effect waves-green btn-flat" onclick="Wizard_Unattended_PrevPage()">Cancel</a>';
        wizard_html += '<a href="#!" id="modal_wizard_unattended_backbutton" class="hide waves-effect waves-green btn-flat" onclick="Wizard_Unattended_PrevPage()">Back</a>';
        wizard_html += '<a href="#!" id="modal_wizard_unattended_nextbutton" class="waves-effect waves-green btn-flat" onclick="Wizard_Unattended_NextPage()">Next</a>';
        wizard_html += '<a href="#!" id="modal_wizard_unattended_finishbutton" class="hide waves-effect waves-green btn-flat" onclick="Wizard_Unattended_Finish()">Finish</a>';
        wizard_html += '</div>';
        target_div.innerHTML = wizard_html;
    } catch(e) {
        console.error('error while creating unattended wizard: ' + e.message);
    }
}

function ShowWizard_Unattended(){
    // make the wizard visible
    var modal_instance = M.Modal.getInstance(document.getElementById("modal_wizard_unattended"));
    modal_instance.open();
}

