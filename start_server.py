import argparse
import asyncio
from node import Node


if __name__ == "__main__":
    parser = argparse.ArgumentParser("P2P2P", "python start_server.py [user_host] [user_port]")
    parser.add_argument("user_host", type=str, help="your host")
    parser.add_argument("user_port", type=int, help="your port")

    args = parser.parse_args()
    user_host, user_port = args.user_host, args.user_port
    node = Node(user_host, user_port)

    print(f"starting server")
    asyncio.run(node.start_server())