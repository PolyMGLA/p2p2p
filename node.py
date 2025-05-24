import asyncio
import socket
import os
from utils import printf

TIMEOUT = 101

class RemoteNode:
    peer: tuple[str, int]
    reader: asyncio.StreamReader
    writer: asyncio.StreamWriter
    time: int

    def __init__(self,
                 peer: tuple[str, int],
                 reader: asyncio.StreamReader,
                 writer: asyncio.StreamWriter):
        self.peer = peer
        self.reader = reader
        self.writer = writer
        self.time = TIMEOUT

    async def send(self, msg: bytes):
        self.writer.write(msg + b"\x00")

        await self.writer.drain()

    async def get(self, count: int):
        return await self.reader.read(count)


class Node:
    is_connected: bool = False
    user_host: str
    user_port: int
    peer: tuple[str, int]
    connected_list: list[RemoteNode]
    reader: asyncio.StreamReader
    writer: asyncio.StreamWriter
    stop_event: asyncio.Event
    messages: list[tuple]

    def __init__(self, host: str, port: int):
        self.user_host = host
        self.user_port = port
        self.connected_list = []
        self.messages = []

    async def connect(self, host: str, port: int):
        self.peer = (host, port)

        self.reader, self.writer = await asyncio.open_connection(*self.peer)
        self.is_connected = True

    async def client_connected_cb(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
        peername = writer.get_extra_info("peername")

        node = RemoteNode(peername, reader, writer)
        self.connected_list.append(node)

        await node.send(f"connected {len(self.connected_list)}\x00".encode())

    async def start_server(self):
        self.server = await asyncio.start_server(self.client_connected_cb, self.user_host, self.user_port)

        self.stop_event = asyncio.Event()

        try:
            while not self.stop_event.is_set():
                if self.is_connected:
                    await self.send_ping()
                    # msg = list(map(lambda x: x.decode(), (await self.get(128)).split(b"\x00")))

                    # for el in msg:
                    #     if el == "":
                    #        pass
                    #     else:
                    #         self.messages.append(("message", self.peer, el))

                    # TODO: стопорит сервер, надо исправить ошибку, чтобы нода читала с self.reader, если можно
                
                removing = []
                
                for user in self.connected_list:
                    if user.time == 0:
                        self.messages.append(("disconnected", user.peer, ""))
                        removing.append(user)
                        continue

                    data = list(map(lambda x: x.decode(), (await user.get(128)).split(b"\x00")))

                    for el in data:
                        if el == "":
                            pass
                        elif el == "heartbeat":
                            user.time = TIMEOUT
                        else:
                            self.messages.append(("message", user.peer, el))
                    
                    user.time = max(0, user.time - 1)

                for user in removing:
                    self.connected_list.remove(user)

                await self.print_state()
                await asyncio.sleep(0.1)
        except (KeyboardInterrupt, asyncio.exceptions.CancelledError):
            print("closing")
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

    async def print_state(self):
        os.system("clear")
        printf("P2P2P client", 40)
        print("\n" * max(0, 9 - len(self.messages)))
        for el in self.messages[-10:]:
            print(el)
        printf("client data", 40)
        print("client:", (self.user_host, self.user_port))
        if self.is_connected:
            print("connected to server", self.peer)
        else:
            print("not connected to any server")
        
        printf("connected users", 40)
        for el in self.connected_list:
            print(el.peer, el.time)