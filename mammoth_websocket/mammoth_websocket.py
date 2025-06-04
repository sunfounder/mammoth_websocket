import asyncio
import websockets
import json
import threading

class MammothWebSocket():

    DEFAULT_PORT = 30102

    def __init__(self, port=DEFAULT_PORT):
        self.port = port
        self.websocket = None
        self.client_ip = None
        self.server_thread = None
        self.server = None
        self.__user_on_device_config__ = None
        self.__user_on_io_data__ = None
        self.__user_on_connect__ = None
        self.__user_on_disconnect__ =None
        self.__device_info__ = {}

    def set_device_info(self, device_info):
        self.__device_info__ = device_info

    def set_device_config_handler(self, on_device_config):
        self.__user_on_device_config__ = on_device_config

    def set_io_data_handler(self, on_io_data):
        self.__user_on_io_data__ = on_io_data

    def set_connect_handler(self, on_connect):
        self.__user_on_connect__ = on_connect

    def set_disconnect_handler(self, on_disconnect):
        self.__user_on_disconnect__ = on_disconnect

    async def handle_connect(self, websocket):
        if self.websocket:
            return False
        self.websocket = websocket
        self.client_ip = websocket.remote_address[0]

        print(f'client {self.client_ip} connected')

        # Send device info
        await websocket.send(json.dumps(self.__device_info__))

        if self.__user_on_connect__:
            self.__user_on_connect__()
        return True

    async def handle_disconnect(self):
        print(f'client {self.client_ip} disconnected')
        self.websocket = None

        if self.__user_on_disconnect__:
            await self.__user_on_disconnect__()

    async def handle_receive(self, data):
        # print(f'received: {data}')
        if isinstance(data, str):
            # print("Handle string data")
            if data.startswith('SET+'):
                # print("Set device config")
                data = data[4:]
                try:
                    data = json.loads(data)
                except Exception as e:
                    await self.response('ERROR', ['Invalid json format', f'{e}'] )
                if self.__user_on_device_config__:
                    await self.__user_on_device_config__(data)
                await self.response('OK')
            elif data.startswith('DATA+'):
                data = data[5:]
                if data != '':
                    try:
                        data = json.loads(data)
                    except Exception as e:
                        await self.response('ERROR', ['Invalid json format', f'{e}'] )

                # handle received data
                if self.__user_on_io_data__:
                    await self.__user_on_io_data__(data)
            else:
                await self.response('ERROR', ['Invalid command format'])

    async def process_received_messages(self, websocket):
        try:
            async for message in websocket:
                await self.handle_receive(message)
        except websockets.exceptions.ConnectionClosedError as e:
            await self.handle_disconnect()

    async def websocket_connection_loop(self, websocket):
        if not await self.handle_connect(websocket):
            return False
        try:
            await self.process_received_messages(websocket)
        finally:
            await self.handle_disconnect()

    def start(self):
        self.server_thread = threading.Thread(target=self.run_server_in_thread)
        self.server_thread.daemon = True
        self.server_thread.start()

    def close(self):
        if self.server:
            self.server.close()
        if self.server_thread:
            self.server_thread.join(timeout=2)
            self.server_thread = None
        
        self.websocket = None
        self.server = None
        print("Server closed")

    def run_server_in_thread(self):
        try:
            asyncio.run(self.main())
        except Exception as e:
            print(f"Server thread error: {e}")

    async def send(self, data):
        try:
            if self.websocket is None:
                return
            await self.websocket.send(data)
        except websockets.exceptions.ConnectionClosedError as e:
            await self.handle_disconnect()
        except websockets.exceptions.ConnectionClosedOK as e:
            await self.handle_disconnect()
        except RuntimeError as e:
            await self.handle_disconnect()

    async def response(self, status, error=[], data={}):
        _response = {
            'status': status,
            'error': error,
            'data': data
        }
        await self.send(json.dumps(_response))

    async def main(self):
        self.server = await websockets.serve(self.websocket_connection_loop, "0.0.0.0", self.port)
        print(f'websocket server start at port {self.port}')
        loop = asyncio.get_event_loop()  # 获取当前事件循环
        try:
            await self.server.serve_forever()  # 捕获 serve_forever 的取消异常
        except asyncio.CancelledError:
            print("Server Cancelled...")
        finally:
            loop.stop()  # 显式停止事件循环







     



                    





