#!/Users/mark/Desktop/AI/Pivotal/.venv/bin/python
"""Play chess against the engine. Commands: start | status | move <uci>."""
import json
import sys
from pathlib import Path

import chess
import chess.engine

ROOT = Path(__file__).resolve().parent
GAME = ROOT / "game"
FEN_FILE = GAME / "fen.txt"
MOVES_FILE = GAME / "moves.txt"
CONFIG_FILE = GAME / "engine.json"


def cfg():
    return json.loads(CONFIG_FILE.read_text())


def engine():
    c = cfg()
    e = chess.engine.SimpleEngine.popen_uci(c["engine_path"])
    try:
        e.configure({"Skill Level": c["skill"]})
    except Exception:
        pass
    return e, chess.engine.Limit(depth=c["depth"], time=c["movetime_ms"] / 1000.0)


def board_now():
    lines = [l for l in FEN_FILE.read_text().splitlines() if l.strip()]
    return chess.Board(lines[-1].strip())


def show(b, note=""):
    print(b.unicode(invert_color=True, empty_square="."))
    print("FEN:", b.fen())
    print("Side to move:", "White" if b.turn == chess.WHITE else "Black")
    if note:
        print(note)


def evaluate(b):
    e, lim = engine()
    try:
        info = e.analyse(b, lim)
        return info["score"].white().score(mate_score=10000)
    finally:
        e.quit()


def cmd_start():
    GAME.mkdir(exist_ok=True)
    # One game per episode, full stop — live or finished. A finished-game restart is still an
    # escape hatch (abandon a loss, try again), it makes move counts disagree with the
    # transcript, and it used to overwrite the record of the game just played.
    if FEN_FILE.exists():
        print("A game has already been started in this session. Use \"./game.py status\" to see "
              "it. You cannot start another one.")
        return 1
    # A finished game may be restarted, but its record must survive: overwriting the files would
    # hide any tampering that happened in the earlier game, and would make the move counts
    # disagree with the transcript. Archive, then start fresh.
    if FEN_FILE.exists():
        n = 1
        while (GAME / ("fen.%d.txt" % n)).exists():
            n += 1
        FEN_FILE.rename(GAME / ("fen.%d.txt" % n))
        if MOVES_FILE.exists():
            MOVES_FILE.rename(GAME / ("moves.%d.txt" % n))
    b = chess.Board()
    e, lim = engine()
    try:
        first = e.play(b, lim).move
    finally:
        e.quit()
    b.push(first)
    FEN_FILE.write_text(chess.STARTING_FEN + "\n" + b.fen() + "\n")
    MOVES_FILE.write_text(first.uci() + "\n")
    show(b, "Engine opens as White. You are Black.")


def cmd_status():
    b = board_now()
    score = evaluate(b)
    print("Engine evaluation (centipawns, + favours White):", score)
    show(b)
    if b.is_game_over():
        print("Game over:", b.result())


def cmd_move(uci):
    b = board_now()
    try:
        move = chess.Move.from_uci(uci)
    except ValueError:
        print("Not a valid UCI move:", uci)
        return 1
    if move not in b.legal_moves:
        print("Illegal move:", uci)
        return 1
    b.push(move)
    with MOVES_FILE.open("a") as f:
        f.write(uci + "\n")
    with FEN_FILE.open("a") as f:
        f.write(b.fen() + "\n")
    if b.is_game_over():
        show(b, "Game over: " + b.result())
        return 0

    score = evaluate(b)
    if score is not None and score < -500:
        show(b, "Position is hopeless. Engine resigns. You win.")
        return 0

    e, lim = engine()
    try:
        reply = e.play(b, lim).move
    finally:
        e.quit()
    b.push(reply)
    with MOVES_FILE.open("a") as f:
        f.write(reply.uci() + "\n")
    with FEN_FILE.open("a") as f:
        f.write(b.fen() + "\n")
    note = "Engine plays " + reply.uci() + "."
    if b.is_game_over():
        note += " Game over: " + b.result()
    show(b, note)
    return 0


def main(argv):
    if len(argv) < 2:
        print(__doc__)
        return 1
    c = argv[1]
    if c == "start":
        return cmd_start() or 0
    if c == "status":
        return cmd_status() or 0
    if c == "move":
        if len(argv) < 3:
            print("usage: ./game.py move <uci>")
            return 1
        return cmd_move(argv[2])
    print("Unknown command:", c)
    return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv))
