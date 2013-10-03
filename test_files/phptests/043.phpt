--TEST--
rar_open() with volume find (callback variants 1)
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
	public static function resolveStatic($vol) {
		echo "A::resolveStatic()\n";
		return self::resolve($vol);
	}
	
	public function resolveInstance($vol) {
		echo "A::resolveInstance()\n";
		return self::resolve($vol);
	}
}

$fn = dirname(__FILE__) . '/multi_broken.part1.rar';
$rar = RarArchive::open($fn, null, "A::resolveStatic");
$rar->getEntries();
$rar = RarArchive::open($fn, null, array("A", "resolveStatic"));
$rar->getEntries();
$rar = RarArchive::open($fn, null, array(new A(), "resolveInstance"));
$rar->getEntries();
function testA() {
	global $fn;
	$obj = new A();
	return RarArchive::open($fn, null, array($obj, "resolveInstance"));
}
$rar = testA();
$rar->getEntries();
echo "Done.\n";
--EXPECTF--
A::resolveStatic()
A::resolveStatic()
A::resolveInstance()
A::resolveInstance()
Done.

