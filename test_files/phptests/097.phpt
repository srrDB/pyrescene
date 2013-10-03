--TEST--
PECL bug #18449 (Extraction of uncompressed and encrypted files fails)
--SKIPIF--
<?php if(!extension_loaded("rar")) print "skip"; ?>
--CLEAN--
<?php
	@unlink(dirname(__FILE__) . '/base.css');
	@unlink(dirname(__FILE__) . '/reset.css');
--FILE--
<?php
$rar_archives = array(
	dirname(__FILE__) . '/secret-crypted-none.rar',
	dirname(__FILE__) . '/secret-none.rar',
);
foreach ($rar_archives as $rar_archive) {
	echo basename($rar_archive), "\n";
	$rar = rar_open($rar_archive, 'secret');
	foreach ($rar as $rar_file) {
		$rar_file->extract(dirname(__FILE__));
	}
	@unlink(dirname(__FILE__) . '/base.css');
	@unlink(dirname(__FILE__) . '/reset.css');
	rar_close($rar);
}

echo "\nDone.\n";
--EXPECTF--
secret-crypted-none.rar
secret-none.rar

Done.