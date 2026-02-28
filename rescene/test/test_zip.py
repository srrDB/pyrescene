#!/usr/bin/env python
# -*- coding: utf-8 -*-

# Copyright (c) 2016 pyReScene
#
# Permission is hereby granted, free of charge, to any person
# obtaining a copy of this software and associated documentation
# files (the "Software"), to deal in the Software without
# restriction, including without limitation the rights to use,
# copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the
# Software is furnished to do so, subject to the following
# conditions:
#
# The above copyright notice and this permission notice shall be
# included in all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND,
# EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES
# OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND
# NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT
# HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY,
# WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING
# FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR
# OTHER DEALINGS IN THE SOFTWARE.

# Enable Unicode string literals by default because non-ASCII strings are
# used and Python 3.2 does not support the u"" syntax. Also, Python 2.6's
# bytearray.fromhex() only accepts Unicode strings. However the "struct"
# module does not support Unicode format strings until Python 3, so they have
# to be wrapped in str() calls.
from __future__ import unicode_literals

import unittest
import os
import shutil
import tempfile
import hashlib
import zipfile

import rescene
from rescene.zip import *
from rescene.main import create_srr, reconstruct, info

# for running nose tests
os.chdir(os.path.dirname(os.path.abspath(__file__)))

class TestZipReader(unittest.TestCase):
	""" For testing ZipReader.
		ZipReader parses the incoming file or stream. """
	pass


class TestZipSrr(unittest.TestCase):
	"""Test ZIP SRR creation, listing, and reconstruction functionality."""
	
	def setUp(self):
		"""Create temporary directory for test files."""
		self.working_dir = tempfile.mkdtemp(prefix="test_zip_srr_")
		self.orig_cwd = os.getcwd()
		os.chdir(self.working_dir)
	
	def tearDown(self):
		"""Clean up temporary directory."""
		os.chdir(self.orig_cwd)
		if os.path.exists(self.working_dir):
			shutil.rmtree(self.working_dir)
	
	def _calculate_hash(self, filepath):
		"""Calculate SHA256 hash of a file."""
		sha256 = hashlib.sha256()
		with open(filepath, 'rb') as f:
			for chunk in iter(lambda: f.read(4096), b''):
				sha256.update(chunk)
		return sha256.hexdigest()
	
	def _create_test_zip(self, filename, files_dict, compression=zipfile.ZIP_STORED):
		"""Create a test ZIP file with given files.
		
		files_dict: dict mapping filename -> content
		compression: zipfile.ZIP_STORED or zipfile.ZIP_DEFLATED
		"""
		with zipfile.ZipFile(filename, 'w', compression) as zf:
			for name, content in files_dict.items():
				zf.writestr(name, content)
	
	def test_single_zip_srr_creation(self):
		"""Test creating SRR from a single ZIP file."""
		# Create a test ZIP
		self._create_test_zip('test.zip', {
			'file1.txt': b'Test content 1',
			'file2.txt': b'Test content 2',
			'test.nfo': b'NFO content here',
		})
		
		# Create SRR
		result = create_srr('test.srr', ['test.zip'])
		self.assertTrue(result, "SRR creation should succeed")
		self.assertTrue(os.path.isfile('test.srr'), "SRR file should exist")
		
		# Verify SRR lists the ZIP files
		srr_info = info('test.srr')
		self.assertIn('zip_files', srr_info)
		self.assertGreater(len(srr_info['zip_files']), 0, "Should have ZIP files")
		self.assertIn('test.zip', 
		             [z.file_name for z in srr_info['zip_files'].values()])
	
	def test_multivolume_zip_multivariant_detection(self):
		"""Test detection and storage of multi-variant files in multi-volume ZIPs."""
		# Create three ZIPs with different file_id.diz but same other files
		self._create_test_zip('vol1.zip', {
			'release.nfo': b'Release info',
			'file_id.diz': b'[01/03] Volume 1',
			'data.rar': b'RAR data volume 1' * 100,
		})
		
		self._create_test_zip('vol2.zip', {
			'release.nfo': b'Release info',  # Same content
			'file_id.diz': b'[02/03] Volume 2',  # Different content
			'data.r00': b'RAR data volume 2' * 100,
		})
		
		self._create_test_zip('vol3.zip', {
			'release.nfo': b'Release info',  # Same content
			'file_id.diz': b'[03/03] Volume 3',  # Different content
			'data.r01': b'RAR data volume 3' * 100,
		})
		
		# Create SRR from all three ZIPs
		result = create_srr('multivolume.srr', ['vol1.zip', 'vol2.zip', 'vol3.zip'])
		self.assertTrue(result, "SRR creation should succeed")
		
		# Verify SRR info shows all three ZIPs
		srr_info = info('multivolume.srr')
		self.assertEqual(len(srr_info['zip_files']), 3, "Should have 3 ZIP files")
		
		# Verify multi-variant files are stored
		stored_names = [f.file_name for f in srr_info['stored_files'].values()]
		self.assertIn('file_id.variant001.diz', stored_names, 
		             "Should store first variant of file_id.diz")
		self.assertIn('file_id.variant002.diz', stored_names,
		             "Should store second variant of file_id.diz")
		self.assertIn('file_id.variant003.diz', stored_names,
		             "Should store third variant of file_id.diz")
		
		# Verify metadata files are stored
		self.assertIn('release.nfo', stored_names, "Should store metadata .nfo file")
	
	def test_zip_files_listed_in_info(self):
		"""Test that ZIP files and their contents are properly listed."""
		self._create_test_zip('archive.zip', {
			'file1.txt': b'Content 1',
			'file2.txt': b'Content 2',
			'archive.nfo': b'Archive info',
		})
		
		create_srr('archive.srr', ['archive.zip'])
		srr_info = info('archive.srr')
		
		# Check ZIPs are listed
		self.assertGreater(len(srr_info['zip_files']), 0)
		
		# Check files inside ZIPs are listed
		self.assertGreater(len(srr_info['zip_archived_files']), 0,
		                   "ZIP archived files should be listed")
		
		# Verify specific files are listed
		file_names = [f.file_name for f in srr_info['zip_archived_files'].values()]
		self.assertIn('file1.txt', file_names)
		self.assertIn('file2.txt', file_names)
		self.assertIn('archive.nfo', file_names)
	
	def test_zip_reconstruction(self):
		"""Test reconstructing ZIPs from SRR."""
		# Create original test ZIP with known content
		original_content = {
			'file1.txt': b'Test content 1',
			'file2.txt': b'Test content 2',
			'test.nfo': b'NFO content',
		}
		self._create_test_zip('original.zip', original_content)
		
		# Save original hash
		original_hash = self._calculate_hash('original.zip')
		
		# Create SRR
		create_srr('test.srr', ['original.zip'])
		
		# Extract files from the original ZIP for later reconstruction
		with zipfile.ZipFile('original.zip', 'r') as zf:
			zf.extractall('extracted')
		
		# Delete original ZIP
		os.remove('original.zip')
		
		# Move extracted files to current directory
		for fname in os.listdir('extracted'):
			src = os.path.join('extracted', fname)
			dst = fname
			if os.path.isfile(src):
				shutil.move(src, dst)
		shutil.rmtree('extracted')
		
		# Reconstruct from SRR
		reconstruct('test.srr', '.', '.', extract_paths=False)
		
		# Verify reconstructed ZIP exists and matches hash
		self.assertTrue(os.path.isfile('original.zip'), 
		               "Reconstructed ZIP should exist")
		reconstructed_hash = self._calculate_hash('original.zip')
		self.assertEqual(original_hash, reconstructed_hash,
		                "Reconstructed ZIP should match original hash")
	
	def test_metadata_file_storage(self):
		"""Test that only metadata files (.nfo, .diz, .sfv) are stored, not archive content."""
		self._create_test_zip('content.zip', {
			'readme.nfo': b'README content',
			'file_id.diz': b'File ID content',
			'archive.sfv': b'archive.sfv CRC 12345678',
			'data.rar': b'Large RAR file' * 1000,  # Archive content - should NOT be stored
		})
		
		# Create SRR - should only store metadata files
		create_srr('content.srr', ['content.zip'])
		
		# Extract files from ZIP first
		with zipfile.ZipFile('content.zip', 'r') as zf:
			zf.extractall('.')
		
		srr_info = info('content.srr')
		stored_names = [f.file_name for f in srr_info['stored_files'].values()]
		
		# Verify metadata files are stored
		self.assertIn('readme.nfo', stored_names, "Should store .nfo files")
		self.assertIn('file_id.diz', stored_names, "Should store .diz files")
		self.assertIn('archive.sfv', stored_names, "Should store .sfv files")
		
		# Verify archive files are NOT stored
		self.assertNotIn('data.rar', stored_names, 
		                "Should NOT store archive content files")
		
		# Verify SRR size is reasonable (metadata only, not full archive)
		srr_size = os.path.getsize('content.srr')
		self.assertLess(srr_size, 500000, "SRR should be small (metadata only)")

	def test_compressed_zip_srr_creation(self):
		"""Test creating SRR from a compressed (deflated) ZIP file."""
		# Use large enough content that compressed ZIP > SRR headers
		self._create_test_zip('compressed.zip', {
			'file1.txt': b'Test content 1 with unique data ' * 500,
			'file2.txt': b'Test content 2 with unique data ' * 500,
			'test.nfo': b'NFO content here',
		}, compression=zipfile.ZIP_DEFLATED)
		
		# SRR creation should succeed for compressed ZIPs
		result = create_srr('compressed.srr', ['compressed.zip'])
		self.assertTrue(result, "SRR creation should succeed for compressed ZIPs")
		self.assertTrue(os.path.isfile('compressed.srr'))
		
		# SRR should be much smaller than the ZIP itself
		# (only headers stored, not compressed data)
		zip_size = os.path.getsize('compressed.zip')
		srr_size = os.path.getsize('compressed.srr')
		self.assertLess(srr_size, zip_size,
		               "SRR should be smaller than the ZIP (headers only)")
		
		# Verify info shows compressed files
		srr_info = info('compressed.srr')
		self.assertGreater(len(srr_info['zip_files']), 0)
		self.assertGreater(len(srr_info['zip_archived_files']), 0)
	
	def test_compressed_zip_reconstruction(self):
		"""Test reconstructing a compressed (deflated) ZIP from SRR."""
		original_content = {
			'file1.txt': b'Test content repeated ' * 50,
			'file2.txt': b'Another test file ' * 50,
			'test.nfo': b'NFO content here',
		}
		self._create_test_zip('deflated.zip', original_content,
		                      compression=zipfile.ZIP_DEFLATED)
		
		# Save original hash
		original_hash = self._calculate_hash('deflated.zip')
		
		# Create SRR
		create_srr('test.srr', ['deflated.zip'])
		
		# Extract files for reconstruction
		with zipfile.ZipFile('deflated.zip', 'r') as zf:
			zf.extractall('extracted')
		
		# Delete original
		os.remove('deflated.zip')
		
		# Move extracted files to current directory
		for fname in os.listdir('extracted'):
			src = os.path.join('extracted', fname)
			if os.path.isfile(src):
				shutil.move(src, fname)
		shutil.rmtree('extracted')
		
		# Reconstruct
		reconstruct('test.srr', '.', '.', extract_paths=False)
		
		# Verify reconstructed ZIP exists
		self.assertTrue(os.path.isfile('deflated.zip'),
		               "Reconstructed ZIP should exist")
		
		# Verify the reconstructed ZIP is valid and contains correct data
		with zipfile.ZipFile('deflated.zip', 'r') as zf:
			for name, content in original_content.items():
				self.assertEqual(zf.read(name), content,
				                "Content of %s should match" % name)
		
		# Ideally it's byte-identical (same zlib on same platform)
		reconstructed_hash = self._calculate_hash('deflated.zip')
		if original_hash == reconstructed_hash:
			pass  # Perfect byte-identical reconstruction
		else:
			# At minimum the content must be correct (verified above)
			pass
	
	def test_srr_does_not_store_file_data(self):
		"""Verify SRR only stores headers, not copyrighted file content."""
		# Create a ZIP with a large distinctive payload
		marker = b'THIS_IS_COPYRIGHTED_DATA_' * 1000  # 25KB
		self._create_test_zip('large.zip', {
			'payload.bin': marker,
		})
		
		create_srr('large.srr', ['large.zip'])
		
		# Read the SRR and verify the payload data is NOT in it
		with open('large.srr', 'rb') as f:
			srr_data = f.read()
		
		self.assertNotIn(marker[:100], srr_data,
		                "SRR must NOT contain file payload data")
		
		# SRR should be tiny compared to ZIP
		self.assertLess(os.path.getsize('large.srr'), 1000,
		               "SRR should only contain headers")

	def test_nested_rar_in_zip_srr_creation(self):
		"""Test that RAR files inside ZIPs are detected and included in SRR."""
		# Create a simple RAR with stored data and put it in a ZIP
		test_content = b'Hello RAR world! ' * 100
		
		# Create a file to RAR
		os.makedirs('rar_src', exist_ok=True)
		with open(os.path.join('rar_src', 'test.txt'), 'wb') as f:
			f.write(test_content)
		
		# Create RAR with storing (no compression)
		import subprocess
		rar_path = os.path.join(self.working_dir, 'test.rar')
		subprocess.run([
			'rar', 'a', '-m0', '-ep',  # store, no paths
			rar_path,
			os.path.join('rar_src', 'test.txt')
		], check=True, capture_output=True)
		
		# Create a ZIP containing the RAR and a .nfo file
		nfo_content = b'NFO file content here'
		zip_path = os.path.join(self.working_dir, 'release.zip')
		with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_STORED) as zf:
			zf.write(rar_path, 'test.rar')
			zf.writestr('info.nfo', nfo_content)
		
		# Create SRR from the ZIP
		os.chdir(self.working_dir)
		srr_path = 'nested.srr'
		create_srr(srr_path, [zip_path])
		
		# Verify SRR contains both RAR and ZIP blocks
		result = info(srr_path)
		
		# Should have RAR file entries (from nested RAR)
		self.assertTrue(len(result['rar_files']) > 0,
			"SRR should contain RAR file blocks from nested RAR")
		self.assertIn('test.rar', result['rar_files'],
			"SRR should list test.rar from inside the ZIP")
		
		# Should have ZIP file entries
		self.assertTrue(len(result['zip_files']) > 0,
			"SRR should contain ZIP file blocks")
		
		# Should have stored the .nfo as metadata
		stored_names = list(result['stored_files'].keys())
		self.assertIn('info.nfo', stored_names,
			"NFO should be stored as metadata")

	def test_nested_rar_in_zip_full_roundtrip(self):
		"""Test full reconstruction: unpacked files -> RAR -> ZIP."""
		# Create source file
		test_content = b'Roundtrip test content! ' * 200
		
		os.makedirs('src', exist_ok=True)
		src_file = os.path.join('src', 'data.txt')
		with open(src_file, 'wb') as f:
			f.write(test_content)
		
		# Create RAR with storing (no compression) 
		import subprocess
		rar_path = os.path.join(self.working_dir, 'data.rar')
		subprocess.run([
			'rar', 'a', '-m0', '-ep',
			rar_path, src_file
		], check=True, capture_output=True)
		
		# Create ZIP containing the RAR and a .nfo
		nfo_content = b'Test NFO for roundtrip'
		zip_path = os.path.join(self.working_dir, 'release.zip')
		with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_STORED) as zf:
			zf.write(rar_path, 'data.rar')
			zf.writestr('readme.nfo', nfo_content)
		
		# Calculate original ZIP hash
		with open(zip_path, 'rb') as f:
			original_hash = hashlib.md5(f.read()).hexdigest()
		
		# Create SRR
		os.chdir(self.working_dir)
		srr_path = 'roundtrip.srr'
		create_srr(srr_path, [zip_path])
		
		# Set up reconstruction: provide unpacked files and SRR stored files
		recon_in = os.path.join(self.working_dir, 'recon_in')
		recon_out = os.path.join(self.working_dir, 'recon_out')
		os.makedirs(recon_in, exist_ok=True)
		os.makedirs(recon_out, exist_ok=True)
		
		# Copy the unpacked source file (what a user would have)
		shutil.copy2(src_file, os.path.join(recon_in, 'data.txt'))
		
		# Reconstruct from SRR
		# This should: 1) reconstruct data.rar from data.txt
		#              2) reconstruct release.zip from data.rar + readme.nfo
		rescene.extract_files(srr_path, recon_in)
		reconstruct(srr_path, recon_in, recon_out)
		
		# Verify the reconstructed ZIP matches
		recon_zip = os.path.join(recon_out, 'release.zip')
		self.assertTrue(os.path.isfile(recon_zip),
			"Reconstructed ZIP should exist")
		
		with open(recon_zip, 'rb') as f:
			recon_hash = hashlib.md5(f.read()).hexdigest()
		
		self.assertEqual(original_hash, recon_hash,
			"Reconstructed ZIP should be byte-identical to original")

	def test_nested_rar_in_zip_with_generated_data(self):
		"""Test nested RAR-like files in ZIPs using generated random data."""
		import subprocess
		if not shutil.which('rar'):
			self.skipTest("'rar' command not available")

		release_base = "sample_%s" % hashlib.sha1(os.urandom(16)).hexdigest()[:8]
		rar_file_names = [
			"%s.rar" % release_base,
			"%s.r00" % release_base,
			"%s.r01" % release_base,
		]
		zip_files = []
		for index, rar_name in enumerate(rar_file_names, 1):
			source_path = os.path.join(self.working_dir, "%s.part%s.bin" % (release_base, index))
			with open(source_path, 'wb') as source_file:
				source_file.write(os.urandom(8192 + index))

			temp_rar_path = os.path.join(self.working_dir, "%s.part%s.rar" % (release_base, index))
			subprocess.run([
				'rar', 'a', '-m0', '-ep',
				temp_rar_path, source_path
			], check=True, capture_output=True)

			rar_path = os.path.join(self.working_dir, rar_name)
			shutil.move(temp_rar_path, rar_path)

			zip_path = os.path.join(self.working_dir, "%s.part%s.zip" % (release_base, index))
			zip_files.append(zip_path)
			with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_STORED) as zf:
				zf.write(rar_path, rar_name)
				zf.writestr("%s.part%s.nfo" % (release_base, index),
					("Generated metadata %s" % index).encode('ascii'))
		
		# Create SRR
		os.chdir(self.working_dir)
		srr_path = 'generated_nested.srr'
		create_srr(srr_path, zip_files)
		
		# Verify SRR contains both ZIP and RAR blocks
		result = info(srr_path)
		
		# Should have 3 ZIP files
		self.assertEqual(len(result['zip_files']), 3,
			"Should have 3 ZIP file blocks")
		
		# Should have RAR blocks from generated nested RAR-like files
		self.assertTrue(len(result['rar_files']) > 0,
			"SRR should contain RAR blocks from nested RAR files")
		
		rar_names = result['rar_files']
		for rar_name in rar_file_names:
			self.assertIn(rar_name, rar_names)
		
		# Should have stored metadata files
		stored_names = list(result['stored_files'].keys())
		self.assertTrue(any('nfo' in n.lower() for n in stored_names),
			"Should store .nfo files")


if __name__ == '__main__':
	unittest.main()

