--TEST--
RarArchive read_property handler invalid dimensions
--SKIPIF--
<?php if(!extension_loaded("rar")) print "skip"; ?>
--FILE--
<?php

//see also test #81 for broken archives

$f1 = dirname(__FILE__) . "/latest_winrar.rar";
$a = RarArchive::open($f1);

echo "* -1 (int):\n";
echo $a[-1];

echo "\n* -1 (string):\n";
echo $a["-1"];

echo "\n* -1 (double):\n";
echo $a[(float) -1];

echo "\n* 100:\n";
echo $a[100];

echo "\n* foo:\n";
echo $a["foo"];

echo "\n* 18446744073709551616 (string, 2^64):\n";
echo $a["18446744073709551616"];

echo "\n* -18446744073709551616 (string, -2^64):\n";
echo $a["-18446744073709551616"];

echo "\n* 18446744073709551616 (float, 2^64):\n";
echo $a[(float) 18446744073709551616];

echo "\n* array():\n";
echo $a[array()];

echo "\n* new stdClass():\n";
echo $a[new stdClass()];

echo "\n";
echo "Done.\n";
--EXPECTF--
* -1 (int):

Warning: main(): Dimension index must be non-negative, given -1 in %s on line %d

* -1 (string):

Warning: main(): Dimension index must be non-negative, given -1 in %s on line %d

* -1 (double):

Warning: main(): Dimension index must be non-negative, given -1 in %s on line %d

* 100:

Warning: main(): Dimension index exceeds or equals number of entries in RAR archive in %s on line %d

* foo:

Warning: main(): Attempt to use a non-numeric dimension to access a RarArchive object (invalid string) in %s on line %d

* 18446744073709551616 (string, 2^64):

Warning: main(): Dimension index is out of integer bounds in %s on line %d

* -18446744073709551616 (string, -2^64):

Warning: main(): Dimension index is out of integer bounds in %s on line %d

* 18446744073709551616 (float, 2^64):

Warning: main(): Dimension index is out of integer bounds in %s on line %d

* array():

Warning: main(): Attempt to use a non-numeric dimension to access a RarArchive object (invalid type) in %s on line %d

* new stdClass():

Warning: main(): Attempt to use an object with no get handler as a dimension to access a RarArchive object in %s on line %d

Done.
