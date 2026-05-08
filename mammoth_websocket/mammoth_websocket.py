import asyncio
import websockets
import json
import threading
import time

class MammothWebSocket():

    DEFAULT_PORT = 30102
    DEFAULT_PING_TIMEOUT = 30  # 默认 ping 超时时间（秒）
    DEFAULT_PING_CHECK_INTERVAL = 5  # 默认检查间隔（秒）
    DEFAULT_DATA_TIMEOUT = 3  # 默认数据超时时间（秒）

    def __init__(self, port=DEFAULT_PORT, ping_timeout=DEFAULT_PING_TIMEOUT, 
                 ping_check_interval=DEFAULT_PING_CHECK_INTERVAL, 
                 data_timeout=DEFAULT_DATA_TIMEOUT):
        self.port = port
        self.ping_timeout = ping_timeout
        self.ping_check_interval = ping_check_interval
        self.data_timeout = data_timeout
        self.websockets = {}
        self._last_activity = {}  # 记录每个客户端最后活动时间
        self._last_data_time = None  # 记录最后一次收到数据的时间
        self._data_paused = False  # 数据暂停状态标志
        self.client_ips = []
        self.server_thread = None
        self.server = None
        self.__user_on_device_config__ = None
        self.__user_on_io_data__ = None
        self.__user_on_connect__ = None
        self.__user_on_disconnect__ = None
        self.__user_on_data_timeout__ = None  # 数据超时回调
        self.__user_on_data_resume__ = None  # 数据恢复回调
        self.__device_info__ = {}
        self._timeout_check_task = None

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

    def set_data_timeout_handler(self, on_data_timeout):
        """设置数据超时回调函数"""
        self.__user_on_data_timeout__ = on_data_timeout

    def set_data_resume_handler(self, on_data_resume):
        """设置数据恢复回调函数"""
        self.__user_on_data_resume__ = on_data_resume

    def is_connected(self, ip=None):
        if ip is None:
            return len(self.websockets) > 0
        else:
            return ip in self.websockets

    def is_data_paused(self):
        """返回当前是否处于数据暂停状态"""
        return self._data_paused

    async def handle_connect(self, websocket):
        ip = websocket.remote_address[0]
        if ip in self.websockets:
            return False
        self.websockets[ip] = websocket
        self._last_activity[ip] = time.time()  # 记录连接时间

        # Send device info
        await websocket.send(json.dumps(self.__device_info__))

        if self.__user_on_connect__:
            await self.__user_on_connect__(ip)
        return True

    async def handle_disconnect(self, websocket):
        ip = websocket.remote_address[0]
        if ip in self.websockets:
            del self.websockets[ip]
            self._last_activity.pop(ip, None)  # 清理活动时间记录
            print(f'client {ip} disconnected')

            if self.__user_on_disconnect__:
                await self.__user_on_disconnect__(ip)

    async def handle_receive(self, data):
        # print(f'received: {data}')
        if isinstance(data, str):
            # print("Handle string data")
            if data == "ping":
                await self.send(f'pong{time.time()}')
            elif data.startswith('SET+'):
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
                self._last_data_time = time.time()  # 更新最后数据时间
                if self._data_paused:
                    self._data_paused = False
                    if self.__user_on_data_resume__:
                        await self.__user_on_data_resume__()
                if self.__user_on_io_data__:
                    await self.__user_on_io_data__(data)
            else:
                await self.response('ERROR', ['Invalid command format'])

    async def process_received_messages(self, websocket):
        ip = websocket.remote_address[0]
        try:
            async for message in websocket:
                self._last_activity[ip] = time.time()  # 更新活动时间
                await self.handle_receive(message)
        except websockets.exceptions.ConnectionClosedError as e:
            await self.handle_disconnect(websocket)

    async def websocket_connection_loop(self, websocket):
        if not await self.handle_connect(websocket):
            return False
        try:
            await self.process_received_messages(websocket)
        finally:
            await self.handle_disconnect(websocket)

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

        self.websockets = {}
        self._last_activity = {}
        self._last_data_time = None
        self._data_paused = False
        self.server = None

    def run_server_in_thread(self):
        try:
            asyncio.run(self.main())
        except Exception as e:
            print(f"Server thread error: {e}")

    async def send(self, data):
        for websocket in list(self.websockets.values()):
            try:
                await websocket.send(data)
            except websockets.exceptions.ConnectionClosedError as e:
                await self.handle_disconnect(websocket)
                continue
            except websockets.exceptions.ConnectionClosedOK as e:
                await self.handle_disconnect(websocket)
                continue
            except RuntimeError as e:
                await self.handle_disconnect(websocket)
                continue

    async def response(self, status, error=[], data={}):
        _response = {
            'status': status,
            'error': error,
            'data': data
        }
        await self.send(json.dumps(_response))

    async def _check_timeout_loop(self):
        """定期检查客户端超时和数据超时"""
        while True:
            await asyncio.sleep(self.ping_check_interval)
            now = time.time()

            # 检查客户端 ping 超时
            timeout_clients = []
            for ip, last_time in list(self._last_activity.items()):
                if now - last_time > self.ping_timeout:
                    timeout_clients.append(ip)

            for ip in timeout_clients:
                websocket = self.websockets.get(ip)
                if websocket:
                    print(f'client {ip} timeout, closing connection')
                    try:
                        await websocket.close(code=1001, reason="Ping timeout")
                    except Exception:
                        pass
                    await self.handle_disconnect(websocket)

            # 检查数据超时（仅当有客户端连接时）
            if len(self.websockets) > 0 and self._last_data_time is not None:
                if now - self._last_data_time > self.data_timeout and not self._data_paused:
                    self._data_paused = True
                    print(f'data timeout, all clients silent for {self.data_timeout}s')
                    if self.__user_on_data_timeout__:
                        await self.__user_on_data_timeout__()

    async def main(self):
        self.server = await websockets.serve(self.websocket_connection_loop, "0.0.0.0", self.port)
        print(f'websocket server start at port {self.port}')
        self._timeout_check_task = asyncio.create_task(self._check_timeout_loop())
        loop = asyncio.get_event_loop()  # 获取当前事件循环
        try:
            await self.server.serve_forever()  # 捕获 serve_forever 的取消异常
        except asyncio.CancelledError:
            print("Server Cancelled...")
        finally:
            if self._timeout_check_task:
                self._timeout_check_task.cancel()
            loop.stop()  # 显式停止事件循环