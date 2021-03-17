import numpy as np
import socket
import time

from pylabnet.gui.pyqt.external_gui import Window
from pylabnet.utils.logging.logger import LogHandler
import pyqtgraph as pg
import pyqtgraph as PlotWidget   #, plot  #check what's plot here
from pylabnet.utils.helper_methods import generate_widgets, unpack_launcher, find_client, load_config, get_gui_widgets, load_script_config
from pylabnet.network.client_server import thorlabs_mpc320, thorlabs_pm320e
from pylabnet.scripts.fiber_coupling.power_monitor import PMInterface as PM_Interface

 
class Controller:

    """ A script class for controlling mpc320 polarization paddles + thorlabs_pm320 power meter + interfacing with GUI"""
    
    RANGE_LIST = [
        'AUTO', 'R1NW', 'R10NW', 'R100NW', 'R1UW', 'R10UW', 'R100UW', 'R1MW',
        'R10MW', 'R100MW', 'R1W', 'R10W', 'R100W', 'R1KW'
    ]


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
        self.num_plots = 4
        self.ir_index, self.rr_index = [], []  ##what?
        self.running = False


        self.gui = Window(
            gui_template=gui,
            host=socket.gethostbyname(socket.gethostname()),
            port=port
        )
        self.gui.apply_stylesheet()

        # add some defenitions

        # Get all GUI widgets
        self.widgets = get_gui_widgets(
            self.gui,
            graph_widget= self.num_plots,   
            velocity = 1,
            wavelength = 1, #for power meter
            angle_steps = 1, #number of angles to scan for optimization precedure
            iterations = 1, #number of iterations for optimization precedure
            converge_parameter = 1, #for optimization precedure
            optimize_all = 1, #runs the code to optimize the power.
            #name_label= 11,
            combo_widget = 4, # 1- paddle (pol paddles), 2- channel (PM), 3 - range input (PM)  range reflected (PM)
            move_to = 3,  #Movement to position. one for each paddle
            step_by = 3,  #Relative movement. one for each paddle
            move_pos = 3, #spin_box type. defines step of movement relative of paddle. One for each paddle
            step_size = 3, #spin_box type. defines step of movement relative of paddle. One for each paddle
            around_angle = 3,  #spin_box type. defines around what angle to optimize the spefici paddle. One for each paddle
            optimize_around = 3, #push button type. Optimizes around a specific angle a specific paddle.
            home = 3,    #push butto. Homes paddles - moves paddle to center angle. One for each paddle
            text_edit = 3, #text edit with angle of paddle. One for each paddle
            get_angle = 3
        )

        self._initialize_gui()
    

    def initialize_parameters(self, channel, params):
        #sets devices to gui parameters
        
        """ Updates wavelength, range of pm and velocity of pol paddle by values set in GUI"""  
        self.pm.set_wavelength(1, params[3])
        self.pm.set_wavelength(2,  params[3])

        if channel == 0:
            if self.ir_index != params[0]:
                self.ir_index = params[0]
                self.pm.set_range(1, self.RANGE_LIST[self.ir_index])
        elif channel == 1:
             if self.rr_index !=  params[1]:
                self.rr_index =  params[1]
                self.pm.set_range(2, self.RANGE_LIST[self.rr_index])

    def _update_velocity(self, params):
        """ Update velocity settings if comboox has been changed."""
        self.pol.set_velocity(params[2])

    def get_GUI_parameters(self):
        #initialize parameters fom Gui widget to be later send to device
        for paddle in self.paddles:
            self.gui_around[paddle] = self.widgets['around_angle'][paddle].value()
            self.gui_pos[paddle] = self.widgets['move_pos'][paddle].value()
            self.gui_step[paddle] = self.widgets['step_size'][paddle].value()

        return(
            self.widgets['combo_widget'][3].currentIndex(), #range_index_i
            self.widgets['combo_widget'][4].currentIndex(), #range_index_r = 
            self.widgets['velocity'].value(), #gui_velocity 
            self.widgets['wavelength'].value(), #gui_wavelength  
            self.widgets['angle_steps'].value(), # gui_angle_steps 
            self.widgets['iterations'].value(), #gui_iterations  
            self.widgets['converge_parameter'].value(), #gui_converge_parameter  
            self.widgets['sleep_time'].value(), #gui_sleep_time =
            self.gui_around,
            self.gui_pos,
            self.gui_step,
        )

        # Update GUI
        for plot_no in range(self.num_plots): # Update Number
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
            )

    def _setup_gui(self, params):
        """ Configures what all buttons do """
        
        for paddle in self.paddles:

            # Mote buttons
            self.widgets['move_to'][paddle].pressed.connect(
                self._move(paddle, params) #get step and sleep_time 
            )

            self.widgets['step_by'][paddle].pressed.connect(
                self._move_rel(paddle, params) 
             ) #get step and sleep_time # self.gui_step, self.gui_sleep_time
            

            self.widgets['home'][paddle].pressed.connect(self._home(paddle)) #get step and sleep_time

            self.widgets['get angle'][paddle].pressed.connect(self._show_pos(paddle))

            #add optimize around

        self.widgets['optimize_all'].pressed.connect(self._optimize()
        ) #gept step and sleep_time

        #parameters that need to be updated in PM or pol paddles
        self.widgets['wavelength'].valueChanged.connect(self._update_wavelength)
        self.widgets['combo_widget'][3].currentIndexChanged.connect(lambda: self._update_range(0)) #why did we have two in poer_monitor
        self.widgets['combo_widget'][4].currentIndexChanged.connect(lambda: self._update_range(1)) #why did we have two in poer_monitor
        self.widgets['velocity'].currentIndexChanged.connect(self._update_velocity)

        # Technical methods
        """ Functions for devices actions in relation to widget paddle index (from 0)"""

    def _home(self, paddle):
        self.pol.home(self, paddle)

    def _move_rel(self, paddle, params):
        self.pol.move_rel(self, paddle, params[14+paddle], params[7])   #get step and sleep_time # self.gui_step, self.gui_sleep_tim
        self.widgets['step_size'][paddle].setValue(params[14+paddle])
        
    def _move(self, paddle, params):
        self.pol.move(self, paddle, params[11+paddle], params[7])# params11+paddle] = self.gui_pos, params [7] = self.gui_sleep_time
        self.widgets['move_pos'][paddle].setValue(params[11+paddle]) 

    def _get_power(self,channel):
        power = self.pm.get_power(channel)
        return power

        #can add a check that movement worked

    def _show_pos(self,paddle):
        pos = self.pol.get_angle(paddle)      
        self.widgets['text_edit'][paddle].setValue(pos)
        return pos

    def run(self):
        # Continuously update data until paused
        self.running = True

        while self.running:
            self._update_pm_output()
            self.gui.force_update()

    def _update_pm_output(self):
        """ Runs the power monitor """

        # Check for/implement changes to settings
        #self.update_settings(0)

        # Get all current values
        try:
            p_in = self.pm.get_power(1)
            split_in = split(p_in)

        # Handle zero error
        except OverflowError:
            p_in = 0
            split_in = (0, 0)
        try:
            p_ref = self.pm.get_power(2)
            split_ref = split(p_ref)
        except OverflowError:
            p_ref = 0
            split_ref = (0, 0)
        try:
            efficiency = np.sqrt(p_ref/(p_in*self.calibration[0]))
        except ZeroDivisionError:
            efficiency = 0
        values = [p_in, p_ref, efficiency]

        # For the two power readings, reformat.
        # E.g., split(0.003) will return (3, -3)
        # And prefix(-3) will return 'm'
        formatted_values = [split_in[0], split_ref[0], efficiency]
        value_prefixes =  [prefix(split_val[1]) for split_val in [split_in, split_ref]]
        #plot efficiency in GUI

        self.widgets['graph_widget'][4].plot(angle, values[3], symbol = 'o', color = 'b' ) 


    def _optimize(self, params):
        """ Optimize code for paddles - finding optimize angles for all paddle """
        
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
            step_size = deviate/params[4]  #angle_step
            params[14+paddle] = -deviate/2  #self.gui_step  #
            self._move_rel(paddle, params)
            while iter_count < params[5]: #self.gui_iterations:
                if iter_count >= 1:
                    params[11+paddle] = ang[iter_count-1]-deviate/2   # self.gui_pos[paddle] = gui_iterations
                    self._move(paddle, params)
                while count < params[4]:  #self.gui_angle_steps:
                    params[14+paddle] = step_size  #self.gui_step
                    self._move_rel(paddle, params)
                    PosF = self._show_pos(paddle)
                    current_power = self._get_power(channel)
                    power.extend([current_power])
                    angle.extend([PosF])
                    count += 1
                #plt.figure((paddle+1)*self.gui_iterations)
                self.widgets['graph_widget'][paddle+1].setTitle(f"paddle # {paddle} , iteration # {iter_count}.")
                self.widgets['graph_widget'][paddle+1].plot(angle, power, symbol = 'o', color = 'r' ) 
                max_index = np.argmax(power)
                ang.extend([angle[max_index]]) 
                if iter_count >= 1:
                    if abs(ang[iter_count] - ang[iter_count-1]) < params[6]: #self.gui_converge_parameter:
                        self.widgets['optimization converged'][paddle].setChecked(True)    #add this in ui file
                        params[11+paddle] = angle[max_index]
                        self.move(paddle,params)
                        count = 0
                        iter_count = 0
                        power = []
                        angle = []
                        break

                deviate = deviate/2
                step_size = deviate/params[5]  #self.gui_iterations
                iter_count += 1
                count = 0

            ang_paddles.extend(ang)
            power_paddles.extend(power)
            ang = []
            iter_count = 0

 
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
    settings = load_script_config(   #relevanf for pm_interface to interface other devices rather than only Thorlabs power meter.
    'power_monitor',
    kwargs['config'],
    logger=logger
    )
    pm = PMInterface(pm_client, settings)

    # Instantiate controller
    control = Controller(pol_client, pm_client, gui_client, logger, config=kwargs['config'], port=kwargs['server_port'])

    # Initialize parameters
    params = control.get_GUI_parameters()
    control.initialize_parameters(channel,params)
    control._setup_gui(params)
    control.run()

    try:
        control.load_settings()
    except Exception as e:
        logger.warn(e)
        logger.warn('Failed to load settings from config file')

    control.gui.app.exec_()

    # Mitigate warnings about unused variables
    if loghost and logport and params:
        pass