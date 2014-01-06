--TEST--
RarArchive count elements handler test
--SKIPIF--
<?php if(!extension_loaded("rar")) print "skip"; ?>
--FILE--
<?php

$f = dirname(__FILE__) . "/dirs_and_extra_headers.rar";
$fempty = dirname(__FILE__) . "/garbage.part03.rar";

echo "* Normal test:\n";
$a = RarArchive::open($f);
echo "Count: " . count($a) . "\n";

echo "\n* Closed file test (1):\n";
$a = RarArchive::open($f);
$a->close();
var_dump(count($a));

echo "\n* Closed file test (2):\n";
$a = RarArchive::open($f);
$a->getEntries();
$a->close();
var_dump(count($a));

echo "\n* Closed file test (3, exceptions):\n";
$a = RarArchive::open($f);
RarException::setUsingExceptions(true);
$a->getEntries();
$a->close();
try {
	var_dump(count($a));
} catch (RarException $e) {
	echo "OK, threw exception with message \"".$e->getMessage()."\"\n";
}
RarException::setUsingExceptions(false);

echo "\n* Empty file:\n";

$a = RarArchive::open($fempty);
echo "Count: " . count($a) . "\n";

echo "\n";
echo "Done.\n";
--EXPECTF--
* Normal test:
Count: 13

* Closed file test (1):

Warning: count(): The archive is already closed in %s on line %d
int(0)

* Closed file test (2):

Warning: count(): The archive is already closed in %s on line %d
int(0)

* Closed file test (3, exceptions):
OK, threw exception with message "The archive is already closed"

* Empty file:
Count: 0

Done.
