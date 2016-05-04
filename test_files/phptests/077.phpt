--TEST--
RarArchive::open NULL can be given to indicate there's no password
--SKIPIF--
<?php if(!extension_loaded("rar")) print "skip"; ?>
--FILE--
<?php

$f = dirname(__FILE__) . '/encrypted_headers.rar';

echo "* No password given:\n";
$file = RarArchive::open($f);
rar_list($file);

echo "* NULL given:\n";
$file = RarArchive::open($f, NULL);
rar_list($file);

echo "* empty string given:\n";
$file = RarArchive::open($f, '');
rar_list($file);

echo "* wrong password given:\n";
$file = RarArchive::open($f, "wrongpassword");
rar_list($file);

echo "\n";
echo "Done.\n";
--EXPECTF--
* No password given:

Warning: rar_list(): ERAR_MISSING_PASSWORD (password needed but not specified) in %s on line %d
* NULL given:

Warning: rar_list(): ERAR_MISSING_PASSWORD (password needed but not specified) in %s on line %d
* empty string given:

Warning: rar_list(): ERAR_MISSING_PASSWORD (password needed but not specified) in %s on line %d
* wrong password given:

Warning: rar_list(): ERAR_BAD_DATA in %s on line %d

Done.
