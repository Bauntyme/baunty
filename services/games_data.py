"""
O'yinlar bo'limi ma'lumotlari (50 ta mini HTML5 o'yin, Sovg'a sandig'i va Dumboq uy hayvoni)
"""
import time
from typing import List, Dict, Any

GAMES_LIST: List[Dict[str, Any]] = [
    {"id": "snake", "title": "Iloncha (Snake)", "category": "Klassika", "icon": "🐍", "playable": True, "plays": 48200, "rating": 4.9},
    {"id": "2048", "title": "2048 Boshqotirma", "category": "Mantiqiy", "icon": "🔢", "playable": True, "plays": 52100, "rating": 4.8},
    {"id": "flappy", "title": "Flappy Bird", "category": "Arkada", "icon": "🐦", "playable": True, "plays": 61400, "rating": 4.7},
    {"id": "tictactoe", "title": "Krestiki-noliki (AI)", "category": "Klassika", "icon": "❌", "playable": True, "plays": 39800, "rating": 4.6},
    {"id": "memory", "title": "Xotira kartalari", "category": "Mantiqiy", "icon": "🃏", "playable": True, "plays": 34100, "rating": 4.8},
    {"id": "math", "title": "Tezkor Matematika", "category": "Ta'lim", "icon": "🧮", "playable": True, "plays": 28900, "rating": 4.9},
    {"id": "colormatch", "title": "Rangni top (Color Match)", "category": "Reaksiya", "icon": "🎨", "playable": True, "plays": 25400, "rating": 4.7},
    {"id": "dino", "title": "Dino Runner", "category": "Arkada", "icon": "🦖", "playable": True, "plays": 44300, "rating": 4.8},
    {"id": "pong", "title": "Ping Pong Retro", "category": "Sport", "icon": "🏓", "playable": True, "plays": 21800, "rating": 4.6},
    {"id": "tetris", "title": "Tetris Block", "category": "Klassika", "icon": "🧱", "playable": True, "plays": 56700, "rating": 4.9},
    {"id": "tapmaster", "title": "Tap Master (Bosish tezligi)", "category": "Reaksiya", "icon": "👆", "playable": True, "plays": 19500, "rating": 4.5},
    {"id": "bubble", "title": "Pufakchalar (Bubble Pop)", "category": "Arkada", "icon": "🫧", "playable": True, "plays": 31200, "rating": 4.7},
    {"id": "knife", "title": "Pichoq otish (Knife Hit)", "category": "Arkada", "icon": "🗡️", "playable": True, "plays": 42100, "rating": 4.8},
    {"id": "brick", "title": "G'isht sindiruvchi", "category": "Arkada", "icon": "🧱", "playable": True, "plays": 27400, "rating": 4.6},
    {"id": "mole", "title": "Krotni ur (Whack-a-Mole)", "category": "Reaksiya", "icon": "🐹", "playable": True, "plays": 23900, "rating": 4.7},
    {"id": "space", "title": "Koinot jangi (Space Battle)", "category": "Jangari", "icon": "🚀", "playable": True, "plays": 38900, "rating": 4.8},
    {"id": "simon", "title": "Simon Says (Ranglar eslatmasi)", "category": "Xotira", "icon": "🔴", "playable": True, "plays": 18400, "rating": 4.6},
    {"id": "connect4", "title": "Connect 4 (To'rtta ketma-ket)", "category": "Mantiqiy", "icon": "🔵", "playable": True, "plays": 22100, "rating": 4.7},
    {"id": "wordguess", "title": "So'zni top (Wordle)", "category": "Mantiqiy", "icon": "🔤", "playable": True, "plays": 33400, "rating": 4.9},
    {"id": "reaction", "title": "Reaksiya o'lchagich", "category": "Reaksiya", "icon": "⚡", "playable": True, "plays": 29100, "rating": 4.8},
    {"id": "pacman", "title": "Pacman Retro", "category": "Klassika", "icon": "🟡", "playable": False, "plays": 38100, "rating": 4.8},
    {"id": "tower", "title": "Minora qurish (Stack)", "category": "Arkada", "icon": "🏗️", "playable": False, "plays": 27100, "rating": 4.6},
    {"id": "jump", "title": "Doodle Jump", "category": "Arkada", "icon": "🦘", "playable": False, "plays": 34900, "rating": 4.7},
    {"id": "fruitslice", "title": "Meva kesish (Fruit Ninja)", "category": "Arkada", "icon": "🍉", "playable": False, "plays": 45800, "rating": 4.9},
    {"id": "bowling", "title": "Bowling 3D", "category": "Sport", "icon": "🎳", "playable": False, "plays": 19200, "rating": 4.5},
    {"id": "archery", "title": "Kamondan otish", "category": "Sport", "icon": "🏹", "playable": False, "plays": 21400, "rating": 4.6},
    {"id": "motohill", "title": "Moto Race 2D", "category": "Poyga", "icon": "🏍️", "playable": False, "plays": 36100, "rating": 4.7},
    {"id": "crossy", "title": "Yo'ldan o'tish (Crossy Road)", "category": "Arkada", "icon": "🐔", "playable": False, "plays": 29800, "rating": 4.7},
    {"id": "maze", "title": "Labirint qidiruvi", "category": "Mantiqiy", "icon": "🌀", "playable": False, "plays": 18700, "rating": 4.5},
    {"id": "minesweeper", "title": "Mina qidiruvchi (Saper)", "category": "Mantiqiy", "icon": "💣", "playable": False, "plays": 26400, "rating": 4.6},
    {"id": "sudoku", "title": "Sudoku Master", "category": "Mantiqiy", "icon": "🔢", "playable": False, "plays": 23100, "rating": 4.8},
    {"id": "billiards", "title": "Billiard 8-Ball", "category": "Sport", "icon": "🎱", "playable": False, "plays": 31500, "rating": 4.7},
    {"id": "checkers", "title": "Shashka", "category": "Klassika", "icon": "⚪", "playable": False, "plays": 28400, "rating": 4.7},
    {"id": "chess", "title": "Shaxmat masalalari", "category": "Klassika", "icon": "♟️", "playable": False, "plays": 35200, "rating": 4.9},
    {"id": "solitaire", "title": "Soliter karta", "category": "Klassika", "icon": "♠️", "playable": False, "plays": 24900, "rating": 4.6},
    {"id": "airhockey", "title": "Air Hockey", "category": "Sport", "icon": "🏒", "playable": False, "plays": 19800, "rating": 4.5},
    {"id": "subway", "title": "Subway Runner 2D", "category": "Arkada", "icon": "🏃", "playable": False, "plays": 49100, "rating": 4.8},
    {"id": "candy", "title": "Shirinliklar (Match 3)", "category": "Boshqotirma", "icon": "🍬", "playable": False, "plays": 43200, "rating": 4.7},
    {"id": "helix", "title": "Helix Jump 2D", "category": "Arkada", "icon": "🌪️", "playable": False, "plays": 28400, "rating": 4.6},
    {"id": "geometry", "title": "Geometry Dash Mini", "category": "Arkada", "icon": "📐", "playable": False, "plays": 37200, "rating": 4.8},
    {"id": "cookie", "title": "Cookie Clicker", "category": "Clicker", "icon": "🍪", "playable": False, "plays": 22400, "rating": 4.5},
    {"id": "pianotiles", "title": "Piano Tiles Mini", "category": "Musiqa", "icon": "🎹", "playable": False, "plays": 39500, "rating": 4.8},
    {"id": "stacktower", "title": "Stack Blocks", "category": "Arkada", "icon": "🧱", "playable": False, "plays": 21800, "rating": 4.5},
    {"id": "zigzag", "title": "ZigZag Ball", "category": "Reaksiya", "icon": "⚡", "playable": False, "plays": 25100, "rating": 4.6},
    {"id": "colorswitch", "title": "Color Switch Mini", "category": "Arkada", "icon": "🌈", "playable": False, "plays": 30200, "rating": 4.7},
    {"id": "angrybirds", "title": "Qushlar parvozi", "category": "Arkada", "icon": "🎯", "playable": False, "plays": 41200, "rating": 4.8},
    {"id": "cutrope", "title": "Arqonni kes (Candy Cut)", "category": "Mantiqiy", "icon": "🐸", "playable": False, "plays": 36700, "rating": 4.7},
    {"id": "hillclimb", "title": "Hill Climb Racing 2D", "category": "Poyga", "icon": "🚙", "playable": False, "plays": 44800, "rating": 4.8},
    {"id": "quiz", "title": "Kino & Musiqa Viktorina", "category": "Ta'lim", "icon": "❓", "playable": False, "plays": 32900, "rating": 4.9},
    {"id": "boxing", "title": "Boks Ringi", "category": "Sport", "icon": "🥊", "playable": False, "plays": 27300, "rating": 4.6},
]

# Simulyatsiya qilingan foydalanuvchi ma'lumotlari (Uy hayvoni va sandiq)
PET_DATA = {
    "name": "Dumboqvoy",
    "level": 3,
    "xp": 140,
    "next_xp": 200,
    "hunger": 85,    # 0 - 100
    "energy": 90,    # 0 - 100
    "happiness": 95, # 0 - 100
    "coins": 350,
}

CHEST_DATA = {
    "is_ready": True,
    "last_claimed": 0,
    "cooldown_seconds": 86400,
}
