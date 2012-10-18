--TEST--
Wrapper cache exaustion test
--SKIPIF--
<?php if(!extension_loaded("rar")) print "skip"; ?>
--FILE--
<?php

$f = array();
$f[] = dirname(__FILE__) . "/latest_winrar.rar";
$f[] = dirname(__FILE__) . "/directories.rar";
$f[] = dirname(__FILE__) . "/dirs_and_extra_headers.rar";
$f[] = dirname(__FILE__) . "/encrypted_only_files.rar";
$f[] = dirname(__FILE__) . "/linux_rar.rar";
$f_l = dirname(__FILE__) . "/rar_unicode.rar";

function printstats() {
	echo "Stats: ".rar_wrapper_cache_stats()."\n";
}

echo "* Invalid call to rar_wrapper_cache_stats():\n";
var_dump(rar_wrapper_cache_stats("sfddf"));

echo "\n* Initial stats:\n";
printstats();

echo "\n* Fill cache:\n";
foreach ($f as $n) {
	var_export(file_exists("rar://" . rawurlencode($n)));
	echo "\n";
}
printstats();
clearstatcache();

echo "\n* Hit cache:\n";
foreach ($f as $n) {
	var_export(file_exists("rar://" . rawurlencode($n)));
	echo "\n";
}
printstats();
clearstatcache();

echo "\n* Evict first file:\n";
var_export(file_exists("rar://" . rawurlencode($f_l))); //0 out
echo "\n";
printstats();
clearstatcache();

echo "\n* One hit, one miss:\n";
var_export(file_exists("rar://" . rawurlencode($f[1]))); //hit
echo "\n";
var_export(file_exists("rar://" . rawurlencode($f[0]))); //miss, 1 out
echo "\n";
printstats();
clearstatcache();

echo "\n* Miss on last evicted:\n";
var_export(file_exists("rar://" . rawurlencode($f[1]))); //miss, 2 out
echo "\n";
printstats();
clearstatcache();

echo "\n* Hit on three last added :\n";
var_export(file_exists("rar://" . rawurlencode($f_l)));
echo "\n";
var_export(file_exists("rar://" . rawurlencode($f[0])));
echo "\n";
var_export(file_exists("rar://" . rawurlencode($f[1])));
echo "\n";
printstats();
clearstatcache();

echo "\n";
echo "Done.\n";
--EXPECTF--
* Invalid call to rar_wrapper_cache_stats():

Warning: rar_wrapper_cache_stats() expects exactly 0 parameters, 1 given in %s on line %d
NULL

* Initial stats:
Stats: 0/0 (hits/misses)

* Fill cache:
true
true
true
true
true
Stats: 0/5 (hits/misses)

* Hit cache:
true
true
true
true
true
Stats: 5/5 (hits/misses)

* Evict first file:
true
Stats: 5/6 (hits/misses)

* One hit, one miss:
true
true
Stats: 6/7 (hits/misses)

* Miss on last evicted:
true
Stats: 6/8 (hits/misses)

* Hit on three last added :
true
true
true
Stats: 9/8 (hits/misses)

Done.
