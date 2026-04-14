
from typing import Union
import pyvisa

from pymodaq.control_modules.move_utility_classes import DAQ_Move_base, main, comon_parameters_fun, DataActuatorType
from pymodaq.utils.data import DataActuator
from pymodaq_plugins_smaract.utils import Config
from pymeasure.instruments.smaract.scu_ascii import (
    SCUChannelStepper,SmarActSCUStepper,SmarActSCU_ASCII, SmarActSCULinear, SmarActSCUAngular,
    SCUChannelLinear, SCUChannelAngular, Q_)

plugin_config = Config()

rm = pyvisa.ResourceManager()
instruments_ports = rm.list_resources() # liste de touts ports sur ordinateur actuel
instruments_movement = ['Linear','Angular','Stepper']

# trouver le bon port sur l'ordinateur actuel, sinon prend le 1er sur liste
if plugin_config('SCU', 'ascii', 'default_port') in instruments_ports:
    instrument_port = plugin_config('SCU', 'ascii', 'default_port')
else:
    instrument_port = instruments_ports[0]


class DAQ_Move_SmarActSCUAscii(DAQ_Move_base):
    """

    """
    is_multiaxes = True
    _axis_names: Union[list[str], dict[str, int]] = ['0', '1', '2']
    _controller_units: Union[str, list[str]] = 'mm'
    _epsilon: Union[float, list[float]] = 0.1  # TODO replace this by a value that is correct depending on your controller
    data_actuator_type = DataActuatorType.DataActuator

    #every property of the current driver that will be used, the 'title' is used for calling the object
    params = [
                 {'title': 'Port', 'name': 'port', 'type': 'list', 'value': instrument_port,
                  'limits': list(instruments_ports)},
                 {'title': 'Device:', 'name': 'device', 'type': 'str', 'value': '', 'readonly': True},
                 {'title': 'SN:', 'name': 'serial_number', 'type': 'str', 'value': '', 'readonly': True},
                 {'title': 'Frequency (Hz)', 'name': 'frequency', 'type': 'int', 'value': 1000,},
                 {'title': 'Amplitude (V)', 'name': 'amplitude', 'type': 'int', 'value': 100,
                  'limits': [15, 100]},
                 {'title': 'Movement', 'name': 'movement', 'type': 'list', 'value': instruments_movement,
                  'limits': list(instruments_movement)},

    ] + comon_parameters_fun(is_multiaxes=is_multiaxes, axis_names=_axis_names, epsilon=_epsilon)
    ##########################################################

    def ini_attributes(self):
        self.controller: Union[SCUChannelLinear, SmarActSCUAngular,
        SmarActSCU_ASCII] = None

    def commit_settings(self, param):
        if param.name() == 'amplitude':
            self.controller.amplitude = Q_(param.value(), 'V')
        elif param.name() == 'frequency':
            self.controller.frequency = Q_(param.value(), 'Hz')

    def ini_stage(self, controller=None):
        """Initialize the controller and stages (axes) with given parameters.

        """

        if self.is_master:
            if self.settings['movement'] == 'Linear':
                self.controller = SmarActSCULinear(self.settings['port'])
            elif self.settings['movement'] == 'Angular':
                self.axis_unit = 'm°'
                self.controller = SmarActSCUAngular(self.settings['port'])
            elif  self.settings['movement'] == 'Stepper':
                self.controller = SmarActSCUStepper(self.settings['port'])
                self.axis_unit = ''

        else:
            self.controller = controller

        self.settings.child('device').setValue(self.controller.model)
        self.settings.child('serial_number').setValue(self.controller.serial_nb)

        self.commit_settings(self.settings.child('amplitude'))
        self.commit_settings(self.settings.child('frequency'))

        #is it not hardcoding here, when we say that the channel must be '0'?
        self.axis_units = [self.controller.channels['0'].unit for _ in range(3)]

        self.settings.child('movement').setOpts(enabled=False)
        info = ''
        initialized = True

        return info, initialized

    def close(self):
        """
        Close the communication with the SmarAct controller.
        """
        self.settings.child('movement').setOpts(enabled=True)
        if self.is_master:
            self.controller.close()

    def  get_actuator_value(self):

        pos = self.controller.channels[self.axis_name].get_position()
        if isinstance(pos, Q_):
            val = float(pos.magnitude)
            unit = str(pos.units)
        else:
            val = float(pos)
            unit = ''

        value = DataActuator(data=val, units=unit)
        value = self.get_position_with_scaling(value)
        self.current_position = value
        return value

    def move_abs(self, value: DataActuator):

        value = self.check_bound(value)
        self.target_value = value
        value = self.set_position_with_scaling(value)

        if self.settings['movement'] == 'Stepper':
            # Le Stepper veut un nombre pur (magnitude)
            target = value.quantities[0][0].magnitude
        else:
            # Linear/Angular utilisent l'objet Quantity exact
            target = value.quantities[0][0]

        self.controller.channels[self.axis_name].move_abs(target)


    def move_rel(self, value: DataActuator):
        """
        Move to a relative position

        Parameters:
        ----------
         - position: float
        """
        value = (self.check_bound(self.current_position + value) - self.current_position)
        self.target_position = value + self.current_position
        value = self.set_position_relative_with_scaling(value)

        if self.settings['movement'] == 'Stepper':
            target = value.quantities[0][0].magnitude
        else:
            target = value.quantities[0][0]

        self.controller.channels[self.axis_name].move_rel(target)



    def move_home(self):
        """
        Move to home and reset position to zero.
        """
        self.controller.channels[self.axis_name].move_to_ref()
        self.get_actuator_value()

    def stop_motion(self):
        """
        Stop any ongoing movement of the positionner.
        """
        self.controller.stop()
        ##self.move_done()


if __name__ == "__main__":
    main(__file__, init=False)
