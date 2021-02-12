import numpy as np
import socket
import time

from pylabnet.gui.pyqt.external_gui import Window
from pylabnet.utils.logging.logger import LogHandler
import pyqtgraph as pg
from pylabnet.utils.helper_methods import generate_widgets, unpack_launcher, find_client, load_config, get_gui_widgets, load_script_config
from pylabnet.network.client_server import thorlabs_mpc320, thorlabs_pm320e


class Controller:

""" A script class for controlling mpc320 polarization paddles + thorlabs_pm320 power meter + interfacing with GUI"""
    
    RANGE_LIST = [
        'AUTO', 'R1NW', 'R10NW', 'R100NW', 'R1UW', 'R10UW', 'R100UW', 'R1MW',
        'R10MW', 'R100MW', 'R1W', 'R10W', 'R100W', 'R1KW'
    ]

    #NUM_PADDLES = 9
    #WIDGET_DICT = dict(
    #    home=NUM_CHANNELS, move_rel=NUM_CHANNELS, move_to=NUM_CHANNELS,
    #    optimize=NUM_CHANNELS, get_power=NUM_CHANNELS, velocity=NUM_CHANNELS,
    #    step_num = NUM_CHANNELS, converge_parameter = NUM_CHANNELS
    #)

    def __init__(self, paddles_client, pm_client, gui='pol_paddles', logger=None, calibration=None, name=None, port=None):
        """ Instantiates the controller for one pol paddles device with 3 paddles with GUI

        :param pm_clients: (client, list of clients) clients of polorization paddles
        :param gui_client: client of monitor GUI
        :param logger: instance of LogClient
        :calibration: (float) Calibration value for power meter.
        :name: (str) Humand-readable name of the power meter.
        """

        self.pol = paddles_client
        self.paddles = [0,1,2]
        self.pm = pm_client
        self.log = LogHandler(logger=log_client)
        self.gui = Window(
            gui_template=gui,
            host=socket.gethostbyname(socket.gethostname()),
            port=port

        self.gui.apply_stylesheet()

        # add some defenitions

        # Get all GUI widgets
        self.widgets = get_gui_widgets(
            self.gui,
            graph_widget= 4,   #was num_plots in power_monitor
            spin_box= 14,
            name_label= 11,
            combo_widget = 2           #choose paddle
        )

        self._initialize_gui()
    

    def sync_settings(self):

        """ Pulls current settings from PM and pol paddles and sets them to GUI """

        # Configure wavelength of power meter
        self.wavelength = self.pm.get_wavelength(1)
        self.widgets['number_widget'][-1].setValue(
            self.wavelength
        )

        # Configure Range to be Auto
        self.pm.set_range(1, self.RANGE_LIST[0])
        self.pm.set_range(2, self.RANGE_LIST[0])
        self.ir_index = 0
        self.rr_index = 0

        #configure velocity of polariation paddles
        self.velocity = self.pol.get_velocity(1)
        self.widgets['spin_box'][6].setValue(
            self.velocity
        )

        # Connect wavelength change action.
        self.widgets['number_widget'][-1].valueChanged.connect(self._update_wavelength)

        # Connect range change.
        self.widgets['combo_widget'][0].currentIndexChanged.connect(lambda: self._update_range(0))
        self.widgets['combo_widget'][1].currentIndexChanged.connect(lambda: self._update_range(1))

        #connect velocity pol paddles
        self.widgets['number_widget'][???].valueChanged.connect(self._update_velocity)


        # Configure angle of paddles in GUI (do we want this or onlygraphic?)
        for paddle in self.paddles
            self.angle = self.pol.get_angle(paddle)
            self.widgets['number_widget'][-1].setValue(
            self.angle
        )

    def _update_wavelength(self):
        """ Updates velovity of pm to WL of GUI"""

        gui_wl = self.widgets['number_widget'][-1].value()

        if self.wavelength != gui_wl:
            self.wavelength = gui_wl
            self.pm.set_wavelength(1, self.wavelength)
            self.pm.set_wavelength(2, self.wavelength)

    def _update_range(self, channel):
        """ Update range settings if combobox has been changed."""

        range_index = self.widgets['combo_widget'][channel].currentIndex()

        if channel == 0:
        if self.ir_index != range_index:
                self.ir_index = range_index
                self.pm.set_range(1, self.RANGE_LIST[self.ir_index])
        elif channel == 1:
             if self.rr_index != range_index:
                self.rr_index = range_index
                self.pm.set_range(2, self.RANGE_LIST[self.rr_index])

    def _update_velocity(self):
        """ Update velocity settings if number widget has been changed."""

        gui_velocity = self.widgets['number_widget'][-1].value()

        if self.velocity != gui_velocity:
            self.velocity = gui_velocity
            self.pol.set_velocity(1, self.velocity)
            self.pol.set_velocity(2, self.velocity)

    #faster option.shorter:
    def initialize_parameters(self, velocity, channel, p_range):
        #Initializes parameters such as wavelength for power meter, velocity for paddles

        self.pol.set_velocity(velocity) 
        self.pm.set_range(channel, p_range)
       
        #Understand graphics:
            # Update GUI
            for plot_no in range(self.num_plots):
                # Update Number
                self.widgets['number_widget'][plot_no].setValue(formatted_values[plot_no])

                # Update Curve
                self.plotdata[plot_no] = np.append(self.plotdata[plot_no][1:], values[plot_no])
                self.widgets[f'curve_{plot_no}'].setData(self.plotdata[plot_no])

                if plot_no < 2:
                    self.widgets["label_widget"][plot_no].setText(f'{value_prefixes[plot_no]}W')

    def _initialize_gui(self):
        """ Instantiates GUI by assigning widgets """

        # Store plot data
        self.plotdata =[np.zeros(1000) for i in range(self.num_plots)]

        for plot_no in range(self.num_plots):
           # Create a curve and store the widget in our dictionary
            self.widgets[f'curve_{plot_no}'] = self.widgets['graph_widget'][plot_no].plot(
                pen=pg.mkPen(color=self.gui.COLOR_LIST[0])

    def _setup_gui(self):
        """ Configures what all buttons do """
        
        for paddle in self.paddles:

            # Mote_to buttons
            self.widgets['move_to'][paddle].pressed.connect(
                lambda channel=channel_no: self._move_rel(paddale)
            )
        # Technical methods
       """ Sets the pos on the GUI to the current value measured by the controller
        :param paddle: (int) paddle index (from 0)"""

    def _home(self, paddle)

        self.pol.home(self, paddle, sleep_time)
    
    def _move_rel(self, paddle_num, step, sleep_time):
        self.pol.move_rel(self, paddle, step, sleep_time)
        self.widgets['move_to'][paddle].setValue(step)
        self.widgets['move_to'][paddle].setStyleSheet(
                'background-color:black'

    def _move(self, paddle_num):
        self.pol.move_rel(self, paddle, step_to, sleep_time)
        self.widgets['move_to'][paddle].setValue(step_to_to)
        self.widgets['move_to'][paddle].setStyleSheet(
                'background-color:black'

    def _show_pos(self,paddle)
     """ Sets the pos on the GUI to the current value measured by the controller
     :param paddle: (int) paddle index (from 0)"""

        pos = self.pol.get_angle(paddle)      
        self.widgets['angle'][paddle].setValue(pos)

    def _optimize(self, paddle, iteration_num, step_num, converge_parameter, sleep_time, channel):
        """ Optimize code for paddles - finding optimize angle for each paddle """
        
        count = 0
        iter_count = 0  #initialized to zero and gro as step in angles as taken in an single iteration
        ang = [] 
        angle = []
        power = []
        pos = []
        ang_paddles = []
        power_paddles = []

        for paddle in self.paddles:
            deviate = 170 #range of angle to scan
            step_size = deviate/step_num
            move_in = self.move_rel(paddle, -deviate/2, sleep_time)
            while iter_count < iteration_num:
                if iter_count >= 1:
                    move = self.move(paddle, ang[iter_count-1]-deviate/2, sleep_time)
                while count < step_num:
                    mover = self.move_rel(paddle, step_size, sleep_time)
                    PosF = self.show_pos(paddle)
                    current_power = self.get_power(channel)
                    power.extend([current_power])
                    angle.extend([PosF])
                    count += 1
                plt.figure((paddle+1)*iteration_num)
                plt.title(f"paddle # {paddle} , iteration # {iter_count}.")
                plt.plot(angle, power, "or")
                max_index = np.argmax(power)
                ang.extend([angle[max_index]]) 
        if iter_count >= 1:
            if abs(ang[iter_count] - ang[iter_count-1]) < converge_parameter:
                self.widgets['optimization converged'][paddle].setChecked(True)
                move = self.move(paddle, angle[max_index], sleep_time)
                count = 0
                iter_count = 0
                power = []
                angle = []
                break

            deviate = deviate/2
            step_size = deviate/step_num
            iter_count += 1
            count = 0

        ang_paddles.extend(ang)
        power_paddles.extend(power)
        ang = []
        iter_count = 0

 

class polInterface:

    def __init__(self, client, config:dict=None):


class PMInterface:
    """
    Interface class to allow other modules to be called in same
    way as a Thorlabs power meter

    Currently supports NI AI with power calibration curve via config
    power (uW) = m*(x-z) + b
    """

    def __init__(self, client, config:dict=None):

        self.client = client
        self.config = config
    
        if isinstance(self.client, thorlabs_pm320e.Client):
            self.type = 'thorlabs_pm320e'
        else:
            self.type = 'nidaqmx'
            self.channels = [
                self.config['input']['channel'],
                self.config['reflection']['channel']
            ]
            self.m = [
                self.config['input']['m'],
                self.config['reflection']['m']
            ]
            self.b = [
                self.config['input']['b'],
                self.config['reflection']['b']
            ]
            self.z = [
                self.config['input']['z'],
                self.config['reflection']['z']
            ]

    def get_power(self, channel):

        if self.type == 'thorlabs_pm320e':
            return self.client.get_power(channel)
        else:
            index = channel - 1
            return ((self.m[index]
                     * (self.client.get_ai_voltage(self.channels[index])[0]
                        -self.z[index]))
                    + self.b[index])*1e-6

    def get_wavelength(self, channel):
        if self.type == 'thorlabs_pm320e':
            return self.client.get_wavelength(channel)
        else:
            return 737

    def get_range(self, channel):
        if self.type == 'thorlabs_pm320e':
            return self.client.get_range(channel)
        else:
            return 'AUTO'

    def set_wavelength(self, channel, wavelength):
        if self.type == 'thorlabs_pm320e':
            return self.client.set_wavelength(channel, wavelength)
        else:
            return

    def set_range(self, channel, p_range):
        if self.type == 'thorlabs_pm320e':
            return self.client.set_range(channel, p_range)
        else:
            return


def launch(**kwargs):
    """ Launches the full nanopositioner control + GUI script """

    # Unpack and assign parameters
    logger = kwargs['logger']
    clients = kwargs['clients']
    config = load_script_config(script='pol_paddle_control',
                        config=kwargs['config'],
                        logger=logger)
    pol_client = find_client(clients=clients, settings=config, client_type='MPC320')  #what is client type?
    pm_client = find_client(clients=clients, settings=config, client_type='PM320e')  #what is client type?
    gui_client = 'pol_paddles'

    # Instantiate controller
    control = Controller(pol_client, pm_client, gui_client, logger, config=kwargs['config'], port=kwargs['server_port'])

    # Initialize parameters
    for paddle_index in range(control.NUM_CHANNELS):
        params = control.get_GUI_parameters(paddle_index)
        control.initialize_parameters(paddle_index, params)

    try:
        control.load_settings()
    except Exception as e:
        logger.warn(e)
        logger.warn('Failed to load settings from config file')

    control.gui.app.exec_()

    # Mitigate warnings about unused variables
    if loghost and logport and params:
        pass