import sys
from PyQt5.QtCore import *
from PyQt5.QtWidgets import *

class Example(QWidget):
    def __init__(self):
        super(Example, self).__init__()
        self.initUI()

    def testPrint(self, out):
        print(str(out))

    def initUI(self):

        mainLayout = QVBoxLayout()

        for x in range(10):
            button = QPushButton("Test " + str(x))
            button.clicked.connect(lambda checked, y=x: print(y))
            mainLayout.addWidget(button)

        self.setLayout(mainLayout)
        self.setWindowTitle("Example")
        self.show()

def main():
    app = QApplication(sys.argv)
    ex = Example()
    sys.exit(app.exec_())


if __name__ == '__main__':
    main()
