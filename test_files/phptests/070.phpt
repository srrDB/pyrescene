--TEST--
URL stat PHP_STREAM_URL_STAT_QUIET does not leak memory
--SKIPIF--
<?php if(!extension_loaded("rar")) print "skip"; ?>
--FILE--
<?php

$file = "rar://" .
	dirname(__FILE__) . '/dirlink_unix.rar' .
	"#non_existant_file";

var_dump(is_dir($file));

echo "Done.\n";
--EXPECTF--
bool(false)
Done.
