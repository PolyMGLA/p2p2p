import asyncio
import socket

TIMEOUT = 100

class Node:
    is_connected: bool = False
    user_host: str
    user_port: int
    conn_host: str
    conn_port: int
    connected_list: list[tuple[str, int], asyncio.StreamReader, asyncio.StreamWriter, int]
    reader: asyncio.StreamReader
    writer: asyncio.StreamWriter
    stop_event: asyncio.Event

    def __init__(self, host: str, port: int):
        self.user_host = host
        self.user_port = port
        self.connected_list = []

    async def connect(self, host: str, port: int):
        self.conn_host = host
        self.conn_port = port

        self.reader, self.writer = await asyncio.open_connection(self.conn_host, self.conn_port)
        self.is_connected = True

    async def client_connected_cb(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
        peername = writer.get_extra_info("peername")
        print("connected", peername)
        self.connected_list.append([peername, reader, writer, TIMEOUT])

        writer.write(f"connected {len(self.connected_list)}".encode())

        await writer.drain()

    async def start_server(self):
        self.server = await asyncio.start_server(self.client_connected_cb, self.user_host, self.user_port)

        self.stop_event = asyncio.Event()

        try:
            while not self.stop_event.is_set():
                if self.is_connected:
                    await self.send_ping()
                for user in self.connected_list:
                    if user[3] <= 0:
                        print("disconnected", user[0])
                        self.connected_list.remove(user)
                        continue

                    data = list(map(lambda x: x.decode(), (await user[1].read(128)).split(b"\x00")))
                    while "" in data:
                        data.remove("")
                    
                    messages = []

                    for el in data:
                        if el == "heartbeat":
                            user[3] = TIMEOUT
                        else:
                            messages.append(el)
                    
                    if len(messages) > 0:
                        print(user[0], messages, user[3])
                    user[3] -= 1

                await asyncio.sleep(0.1)
        except Exception as e:
            print(e)
        finally:
            self.server.close()
            await self.server.wait_closed()

    async def stop_server(self):
        self.stop_event.set()

    async def send(self, message: bytes):
        self.writer.write(message + b"\x00")

        await self.writer.drain()

    async def get(self, count: int):
        return await self.reader.read(count)
    
    async def send_ping(self):
        await self.send(b"heartbeat")