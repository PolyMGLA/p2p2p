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
    parent: RemoteNode
    user_host: str
    user_port: int
    connected_list: list[RemoteNode]
    stop_event: asyncio.Event
    messages: list[tuple]
    listening_task: asyncio.Task

    def __init__(self, host: str, port: int):
        self.user_host = host
        self.user_port = port
        self.connected_list = []
        self.messages = []
        self.listening_task = None

    async def connect(self, host: str, port: int):
        peer = (host, port)

        reader, writer = await asyncio.open_connection(*peer)
        self.parent = RemoteNode(peer, reader, writer)

        self.is_connected = True
        
        self.listening_task = asyncio.create_task(self.listen_server())

    async def disconnect(self):
        if self.is_connected:
            self.parent.writer.close()
            self.is_connected = False
            self.listening_task.cancel()


    async def listen_server(self):
        try:
            while self.is_connected:
                data = await self.parent.reader.read(1024)
                if not data:
                    self.is_connected = False
                    self.messages.append(("disconnected", self.parent.peer, "connection closed by server"))
                    break
                
                messages = list(map(lambda x: x.decode(), data.split(b"\x00")))
                for msg in messages:
                    if msg == "":
                        continue
                    elif msg == "heartbeat":
                        self.parent.time = TIMEOUT
                    else:
                        self.messages.append(("message", self.parent.peer, msg))
                self.parent.time = max(0, self.parent.time - 1)
                if not self.parent.time:
                    self.is_connected = False
                    self.messages.append(("disconnected", self.parent.peer, "connection closed by server"))
                    break

                await self.send_ping()

                await asyncio.sleep(0.1)
        except Exception as e:
            self.messages.append(("error", self.parent.peer, f"listening error: {str(e)}"))
            self.is_connected = False
            

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
                removing = []
                
                for user in self.connected_list:
                    if user.writer.is_closing() or user.time == 0:
                        self.messages.append(("disconnected", user.peer, ""))
                        removing.append(user)
                        continue

                    data = await user.get(1024)
                    data = list(map(lambda x: x.decode(), data.split(b"\x00")))

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
            self.messages.append(("error", (), str(e)))
        finally:
            self.server.close()
            await self.disconnect()
            await self.server.wait_closed()

    async def stop_server(self):
        self.stop_event.set()

    async def send(self, message: bytes):
        self.parent.writer.write(message + b"\x00")

        await self.parent.writer.drain()

    async def get(self, count: int):
        return await self.parent.reader.read(count)
    
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
            print("connected to server", self.parent.peer, self.parent.time)
        else:
            print("not connected to any server")
        
        printf("connected users", 40)
        for el in self.connected_list:
            print(el.peer, el.time)