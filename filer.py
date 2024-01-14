from datetime import datetime, timezone
from zoneinfo import ZoneInfo
from collections import OrderedDict
from os import walk
import os.path
import shutil

from PIL import Image


TZ = ZoneInfo('Europe/Helsinki')


class Filer(object):
    def __init__(self):
        self._files = []
        self._groups = OrderedDict()
        self.to_directory = None

    def add_file(self, file):
        self._files.append(file)

        if file.fullroot in self._groups:
            group = self._groups[file.fullroot]
        else:
            group = FileGroup(self, file.root)
            self._groups[file.fullroot] = group

        group.add_file(file)

    @property
    def files(self):
        g = (f for f in self._groups.values() if f.capture_date)
        return sorted(g, key=lambda g: g.capture_date)

    @staticmethod
    def from_directory(directory):
        return load_directory(directory)

    def __str__(self):
        return f'<Filer with {len(self._files)} files>'

    def __repr__(self):
        return self.__str__()

class FileGroup():
    def __init__(self, filer, root):
        self.filer = filer
        self.files = []
        self.files_by_ext = {}
        self.exif = None
        self.root = root
        self.capture_date = None

    def add_file(self, file):
        self.files.append(file)
        self.files_by_ext[file.ext.lower()] = file
        if file.ext.lower() == '.jpg':
            # Expect only one file to be JPG
            assert not self.capture_date, f'Error: {self} already has capture_date set'
            file.load_exif()
            self.capture_date = file.capture_date

    def get_for_ext(self, ext):
        return self.files_by_ext[ext]

    def copy_files(self):
        for file in self.files:
            copy_to = os.path.join(self.filer.to_directory, file.filename)
            if os.path.isfile(copy_to):
                print(f'File {copy_to} already exists! Not copying...')
                continue
            print(f'copy from {file.fullpath} to {copy_to}')
            shutil.copy2(file.fullpath, copy_to)

    def __str__(self):
        return f'<FileGroup {self.root} with {len(self.files)} files, capture_date={self.capture_date}>'

    def __repr__(self):
        return self.__str__()


class FilerFile(object):
    def __init__(self, dirpath, filename):
        self.dirpath = dirpath
        self.filename = filename
        self.root, self.ext = os.path.splitext(filename)
        self.fullroot = os.path.join(self.dirpath, self.root)
        self.exif = None

    @property
    def fullpath(self):
        return os.path.join(self.dirpath, self.filename)

    def load_exif(self):
        self.exif = Image.open(self.fullpath)._getexif()
        self.capture_date = datetime.strptime(self.exif[36867], '%Y:%m:%d %H:%M:%S')
        self.capture_date = self.capture_date.replace(tzinfo=TZ)

    def __str__(self):
        return f'<FilerFile {self.filename}>'

    def __repr__(self):
        return self.__str__()


def load_directory(directory):
    filer = Filer()
    w = walk(directory)
    for (dirpath, dirnames, filenames) in w:
        for filename in filenames:
            filer.add_file(FilerFile(dirpath, filename))
    return filer


if __name__ == "__main__":
    filer = load_directory('/Users/raekkeri/Desktop/pics')
    print(filer)
    print(filer._groups)
