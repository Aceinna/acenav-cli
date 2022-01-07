from bluetooth import *
import time
import base64

from ...framework.utils import print as print_helper
from ...framework.constants import APP_TYPE
from ...framework.context import APP_CONTEXT
from ...core.gnss import RTCMParser
from ...core.event_base import EventBase




class BTServer(EventBase):
    def __init__(self, device_message):
        super(BTServer, self).__init__()

        self.parser = RTCMParser()
        self.parser.on('parsed', self.handle_parsed_data)
        self.is_connected = 0
        self.is_close = False
        self.bt_close = False
        self.append_header_string= None
        self.bt_server_socket = None
        self.device_message = device_message

    def run(self):
        APP_CONTEXT.get_print_logger().info('BT run..')
        while True:
            if self.is_close:
                if self.bt_server_socket:
                    self.bt_server_socket.close()
                self.is_connected = 0
                return

            while True:
                # if self.communicator.can_write():
                time.sleep(3)
                self.is_connected = self.doConnect()
                if self.is_connected == 0:
                    time.sleep(3)
                else:
                    self.is_close = False
                    self.bt_close = False
                    print('BT connected..')
                    break
                # else:
                #    time.sleep(1)
            while self.bt_close == False:
                self.recv()

    def set_connect_headers(self, headers:dict):
        self.append_header_string = ''
        for key in headers.keys():
            self.append_header_string += '{0}: {1}\r\n'.format(key, headers[key])

    def clear_connect_headers(self):
        self.append_header_string = None


    def doConnect(self):
        self.is_connected = 0

        self.bt_server=BluetoothSocket( RFCOMM )
        self.bt_server.bind(("",PORT_ANY))
        self.bt_server.listen(1)

        port = self.bt_server.getsockname()[1]

        uuid = "94f39d29-7d6d-437d-973b-fba39e49d4ee"

        advertise_service(self.bt_server, "SampleServer",
                        service_id = uuid,
                        service_classes = [ uuid, SERIAL_PORT_CLASS ],
                        profiles = [ SERIAL_PORT_PROFILE ])

        print("BT:[Waiting for connection on RFCOMM channel %d]" % port)

        self.bt_server_socket, client_info = self.bt_server.accept()

        print("BT:[Accepted connection from]", client_info)
        print(self.device_message)
        self.bt_server_socket.send(self.device_message)
        self.is_connected = 1
        return self.is_connected

    def send(self, data):
        if self.is_connected:
            try:
                if isinstance(data, str):
                    self.bt_server_socket.send(data.encode('utf-8'))
                else:
                    self.bt_server_socket.send(bytes(data))
            except Exception as e:
                print_helper.print_on_console('BT:[send] error occur {0}'.format(e), skip_modes=[APP_TYPE.CLI])
                APP_CONTEXT.get_print_logger().info(
                    'BT:[send] {0}'.format(e))
                self.bt_close = True
                self.bt_server.close()
                self.bt_server_socket.close()
                self.is_connected = 0

    def recv(self):
        try:
            # print(dir(self.bt_server))
            self.bt_server.settimeout(10)
        except Exception as e:
            print(e)
        while True:
            if self.is_close or self.bt_close:
                return
            try:
                data = self.bt_server_socket.recv(1024)
                if data:
                    APP_CONTEXT.get_print_logger().info(
                        'BT:[recv] rxdata {0}'.format(len(data)))
                    # self.parser.receive(data)
                else:
                    # print_helper.print_on_console('BT:[recv] no data error', skip_modes=[APP_TYPE.CLI])
                    # APP_CONTEXT.get_print_logger().info(
                    #     'BT:[recv] no data error')
                    # self.bt_server_socket.close()
                    return

            except Exception as e:
                print(e)
                # print_helper.print_on_console('BT:[recv] error occur {0}'.format(e), skip_modes=[APP_TYPE.CLI])
                # APP_CONTEXT.get_print_logger().info(
                #     'BT:[recv] error occur {0}'.format(e))
                # self.bt_server_socket.close()
                # return

    def recvResponse(self):
        self.bt_server_socket.settimeout(3)
        while True:
            try:
                data = self.bt_server_socket.recv(1024)
                if not data or len(data) == 0:
                    print_helper.print_on_console('BT:[recvR] no data', skip_modes=[APP_TYPE.CLI])
                    return None

                return data
            except Exception as e:
                APP_CONTEXT.get_print_logger().info(
                    'BT:[recvR] error occur {0}'.format(e))
                return None

    def close(self):
        self.append_header_string = None
        self.is_close = True


    def handle_parsed_data(self, data):
        combined_data = []
        for item in data:
            combined_data += item
        self.emit('parsed', combined_data)
