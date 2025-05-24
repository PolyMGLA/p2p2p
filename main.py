import argparse
import asyncio
from node import Node

async def main(node: Node):
    print(f"connecting to {network_host}:{network_port}")
    await node.connect(network_host, network_port)

    await node.send(b"connected")
    
    await node.start_server()

if __name__ == "__main__":
    parser = argparse.ArgumentParser("P2P2P", "python main.py [user_host] [user_port] [network_host] [network_port]")
    parser.add_argument("user_host", type=str, help="your host")
    parser.add_argument("user_port", type=int, help="your port")
    parser.add_argument("network_host", type=str, help="network host")
    parser.add_argument("network_port", type=int, help="network port")

    args = parser.parse_args()
    user_host, user_port, network_host, network_port = args.user_host, args.user_port, args.network_host, args.network_port
    node = Node(user_host, user_port)

    asyncio.run(main(node))