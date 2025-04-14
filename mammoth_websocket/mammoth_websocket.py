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

    return list(struct.unpack(f'{endian_prefix}{format_char}', bytes(byte_list)))


class MammothWebSocket():

    DEFAULT_PORT = 30102

    def __init__(self, port=DEFAULT_PORT):
        self.port = port
        self.server_thread = threading.Thread(target=self.server_run)
        self.server_thread.daemon = True
        self.client_num = 0
        self.clients = {}
        self.is_received = False
        self.send_dict = {}
        self.device_info = {}
        self.on_receive = None
        self.on_connect = None
        self.on_disconnect = None
        self.last_rev_time = 0

    def start(self):
        self.work_flag = True
        self.server_thread.start()

    def close(self):
        self.server.close()
        self.work_flag = False
        # print('close done1')
        # print( self.server_thread.is_alive())
        # self.server_thread.join()
        while len(self.clients):
            time.sleep(0.01)
        print('close done')

    def server_run(self):
        asyncio.run(self.main())

    async def main(self):
        self.server = await websockets.serve(self.websocket_loop, "0.0.0.0", self.port)
        print(f'websocket server start at port {self.port}')
        async with self.server:
            await asyncio.Future() # run forever
        print('server closed')

    async def websocket_loop(self, websocket):
        _client_id = str(self.client_num)
        _client_ip = websocket.remote_address[0]
        _client = {
            'id': _client_id,
            'ip': _client_ip,
            'websocket': websocket,
        }
        self.client_num  += 1
        self.clients[str(_client_id)] = _client
        print(f'client {_client_id, _client_ip} conneted')

        ## send_device_info
        await websocket.send(json.dumps(self.device_info))

        if self.on_connect != None:
            self.on_connect()

        try:
            # listen messages loop
            async for message in websocket:
                print(f'{time.time()-self.last_rev_time:.5f} {_client_id}: {message}')
                self.last_rev_time = time.time()
                if self.on_receive != None:
                    await self.on_receive(message, _client_id)
                # await websocket.send('ok')
                
            # disconneted normally
            print(f'client {_client_id, _client_ip} disconneted normally.')

        ## disconneted with error
        except websockets.exceptions.ConnectionClosedError as e:
            print(f'client {_client_id, _client_ip} disconneted with error:\n{e.code}:{e.reason}')
            
        ## disconneted handler
        if self.on_disconnect != None:
            self.on_disconnect()

        ## remove client
        self.clients.pop(str(_client_id))


    async def asyn_send(self, data, client_num=None):
        ## define send single client function
        async def _send_work(client_num, data):
            client = self.clients[str(client_num)]
            try:
                await client['websocket'].send(data) 
            except websockets.exceptions.ConnectionClosed as connection_code:
                print(f'{client_num}: {connection_code}')
                _ip = client['ip']
                print(f'client {client_num, _ip} disconneted')
                self.clients.pop(str(client_num))

        ## send data
        if len(self.clients) > 0:
            # send all clients
            if client_num is None:
                await asyncio.gather(
                    *[_send_work(client_num, data) for client_num in self.clients.keys()]
                )
            # send to single client with client_num
            else: 
                await _send_work(client_num, data)

            # print('send data: %s'%data)


    async def response(self, status, error=[], data={}):
        _response = {
            'status': status,
            'error': error,
            'data': data
        }
        await self.asyn_send(json.dumps(_response))
    
    def send(self, data, client_num=None):
        asyncio.run(self.asyn_send(data, client_num))


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
        for key, value in entities.items():
            _id = value['id']
            _value = []

            if not isinstance(value['value'], list):
                value['value'] = [value['value']]

            print(f'{key}: {value["value"]}')
            _value.extend(numbers_to_bytes(value['value'], value['type']))
            data += [_id] + _value

        ## calculate checksum
        checksum = 0
        for d in data:
            checksum ^= d

        ## pack data
        data = [START] + [len(data)] + [checksum] + data + [END]
        data_hex = [f'0x{d:02x}' for d in data]
        # print(f'data_hex: {data_hex}')
        return bytes(data)

    def bytes_to_entities(self, entities, data):
        START = 0xA0
        END = 0xA1
        MIN_LEN = 6

        # print(f'data: {data}, {type(data)}')
        data = list(data)
        data_hex = [f'0x{d:02x}' for d in data]
        # print(f'data hex: {data_hex}')
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
            if _id not in entities['id'].keys():
                print(f'entity id not found: {_id}')
                index += 1
                continue

            # print(f'_id: {_id}', end='\t')
            _name = entities['id'][_id]
            _len = entities[_name]['len']
            _types = entities[_name]['type']
            _data = entities_data[index+1:index+1+_len]
            entities[_name]['value'] = bytes_to_numbers(_data, _types)
            index += _len + 1
            print(f'{_name}: {entities[_name]["value"]}')

            _entities_temp[_name] = entities[_name]

        return _entities_temp
        # print(f'entities ({id(entities)}): {entities}')









     



                    





