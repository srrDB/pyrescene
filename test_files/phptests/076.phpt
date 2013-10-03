--TEST--
RarEntry::extract NULL can be given to indicate there's no password
--SKIPIF--
<?php if(!extension_loaded("rar")) print "skip"; ?>
--CLEAN--
<?php
$dest = dirname(__FILE__) . "temp_file";
@unlink($dest);
--FILE--
<?php

$file = RarArchive::open(dirname(__FILE__) . '/encrypted_only_files.rar');

$dest = dirname(__FILE__) . "temp_file";

foreach ($file as $e) {
	echo "* No password given:\n";
	$result = $e->extract('', $dest);
	var_dump($result);
	
	echo "\n* NULL given (should have the same effect as no password):\n";
	$result = $e->extract('', $dest, NULL);
	var_dump($result);
	
	echo "\n* empty string given as password (should have the same ".
		"effect as no password):\n";
	$result = $e->extract('', $dest, '');
	var_dump($result);
	
	echo "\n* password given; a wrong one:\n";
	$result = $e->extract('', $dest, 'wrongpassword');
	var_dump($result);
	
	break;
}

echo "\n";
echo "Done.\n";
--EXPECTF--
* No password given:

Warning: RarEntry::extract(): ERAR_MISSING_PASSWORD (password needed but not specified) in %s on line %d
bool(false)

* NULL given (should have the same effect as no password):

Warning: RarEntry::extract(): ERAR_MISSING_PASSWORD (password needed but not specified) in %s on line %d
bool(false)

* empty string given as password (should have the same effect as no password):

Warning: RarEntry::extract(): ERAR_MISSING_PASSWORD (password needed but not specified) in %s on line %d
bool(false)

* password given; a wrong one:

Warning: RarEntry::extract(): ERAR_BAD_DATA in %s on line %d
bool(false)

Done.
