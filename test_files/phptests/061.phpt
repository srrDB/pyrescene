--TEST--
RAR directory stream attempt on file
--SKIPIF--
<?php
if(!extension_loaded("rar")) die("skip");
--FILE--
<?php
$u = "rar://" .
	dirname(__FILE__) . '/dirlink_unix.rar' .
	"#file";
var_dump(opendir($u));

echo "Done.\n";
--EXPECTF--
Warning: opendir(rar://%sdirlink_unix.rar#file): failed to open dir: Archive %sdirlink_unix.rar has an entry named file, but it is not a directory in %s on line %d
bool(false)
Done.
