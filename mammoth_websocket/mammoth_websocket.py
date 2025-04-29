import asyncio
import websockets
import json
import time
import threading
import struct


def numbers_to_bytes(data, data_types, endianness='big'):
    data = [int(x) for x in data]
    format_char = ''
    for data_type in data_types:
        if data_type == 'uint8':
            format_char += 'B'
        elif data_type == 'int8':
            format_char += 'b'
        elif data_type == 'uint16':
            format_char += 'H'
        elif data_type == 'int16':
            format_char += 'h'
        elif data_type == 'uint32':
            format_char += 'I'
        elif data_type == 'int32':
            format_char += 'i'
        else:
            raise ValueError("Unsupported data type. Supported types are 'uint8', 'int8',"
                         "'uint16', 'int16', uint32', and 'int32'.")

    if endianness == 'big':
        endian_prefix = '>'
    elif endianness == 'little':
        endian_prefix = '<'
    else:
        raise ValueError("Unsupported endianness. Use 'big' or 'little'.")

    packed = struct.pack(f'{endian_prefix}{format_char}', *data)
    return [byte for byte in packed]


def bytes_to_numbers(byte_list, data_types, endianness='big'):
    format_char = ''
    for data_type in data_types:
        if data_type == 'uint8':
            format_char += 'B'
        elif data_type == 'int8':
            format_char += 'b'
        elif data_type == 'uint16':
            format_char += 'H'
        elif data_type == 'int16':
            format_char += 'h'
        elif data_type == 'uint32':
            format_char += 'I'
        elif data_type == 'int32':
            format_char += 'i'
        else:
            raise ValueError("Unsupported data type. Supported types are 'uint8', 'int8',"
                         "'uint16', 'int16', uint32', and 'int32'.")
        
    if endianness == 'big':
        endian_prefix = '>'
    elif endianness == 'little':
        endian_prefix = '<'
    else:
        raise ValueError("Unsupported endianness. Use 'big' or 'little'.")

    # 使用struct模块打包二进制数据
    format_str = f'{endian_prefix}{format_char}'
    try:
        packed = struct.pack(format_str, *data)
    except struct.error as e:
        raise ValueError(f"Data packing error: {e}") from None
    
    return list(packed)  # 直接返回struct打包后的字


class MammothWebSocket():

    DEFAULT_PORT = 30102

    def __init__(self, port=DEFAULT_PORT, data_interval=20):
        self.port = port
        self.server_thread = threading.Thread(target=self.server_run)
        self.server_thread.daemon = True
        self.clients = {}
        self.is_received = False
        self.send_dict = {}
        self.device_info = {}
        self.on_device_config = lambda x: None
        self.on_io_data = lambda x: None
        self.command_entities = None
        self.sensor_entities = None
        self.on_connect = None
        self.on_disconnect = None
        self.last_rev_time = 0
        self.loop = None  # 新增事件循环引用
        self.data_interval = data_interval
        self.client_num = 0
        self.broadcast_task = None

    def start(self):
        self.running = True
        self.server_thread.start()
        self.broadcast_task = threading.Thread(target=self.run_broadcast)
        self.broadcast_task.start()

    def run_broadcast(self):
        self.broadcast_loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.broadcast_loop)
        self.broadcast_loop.run_until_complete(self.broadcast_sensor_data())

    async def broadcast_sensor_data(self):
        """Broadcast sensor data to all connected clients."""
        while self.running:
            # try:
            # 添加数据有效性检查
            if not self.sensor_entities:
                print("Sensor entities not initialized")
                await asyncio.sleep(1)
                continue
            
            # 生成传感器数据
            with self.sensor_entities.data_lock:
                data = self.entities_to_bytes(self.sensor_entities)
            
            if len(data) == 0:
                await asyncio.sleep(self.data_interval/1000)

            if len(self.clients) == 0:
                await asyncio.sleep(self.data_interval/1000)
                continue
            
            # print(f"Broadcasting data: {' '.join([f'{x:02x}' for x in data])}")

            # 遍历所有客户端广播
            tasks = []
            for client_id in self.clients:  
                tasks.append(self.send(data, client_id))
            if tasks:
                await asyncio.gather(*tasks)

            self.sensor_entities.clear_datas()
            
            await asyncio.sleep(self.data_interval/1000)
            # except Exception as e:
            #     print(f"Broadcast error: {str(e)}")

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

    async def on_receive(self, data, client_id):
        # command
        if isinstance(data, str):
            # print(f"Received string ({client_id}): {data}")
            if data.startswith('SET+'):
                try:
                    data = data[4:]
                    data = json.loads(data)
                    self.on_device_config(data)
                    await self.response('OK')
                except Exception as e:
                    await self.response('ERROR', ['Invalid json format', f'{e}'] )
            else:
                await self.response('ERROR', ['Invalid command format'])

        # data
        elif isinstance(data, bytes):
            # read command
            if self.command_entities is None:
                await self.response('ERROR', ['command_entities is None'])
                return
            data = self.bytes_to_entities(self.command_entities, data)
            if isinstance(data, dict):
                # handle command
                self.on_io_data(data)
            else:
                print(f"Invalid command format ({client_id}): {data}")

    async def _on_connect(self, websocket):
        client_id = self.client_num
        client_ip = websocket.remote_address[0]
        client = {
            'id': client_id,
            'ip': client_ip,
            'websocket': websocket,
        }
        self.clients[client_id] = client

        print(f'client {client_id, client_ip} connected')

        # Send device info
        await websocket.send(json.dumps(self.device_info))

        if self.on_connect is not None:
            self.on_connect()
    
        self.client_num += 1

        return client_id

    async def _on_disconnect(self, client_id):
        client = self.clients[client_id]
        client_ip = client['ip']
        print(f'client {client_id, client_ip} disconnected')
        self.clients.pop(client_id, None)

        if self.on_disconnect is not None:
            self.on_disconnect()

    async def receive_message(self, websocket, client_id):
        try:
            async for message in websocket:
                # print(f'{time.time()-self.last_rev_time:.5f} {_client_id}: {message}')
                self.last_rev_time = time.time()
                if self.on_receive != None:
                    await self.on_receive(message, client_id)
                # await websocket.send('ok')
        except websockets.exceptions.ConnectionClosedError as e:
            print(f'Client {client_id} disconnected: {e}')

    async def websocket_loop(self, websocket):
        client_id = await self._on_connect(websocket)

        try:
            await self.receive_message(websocket, client_id)
        finally:
            await self._on_disconnect(client_id)

    async def send(self, data, client_id):
        client = self.clients.get(client_id)
        try:
            await client['websocket'].send(data)
        except websockets.exceptions.ConnectionClosedError as e:
            print(f'Client {client_id} disconnected: {e}')
            self._on_disconnect(client_id)

    # async def send_sensor_data(self):
    #     # for id, sensor in self.sensor_entities.ids.items():
    #     #     print(f'{sensor.name}: {sensor.values}')
    #     data = self.entities_to_bytes(self.sensor_entities)
        
    #     await self.async_send(data)

    async def response(self, status, error=[], data={}):
        _response = {
            'status': status,
            'error': error,
            'data': data
        }
        await self.async_send(json.dumps(_response))
    
    # def send(self, data, client_id=None):
    #     asyncio.run(self.async_send(data, client_id))

    def entities_to_bytes(self, entities):
        '''
        data format:

        |    0   |   1  |   2    |   3    |     4     |  ...  |    ...    |  ...   |    ...    |  ...  |    -2     |    -1    |
        | :----: | :---:| :----: | :----: | :-------: | :---: | :-------: | :----: | :-------: | :---: | :-------: | :------: |
        |  START | len  |checksum| entity_id | entity_date_0 |  ...  | entity_date_n | entity_id | entity_date_0 |  ...  | entity_date_n | END |

        START: 0xA0
        END: 0xA1
        len: Except START, checksum, END
        checksum: XOR of entity, except START, checksum, END
        '''
        START = 0xA0
        END = 0xA1
        data = []
        ## fix data buffer
        for _id, entity in entities.ids.items():
            result = []
            if entity.values is None:
                continue

            if 'str' in entity.types:
                string = entity.values
                print(f'string: {string}')
                if len(string) > 0:
                    string_bytes = bytes(string, 'utf-8')
                    print(f'string_bytes: {" ".join([f"0x{d:02x}" for d in string_bytes])}')
                    byte_length = len(string_bytes)
                    print(f'byte_length: {byte_length}')
                    result.extend(numbers_to_bytes([byte_length], [entity.types[0]]))
                    result.extend(string_bytes)
            else:
                result.extend(numbers_to_bytes(entity.values, entity.types))
            data += [_id] + result

        ## calculate checksum
        checksum = 0
        for d in data:
            checksum ^= d

        if len(data) == 0:
            return []

        ## pack data
        data = [START] + [len(data)] + [checksum] + data + [END]
        print(f'data_hex: {[f'0x{d:02x}' for d in data]}')
        return bytes(data)

    def bytes_to_entities(self, entities, data):
        START = 0xA0
        END = 0xA1
        MIN_LEN = 6

        data = list(data)
        print(f'data hex: {" ".join([f"0x{d:02x}" for d in data])}')
        result = {}
        if len(data) < MIN_LEN:
            print('data length error')
            return False

        _start = data[0]
        _data_len = data[1]
        checksum = data[2]
        entities_data = data[3:-1]
        _end = data[-1]

        # check start and end
        if _start != START or _end != END:
            print('start or end code error')
            return False

        # check data length
        if _data_len != len(entities_data):
            print('data length error')
            return False

        # calcualate checksum
        checksum_temp = 0
        for d in entities_data:
            checksum_temp ^= d

        # print(f'checksum: {checksum}, {checksum_temp}')
        if checksum != checksum_temp:
            print('checksum error')
            return False

        # unpack data
        index = 0
        _entities_temp = {}
        while (index < _data_len):
            _id = entities_data[index]
            if _id not in entities.ids.keys():
                print(f'entity id not found: {_id}')
                index += 1
                continue

            # print(f'_id: {_id}', end='\t')
            entity = entities.ids[_id]
            _len = entity.length
            _types = entity.types
            _data = entities_data[index+1:index+1+_len]
            index += _len + 1
            if 'str' in _types:
                _temp_types = _types.copy()
                _temp_types.remove('str')
                _strlen = bytes_to_numbers(_data, _temp_types)[0]
                _data = entities_data[index:index+_strlen]
                # _data = ''.join([d.decode('utf-8') for d in _data])
                _data = bytes(_data).decode('utf-8')
                index += _strlen
                result[entity.name] = _data
            else:
                _data = bytes_to_numbers(_data, _types)
                result[entity.name] = _data
        return result

    async def main(self):
        self.server = await websockets.serve(self.websocket_loop, "0.0.0.0", self.port)
        print(f'websocket server start at port {self.port}')
        async with self.server:
            await asyncio.Future() # run forever
        print('server closed')









     



                    





