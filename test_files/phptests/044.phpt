--TEST--
rar_open() with volume find (callback variants 2)
--SKIPIF--
<?php
if(!extension_loaded("rar")) die("skip");
if(!defined('PHP_VERSION_ID') || PHP_VERSION_ID<50300) die("skip");
--FILE--
<?php
class A {
	public static function resolve($vol) {
		if (preg_match('/_broken/', $vol))
			return str_replace('_broken', '', $vol);
		else
			return null;
	}
	public function __invoke($vol) {
		echo "A::__invoke()\n";
		return self::resolve($vol);
	}
}

$fn = dirname(__FILE__) . '/multi_broken.part1.rar';
$f = function ($vol) {
	echo "Closure\n";
	return A::resolve($vol);
};
$rar = RarArchive::open($fn, null, new A());
$rar->getEntries();
$rar = RarArchive::open($fn, null, $f);
$rar->getEntries();

$f2 = function ($vol) {
	echo "Closure (2)\n";
	return A::resolve($vol);
};
$rar = RarArchive::open($fn, null, $f2);
unset($f2);
$rar->getEntries();
echo "Done.\n";
--EXPECTF--
A::__invoke()
Closure
Closure (2)
Done.

