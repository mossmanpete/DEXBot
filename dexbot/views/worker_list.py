import time
from threading import Thread
import webbrowser

from dexbot import __version__
from dexbot.qt_queue.queue_dispatcher import ThreadDispatcher
from dexbot.qt_queue.idle_queue import idle_add
from .ui.worker_list_window_ui import Ui_MainWindow
from .create_worker import CreateWorkerView
from .settings import SettingsView
from .worker_item import WorkerItemWidget
from .errors import gui_error
from .layouts.flow_layout import FlowLayout

from PyQt5 import QtGui
from PyQt5.QtWidgets import QMainWindow
from bitsharesapi.bitsharesnoderpc import BitSharesNodeRPC


class MainView(QMainWindow, Ui_MainWindow):

    def __init__(self, main_controller):
        super().__init__()
        self.setupUi(self)
        self.main_controller = main_controller

        # Global configuration
        self.config = self.main_controller.config

        # View settings
        self.max_workers = 10

        # Number of active workers
        self.num_of_active_workers = 0

        # Worker item widgets on the main view
        self.workers = {}

        self.closing = False
        self.statusbar_updater = None
        self.statusbar_updater_first_run = True
        self.main_controller.set_info_handler(self.set_worker_status)
        self.layout = FlowLayout(self.scrollAreaContent)

        # View events
        self.add_worker_button.clicked.connect(lambda: self.handle_add_worker())
        self.settings_button.clicked.connect(lambda: self.handle_open_settings())
        self.help_button.clicked.connect(lambda: self.handle_open_documentation())

        # Load worker widgets from config file
        # Todo: THREADING HERE
        # Assign thread for each worker item widget and then set it up so that start worker button starts the thread
        for worker_name in self.config.workers_data:
            self.add_worker_widget(worker_name)

            # Limit the max amount of workers so that the performance isn't greatly affected
            if self.num_of_active_workers >= self.max_workers:
                self.add_worker_button.setEnabled(False)
                break

        # Dispatcher polls for events from the workers that are used to change the ui
        # Todo: This can be removed??
        # self.dispatcher = ThreadDispatcher(self)
        # self.dispatcher.start()

        # Statusbar updater
        self.status_bar.showMessage("ver {} - Node delay: - ms".format(__version__))
        self.statusbar_updater = Thread(target=self._update_statusbar_message)
        self.statusbar_updater.start()

        QtGui.QFontDatabase.addApplicationFont(":/bot_widget/font/SourceSansPro-Bold.ttf")

    def add_worker_widget(self, worker_name):
        worker_config = self.main_controller.config.get_worker_config(worker_name)

        widget = WorkerItemWidget(worker_name, worker_config, self.main_controller, view=self)
        widget.setFixedSize(widget.frameSize())

        # Add worker item widget to a list of workers
        self.workers[worker_name] = widget

        # Add worker item widget to the main layout
        self.layout.addWidget(widget)

        # Limit the max amount of workers so that the performance isn't greatly affected
        self.num_of_active_workers += 1
        if self.num_of_active_workers >= self.max_workers:
            self.add_worker_button.setEnabled(False)

    def remove_worker_widget(self, worker_name):
        """ Remove deleted worker from the main view"""
        self.workers.pop(worker_name, None)

        self.num_of_active_workers -= 1
        if self.num_of_active_workers < self.max_workers:
            self.add_worker_button.setEnabled(True)

    def change_worker_widget_name(self, old_worker_name, new_worker_name):
        """ Update worker name that has been edited """
        worker_data = self.workers.pop(old_worker_name)
        self.workers[new_worker_name] = worker_data

    @gui_error
    def handle_add_worker(self):
        create_worker_dialog = CreateWorkerView(self.main_controller.bitshares_instance)
        return_value = create_worker_dialog.exec_()

        # User clicked save
        if return_value == 1:
            worker_name = create_worker_dialog.worker_name
            self.main_controller.create_worker(worker_name)

            self.config.add_worker_config(worker_name, create_worker_dialog.worker_data)
            self.add_worker_widget(worker_name)

    @gui_error
    def handle_open_settings(self):
        settings_dialog = SettingsView()
        return_value = settings_dialog.exec_()

    @staticmethod
    def handle_open_documentation():
        webbrowser.open('https://github.com/Codaone/DEXBot/wiki')

    def set_worker_name(self, worker_name, value):
        self.workers[worker_name].set_worker_name(value)

    def set_worker_account(self, worker_name, value):
        self.workers[worker_name].set_worker_account(value)

    def set_worker_profit(self, worker_name, value):
        self.workers[worker_name].set_worker_profit(value)

    def set_worker_market(self, worker_name, value):
        self.workers[worker_name].set_worker_market(value)

    def set_worker_slider(self, worker_name, value):
        self.workers[worker_name].set_worker_slider(value)

    def customEvent(self, event):
        # Process idle_queue_dispatcher events
        event.callback()

    def closeEvent(self, event):
        self.closing = True
        self.status_bar.showMessage("Closing app...")
        if self.statusbar_updater and self.statusbar_updater.is_alive():
            self.statusbar_updater.join()

    def _update_statusbar_message(self):
        while not self.closing:
            # When running first time the workers are also interrupting with the connection
            # so we delay the first time to get correct information
            if self.statusbar_updater_first_run:
                self.statusbar_updater_first_run = False
                time.sleep(1)

            idle_add(self.set_statusbar_message)
            runner_count = 0
            # Wait for 30s but do it in 0.5s pieces to not prevent closing the app
            while not self.closing and runner_count < 60:
                runner_count += 1
                time.sleep(0.5)

    def set_statusbar_message(self):
        node = self.config['node']
        try:
            start = time.time()
            BitSharesNodeRPC(node, num_retries=1)
            latency = (time.time() - start) * 1000
        except BaseException:
            latency = -1

        if latency != -1:
            self.status_bar.showMessage("ver {} - Node delay: {:.2f}ms".format(__version__, latency))
        else:
            self.status_bar.showMessage("ver {} - Node disconnected".format(__version__))

    def set_worker_status(self, worker_name, level, status):
        if worker_name != 'NONE':
            worker = self.workers.get(worker_name, None)
            if worker:
                worker.set_status(status)
