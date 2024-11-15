import asyncio
import aio_pika
import tkinter as tk


class RabbitMQManager:
    def __init__(self, player1_queue, player2_queue, on_message_callback):
        self.player1_queue = player1_queue
        self.player2_queue = player2_queue
        self.on_message_callback = on_message_callback
        self.connection = None
        self.channel = None
        self.game = None

    async def connect(self):
        self.connection = await aio_pika.connect_robust(
            "amqps://pyfijodg:JIo29p_X4bz64DTLD9y-paeT38Azwy5_@jackal.rmq.cloudamqp.com/pyfijodg",
            loop=asyncio.get_running_loop()
        )
        self.channel = await self.connection.channel()

    async def create_queues(self):
        await self.channel.declare_queue(self.player1_queue, auto_delete=True)
        await self.channel.declare_queue(self.player2_queue, auto_delete=True)

    async def start_consuming(self):
        await self.channel.set_qos(prefetch_count=1)
        await self.channel.consume(self.player1_queue, self.process_message)
        await self.channel.consume(self.player2_queue, self.process_message)

    async def process_message(self, message):
        async with message.process():
            player_id = message.headers.get("Player-Id")
            if player_id is not None:
                self.on_message_callback(player_id, message.body.decode())

    async def send_message(self, player_id, message):
        queue_name = self.player1_queue if player_id == "player1" else self.player2_queue
        properties = aio_pika.BasicProperties(headers={"Player-Id": player_id})
        await self.channel.default_exchange.publish(
            aio_pika.Message(body=message.encode(), properties=properties),
            routing_key=queue_name
        )

    async def close(self):
        await self.connection.close()


class TicTacToeGame:
    def __init__(self, player_id):
        self.player_id = player_id
        self.marker = "X" if player_id == "player1" else "O"
        self.board = [" "] * 9

    def set_rabbitmq_manager(self, rabbitmq_manager):
        self.rabbitmq_manager = rabbitmq_manager

    async def start_game(self):
        player1_queue = f"{self.player_id}_queue"
        player2_queue = f"{'player2' if self.player_id == 'player1' else 'player1'}_queue"

        self.rabbitmq_manager = RabbitMQManager(player1_queue, player2_queue, self.on_message_received)
        self.rabbitmq_manager.game = self
        await self.rabbitmq_manager.connect()
        await self.rabbitmq_manager.create_queues()
        await self.rabbitmq_manager.start_consuming()

    def on_message_received(self, player_id, message):
        move = int(message)
        if self.is_valid_move(move):
            self.update_board(move)
            self.print_board()
            if self.is_winner():
                print(f"Player {self.player_id} wins!")
                asyncio.create_task(self.rabbitmq_manager.close())
            elif self.is_draw():
                print("It's a draw!")
                asyncio.create_task(self.rabbitmq_manager.close())
            else:
                self.send_current_player_turn()

    def is_valid_move(self, move):
        return 0 <= move <= 8 and self.board[move] == " "

    def update_board(self, move):
        self.board[move] = self.marker

    def print_board(self):
        print(f" {self.board[0]} | {self.board[1]} | {self.board[2]} ")
        print("---+---+---")
        print(f" {self.board[3]} | {self.board[4]} | {self.board[5]} ")
        print("---+---+---")
        print(f" {self.board[6]} | {self.board[7]} | {self.board[8]} ")

    def send_current_player_turn(self):
        asyncio.create_task(self.get_next_move())

    async def get_next_move(self):
        move = await self.loop.run_in_executor(None, lambda: int(input(f"Player {self.player_id}, enter your next move (0-8): ")))
        if self.is_valid_move(move):
            await self.rabbitmq_manager.send_message(self.player_id, str(move))
        else:
            print("Invalid move. Try again.")
            await self.get_next_move()

    def is_winner(self):
        winning_combinations = [
            (0, 1, 2), (3, 4, 5), (6, 7, 8),  # horizontal
            (0, 3, 6), (1, 4, 7), (2, 5, 8),  # vertical
            (0, 4, 8), (2, 4, 6)  # diagonal
        ]
        for combination in winning_combinations:
            if (
                self.board[combination[0]] == self.board[combination[1]]
                == self.board[combination[2]] != " "
            ):
                return True
        return False

    def is_draw(self):
        return " " not in self.board


class TicTacToeGUI:
    def __init__(self, player_id):
        self.player_id = player_id
        self.rabbitmq_manager = None
        self.game = TicTacToeGame(player_id)

        self.root = tk.Tk()
        self.root.title("Tic Tac Toe")

        self.buttons = []

        for i in range(9):
            button = tk.Button(self.root, text=" ", width=10, height=5, command=lambda index=i: self.button_click(index))
            button.grid(row=i // 3, column=i % 3)
            self.buttons.append(button)

    def button_click(self, index):
        if self.game.is_valid_move(index):
            self.buttons[index].configure(text=self.game.marker)
            self.game.update_board(index)
            self.game.print_board()
            if self.game.is_winner():
                print(f"Player {self.player_id} wins!")
                asyncio.create_task(self.rabbitmq_manager.close())
            elif self.game.is_draw():
                print("It's a draw!")
                asyncio.create_task(self.rabbitmq_manager.close())
            else:
                self.game.send_current_player_turn()

    async def start_game(self):
        await self.game.start_game()

    def run(self):
        self.root.mainloop()


async def main():
    player_id = input("Enter your player ID (player1 or player2): ")
    gui = TicTacToeGUI(player_id)

    rabbitmq_manager = RabbitMQManager(None, None, None)
    rabbitmq_manager.game = gui.game
    gui.game.set_rabbitmq_manager(rabbitmq_manager)

    await rabbitmq_manager.connect()
    await rabbitmq_manager.create_queues()
    asyncio.create_task(rabbitmq_manager.start_consuming())

    asyncio.create_task(gui.start_game())
    gui.run()


asyncio.run(main())
