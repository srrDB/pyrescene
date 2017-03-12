#!/usr/bin/env python
# encoding: utf-8

# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>

import os
import re
import sys
import shutil
import optparse
import requests
from bs4 import BeautifulSoup

def main(options, args):
	# http://screenshotcomparison.com/comparison/200409/picture:0
	url = args[0]
	if "screenshotcomparison.com" not in url:
		print("First parameter must be the url to scrape")
		return 2
	
	comp_id = grab_id(url)
	if not comp_id:
		return 1
	
	url = "http://screenshotcomparison.com/comparison/%s/" % comp_id
	response = requests.get(url + "picture:0")
	print("Scraping %s" % response.url)
	
	soup = BeautifulSoup(response.text, 'html.parser')

	count = get_comparisons_count(soup)
	pngs = get_pngs_from_page(soup)
	save_pngs(pngs, options.output_dir, 1)
	
	# more images after first page
	for i in range(2, count + 1):
		response = requests.get("%spicture:%d" % (url, i - 1)) # index one off
		print("Scraping %s" % response.url)
		soup = BeautifulSoup(response.text, 'html.parser')
		pngs = get_pngs_from_page(soup)
		save_pngs(pngs, options.output_dir, i)
		
	return 0
	
def save_pngs(pngs, output_path, page):
	url = "http://screenshotcomparison.com"
	for index, image in enumerate(pngs):
		print("Saving %s" % image)
		response = requests.get(url + image, stream=True)
		fname = "p%di%d_" % (page, index + 1) + os.path.basename(image)
		destination = os.path.join(output_path, fname)
		with open(destination, 'wb') as out_file:
			shutil.copyfileobj(response.raw, out_file)
		del response

def get_comparisons_count(soup):
	nav = soup.find(id='img_nav')
	links = nav.find_all('a')
	last_page = links[-1]
	return int(last_page.text[1:])
	
def get_pngs_from_page(soup):
	script = soup.head.find_all("script")[-1].text
	matches = re.findall("/images/\d+_\d+\.png", script)

	result = []
	for match in matches:
		if match not in result:
			result.append(match)
	return reversed(result)
	
def grab_id(url):
	match = re.match(".*\.com\/comparison\/(\d+)\/.*", url)
	if match:
		return match.group(1)
	return False

if __name__ == "__main__":
	parser = optparse.OptionParser(
		usage="Usage: %prog [url] -o [dir]'\n"
		"This tool will scrape images from screenshotcomparison.com.\n",
		version="%prog 1.0 (2017-03-12)")  # --help, --version

	parser.add_option("-o", help="output DIRECTORY\n",
				dest="output_dir", metavar="DIRECTORY", default=os.getcwd())

	# no arguments given
	if len(sys.argv) < 2:
		print(parser.format_help())
	else:
		(options, args) = parser.parse_args()
		sys.exit(main(options, args))