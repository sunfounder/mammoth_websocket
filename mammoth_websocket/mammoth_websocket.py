import asyncio
import websockets
import json
import time
import threading

class Client:
    def __init__(self, id, ip, websocket):
        self.id = id
        self.websocket = websocket
        self.ip = ip

class MammothWebSocket():

    DEFAULT_PORT = 30102

    def __init__(self, port=DEFAULT_PORT, data_interval=20):
        self.port = port
        self.client_num = 0
        self.clients = {}
        self.data_interval = data_interval
        self.running = False
        self.running = False
        self.server_thread = None
        self.broadcast_thread = None
        self.loop = None
        self.__user_on_device_config__ = lambda x: None
        self.__user_on_io_data__ = lambda x: None
        self.__user_on_connect__ = lambda x: None
        self.__user_on_disconnect__ =lambda x: None
        self.io_data = {}
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

    def update_io_data(self, data):
        if isinstance(data, dict):
            self.io_data = {}
            self.io_data.update(data)

    async def on_connect(self, websocket):
        client_id = self.client_num
        client_ip = websocket.remote_address[0]
        client = Client(client_id, client_ip, websocket)
        self.clients[client_id] = client

        print(f'client {client_id, client_ip} connected')

        # Send device info
        await websocket.send(json.dumps(self.__device_info__))

        try:
            self.__user_on_connect__(client_id)
        except Exception as e:
            print(f"on_connect error: {str(e)}")
    
        self.client_num += 1

        return client_id

    async def on_disconnect(self, client_id):
        client = self.clients[client_id]
        print(f'client {client.id, client.ip} disconnected')
        self.clients.pop(client.id, None)

        try:
            self.__user_on_disconnect__(client.id)
        except Exception as e:
            print(f"on_disconnect error: {str(e)}")

    async def on_receive(self, data, client_id):
        if isinstance(data, str):
            # print(f"Received string ({client_id}): {data}")
            if data.startswith('SET+'):
                data = data[4:]
                try:
                    data = json.loads(data)
                except Exception as e:
                    await self.response('ERROR', ['Invalid json format', f'{e}'] )
                try:
                    self.__user_on_device_config__(data)
                except Exception as e:
                    print(f"on_io_data error: {str(e)}")
                await self.response('OK')
            if data.startswith('DATA+'):
                data = data[5:]
                try:
                    data = json.loads(data)
                except Exception as e:
                    await self.response('ERROR', ['Invalid json format', f'{e}'] )
                try:
                    self.__user_on_io_data__(data)
                except Exception as e:
                    print(f"on_io_data error: {str(e)}")
            else:
                await self.response('ERROR', ['Invalid command format'])

    async def receive_message(self, websocket, client_id):
        try:
            async for message in websocket:
                await self.on_receive(message, client_id)
        except websockets.exceptions.ConnectionClosedError as e:
            print(f'Client {client_id} disconnected: {e}')

    async def websocket_loop(self, websocket):
        client_id = await self.on_connect(websocket)

        try:
            await self.receive_message(websocket, client_id)
        finally:
            await self.on_disconnect(client_id)

    def start(self):
        self.running = True
        self.server_thread = threading.Thread(target=self.server_run)
        self.server_thread.daemon = True
        self.server_thread.start()
        self.broadcast_thread = threading.Thread(target=self.run_broadcast)
        self.broadcast_thread.start()

    def run_broadcast(self):
        self.broadcast_loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.broadcast_loop)
        self.broadcast_loop.run_until_complete(self.broadcast_io_data())

    async def broadcast_io_data(self):
        """Broadcast sensor data to all connected clients."""
        while self.running:
            if len(self.io_data) == 0:
                await asyncio.sleep(self.data_interval/1000)
                continue

            if len(self.clients) == 0:
                await asyncio.sleep(self.data_interval/1000)
                continue

            data = { "io_data": self.io_data }
            data = json.dumps(data)
            # print(f'broadcast data: {data}')

            # 遍历所有客户端广播
            await self.send_all(data)
            self.io_data = {}
            
            await asyncio.sleep(self.data_interval/1000)

    def close(self):
        self.server.close()
        self.running = False
        while len(self.clients):
            time.sleep(0.01)
        print('close done')

    def server_run(self):
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)
        self.loop.run_until_complete(self.main())

    async def send_all(self, data):
        tasks = []
        for client_id in self.clients:
            tasks.append(self.send(data, client_id))
        if tasks:
            await asyncio.gather(*tasks)

    async def send(self, data, client_id):
        client = self.clients.get(client_id)
        try:
            await client.websocket.send(data)
        except websockets.exceptions.ConnectionClosedError as e:
            print(f'Client {client_id} disconnected: {e}')
            self.on_disconnect(client_id)
        except websockets.exceptions.ConnectionClosedOK as e:
            self.on_disconnect(client_id)
        except RuntimeError as e:
            self.on_disconnect(client_id)

    async def response(self, status, error=[], data={}):
        _response = {
            'status': status,
            'error': error,
            'data': data
        }
        await self.send_all(json.dumps(_response))

    async def main(self):
        self.server = await websockets.serve(self.websocket_loop, "0.0.0.0", self.port)
        print(f'websocket server start at port {self.port}')
        async with self.server:
            await asyncio.Future() # run forever
        print('server closed')







     



                    





