import sys
import asyncio
import chess
import chess.svg
from PyQt5.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout,
                             QHBoxLayout, QLabel, QPushButton, QTextEdit, QSplitter)
from PyQt5.QtSvg import QSvgWidget
from PyQt5.QtCore import Qt, QTimer, QSize, pyqtSignal, QObject, QThread
from PyQt5.QtGui import QFont
import io
from chess_agents import ChessGame, ChessMove, NoValidMove

class ChessGameWorker(QObject):
    """Worker to run the chess game in a separate thread"""
    move_made = pyqtSignal(object, str)
    game_over = pyqtSignal(str)
    error_occurred = pyqtSignal(str)

    def __init__(self, game):
        super().__init__()
        self.game = game
        self.running = True

    def run_game(self):
        """Run game in a new event loop"""
        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            loop.run_until_complete(self.play_game())
        except Exception as e:
            self.error_occurred.emit(f"Error in game: {str(e)}")
        finally:
            loop.close()

    async def play_game(self):
        try:
            while self.running and not self.game.board.is_game_over():
                move_result, message = await self.game.play_one_move()
                self.move_made.emit(self.game.board.copy(), message)

                # Give the UI time to update and slow down the game for better viewing
                await asyncio.sleep(1)

            # Game over
            if self.game.board.is_game_over():
                result = self.game.get_game_result()
                self.game_over.emit(result)
        except Exception as e:
            self.error_occurred.emit(f"Error during game play: {str(e)}")

    def stop(self):
        self.running = False

class ChessBoardWidget(QSvgWidget):
    """Widget to display the chess board using SVG"""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setGeometry(0, 0, 600, 600)
        self.board = chess.Board()
        self.update_board()

    def update_board(self, last_move=None):
        """Update the board display"""
        svg_bytes = chess.svg.board(
            self.board,
            size=600,
            lastmove=last_move,
            colors={'square light': '#f0d9b5', 'square dark': '#b58863'}
        ).encode('utf-8')
        self.load(svg_bytes)

    def set_board(self, board, last_move=None):
        """Set a new board position"""
        self.board = board
        self.update_board(last_move)

class ChessUI(QMainWindow):
    """Main UI for the chess game"""
    def __init__(self):
        super().__init__()
        self.game = ChessGame()
        # Set this at class level to ensure access
        self.game.ui_callback = self.receive_commentary
        self.init_ui()

    def receive_commentary(self, color, move, reasoning):
        """Callback method to receive commentary directly from the game"""
        import datetime
        timestamp = datetime.datetime.now().strftime("%H:%M:%S")

        commentary = f"[{timestamp}] {color}'s reasoning for move {move}:\n{reasoning}\n\n"
        print(f"UI received direct commentary: {commentary[:50]}...")

        # Use a timer to ensure this runs in the UI thread
        QTimer.singleShot(0, lambda: self.reasoning_display.append(commentary))

    def init_ui(self):
        """Initialize the UI components"""
        self.setWindowTitle('AI Chess - Pydantic Agents')
        self.setGeometry(100, 100, 1200, 800)

        # Create main widget and layout
        main_widget = QWidget()
        main_layout = QHBoxLayout(main_widget)

        # Create board widget
        self.board_widget = ChessBoardWidget()

        # Create side panel
        side_panel = QWidget()
        side_layout = QVBoxLayout(side_panel)

        # Game controls
        control_layout = QHBoxLayout()
        self.start_button = QPushButton('Start Game')
        self.start_button.clicked.connect(self.start_game)
        self.stop_button = QPushButton('Stop Game')
        self.stop_button.clicked.connect(self.stop_game)
        self.stop_button.setEnabled(False)
        control_layout.addWidget(self.start_button)
        control_layout.addWidget(self.stop_button)

        # Status display
        self.status_label = QLabel('Game ready to start')
        self.status_label.setAlignment(Qt.AlignCenter)
        self.status_label.setFont(QFont('Arial', 12, QFont.Bold))

        # Create tabbed interface for move history and commentary
        tab_widget = QSplitter(Qt.Vertical)

        # Move history
        history_container = QWidget()
        history_layout = QVBoxLayout(history_container)
        history_label = QLabel('Move History:')
        history_label.setFont(QFont('Arial', 10, QFont.Bold))
        self.move_history = QTextEdit()
        self.move_history.setReadOnly(True)
        history_layout.addWidget(history_label)
        history_layout.addWidget(self.move_history)

        # Agent reasoning / commentary
        commentary_container = QWidget()
        commentary_layout = QVBoxLayout(commentary_container)
        commentary_label = QLabel('Agent Commentary:')
        commentary_label.setFont(QFont('Arial', 10, QFont.Bold))
        self.reasoning_display = QTextEdit()
        self.reasoning_display.setReadOnly(True)

        # Set text color to ensure visibility
        self.reasoning_display.setStyleSheet("QTextEdit { color: black; background-color: #f5f5f5; }")

        # Set a more readable font for the commentary
        commentary_font = QFont("Courier New", 15)
        self.reasoning_display.setFont(commentary_font)
        commentary_layout.addWidget(commentary_label)
        commentary_layout.addWidget(self.reasoning_display)

        # Add containers to the tab widget
        tab_widget.addWidget(history_container)
        tab_widget.addWidget(commentary_container)

        # Add widgets to side panel layout
        side_layout.addLayout(control_layout)
        side_layout.addWidget(self.status_label)
        side_layout.addWidget(tab_widget)

        # Add everything to main layout
        main_layout.addWidget(self.board_widget, 3)
        main_layout.addWidget(side_panel, 2)

        self.setCentralWidget(main_widget)

        # Game worker (will be initialized when game starts)
        self.game_thread = None
        self.game_worker = None

    def start_game(self):
        """Start the chess game"""
        self.game = ChessGame()  # Create new game
        self.board_widget.set_board(self.game.board)
        self.move_history.clear()
        self.reasoning_display.clear()
        self.status_label.setText('Game in progress...')

        # Disable start button, enable stop button
        self.start_button.setEnabled(False)
        self.stop_button.setEnabled(True)

        # Start game in a separate thread
        self.game_thread = QThread()
        self.game_worker = ChessGameWorker(self.game)
        self.game_worker.moveToThread(self.game_thread)

        # Connect signals
        self.game_worker.move_made.connect(self.update_after_move)
        self.game_worker.game_over.connect(self.game_finished)
        self.game_worker.error_occurred.connect(self.handle_error)
        self.game_thread.started.connect(self.game_worker.run_game)

        self.game_thread.start()

    def stop_game(self):
        """Stop the current game"""
        if self.game_worker:
            self.game_worker.stop()

        if self.game_thread:
            self.game_thread.quit()
            self.game_thread.wait()

        self.status_label.setText('Game stopped')
        self.start_button.setEnabled(True)
        self.stop_button.setEnabled(False)

    def update_after_move(self, board, message):
        """Update the UI after a move has been made"""
        # Update the board display
        last_move = None
        if self.game.move_history:
            last_move_uci = self.game.move_history[-1]
            last_move = chess.Move.from_uci(last_move_uci)

        self.board_widget.set_board(board, last_move)

        # Update status
        self.status_label.setText(message)

        # Update move history
        move_text = f"Move {len(self.game.move_history)}: {message}\n"
        self.move_history.append(move_text)

        # Update reasoning if available
        if len(self.game.move_history) > 0:
            # Get the color of the player who just moved
            color = "White" if len(self.game.move_history) % 2 == 1 else "Black"
            last_move = self.game.move_history[-1]

            # Get the reasoning directly from the game object
            reasoning = getattr(self.game, 'last_move_reasoning', "No reasoning available")

            # Ensure reasoning is not empty
            if not reasoning or reasoning.strip() == "":
                reasoning = "No detailed reasoning provided"

            # Add a timestamp and format the reasoning
            import datetime
            timestamp = datetime.datetime.now().strftime("%H:%M:%S")

            # Create a distinct commentary entry
            commentary = f"[{timestamp}] {color}'s reasoning for move {last_move}:\n{reasoning}\n\n"

            # Explicitly print to console for debugging
            print(f"Adding commentary to UI: {commentary[:50]}...")

            # Append to the reasoning display
            self.reasoning_display.append(commentary)

            # Auto-scroll to the bottom of the reasoning display
            scrollbar = self.reasoning_display.verticalScrollBar()
            scrollbar.setValue(scrollbar.maximum())

    def handle_error(self, error_message):
        """Handle errors from the game worker"""
        self.status_label.setText(f'Error: {error_message}')
        self.move_history.append(f"\nError occurred: {error_message}")

        self.start_button.setEnabled(True)
        self.stop_button.setEnabled(False)

        # Clean up thread
        if self.game_thread:
            self.game_thread.quit()
            self.game_thread.wait()

    def game_finished(self, result):
        """Handle game over event"""
        self.status_label.setText(f'Game over! Result: {result}')
        self.move_history.append(f"\nGame over! Result: {result}")

        self.start_button.setEnabled(True)
        self.stop_button.setEnabled(False)

        # Clean up thread
        if self.game_thread:
            self.game_thread.quit()
            self.game_thread.wait()

def main():
    app = QApplication(sys.argv)
    chess_ui = ChessUI()
    chess_ui.show()
    sys.exit(app.exec_())

if __name__ == '__main__':
    main()