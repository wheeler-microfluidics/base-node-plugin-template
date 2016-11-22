import sys, traceback
from datetime import datetime

import gtk
from path_helpers import path
from pygtkhelpers.utils import dict_to_form
from flatland import Form, Float, Integer, Boolean, String, Enum
from flatland.validation import ValueAtLeast, ValueAtMost
import microdrop_utility as utility
from microdrop_utility.gui import yesno, FormViewDialog
from microdrop.gui.protocol_grid_controller import ProtocolGridController
from microdrop.logger import logger
from microdrop.plugin_helpers import (AppDataController, StepOptionsController,
                                      get_plugin_info)
from microdrop.plugin_manager import (PluginGlobals, Plugin, IPlugin,
                                      implements, emit_signal,
                                      get_service_instance)
from microdrop.app_context import get_app
import gobject
from serial_device import get_serial_ports

PluginGlobals.push_env('microdrop.managed')


class BaseNodePlugin(Plugin, AppDataController, StepOptionsController):
    """
    This class is automatically registered with the PluginManager.
    """
    implements(IPlugin)
    version = get_plugin_info(path(__file__).parent).version
    plugin_name = get_plugin_info(path(__file__).parent).plugin_name

    serial_ports_ = [port for port in get_serial_ports()]
    if len(serial_ports_):
        default_port_ = serial_ports_[0]
    else:
        default_port_ = None

    '''
    AppFields
    ---------

    A flatland Form specifying application options for the current plugin.
    Note that nested Form objects are not supported.

    Since we subclassed AppDataController, an API is available to access and
    modify these attributes.  This API also provides some nice features
    automatically:
        -all fields listed here will be included in the app options dialog
            (unless properties=dict(show_in_gui=False) is used)
        -the values of these fields will be stored persistently in the microdrop
            config file, in a section named after this plugin's name attribute
    '''
    AppFields = Form.of(
       Enum.named('serial_port').using(default=default_port_,
                                        optional=True).valued(*serial_ports_),
       # Float.named('float_option').using(optional=True, default=1.0),
       # Integer.named('integer_option').using(optional=True, default=1),
       # Boolean.named('boolean_option').using(optional=True, default=True),
       # String.named('string_option').using(optional=True, default="default"),
    )

    '''
    StepFields
    ---------

    A flatland Form specifying the per step options for the current plugin.
    Note that nested Form objects are not supported.

    Since we subclassed StepOptionsController, an API is available to access and
    modify these attributes.  This API also provides some nice features
    automatically:
        -all fields listed here will be included in the protocol grid view
            (unless properties=dict(show_in_gui=False) is used)
        -the values of these fields will be stored persistently for each step
    '''
    StepFields = Form.of(
        #Float.named('float_step_option').using(optional=True, default=1.0,
        #                                         #validators=
        #                                         #[ValueAtLeast(minimum=0),
        #                                         # ValueAtMost(maximum=100)]
        #                                         ),
    )

    def __init__(self):
        self.name = self.plugin_name
        self.proxy = None
        self.initialized = False  # Latch to, e.g., config menus, only once
        
    def connect(self):
        """ 
        Try to connect to the syring pump at the default serial
        port selected in the Microdrop application options.

        If unsuccessful, try to connect to the proxy on any
        available serial port, one-by-one.
        """

        from base_node_rpc import SerialProxy

        if len(BaseNodePlugin.serial_ports_):
            app_values = self.get_app_values()
            # try to connect to the last successful port
            try:
                self.proxy = SerialProxy(port=str(app_values['serial_port']))
            except:
                self.proxy = SerialProxy()
            app_values['serial_port'] = self.proxy.port
            self.set_app_values(app_values)
        else:
            raise Exception("No serial ports available.")

    def check_device_name_and_version(self):
        """
        Check to see if:

         a) The connected device is a what we are expecting
         b) The device firmware matches the host driver API version

        In the case where the device firmware version does not match, display a
        dialog offering to flash the device with the firmware version that
        matches the host driver API version.
        """ 
        try:
            self.connect()
            properties = self.proxy.properties
            package_name = properties['package_name']
            display_name = properties['display_name']
            if package_name != self.proxy.host_package_name:
                raise Exception("Device is not a %s" % properties['display_name'])

            host_software_version = self.proxy.host_software_version
            remote_software_version = self.proxy.remote_software_version

            # Reflash the firmware if it is not the right version.
            if host_software_version != remote_software_version:
                response = yesno("The %s firmware version (%s) "
                                 "does not match the driver version (%s). "
                                 "Update firmware?" % (display_name,
                                                       remote_software_version,
                                                       host_software_version))
                if response == gtk.RESPONSE_YES:
                    self.on_flash_firmware()
        except Exception, why:
            logger.warning("%s" % why)

    def on_edit_configuration(self, widget=None, data=None):
        '''
        Display a dialog to manually edit the configuration settings.
        '''
        config = self.proxy.config
        form = dict_to_form(config)
        dialog = FormViewDialog(form, 'Edit configuration settings')
        valid, response = dialog.run()
        if valid:
            self.proxy.update_config(**response)

    def on_flash_firmware(self, widget=None, data=None):
        app = get_app()
        try:
            connected = self.proxy != None
            if not connected:
                self.check_device_name_and_version()
            if connected:
                port = self.proxy.port
                # disconnect
                del self.proxy
                self.proxy = None

                from arduino_helpers.upload import upload
                from base_node_rpc import get_firmwares

                logger.info(upload('uno', lambda b: get_firmwares()[b][0], port))
                app.main_window_controller.info("Firmware updated successfully.",
                                                "Firmware update")
        except Exception, why:
            logger.error("Problem flashing firmware. ""%s" % why)
        self.check_device_name_and_version()

    def cleanup_plugin(self):
        if self.proxy != None:
            del self.proxy
            self.proxy = None

    def on_plugin_enable(self):
        super(BaseNodePlugin, self).on_plugin_enable()
        self.cleanup_plugin()
        self.check_device_name_and_version()
        if not self.initialized:
            app = get_app()
            self.tools_menu_item = gtk.MenuItem('BaseNodePlugin' )
            app.main_window_controller.menu_tools.append(self.tools_menu_item)
            self.tools_menu = gtk.Menu()
            self.tools_menu.show()
            self.tools_menu_item.set_submenu(self.tools_menu)

            self.edit_config_menu_item = \
                gtk.MenuItem("Edit configuration settings...")
            self.tools_menu.append(self.edit_config_menu_item)
            self.edit_config_menu_item.connect("activate",
                                               self.on_edit_configuration)
            self.edit_config_menu_item.show()
            self.edit_config_menu_item.set_sensitive(False)

        self.tools_menu_item.show()
        self.edit_config_menu_item.set_sensitive(self.proxy != None)

        if get_app().protocol:
            self.on_step_run()
            self._update_protocol_grid()

    def on_plugin_disable(self):
        self.tools_menu_item.hide()
        self.cleanup_plugin()
        if get_app().protocol:
            self.on_step_run()
            self._update_protocol_grid()

    def _update_protocol_grid(self):
        pgc = get_service_instance(ProtocolGridController, env='microdrop')
        if pgc.enabled_fields:
            pgc.update_grid()

    def on_step_run(self):
        """"
        Handler called whenever a step is executed. Note that this signal
        is only emitted in realtime mode or if a protocol is running.

        Plugins that handle this signal must emit the on_step_complete
        signal once they have completed the step. The protocol controller
        will wait until all plugins have completed the current step before
        proceeding.

        return_value can be one of:
            None
            'Repeat' - repeat the step
            or 'Fail' - unrecoverable error (stop the protocol)
        """
        app = get_app()
        logger.info('[BaseNodePlugin] on_step_run(): step #%d',
                    app.protocol.current_step_number)
        app_values = self.get_app_values()
        options = self.get_step_options()

        if (self.proxy != None and (app.realtime_mode or app.running)):
            microsteps = self.proxy.microstep_setting
            steps = (app_values['steps_per_microliter'] * options['microliters']
                     * microsteps)
            steps_per_second = (app_values['steps_per_microliter'] * microsteps
                                * options['microliters_per_min'] / 60.0)
            self.proxy.move(steps, steps_per_second)
            print 'move(steps=%d, steps_per_second=%d)' % (steps, steps_per_second)
            while self.proxy.steps_remaining:
                gtk.main_iteration()
        return_value = None
        emit_signal('on_step_complete', [self.name, return_value])


PluginGlobals.pop_env()
