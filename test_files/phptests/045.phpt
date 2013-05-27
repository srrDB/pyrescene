--TEST--
rar_open() with invalid volume callback
--SKIPIF--
<?php
if(!extension_loaded("rar")) die("skip");
--FILE--
<?php

class A {
	public static function resolve($vol) {
		if (preg_match('/_broken/', $vol))
			return str_replace('_broken', '', $vol);
		else
			return null;
	}
	public function resolveInstance($vol) {
		echo "A::resolveInstance()\n";
		return self::resolve($vol);
	}
}

$fn = dirname(__FILE__) . '/multi_broken.part1.rar';

echo "\nNot given a callback:\n";
$rar = RarArchive::open($fn, null, new Exception());

echo "\nGiven static callback for instance method (test IS_CALLABLE_STRICT):\n";
$rar = RarArchive::open($fn, null, "A::resolveInstance");
var_dump($rar);

echo "\nGiven callback that takes more arguments:\n";
$rar = RarArchive::open($fn, null, 'array_walk');
$rar->getEntries();

echo "\nGiven callback that takes another kind of arguments:\n";
$rar = RarArchive::open($fn, null, 'ksort');
$rar->getEntries();

echo "\nGiven callback that returns another kind of arguments:\n";
function testA($vol) { return true; }
$rar = RarArchive::open($fn, null, 'testA');
$rar->getEntries();

echo "\nGiven callback that throws Exception:\n";
function testB($vol) { throw new Exception(); }
$rar = RarArchive::open($fn, null, 'testB');
try {
	$rar->getEntries();
	die("should have thrown exception.");
} catch (Exception $e) {
	echo "OK, threw exception.\n";
}

echo "Done.\n";
--EXPECTF--
Not given a callback:

Warning: RarArchive::open(): Expected the third argument, if provided, to be a valid callback in %s on line %d

Given static callback for instance method (test IS_CALLABLE_STRICT):

Warning: RarArchive::open(): Expected the third argument, if provided, to be a valid callback in %s on line %d
bool(false)

Given callback that takes more arguments:

Warning: array_walk() expects at least %d parameters, 1 given in %s on line %d

Warning: RarArchive::getEntries(): ERAR_EOPEN (file open error) in %s on line %d

Given callback that takes another kind of arguments:

Warning: ksort() expects parameter 1 to be array, string given in %s on line %d

Warning: RarArchive::getEntries(): Wrong type returned by volume find callback, expected string or NULL in %s on line %d

Warning: RarArchive::getEntries(): ERAR_EOPEN (file open error) in %s on line %d

Given callback that returns another kind of arguments:

Warning: RarArchive::getEntries(): Wrong type returned by volume find callback, expected string or NULL in %s on line %d

Warning: RarArchive::getEntries(): ERAR_EOPEN (file open error) in %s on line %d

Given callback that throws Exception:

Warning: RarArchive::getEntries(): Failure to call volume find callback in %s on line %d

Warning: RarArchive::getEntries(): ERAR_EOPEN (file open error) in %s on line %d
OK, threw exception.
Done.

