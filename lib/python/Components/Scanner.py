from Plugins.Plugin import PluginDescriptor
from Components.PluginComponent import plugins

from os import path as os_path, walk as os_walk
from string import lower
from mimetypes import guess_type

def getExtension(file):
	p = file.rfind('.')
	if p == -1:
		ext = ""
	else:   
		ext = file[p+1:]

	return lower(ext)

def getType(file):
	(type, _) = guess_type(file)
	if type is None:
		# Detect some mimetypes unknown to dm7025
		# TODO: do mimetypes.add_type once should be better
		ext = getExtension(file)
		if ext == "ipk":
			return "application/x-debian-package"
		elif ext == "ogg":
			return "application/ogg"
	return type

class Scanner:
	def __init__(self, name, mimetypes= [], paths_to_scan = [], description = "", openfnc = None):
		self.mimetypes = mimetypes
		self.name = name
		self.paths_to_scan = paths_to_scan
		self.description = description
		self.openfnc = openfnc

	def checkFile(self, file):
		return True

	def handleFile(self, res, file):
		if (self.mimetypes is None or file.mimetype in self.mimetypes) and self.checkFile(file):
			res.setdefault(self, []).append(file)

	def __repr__(self):
		return "<Scanner " + self.name + ">"

	def open(self, list, *args, **kwargs):
		if self.openfnc is not None:
			self.openfnc(list, *args, **kwargs)

class ScanPath:
	def __init__(self, path, with_subdirs = False):
		self.path = path
		self.with_subdirs = with_subdirs

	def __repr__(self):
		return self.path + "(" + str(self.with_subdirs) + ")"

	# we will use this in a set(), so we need to implement __hash__ and __cmp__
	def __hash__(self):
		return self.path.__hash__() ^ self.with_subdirs.__hash__()

	def __cmp__(self, other):
		if self.path < other.path:
			return -1
		elif self.path > other.path:
			return +1
		else:
			return self.with_subdirs.__cmp__(other.with_subdirs)

class ScanFile:
	def __init__(self, path, mimetype = None, size = None, autodetect = True):
		self.path = path
		if mimetype is None and autodetect:
			(self.mimetype, _) = guess_type(path)
		else:
			self.mimetype = mimetype
		self.size = size

	def __repr__(self):
		return "<ScanFile " + self.path + " (" + str(self.mimetype) + ", " + str(self.size) + " MB)>"

def execute(option):
	print "execute", option
	if option is None:
		return

	(_, scanner, files, session) = option
	scanner.open(files, session)

def scanDevice(mountpoint):
	scanner = [ ]

	for p in plugins.getPlugins(PluginDescriptor.WHERE_FILESCAN):
		l = p()
		if not isinstance(l, list):
			l = [l]
		scanner += l

	print "scanner:", scanner

	res = { }

	# merge all to-be-scanned paths, with priority to 
	# with_subdirs.

	paths_to_scan = set()

	# first merge them all...
	for s in scanner:
		paths_to_scan.update(set(s.paths_to_scan))

	# ...then remove with_subdir=False when same path exists
	# with with_subdirs=True
	for p in set(paths_to_scan):
		if p.with_subdirs == True and ScanPath(path=p.path) in paths_to_scan:
			paths_to_scan.remove(ScanPath(path=p.path))

	# convert to list
	paths_to_scan = list(paths_to_scan)

	# now scan the paths
	for p in paths_to_scan:
		path = os_path.join(mountpoint, p.path)

		for root, dirs, files in os_walk(path):
			for f in files:
				sfile = ScanFile(os_path.join(root, f))
				for s in scanner:
					s.handleFile(res, sfile)

			# if we really don't want to scan subdirs, stop here.
			if not p.with_subdirs:
				del dirs[:]

	# res is a dict with scanner -> [ScanFiles]
	return res

def openList(session, files):
	if not isinstance(files, list):
		files = [ files ]

	scanner = [ ]

	for p in plugins.getPlugins(PluginDescriptor.WHERE_FILESCAN):
		l = p()
		if not isinstance(l, list):
			l = [l]
		scanner += l

	print "scanner:", scanner

	res = { }

	for file in files:
		for s in scanner:
			s.handleFile(res, file)

	choices = [ (r.description, r, res[r], session) for r in res ]
	Len = len(choices)
	if Len > 1:
		from Screens.ChoiceBox import ChoiceBox

		session.openWithCallback(
			execute,
			ChoiceBox,
			title = "The following viewers were found...",
			list = choices
		)
		return True
	elif Len:
		execute(choices[0])
		return True

	return False

def openFile(session, mimetype, file):
	return openList(session, [ScanFile(file, mimetype)])