--TEST--
RarEntry::getStream NULL can be given to indicate there's no password
--SKIPIF--
<?php if(!extension_loaded("rar")) print "skip"; ?>
--FILE--
<?php

$file = RarArchive::open(dirname(__FILE__) . '/encrypted_only_files.rar');

foreach ($file as $e) {
	echo "* No password given:\n";
	$stream = $e->getStream();
	var_dump($stream);
	
	echo "\n* NULL given (should have the same effect as no password):\n";
	$stream = $e->getStream(NULL);
	var_dump($stream);
	
	echo "\n* empty string given as password (should have the same effect; "
		. "rar disallows empty passwords):\n";
	$stream = $e->getStream('');
	var_dump($stream);
	
	echo "\n* non-empty password given; should give stream:\n";
	$stream = $e->getStream('bugabuga');
	var_dump($stream);
	
	break;
}

echo "\n";
echo "Done.\n";
--EXPECTF--
* No password given:

Warning: RarEntry::getStream(): ERAR_MISSING_PASSWORD (password needed but not specified) in %s on line %d
bool(false)

* NULL given (should have the same effect as no password):

Warning: RarEntry::getStream(): ERAR_MISSING_PASSWORD (password needed but not specified) in %s on line %d
bool(false)

* empty string given as password (should have the same effect; rar disallows empty passwords):

Warning: RarEntry::getStream(): ERAR_MISSING_PASSWORD (password needed but not specified) in %s on line %d
bool(false)

* non-empty password given; should give stream:
resource(%d) of type (stream)

Done.
