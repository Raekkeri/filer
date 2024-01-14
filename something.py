import traceback
import datetime
import sys
from PySide6 import QtCore, QtWidgets, QtGui
from filer import Filer
from collections import defaultdict
import queue


q = queue.Queue()

class WorkerThread(QtCore.QThread):
    task_done = QtCore.Signal(object)

    def run(self):
        while True:
            action, item = q.get(block=True)

            try:
                if action == 'prepare-pixmap':
                    item.setText(f'{item.text()} ...')
                    item._dto.pixmap

                elif action == 'items-cleanup':
                    items = (i for i in item if i._dto._pixmap_timestamp)
                    for _item in items:
                        if (datetime.datetime.utcnow() - _item._dto._pixmap_timestamp).total_seconds() > 120:
                            _item._dto.cleanup_pixmap()
                    q.task_done()
                    continue

                elif action == 'copy' and item._dto.file:
                    item._dto.file.copy_files()
                    item._dto.copied = True

                self.task_done.emit((action, item))
            except Exception as e:
                print(f'Exception in worker ({e}):\n{traceback.print_exc()}')

            q.task_done()


class ListItemDTO(object):
    def __init__(self, item, file):
        self.item = item
        self.file = file
        self._pixmap = None
        self._pixmap_timestamp = None
        self.copied = False
        self.discarded = False

    def get_label(self):
        return (
            f'{"x " if self.discarded else ""}'
            f'{self.file.root}'
            f'{" ->" if self.copied else ""}'
        )

    @property
    def pixmap(self):
        if not self._pixmap:
            reader = QtGui.QImageReader(self.file.get_for_ext('.jpg').fullpath)
            reader.setAutoTransform(True)
            image = reader.read()
            pixmap = QtGui.QPixmap.fromImage(image)
            pixmap = pixmap.scaled(1000, 800, QtCore.Qt.KeepAspectRatio)
            self._pixmap = pixmap

        self._pixmap_timestamp = datetime.datetime.utcnow()
        return self._pixmap

    def cleanup_pixmap(self):
        self._pixmap = None
        self._pixmap_timestamp = None


class GroupDTO(object):
    def __init__(self, item, date):
        self.item = item
        self.date = date
        self.pixmap = None
        self._pixmap_timestamp = None
        self.items = []
        self._discarded = False
        self.file = None

    @property
    def discarded(self):
        return self._discarded

    @discarded.setter
    def discarded(self, value):
        self._discarded = value
        for item in self.items:
            item.setHidden(self._discarded)

    def get_label(self):
        return f'--- {self.date.isoformat()}'

    def cleanup_pixmap(self):
        return


class MyListWidget(QtWidgets.QListWidget):
    def keyPressEvent(self, event):
        if event.key() == QtCore.Qt.Key_Space or event.key() == QtCore.Qt.Key_L:
            q.put(('copy', self.currentItem()))
        elif event.key() == QtCore.Qt.Key_X or event.key() == QtCore.Qt.Key_H:
            item = self.currentItem()
            item._dto.discarded = not item._dto.discarded
            item.setText(item._dto.get_label())
            return
        elif event.key() == QtCore.Qt.Key_J:
            g = self.item_iterator(1)
            if not event.modifiers() & QtCore.Qt.MetaModifier:
                g = (i for i in g if not i._dto.discarded)
            self.setCurrentItem(next(g))
            return
        elif event.key() == QtCore.Qt.Key_K:
            g = self.item_iterator(-1)
            if not event.modifiers() & QtCore.Qt.MetaModifier:
                g = (i for i in g if not i._dto.discarded)
            self.setCurrentItem(next(g))
            return
        return super().keyPressEvent(event)

    def item_iterator(self, step):
        start = current = self.currentRow()
        count = self.count()

        while 1:
            current = current + step
            if current >= count:
                current = 0
            elif current < 0:
                current = count - 1
            if current == start:
                return
            ret = self.item(current)
            if ret.isHidden():
                continue
            yield self.item(current)


class MyWidget(QtWidgets.QWidget):
    def __init__(self):
        super().__init__()

        self.workerThread = WorkerThread(self)
        self.workerThread.start()
        self.workerThread.task_done.connect(self.task_done_in_thread)

        self.cached_by_listitem = {}

        self.button_from = QtWidgets.QPushButton("From")
        self.button_to = QtWidgets.QPushButton("To")
        self.text = QtWidgets.QLabel("Hello World",
                                     alignment=QtCore.Qt.AlignCenter)

        self.grid = QtWidgets.QGridLayout(self)


        self._list = MyListWidget(self)
        self._list.currentItemChanged.connect(self.item_changed)
        self._list.setMinimumWidth(200)

        self.label = QtWidgets.QLabel(self)

        self.grid.addWidget(self._list, 0, 0, 29, 5)
        self.grid.addWidget(self.label, 0, 5, -1, 100)
        self.grid.addWidget(self.button_from, 29, 0, 1, 5)
        self.grid.addWidget(self.button_to, 30, 0, 1, 5)

        self.button_from.clicked.connect(self.select_from)
        self.button_to.clicked.connect(self.select_to)

        self.from_directory = '/Users/raekkeri/Desktop/20212107-pakkaskeli'
        self.load_files()

    def closeEvent(self, event):
        self.workerThread.terminate()

    def task_done_in_thread(self, obj):
        action, item = obj
        item.setText(item._dto.get_label())

    @property
    def items(self):
        return [self._list.item(x) for x in range(self._list.count())]

    def load_files(self):

        #self.items = []
        self._list.clear()
        self.filer = Filer.from_directory(self.from_directory)
        self.filer.to_directory = '/Users/raekkeri/Desktop/test_to' # XXX
        #for file in self.filer.files:
            #item = QtWidgets.QListWidgetItem(file.root, self._list)
            #item._dto = ListItemDTO(item, file)
            #self.items.append(item)

        #self.items = []

        self.groups = defaultdict(list)
        for obj in self.filer.files:
            self.groups[obj.capture_date.date()].append(obj)

        self.load_items()

    def load_items(self):
        for g, files in self.groups.items():
            dto = GroupDTO(None, g)
            item = QtWidgets.QListWidgetItem(dto.get_label(), self._list)
            item._dto = dto
            dto.item = item

            for file in files:
                item = QtWidgets.QListWidgetItem(file.root, self._list)
                item._dto = ListItemDTO(item, file)
                dto.items.append(item)


        #for i in li:
        self._list.setCurrentItem(self.items[1])

    def item_changed(self, current, previous):
        if current._dto.pixmap:
            self.label.setPixmap(current._dto.pixmap)
        idx = self.items.index(current)

        #for offset in [1, -1]:
        for offset in [1, -1, 2, -2, 3, -3]:
            try:
                q.put(('prepare-pixmap', self.items[idx + offset]))
            except IndexError:
                print('indexerror...')

        q.put(('items-cleanup', self.items))

    @QtCore.Slot()
    def select_from(self):
        name = QtWidgets.QFileDialog.getExistingDirectory(
            self, 'From directory', '/',
            QtWidgets.QFileDialog.ShowDirsOnly | QtWidgets.QFileDialog.DontResolveSymlinks)
        self.from_directory = name
        self.load_files()

    @QtCore.Slot()
    def select_to(self):
        name = QtWidgets.QFileDialog.getExistingDirectory(
            self, 'To directory', '/',
            QtWidgets.QFileDialog.ShowDirsOnly | QtWidgets.QFileDialog.DontResolveSymlinks)
        self.filer.to_directory = name


if __name__ == "__main__":
    app = QtWidgets.QApplication([])

    widget = MyWidget()
    widget.resize(1200, 900)
    widget.show()

    sys.exit(app.exec())
