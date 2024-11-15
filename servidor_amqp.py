import asyncio
import aio_pika


class TicTacToeServer:
    def __init__(self):
        self.connection = None
        self.channel = None
        self.game_queue = None
        self.players = []

    async def start(self):
        self.connection = await aio_pika.connect_robust(
            "amqps://pyfijodg:JIo29p_X4bz64DTLD9y-paeT38Azwy5_@jackal.rmq.cloudamqp.com/pyfijodg",
            loop=asyncio.get_event_loop()
        )

        self.channel = await self.connection.channel()
        self.game_queue = await self.channel.declare_queue("game_queue")

        await self.game_queue.consume(self.handle_message)

        print("Servidor iniciado. Aguardando jogadores...")

    async def handle_message(self, message: aio_pika.IncomingMessage):
        async with message.process():
            player_queue_name = message.body.decode()

            if player_queue_name not in self.players:
                self.players.append(player_queue_name)
                print(f"Jogador conectado: {player_queue_name}")

            if len(self.players) == 2:
                await self.send_game_start_message()
                await self.play_game()

    async def send_game_start_message(self):
        for player_queue_name in self.players:
            await self.channel.default_exchange.publish(
                aio_pika.Message(body="start".encode()),
                routing_key=player_queue_name
            )

    async def play_game(self):
        game_state = "         "
        self.current_player_index = 0

        while not self.is_game_over(game_state):
            current_player_queue = self.players[self.current_player_index]
            other_player_queue = self.players[1 - self.current_player_index]

            await self.channel.default_exchange.publish(
                aio_pika.Message(body=game_state.encode()),
                routing_key=current_player_queue
            )

            await self.channel.default_exchange.publish(
                aio_pika.Message(body="turn".encode()),
                routing_key=current_player_queue
            )

            message = await self.channel.default_exchange.get(
                routing_key=current_player_queue,
                no_ack=True
            )

            move = int(message.body.decode())

            if self.is_valid_move(move, game_state):
                game_state = self.update_game_state(move, game_state)
            else:
                await self.send_invalid_move_message()

            self.current_player_index = 1 - self.current_player_index

        await self.send_game_end_message()

    def is_game_over(self, game_state):
        return " " not in game_state

    def is_valid_move(self, move, game_state):
        return game_state[move] == " "

    def update_game_state(self, move, game_state):
        return game_state[:move] + "X" + game_state[move + 1:]

    async def send_invalid_move_message(self):
        current_player_queue = self.players[self.current_player_index]

        await self.channel.default_exchange.publish(
            aio_pika.Message(body="invalid_move".encode()),
            routing_key=current_player_queue
        )

    async def send_game_end_message(self):
        for player_queue_name in self.players:
            await self.channel.default_exchange.publish(
                aio_pika.Message(body="end".encode()),
                routing_key=player_queue_name
            )

    async def close(self):
        await self.connection.close()


def main():
    server = TicTacToeServer()
    asyncio.get_event_loop().run_until_complete(server.start())


if __name__ == "__main__":
    main()
