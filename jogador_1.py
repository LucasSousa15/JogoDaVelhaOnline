import asyncio
import aio_pika


class TicTacToePlayer:
    def __init__(self):
        self.connection = None
        self.channel = None
        self.player_queue = None

    async def start(self):
        self.connection = await aio_pika.connect_robust(
            "Seu servidor AMQP",
            loop=asyncio.get_event_loop()
        )

        self.channel = await self.connection.channel()
        self.player_queue = await self.channel.declare_queue("", exclusive=True)

        await self.channel.default_exchange.publish(
            aio_pika.Message(body=self.player_queue.name.encode()),
            routing_key="game_queue"
        )

        await self.player_queue.consume(self.handle_message)

        print("Aguardando jogo iniciar...")

    async def handle_message(self, message: aio_pika.IncomingMessage):
        async with message.process():
            message_body = message.body.decode()

            if message_body == "start":
                print("Jogo iniciado!")
            elif message_body == "turn":
                move = await self.get_valid_move()
                await self.channel.default_exchange.publish(
                    aio_pika.Message(body=str(move).encode()),
                    routing_key=self.player_queue.name
                )
            elif message_body == "end":
                print("Jogo encerrado!")
                await self.close()
            elif message_body == "invalid_move":
                print("Jogada inválida. Tente novamente.")
            else:
                print_game_state(message_body)

    async def get_valid_move(self):
        while True:
            move = input("Sua vez de jogar. Escolha uma posição (0-8): ")
            if move.isdigit() and 0 <= int(move) <= 8:
                return int(move)

    async def close(self):
        await self.connection.close()


def print_game_state(game_state):
    board = [ch if ch != " " else str(idx) for idx, ch in enumerate(game_state)]
    print(f" {board[0]} | {board[1]} | {board[2]} ")
    print("---|---|---")
    print(f" {board[3]} | {board[4]} | {board[5]} ")
    print("---|---|---")
    print(f" {board[6]} | {board[7]} | {board[8]} ")


def main():
    player = TicTacToePlayer()
    asyncio.run(player.start())


if __name__ == "__main__":
    main()
