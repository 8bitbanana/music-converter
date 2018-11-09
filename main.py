import sys, traceback, copy, json, os, random, string, isodate, webbrowser
import apicontrol, search, spotify, youtube
from PyQt5.QtCore import *
from PyQt5.QtWidgets import *
from PyQt5.QtWebEngineWidgets import *
from PyQt5.QtGui import *
from mutagen.mp3 import EasyMP3

PROGRAM_NAME = "Universal Music"
PROGRAM_AUTHOR = "Ethan Crooks"
TABLE_COLUMN_WIDTH = 150
TABLE_FIXED_HEIGHT = 500
ACCOUNTS_COMBOBOX_FIXED_WIDTH = 150
ACCOUNTS_TABLE_FIXED_WIDTH = 400
ACCOUNTS_TABLE_FIXED_HEIGHT = 250
SEARCH_TABLE_FIXED_WIDTH = 600
SEARCH_TABLE_FIXED_HEIGHT = 350
MAX_THREADS = 4
TABLEITEM_FLAGS_NOEDIT = Qt.ItemIsEnabled | Qt.ItemIsUserCheckable | Qt.ItemIsSelectable
TABLEITEM_FLAGS_EDIT = Qt.ItemIsEnabled | Qt.ItemIsEditable | Qt.ItemIsUserCheckable | Qt.ItemIsSelectable

playlist_file = "data/playlists.json"
spotify_username = None
youtube_username = None
spotify_scope = "playlist-read-private playlist-modify-public playlist-modify-private"
youtube_scope = "youtube"

# Prints out the exception, even if it is in a QThread. Debug
def except_hook(cls, exception, traceback):
    print(cls, exception, traceback)
    sys.__excepthook__(cls, exception, traceback)
    sys.exit(1)

# Converts a track object into a list for updateTable to display
def trackToRow(track):
    trackList = [
        track.title,
        track.artist,
        track.services['spotify']['id'],
        track.services['youtube']['id'],
        track.services['local']['id']
    ]
    return trackList

# Wipes the token cache
def wipe_cache():
    spotify.wipe_cache()
    youtube.wipe_cache()

# Defines signals for the threads to use to pass data
class WorkerSignals(QObject):
    finished = pyqtSignal()
    error = pyqtSignal(tuple)
    result = pyqtSignal(object)
    progress = pyqtSignal(int)

# Worker object. Runs the specified function with the specified arguments in the threadpool
class Worker(QRunnable):
    def __init__(self, fn, *args, **kwargs):
        print("Thread Started - "+str(fn))
        super(Worker, self).__init__()
        self.fn = fn
        self.args = args
        self.kwargs = kwargs
        self.signals = WorkerSignals()
        self.kwargs['progressCallback'] = self.signals.progress

    @pyqtSlot()
    def run(self):
        try:
            result = self.fn(*self.args, **self.kwargs)
        except:
            traceback.print_exc()
            exctype, value = sys.exc_info()[:2]
            self.signals.error.emit((exctype, value, traceback.format_exc()))
        else:
            self.signals.result.emit(result) # Return the result of the processing
        finally:
            self.signals.finished.emit() # Done

# Generates a busy QProgress bar
def generateBar(button):
    bar = QProgressBar()
    bar.setMinimum(0)
    bar.setMaximum(0)
    bar.setFormat(button.text())
    bar.setFixedSize(button.maximumSize())
    bar.setAlignment(Qt.AlignCenter)
    return bar

# Main Window
class MainWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.initDataFiles()
        self.settings = QSettings(PROGRAM_AUTHOR, PROGRAM_NAME)
        self.tracks = []
        self.undoStack = []
        self.lastAction = None
        self.redoStack = []
        self.spotifyUsername = self.settings.value("logins/spotify", None) # second arg specifies default value
        self.youtubeUsername = self.settings.value("logins/youtube", None) # if the key doesn't exist
        self.sAuth = None
        self.yAuth = None
        self.fetchLock = False
        self.updateAuths(self.spotifyUsername, self.youtubeUsername)
        self.threadpool = QThreadPool()
        self.threadpool.setMaxThreadCount(MAX_THREADS)
        self.initUI()
        print("Multithreading with maximum %d threads" % self.threadpool.maxThreadCount())

    # If playlists.json does not exist, create and initialise it
    def initDataFiles(self):
        head, tail = os.path.split(playlist_file)
        if head and not os.path.isdir(head): os.makedirs(head)
        if not os.path.isfile(playlist_file):
            with open(playlist_file, "w") as f:
                f.write("{}")

    # Main function for creating the UI
    def initUI(self):
        # Defining Widgets
        titleLabel = QLabel("<h1>Music Converter</h1>")

        importLabel = QLabel("Import")
        importLabel.setAlignment(Qt.AlignHCenter)
        importSpotifyButton = QPushButton("from Spotify")
        importYoutubeButton = QPushButton("from YouTube")
        importLocalButton = QPushButton("from Local")

        exportLabel = QLabel("Export")
        exportLabel.setAlignment(Qt.AlignHCenter)
        exportSpotifyButton = QPushButton("to Spotify")
        exportYoutubeButton = QPushButton("to Youtube")

        loginButton = QPushButton("Manage\nAccounts")

        loadButton = QPushButton("from Text")
        saveButton = QPushButton("to Text")
        managePlaylistsButton = QPushButton("Manage\nPlaylists")
        spotifyFetchButton = QPushButton("Fetch All\nSpotify")
        youtubeFetchButton = QPushButton("Fetch All\nYouTube")
        removeButton = QPushButton("Remove\nEverything")

        spotifyFetchBar = QProgressBar()
        spotifyFetchBar.setMinimum(0)
        spotifyFetchBar.setMaximum(100)
        spotifyFetchBar.setFormat(spotifyFetchButton.text())
        spotifyFetchBar.setFixedSize(spotifyFetchButton.maximumSize())
        spotifyFetchBar.setAlignment(Qt.AlignCenter)
        spotifyFetchBar.setTextVisible(True)

        youtubeFetchBar = QProgressBar()
        youtubeFetchBar.setMinimum(0)
        youtubeFetchBar.setMaximum(100)
        youtubeFetchBar.setFormat(youtubeFetchButton.text())
        youtubeFetchBar.setFixedSize(youtubeFetchButton.maximumSize())
        youtubeFetchBar.setAlignment(Qt.AlignCenter)
        youtubeFetchBar.setTextVisible(True)

        # Defining Widget Stacks
        importSpotifyStack = QStackedWidget()
        importSpotifyStack.addWidget(importSpotifyButton)
        importSpotifyStack.addWidget(generateBar(importSpotifyButton))
        importYoutubeStack = QStackedWidget()
        importYoutubeStack.addWidget(importYoutubeButton)
        importYoutubeStack.addWidget(generateBar(importYoutubeButton))

        spotifyFetchStack = QStackedWidget()
        spotifyFetchStack.addWidget(spotifyFetchButton)
        spotifyFetchStack.addWidget(spotifyFetchBar)
        youtubeFetchStack = QStackedWidget()
        youtubeFetchStack.addWidget(youtubeFetchButton)
        youtubeFetchStack.addWidget(youtubeFetchBar)

        exportSpotifyStack = QStackedWidget()
        exportSpotifyStack.addWidget(exportSpotifyButton)
        exportSpotifyStack.addWidget(generateBar(exportSpotifyButton))
        exportYoutubeStack = QStackedWidget()
        exportYoutubeStack.addWidget(exportYoutubeButton)
        exportYoutubeStack.addWidget(generateBar(exportYoutubeButton))

        importSpotifyStack.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        importYoutubeStack.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        importLocalButton.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        loadButton.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        exportSpotifyStack.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        exportYoutubeStack.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        saveButton.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)

        spotifyFetchStack.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        youtubeFetchStack.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)

        # Defining Table
        tableHeaders = ["Title", "Artist", "Spotify", "YouTube", "Local"]
        table = QTableWidget(0, 5)
        table.setHorizontalHeaderLabels(tableHeaders)
        #table.setSizeAdjustPolicy(QAbstractScrollArea.AdjustToContents)
        table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        table.setSelectionBehavior(QAbstractItemView.SelectRows)
        table.setSelectionMode(QAbstractItemView.MultiSelection)
        table.setMinimumHeight(TABLE_FIXED_HEIGHT)
        for col in range(table.columnCount()):
            table.setColumnWidth(col, TABLE_COLUMN_WIDTH)
        table.setMinimumWidth(TABLE_COLUMN_WIDTH * 5 + 50)
        table.setSizePolicy(QSizePolicy.Minimum, QSizePolicy.Minimum)
        table.customContextMenuRequested.connect(self.showTableContextMenu)
        table.setContextMenuPolicy(Qt.CustomContextMenu)

        # Defining Menu
        menuBar = QMenuBar(self)

        fileMenu = menuBar.addMenu("&File")
        quitAction = fileMenu.addAction("&Quit")

        editMenu = menuBar.addMenu("&Edit")
        undoAction = editMenu.addAction("&Undo")
        redoAction = editMenu.addAction("&Redo")
        tableReorderAction = editMenu.addAction("&Reorder Tracks")
        tableShuffleAction = editMenu.addAction("&Shuffle Tracks")

        addMenu = menuBar.addMenu("&Add")
        addSearchTrackAction = addMenu.addAction("&Search for an Item")
        addCustomTrackAction = addMenu.addAction("Add &Custom Track")

        accountsMenu = menuBar.addMenu("A&ccounts")
        manageAccountsAction = accountsMenu.addAction("Manage &Login")
        managePlaylistsAction = accountsMenu.addAction("Manage &Playlists")
        wipeLoginsAction = accountsMenu.addAction("&Wipe Accounts")

        #debugAction = menuBar.addAction("Debug")
        #debugAction.triggered.connect(lambda: importLocalButton.setFixedWidth(spotifyFetchStack.width()))
        #debugAction.setEnabled(False)

        self.menuBar = menuBar

        # Defining Layouts
        leftVBox = QVBoxLayout()
        leftVBox.addStretch(1)
        leftVBox.addWidget(importLabel)
        leftVBox.addWidget(importSpotifyStack)
        leftVBox.addWidget(importYoutubeStack)
        leftVBox.addWidget(importLocalButton)
        leftVBox.addWidget(loadButton)
        leftVBox.addStretch(1)

        rightVBox = QVBoxLayout()
        rightVBox.addStretch(1)
        rightVBox.addWidget(exportLabel)
        rightVBox.addWidget(exportSpotifyStack)
        rightVBox.addWidget(exportYoutubeStack)
        rightVBox.addWidget(saveButton)
        rightVBox.addStretch(1)

        titleHBox = QHBoxLayout()
        titleHBox.addStretch(1)
        titleHBox.addWidget(titleLabel)
        titleHBox.addStretch(1)

        upperHBox = QHBoxLayout()
        #upperHBox.addStretch(1)
        upperHBox.addLayout(leftVBox)
        upperHBox.addWidget(table)
        upperHBox.addLayout(rightVBox)
        #upperHBox.addStretch(1)

        lowerHBox = QHBoxLayout()
        lowerHBox.addStretch(1)
        lowerHBox.addWidget(loginButton)
        lowerHBox.addWidget(managePlaylistsButton)
        lowerHBox.addWidget(spotifyFetchStack)
        lowerHBox.addWidget(youtubeFetchStack)
        lowerHBox.addWidget(removeButton)
        lowerHBox.addStretch(1)

        mainVBox = QVBoxLayout()
        mainVBox.addLayout(titleHBox)
        mainVBox.addLayout(upperHBox)
        #mainVBox.addStretch(1)
        mainVBox.addLayout(lowerHBox)

        # Connecting signals and slots
        importSpotifyButton.clicked.connect(lambda: self.initImportThread("spotify", importSpotifyStack))
        importYoutubeButton.clicked.connect(lambda: self.initImportThread("youtube", importYoutubeStack))
        importLocalButton.clicked.connect(self.importLocal)
        spotifyFetchButton.clicked.connect(lambda: self.initUpdateThread("spotify", spotifyFetchStack, displayProgress=True))
        youtubeFetchButton.clicked.connect(lambda: self.initUpdateThread("youtube", youtubeFetchStack, displayProgress=True))
        removeButton.clicked.connect(self.removeSelected)
        table.cellClicked.connect(self.updateRemoveButton)
        table.currentCellChanged.connect(self.updateRemoveButton)
        loginButton.clicked.connect(self.openAccountsDialog)
        loadButton.clicked.connect(self.importJson)
        saveButton.clicked.connect(lambda: self.exportJson(self.tracks))
        managePlaylistsButton.clicked.connect(self.openManagePlaylistDialog)

        exportSpotifyButton.clicked.connect(lambda: self.initExportThread("spotify"))
        exportYoutubeButton.clicked.connect(lambda: self.initExportThread("youtube"))

        quitAction.triggered.connect(lambda: sys.exit(0))
        addCustomTrackAction.triggered.connect(self.openCustomTrackDialog)
        manageAccountsAction.triggered.connect(self.openAccountsDialog)
        wipeLoginsAction.triggered.connect(self.wipeAccounts)
        tableShuffleAction.triggered.connect(self.shuffleTable)
        tableReorderAction.triggered.connect(self.openReorderDialog)
        managePlaylistsAction.triggered.connect(self.openManagePlaylistDialog)
        addSearchTrackAction.triggered.connect(self.openTrackSearchDialog)
        undoAction.triggered.connect(self.undo)
        redoAction.triggered.connect(self.redo)

        # Defining Keyboard Shortcuts
        undoAction.setShortcuts(QKeySequence(Qt.CTRL + Qt.Key_Z))
        redoAction.setShortcuts(QKeySequence(Qt.CTRL + Qt.SHIFT + Qt.Key_Z))

        # Defining Global Objects
        self.removeButton = removeButton
        self.importSpotifyStack = importSpotifyStack
        self.importYoutubeStack = importYoutubeStack
        self.spotifyFetchStack = spotifyFetchStack
        self.youtubeFetchStack = youtubeFetchStack
        self.exportSpotifyStack = exportSpotifyStack
        self.exportYoutubeStack = exportYoutubeStack
        self.spotifyFetchBar = spotifyFetchBar
        self.youtubeFetchBar = youtubeFetchBar
        self.table = table

        self.importLocalButton = importLocalButton
        self.loadButton = loadButton
        self.saveButton = saveButton

        # Defining lists of objects for updateRequirementButtons
        self.requirements = {
            'spotifyAccount': [
                lambda: self.sAuth != None,
                [
                    importSpotifyStack,
                    spotifyFetchStack,
                    exportSpotifyStack
                ]
            ],
            'youtubeAccount': [
                lambda: self.yAuth != None,
                [
                    importYoutubeStack,
                    youtubeFetchStack,
                    exportYoutubeStack
                ]
            ],
            'anyAccount': [
                lambda: self.sAuth != None or self.yAuth != None,
                [
                    managePlaylistsButton,
                    managePlaylistsAction,
                    addSearchTrackAction
                ]
            ],
            'tracks': [
                lambda: not self.table.rowCount() == 0,
                [
                    removeButton,
                    exportSpotifyStack,
                    exportYoutubeStack,
                    saveButton,
                    spotifyFetchStack,
                    youtubeFetchStack,
                ]
            ],
            'multipleTracks': [
                lambda: self.table.rowCount() > 1,
                [
                    tableShuffleAction,
                    tableReorderAction
                ]
            ],
            'undo': [
                lambda: len(self.undoStack) > 0,
                [
                    undoAction
                ]
            ],
            'redo': [
                lambda: len(self.redoStack) > 0,
                [
                    redoAction
                ]
            ],
            'fetchLock': [
                lambda: not self.fetchLock,
                [
                    importSpotifyButton,
                    importYoutubeButton,
                    importLocalButton,
                    spotifyFetchButton,
                    youtubeFetchButton,
                    loadButton,
                    removeButton,

                    undoAction,
                    redoAction,
                    tableReorderAction,
                    tableShuffleAction,
                    addSearchTrackAction,
                    addCustomTrackAction,
                ]
            ],
            'threadLock': [
                lambda: self.threadpool.activeThreadCount() == 0,
                [
                    spotifyFetchButton,
                    youtubeFetchButton,
                    lambda state: self.toggleTableButtons(state)
                ]
            ]
        }

        self.updateRequirementButtons()
        self.setLayout(mainVBox)

    # Resizes some buttons whos whose width can only be accessed AFTER the widget has loaded. MenuWrapper calls this after self.show()
    def layoutCleanup(self):
        self.importLocalButton.setFixedWidth(self.importSpotifyStack.width())
        self.loadButton.setFixedWidth(self.importSpotifyStack.width())
        self.saveButton.setFixedWidth(self.exportSpotifyStack.width())

    # Updates sAuth and yAuth to tokens created using the specified usernames s and y
    def updateAuths(self, s, y, **kwargs):
        spotifyToken = None
        youtubeToken = None
        if self.spotifyUsername in [x['username'] for x in spotify.token(spotify_scope, request=True).auths]:
            spotifyToken = spotify.token(spotify_scope, s)
            self.settings.setValue("logins/spotify", s)
        else:
            self.settings.setValue("logins/spotify", None)
        if self.youtubeUsername in [x['username'] for x in youtube.token(youtube_scope, request=True).auths]:
            youtubeToken = youtube.token(youtube_scope, y)
            self.settings.setValue("logins/youtube", y)
        else:
            self.settings.setValue("logins/youtube", None)
        self.sAuth, self.yAuth = spotifyToken, youtubeToken

    # Thread wrapper for updateAuths
    def getAuthsThreadWrapper(self, *args, **kwargs):
        worker = Worker(self.updateAuths, *args, **kwargs)
        worker.signals.finished.connect(self.thread_complete)
        worker.signals.finished.connect(self.updateRequirementButtons)
        worker.signals.error.connect(self.showErrorMessage)
        self.threadpool.start(worker)
        self.updateRequirementButtons()

    # Wipes all accounts after a confirmation dialog box
    def wipeAccounts(self):
        messageBox = QMessageBox()
        messageBox.setWindowTitle(" ")
        messageBox.setText("Wiping all accounts")
        messageBox.setInformativeText("Are you sure?")
        messageBox.setStandardButtons(QMessageBox.Yes | QMessageBox.No)
        messageBox.setDefaultButton(QMessageBox.No)
        if messageBox.exec() == QMessageBox.Yes:
            print("Wiping Account Caches!")
            spotify.wipe_cache()
            youtube.wipe_cache()
            self.spotifyUsername = None
            self.youtubeUsername = None
            self.sAuth = None
            self.yAuth = None
        self.updateRequirementButtons()

    # Shows an error message popup.
    # error - The error object returned
    # customText - Custom text to display instead of the raw error description
    # customTitle - A custom title
    def showErrorMessage(self, error=None, customText=None, customTitle="An Error Occured"):
        if error != None:
            exctype = error[0]
            value = error[1]
            text = exctype.__name__ + " - " + str(value)
        elif customText != None:
            text = customText
        else:
            raise ValueError("Irony")
        message = QMessageBox()
        message.setWindowTitle("Error")
        message.setIcon(QMessageBox.Warning)
        message.setText(customTitle.ljust(30, " "))
        message.setInformativeText(text)
        message.setWindowModality(Qt.ApplicationModal)
        message.exec()

    # Uses self.requirements to work out which buttons need to be greyed out to prevent errors
    def updateRequirementButtons(self):
        allItems = []
        for x in self.requirements.values(): allItems += x[1]
        for item in allItems:
            state = True
            for key in self.requirements.keys():
                requirement = self.requirements[key]
                if item in requirement[1]:
                    if not requirement[0](): # Run the lambda function
                        state = False
            if callable(item): # Is the object a function? Call it.
                item(state)
            elif "__module__" in dir(item) and item.__module__ == "PyQt5.QtWidgets": # Is the object a QWidget? Enable/disable it.
                item.setEnabled(state)
            else: # Otherwise, warn that that object shouldn't be here.
                print("Invalid object for updateRequirementButtons - " + str(item))

    def toggleTableButtons(self, enabled):
        for row in range(self.table.rowCount()):
            for col in range(self.table.columnCount()):
                item = self.table.indexWidget(self.table.model().index(row, col))
                if type(item) == QStackedWidget:
                    item.widget(0).setEnabled(enabled)

    # Updates the remove button to selected or everything
    def updateRemoveButton(self):
        selected = len(self.table.selectedIndexes()) != 0
        if selected:
            self.removeButton.setText("Remove\nSelected")
        else:
            self.removeButton.setText("Remove\nEverything")

    # Removes selected rows, if any. If no rows are selected, wipe the table after a confirmation box.
    def removeSelected(self):
        selected = []
        oldTracks = copy.deepcopy(self.tracks)
        for model_index in self.table.selectionModel().selectedRows():
            index = QPersistentModelIndex(model_index)
            selected.append(index)
        if selected:
            self.undoStack.append(
                lambda self=self, oldTracks=oldTracks: self.updateTable(self.table, oldTracks, False))
            for index in selected:
                self.tracks.pop(index.row())
                self.table.removeRow(index.row())
            self.lastAction = lambda self=self, tracks=copy.deepcopy(self.tracks): self.updateTable(self.table, tracks, False)
        else:
            messageBox = QMessageBox()
            messageBox.setWindowTitle(" ")
            messageBox.setText("Removing all tracks")
            messageBox.setInformativeText("Are you sure?")
            messageBox.setStandardButtons(QMessageBox.Yes | QMessageBox.No)
            messageBox.setDefaultButton(QMessageBox.Yes)
            ret = messageBox.exec()
            if ret == QMessageBox.Yes:
                self.updateTable(self.table, [], False)
        self.updateRemoveButton()

    # Prints the thread. Debug
    def printThread(self, s):
        print(s)

    # For seeing when a thread is completed. Debug.
    def thread_complete(self):
        print("Thread complete")

    # Reads the playlist.json file into a dict. If convert is true, all tracks are converted to track objects.
    def readPlaylistsJson(self, convert=True):
        f = open(playlist_file)
        playlists = f.read()
        if len(playlists) == 0:
            return {}
        else:
            playlists = json.loads(playlists)
        f.close()
        if convert:
            for playlist in playlists.keys():
                for x, track in enumerate(playlists[playlist]):
                    playlists[playlist][x] = apicontrol.track_from_dict(track)
        return playlists

    # Updates playlists.json with the tracks specified. Runs ExportPlaylistDialog to get the playlist name
    def exportJson(self, tracks):
        tracks = copy.deepcopy(tracks)
        for x, track in enumerate(tracks):
            tracks[x] = track.to_dict()
        playlists = self.readPlaylistsJson(convert=False)
        dialog = ExportPlaylistDialog("json")
        if dialog.exec_():
            name = dialog.name
        else:
            return
        playlists[name] = tracks
        f = open(playlist_file, "w")
        f.write(json.dumps(playlists))
        f.close()

    # Reads the specified MP3 file, returning a track object
    def readLocalMP3(self, filename):
        mp3 = EasyMP3(filename)
        try:
            title = mp3.tags['title'][0]
        except KeyError: # no title, no track object
            return None
        try:
            artist = mp3.tags['artist'][0]
        except KeyError:
            artist = "" # we can live with no artist
        track = apicontrol.Track(title, artist)
        track.update_service("local", filename)
        track.update_duration("local", mp3.info.length)
        return track

    # Opens a QFileDialog to get a list of files, then imports the selected files into the central table
    def importLocal(self):
        dialog = QFileDialog()
        dialog.setAcceptMode(QFileDialog.AcceptOpen)
        dialog.setFileMode(QFileDialog.ExistingFiles)
        dialog.setViewMode(QFileDialog.Detail)
        dialog.setNameFilter("*.mp3")
        dialog.setDirectory(QStandardPaths.standardLocations(QStandardPaths.MusicLocation)[0])
        if dialog.exec_():
            files = dialog.selectedFiles()
            tracks = []
            for filename in files:
                track = self.readLocalMP3(filename)
                if track: tracks.append(track)
            self.appendTableThreadWrapper(tracks)

    # Imports the selected playlist from playlists.json to the central table
    def importJson(self):
        playlists = self.readPlaylistsJson()
        dialog = ImportPlaylistDialog(playlists)
        if dialog.exec_():
            selected_playlist = playlists[dialog.selected_playlist]
            self.appendTableThreadWrapper(selected_playlist)

    # Runs ExportPlaylistDialog to get the target playlist details, then runs a thread to export the tracks
    def initExportThread(self, service):
        dialog = ExportPlaylistDialog(service)
        if dialog.exec_():
            name = dialog.name
            desc = dialog.desc
            public = dialog.public
        else:
            return
        tracks = self.tracks
        if service == "spotify":
            self.exportSpotifyStack.setCurrentIndex(1)
            worker = Worker(self.exportSpotify, name, desc, tracks, public)
            worker.signals.finished.connect(self.thread_complete)
            worker.signals.finished.connect(lambda: self.exportSpotifyStack.setCurrentIndex(0))
            worker.signals.finished.connect(self.updateRequirementButtons)
            worker.signals.error.connect(self.showErrorMessage)
        elif service == "youtube":
            self.exportYoutubeStack.setCurrentIndex(1)
            worker = Worker(self.exportYoutube, name, desc, tracks, public)
            worker.signals.finished.connect(self.thread_complete)
            worker.signals.finished.connect(lambda: self.exportYoutubeStack.setCurrentIndex(0))
            worker.signals.finished.connect(self.updateRequirementButtons)
            worker.signals.error.connect(self.showErrorMessage)
        else:
            raise ValueError("Invalid service for initExportThread - "+service)
        self.threadpool.start(worker)
        self.updateRequirementButtons()

    # Exports a spotify playlist with the specified parameters
    def exportSpotify(self, name, desc, tracks, public, *args, **kwargs):
        playlist_id = apicontrol.spotify_write_playlist(self.sAuth, name, desc, tracks, public)
        return playlist_id

    # Exports a youtube playlist with the specified parameters
    def exportYoutube(self, name, desc, tracks, public, *args, **kwargs):
        playlist_id = apicontrol.youtube_write_playlist(self.yAuth, name, desc, tracks, public)
        return playlist_id

    # Thread wrapper for importing tracks
    def initImportThread(self, service, fetchStack, playlist_id=None, album=False):
        if service == "spotify":
            if playlist_id:
                worker = Worker(self.importSpotify, playlist_id, album)
                worker.signals.result.connect(lambda result: self.updateTable(self.table, result, append=True))
            else:
                worker = Worker(self.importSpotify)
                worker.signals.result.connect(lambda result: self.openPlaylistDialog(result, service))
            worker.signals.finished.connect(self.thread_complete)
            worker.signals.error.connect(self.showErrorMessage)
        elif service == "youtube":
            if playlist_id:
                worker = Worker(self.importYoutube, playlist_id)
                worker.signals.result.connect(lambda result: self.updateTable(self.table, result, append=True))
            else:
                worker = Worker(self.importYoutube)
                worker.signals.result.connect(lambda result: self.openPlaylistDialog(result, service))
            worker.signals.finished.connect(self.thread_complete)
            worker.signals.error.connect(self.showErrorMessage)
        else:
            raise ValueError("Invalid service for initImportThread")
        if playlist_id:
            fetchStack.setCurrentIndex(1)
            worker.signals.finished.connect(lambda: fetchStack.setCurrentIndex(0))
        else:
            self.fetchLock = True
            worker.signals.finished.connect(lambda: self.fetchLockWrapper(False))
        worker.signals.finished.connect(self.updateRequirementButtons)
        self.threadpool.start(worker)
        self.updateRequirementButtons()

    # Get all spotify playlists
    def importSpotify(self, playlist_id = None, album=False, *args, **kwargs):
        if playlist_id:
            playlist = apicontrol.spotify_read_playlist(self.sAuth, playlist_id, album)
            return playlist
        else:
            playlists = apicontrol.spotify_read_playlists(self.sAuth, ids=True)
            return playlists

    # Get all youtube playlists
    def importYoutube(self, playlist_id = None, *args, **kwargs):
        if playlist_id:
            playlist = apicontrol.youtube_read_playlist(self.yAuth, playlist_id)
            return playlist
        else:
            playlists = apicontrol.youtube_read_playlists(self.yAuth, ids=True)
            return playlists

    # Opens the playlist dialog to pick a playlist, then updates the table with the chosen playlist
    def openPlaylistDialog(self, playlists, service):
        dialog = ImportPlaylistDialog(playlists)
        if dialog.exec_():
            if service == "spotify":
                self.initImportThread(service, self.importSpotifyStack, playlists[dialog.selected_playlist])
            elif service == "youtube":
                self.initImportThread(service, self.importYoutubeStack, playlists[dialog.selected_playlist])
            else:
                raise ValueError("Invalid service for openPlaylistDialog")

    # Thread wrapper for updateTable, append=False
    def updateTableThreadWrapper(self, tracks):
        self.updateTable(self.table, tracks, False)

    # Thread wrapper for updateTable, append=True
    def appendTableThreadWrapper(self, tracks):
        self.updateTable(self.table, tracks, True)

    # Thread wrapper for updating a list of tracks
    # selected - Update only this list of rows. If None update all rows.
    # displayProgress - Update the progress bar with the progress of the update
    def initUpdateThread(self, service, fetchStack, selected=None, displayProgress=False):
        tracks = copy.deepcopy(self.tracks)
        if service == "spotify":
            if self.sAuth == None:
                self.showErrorMessage(customText="Logged out of Spotify")
                return
            worker = Worker(self.updateSpotify, tracks, selected=selected)
            worker.signals.finished.connect(self.thread_complete)
            worker.signals.finished.connect(lambda: self.fetchLockWrapper(False))
            worker.signals.finished.connect(self.updateRequirementButtons)
            worker.signals.result.connect(self.updateTableThreadWrapper)
            if displayProgress: worker.signals.progress.connect(self.spotifyFetchBar.setValue)
            worker.signals.error.connect(self.showErrorMessage)
        elif service == "youtube":
            if self.yAuth == None:
                self.showErrorMessage(customText="Logged out of YouTube")
                return
            worker = Worker(self.updateYoutube, tracks, selected=selected)
            worker.signals.finished.connect(self.thread_complete)
            worker.signals.finished.connect(lambda: self.fetchLockWrapper(False))
            worker.signals.finished.connect(self.updateRequirementButtons)
            worker.signals.result.connect(self.updateTableThreadWrapper)
            if displayProgress: worker.signals.progress.connect(self.youtubeFetchBar.setValue)
            worker.signals.error.connect(self.showErrorMessage)
        else:
            raise ValueError("Invalid service for initImportThread")
        fetchStack.setCurrentIndex(1)
        worker.signals.finished.connect(lambda: fetchStack.setCurrentIndex(0))
        self.fetchLock = True
        self.threadpool.start(worker)
        self.updateRequirementButtons()

    # You cannot assign in a lambda function, so this function circumvents that
    def fetchLockWrapper(self, lock):
        self.fetchLock = lock

    # Update a list of spotify tracks
    def updateSpotify(self, tracks, progressCallback, selected=None, *args, **kwargs):
        progressCallback.emit(0)
        for i, track in enumerate(tracks):
            if selected != None and not i in selected:
                continue
            if track.services['spotify']['id'] != None:
                continue
            try:
                new_track = search.youtube_to_spotify(track, self.sAuth)
            except Exception as e: # So the thread doesn't close when a single track errors
                traceback.print_exc()
                new_track = None
            if new_track == None:
                print(str(track) + " failed to update")
            else:
                print(str(track) + " updated")
                tracks[i] = new_track
            progressCallback.emit(round((i+1)/len(tracks)*100))
        return tracks

    # Update a list of youtube tracks
    def updateYoutube(self, tracks, progressCallback, selected=None, *args, **kwargs):
        progressCallback.emit(0)
        for i, track in enumerate(tracks):
            if selected != None and not i in selected:
                continue
            if track.services['youtube']['id'] != None:
                continue
            try:
                new_track = search.spotify_to_youtube(track, self.yAuth)
            except Exception as e: # So the thread doesn't close when a single track errors
                traceback.print_exc()
                new_track = None
            if new_track == None:
                print(str(track) + " failed to update")
            else:
                print(str(track) + " updated")
                tracks[i] = new_track
            progressCallback.emit(round((i + 1) / len(tracks) * 100))
        return tracks

    # Deprecated. Makes the whole table open or closed for editing.
    def setTableEdit(self, edit):
        for row in range(self.table.rowCount()):
            for col in range(self.table.columnCount()):
                if type(self.table.item(row, col)) == QTableWidgetItem:
                    if edit:
                        self.table.item(row, col).setFlags(TABLEITEM_FLAGS_EDIT)
                    else:
                        self.table.item(row, col).setFlags(TABLEITEM_FLAGS_NOEDIT)

    # Shuffles the table
    def shuffleTable(self):
        tracks = copy.deepcopy(self.tracks)
        random.shuffle(tracks)
        self.updateTable(self.table, tracks)

    # Undos the last action in the undoStack
    def undo(self):
        if self.undoStack:
            fn = self.undoStack.pop()
            self.redoStack.append(self.lastAction)
            undoStack = copy.deepcopy(self.undoStack)
            fn()
            self.undoStack = undoStack # To prevent the undoStack from being edited by the function we are undoing from
            self.updateRequirementButtons()

    # Redos the last action in the redoStack
    def redo(self):
        if self.redoStack:
            fn = self.redoStack.pop()
            fn()
            self.updateRequirementButtons()

    # Updates the specified table with the specified tracks.
    # If append is True, append the specified tracks to the existing tracks in the table.
    def updateTable(self, table, tracks, append=False):
        scrollPos = table.verticalScrollBar().value()
        oldTracks = copy.deepcopy(self.tracks)
        self.undoStack.append(lambda self=self, table=table, oldTracks=oldTracks: self.updateTable(table, oldTracks, append=False))
        self.lastAction = lambda self=self, table=table, tracks=copy.deepcopy(tracks), append=append: self.updateTable(table, tracks, append)
        if append:
            self.tracks += tracks
        else:
            self.tracks = copy.deepcopy(tracks)
        for i, track in enumerate(tracks):
            tracks[i] = trackToRow(track)
        if append:
            offset = table.rowCount()
        else:
            table.clearContents()
            offset = 0
        table.setRowCount(len(tracks)+offset)
        for x, track in enumerate(tracks):
            for y, cell in enumerate(track):
                if cell == None:
                    if y == 2 or y == 3:
                        fetchButton = QPushButton("Fetch")
                        fetchStack = QStackedWidget()
                        fetchStack.addWidget(fetchButton)
                        fetchStack.addWidget(generateBar(fetchButton))
                        if y == 2:
                            fetchButton.clicked.connect(lambda checked, x=x+offset, fetchStack=fetchStack, fetchButton=fetchButton: self.initUpdateThread("spotify", fetchStack, [x]))
                            #self.requirements['spotifyAccount'][1].append(fetchStack)
                        elif y == 3:
                            fetchButton.clicked.connect(lambda checked, x=x+offset, fetchStack=fetchStack, fetchButton=fetchButton: self.initUpdateThread("youtube", fetchStack, [x]))
                            #self.requirements['youtubeAccount'][1].append(fetchStack)
                        table.setIndexWidget(table.model().index(x+offset,y), fetchStack)
                    elif y == 4:
                        item = QTableWidgetItem("None")
                        item.setFlags(TABLEITEM_FLAGS_NOEDIT)
                        table.setItem(x + offset, y, item)
                else:
                    if y == 4: cell = os.path.split(cell)[1] # Only display the filename, not the full path
                    item = QTableWidgetItem(cell)
                    item.setFlags(TABLEITEM_FLAGS_NOEDIT)
                    table.setItem(x+offset, y, item)
        table.verticalScrollBar().setValue(scrollPos)
        self.updateRequirementButtons()

    def showTableContextMenu(self, pos):
        clipboard = QGuiApplication.clipboard()
        item = self.table.itemAt(pos)
        if not item: return
        contextMenu = QMenu()
        if not (item.column() == 4 and item.text() == "None"): # To stop copy from appearing for local "None" links
            copyAction = contextMenu.addAction("Copy")
            copyAction.triggered.connect(lambda: clipboard.setText(item.text()))
        if item.column() in (0, 1):
            editAction = contextMenu.addAction("Edit")
            editAction.triggered.connect(lambda clicked, item=item: self.editCell(item))
        if item.column() == 2:
            openAction = contextMenu.addAction("Open in browser")
            openAction.triggered.connect(lambda: webbrowser.open(self.tracks[item.row()].get_link("spotify")))
            if self.tracks[item.row()].services["spotify"]['id']:
                detatchAction = contextMenu.addAction("Detach link")
                detatchAction.triggered.connect(lambda clicked, item=item: self.detatchLink(item))
        if item.column() == 3:
            openAction = contextMenu.addAction("Open in browser")
            openAction.triggered.connect(lambda: webbrowser.open(self.tracks[item.row()].get_link("youtube")))
            if self.tracks[item.row()].services["youtube"]['id']:
                detatchAction = contextMenu.addAction("Detach Link")
                detatchAction.triggered.connect(lambda clicked, item=item: self.detatchLink(item))
        if item.column() == 4:
            if self.tracks[item.row()].services["local"]['id']:
                openAction = contextMenu.addAction("Play")
                filePath = "file:///" + self.tracks[item.row()].services['local']['id']
                openAction.triggered.connect(lambda: QDesktopServices.openUrl(QUrl(filePath)))
                openLocationAction = contextMenu.addAction("Open file location")
                folderPath = os.path.split(copy.copy(filePath))[0]
                openLocationAction.triggered.connect(lambda: QDesktopServices.openUrl(QUrl(folderPath)))
                detatchAction = contextMenu.addAction("Detach Link")
                detatchAction.triggered.connect(lambda clicked, item=item: self.detatchLink(item))
        contextMenu.exec(QCursor.pos())

    def detatchLink(self, item):
        if item.column() == 2:
            service = "spotify"
        elif item.column() == 3:
            service = "youtube"
        elif item.column() == 4:
            service = "local"
        else:
            raise ValueError("detatchLink item service invalid")
        tracks = copy.deepcopy(self.tracks)
        tracks[item.row()].update_service(service, None)
        tracks[item.row()].update_duration(service, None, force=True)
        self.updateTable(self.table, tracks, False)

    def editCell(self, item):
        dialog = QInputDialog()
        if item.column() == 0:
            valueType = "title"
        elif item.column() == 1:
            valueType = "artist"
        else:
            raise ValueError("Invalid item colum for editCell")
        newText, ok = dialog.getText(self, "Edit Value", "Enter a value for the track "+valueType, text=item.text())
        if ok and len(newText) > 0:
            self.undoStack.append(
                lambda tracks=copy.deepcopy(self.tracks): self.updateTable(self.table, tracks, append=False))
            item.setText(newText)
            if item.column() == 0:
                self.tracks[item.row()].title = newText
            elif item.column() == 1:
                self.tracks[item.row()].artist = newText
            self.lastAction = lambda tracks=copy.deepcopy(self.tracks): self.updateTable(self.table, tracks, append=False)

    # Opens CustomTrackDialog
    def openCustomTrackDialog(self):
        dialog = CustomTrackDialog()
        if dialog.exec_():
            track = dialog.track
            self.updateTable(self.table, [track], True)

    # Opens ReorderDialog
    def openReorderDialog(self):
        dialog = ReorderDialog(self.tracks)
        if dialog.exec_():
            tracks = dialog.tracks
            self.updateTable(self.table, tracks)

    # Opens AccountsDialog, passing the currently saved tokens from the spotify & youtube modules
    def openAccountsDialog(self):
        spotifyCachedTokens = spotify.token(spotify_scope, request=True).auths
        youtubeCachedTokens = youtube.token(youtube_scope, request=True).auths
        # Set to remove duplicates, any iterable would work with AccountsDialog
        spotifyAccounts = {x['username'] for x in spotifyCachedTokens}
        youtubeAccounts = {x['username'] for x in youtubeCachedTokens}
        dialog = AccountsDialog(spotifyAccounts, youtubeAccounts, self.spotifyUsername, self.youtubeUsername)
        if dialog.exec_():
            self.spotifyUsername = dialog.spotifyCurrent
            self.youtubeUsername = dialog.youtubeCurrent
            #self.sAuth, self.yAuth = self.getAuths(self.spotifyUsername, self.youtubeUsername)
            self.getAuthsThreadWrapper(self.spotifyUsername, self.youtubeUsername)
            print("Accounts updated to " + str(self.spotifyUsername) + " and " + str(self.youtubeUsername))
        self.updateRequirementButtons()

    # Opens ManagePlaylistDialog, passing the users spotify & youtube playlists
    def openManagePlaylistDialog(self):
        spotifyPlaylists = None
        youtubePlaylists = None
        if self.sAuth: spotifyPlaylists = apicontrol.spotify_read_playlists(self.sAuth, ids=True)
        if self.yAuth: youtubePlaylists = apicontrol.youtube_read_playlists(self.yAuth, ids=True)
        dialog = ManagePlaylistDialog(spotifyPlaylists, youtubePlaylists, self.sAuth, self.yAuth)
        if dialog.exec_():
            pass

    # Opens the TrackSearchDialog
    def openTrackSearchDialog(self):
        dialog = TrackSearchDialog(self.sAuth, self.yAuth, self.threadpool)
        if dialog.exec_():
            result = dialog.result
            if type(result) == apicontrol.Track:
                self.updateTable(self.table, [result], append=True)
            elif type(result) == dict:
                if result['service'] == "spotify": # todo - loading bar instead of importSpotifyStack
                    self.initImportThread(result['service'], self.importSpotifyStack, result['id'], result['album'])
                elif result['service'] == "youtube":
                    self.initImportThread(result['service'], self.importYoutubeStack, result['id'], result['album'])
                else:
                    raise ValueError("Invalid service for TrackSearchDialog return")

# Dialog to search for tracks by name
class TrackSearchDialog(QDialog):
    def __init__(self, sAuth, yAuth, threadpool):
        super().__init__()
        self.track = None
        self.sAuth = sAuth
        self.yAuth = yAuth
        self.threadpool = threadpool
        self.initUI()

    # Main function for creating the UI
    def initUI(self):
        self.searchTypes = {
            "track":{
                "name":"Tracks",
                "spotify":"track",
                "youtube":"video",
                "result":"single"
            },
            "playlist":{
                "name":"Playlists",
                "spotify":"playlist",
                "youtube":"playlist",
                "result":"multiple"
            },
            "album":{
                "name":"Albums",
                "spotify":"album",
                "youtube":None,
                "result":"multiple"
            }
        }
        self.currentSearchType = "track"
        searchBar = QLineEdit()
        searchBar.setMinimumWidth(SEARCH_TABLE_FIXED_WIDTH)
        searchButton = QPushButton("Search")
        spotifyLabel = QLabel("Spotify")
        youtubeLabel = QLabel("YouTube")
        doneButton = QPushButton("Done")
        cancelButton = QPushButton("Cancel")

        self.tableHeaders = ["Title", "Artist", "Duration", ""]
        spotifyTable = QTableWidget(0,4)
        spotifyTable.setFixedWidth(SEARCH_TABLE_FIXED_WIDTH)
        spotifyTable.setMinimumHeight(SEARCH_TABLE_FIXED_HEIGHT)
        #spotifyTable.setSizeAdjustPolicy(QAbstractScrollArea.AdjustToContents)
        spotifyTable.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        spotifyTable.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        spotifyTable.setHorizontalHeaderLabels(self.tableHeaders)
        spotifyTable.setSelectionMode(QAbstractItemView.NoSelection)
        spotifyTable.verticalHeader().hide()
        youtubeTable = QTableWidget(0,4)
        youtubeTable.horizontalHeader()
        youtubeTable.setFixedWidth(SEARCH_TABLE_FIXED_WIDTH)
        youtubeTable.setMinimumHeight(SEARCH_TABLE_FIXED_HEIGHT)
        #youtubeTable.setSizeAdjustPolicy(QAbstractScrollArea.AdjustToContents)
        youtubeTable.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        youtubeTable.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        youtubeTable.setHorizontalHeaderLabels(self.tableHeaders)
        youtubeTable.setSelectionMode(QAbstractItemView.NoSelection)
        youtubeTable.verticalHeader().hide()

        if not self.sAuth: self.tableSetEnabled(spotifyTable, False, "Logged Out")
        if not self.yAuth: self.tableSetEnabled(youtubeTable, False, "Logged Out")

        searchComboBox = QComboBox()
        for i, t in enumerate(self.searchTypes):
            searchComboBox.insertItem(i, self.searchTypes[t]['name'])

        searchHBox = QHBoxLayout()
        searchHBox.addStretch(1)
        searchHBox.addWidget(searchBar)
        searchHBox.addWidget(searchButton)
        searchHBox.addWidget(searchComboBox)
        searchHBox.addStretch(1)

        tableGrid = QGridLayout()
        tableGrid.addWidget(spotifyLabel, 0,0)
        tableGrid.addWidget(spotifyTable, 1,0)
        tableGrid.addWidget(youtubeLabel, 0,1)
        tableGrid.addWidget(youtubeTable, 1,1)

        buttonHBox = QHBoxLayout()
        buttonHBox.addWidget(doneButton)
        buttonHBox.addWidget(cancelButton)

        mainVBox = QVBoxLayout()
        mainVBox.addLayout(searchHBox)
        mainVBox.addLayout(tableGrid)
        mainVBox.addLayout(buttonHBox)

        searchButton.clicked.connect(self.searchAll)
        doneButton.clicked.connect(self.reject)
        cancelButton.clicked.connect(self.reject)
        searchComboBox.currentTextChanged.connect(self.updateSearchType)
        #searchBar.returnPressed.connect(self.searchAll)

        self.searchBar = searchBar
        self.spotifyTable = spotifyTable
        self.youtubeTable = youtubeTable

        self.setLayout(mainVBox)
        self.setWindowModality(Qt.ApplicationModal)
        self.setWindowTitle("Search for an Item")
        self.show()
        searchComboBox.setFixedHeight(searchBar.height()+1) # +1 to align it properly

    def updateSearchType(self, text):
        for i in self.searchTypes:
            if self.searchTypes[i]['name'] == text:
                self.currentSearchType = i
                if self.searchTypes[i]['spotify'] == None:
                    self.tableSetEnabled(self.spotifyTable, False, message="n/a")
                else:
                    self.tableSetEnabled(self.spotifyTable, True)
                if self.searchTypes[i]['youtube'] == None:
                    self.tableSetEnabled(self.youtubeTable, False, message="n/a")
                else:
                    self.tableSetEnabled(self.youtubeTable, True)

    # Sets enables/disables the specified table. Add a custom message with message
    def tableSetEnabled(self, table, enabled, message="No Results"):
        if enabled:
            if not table.isEnabled():
                table.clear()
                table.setRowCount(0)
            table.horizontalHeader().show()
            table.setHorizontalHeaderLabels(self.tableHeaders)
        else:
            table.horizontalHeader().hide()
            table.setRowCount(1)
            table.clear()
            item = QTableWidgetItem(message)
            table.setItem(0, 0, item)
        table.setEnabled(enabled)
        table.setShowGrid(enabled)

    # Thread wrapper for doSearch. Disables respecive tables until the search is done
    def searchAll(self):
        searchType = self.currentSearchType
        print("searchAll")
        if self.sAuth:
            self.tableSetEnabled(self.spotifyTable, False, "Searching...")
            worker = Worker(self.doSearch, "spotify", searchType)
            worker.signals.result.connect(lambda results: self.updateTable("spotify", results, searchType))
            worker.signals.error.connect(lambda error: self.tableSetEnabled(self.spotifyTable, False, message="Error")) # todo - more descriptive
            self.threadpool.start(worker)
        if self.yAuth:
            self.tableSetEnabled(self.youtubeTable, False, "Searching...")
            worker = Worker(self.doSearch, "youtube", searchType)
            worker.signals.result.connect(lambda results: self.updateTable("youtube", results, searchType))
            worker.signals.error.connect(lambda error: self.tableSetEnabled(self.youtubeTable, False, message="Error"))
            self.threadpool.start(worker)

    # Formats a duration in seconds into a string for updateTable to display
    def formatTime(self, seconds):
        m, s = divmod(seconds, 60)
        h, m = divmod(m, 60)
        if h>99: return "Too Long"
        if h > 0:
            return "%d:%02d:%02d" % (h, m, s)
        else:
            return "%d:%02d" % (m, s)

    # Updates the specified service's table with results, adding Add buttons
    # Takes a track object, or
    #{
    #    'name':...,
    #    'owner':...,
    #    'items':[...]
    #}
    def updateTable(self, service, results, searchType):
        if service == "spotify":
            table = self.spotifyTable
            #results = self.spotifyResults
        elif service == "youtube":
            table = self.youtubeTable
            #results = self.youtubeResults
        else:
            raise ValueError("Invalid service for updateTable")
        resultType = self.searchTypes[searchType]['result']
        if resultType == "single":
            self.tableHeaders = ["Title", "Artist", "Duration", ""]
        elif resultType == "multiple":
            self.tableHeaders = ['Name', "Owner", "Length", ""]
        if results:
            self.tableSetEnabled(table, True)
            table.setRowCount(len(results))
            for i, result in enumerate(results):
                if resultType == "single":
                    titleItem = QTableWidgetItem(result.title)
                    artistItem = QTableWidgetItem(result.artist)
                    durationItem = QTableWidgetItem(self.formatTime(result.get_duration()))
                    titleItem.setFlags(TABLEITEM_FLAGS_NOEDIT)
                    artistItem.setFlags(TABLEITEM_FLAGS_NOEDIT)
                    durationItem.setFlags(TABLEITEM_FLAGS_NOEDIT)
                    table.setItem(i, 0, titleItem)
                    table.setItem(i, 1, artistItem)
                    table.setItem(i, 2, durationItem)
                elif resultType == "multiple":
                    nameItem = QTableWidgetItem(result['name'])
                    ownerItem = QTableWidgetItem(result['owner'])
                    lengthItem = QTableWidgetItem(str(result['length']))
                    nameItem.setFlags(TABLEITEM_FLAGS_NOEDIT)
                    lengthItem.setFlags(TABLEITEM_FLAGS_NOEDIT)
                    table.setItem(i, 0, nameItem)
                    table.setItem(i, 1, ownerItem)
                    table.setItem(i, 2, lengthItem)
                addButton = QPushButton("Add")
                table.setIndexWidget(table.model().index(i, 3), addButton)
                if resultType == "single":
                    addButton.clicked.connect(lambda clicked, result=result: self.closeDialog(result))
                if resultType == "multiple":
                    addButton.clicked.connect(lambda clicked, result=result: self.closeDialog(result))
        else:
            self.tableSetEnabled(table, False, "No Results")

    # Checks for possibly valid ids in the search, returning a dictionary with tracks, playlists and albums
    def matchId(self, service, text, searchType):
        requirements = {
            "spotify": {
                "length":{
                    "track":22,
                    "album":22,
                    "playlist":22
                },
                "chars": string.ascii_letters + string.digits
            },
            "youtube": {
                "length":{
                    "track":11,
                    "playlist":34,
                    "album":-1
                },
                "chars": string.ascii_letters + string.digits + "_-"
            }
        }
        if not service in requirements:
            raise ValueError("Invalid service for id_matching")
        substrings = []
        current_substring = ""
        for x in text:
            if x in requirements[service]['chars']:
                current_substring += x
            else:
                if current_substring:
                    substrings.append(current_substring)
                    current_substring = ""
        if current_substring:
            substrings.append(current_substring)
        return {
            "tracks": [x for x in substrings if len(x) == requirements[service]['length']['track'] and searchType == "track"],
            "playlists": [x for x in substrings if len(x) == requirements[service]['length']['playlist'] and searchType == "playlist"],
            "albums": [x for x in substrings if len(x) == requirements[service]['length']['album'] and searchType == "album"]
        }

    # Searches. Gets possible results for matchId and the search module
    def doSearch(self, service, searchType, **kwargs):
        if self.searchTypes[searchType][service] == None:
            return []
        resultType = self.searchTypes[searchType]['result']
        query = self.searchBar.text()
        if query == "": return []
        results = []
        matched_ids = self.matchId(service, query, searchType) # matchId automatically takes searchType into account
        if service == "spotify":
            for matched_id in matched_ids['tracks']:
                data = apicontrol.spotify_get_item(self.sAuth, matched_id, "track")
                if data:
                    track = apicontrol.Track(
                        data['name'],
                        data['artists'][0]['name'],
                        data['album']['name']
                    )  # music returned via track_id cannot be local
                    track.update_service("spotify", matched_id)
                    track.update_duration("spotify", int(data['duration_ms']) / 1000)
                    results.append(track)
            for matched_id in matched_ids['playlists']:
                data = apicontrol.spotify_get_playlist_info(self.sAuth, matched_id)
                newItem = {
                    'name': data['name'],
                    'owner': data['owner']['display_name'],
                    'items': apicontrol.spotify_read_playlist(self.sAuth, data['id'])
                }
                results.append(newItem)
            for matched_id in matched_ids['albums']:
                data = apicontrol.spotify_get_playlist_info(self.sAuth, matched_id, album=True)
                newItem = {
                    'name': data['name'],
                    'owner': data['artists'][0]['name'],
                    'items': apicontrol.spotify_read_playlist(self.sAuth, data['id'], album=True)
                }
                results.append(newItem)
            search_results = search.spotify_search(query, self.searchTypes[searchType][service], self.sAuth, amount=10)
            if search_results == None: search_results = []
            for result in search_results:
                if resultType == "single":
                    track = apicontrol.Track(
                        result['name'],
                        result['artists'][0]['name'],
                        result['album']['name']
                    ) # track searched by id cannot be local
                    track.update_service("spotify", result['id'])
                    track.update_duration("spotify", result['duration_ms'] / 1000)
                    results.append(track)
                elif resultType == "multiple":
                    if searchType == "playlist":
                        newItem = {
                            'name': result['name'],
                            'owner': result['owner']['display_name'],
                            'length': result['tracks']['total'],
                            'album':False,
                            'id': result['id'],
                            'service': 'spotify'
                        }
                    elif searchType == "album":
                        newItem = {
                            'name': result['name'],
                            'owner': result['artists'][0]['name'],
                            'length': result['tracks']['total'],
                            'album': True,
                            'id': result['id'],

                        }
                    else:
                        raise ValueError("Invalid searchType for spotify doSearch")
                    results.append(newItem)
        elif service == "youtube":
            for matched_id in matched_ids['tracks']:
                data = apicontrol.youtube_get_item(self.yAuth, matched_id, "video")
                if data:
                    track = apicontrol.Track(
                        data['snippet']['title'],
                        data['snippet']['channelTitle'],
                        None
                    )
                    track.update_service("youtube", data['id'])
                    track.update_duration("youtube", isodate.parse_duration(data['contentDetails']['duration']).total_seconds())
                    results.append(track)
            for matched_id in matched_ids['playlists']:
                data = apicontrol.youtube_get_playlist_info(self.yAuth, matched_id)
                newItem = {
                    'name': data['snippet']['title'],
                    'owner': data['snippet']['channelTitle'],
                    'items': apicontrol.youtube_read_playlist(self.yAuth, data['id'])
                }
                results.append(newItem)
            search_results = search.youtube_search(query, self.searchTypes[searchType][service], self.yAuth, amount=10)
            for result in search_results:
                if resultType == "single":
                    data = apicontrol.youtube_get_item(self.yAuth, result['id']['videoId'], "video")
                    if data['snippet']['liveBroadcastContent'] != 'none': continue # Filter out livestreams
                    track = apicontrol.Track(
                        data['snippet']['title'],
                        data['snippet']['channelTitle'],
                        None
                    )
                    track.update_service("youtube", data['id'])
                    track.update_duration("youtube", isodate.parse_duration(data['contentDetails']['duration']).total_seconds())
                    results.append(track)
                elif resultType == "multiple":
                    if searchType == "playlist":
                        playlist_data = apicontrol.youtube_get_playlist_info(self.yAuth, result['id']['playlistId'])
                        newItem = {
                            'name': playlist_data['snippet']['title'],
                            'owner': playlist_data['snippet']['channelTitle'],
                            'length': playlist_data['contentDetails']['itemCount'],
                            'id': result['id']['playlistId'],
                            'album': False,
                            'service':service,
                        }
                    else:
                        raise ValueError("Invalid searchType for youtube doSearch")
                    results.append(newItem)
        else:
            raise ValueError("Invalid service for search")
        return results

    # Closes the dialog, returning the requested track
    def closeDialog(self, result):
        self.result = result
        self.accept()

# Dialog to reorder the tracks loaded in the central table
class ReorderDialog(QDialog):
    def __init__(self, tracks):
        super().__init__()
        self.tracks = tracks
        self.initUI()

    # Main function for creating the UI
    def initUI(self):
        doneButton = QPushButton("Done")
        doneButton.setDefault(True)
        cancelButton = QPushButton("Cancel")

        infoLabel = QLabel("Drag to Reorder")

        mainList = QListWidget()
        mainList.setDragDropMode(QAbstractItemView.InternalMove)
        mainList.setDefaultDropAction(Qt.MoveAction)
        mainList.setSelectionMode(QAbstractItemView.SingleSelection)

        for track in self.tracks:
            item = QListWidgetItem(track.title)
            item.track = track
            mainList.addItem(item)

        buttonHBox = QHBoxLayout()
        buttonHBox.addWidget(doneButton)
        buttonHBox.addWidget(cancelButton)

        mainVBox = QVBoxLayout()
        mainVBox.addWidget(infoLabel)
        mainVBox.addWidget(mainList)
        mainVBox.addLayout(buttonHBox)

        doneButton.clicked.connect(self.closeDialog)
        cancelButton.clicked.connect(self.reject)

        self.mainList = mainList

        self.setLayout(mainVBox)
        self.setWindowModality(Qt.ApplicationModal)
        self.setWindowTitle("Reorder Tracks")
        self.show()

    # Closes the dialog, returning the reordered tracks
    def closeDialog(self):
        tracks = [self.mainList.item(i).track for i in range(self.mainList.count())]
        self.tracks = tracks
        self.accept()

# Dialog to add a custom track, specifying title and artist manually
class CustomTrackDialog(QDialog):
    def __init__(self):
        super().__init__()
        self.title = None
        self.artist = None
        self.artist = None
        self.initUI()

    # Main function for creating the UI
    def initUI(self):
        doneButton = QPushButton("Done")
        doneButton.setEnabled(False)
        doneButton.setDefault(True)
        cancelButton = QPushButton("Cancel")

        buttonHBox = QHBoxLayout()
        buttonHBox.addWidget(doneButton)
        buttonHBox.addWidget(cancelButton)

        titleLabel = QLabel("Title:")
        titleLabel.setAlignment(Qt.AlignRight)
        artistLabel = QLabel("Artist:")
        artistLabel.setAlignment(Qt.AlignRight)
        titleEdit = QLineEdit()
        artistEdit = QLineEdit()

        centerGridLayout = QGridLayout()
        centerGridLayout.addWidget(titleLabel, 0,0)
        centerGridLayout.addWidget(titleEdit, 0,1)
        centerGridLayout.addWidget(artistLabel, 1,0)
        centerGridLayout.addWidget(artistEdit, 1,1)

        mainVBox = QVBoxLayout()
        mainVBox.addLayout(centerGridLayout)
        mainVBox.addLayout(buttonHBox)

        titleEdit.textChanged.connect(self.updateDoneButton)
        artistEdit.textChanged.connect(self.updateDoneButton)
        doneButton.clicked.connect(self.closeDialog)
        cancelButton.clicked.connect(self.reject)

        self.titleEdit = titleEdit
        self.artistEdit = artistEdit
        self.doneButton = doneButton

        self.setLayout(mainVBox)
        self.setWindowModality(Qt.ApplicationModal)
        self.setWindowTitle("Enter Custom Track")
        self.show()

    # Enables the done button if the title and artist bars are populated
    def updateDoneButton(self):
        self.doneButton.setEnabled(len(self.titleEdit.text()) != 0 and len(self.artistEdit.text()) != 0)

    # Closes the dialog, returning a track object
    def closeDialog(self):
        self.title = self.titleEdit.text()
        self.artist = self.artistEdit.text()
        self.track = apicontrol.Track(self.title, self.artist)
        self.accept()

# Dialog for exporting a set of tracks
# When updating a playlist rather than exporting, pass a dictionary into current
# with name, desc, and public values so the fields are pre-filled
class ExportPlaylistDialog(QDialog):
    def __init__(self, service, current=None):
        super().__init__()
        self.descRequired = True
        self.publicRequired = True
        if service == "spotify":
            service = "Spotify"
        if service == "youtube":
            service = "YouTube"
        if service == "json":
            service = "JSON"
            self.descRequired = False
            self.publicRequired = False
        self.service = service
        if current:
            self.name = current['name']
            self.desc = current['desc']
            self.public = current['public']
            self.prefill = True
        else:
            self.name = "Exported Playlist"
            self.desc = ""
            self.public = False
            self.prefill = False
        self.initUI()

    # Main function for creating the UI
    def initUI(self):
        if self.prefill:
            titleLabel = QLabel("<h1>Update {} Playlist</h1>".format(self.service))
            doneButton = QPushButton("Update")
            self.setWindowTitle("Update Playlist")
        else:
            titleLabel = QLabel("<h1>Export to {}</h1>".format(self.service))
            doneButton = QPushButton("Export")
            self.setWindowTitle("Export Playlist")
        titleLabel.setAlignment(Qt.AlignHCenter)
        doneButton.setDefault(True)
        doneButton.setEnabled(False)
        cancelButton = QPushButton("Cancel")

        buttonHBox = QHBoxLayout()
        buttonHBox.addWidget(doneButton)
        buttonHBox.addWidget(cancelButton)

        nameLabel = QLabel("Name:")
        nameLabel.setAlignment(Qt.AlignRight)
        descLabel = QLabel("Description:")
        descLabel.setAlignment(Qt.AlignRight)
        nameEdit = QLineEdit()
        descEdit = QTextEdit()
        descEdit.setMaximumHeight(descEdit.height()/6)
        publicLabel = QLabel("Public:")
        publicLabel.setAlignment(Qt.AlignRight)
        publicCheckBox = QCheckBox()

        if self.prefill:
            nameEdit.setText(self.name)
            descEdit.setText(self.desc)
            publicCheckBox.setChecked(self.public)

        centerGridLayout = QGridLayout()
        centerGridLayout.addWidget(nameLabel, 0,0)
        centerGridLayout.addWidget(nameEdit, 0,1)
        if self.descRequired:
            centerGridLayout.addWidget(descLabel, 1,0)
            centerGridLayout.addWidget(descEdit, 1,1)
        if self.publicRequired:
            centerGridLayout.addWidget(publicLabel, 2,0)
            centerGridLayout.addWidget(publicCheckBox, 2,1)

        mainVBox = QVBoxLayout()
        mainVBox.addStretch(1)
        mainVBox.addWidget(titleLabel)
        mainVBox.addLayout(centerGridLayout)
        mainVBox.addLayout(buttonHBox)
        mainVBox.addStretch(1)

        nameEdit.textChanged.connect(self.updateDoneButton)
        doneButton.clicked.connect(self.closeDialog)
        cancelButton.clicked.connect(self.reject)

        self.nameEdit = nameEdit
        self.descEdit = descEdit
        self.publicCheckBox = publicCheckBox
        self.doneButton = doneButton

        self.updateDoneButton()
        self.setLayout(mainVBox)
        self.setWindowModality(Qt.ApplicationModal)
        # window title set in above if statement
        self.show()

    # Enables the done button if nameEdit is populated
    def updateDoneButton(self):
        self.doneButton.setEnabled(len(self.nameEdit.text()) != 0)

    # Closes the dialog, returning name, desc and public
    def closeDialog(self):
        self.name = self.nameEdit.text()
        self.desc = self.descEdit.toPlainText()
        self.public = self.publicCheckBox.isChecked()
        self.accept()

# Dialog for managing Spotify/YouTube playlists
class ManagePlaylistDialog(QDialog):
    def __init__(self, spotifyPlaylists, youtubePlaylists, sAuth, yAuth):
        super().__init__()
        self.spotifyPlaylists = spotifyPlaylists
        self.youtubePlaylists = youtubePlaylists
        self.sAuth = sAuth
        self.yAuth = yAuth
        self.initUI()

    # Main function for creating the UI
    def initUI(self):
        spotifyLabel = QLabel("Spotify")
        youtubeLabel = QLabel("YouTube")

        #spotifyLabel.setSizePolicy(QSizePolicy.Minimum, QSizePolicy.Fixed)

        spotifyTable = QTableWidget(0, 3)
        spotifyTable.setFixedWidth(ACCOUNTS_TABLE_FIXED_WIDTH)
        spotifyTable.setMinimumHeight(ACCOUNTS_TABLE_FIXED_HEIGHT)
        #spotifyTable.setSizeAdjustPolicy(QAbstractScrollArea.AdjustToContents)
        spotifyTable.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        spotifyTable.horizontalHeader().hide()
        spotifyTable.verticalHeader().hide()
        spotifyTable.setShowGrid(False)
        spotifyTable.setSelectionMode(QAbstractItemView.NoSelection)

        youtubeTable = QTableWidget(0, 3)
        youtubeTable.setFixedWidth(ACCOUNTS_TABLE_FIXED_WIDTH)
        youtubeTable.setMinimumHeight(ACCOUNTS_TABLE_FIXED_HEIGHT)
        #youtubeTable.setSizeAdjustPolicy(QAbstractScrollArea.AdjustToContents)
        youtubeTable.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        youtubeTable.horizontalHeader().hide()
        youtubeTable.verticalHeader().hide()
        youtubeTable.setShowGrid(False)
        youtubeTable.setSelectionMode(QAbstractItemView.NoSelection)

        doneButton = QPushButton("Done")
        doneButton.setDefault(True)

        tableGridLayout = QGridLayout()
        tableGridLayout.addWidget(spotifyLabel, 0, 0)
        tableGridLayout.addWidget(spotifyTable, 1, 0)
        tableGridLayout.addWidget(youtubeLabel, 0, 1)
        tableGridLayout.addWidget(youtubeTable, 1, 1)

        buttonHBox = QHBoxLayout()
        buttonHBox.addStretch(1)
        buttonHBox.addWidget(doneButton)
        buttonHBox.addStretch(1)

        mainVBox = QVBoxLayout()
        mainVBox.addLayout(tableGridLayout)
        mainVBox.addLayout(buttonHBox)

        doneButton.clicked.connect(self.accept)

        self.spotifyTable = spotifyTable
        self.youtubeTable = youtubeTable

        self.updateTable("spotify")
        self.updateTable("youtube")

        self.setLayout(mainVBox)
        self.setWindowModality(Qt.ApplicationModal)
        self.setWindowTitle("Manage Playlists")
        self.show()

    # Updates a playlist. Uses ExportPlaylistDialog, passing a dictionary into current to prefill the values
    def update_playlist(self, service, playlist_name, playlist_id):
        if service == "spotify":
            playlist = apicontrol.spotify_get_playlist_info(self.sAuth, playlist_id)
            if playlist['owner']['id'] != self.sAuth.username:
                message = QMessageBox()
                message.setWindowTitle("Error")
                message.setIcon(QMessageBox.Warning)
                message.setText("Unowned Playlist")
                message.setInformativeText("You do not own this playlist and cannot make changes to it")
                message.setWindowModality(Qt.ApplicationModal)
                message.exec()
                return
            current = {
                'name':playlist['name'],
                'desc':playlist['description'],
                'public':bool(playlist['public'])
            }
        elif service == "youtube":
            playlist = apicontrol.youtube_get_playlist_info(self.yAuth, playlist_id)
            current = {
                'name':playlist['snippet']['title'],
                'desc':playlist['snippet']['description'],
                'public':playlist['status']['privacyStatus'] == "public" # false if unlisted or private
            }
        else:
            raise ValueError("Invalid service for update_playlist")
        dialog = ExportPlaylistDialog(service, current)
        if dialog.exec_():
            if service == "spotify":
                apicontrol.spotify_update_playlist(self.sAuth,playlist, dialog.name, dialog.desc, dialog.public)
                self.spotifyPlaylists[dialog.name] = self.spotifyPlaylists.pop(playlist_name)
            elif service == "youtube":
                apicontrol.youtube_update_playlist(self.yAuth,playlist, dialog.name, dialog.desc, dialog.public)
                self.youtubePlaylists[dialog.name] = self.youtubePlaylists.pop(playlist_name)
            self.updateTable(service)

    # Deletes the specified playlist, after a confirmation box
    def delete_playlist(self, service, playlist_name, playlist_id):
        messageBox = QMessageBox()
        messageBox.setWindowTitle(" ")
        messageBox.setInformativeText("Are you sure?")
        messageBox.setStandardButtons(QMessageBox.Yes | QMessageBox.No)
        messageBox.setDefaultButton(QMessageBox.No)
        if service == "spotify":
            messageBox.setText("Deleting " + playlist_name + " from Spotify")
            if messageBox.exec_() == QMessageBox.Yes:
                apicontrol.spotify_delete_playlist(self.sAuth, playlist_id)
                self.spotifyPlaylists.pop(playlist_name)
                self.updateTable("spotify")
        elif service == "youtube":
            messageBox.setText("Deleting " + playlist_name + " from YouTube")
            if messageBox.exec_() == QMessageBox.Yes:
                apicontrol.youtube_delete_playlist(self.yAuth, playlist_id)
                self.youtubePlaylists.pop(playlist_name)
                self.updateTable("youtube")
        else:
            raise ValueError("Invalid service for delete_playlist")

    # Updates the specified service's table todo - Handle playlists with duplicate titles
    def updateTable(self, service):
        if service == "spotify":
            table = self.spotifyTable
            playlists = self.spotifyPlaylists
        elif service == "youtube":
            table = self.youtubeTable
            playlists = self.youtubePlaylists
        else:
            raise ValueError("Invalid service for updateTable")
        if playlists == None:
            table.setRowCount(1)
            item = QTableWidgetItem("Logged Out")
            table.setItem(0, 0, item)
            table.setEnabled(False)
        else:
            table.setRowCount(len(playlists))
            for i, playlist in enumerate(playlists):
                item = QTableWidgetItem(playlist)
                item.setFlags(TABLEITEM_FLAGS_NOEDIT)
                updateButton = QPushButton("Change")
                deleteButton = QPushButton("Delete")
                table.setItem(i, 0, item)
                table.setIndexWidget(table.model().index(i, 1), updateButton)
                table.setIndexWidget(table.model().index(i, 2), deleteButton)
                updateButton.clicked.connect(
                    lambda
                        clicked,
                        playlist_name=playlist,
                        playlist_id=playlists[playlist],
                        service=service:
                            self.update_playlist(service, playlist_name, playlist_id)
                )
                deleteButton.clicked.connect(
                    lambda
                        clicked,
                        playlist_name=playlist,
                        playlist_id=playlists[playlist],
                        service=service:
                            self.delete_playlist(service, playlist_name, playlist_id)
                )

# Dialog for selecting a playlist to import
class ImportPlaylistDialog(QDialog):
    def __init__(self, playlists):
        super().__init__()
        self.playlists = list(playlists.keys())
        self.selected_playlist = None
        self.initUI()

    # Main function for creating the UI
    def initUI(self):

        mainList = QListWidget()
        for i, item in enumerate(self.playlists):
            newItem = QListWidgetItem(item)
            mainList.insertItem(i, newItem)

        doneButton = QPushButton("Done")
        doneButton.setEnabled(False)
        doneButton.setDefault(True)
        cancelButton = QPushButton("Cancel")

        buttonHBox = QHBoxLayout()
        buttonHBox.addWidget(doneButton)
        buttonHBox.addWidget(cancelButton)

        mainVBox = QVBoxLayout()
        mainVBox.addWidget(mainList)
        mainVBox.addLayout(buttonHBox)

        mainList.itemSelectionChanged.connect(lambda: doneButton.setEnabled(True))
        doneButton.clicked.connect(self.closeDialog)
        cancelButton.clicked.connect(self.reject)

        self.mainList = mainList

        self.setLayout(mainVBox)
        self.setWindowTitle("Select Playlist")
        self.setWindowModality(Qt.ApplicationModal)
        self.show()

    # Closes the dialog, returning the selected playlist
    def closeDialog(self):
        self.selected_playlist = self.playlists[self.mainList.currentRow()]
        self.accept()

# Dialog for opening a browser. Specify a URL to start at with startUrl.
# The dialog will quit when the current URL has quitUrl CONTAINED within it. E.g. specifying "localhost?code="
# in quitUrl will get the browser to quit when an auth code is returned
class BrowserDialog(QDialog):
    def __init__(self, startUrl, quitUrl = None):
        super().__init__()
        self.startUrl = startUrl
        self.quitUrl = quitUrl
        self.initUI()

    # Main function for creating the UI
    def initUI(self):
        backButton = QPushButton("Back")
        forwardButton = QPushButton("Forward")
        reloadButton = QPushButton("Reload")
        urlBar = QLineEdit("Loading...")
        urlBar.setSizePolicy(QSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding))
        urlBar.setReadOnly(True)

        browser = QWebEngineView()
        browser.resize(1200,800)

        upperHBox = QHBoxLayout()
        upperHBox.addWidget(backButton)
        upperHBox.addWidget(forwardButton)
        upperHBox.addWidget(reloadButton)
        upperHBox.addWidget(urlBar)

        mainVBox = QVBoxLayout()
        mainVBox.addLayout(upperHBox)
        mainVBox.addWidget(browser)
        mainVBox.addStretch(1)

        self.browser = browser
        self.urlBar = urlBar

        backButton.clicked.connect(browser.back)
        forwardButton.clicked.connect(browser.forward)
        reloadButton.clicked.connect(browser.reload)
        browser.urlChanged.connect(self.updateUrlLabel)
        browser.urlChanged.connect(self.checkUrl)

        browser.page().profile().cookieStore().deleteAllCookies() # Delete cookies
        browser.setUrl(QUrl(self.startUrl))

        self.setLayout(mainVBox)
        self.setWindowModality(Qt.ApplicationModal)
        self.setWindowTitle("Web Browser")
        self.show()

    # Checks to see if the current url matches quitUrl
    def checkUrl(self):
        if self.quitUrl:
            url = self.browser.url().toString()
            if self.quitUrl in url:
                self.url = url
                self.accept()

    # Updates the url label with the new url
    def updateUrlLabel(self, url):
        url = url.toString()
        self.urlBar.setText(url)
        self.urlBar.setCursorPosition(0)

# Dialog for managing loaded accounts
class AccountsDialog(QDialog):
    def __init__(self, spotifyAccounts, youtubeAccounts, spotifyCurrent=None, youtubeCurrent=None):
        super().__init__()
        self.spotifyAccounts = spotifyAccounts
        self.youtubeAccounts = youtubeAccounts
        self.spotifyCurrent = spotifyCurrent
        self.youtubeCurrent = youtubeCurrent
        self.removedAccount = None
        self.createdAccount = None
        self.reloadFlag = False
        self.initUI()

    # Main function for creating the UI
    def initUI(self):

        spotifyLabel = QLabel("Spotify")
        youtubeLabel = QLabel("YouTube")

        spotifyTable = QTableWidget(0, 3)
        spotifyTable.setFixedWidth(ACCOUNTS_TABLE_FIXED_WIDTH)
        spotifyTable.setFixedHeight(ACCOUNTS_TABLE_FIXED_HEIGHT)
        spotifyTable.setSizeAdjustPolicy(QAbstractScrollArea.AdjustToContents)
        spotifyTable.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        spotifyTable.horizontalHeader().hide()
        spotifyTable.verticalHeader().hide()
        spotifyTable.setShowGrid(False)
        spotifyTable.setSelectionMode(QAbstractItemView.NoSelection)

        youtubeTable = QTableWidget(0, 3)
        youtubeTable.setFixedWidth(ACCOUNTS_TABLE_FIXED_WIDTH)
        youtubeTable.setFixedHeight(ACCOUNTS_TABLE_FIXED_HEIGHT)
        youtubeTable.setSizeAdjustPolicy(QAbstractScrollArea.AdjustToContents)
        youtubeTable.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        youtubeTable.horizontalHeader().hide()
        youtubeTable.verticalHeader().hide()
        youtubeTable.setShowGrid(False)
        youtubeTable.setSelectionMode(QAbstractItemView.NoSelection)

        newSpotifyButton = QPushButton("New")
        newYoutubeButton = QPushButton("New")

        doneButton = QPushButton("Done")
        doneButton.setDefault(True)
        cancelButton = QPushButton("Cancel")

        tableGridLayout = QGridLayout()
        tableGridLayout.addWidget(spotifyLabel, 0,0)
        tableGridLayout.addWidget(spotifyTable, 1,0)
        tableGridLayout.addWidget(newSpotifyButton, 2,0)
        tableGridLayout.addWidget(youtubeLabel, 0,1)
        tableGridLayout.addWidget(youtubeTable, 1,1)
        tableGridLayout.addWidget(newYoutubeButton, 2,1)

        buttonHBox = QHBoxLayout()
        buttonHBox.addStretch(1)
        buttonHBox.addWidget(doneButton)
        buttonHBox.addWidget(cancelButton)
        buttonHBox.addStretch(1)

        mainVBox = QVBoxLayout()
        mainVBox.addLayout(tableGridLayout)
        mainVBox.addLayout(buttonHBox)

        doneButton.clicked.connect(self.accept)
        cancelButton.clicked.connect(self.reject)
        newSpotifyButton.clicked.connect(lambda: self.newAccount("spotify"))
        newYoutubeButton.clicked.connect(lambda: self.newAccount("youtube"))

        self.spotifyTable = spotifyTable
        self.youtubeTable = youtubeTable

        self.updateTable("spotify")
        self.updateTable("youtube")

        self.setLayout(mainVBox)
        self.setWindowModality(Qt.ApplicationModal)
        self.setWindowTitle("Manage Accounts")
        self.show()

    # Changes the specified service's current account to the specified account
    def changeAccount(self, service, newAccount):
        if service == "spotify":
            if self.spotifyCurrent == newAccount:
                self.spotifyCurrent = None # If newAccount is unchanged from current account, "Log Out" has been clicked so clear current
            else:
                self.spotifyCurrent = newAccount
        elif service == "youtube":
            if self.youtubeCurrent == newAccount:
                self.youtubeCurrent = None
            else:
                self.youtubeCurrent = newAccount
        else:
            raise ValueError("Invalid service for changeAccount")

    # Deletes the specified account from the specified service
    def deleteAccount(self, service, account):
        messageBox = QMessageBox()
        messageBox.setWindowTitle(" ")
        messageBox.setText("Deleting " + account)
        messageBox.setInformativeText("Are you sure?")
        messageBox.setStandardButtons(QMessageBox.Yes | QMessageBox.No)
        messageBox.setDefaultButton(QMessageBox.No)
        if messageBox.exec() == QMessageBox.Yes:
            if service == "spotify":
                if self.spotifyCurrent == account:
                    self.spotifyCurrent = None
                spotify.delete_account(account)
                self.spotifyAccounts.remove(account)
            elif service == "youtube":
                if self.youtubeCurrent == account:
                    self.youtubeCurrent = None
                youtube.delete_account(account)
                self.youtubeAccounts.remove(account)
            self.updateTable(service)

    # Starts the process of creating a new account in the specified service
    def newAccount(self, service):
        if service == "spotify":
            url = spotify.token(spotify_scope, returnUrl=True).url
            dialog = BrowserDialog(url, "localhost/?code=")
            if dialog.exec_():
                account = spotify.token(spotify_scope, returnUrl=dialog.url).username
                self.spotifyCurrent = account
                self.spotifyAccounts.add(account)
                self.updateTable(service)
        elif service == "youtube":
            url = youtube.token(youtube_scope, returnUrl=True).url
            dialog = BrowserDialog(url, "localhost/?code=")
            if dialog.exec_():
                account = youtube.token(youtube_scope, returnUrl=dialog.url).username
                self.youtubeCurrent = account
                self.youtubeAccounts.add(account)
                self.updateTable(service)
        else:
            raise ValueError("Invalid service for newAccount")

    # Updates the specified service's table
    def updateTable(self, service):
        if service == "spotify":
            table = self.spotifyTable
            accounts = self.spotifyAccounts
            loggedAccount = self.spotifyCurrent
        elif service == "youtube":
            table = self.youtubeTable
            accounts = self.youtubeAccounts
            loggedAccount = self.youtubeCurrent
        else:
            raise ValueError("Invalid service for updateTable")
        table.setRowCount(len(accounts))
        for i, account in enumerate(accounts):
            font = QFont()
            font.setBold(True)
            item = QTableWidgetItem(account)
            item.setFlags(TABLEITEM_FLAGS_NOEDIT)
            if loggedAccount == None:
                switchButton = QPushButton("Log In")
                toSwitch = account
            elif loggedAccount == account:
                switchButton = QPushButton("Log Out")
                item.setFont(font)
                toSwitch = None
            else:
                switchButton = QPushButton("Switch")
                toSwitch = account
            removeButton = QPushButton("Remove")
            table.setItem(i, 0, item)
            table.setIndexWidget(table.model().index(i, 1), switchButton)
            table.setIndexWidget(table.model().index(i, 2), removeButton)
            switchButton.clicked.connect(lambda clicked, service=service, account=toSwitch: self.changeAccount(service, account))
            switchButton.clicked.connect(lambda clicked, service=service: self.updateTable(service))
            removeButton.clicked.connect(lambda clicked, service=service, account=account: self.deleteAccount(service, account))

# A QMainWindow wrapper around MainWindow to allow the menu to be displayed.
class MenuWrapper(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setCentralWidget(MainWindow())
        self.setMenuBar(self.centralWidget().menuBar)
        self.setWindowTitle("Music Converter")
        self.show()
        self.centralWidget().layoutCleanup()

# Main function. Initialises Qt
def main():
    sys.excepthook = except_hook
    app = QApplication(sys.argv)
    win = MenuWrapper()
    sys.exit(app.exec_())

# Main function is not run if this file is imported as a module
if __name__ == "__main__": main()