import asyncio
import datetime
from typing import Literal, Optional, List, Dict, Any
import chess
import chess.svg
import os
import json
import logfire

from pydantic import BaseModel, Field
from pydantic_ai import Agent, RunContext, ModelRetry
from pydantic_ai.models.openai import OpenAIModel
from pydantic_ai.providers.openai import OpenAIProvider
from pydantic_ai.usage import Usage, UsageLimits

# Configure logfire if you have it set up
logfire.configure(send_to_logfire='if-token-present')

# Define models for chess game data
class ChessPosition(BaseModel):
    """Represents the current state of a chess game"""
    fen: str = Field(description="FEN notation of the current board position")
    last_move: Optional[str] = Field(None, description="The last move made in UCI notation")
    legal_moves: List[str] = Field(description="List of legal moves in UCI notation")
    is_check: bool = Field(description="Whether the current player is in check")
    is_checkmate: bool = Field(description="Whether the current position is checkmate")
    is_stalemate: bool = Field(description="Whether the current position is stalemate")
    is_game_over: bool = Field(description="Whether the game is over")
    half_move_clock: int = Field(description="Number of half moves since last capture or pawn advance")
    fullmove_number: int = Field(description="Number of full moves in the game")
    active_color: Literal["white", "black"] = Field(description="Color that has the move")

class ChessMove(BaseModel):
    """A chess move to be played"""
    move_uci: str = Field(description="Move in UCI notation (e.g., 'e2e4')")
    reasoning: str = Field(description="Explanation of why this move was chosen")

class NoValidMove(BaseModel):
    """When no valid move can be found"""
    reason: str = Field(description="Reason why no move could be made")

# Configure Ollama models with models that support OpenAI format
# Use the same model for both players to avoid compatibility issues
white_model = OpenAIModel(
    model_name='qwen2.5:7b',  # Using the model you mentioned works
    provider=OpenAIProvider(base_url='http://localhost:11434/v1')
)

black_model = OpenAIModel(
    model_name='qwen2.5:7b',  # Using the same model for both players
    provider=OpenAIProvider(base_url='http://localhost:11434/v1')
)

# Create chess agents
white_agent = Agent[ChessPosition, ChessMove | NoValidMove](
    white_model,
    result_type=ChessMove | NoValidMove,  # type: ignore
    retries=2,
    system_prompt=(
        "You are an intelligent chess player controlling the WHITE pieces. "
        "Your goal is to analyze the current board position and choose the best move. "
        "\n\n"
        "You will be given the current position in FEN notation, the list of legal moves, "
        "and information about the game state. A FEN string describes a chess position and looks like: "
        "'rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1' for the starting position. "
        "\n\n"
        "Each legal move will be provided in UCI (Universal Chess Interface) format, like 'e2e4' "
        "which means move the piece from square e2 to square e4. "
        "\n\n"
        "For the initial position, good opening moves for WHITE include: "
        "e2e4 (King's Pawn), d2d4 (Queen's Pawn), c2c4 (English Opening), or g1f3 (Reti Opening)."
        "\n\n"
        "YOU MUST select a move from the list of legal moves provided. "
        "Think step by step about strategic implications, piece safety, and tactical opportunities. "
        "Provide your reasoning for the chosen move."
    ),
    instrument=True,
)

black_agent = Agent[ChessPosition, ChessMove | NoValidMove](
    black_model,
    result_type=ChessMove | NoValidMove,  # type: ignore
    retries=2,
    system_prompt=(
        "You are an intelligent chess player controlling the BLACK pieces. "
        "Your goal is to analyze the current board position and choose the best move. "
        "\n\n"
        "You will be given the current position in FEN notation, the list of legal moves, "
        "and information about the game state. A FEN string describes a chess position and looks like: "
        "'rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1' for the starting position. "
        "\n\n"
        "Each legal move will be provided in UCI (Universal Chess Interface) format, like 'e7e5' "
        "which means move the piece from square e7 to square e5. "
        "\n\n"
        "For the initial position, good opening moves for BLACK include: "
        "e7e5 (King's Pawn), e7e6 (French Defense), c7c5 (Sicilian Defense), or d7d5 (Queen's Pawn)."
        "\n\n"
        "YOU MUST select a move from the list of legal moves provided. "
        "Think step by step about strategic implications, piece safety, and tactical opportunities. "
        "Provide your reasoning for the chosen move."
    ),
    instrument=True,
)

# Add validation to ensure the moves are legal
@white_agent.result_validator
@black_agent.result_validator
async def validate_move(
        ctx: RunContext[ChessPosition], result: ChessMove | NoValidMove
) -> ChessMove | NoValidMove:
    """Validate that the chosen move is legal"""
    if isinstance(result, NoValidMove):
        return result

    if result.move_uci not in ctx.deps.legal_moves:
        raise ModelRetry(f"Move {result.move_uci} is not in the list of legal moves: {ctx.deps.legal_moves}")

    return result

# Chess game manager
class ChessGame:
    def __init__(self):
        self.board = chess.Board()
        self.move_history = []
        self.usage = Usage()
        self.usage_limits = UsageLimits(request_limit=100)  # Adjust as needed
        self.last_move_reasoning = ""  # Store the reasoning for the last move
        self.ui_callback = None  # Callback to notify UI directly

    def get_current_position(self) -> ChessPosition:
        """Get the current chess position as a pydantic model"""
        return ChessPosition(
            fen=self.board.fen(),
            last_move=self.move_history[-1] if self.move_history else None,
            legal_moves=[move.uci() for move in self.board.legal_moves],
            is_check=self.board.is_check(),
            is_checkmate=self.board.is_checkmate(),
            is_stalemate=self.board.is_stalemate(),
            is_game_over=self.board.is_game_over(),
            half_move_clock=self.board.halfmove_clock,
            fullmove_number=self.board.fullmove_number,
            active_color="white" if self.board.turn == chess.WHITE else "black"
        )

    async def play_one_move(self) -> tuple[ChessMove | NoValidMove, str]:
        """Have the current player make a move"""
        position = self.get_current_position()

        # Check if the game is over
        if position.is_game_over:
            return NoValidMove(reason="Game is already over"), "Game Over"

        # Choose the appropriate agent based on whose turn it is
        active_agent = white_agent if position.active_color == "white" else black_agent
        agent_name = "White" if position.active_color == "white" else "Black"

        # Prepare a more descriptive message for the agent
        move_description = ""
        if len(self.move_history) > 0:
            last_move = self.move_history[-1]
            last_color = "White" if len(self.move_history) % 2 == 1 else "Black"
            move_description = f"{last_color}'s last move was {last_move}. "

        human_readable_fen = position.fen.split(" ")[0]
        prompt = (
            f"It's your turn to play as {agent_name.upper()}. {move_description}\n"
            f"Current board (FEN): {position.fen}\n"
            f"Position summary: {human_readable_fen}\n"
            f"Legal moves: {', '.join(position.legal_moves)}\n"
            f"Check: {'Yes' if position.is_check else 'No'}, "
            f"Move number: {position.fullmove_number}\n"
            f"Analyze this position and choose the best move from the legal moves."
        )

        # Run the agent to get a move
        try:
            result = await active_agent.run(
                prompt,
                deps=position,
                usage=self.usage,
                usage_limits=self.usage_limits,
            )

            # Handle the result
            move_result = result.data
            if isinstance(move_result, ChessMove):
                # Make the move on the board
                move = chess.Move.from_uci(move_result.move_uci)
                self.board.push(move)
                self.move_history.append(move_result.move_uci)

                # Store the reasoning and print it for debugging
                self.last_move_reasoning = move_result.reasoning
                print(f"Storing reasoning: {self.last_move_reasoning[:50]}...")

                # Notify UI directly via callback if registered
                if self.ui_callback:
                    self.ui_callback(agent_name, move_result.move_uci, move_result.reasoning)

                # Log the move
                logfire.info(
                    "{color} played {move}: {reasoning}",
                    color=agent_name,
                    move=move_result.move_uci,
                    reasoning=move_result.reasoning
                )

                return move_result, f"{agent_name} played {move_result.move_uci}"
            else:
                return move_result, f"{agent_name} could not make a move: {move_result.reason}"
        except Exception as e:
            # Handle exceptions, log them and return a NoValidMove
            error_msg = f"Error during {agent_name}'s move: {str(e)}"
            logfire.error(error_msg)
            return NoValidMove(reason=error_msg), error_msg

    async def play_game(self, max_moves: int = 50) -> List[dict]:
        """Play a complete game between the two agents"""
        game_record = []

        for move_num in range(max_moves):
            if self.board.is_game_over():
                result = self.get_game_result()
                logfire.info("Game over: {result}", result=result)
                game_record.append({"event": "game_over", "result": result})
                break

            move_result, message = await self.play_one_move()

            # Record the move
            position = self.get_current_position()
            game_record.append({
                "move_number": move_num + 1,
                "move": move_result.move_uci if isinstance(move_result, ChessMove) else None,
                "reasoning": move_result.reasoning if isinstance(move_result, ChessMove) else None,
                "position": position.dict(),
                "message": message
            })

            # Print current state
            print(f"Move {move_num + 1}: {message}")
            print(self.board)
            print("\n")

        return game_record

    def get_game_result(self) -> str:
        """Get the result of the game"""
        if self.board.is_checkmate():
            return "1-0" if not self.board.turn else "0-1"
        elif self.board.is_stalemate():
            return "1/2-1/2 (Stalemate)"
        elif self.board.is_insufficient_material():
            return "1/2-1/2 (Insufficient material)"
        elif self.board.is_fifty_moves():
            return "1/2-1/2 (Fifty-move rule)"
        elif self.board.is_repetition():
            return "1/2-1/2 (Repetition)"
        else:
            return "Unknown result"

async def main():
    game = ChessGame()
    game_record = await game.play_game(max_moves=30)

    # Save the game record
    with open("game_record.json", "w") as f:
        json.dump(game_record, f, indent=2)

    print(f"Game complete! Final position:")
    print(game.board)
    print(f"Result: {game.get_game_result()}")
    print(f"Total LLM usage: {game.usage}")

if __name__ == "__main__":
    asyncio.run(main())