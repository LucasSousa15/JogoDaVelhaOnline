import asyncio
import aio_pika
import tkinter as tk


class RabbitMQManager:
    def __init__(self, game_queue, player_queues, on_message_callback):
        self.game_queue = game_queue  # Define a fila do jogo
        self.player_queues = player_queues  # Define as filas dos jogadores
        self.on_message_callback = on_message_callback  # Define a função de retorno de chamada para mensagens recebidas
        self.connection = None  # Inicializa a conexão com None
        self.channel = None  # Inicializa o canal com None
        self.game = None  # Inicializa o jogo com None

    async def connect(self):
        self.connection = await aio_pika.connect_robust(
            "seu servidor ampq",
            loop=asyncio.get_event_loop()
        )  # Conecta-se ao RabbitMQ usando a biblioteca aio_pika
        self.channel = await self.connection.channel()  # Cria um canal na conexão estabelecida

    async def create_queues(self):
        await self.channel.declare_queue(self.game_queue, auto_delete=False)  # Cria a fila do jogo no canal
        for player_queue in self.player_queues:
            await self.channel.declare_queue(player_queue, auto_delete=False)  # Cria as filas dos jogadores no canal

    async def start_consuming(self):
        game_queue = await self.channel.declare_queue(self.game_queue)  # Declara a fila do jogo
        await game_queue.consume(self.process_game_message)  # Inicia o consumo da fila do jogo com a função de processamento
        for player_queue in self.player_queues:
            player_queue = await self.channel.declare_queue(player_queue)  # Declara as filas dos jogadores
            await player_queue.consume(self.process_player_message)  # Inicia o consumo das filas dos jogadores com a função de processamento

    async def process_game_message(self, message):
        async with message.process():
            self.on_message_callback(self.game_queue, message.body.decode())  # Chama a função de retorno de chamada para mensagens recebidas na fila do jogo

    async def process_player_message(self, message):
        async with message.process():
            player_id = message.properties.headers.get("Player-Id")  # Obtém o ID do jogador a partir das propriedades da mensagem
            if player_id is not None:
                self.on_message_callback(player_id, message.body.decode())  # Chama a função de retorno de chamada para mensagens recebidas nas filas dos jogadores

    async def send_message(self, queue_name, message):
        properties = aio_pika.BasicProperties()
        await self.channel.default_exchange.publish(
            aio_pika.Message(body=message.encode(), properties=properties),
            routing_key=queue_name
        )  # Publica uma mensagem na fila especificada com o corpo da mensagem e as propriedades

    async def close(self):
        await self.connection.close()  # Fecha a conexão com o RabbitMQ


class TicTacToeGame:
    def __init__(self, player_id):
        self.player_id = player_id  # Define o ID do jogador
        self.marker = "X" if player_id == "player1" else "O"  # Define o marcador do jogador
        self.board = [" "] * 9  # Inicializa o tabuleiro do jogo com espaços em branco
        self.rabbitmq_manager = None  # Inicializa o RabbitMQManager com None
        self.game_queue = "game_queue"  # Define o nome da fila do jogo
        self.player_queues = ["player_queue_player1", "player_queue_player2"]  # Define os nomes das filas dos jogadores

    async def start_game(self):
        self.rabbitmq_manager = RabbitMQManager(self.game_queue, self.player_queues, self.on_message_received)  # Cria um RabbitMQManager para o jogo
        self.rabbitmq_manager.game = self  # Define o jogo no RabbitMQManager
        await self.rabbitmq_manager.connect()  # Conecta-se ao RabbitMQ
        await self.rabbitmq_manager.create_queues()  # Cria as filas necessárias
        await self.rabbitmq_manager.start_consuming()  # Inicia o consumo das filas

    def on_message_received(self, sender_id, message):
        if sender_id == self.game_queue:  # Se a mensagem veio da fila do jogo
            move = int(message)  # Converte a mensagem em um movimento válido
            if self.is_valid_move(move):  # Verifica se o movimento é válido
                self.update_board(move)  # Atualiza o tabuleiro com o movimento
                self.print_board()  # Imprime o tabuleiro atualizado
                if self.is_winner():  # Verifica se o jogador venceu
                    print(f"Player {self.player_id} wins!")  # Imprime que o jogador venceu
                    asyncio.create_task(self.rabbitmq_manager.close())  # Fecha a conexão com o RabbitMQ
                elif self.is_draw():  # Verifica se há um empate
                    print("It's a draw!")  # Imprime que houve um empate
                    asyncio.create_task(self.rabbitmq_manager.close())  # Fecha a conexão com o RabbitMQ
                else:
                    updated_board = ' '.join(self.board)  # Cria uma representação em string do tabuleiro atualizado
                    for player_queue in self.player_queues:
                        asyncio.create_task(self.rabbitmq_manager.send_message(player_queue, updated_board))  # Envia o tabuleiro atualizado para as filas dos jogadores
        else:
            self.board = message.split()  # Se a mensagem veio de um jogador, atualiza o tabuleiro com o estado recebido
            self.print_board()  # Imprime o tabuleiro atualizado

    def is_valid_move(self, move):
        return self.board[move] == " "  # Verifica se o movimento é válido (espaço em branco)

    def update_board(self, move):
        self.board[move] = self.marker  # Atualiza o tabuleiro com o movimento do jogador

    def print_board(self):
        print("Board:")
        for i in range(0, 9, 3):
            print(f"{self.board[i]} | {self.board[i + 1]} | {self.board[i + 2]}")  # Imprime o tabuleiro atual

    def is_winner(self):
        winning_combinations = [
            [0, 1, 2], [3, 4, 5], [6, 7, 8],  # Rows
            [0, 3, 6], [1, 4, 7], [2, 5, 8],  # Columns
            [0, 4, 8], [2, 4, 6]  # Diagonals
        ]  # Combinações vencedoras possíveis

        for combination in winning_combinations:
            if self.board[combination[0]] == self.board[combination[1]] == self.board[combination[2]] != " ":
                return True  # Verifica se alguma combinação vencedora foi alcançada

        return False  # Retorna False se nenhuma combinação vencedora foi alcançada

    def is_draw(self):
        return " " not in self.board  # Verifica se há um empate (nenhum espaço em branco no tabuleiro)


class TicTacToeGUI:
    def __init__(self, player_id):
        self.player_id = player_id  # Define o ID do jogador
        self.rabbitmq_manager = None  # Inicializa o RabbitMQManager com None
        self.game = None  # Inicializa o jogo com None

        self.root = tk.Tk()  # Cria uma janela do tkinter
        self.root.title("Tic Tac Toe")  # Define o título da janela

        self.buttons = []  # Inicializa a lista de botões

        for i in range(9):
            button = tk.Button(self.root, text=" ", width=10, height=5,
                               command=lambda index=i: self.button_click(index))
            button.grid(row=i // 3, column=i % 3)  # Cria um botão na janela para cada posição no tabuleiro
            self.buttons.append(button)  # Adiciona o botão à lista de botões

    def button_click(self, index):
        if self.game.is_valid_move(index):  # Se o movimento for válido
            self.buttons[index].configure(text=self.game.marker)  # Atualiza o texto do botão com o marcador do jogador
            self.game.update_board(index)  # Atualiza o tabuleiro com o movimento do jogador
            self.game.print_board()  # Imprime o tabuleiro atualizado
            if self.game.is_winner():  # Verifica se o jogador venceu
                print(f"Player {self.player_id} wins!")  # Imprime que o jogador venceu
                asyncio.create_task(self.rabbitmq_manager.close())  # Fecha a conexão com o RabbitMQ
            elif self.game.is_draw():  # Verifica se há um empate
                print("It's a draw!")  # Imprime que houve um empate
                asyncio.create_task(self.rabbitmq_manager.close())  # Fecha a conexão com o RabbitMQ
            else:
                asyncio.create_task(self.rabbitmq_manager.send_message(self.game.game_queue, str(index)))  # Envia o movimento para a fila do jogo

    def run(self):
        self.root.mainloop()  # Executa o loop principal do tkinter


async def main():
    player_id = input("Enter your player ID (player1 or player2): ")  # Solicita o ID do jogador
    gui = TicTacToeGUI(player_id)  # Cria a interface gráfica do jogo

    game = TicTacToeGame(player_id)  # Cria o jogo
    await game.start_game()  # Inicia o jogo

    gui.rabbitmq_manager = game.rabbitmq_manager  # Define o RabbitMQManager na interface gráfica
    gui.game = game  # Define o jogo na interface gráfica

    gui.run()  # Executa a interface gráfica


if __name__ == "__main__":
    asyncio.run(main())  # Executa a função principal asyncio
