from PyQt5.QtCore import pyqtSlot, Qt
from PyQt5.QtWidgets import QGridLayout

import matplotlib.pyplot as plt
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas, NavigationToolbar2QT as NavToolbar
from matplotlib.figure import Figure


class PlotWidget(QGridLayout):

    def __init__(self, parent=None, instrumentManager=None):
        QGridLayout.__init__(self)

        self.figures = [
            [Figure()] * 4,
            [Figure()] * 4,
        ]

        for row, figs in enumerate(self.figures):
            for col, fig in enumerate(figs):
                self.addWidget(FigureCanvas(fig), row, col)

        # toolbar = NavToolbar(canvas, parent=parent)

        self._instrumentManager = instrumentManager

        for figs in self.figures:
            for fig in figs:
                fig.gca().plot([1, 2, 3], [1, 2, 3])

    @pyqtSlot(name='updatePlot')
    def updatePlot(self):
        print('update plot')
        freqs = list()
        amps = list()
        for freq, amp in self._instrumentManager._measure_data:
            freqs.append(freq)
            amps.append(amp)

        self.figure.clear()
        self.figure.gca().plot(freqs, amps)
        self.figure.canvas.draw()



