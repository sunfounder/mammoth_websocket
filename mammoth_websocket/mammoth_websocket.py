import asyncio
import websockets
import json
import threading

class Client:
    def __init__(self, id, ip, websocket):
        self.id = id
        self.websocket = websocket
        self.ip = ip

class MammothWebSocket():

    DEFAULT_PORT = 30102

    def __init__(self, port=DEFAULT_PORT):
        self.port = port
        self.websocket = None
        self.client_ip = None
        self.running = False
        self.server_thread = None
        self.loop = None
        self.__user_on_device_config__ = None
        self.__user_on_io_data__ = None
        self.__user_on_connect__ = None
        self.__user_on_disconnect__ =None
        self.__device_info__ = {}

    def set_device_info(self, device_info):
        self.__device_info__ = device_info

    def set_on_device_config(self, on_device_config):
        self.__user_on_device_config__ = on_device_config

    def set_on_io_data(self, on_io_data):
        self.__user_on_io_data__ = on_io_data

    def set_on_connect(self, on_connect):
        self.__user_on_connect__ = on_connect

    def set_on_disconnect(self, on_disconnect):
        self.__user_on_disconnect__ = on_disconnect

    async def on_connect(self, websocket):
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

    async def on_disconnect(self):
        print(f'client {self.client_ip} disconnected')
        self.client = None

        if self.__user_on_disconnect__:
            self.__user_on_disconnect__()

    async def on_receive(self, data):
        if isinstance(data, str):
            if data.startswith('SET+'):
                data = data[4:]
                try:
                    data = json.loads(data)
                except Exception as e:
                    await self.response('ERROR', ['Invalid json format', f'{e}'] )
                if self.__user_on_device_config__:
                    await self.__user_on_device_config__(data)
                await self.response('OK')
            if data.startswith('DATA+'):
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

    async def receive_message(self, websocket):
        try:
            async for message in websocket:
                await self.on_receive(message)
        except websockets.exceptions.ConnectionClosedError as e:
            self.on_disconnect()

    async def websocket_loop(self, websocket):
        print("websocket_loop")
        if not await self.on_connect(websocket):
            return False

        try:
            await self.receive_message(websocket)
        finally:
            await self.on_disconnect()

    def start(self):
        self.running = True
        self.server_thread = threading.Thread(target=self.server_run)
        self.server_thread.daemon = True
        self.server_thread.start()

    def close(self):
        self.server.close()
        self.running = False

    def server_run(self):
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)
        self.loop.run_until_complete(self.main())

    async def send(self, data):
        try:
            await self.websocket.send(data)
        except websockets.exceptions.ConnectionClosedError as e:
            self.on_disconnect()
        except websockets.exceptions.ConnectionClosedOK as e:
            self.on_disconnect()
        except RuntimeError as e:
            self.on_disconnect()

    async def response(self, status, error=[], data={}):
        _response = {
            'status': status,
            'error': error,
            'data': data
        }
        await self.send(json.dumps(_response))

    async def main(self):
        self.server = await websockets.serve(self.websocket_loop, "0.0.0.0", self.port)
        print(f'websocket server start at port {self.port}')
        async with self.server:
            await asyncio.Future() # run forever
        print('server closed')







     



                    





