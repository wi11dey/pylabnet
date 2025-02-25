import pyqtgraph as pg
import numpy as np
import copy
import time
from PyQt5 import QtWidgets, QtCore

from pyqtgraph.widgets.MatplotlibWidget import MatplotlibWidget
from pylabnet.gui.pyqt.external_gui import Window, ParameterPopup, GraphPopup
from pylabnet.utils.logging.logger import LogClient, LogHandler
from pylabnet.utils.helper_methods import save_metadata, generic_save, pyqtgraph_save, fill_2dlist
from pylabnet.utils.confluence_handler.confluence_handler import Confluence_Handler

class Dataset():

    def __init__(self, gui: Window, log: LogClient = None, data=None,
                 x=None, graph=None, name=None, dont_clear=False, enable_confluence=True, **kwargs):
        """ Instantiates an empty generic dataset

        :param gui: (Window) GUI window for data graphing
        :param log: (LogClient)
        :param data: initial data to set
        :param x: x axis
        :param graph: (pg.PlotWidget) graph to use
        :param confluence, instances of confluence_handler class - handle confluence things. 
        """

        self.log = LogHandler(log)
        if 'config' in kwargs:
            self.config = kwargs['config']
        else:
            self.config = {}
        self.metadata = self.log.get_metadata()
        if name is None:
            self.name = self.__class__.__name__
        else:
            self.name = name

        # Set data registers
        self.data = data
        self.x = x
        self.children = {}
        self.mapping = {}
        self.widgets = {}

        # Flag indicating whether data should be
        self.dont_clear = dont_clear

        # Configure data visualization
        self.gui = gui

        self.visualize(graph, **kwargs)

        # Property which defines whether dataset is important, i.e. should it be saved in a separate dataset
        self.is_important = False

        # Confluence handler and its button
        self.confluence_handler  = None

        if(self.log == None): enable_confluence = False

        if(enable_confluence is True):
            self.confluence_handler = Confluence_Handler(self, self.app,  log_client=self.log)

            extractAction_Upload = QtWidgets.QAction("&UPLOAD to CONFLUENCE", self)
            extractAction_Upload.setShortcut("Ctrl+S")
            extractAction_Upload.setStatusTip('Upload to the confluence page')
            extractAction_Upload.triggered.connect(self.upload_pic)

            extractAction_Update = QtWidgets.QAction("&CONFLUENCE SETTING", self)
            extractAction_Update.setShortcut("Ctrl+X")
            extractAction_Update.setStatusTip('The space and page names of confluence')
            extractAction_Update.triggered.connect(self.update_setting)


            mainMenu = self.menuBar()
            ActionMenu = mainMenu.addMenu('&Action')
            ActionMenu.addAction(extractAction_Upload)
            ActionMenu.addAction(extractAction_Update)


    def update_setting(self):
        self.confluence_handler.confluence_popup.Popup_Update()


    def upload_pic(self):
        self.confluence_handler.confluence_popup.Popup_Upload()
        return


    def add_child(self, name, mapping=None, data_type=None,
                  new_plot=True, dont_clear=False, **kwargs):
        """ Adds a child dataset with a particular data mapping

        :param name: (str) name of processed dataset
            becomes a Dataset object (or child) as attribute of self
        :param mapping: (function) function which transforms Dataset to processed Dataset
        :param data_type: (Class) type of Dataset to add
        :param new_plot: (bool) whether or not to use a new plot
        """

        if new_plot:
            graph = None
        else:
            graph = self.graph

        if data_type is None:
            data_type = self.__class__

        self.children[name] = data_type(
            gui=self.gui,
            data=self.data,
            graph=graph,
            name=name,
            dont_clear=dont_clear,
            **kwargs
        )

        if mapping is not None:
            self.mapping[name] = mapping

    def set_data(self, data=None, x=None):
        """ Sets data

        :param data: data to set
        :param x: x axis
        """

        self.data = data

        if x is not None:
            self.x = x

        self.set_children_data()

    def set_children_data(self):
        """ Sets all children data with mappings """

        for name, child in self.children.items():
            # If we need to process the child data, do it

            if name in self.mapping:
                self.mapping[name](self, prev_dataset=child)

    def visualize(self, graph, **kwargs):
        """ Prepare data visualization on GUI

        :param graph: (pg.PlotWidget) graph to use
        """

        self.handle_new_window(graph, **kwargs)

        if 'color_index' in kwargs:
            color_index = kwargs['color_index']
        else:
            color_index = self.gui.graph_layout.count() - 1
        self.curve = self.graph.plot(
            pen=pg.mkPen(self.gui.COLOR_LIST[
                color_index
            ])
        )
        self.update(**kwargs)

    def clear_data(self):
        self.data = None
        self.curve.setData([])

    # Note: This recursive code could potentially run into infinite iteration problem.
    def clear_all_data(self):

        if not self.dont_clear:
            self.clear_data()
            self.update()

        for child in self.children.values():
            child.clear_all_data()

    def update(self, **kwargs):
        """ Updates current data to plot"""

        if self.data is not None:
            if self.x is not None:
                self.curve.setData(self.x[:len(self.data)], self.data)
            else:
                self.curve.setData(self.data)

        for child in self.children.values():
            child.update(**kwargs)

    def interpret_status(self, status):
        """ Interprets a status flag for exepriment monitoring

        :param status: (str) current status message
        """

        if status == 'OK':
            self.gui.presel_status.setText(status)
            self.gui.presel_status.setStyleSheet('')
        elif status == 'BAD':
            self.gui.presel_status.setText(status)
            self.gui.presel_status.setStyleSheet('background-color: red;')
        else:
            self.gui.presel_status.setText(status)
            self.gui.presel_status.setStyleSheet('background-color: gray;')

    def save(self, filename=None, directory=None, date_dir=True):

        generic_save(
            data=self.data,
            filename=f'{filename}_{self.name}',
            directory=directory,
            date_dir=date_dir
        )
        if self.x is not None:
            generic_save(
                data=self.x,
                filename=f'{filename}_{self.name}_x',
                directory=directory,
                date_dir=date_dir
            )

        if hasattr(self, 'graph'):
            pyqtgraph_save(
                self.graph.getPlotItem(),
                f'{filename}_{self.name}',
                directory,
                date_dir
            )

        # if the dataset is important, save it again in the important dataset folder.
        if self.is_important:
            generic_save(
                data=self.data,
                filename=f'{filename}_{self.name}',
                directory=directory + "\\important_data",
                date_dir=date_dir
            )
            if self.x is not None:
                generic_save(
                    data=self.x,
                    filename=f'{filename}_{self.name}_x',
                    directory=directory + "\\important_data",
                    date_dir=date_dir
                )

            if hasattr(self, 'graph'):
                pyqtgraph_save(
                    self.graph.getPlotItem(),
                    f'{filename}_{self.name}',
                    directory + "\\important_data",
                    date_dir
                )

        for child in self.children.values():
            child.save(filename, directory, date_dir)

    def add_params_to_gui(self, **params):
        """ Adds parameters of dataset to gui

        :params: (dict) containing all parameter names and values
        """

        for name, value in params.items():

            hbox = QtWidgets.QHBoxLayout()
            hbox.addWidget(QtWidgets.QLabel(name))
            if type(value) is int:
                self.widgets[name] = QtWidgets.QSpinBox()
                self.widgets[name].setMaximum(1000000000)
                self.widgets[name].setMinimum(-1000000000)
                self.widgets[name].setValue(value)
                self.widgets[name].valueChanged.connect(
                    lambda state, obj=self, name=name: setattr(obj, name, state)
                )
            elif type(value) is float:
                self.widgets[name] = QtWidgets.QDoubleSpinBox()
                self.widgets[name].setMaximum(1000000000.)
                self.widgets[name].setMinimum(-1000000000.)
                self.widgets[name].setDecimals(6)
                self.widgets[name].setValue(value)
                self.widgets[name].valueChanged.connect(
                    lambda state, obj=self, name=name: setattr(obj, name, state)
                )
            else:
                self.widgets[name] = QtWidgets.QLabel(str(value))
            setattr(self.gui, name, self.widgets[name])

            hbox.addWidget(self.widgets[name])
            self.gui.dataset_layout.addLayout(hbox)

        self.gui.initialize_step_sizes()

    def handle_new_window(self, graph, **kwargs):
        """ Handles visualizing and possibility of new popup windows """

        if graph is None:

            # If we want to use a separate window
            if 'window' in kwargs:

                # Check whether this window exists
                if not kwargs['window'] in self.gui.windows:

                    if 'window_title' in kwargs:
                        window_title = kwargs['window_title']
                    else:
                        window_title = 'Graph Holder'

                    self.gui.windows[kwargs['window']] = GraphPopup(
                        window_title=window_title, size=(700, 300)
                    )

                self.graph = pg.PlotWidget()
                self.gui.windows[kwargs['window']].graph_layout.addWidget(
                    self.graph
                )

            # Otherwise, add a graph to the main layout
            else:
                self.graph = self.gui.add_graph()
            self.graph.getPlotItem().setTitle(self.name)

        # Reuse a PlotWidget if provided
        else:
            self.graph = graph


class AveragedHistogram(Dataset):
    """ Subclass for plotting averaged histogram """

    def set_data(self, data=None, x=None):
        """ Sets data by adding to previous histogram

        :param data: new data to set
        :param x: x axis
        """

        # Cast as a numpy array if needed
        if isinstance(data, list):
            self.recent_data = np.array(data)
        else:
            self.recent_data = data

        if self.data is None:
            self.data = copy.deepcopy(self.recent_data)
        else:
            self.data += self.recent_data

        self.set_children_data()


class PreselectedHistogram(AveragedHistogram):
    """ Measurement class for showing raw averaged, single trace,
        and preselected data using a gated counter for preselection"""

    def __init__(self, *args, **kwargs):
        """ Instantiates preselected histogram measurement

        see parent classes for details
        """

        kwargs['name'] = 'Average Histogram'
        self.preselection = True
        self.presel_success_indicator = pg.SpinBox(value=0.0)
        self.presel_success_indicator.setStyleSheet('font-size: 12pt')
        self.presel_success_value = 0
        super().__init__(*args, **kwargs)
        self.add_child(name='Single Trace', mapping=self.recent, data_type=Dataset)
        if 'presel_params' in self.config:
            self.presel_params = self.config['presel_params']
            self.fill_parameters(self.presel_params)
        else:
            self.presel_params = None
            self.setup_preselection(threshold=float, less_than=str, avg_values=int)
        if 'presel_data_length' in self.config:
            presel_data_length = self.config['presel_data_length']
        else:
            presel_data_length = None

        hbox = QtWidgets.QHBoxLayout()

        label = QtWidgets.QLabel('Recent preselection average: ')
        label.setStyleSheet('font-size: 12pt')
        hbox.addWidget(label)
        hbox.addWidget(self.presel_success_indicator)
        self.gui.graph_layout.addLayout(hbox)
        self.add_child(
            name='Preselection Counts',
            data_type=InfiniteRollingLine,
            data_length=presel_data_length
        )
        self.line = self.children['Preselection Counts'].graph.getPlotItem().addLine(y=self.presel_params['threshold'])

    def setup_preselection(self, **kwargs):

        self.popup = ParameterPopup(**kwargs)
        self.popup.parameters.connect(self.fill_parameters)

    def fill_parameters(self, params):

        self.presel_params = params
        self.add_child(
            name='Preselected Trace',
            mapping=self.preselect,
            data_type=AveragedHistogram
        )
        self.log.update_metadata(presel_params=self.presel_params)
        self.add_params_to_gui(**self.presel_params)

        self.widgets['threshold'].valueChanged.connect(self.update_threshold)

    def preselect(self, dataset, prev_dataset):
        """ Preselects based on user input parameters """

        if self.presel_params['less_than'] == 'True':
            if dataset.children['Preselection Counts'].data[-1] < self.presel_params['threshold']:
                dataset.preselection = True
                if prev_dataset.data is None:
                    prev_dataset.data = dataset.recent_data
                else:
                    prev_dataset.data += dataset.recent_data
            else:
                dataset.preselection = False
        else:
            if dataset.children['Preselection Counts'].data[-1] > self.presel_params['threshold']:
                dataset.preselection = True
                if prev_dataset.data is None:
                    prev_dataset.data = dataset.recent_data
                else:
                    prev_dataset.data += dataset.recent_data
            else:
                dataset.preselection = False

        # Calculate most recent preselection value

        presel_trace = dataset.children['Preselection Counts'].data
        presel_trace_len = len(presel_trace)
        if presel_trace_len > 0:
            if self.presel_params['avg_values'] > presel_trace_len:
                self.presel_success_value = np.mean(presel_trace)
            else:
                self.presel_success_value = np.mean(presel_trace[-self.presel_params['avg_values']:])

    def set_data(self, data=None, x=None, preselection_data=None):
        """ Sets the data for a new round of acquisition

        :param data: histogram data from latest acquisition
            note the histogram should have been cleared prior to acquisition
        :param x: x axis for data
        :param preselection_data: (float) value of preselection indicator
            from latest acquisition
        """

        self.children['Preselection Counts'].set_data(preselection_data)
        super().set_data(data, x)

    def interpret_status(self, status):
        super().interpret_status(status)

        for name, child in self.children.items():
            if name in self.mapping and self.mapping[name] == self.preselect:
                vb = child.graph.getPlotItem().getViewBox()
                if status == 'BAD':
                    vb.setBackgroundColor(0.1)
                else:
                    vb.setBackgroundColor(0.0)

    def update(self, **kwargs):

        self.presel_success_indicator.setValue(self.presel_success_value)
        super().update(**kwargs)

    def update_threshold(self, threshold: float):
        """ Updates the threshold to a new value

        :param threshold: (float) new value of threshold
        """

        setattr(self, 'threshold', threshold)
        self.presel_params['threshold'] = threshold
        self.line.setValue(self.presel_params['threshold'])

    @staticmethod
    def recent(dataset, prev_dataset):
        prev_dataset.data = dataset.recent_data


class InvisibleData(Dataset):
    """ Dataset which does not plot """

    def visualize(self, graph, **kwargs):
        self.curve = pg.PlotDataItem()


class RollingLine(Dataset):
    """ Implements a rolling dataset where new values are
        added incrementally e.g. in time-traces """

    def __init__(self, *args, **kwargs):

        # We need to know the data length, so prompt if necessary
        if 'data_length' in kwargs and kwargs['data_length'] is not None:
            self.data_length = kwargs['data_length']
        else:
            self.popup = ParameterPopup(data_length=int)
            self.waiting = True
            self.popup.parameters.connect(self.setup_axis)
        super().__init__(*args, **kwargs)

    def setup_axis(self, params):

        self.data_length = params['data_length']
        self.waiting = False

    def set_data(self, data):
        """ Updates data

        :param data: (scalar) data to add
        """

        if self.data is None:
            self.data = np.array([data])

        else:
            if len(self.data) == self.data_length:
                self.data = np.append(self.data, data)[1:]
            else:
                self.data = np.append(self.data, data)

        for name, child in self.children.items():
            # If we need to process the child data, do it
            if name in self.mapping:
                self.mapping[name](self, prev_dataset=child)


class InfiniteRollingLine(RollingLine):
    """ Extension of RollingLine that stores the data
        indefinitely, but still only plots a finite amount """

    def set_data(self, data):
        """ Updates data

        :param data: (scalar) data to add
        """

        if self.data is None:
            self.data = np.array([data])

        else:
            self.data = np.append(self.data, data)

    def update(self, **kwargs):
        """ Updates current data to plot"""

        if self.data is not None:

            if len(self.data) > self.data_length:
                if self.x is not None:
                    self.curve.setData(self.x, self.data[-self.data_length:])
                else:
                    self.curve.setData(self.data[-self.data_length:])

                for name, child in self.children.items():
                    # If we need to process the child data, do it
                    if name in self.mapping:
                        self.mapping[name](self, prev_dataset=child)
                    child.update(**kwargs)
            else:
                super().update(**kwargs)


class ManualOpenLoopScan(Dataset):

    def __init__(self, *args, **kwargs):

        self.args = args
        self.kwargs = kwargs
        self.stop = False

        kwargs['name'] = 'Raw Counts'

        if 'config' in kwargs:
            self.config = kwargs['config']
        else:
            self.config = {}
        self.kwargs.update(self.config)

        super().__init__(*self.args, **self.kwargs)

        self.add_child(
            name='Smooth counts',
            mapping=self.smooth_data,
            data_type=Dataset
        )

        self.add_child(
            name='Wavelength',
            data_type=InfiniteRollingLine,
            data_length=1000
        )

        # Get scan parameters from config
        if set(['integration', 'max_runs', 'bins_per_ghz', 'min_bins']).issubset(self.kwargs.keys()):
            self.fill_params(self.kwargs)

        else:
            self.log.error('Please provide config file parameters "delay", "max_runs", "bins_per_ghz", and "min_bins.')

    def fill_params(self, config):
        """ Fills the min max and pts parameters """
        self.integration, self.max_runs, self.bins_per_ghz, self.min_bins = config['integration'], config['max_runs'], config['bins_per_ghz'], config['min_bins']
        # Questions: Why is this line necessary for the plot to appear.
        self.kwargs.update(dict(
            x=np.linspace(400, 500, 100),
            name='Fwd trace'
        ))

    def visualize(self, graph, **kwargs):
        self.handle_new_window(graph, **kwargs)

        if 'color_index' in kwargs:
            color_index = kwargs['color_index']
        else:
            color_index = self.gui.graph_layout.count() - 1
        self.curve = self.graph.plot(
            pen=pg.mkPen(self.gui.COLOR_LIST[
                color_index
            ]),
            symbol='o',
            symbolPen=pg.mkPen(self.gui.COLOR_LIST[
                color_index
            ]),
            symbolBrush=pg.mkBrush(self.gui.COLOR_LIST[color_index]),
            downsample=0.5,
            downsampleMethod='mean'
        )
        self.update(**kwargs)

    def set_data(self, data=None, x=None, wavelength=None):
        """ Sets the data for a new round of acquisition

        :param data: histogram data from latest acquisition
            note the histogram should have been cleared prior to acquisition
        :param x: x axis for data
        :param wavelength: (float) value of acquired wavelength
        """

        # Add wavelength to aux monitor.
        self.children['Wavelength'].set_data(wavelength)

        # Append new data.
        if self.data is None:
            self.data = np.array([data])

        else:
            self.data = np.append(self.data, data)

        if self.x is None:
            self.x = np.array([x])

        else:
            self.x = np.append(self.x, x)

        # Re-order array
        self.data = self.data[np.argsort(self.x)]
        self.x = self.x[np.argsort(self.x)]

        # Add data to parent dataset.
        super().set_data(self.data, self.x)

    def smooth_data(self, dataset, prev_dataset):

        previous_x = dataset.x
        previous_y = dataset.data

        data_len = len(previous_y)
        scan_span = ((previous_x[-1] - previous_x[0]) * 1e3)
        current_bins_per_ghz = data_len / scan_span

        # self.log.info(f'Scan span = {scan_span}')
        # self.log.info(f'current_bins_per_ghz = {current_bins_per_ghz}')
        # self.log.info(f'self.bins_per_ghz = {self.bins_per_ghz}')

        new_num_bins = int(scan_span * self.bins_per_ghz)
        #self.log.info(f'new_num_bins = {new_num_bins}')

        if current_bins_per_ghz < self.bins_per_ghz or scan_span < 0.001 or new_num_bins < self.min_bins:
            prev_dataset.data = previous_y
            prev_dataset.x = previous_x
        else:

            self.log.info(f'new_num_bins = {new_num_bins}')
            self.log.info(f'data_len = {data_len}')

            padded_x = np.pad(previous_x, (0, new_num_bins - data_len % new_num_bins), 'constant')
            padded_y = np.pad(previous_y, (0, new_num_bins - data_len % new_num_bins), 'constant')

            binlength = int(len(padded_x) / new_num_bins)

            # Rebin arrays
            rebinned_x = np.zeros(new_num_bins)
            rebinned_y = np.zeros(new_num_bins)

            # Tranform 0s to Nan so they don't change the mean values.
            padded_x[padded_x == 0] = np.nan
            padded_y[padded_y == 0] = np.nan

            for i in range(new_num_bins):
                # Sum counts
                rebinned_y[i] = np.sum(padded_y[i * binlength:(i + 1) * binlength])
                # Average wavelength
                rebinned_x[i] = np.average(padded_x[i * binlength:(i + 1) * binlength])

            # Remove nans.
            nan_index = ~np.isnan(rebinned_x)
            self.log.info(nan_index)

            rebinned_x = rebinned_x[nan_index]
            rebinned_y = rebinned_y[nan_index]

            prev_dataset.data = rebinned_y[:-1]
            prev_dataset.x = rebinned_x[:-1]


class LockMonitor(Dataset):

    def __init__(self, *args, **kwargs):

        self.args = args
        self.kwargs = kwargs
        self.stop = False

        if 'config' in kwargs:
            self.config = kwargs['config']
        else:
            self.config = {}
        self.kwargs.update(self.config)

        self.v = None
        self.rp_pid_gate = None

        super().__init__(*self.args, **self.kwargs)

        # Add child for PD current
        self.add_child(
            name='Piezo Voltage',
            data_type=InfiniteRollingLine,
            data_length=10000,
            color_index=4
        )

        # Add child for PD current
        self.add_child(
            name='PD Transmission',
            data_type=InfiniteRollingLine,
            data_length=10000,
            color_index=4
        )
        self.add_child(
            name='Demodulated PD Transmission',
            data_type=InfiniteRollingLine,
            data_length=10000,
            color_index=4
        )
        self.add_child(
            name='Cavity lock',
            data_type=Dataset,
            window='lock_monitor',
            window_title='Cavity lock monitor',
            color_index=3
        )
        self.add_child(
            name='Cavity history',
            data_type=InfiniteRollingLine,
            data_length=10000,
            window='lock_monitor',
            color_index=4
        )
        self.add_child(
            name='Max count history',
            data_type=InfiniteRollingLine,
            data_length=10000,
            window='lock_monitor',
            color_index=5
        )

    def set_v_and_counts(self, v, counts):
        """ Updates voltage and counts"""
        self.v = v
        # self.widgets['voltage'].setValue(self.v)
        self.children['Cavity history'].set_data(self.v)
        self.children['Max count history'].set_data(counts)

    def set_pd_demod_piezo_voltage(self, pd_voltage, demod_voltage, piezo_voltage):
        self.children['PD Transmission'].set_data(pd_voltage)
        self.children['Demodulated PD Transmission'].set_data(demod_voltage)
        self.children['Piezo Voltage'].set_data(piezo_voltage)


class Scatterplot(Dataset):
    def visualize(self, graph, **kwargs):
        self.handle_new_window(graph, **kwargs)

        self.curve = pg.ScatterPlotItem(x=[0], y=[0])
        self.graph.addItem(self.curve)
        self.update(**kwargs)


class TriangleScan1D(Dataset):
    """ 1D Triangle sweep of a parameter """

    def __init__(self, *args, **kwargs):

        self.args = args
        self.kwargs = kwargs
        self.all_data = None
        self.update_hmap = False
        self.stop = False
        if 'config' in kwargs:
            self.config = kwargs['config']
        else:
            self.config = {}
        self.kwargs.update(self.config)

        # # First, try to get scan parameters from GUI
        # if hasattr(self, 'widgets'):
        #     if set(['min', 'max', 'pts', 'reps']).issubset(self.widgets.keys()):
        #         self.widgets['reps'].setValue(0)
        #         self.fill_params(dict(
        #             min = self.widgets['min'].value(),
        #             max = self.widgets['max'].value(),
        #             pts = self.widgets['pts'].value()
        #         ))

        # Get scan parameters from config
        if set(['min', 'max', 'pts']).issubset(self.kwargs.keys()):
            self.fill_params(self.kwargs)

        # Prompt user if not provided in config
        else:
            self.popup = ParameterPopup(min=float, max=float, pts=int)
            self.popup.parameters.connect(self.fill_params)

    def fill_params(self, config):
        """ Fills the min max and pts parameters """

        self.min, self.max, self.pts = config['min'], config['max'], config['pts']

        if 'backward' in self.kwargs:
            self.backward = True
            self.kwargs.update(dict(
                x=np.linspace(self.max, self.min, self.pts),
                name='Bwd trace'
            ))
        else:
            self.backward = False
            self.kwargs.update(dict(
                x=np.linspace(self.min, self.max, self.pts),
                name='Fwd trace'
            ))
        super().__init__(*self.args, **self.kwargs)

        pass_kwargs = dict()
        if 'window' in config:
            pass_kwargs['window'] = config['window']

        # Add child for averaged plot
        self.add_child(
            name=f'{"Bwd" if self.backward else "Fwd"} avg',
            mapping=self.avg,
            data_type=Dataset,
            new_plot=False,
            x=self.x,
            color_index=2
        )

        # Add child for HMAP
        self.add_child(
            name=f'{"Bwd" if self.backward else "Fwd"} scans',
            mapping=self.hmap,
            data_type=HeatMap,
            min=self.min,
            max=self.max,
            pts=self.pts,
            **pass_kwargs
        )

        # Add child for backward plot
        if not self.backward:
            self.add_child(
                name='Bwd trace',
                min=self.min,
                max=self.max,
                pts=self.pts,
                backward=True,
                color_index=1,
                **pass_kwargs
            )

            for i in reversed(range(self.gui.dataset_layout.count())):
                self.gui.dataset_layout.itemAt(i).setParent(None)
            self.add_params_to_gui(
                min=config['min'],
                max=config['max'],
                pts=config['pts'],
                reps=0
            )

    def avg(self, dataset, prev_dataset):
        """ Computes average dataset (mapping) """

        # If we have already integrated a full dataset, avg
        if dataset.reps > 1:
            current_index = len(dataset.data) - 1
            prev_dataset.data[current_index] = (
                prev_dataset.data[current_index] * (dataset.reps - 1)
                + dataset.data[-1]
            ) / (dataset.reps)
        else:
            prev_dataset.data = dataset.data

    def set_data(self, value):

        if self.data is None:
            self.reps = 1
            self.data = np.array([value])
        else:
            self.data = np.append(self.data, value)

        if len(self.data) > self.pts:
            self.update_hmap = True
            self.reps += 1

            try:
                reps_to_do = self.widgets['reps'].value()
                if reps_to_do > 0 and self.reps > reps_to_do:
                    self.stop = True
            except KeyError:
                pass

            if self.all_data is None:
                self.all_data = self.data[:-1]
            else:
                self.all_data = np.vstack((self.all_data, self.data[:-1]))
            self.data = np.array([self.data[-1]])

        self.set_children_data()

    def update(self, **kwargs):
        """ Updates current data to plot"""

        if self.data is not None and len(self.data) <= len(self.x):
            self.curve.setData(self.x[:len(self.data)], self.data)

        for child in self.children.values():
            child.update(update_hmap=copy.deepcopy(self.update_hmap))

        if self.update_hmap:
            self.update_hmap = False

    def hmap(self, dataset, prev_dataset):

        if dataset.update_hmap:
            prev_dataset.data = dataset.all_data

            if 'Bwd' in prev_dataset.name:
                try:
                    prev_dataset.data = np.fliplr(prev_dataset.data)
                except ValueError:
                    prev_dataset.data = np.flip(prev_dataset.data)


class SawtoothScan1D(Dataset):
    """ 1D Sawtooth sweep of a parameter """

    def __init__(self, *args, **kwargs):

        self.args = args
        self.kwargs = kwargs
        self.all_data = None
        self.update_hmap = False
        self.stop = False
        if 'config' in kwargs:
            self.config = kwargs['config']
        else:
            self.config = {}
        self.kwargs.update(self.config)

        # Get scan parameters from config
        if set(['min', 'max', 'pts']).issubset(self.kwargs.keys()):
            self.fill_params(self.kwargs)

        # Prompt user if not provided in config
        else:
            self.popup = ParameterPopup(min=float, max=float, pts=int)
            self.popup.parameters.connect(self.fill_params)

    def fill_params(self, config):
        """ Fills the min max and pts parameters """

        self.min, self.max, self.pts = config['min'], config['max'], config['pts']

        self.kwargs.update(dict(
            x=np.linspace(self.min, self.max, self.pts),
            name=config['name'] + 'trace'
        ))
        super().__init__(*self.args, **self.kwargs)

        pass_kwargs = dict()
        if 'window' in config:
            pass_kwargs['window'] = config['window']

        # Add child for averaged plot
        self.add_child(
            name=config['name'] + 'avg',
            mapping=self.avg,
            data_type=Dataset,
            new_plot=False,
            x=self.x,
            color_index=2
        )

        # Add child for HMAP
        self.add_child(
            name=config['name'] + 'scans',
            mapping=self.hmap,
            data_type=HeatMap,
            min=self.min,
            max=self.max,
            pts=self.pts,
            **pass_kwargs
        )

    def avg(self, dataset, prev_dataset):
        """ Computes average dataset (mapping) """

        # If we have already integrated a full dataset, avg
        if dataset.reps > 1:
            current_index = len(dataset.data) - 1
            prev_dataset.data[current_index] = (
                prev_dataset.data[current_index] * (dataset.reps - 1)
                + dataset.data[-1]
            ) / (dataset.reps)
        else:
            prev_dataset.data = dataset.data

    def set_data(self, value):

        if self.data is None:
            self.reps = 1
            self.data = np.array([value])
        else:
            self.data = np.append(self.data, value)

        if len(self.data) > self.pts:
            self.update_hmap = True
            self.reps += 1

            try:
                reps_to_do = self.widgets['reps'].value()
                if reps_to_do > 0 and self.reps > reps_to_do:
                    self.stop = True
            except KeyError:
                pass

            if self.all_data is None:
                self.all_data = self.data[:-1]
            else:
                self.all_data = np.vstack((self.all_data, self.data[:-1]))
            self.data = np.array([self.data[-1]])

        self.set_children_data()

    def update(self, **kwargs):
        """ Updates current data to plot"""

        if self.data is not None and len(self.data) <= len(self.x):
            self.curve.setData(self.x[:len(self.data)], self.data)

        for child in self.children.values():
            child.update(update_hmap=copy.deepcopy(self.update_hmap))

        if self.update_hmap:
            self.update_hmap = False

    def hmap(self, dataset, prev_dataset):

        if dataset.update_hmap:
            prev_dataset.data = dataset.all_data


class HeatMap(Dataset):

    def visualize(self, graph, **kwargs):

        self.handle_new_window(graph, **kwargs)

        self.graph.show()
        self.graph.view.setAspectLocked(False)
        self.graph.view.invertY(False)
        self.graph.setPredefinedGradient('inferno')
        if set(['min', 'max', 'pts']).issubset(kwargs.keys()):
            self.min, self.max, self.pts = kwargs['min'], kwargs['max'], kwargs['pts']
            self.graph.view.setLimits(xMin=kwargs['min'], xMax=kwargs['max'])

    def update(self, **kwargs):

        if 'update_hmap' in kwargs and kwargs['update_hmap']:
            try:
                if hasattr(self, 'min'):
                    self.graph.setImage(
                        img=np.transpose(self.data),
                        autoRange=False,
                        scale=((self.max - self.min) / self.pts, 1),
                        pos=(self.min, 0)
                    )
                else:
                    self.graph.setImage(
                        img=np.transpose(self.data),
                        autoRange=False
                    )
            except:
                pass

    def save(self, filename=None, directory=None, date_dir=True):

        generic_save(
            data=self.data,
            filename=f'{filename}_{self.name}',
            directory=directory,
            date_dir=date_dir
        )
        if self.x is not None:
            generic_save(
                data=self.x,
                filename=f'{filename}_{self.name}_x',
                directory=directory,
                date_dir=date_dir
            )

        if hasattr(self, 'graph'):
            pyqtgraph_save(
                self.graph.getView(),
                f'{filename}_{self.name}',
                directory,
                date_dir
            )

        for child in self.children.values():
            child.save(filename, directory, date_dir)

        save_metadata(self.log, filename, directory, date_dir)

    def handle_new_window(self, graph, **kwargs):

        # If we want to use a separate window
        if 'window' in kwargs:

            # Check whether this window exists
            if not hasattr(self.gui, kwargs['window']):

                if 'window_title' in kwargs:
                    window_title = kwargs['window_title']
                else:
                    window_title = 'Graph Holder'
                setattr(
                    self.gui,
                    kwargs['window'],
                    GraphPopup(window_title=window_title)
                )

            self.graph = pg.ImageView(view=pg.PlotItem())
            getattr(self.gui, kwargs['window']).graph_layout.addWidget(
                self.graph
            )

        # Otherwise, add a graph to the main layout
        else:
            self.graph = pg.ImageView(view=pg.PlotItem())
            self.gui.graph_layout.addWidget(self.graph)

    def clear_data(self):

        # Reset Heatmap with zeros
        self.graph.setImage(
            img=np.transpose(np.zeros((10, 10))),
            autoRange=False
        )

        self.data = None


class LockedCavityScan1D(TriangleScan1D):

    def __init__(self, *args, **kwargs):

        self.t0 = time.time()
        self.v = None
        self.sasha_aom = None
        self.toptica_aom = None

        super().__init__(*args, **kwargs)

    def fill_params(self, config):

        super().fill_params(config)

        if not self.backward:
            self.add_child(
                name='Cavity lock',
                data_type=Dataset,
                window='lock_monitor',
                window_title='Cavity lock monitor',
                color_index=3
            )
            self.add_child(
                name='Cavity history',
                data_type=InfiniteRollingLine,
                data_length=10000,
                window='lock_monitor',
                color_index=4
            ),
            self.add_child(
                name='Max count history',
                data_type=InfiniteRollingLine,
                data_length=10000,
                window='lock_monitor',
                color_index=5
            )
            # self.add_params_to_gui(
            #     voltage=0.0
            # )

    def set_v_and_counts(self, v, counts):
        """ Updates voltage and counts"""

        self.v = v
        # self.widgets['voltage'].setValue(self.v)
        self.children['Cavity history'].set_data(self.v)
        self.children['Max count history'].set_data(counts)

    def clear_data(self):

        # Clear forward/backward scan line
        self.curve.setData([])
        self.data = None

        # Clear retasined data used in heatmaps
        self.all_data = None


class LockedCavityPreselectedHistogram(PreselectedHistogram):

    def __init__(self, *args, **kwargs):

        self.t0 = time.time()
        self.v = None
        self.sasha_aom = None
        self.toptica_aom = None
        self.snspd_7 = None
        self.snspd_8 = None

        super().__init__(*args, **kwargs)

    def fill_parameters(self, params):

        super().fill_parameters(params)
        self.add_child(
            name='Cavity lock',
            data_type=Dataset,
            window='lock_monitor',
            window_title='Cavity lock monitor',
            color_index=3
        )
        self.add_child(
            name='Cavity history',
            data_type=InfiniteRollingLine,
            data_length=10000,
            window='lock_monitor',
            color_index=4
        ),
        self.add_child(
            name='Max count history',
            data_type=InfiniteRollingLine,
            data_length=10000,
            window='lock_monitor',
            color_index=5
        ),
        self.add_child(
            name='Single photons',
            data_type=AveragedHistogram,
            window='photon',
            window_title='Single-photon data'
        )

    def set_v_and_counts(self, v, counts):
        """ Updates voltage and counts"""

        self.v = v
        # self.widgets['voltage'].setValue(self.v)
        self.children['Cavity history'].set_data(self.v)
        self.children['Max count history'].set_data(counts)


class ErrorBarGraph(Dataset):

    def visualize(self, graph, **kwargs):
        """ Prepare data visualization on GUI
        :param graph: (pg.PlotWidget) graph to use
        """

        self.error = None
        self.handle_new_window(graph, **kwargs)

        if 'color_index' in kwargs:
            color_index = kwargs['color_index']
        else:
            if 'window' in kwargs:
                color_index = self.gui.windows[kwargs['window']].graph_layout.count() - 1
            else:
                color_index = self.gui.graph_layout.count() - 1
        self.curve = pg.BarGraphItem(x=[0], height=[0], brush=pg.mkBrush(self.gui.COLOR_LIST[color_index]), width=0.5)
        self.error_curve = pg.ErrorBarItem(pen=None, symbol='o', beam=0.5)
        self.graph.addItem(self.curve)
        self.graph.addItem(self.error_curve)
        self.update(**kwargs)

    def update(self, **kwargs):
        """ Updates current data to plot"""

        if self.data is not None:
            if self.x is not None:
                try:
                    width = (self.x[1] - self.x[0]) / 2
                except IndexError:
                    width = 0.5
                self.curve.setOpts(x=self.x, height=self.data, width=width)
            else:
                self.x = np.arange(0, len(self.data))
                self.curve.setOpts(x=self.x, height=self.data, width=0.5)

        if self.error is not None:
            if self.x is not None:
                try:
                    width = (self.x[1] - self.x[0]) / 2
                except IndexError:
                    width = 0.5
                self.error_curve.setData(x=self.x, y=self.data, height=self.error, beam=width)
            else:
                self.error_curve.setData(y=self.data, height=self.error, beam=0.5)

        for child in self.children.values():
            child.update(**kwargs)


class ErrorBarPlot(Dataset):

    def visualize(self, graph, **kwargs):
        """ Prepare data visualization on GUI

        :param graph: (pg.PlotWidget) graph to use
        """

        self.error = None
        self.handle_new_window(graph, **kwargs)

        if 'color_index' in kwargs:
            color_index = kwargs['color_index']
        else:
            color_index = self.gui.graph_layout.count() - 1
        self.curve = pg.ErrorBarItem(pen=pg.mkPen(self.gui.COLOR_LIST[color_index]), symbol='o')
        self.graph.addItem(self.curve)
        self.update(**kwargs)

    def update(self, **kwargs):
        """ Updates current data to plot"""

        if self.data is not None and self.error is not None:
            if self.x is not None:
                try:
                    width = (self.x[1] - self.x[0]) / 2
                except IndexError:
                    width = 0.5
                self.curve.setData(x=self.x, y=self.data, height=self.error, beam=width)
            else:
                self.curve.setData(x=np.arange(len(self.data)), y=self.data, height=self.error, beam=0.5)

        for child in self.children.values():
            child.update(**kwargs)


# class PhotonErrorBarPlot(ErrorBarPlot):
    # un_normalized = np.array([])
    # total_events = 0
    # reps=0

    # def visualize(self, graph, **kwargs):

    #     super().visualize(graph, **kwargs)
    #     self.add_child(
    #         name='Photon probabilities, log scale',
    #         mapping=passthru,
    #         data_type=Dataset,
    #         window=kwargs['window']
    #     )
    #     self.children['Photon probabilities, log scale'].graph.getPlotItem().setLogMode(False, True)


class PhotonErrorBarPlot(ErrorBarGraph):
    un_normalized = np.array([])
    normalized = np.array([])
    total_events = 0
    reps = 0

    def visualize(self, graph, **kwargs):
        super().visualize(graph, **kwargs)
        self.add_child(
            name='Photon probabilities, log scale',
            mapping=passthru,
            data_type=Dataset,
            window=kwargs['window']
        )
        self.children['Photon probabilities, log scale'].graph.getPlotItem().setLogMode(False, True)


class InterpolatedMap(Dataset):
    """ Stores a dictionary of 2-tuple coordinates associated with a scalar
    value (e.g. fidelity). When a new datapoint is added, the value at that
    point is updated by averaging with the previous data at that location.
    Plots an interpolated 2D map in a Matplotlib Widget of the acquired datapoints. """

    def __init__(self, *args, **kwargs):
        kwargs['name'] = 'InterpolatedMap'
        super().__init__(*args, **kwargs)

        # Requires SciPy >=1.7.0
        try:
            from scipy.interpolate import RBFInterpolator
        except ImportError as e:
            self.log.warn("This import requires SciPy >=1.7.0.")
            raise(e)

    def set_data(self, data):
        """ Updates data stored in the data dict.

        Datapoints should be in the form ((x, y), z) where (x, y) are
        the coordinate positions and z is the value to be plotted.
        (x, y) are the keys and z is the value in the dict.
        """
        coords, fidelity = data

        # Initialize the data dict
        if self.data is None:
            self.data = {}

        # Place the data into the dictionary, updating the average if already present
        if coords not in self.data:
            self.data[coords] = (1, fidelity)
        else:
            old_N, old_avg = self.data[coords]
            self.data[coords] = (old_N + 1, (old_N * old_avg + fidelity) / (old_N + 1))

    def visualize(self, graph, **kwargs):
        self.handle_new_window(graph, **kwargs)
        self.update(**kwargs)

    def update(self, **kwargs):
        """ Updates current data to plot"""

        # Can't interpolate with too few points
        if self.data is None or len(self.data) < 3:
            return

        # TODO: HELP - how to make this plot update less often??
        import time
        if (int(time.time()) % 5) != 0:
            return

        fig = self.graph.getFigure()
        fig.clf() # Clear figure
        ax = fig.gca()

        # Ignore the first field (# of datapoints at that coord)
        obs_dict = {key: val[1] for key, val in self.data.items()}
        # Extract datapoints as arrays
        coords, fidelities = zip(*obs_dict.items())
        coords = np.array(coords)

        # Compute plotting bounds
        xlims = min(coords[:, 0]), max(coords[:, 0])
        ylims = min(coords[:, 1]), max(coords[:, 1])

        # Create grid for plotting region, imaginary number is part of mgrid() syntax
        n_points = 50
        xgrid = np.mgrid[0.95 * xlims[0]:1.05 * xlims[1]:n_points * 1j, 0.95 * ylims[0]:1.05 * ylims[1]:n_points * 1j]

        # Flatten grid, apply the interpolator to this flattened grid, reshape back to grid
        xflat = xgrid.reshape(2, -1).T
        yflat = RBFInterpolator(coords, fidelities)(xflat)
        ygrid = yflat.reshape(n_points, n_points)

        # Plot interpolated color mesh
        ax.pcolormesh(*xgrid, ygrid, vmin=0.85, vmax=1.0)

        # Plot scatter points
        scatterplot = ax.scatter(*coords.T, c=fidelities, s=50, ec='k', vmin=0.85, vmax=1.0)
        fig.colorbar(scatterplot)

        self.graph.draw()

    def handle_new_window(self, graph, **kwargs):
        """ Handles visualizing and possibility of new popup windows.
        Creates a Matplotlib widget instead of a Pyqtgraph widget. """

        if graph is None:
            # If we want to use a separate window
            if 'window' in kwargs:
                # Check whether this window exists
                if not kwargs['window'] in self.gui.windows:
                    if 'window_title' in kwargs:
                        window_title = kwargs['window_title']
                    else:
                        window_title = 'Graph Holder'

                    self.gui.windows[kwargs['window']] = GraphPopup(
                        window_title=window_title, size=(700, 300)
                    )

                self.graph = MatplotlibWidget()

                self.gui.windows[kwargs['window']].graph_layout.addWidget(
                    self.graph
                )

            # Otherwise, add a graph to the main layout
            else:
                self.graph = self.gui.add_graph()
        # Reuse a PlotWidget if provided
        else:
            self.graph = graph


# Useful mappings

def moving_average(dataset, prev_dataset=None):
    n = 20
    ret = np.cumsum(dataset.data)
    ret[n:] = ret[n:] - ret[:-n]
    prev_dataset.set_data(data=ret[n - 1:] / n)


def passthru(dataset, prev_dataset):
    prev_dataset.set_data(x=dataset.x, data=dataset.data)
