from PyQt5.QtCore import pyqtSlot, Qt
from PyQt5.QtWidgets import QGridLayout

import matplotlib.pyplot as plt
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas, NavigationToolbar2QT as NavToolbar
from matplotlib.figure import Figure


class PlotWidget(QGridLayout):

    def __init__(self, parent=None, instrumentManager=None):
        QGridLayout.__init__(self)

        self.fig11 = Figure()
        self.fig12 = Figure()
        self.fig13 = Figure()
        self.fig14 = Figure()
        self.fig21 = Figure()
        self.fig22 = Figure()
        self.fig23 = Figure()
        self.fig24 = Figure()

        self.addWidget(FigureCanvas(self.fig11), 0, 1)
        self.addWidget(FigureCanvas(self.fig12), 0, 2)
        self.addWidget(FigureCanvas(self.fig13), 0, 3)
        self.addWidget(FigureCanvas(self.fig14), 0, 4)
        self.addWidget(FigureCanvas(self.fig21), 1, 1)
        self.addWidget(FigureCanvas(self.fig22), 1, 2)
        self.addWidget(FigureCanvas(self.fig23), 1, 3)
        self.addWidget(FigureCanvas(self.fig24), 1, 4)

        # toolbar = NavToolbar(canvas, parent=parent)

        self._instrumentManager = instrumentManager

    def plot(self, fig, xs, ys):
        fig.clear()
        for x, y in zip(xs, ys):
            fig.gca().plot(x, y)
        fig.canvas.draw()

    def plot_baseline(self):
        self.plot(self.fig11,
                  [self._instrumentManager._res_freqs] * 1,
                  [self._instrumentManager._res_baseline])

    def plot_normalized_att(self):
        self.plot(self.fig21,
                  [self._instrumentManager._res_freqs] * 8,
                  self._instrumentManager._res_normalized_att)

    def plot_s11(self):
        self.plot(self.fig12,
                  [self._instrumentManager._res_freqs] * 8,
                  self._instrumentManager._res_s11)

    def plot_s22(self):
        self.plot(self.fig22,
                  [self._instrumentManager._res_freqs] * 8,
                  self._instrumentManager._res_s22)

    def plot_err_per_code(self):
        self.plot(self.fig23,
                  [self._instrumentManager._res_freqs] * 8,
                  self._instrumentManager._res_att_err_per_code)

    @pyqtSlot()
    def updatePlot(self):
        print('update plot')

        self.plot_baseline()
        self.plot_normalized_att()
        self.plot_s11()
        self.plot_s22()

        try:
            self.plot_err_per_code()
        except Exception as ex:
            print(ex)

