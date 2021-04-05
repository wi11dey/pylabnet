import re
import numpy as np
from pylabnet.utils.pulseblock.pb_sample import pb_sample, pulse_sample
from pylabnet.utils.pulseblock.placeholder import Placeholder
from pylabnet.utils.pulseblock.pulse import PCombined


# Sampling rate of HDWAG sequencer (300 MHz).
DIG_SAMP_RATE = 300e6
# Sampling rate of HDWAG Analog output (2.4 GHz max).
ANA_SAMP_RATE = 2.4e9

# Duration of setDIO() commands to be used as offset in wait() commands.
SETDIO_OFFSET = 4


class AWGPulseBlockHandler():

    def __init__(self, pb, assignment_dict=None, exp_config_dict=None,
                 dig_samp_rate=DIG_SAMP_RATE, ana_samp_rate=ANA_SAMP_RATE,
                 hd=None, end_low=True):
        """ Initializes the pulse block handler for the ZI HDAWG.

        :hd: (object) An instance of the zi_hdawg.Driver()
        :pb: (object) An instance of a pb.PulseBlock()
        :dig_samp_rate: (float) Sampling rate of HDAWG sequencer (300 MHz)
        :ana_samp_rate: (float) Sampling rate of HDAWG analog output (2.4 GHz max)

        :assignment_dict: (dictionary) Dictionary mapping the channel names in the
            pulse block to DIO bits or analog channels. e.g.
            {
                "mw_gate" : ["dio", 0],
                "ctr" : ["dio", 1],
                "laser" : ["analog", 0],
            }

            The assignment dictionary can be incomplete,
            in which case the user will be asked to provide the
            missing values. If no assignment dictionary is
            provided, user is asked to provide all channel values.
        :exp_config_dict: (dict) Dictionary of any experiment configurations.
        :end_low: (bool) whether or not to force the sequence to end low
        """

        # Use the log client of the HDAWG.
        self.hd = hd
        self.log = hd.log

        # Store arguments.
        self.pb = pb

        # Handle end low case
        self.end_low = end_low

        self.digital_sr = dig_samp_rate
        self.analog_sr = ana_samp_rate
        self.exp_config_dict = exp_config_dict

        # Ask user for bit assignment if no dictionary provided.
        if assignment_dict is None:
            # Initiate empty dictionary
            self.assignment_dict = {}
            # Ask user to assign all channels
            self._ask_for_ch_assignment(self.pb.p_dict.keys())

        # Store assignment dict if provided.
        else:
            self.assignment_dict = assignment_dict
            # Check key value integrity of assignment dict.
            self._check_key_assignments()
        
        # Store remapped samples, number of samples and number of traces for the
        # digital channels.
        (self.digital_sample_dict,
         self.num_digital_samples,
         self.num_digital_traces) = self._get_remapped_digital_samples(samp_rate=dig_samp_rate)

        # List of DIO bits that are used by pulses in this pulseblock     
        self.used_dio_bits = list(self.digital_sample_dict.keys())

        # Stores a list of configs for each type of config (e.g. osc freq, DC offset)
        # Populated when we parse the Pulseblocks and then used when we setup the
        # AWG using the AWG API commands.
        self.setup_config_dict = dict()

    def _ask_for_ch_assignment(self, keys_to_assign):
        """Ask user to provide bit/channel number for trace

        :keys_to_assign: (np.array) Array of keys in pulseblock dictionary
            (trace names).
        """

        for trace_name in keys_to_assign:

            if trace_name.is_analog:
                ch_num = input(f"Please assign an analog channel (1-8) to pulse trace '{trace_name.name}':")

                # Check if user has entered a int.
                wrong_int_msg = "Please enter an integer from 1-8."
                try:
                    ch_num = int(ch_num)
                except ValueError:
                    self.log.error(wrong_int_msg)

                if ch_num not in range(1, 9):
                    self.log.error(wrong_int_msg)

            else:
                ch_num = input(f"Please assign a DIO bit (0-31) to pulse trace '{trace_name.name}':")

                # Check if user has entered a int.
                wrong_int_msg = "Please enter an integer from 0-31."
                try:
                    ch_num = int(ch_num)
                except ValueError:
                    self.log.error(wrong_int_msg)

                if ch_num not in range(32):
                    self.log.error(wrong_int_msg)

            # Check if channel is already assigned
            if ch_num in self.assignment_dict.values():
                self.log.error(f"DIO bit / Channel {ch_num} already in use.")

            # assignment_dict items are in the form (analog/digital, channel)
            self.assignment_dict[trace_name][0] = "analog" if trace_name.is_analog else "dio"
            self.assignment_dict[trace_name][1] = ch_num

    def _check_key_assignments(self):
        """Check if key values in assignment dict coincide with keys in pulseblock"""

        for pb_key in self.pb.p_dict.keys():
            if pb_key.name not in self.assignment_dict.keys():
                self.log.warn(
                    f"Key '{pb_key.name}' in pulseblock instance not found in assignment dictionary, please specify."
                )

                # Ask user to provide channel number for key.
                self._ask_for_ch_assignment([pb_key])

    def _get_remapped_digital_samples(self, samp_rate):
        """Transforms pulseblock object into dictionary of sample-wise defined digital waveforms.

        :samp_rate: (float) Sampling rate of HDAWG sequencer
        Returns dictionary with keys corresponding to DIO bit numbers and
        values to the desired digital waveform.
        """

        # Turn pulse block into sample dictionary
        sampled_digital_pb = pb_sample(self.pb, samp_rate=samp_rate)

        # Number of samples per pulse
        num_digital_samples = sampled_digital_pb[-2]
        traces = sampled_digital_pb[0]

        # Number of different traces
        num_digital_traces = len(traces)

        # Create dictionary with channel names replaced by DIO bit
        digital_sample_dict = {}
        for channel_name in traces.keys():
            if self.assignment_dict[channel_name][0] == "analog":
                self.log.warn(f"Attempted to map an analog channel {channel_name} using the functions for digital signals.")
                continue

            digital_sample_dict.update(
                # assignment_dict items are in the form (analog/digital, channel)
                {self.assignment_dict[channel_name][1]: traces[channel_name]}
            )

        return digital_sample_dict, num_digital_samples, num_digital_traces

    def gen_single_digital_codeword(self, sample_dict):
        """ Generate a single DIO codeword.

        :sample_dict: (dict) Keys: DIO bit numbers, values: bit indicating
        whether that DIO bit should be turned on.

        :return: codeword: (int) Integer representing the DIO value with a 1
        in each binary position where the DIO bit is on.
        """
        # Initial codeword: 00000 ... 0000
        codeword = 0b0
        dio_bits = sample_dict.keys()

        for dio_bit in dio_bits:
            sample_val = sample_dict[dio_bit]

            # If value is True, add 1 at dio_bit-th position
            if sample_val:
                # E.g., for DIO-bit 3: 0000 ... 0001000
                bitshifted_dio_bit = (0b1 << int(dio_bit))
                # Binary OR updates codeword.
                codeword |= bitshifted_dio_bit

        return codeword

    def gen_digital_codewords(self):
        """Generate array of DIO codewords.

        Given the remapped sample array, translate it into an
        array of DIO codewords, sample by sample.
        """

        # Array storing one codeword per sample.
        dio_codewords = np.zeros(self.num_digital_samples, dtype='int64')

        for sample_num in range(self.num_digital_samples):

            # Extract the sample at that time position for each channel
            sample_dict = {dio_bit: ch_samples[sample_num] for
                        dio_bit, ch_samples in self.digital_sample_dict.items()}

            codeword = self.gen_single_digital_codeword(sample_dict)

            # Store codeword.
            dio_codewords[sample_num] = codeword

        return dio_codewords

    def gen_analog_instructions(self, waveform_idx):
        """Generate the setup instructions for the analog channels and the
        waveforms to be transferred to the AWG.

        :param: waveform_idx (int): Indices assigned to waveforms from this
            pulseblock will start counting incrementing from this value.

        :return: setup_instr (str) representing the AWG instructions used to 
            set up the analog pulses.
        :return: waveforms: (list) of tuples(waveform var name, ch_name, 
            start_step, end_step, np.array waveform). Start/end are in AWG 
            time steps.
        :return: sweep_waveform: (tuple) of parameters for a waveform involved 
            in a sweep. None if none present. Parameters are (list of waveform
            variable names, list of waveform indices, pulse sweep type, 
            sweep min value, max value, number of sweep steps)
        """

        waveforms = []
        sweep_waveform = None
        setup_instr = ""

        # if len(self.pb.p_dict.keys()) > 2:
        #     self.log.error("Pulsemaster is currently only designed to handle 2 analog channels.")
        #     return

        analog_pulse_dict = {ch:pulse_list for (ch, pulse_list) in
                        self.pb.p_dict.items() if ch.is_analog}

        #### 1. Merge all nearby pulses within each single channel ####

        # p_dict: Keys - Channel object
        # Values - list of Pulse objects (e.g. PGaussian)
        for ch, pulse_list in analog_pulse_dict.items():

            # Default pulse function for that channel
            dflt_pulse = self.pb.dflt_dict[ch]

            # Keep checking until no merges found
            merge_found = True
            while merge_found:

                merge_found = False
                pulse_list.sort(key=lambda pulse: pulse.t0)

                # Iterate through all pulses but the last one
                for idx, pulse in enumerate(pulse_list[:-1]):

                    p1 = pulse_list[idx]
                    p2 = pulse_list[idx+1]

                    if (p1.t0 + p1.dur) > p2.t0:
                        self.log.error("Found overlapping pulses!")
                        return
                    # Merge pulses that are 16 AWG timesteps apart
                    # Pulses must be multiple of 16 samples = 2 timesteps
                    # wait(0) takes 3 timesteps which is the min AWG seq wait time
                    # Min separation is thus 3+2+2 = 7, we ~double it to get 16.
                    elif (p2.t0 - (p1.t0 + p1.dur)) <= 16 / DIG_SAMP_RATE:

                        # Don't merge if different settings
                        if (p1.mod != p2.mod or
                            p1.mod_freq != p2.mod_freq or
                            p1.mod_ph != p2.mod_ph):
                            continue

                        # Don't merge if any of them have variable times
                        if (type(p1.t0) == Placeholder or type(p2.t0) == Placeholder):
                            continue

                        # Merge and delete the constituents
                        if type(p1) == PCombined:
                            pulse_list.append(p1.merge(p2))
                        elif type(p2) == PCombined:
                            pulse_list.append(p2.merge(p1))
                        else:
                            pulse_list.append(PCombined([p1, p2], dflt_pulse))

                        del pulse_list[idx:idx+2]
                        # Go back to the start of the for loop to avoid looping
                        # over a modified list.
                        merge_found = True
                        break

        #### 2. Digitize all pulses within a single channel ####           

        for ch, pulse_list in analog_pulse_dict.items():
            dflt_pulse = self.pb.dflt_dict[ch]

            for pulse in pulse_list:

                # Temporarily disable modulation to get the digitized envelope
                # The digitization includes padding to reach a multiple of 16
                # and a minimum length of 32 samples.
                temp = pulse.mod
                pulse.mod = False
                samp_arr, n_pts, add_pts = pulse_sample(pulse, dflt_pulse,
                                    self.analog_sr, len_min=32, len_step=16)
                pulse.mod = temp

                 # Variable for the waveform in the code
                wave_var_name = f"{self.pb.name}_{ch.name}_{pulse.t0:.2}"

                # Remove illegal chars
                wave_var_name = re.sub("[-* ]", "", wave_var_name)
                wave_var_name = re.sub("[.+]", "_", wave_var_name)


                if wave_var_name in [wave[0] for wave in waveforms]:
                    self.log.error("Found two pulses at the same time in the same channel.")
                    return

                # Save the pulse start/end time and name, which we will use for
                # arranging by their times. Times are multipled by the DIO
                # rate to convert into AWG time steps.
                if type(pulse.t0) == Placeholder:
                    tstep_start = (pulse.t0 * self.digital_sr).round_val()
                else:
                    tstep_start = int(np.round(pulse.t0 * self.digital_sr))
                if type(pulse.t0 + pulse.dur) == Placeholder:
                    tstep_end = ((pulse.t0 + pulse.dur) * self.digital_sr).round_val()
                else:
                    tstep_end = int(np.round((pulse.t0 + pulse.dur) *  self.digital_sr))

                waveforms.append([wave_var_name,
                                ch.name,
                                tstep_start,
                                tstep_end,
                                waveform_idx,
                                samp_arr])

                # Declare the waveform in the AWG code with a placeholder
                setup_instr += f'wave {wave_var_name} = placeholder({len(samp_arr)});\n'
                setup_instr += f'assignWaveIndex({wave_var_name}, {waveform_idx});\n'
                waveform_idx += 1  

                # Check if the current pulse is involved in a sweep
                # If so, we need to assign an additional wave index for the 
                # swept pulse since we need to specify its channel number.
                if "sweep" in pulse.params and pulse.params["sweep"]:

                    # Only need to specify once for an IQ pair
                    if ch.name.endswith("_i"):
                        pass
                    elif ch.name.endswith("_q"):
                        ch_num_q = self.assignment_dict[ch.name][1]
                        ch_num_i = self.assignment_dict[ch.name[:-2] + "_i"][1]
                        assert("_q_" in wave_var_name)
                        wave_var_name_i = wave_var_name.replace("_q_", "_i_")
            
                        setup_instr += f'assignWaveIndex({ch_num_i}, {wave_var_name_i}, {ch_num_q}, {wave_var_name}, {waveform_idx});\n'
                        
                        if sweep_waveform is not None:
                            self.log.error("Detected >1 sweep waveforms! "
                                           "Can only have 1 sweep waveform!")
                            return
                        sweep_waveform = ([wave_var_name_i, wave_var_name],
                                          [waveform_idx], 
                                          pulse.params["sweep_type"],
                                          pulse.params["sweep_min"],
                                          pulse.params["sweep_max"],
                                          pulse.params["sweep_steps"]) 
                        waveform_idx += 1  

                    # For a normal sweep pulse that only has 1 channel        
                    else:
                        ch_num = self.assignment_dict[ch.name][1]
                        setup_instr += f'assignWaveIndex({ch_num}, {wave_var_name}, {waveform_idx});\n'
                        
                        if sweep_waveform is not None:
                            self.log.error("Detected >1 sweep waveforms! "
                                           "Can only have 1 sweep waveform!")
                            return
                        sweep_waveform = ([wave_var_name],
                                          [waveform_idx],
                                          pulse.params["sweep_type"],
                                          pulse.params["sweep_min"],
                                          pulse.params["sweep_max"],
                                          pulse.params["sweep_steps"])
                        waveform_idx += 1                        

        #### 3. Extract parameters for channel / output setup procedure  ####

            # Frequency, Phase of oscillator
            # Connecting oscillator number to output
            # Modulation mode of output
            # DC offset of output : for IQ mixing

            pulse = pulse_list[0]
            self.setup_config_dict[ch.name] = {}

            if pulse.mod:
                mod, mod_freq, mod_ph = pulse.mod, pulse.mod_freq, pulse.mod_ph

                self.setup_config_dict[ch.name].update({ "mod": mod,
                                                    "mod_freq": mod_freq,
                                                    "mod_ph": mod_ph})

            if "iq" in pulse.params and pulse.params["iq"]:
                amp_iq, dc_iq, lo_freq = pulse.params["amp_iq"], pulse.params["dc_iq"], pulse.params["lo_freq"]

                self.setup_config_dict[ch.name].update({
                                                    "amp_iq": amp_iq,
                                                    "dc_iq": dc_iq,
                                                    "lo_freq": lo_freq})

        #### 3. Handle synchronization of pulses across channel ####
        # Forces pulses that overlap across channels to have the same start and
        # end time by padding with zeros; they will be played at the same time
        # in the AWG.

        # Iterate over all pairs of pulses across all channels
        # for ch1, pulse_list1 in analog_pulse_dict.items():
        #     for pulse1 in pulse_list1:
        #         for ch2, pulse_list2 in analog_pulse_dict.items():
        #             if ch1 == ch2: continue # Only compare across different channels
        #             for pulse2 in pulse_list2:

        #                 while True:
        #                     # Pulse 1 starts first
        #                     if pulse1.t0  < pulse2.t0 < (pulse1.t0 + pulse1.dur):
        #                         # Pulse 2 completely within pulse 1
        #                         if (pulse2.t0 + pulse2.dur) < (pulse1.t0 + pulse1.dur):

        #                             # Extend pulse2 to match the times of pulse1
        #                             # done is set to True if this succeeded.
        #                             done, pulse2 = extend_pulse(pulse2, pulse_list2, self.pb.dflt_dict[ch2],
        #                                             pulse1.t0, pulse1.t0 + pulse1.dur)
        #                             # done is False if pulse2 found another pulse
        #                             # in the way when trying to extend; pulse2
        #                             # is now merged with that pulse and we loop
        #                             # to check relative timings with pulse1 again.
        #                             if done: break

        #                         # Partially intersecting
        #                         else:
        #                             done1, pulse1 = extend_pulse(pulse1, pulse_list1, self.pb.dflt_dict[ch1],
        #                                                         None, pulse2.t0 + pulse2.dur)
        #                             done2, pulse2 = extend_pulse(pulse2, pulse_list2, self.pb.dflt_dict[ch2],
        #                                                         pulse1.t0, None)
        #                             if done1 and done2: break

        #                     # Pulse 2 starts first
        #                     elif pulse2.t0 < pulse1.t0 < (pulse2.t0 + pulse2.dur):
        #                         # Pulse 1 completely within pulse 2
        #                         if (pulse1.t0 + pulse1.dur) < (pulse2.t0 + pulse2.dur):
        #                             done, pulse1 = extend_pulse(pulse1, pulse_list1, self.pb.dflt_dict[ch1],
        #                                                         pulse2.t0, pulse2.t0 + pulse2.dur)
        #                             if done: break

        #                         # Partially intersecting
        #                         else:
        #                             done1, pulse1 = extend_pulse(pulse1, pulse_list1, pulse2.t0, None)
        #                             done2, pulse2 = extend_pulse(pulse2, pulse_list2, None, pulse1.t0 + pulse1.dur)
        #                             if done1 and done2: break
        #                     # Pulses not intersecting
        #                     else:
        #                         break

        return setup_instr, waveforms, sweep_waveform

    def zip_digital_commands(self): 
        """Generate zipped version of DIO commands.

        This will reduce the digital waveform to specify the times, when the DIO
        output changes, and corresponsing timesteps where the output change.
        Does not account for the time taken for the wait() command.

        :return: codewords: (np.array) of unique DIO codewords ordered in time
        :return: codeword_times: (list) of times in AWG timesteps to output the
            DIO codewords
        """

        # np.array of DIO codewords as sampled at each AWG time step.
        codewords_array = self.digital_codewords_samples

        # Force final output to be zero 
        if self.end_low:
            codewords_array[-1] = 0

        # Find out where the the codewords changes. The indices refer to the
        # left edge of transition, e.g. [0 0 1] returns index 1.
        dio_change_index = np.where(codewords_array[:-1] != codewords_array[1:])[0]

        if len(dio_change_index) == 0:
            return [], []

        # Add 1 to shift from the left to right edge of transition. Add 0
        # for the initial DIO value.
        codeword_times_force_value = [0] + list(dio_change_index + 1)
        # Get the unique DIO codewords in order.
        codewords = codewords_array[codeword_times_force_value]

        # Codeword times that keeps the Placeholder value of timings
        codeword_times = []
        for ch in [ch for ch in self.pb.p_dict.keys() if not ch.is_analog]:
            for p_item in self.pb.p_dict[ch]:
                # Find indexes of pulse edges
                indx_1 = p_item.t0 * DIG_SAMP_RATE
                indx_2 = indx_1 + p_item.dur * DIG_SAMP_RATE
                codeword_times.extend([indx_1, indx_2])

        codeword_times = list(set(codeword_times))
        codeword_times.sort()

        # If 0 is not already in the list of times (from a pulse being there),
        # we need to add it in since otherwise we would have no initial value.
        if codeword_times[0] != 0:
            codeword_times = [0] + codeword_times

        # Sanity check that both methods should give the same length
        assert(len(codeword_times) == len(codeword_times_force_value))
    
        return codewords, codeword_times

    def combine_command_timings(self):

        """ Combine the commands and timings from the analog and digital commands
        to give a combined list of codewords and wait time intervals.

        :return: combined_commands: (list) of commands represented as tuples.  
            Digital: ("digital", dio_codeword)
            Analog: ("analog", list of var names, list of ch names)
            Analog has a list since we can have >1 wave at the same time
        :return: combined_waittimes: (list) of wait times between all commands,
            including digital and digital.
        """

        # list of times in AWG timesteps to output the DIO codewords 
        digital_times = self.digital_times
        # list of tuples(waveform var name, ch_name, start_time, end_time, 
        # waveform idx, np.array waveform). Times in AWG timesteps
        waveforms = self.waveforms

        combined_commands, combined_times = [], [0]

        # Sort by start time
        waveforms.sort(key=lambda pulse: pulse[2])

        dio_index = 0
        ana_index = 0

        # Iterate as long as at least 1 list is still non-empty
        while dio_index < len(digital_times) or ana_index < len(waveforms):

            # DIO list is empty, take from the analog list
            if dio_index == len(digital_times):
                take = "analog"

            # Analog list is empty, take from the digital list
            elif ana_index == len(waveforms):
                take = "dio"

            # Both still have elements, compare their start times
            else:
                if digital_times[dio_index] < waveforms[ana_index][2]:
                    take = "dio"
                else:
                    take = "analog"

            if take == "dio":
                # Store DIO codeword
                combined_commands.append(("dio", self.digital_codewords[dio_index]))
                combined_times.append(digital_times[dio_index])
                dio_index += 1
            else:
                # Initialize in cases where range(ana_index+1, len(waveforms)) is empty list
                ana_index_search = ana_index + 1

                # Check if subsequent waveforms start at the same time
                # The case where they are somewhat close but need to be padded
                # will be handled earlier in the pulse parser
                for ana_index_search in range(ana_index+1, len(waveforms)+1):
                    # Stop when reach end of list or a pulse with a different time
                    if (ana_index_search == len(waveforms) or
                        waveforms[ana_index][2] != waveforms[ana_index_search][2]):
                        break

                # Store waveform var name and channel name for the waveforms
                # that start at the same time.
                combined_commands.append((
                    "analog",
                    [waveforms[index][0] for index in range(ana_index, ana_index_search)],
                    [waveforms[index][1] for index in range(ana_index, ana_index_search)])
                )

                combined_times.append(waveforms[ana_index][2])
                ana_index = ana_index_search # Increment to the next unused waveform

        # Waittimes are just the differences between the command times
        # Don't use np.diff since that converts Placeholder to np float
        combined_waittimes = [combined_times[i] - combined_times[i-1] for i in range(1, len(combined_times))]

        return combined_commands, combined_waittimes

    def awg_seq_command(self, command, mask):
        """ Generate a line of AWG code for a given analog/digital command.

        :command: (tuple) representing an analog or digital command
            Digital: ("digital", dio_codeword)
            Analog: ("analog", list of var names, list of ch names)
        :mask: (int) Mask for DIO outputs to avoid overwriting existing output bits

        :return: (str) AWG code representing the specified command
        """

        set_dio_cmd = "setDIO({});\n"
        playwave_cmd = "playWave({});\n"
        cmd_table_cmd = "//LOOP OVER SWEEP PARAMETER;\nexecuteTableEntry({});\n"
        wave_str = ""

        if command[0] == "dio":
            # Add setDIO command to sequence
            dio_codeword = int(command[1])
            if self.exp_config_dict["preserve_bits"]:
                # Zero out any bits that fall outside the mask to avoid modifying
                # bits not involved in pulses. The codeword should usually 
                # always lie within the mask bits and so this should do nothing, 
                # but acts as a failsafe.
                masked_codeword = (mask & dio_codeword) 
                return set_dio_cmd.format(f"masked_state|{masked_codeword}")
            else:
                return set_dio_cmd.format(dio_codeword)

        elif command[0] == "analog":
            waveform_var_names, ch_names = command[1], command[2]
            ch_types, ch_nums = zip(*[self.assignment_dict[ch_name] for ch_name in ch_names])

            if not all(ch_type == "analog" for ch_type in ch_types):
                self.log.warn(f"Channel expected to get analog but got an unexpected type.")

            if (self.sweep_waveform is not None and
                set(waveform_var_names) == set(self.sweep_waveform[0])):
                return cmd_table_cmd.format(f"sweep_idx_{self.pb.name}")

            # For analog waveforms, the command is playWave(ch, wave, ch, wave, ...)
            # Put the waveforms from the earlier channels first.
            for ch_num, waveform_var_name in sorted(zip(ch_nums, waveform_var_names)):
                if wave_str != "": wave_str += ", "  # Separator btw channels
                wave_str += f"{ch_num}, {waveform_var_name}"

            return playwave_cmd.format(wave_str)

        else:
            self.log.warn(f"Unknown command type {command[0]} found.")

    def setup_variable_settings(self, sequence):
        """ Add commands to dynamically change the AWG settings for settings that
        are set to be variables that are defined in the AWG code. """

        for ch, ch_config_dict in self.setup_config_dict.items():
            ch_type, ch_num = self.assignment_dict[ch]
            # Convert from specified 1-indexed to 0-indexed in the AWG code
            ch_num -= 1

            for config_type, config_val in ch_config_dict.items():
                # Ignore non-placeholders as those were setup before.
                if type(config_val) != Placeholder:
                    continue

                # Convert to the string reprensenting the variable
                config_val = config_val.var_str()

                if config_type == "mod_freq":
                    sequence += f"setDouble('oscs/{ch_num}/freq', {config_val});\n"
                elif config_type == "mod_ph":
                    sequence += f"setDouble('sines/{ch_num}/phaseshift', {config_val});\n"
                else:
                    self.hd.log.warn(f"Unsupported analog channel config {config_type}.")

        return sequence


    def construct_awg_sequence(self, wait_offset=SETDIO_OFFSET):
        """Construct .seqc sequence representing the AWG instructions to output
        a set of pulses over multiple channels

        :commands: (list) List of unique command tuples in sequential order
            from both digital and analog channels.  Tuples are of the form
            ("dio", dio_codeword) or ("analog", waveform_var_name, ch_name)
        :waittimes: (np.array) Array of waittimes between commands, in
            sequential order.
        :wait_offset: (int) Number of samples to adjust the waittime in order to
            account for duration of setDIO() command.
        """
        
        mask = None
        if self.exp_config_dict["preserve_bits"]:
            mask = sum(1 << bit for bit in self.used_dio_bits)

        sequence = f"// Start of Pulseblock {self.pb.name}\n"
        wait_cmd = "wait({});\n"

        sequence = self.setup_variable_settings(sequence)

        # Waits and commands are interspersed (wait-command-wait-command-...)
        # If the first wait is 0, it is not displayed due to the wait_offset
        for i, waittime in enumerate(self.combined_waittimes):

            # Add waittime to sequence but subtract the wait offset
            if waittime > wait_offset:
                if type(waittime) == Placeholder:
                    # Subtract the default offset from the Placeholder
                    # It is used to separate Placeholder pulses in time since
                    # their initial separation is unknown.
                    waittime -= Placeholder.default_values["offset_var"] * 1e-6 * DIG_SAMP_RATE
                    sequence += wait_cmd.format((waittime - wait_offset).int_str())
                else:
                    sequence += wait_cmd.format(int(waittime - wait_offset))

            sequence += self.awg_seq_command(self.combined_commands[i], mask)
        
        sequence += f"// End of Pulseblock {self.pb.name}\n"

        return sequence

    def get_awg_sequence(self, waveform_idx):
        """Generate a set of .seqc instructions for the AWG to output a set of
        pulses over multiple channels

        Returns a string containing a series of setDIO() and wait() .seqc
        commands which will reproduce the waveform defined
        by the pulseblock object.

        :param: waveform_idx (int): Indices assigned to waveforms from this
            pulseblock will start counting incrementing from this value; needs
            to be passed from the main program to sync the number with other PBs.
        :return: setup_seq (str): AWG commands used for setup of the pulse
            sequence and will only need to be run once even if the sequence is
            run multiple times.
        :return: sequence (str): AWG commands (e.g. setDIO() and wait()) that
            will generate the pulses described by the pulseblock.
        """

        # Get sample-wise sets of codewords for the digital channels.
        self.digital_codewords_samples = self.gen_digital_codewords()

        # Reduce this array to a set of codewords + waittimes.
        self.digital_codewords, self.digital_times = self.zip_digital_commands()

        # Get instructions for the analog channels
        # analog_setup is a string to be prepended to the compiled code
        self.analog_setup, self.waveforms, self.sweep_waveform = self.gen_analog_instructions(waveform_idx)

        self.combined_commands, self.combined_waittimes = self.combine_command_timings()

        # Reconstruct set of .seqc instructions representing the digital waveform.
        self.sequence = self.construct_awg_sequence()

        return self.analog_setup, self.sequence, self.waveforms, self.sweep_waveform
