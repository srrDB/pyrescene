--TEST--
PECL bug #18449 (Extraction of uncompressed and encrypted files fails; stream variant)
--SKIPIF--
<?php if(!extension_loaded("rar")) print "skip"; ?>
--CLEAN--
<?php
	@unlink(dirname(__FILE__) . '/base.css');
	@unlink(dirname(__FILE__) . '/reset.css');
--FILE--
<?php

$rar = rar_open(dirname(__FILE__) . '/secret-none.rar', 'secret');
foreach ($rar as $rar_file) {
	var_dump(strlen(stream_get_contents($rar_file->getStream())));
}

echo "\nDone.\n";
--EXPECTF--
int(2279)
int(1316)

Done.