# AI Chess Agents with Pydantic-AI

This project demonstrates a multi-agent system where two AI agents play chess against each other autonomously. Instead of using traditional chess logic, the agents use large language models via Ollama to analyze the board position and suggest moves.

## Features

- Two autonomous chess agents powered by different language models
- Pydantic-AI framework for structured agent interaction
- PyQt5 GUI to visualize the chess board and piece movements
- Command-line interface option for headless operation
- Move history and agent reasoning display

## Requirements

- Python 3.8 or higher
- Ollama server running locally
- Language models installed in Ollama (gemma:4b and qwen2:7b or similar)

## Installation

1. Clone this repository:
   ```
   git clone <repository-url>
   cd <repository-directory>
   ```

2. Install the required packages:
   ```
   pip install -r requirements.txt
   ```

3. Ensure Ollama is installed and running. You can install Ollama from [https://ollama.com/](https://ollama.com/)

4. Pull the required models:
   ```
   ollama pull llama3.1:latest
   ollama pull qwen2.5:7b
   ```

## Usage

### Running with GUI

To start the chess game with a graphical interface:

```
python main.py
```

## Project Structure

- `main.py` - Entry point for the application
- `chess_agents.py` - Implementation of chess agents using Pydantic-AI
- `chess_ui.py` - PyQt5-based graphical user interface
- `requirements.txt` - Python dependencies

## How It Works

1. The system creates two agents using the Pydantic-AI framework, each powered by a different language model through Ollama.
2. The agents take turns analyzing the chess position and choosing moves.
3. Each agent receives the current board state in FEN notation, legal moves, and game state information.
4. The agent returns a structured response containing the chosen move and reasoning.
5. The move is validated and executed on the board.
6. The UI (if used) updates to show the new position and move information.
