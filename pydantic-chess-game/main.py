#!/usr/bin/env python3
"""
Chess Agents with Pydantic-AI and Ollama LLMs

This script runs a chess game between two AI agents powered by language models through Ollama.
You can either run the game with a GUI or in CLI mode.
"""

import sys
import asyncio
import argparse

def parse_args():
    parser = argparse.ArgumentParser(description='Chess game with AI agents powered by Ollama LLMs')
    parser.add_argument('--cli', action='store_true', help='Run in CLI mode without GUI')
    parser.add_argument('--max-moves', type=int, default=50, help='Maximum number of moves for the game')
    return parser.parse_args()

async def run_cli_game(max_moves):
    """Run the game in command line mode"""
    from chess_agents import ChessGame

    game = ChessGame()
    game_record = await game.play_game(max_moves=max_moves)

    print(f"Game complete! Final position:")
    print(game.board)
    print(f"Result: {game.get_game_result()}")
    print(f"Total LLM usage: {game.usage}")

    # Save the game record
    import json
    with open("game_record.json", "w") as f:
        json.dump(game_record, f, indent=2)

    return 0

def run_gui_game():
    """Run the game with the GUI"""
    from PyQt5.QtWidgets import QApplication
    from chess_ui import ChessUI

    app = QApplication(sys.argv)
    chess_ui = ChessUI()
    chess_ui.show()
    return app.exec_()

def main():
    args = parse_args()

    if args.cli:
        return asyncio.run(run_cli_game(args.max_moves))
    else:
        return run_gui_game()

if __name__ == '__main__':
    sys.exit(main())