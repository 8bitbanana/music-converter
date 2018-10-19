import sys
from PyQt4 import QtGui, QtCore

class Example(QtGui.QWidget):
    def __init__(self):
        super(Example, self).__init__()
        self.initUI()

    def initUI(self):

        QtGui.QToolTip.setFont(QtGui.QFont("SansSerif", 10))
        self.setToolTip("This is a <b>QWidget</b> widget")

        # Qt uses html tags apparently
        # First parameter is the label, next parameter is the parent of the button
        btn = QtGui.QPushButton("Button", self)
        btn.setToolTip("This is a <b>QPushButton</b> widget")

        #                    v-Main app              v-Current Instance
        btn.clicked.connect(QtCore.QCoreApplication.instance().quit)

        # sizeHint gives the recommended size for the button
        btn.resize(btn.sizeHint())
        btn.move(50,50)
        
        self.setGeometry(300, 300, 250, 150)
        self.setWindowTitle("Example")
        self.show()

def main():
    app = QtGui.QApplication(sys.argv)
    ex = Example()
    sys.exit(app.exec_())


if __name__ == '__main__':
    main()

# http://zetcode.com/
