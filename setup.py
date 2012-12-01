from distutils.core import setup
# http://infinitemonkeycorps.net/docs/pph/
# http://as.ynchrono.us/2007/12/filesystem-structure-of-python-project_21.html

# http://packages.python.org/distribute/setuptools.html#specifying-your-project-s-version
# http://stackoverflow.com/questions/458550/standard-way-to-embed-version-into-python-package
# http://guide.python-distribute.org/creation.html#arranging-your-file-and-directory-structure

# http://google-styleguide.googlecode.com/svn/trunk/pyguide.html
# http://docs.python.org/library/pydoc.html

# http://docs.python.org/2/distutils/sourcedist.html
# build the package:
# $ python setup.py sdist

setup(
    name = "pyReScene",
    packages = ["rescene", "resample"],
    scripts  = ["bin/srr", "bin/srs", "bin/pyrescene.py"],
    version = "0.1",
    description = "Python ReScene and ReSample implementation",
    author = "Gfy", # ~umlaut@adsl-66-136-81-22.dsl.rcsntx.swbell.net (umlaut)
    author_email = "gfy@lavabit.com",
    url = "https://bitbucket.org/Gfy/pyrescene",
    download_url = "https://bitbucket.org/Gfy/pyrescene/downloads",
    license = "MIT",
    keywords = ["rescene", "srr", "resample", "srs", "repackage", "rar",
	            "avi", "mkv", "mp4", "wmv"],
    classifiers = [
		"Development Status :: 4 - Beta",
        "Programming Language :: Python :: 2.6",
        "Programming Language :: Python :: 2.7",
        "Environment :: Console",
        "Intended Audience :: Developers",
        "Intended Audience :: End Users/Desktop",
        "License :: OSI Approved :: MIT License",
        "Natural Language :: English",
        "Operating System :: OS Independent",
        "Topic :: System :: Archiving :: Backup",
        "Topic :: Utilities"
        ], # http://pypi.python.org/pypi?:action=list_classifiers
    long_description = """\
pyReScene is a port of ReScene .NET to the Python programming language.
ReScene is a mechanism for backing up and restoring the metadata from "scene" 
released RAR files. RAR archive volumes are rebuild using the stored metadata 
in the SRR file and the extracted files from the RAR archive. Thus far this
process only works on RAR files created with "Store" mode (otherwise known as 
-m0 or No Compression). pyReScene consists of multiple related tools. 
"""
)