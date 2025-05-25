import asyncio
import os
import traceback
from utils import printf, get_error_context

TIMEOUT = 101
messages: list[tuple] = []
netExceptions = (BrokenPipeError, ConnectionResetError, ConnectionAbortedError,
                asyncio.TimeoutError, OSError)

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

    async def send(self, msg: bytes) -> bool:
        try:
            if not await self.is_connection_alive(): return b""
            self.writer.write(msg + b"\x00")

            await self.writer.drain()

            return True
        except netExceptions:
            return False
        except Exception as e:
            context = get_error_context()
            messages.append(("error", (), str(e), context, traceback.format_exc()))
            return False

    async def get(self, count: int, timeout=0.1) -> bytes:
        try:
            if not await self.is_connection_alive(): return b""
            return await asyncio.wait_for(self.reader.read(count), timeout=timeout)
        except netExceptions:
            return b""
        except Exception as e:
            context = get_error_context()
            messages.append(("error", (), str(e), context, traceback.format_exc()))
            return b""
        
    async def send_ping(self):
        return await self.send(b"heartbeat")
    
    async def is_connection_alive(self) -> bool:
        try:
            if self.writer.is_closing() or self.writer.transport.is_closing():
                return False
            data = await self.reader.read(0)
            return True
        except netExceptions:
            return False
        except Exception as e:
            context = get_error_context()
            messages.append(("error", (), str(e), context, traceback.format_exc()))
            return False
        
    async def close_connection(self):
        self.writer.close()


class Node:
    is_connected: bool = False
    parent: RemoteNode
    user_host: str
    user_port: int
    connected_list: list[RemoteNode]
    stop_event: asyncio.Event

    def __init__(self, host: str, port: int):
        self.user_host = host
        self.user_port = port
        self.connected_list = []

    async def connect(self, host: str, port: int) -> bool:
        try:
            peer = (host, port)

            reader, writer = await asyncio.open_connection(*peer)
            self.parent = RemoteNode(peer, reader, writer)

            await self.parent.send(b"connected")

            self.is_connected = True
            return True
        except netExceptions:
            messages.append(("not connected", (), "failed to connect to server"))
            return False
        except Exception as e:
            context = get_error_context()
            messages.append(("error", (), str(e), context, traceback.format_exc()))
            return False

    async def disconnect(self):
        if self.is_connected:
            self.parent.writer.close()
            self.is_connected = False

    async def client_connected_cb(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
        try:
            peername = writer.get_extra_info("peername")

            node = RemoteNode(peername, reader, writer)
            self.connected_list.append(node)

            await node.send(f"connected {len(self.connected_list)}\x00".encode())
        except Exception as e:
            context = get_error_context()
            messages.append(("error", (), str(e), context, traceback.format_exc()))


    async def start_server(self):
        self.server = await asyncio.start_server(self.client_connected_cb, self.user_host, self.user_port)
        
        self.stop_event = asyncio.Event()

        try:
            while not self.stop_event.is_set():
                if self.is_connected:
                    if not self.parent.time:
                        self.is_connected = False
                        messages.append(("disconnected", self.parent.peer, "connection closed by server"))

                if self.is_connected:
                    data = await self.parent.get(1024)
                    
                    msgs = list(map(lambda x: x.decode(), data.split(b"\x00")))
                    for msg in msgs:
                        if msg == "":
                            continue
                        elif msg == "heartbeat":
                            self.parent.time = TIMEOUT
                        else:
                            messages.append(("message", self.parent.peer, msg))
                    self.parent.time = max(0, self.parent.time - 1)

                    await self.parent.send_ping()

                removing = []
                
                for user in self.connected_list:
                    if user.time == 0:
                        messages.append(("disconnected", user.peer, ""))
                        removing.append(user)
                        continue

                    await user.send_ping()

                    data = await user.get(1024)

                    data = list(map(lambda x: x.decode(), data.split(b"\x00")))

                    for el in data:
                        if el == "":
                            pass
                        elif el == "heartbeat":
                            user.time = TIMEOUT
                        else:
                            messages.append(("message", user.peer, el))
                    
                    user.time = max(0, user.time - 1)

                for user in removing:
                    self.connected_list.remove(user)

                await self.print_state()
                await asyncio.sleep(0.1)
        except (KeyboardInterrupt, asyncio.exceptions.CancelledError):
            messages.append(("closing", (), "closing"))
            await self.stop_server()
        except Exception as e:
            context = get_error_context()
            messages.append(("error", (), str(e), context, traceback.format_exc()))
            await self.stop_server()
        finally:
            await self.close_connections()
            await self.print_state()
            self.server.close()
            await self.disconnect()
            await self.server.wait_closed()

    async def stop_server(self):
        self.stop_event.set()

    async def close_connections(self):
        if self.is_connected:
            await self.parent.close_connection()

        for user in self.connected_list:
            await user.close_connection()

    async def print_state(self):
        global messages
        
        os.system("clear")
        printf("P2P2P client", 40)
        print("\n" * max(0, 9 - len(messages)))
        messages = messages[-10:]
        for el in messages:
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