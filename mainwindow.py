from PyQt5 import uic
from PyQt5.QtWidgets import QMainWindow, QMessageBox
from PyQt5.QtCore import Qt, pyqtSignal, pyqtSlot

from instrumentmanager import InstrumentManager
from mytools.mapmodel import MapModel
from measuremodel import MeasureModel
from plotwidget import PlotWidget


class MainWindow(QMainWindow):

    instrumentsFound = pyqtSignal()
    sampleFound = pyqtSignal()
    measurementFinished = pyqtSignal(int)

    def __init__(self, parent=None):
        super().__init__(parent)

        self.setAttribute(Qt.WA_QuitOnClose)
        self.setAttribute(Qt.WA_DeleteOnClose)

        # create instance variables
        self._ui = uic.loadUi('mainwindow.ui', self)

        # create models
        self._instrumentManager = InstrumentManager()
        self._measureModel = MeasureModel(parent=self, instrumentManager=self._instrumentManager)

        self._chipModel = MapModel(parent=self, data={0: '1324ПМ1 (0,25 дБ)', 1: '1324ПМ2 (0,5 дБ)'})

        # create plot widgets
        self._plotWidget = PlotWidget(parent=self, instrumentManager=self._instrumentManager)
        self._ui.grpPlot.setLayout(self._plotWidget)

        self.initDialog()

    def setupUiSignals(self):
        pass

        self.measurementFinished.connect(self._measureModel.updateModel)
        self.measurementFinished.connect(self._plotWidget.updatePlot)

    def initDialog(self):
        self.setupUiSignals()

        self._ui.comboChip.setModel(self._chipModel)

        self._ui.tableMeasure.setModel(self._measureModel)

        self.modeSearchInstruments()

        self.refreshView()

    # UI utility methods
    def refreshView(self):
        self.resizeTable()

    def resizeTable(self):
        self._ui.tableMeasure.resizeRowsToContents()
        self._ui.tableMeasure.resizeColumnsToContents()

    def modeSearchInstruments(self):
        self._ui.btnMeasureStop.hide()
        self._ui.btnCheckSample.setEnabled(False)
        self._ui.comboChip.setEnabled(False)
        self._ui.btnMeasureStart.setEnabled(False)

    def modeCheckSample(self):
        self._ui.btnCheckSample.setEnabled(True)
        self._ui.comboChip.setEnabled(True)
        self._ui.btnMeasureStart.show()
        self._ui.btnMeasureStart.setEnabled(False)
        self._ui.btnMeasureStop.hide()
        analyzer, progr = self._instrumentManager.getInstrumentNames()
        self._ui.editAnalyzer.setText(analyzer)
        self._ui.editProg.setText(progr)

    def modeReadyToMeasure(self):
        self._ui.btnCheckSample.setEnabled(False)
        self._ui.comboChip.setEnabled(False)
        self._ui.btnMeasureStart.setEnabled(True)

    def modeMeasureInProgress(self):
        self._ui.btnCheckSample.setEnabled(False)
        self._ui.comboChip.setEnabled(False)
        self._ui.btnMeasureStart.setVisible(False)
        self._ui.btnMeasureStop.setVisible(True)

    def modeMeasureFinished(self):
        self._ui.btnCheckSample.setEnabled(False)
        self._ui.comboChip.setEnabled(False)
        self._ui.btnMeasureStart.setVisible(False)
        self._ui.btnMeasureStop.setVisible(True)

    def collectParams(self):
        chip_type = self._ui.comboChip.currentData(MapModel.RoleNodeId)
        return chip_type

    # instrument control methods
    def search(self):
        if not self._instrumentManager.findInstruments():
            QMessageBox.information(self, "Ошибка",
                                    "Не удалось найти инструменты, проверьте подключение.\nПодробности в логах.")
            return False

        print('found all instruments, enabling sample test')
        return True

    # event handlers
    def resizeEvent(self, event):
        self.refreshView()

    # autowire callbacks
    @pyqtSlot()
    def on_btnSearchInstruments_clicked(self):
        self.modeSearchInstruments()
        if not self.search():
            return
        self.modeCheckSample()
        self.instrumentsFound.emit()


    def failWith(self, message):
        QMessageBox.information(self, "Ошибка", message)

    @pyqtSlot()
    def on_btnCheckSample_clicked(self):
        try:
            if not self._instrumentManager.checkSample():
                self.failWith("Не удалось найти образец, проверьте подключение.\nПодробности в логах.")
                print('sample not detected')
                return
        except Exception as ex:
            print(ex)
        self.modeReadyToMeasure()
        self.sampleFound.emit()
        self.refreshView()

    @pyqtSlot()
    def on_btnMeasureStart_clicked(self):
        print('start measurement task')

        # if not self._instrumentManager.checkSample():
        #     self.failWith("Не удалось найти образец, проверьте подключение.\nПодробности в логах.")
        #     print('sample not detected')
        #     return

        self.modeMeasureInProgress()
        params = self.collectParams()
        self._instrumentManager.measure(params)
        self.measurementFinished.emit(params)
        self.modeMeasureFinished()
        self.refreshView()

    @pyqtSlot()
    def on_btnMeasureStop_clicked(self):
        # TODO implement
        print('abort measurement task')
        self.modeCheckSample()

    @pyqtSlot()
    def on_btnReport_clicked(self):
        print('reporting')

