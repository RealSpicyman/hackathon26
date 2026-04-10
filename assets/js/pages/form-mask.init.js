/*
Template Name: Skote - Admin & Dashboard Template
Author: Themesbrand
Website: https://themesbrand.com/
Contact: themesbrand@gmail.com
File: Form mask Js File
*/

// Date Style 1

var date1Selector = document.getElementById("input-date1");

var im = new Inputmask("dd/mm/yyyy");
im.mask(date1Selector);

// Date Style 2

var date2Selector = document.getElementById("input-date2");

var im = new Inputmask("mm/dd/yyyy");
im.mask(date2Selector);

// Date time

var datetimeSelector = document.getElementById("input-datetime");

var im = new Inputmask("dd-mm-yyyy HH:MM:ss");
im.mask(datetimeSelector);

// Currency:  
var currencySelector = document.getElementById("input-currency");

var im = new Inputmask("$ 0.00");
im.mask(currencySelector);

// IP address

var ipSelector = document.getElementById("input-ip");

var im = new Inputmask("99.99.99.99");
im.mask(ipSelector);

// email

var emailSelector = document.getElementById("input-email");

var im = new Inputmask("_@_._");

im.mask(emailSelector);

// repeat
var repeatSelector = document.getElementById("input-repeat");

var im = new Inputmask("9999999999");
im.mask(repeatSelector);

// Mask

var selector = document.getElementById("input-mask");

var im = new Inputmask("99-9999999");
im.mask(selector);

//or

// Inputmask({"mask": "(999) 999-9999", ... other_options, ...}).mask(selector);
// Inputmask("9-a{1,3}9{1,3}").mask(selector);
// Inputmask("9", { repeat: 10 }).mask(selector);

// Inputmask({ regex: "\\d*" }).mask(selector);
// Inputmask({ regex: String.raw`\d*` }).mask(selector);