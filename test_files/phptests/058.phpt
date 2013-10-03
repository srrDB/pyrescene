--TEST--
RAR file stream stat applied to directory consistency with url stat
--SKIPIF--
<?php
if(!extension_loaded("rar")) die("skip");
--FILE--
<?php
$u = "rar://" .
	dirname(__FILE__) . '/dirlink_unix.rar' .
	"#emptydir";
$stream = fopen($u, "r");
$fs = (fstat($stream));

$us = stat($u);

var_dump($fs == $us);

var_dump(is_dir($u));

echo "Done.\n";
--EXPECTF--
bool(true)
bool(true)
Done.
