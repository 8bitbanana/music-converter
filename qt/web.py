from PyQt5.QtCore import *
from PyQt5.QtWidgets import *
from PyQt5.QtWebEngineWidgets import *
from PyQt5.QtGui import *

import sys

URL_BAR_MAX_CHARS = 150

def except_hook(cls, exception, traceback):
    print(cls, exception, traceback)
    sys.__excepthook__(cls, exception, traceback)
    sys.exit(1)


class MainWindow(QWidget):
    def __init__(self, quitUrl = None):
        super().__init__()
        self.quitUrl = quitUrl
        self.initUI()

    def initUI(self):
        titleLabel = QLabel("Web Browser")

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
        mainVBox.addWidget(titleLabel)
        mainVBox.addLayout(upperHBox)
        mainVBox.addWidget(browser)
        mainVBox.addStretch(1)

        self.urlBar = urlBar

        backButton.clicked.connect(browser.back)
        forwardButton.clicked.connect(browser.forward)
        reloadButton.clicked.connect(browser.reload)
        browser.urlChanged.connect(self.updateUrlLabel)

        browser.page().profile().setPersistentCookiesPolicy(QWebEngineProfile.NoPersistentCookies) # disable cookies, so logins are not saved
        browser.setUrl(QUrl("https://accounts.google.com/signin/oauth?client_id=251705760801-5o6ihfj26i59d171n81koolor0d6i6al.apps.googleusercontent.com&as=qUvNxSrWm6HdweoePqf3VA&nosignup=1&Email=gd8bitbanana@gmail.com&destination=https://localhost&approval_state=!ChRNUVYxUWtaVU40TGRFeE1sMnQxMhIfNDNaRnhLeG5FQzBVMEVBN1JaNXdOM085VV85M1RoWQ%E2%88%99ANKMe1QAAAAAW19l-MVGRERBQsOgPPV_0cqeQ579HtKb&oauthgdpr=1&delegation=1&xsrfsig=AHgIfE9DEQ4dO3vNfAv9GI_7pvpeuzQD_w"))
        #browser.setUrl(QUrl("https://google.com"))

        self.browser = browser

        self.setLayout(mainVBox)
        self.setWindowTitle("Web Browser")
        self.show()

    def checkUrl(self):
        if self.quitUrl:
            if self.quitUrl in self.browser.url().toString():
                # quit dialog
                pass

    def updateUrlLabel(self, url):
        url = url.toString()
        self.urlBar.setText(url)
        self.urlBar.setCursorPosition(0)

if __name__ == "__main__":
    sys.excepthook = except_hook
    app = QApplication(sys.argv)
    win = MainWindow()
    sys.exit(app.exec_())