/**
 * Mini HTML5 Web O'yinlar dvijogi (10 ta to'liq interaktiv o'yin)
 */

window.GameRunner = {
    activeGame: null,
    canvas: null,
    ctx: null,
    animFrame: null,
    score: 0,

    init(container, gameId) {
        this.stop();
        this.score = 0;
        this.activeGame = gameId;
        container.innerHTML = `
            <div class="game-header-bar">
                <span class="game-score-badge">Ochko: <b id="game-score">0</b></span>
                <button class="game-btn-restart" onclick="GameRunner.restart()"><i class="fas fa-redo"></i> Qayta</button>
            </div>
            <div id="game-stage" class="game-stage"></div>
            <div class="game-touch-controls" id="game-controls"></div>
        `;

        const stage = document.getElementById('game-stage');
        const updateScore = (val) => {
            this.score = val;
            const el = document.getElementById('game-score');
            if (el) el.innerText = val;
        };

        if (gameId === 'snake') this.initSnake(stage, updateScore);
        else if (gameId === '2048') this.init2048(stage, updateScore);
        else if (gameId === 'flappy') this.initFlappy(stage, updateScore);
        else if (gameId === 'tictactoe') this.initTicTacToe(stage, updateScore);
        else if (gameId === 'memory') this.initMemory(stage, updateScore);
        else if (gameId === 'math') this.initMath(stage, updateScore);
        else if (gameId === 'colormatch') this.initColorMatch(stage, updateScore);
        else if (gameId === 'dino') this.initDino(stage, updateScore);
        else if (gameId === 'pong') this.initPong(stage, updateScore);
        else if (gameId === 'tetris') this.initTetris(stage, updateScore);
        else this.initGenericArcade(stage, gameId, updateScore);
    },

    restart() {
        if (this.activeGame) {
            const stage = document.getElementById('game-stage');
            if (stage && stage.parentElement) {
                this.init(stage.parentElement, this.activeGame);
            }
        }
    },

    stop() {
        if (this.animFrame) cancelAnimationFrame(this.animFrame);
        this.animFrame = null;
        if (this.gameInterval) clearInterval(this.gameInterval);
        this.gameInterval = null;
    },

    // 1. ILONCHA (SNAKE)
    initSnake(stage, updateScore) {
        stage.innerHTML = `<canvas id="g-canvas" width="320" height="320"></canvas>`;
        const canvas = document.getElementById('g-canvas');
        const ctx = canvas.getContext('2d');
        const grid = 16;
        let count = 0;
        let snake = { x: 160, y: 160, dx: grid, dy: 0, cells: [], maxCells: 4 };
        let apple = { x: 320 - grid * 4, y: 320 - grid * 4 };
        let score = 0;
        let gameOver = false;

        const controls = document.getElementById('game-controls');
        controls.innerHTML = `
            <div class="d-pad">
                <button onclick="window.snakeDir(0, -16)">⬆️</button>
                <div class="d-pad-mid">
                    <button onclick="window.snakeDir(-16, 0)">⬅️</button>
                    <button onclick="window.snakeDir(16, 0)">➡️</button>
                </div>
                <button onclick="window.snakeDir(0, 16)">⬇️</button>
            </div>
        `;
        window.snakeDir = (dx, dy) => {
            if (gameOver) return;
            if (dx !== 0 && snake.dx === 0) { snake.dx = dx; snake.dy = 0; window.soundEngine.playClick(); }
            if (dy !== 0 && snake.dy === 0) { snake.dy = dy; snake.dx = 0; window.soundEngine.playClick(); }
        };

        const loop = () => {
            this.animFrame = requestAnimationFrame(loop);
            if (++count < 6) return;
            count = 0;
            ctx.clearRect(0, 0, canvas.width, canvas.height);

            snake.x += snake.dx;
            snake.y += snake.dy;
            if (snake.x < 0) snake.x = canvas.width - grid;
            else if (snake.x >= canvas.width) snake.x = 0;
            if (snake.y < 0) snake.y = canvas.height - grid;
            else if (snake.y >= canvas.height) snake.y = 0;

            snake.cells.unshift({ x: snake.x, y: snake.y });
            if (snake.cells.length > snake.maxCells) snake.cells.pop();

            ctx.fillStyle = '#ff4d4d';
            ctx.fillRect(apple.x, apple.y, grid - 1, grid - 1);

            ctx.fillStyle = '#4ade80';
            snake.cells.forEach((cell, index) => {
                ctx.fillRect(cell.x, cell.y, grid - 1, grid - 1);
                if (cell.x === apple.x && cell.y === apple.y) {
                    snake.maxCells++;
                    score += 10;
                    updateScore(score);
                    window.soundEngine.playCoin();
                    apple.x = Math.floor(Math.random() * 20) * grid;
                    apple.y = Math.floor(Math.random() * 20) * grid;
                }
                for (let i = index + 1; i < snake.cells.length; i++) {
                    if (cell.x === snake.cells[i].x && cell.y === snake.cells[i].y) {
                        gameOver = true;
                        window.soundEngine.playHit();
                        cancelAnimationFrame(this.animFrame);
                        ctx.fillStyle = 'rgba(0,0,0,0.7)';
                        ctx.fillRect(0, 0, canvas.width, canvas.height);
                        ctx.fillStyle = '#fff';
                        ctx.font = '20px sans-serif';
                        ctx.textAlign = 'center';
                        ctx.fillText('O\'yin tugadi!', canvas.width / 2, canvas.height / 2);
                    }
                }
            });
        };
        loop();
    },

    // 2. 2048
    init2048(stage, updateScore) {
        let board = [
            [0,0,0,0],
            [0,0,0,0],
            [0,0,0,0],
            [0,0,0,0]
        ];
        let score = 0;
        const addRandom = () => {
            let empty = [];
            for (let r=0; r<4; r++) for (let c=0; c<4; c++) if (board[r][c]===0) empty.push({r,c});
            if (empty.length > 0) {
                let cell = empty[Math.floor(Math.random()*empty.length)];
                board[cell.r][cell.c] = Math.random() < 0.9 ? 2 : 4;
            }
        };
        addRandom(); addRandom();

        const render = () => {
            stage.innerHTML = `<div class="grid-2048">` +
                board.map(row => row.map(val => `<div class="cell-2048 val-${val}">${val || ''}</div>`).join('')).join('') +
            `</div>`;
        };
        render();

        const slide = (row) => {
            let arr = row.filter(val => val);
            for (let i = 0; i < arr.length - 1; i++) {
                if (arr[i] === arr[i + 1]) {
                    arr[i] *= 2;
                    score += arr[i];
                    updateScore(score);
                    window.soundEngine.playCoin();
                    arr.splice(i + 1, 1);
                }
            }
            while (arr.length < 4) arr.push(0);
            return arr;
        };

        window.move2048 = (dir) => {
            let prev = JSON.stringify(board);
            if (dir === 'left') {
                for (let r = 0; r < 4; r++) board[r] = slide(board[r]);
            } else if (dir === 'right') {
                for (let r = 0; r < 4; r++) board[r] = slide(board[r].reverse()).reverse();
            } else if (dir === 'up') {
                for (let c = 0; c < 4; c++) {
                    let col = [board[0][c], board[1][c], board[2][c], board[3][c]];
                    col = slide(col);
                    for (let r = 0; r < 4; r++) board[r][c] = col[r];
                }
            } else if (dir === 'down') {
                for (let c = 0; c < 4; c++) {
                    let col = [board[3][c], board[2][c], board[1][c], board[0][c]];
                    col = slide(col);
                    for (let r = 0; r < 4; r++) board[3 - r][c] = col[r];
                }
            }
            if (prev !== JSON.stringify(board)) {
                addRandom();
                render();
            }
        };

        const controls = document.getElementById('game-controls');
        controls.innerHTML = `
            <div class="d-pad">
                <button onclick="window.move2048('up')">⬆️</button>
                <div class="d-pad-mid">
                    <button onclick="window.move2048('left')">⬅️</button>
                    <button onclick="window.move2048('right')">➡️</button>
                </div>
                <button onclick="window.move2048('down')">⬇️</button>
            </div>
        `;
    },

    // 3. FLAPPY BIRD
    initFlappy(stage, updateScore) {
        stage.innerHTML = `<canvas id="g-canvas" width="320" height="320"></canvas>`;
        const canvas = document.getElementById('g-canvas');
        const ctx = canvas.getContext('2d');
        let birdY = 160, velocity = 0, gravity = 0.35;
        let pipes = [{ x: 320, top: 100, bottom: 120 }];
        let score = 0, gameOver = false;

        const jump = () => {
            if (gameOver) return;
            velocity = -5.5;
            window.soundEngine.playJump();
        };
        canvas.onclick = jump;
        document.getElementById('game-controls').innerHTML = `
            <button class="btn-tap-jump" onclick="window.flappyJump()">🦘 SAKRASH (TAP)</button>
        `;
        window.flappyJump = jump;

        const loop = () => {
            this.animFrame = requestAnimationFrame(loop);
            ctx.fillStyle = '#70c5ce';
            ctx.fillRect(0, 0, canvas.width, canvas.height);

            velocity += gravity;
            birdY += velocity;

            // Bird
            ctx.fillStyle = '#facc15';
            ctx.beginPath();
            ctx.arc(60, birdY, 12, 0, Math.PI * 2);
            ctx.fill();

            // Pipes
            pipes.forEach(p => {
                p.x -= 2;
                ctx.fillStyle = '#22c55e';
                ctx.fillRect(p.x, 0, 40, p.top);
                ctx.fillRect(p.x, canvas.height - p.bottom, 40, p.bottom);

                if (p.x === 60) {
                    score++;
                    updateScore(score);
                    window.soundEngine.playCoin();
                }

                if (60 + 12 > p.x && 60 - 12 < p.x + 40) {
                    if (birdY - 12 < p.top || birdY + 12 > canvas.height - p.bottom) {
                        gameOver = true;
                    }
                }
            });

            if (pipes[pipes.length - 1].x < 180) {
                let topH = Math.floor(Math.random() * 120) + 40;
                pipes.push({ x: 320, top: topH, bottom: canvas.height - topH - 100 });
            }
            if (pipes[0].x < -40) pipes.shift();

            if (birdY > canvas.height || birdY < 0) gameOver = true;

            if (gameOver) {
                window.soundEngine.playHit();
                cancelAnimationFrame(this.animFrame);
                ctx.fillStyle = 'rgba(0,0,0,0.6)';
                ctx.fillRect(0,0,canvas.width,canvas.height);
                ctx.fillStyle = '#fff';
                ctx.font = '22px sans-serif';
                ctx.textAlign = 'center';
                ctx.fillText('Yiqildi!', canvas.width / 2, canvas.height / 2);
            }
        };
        loop();
    },

    // 4. TIC TAC TOE
    initTicTacToe(stage, updateScore) {
        let board = Array(9).fill('');
        let gameOver = false;
        let score = 0;

        const checkWin = (b) => {
            const wins = [
                [0,1,2],[3,4,5],[6,7,8],
                [0,3,6],[1,4,7],[2,5,8],
                [0,4,8],[2,4,6]
            ];
            for (let [x,y,z] of wins) {
                if (b[x] && b[x]===b[y] && b[x]===b[z]) return b[x];
            }
            if (!b.includes('')) return 'draw';
            return null;
        };

        const render = () => {
            stage.innerHTML = `<div class="grid-ttt">` +
                board.map((v, i) => `<div class="cell-ttt" onclick="window.clickTTT(${i})">${v}</div>`).join('') +
            `</div><div id="ttt-status" class="ttt-status">Sizning navbatingiz (X)</div>`;
        };

        window.clickTTT = (i) => {
            if (gameOver || board[i]) return;
            board[i] = '❌';
            window.soundEngine.playClick();
            let winner = checkWin(board);
            if (winner) return finish(winner);

            // AI Move
            render();
            setTimeout(() => {
                let empty = board.map((v, idx) => v === '' ? idx : null).filter(v => v !== null);
                if (empty.length > 0) {
                    let move = empty[Math.floor(Math.random() * empty.length)];
                    board[move] = '⭕';
                    let aiWinner = checkWin(board);
                    if (aiWinner) finish(aiWinner);
                    else render();
                }
            }, 300);
        };

        const finish = (winner) => {
            gameOver = true;
            render();
            const status = document.getElementById('ttt-status');
            if (winner === '❌') {
                status.innerText = '🎉 Siz yutdingiz!';
                score += 100;
                updateScore(score);
                window.soundEngine.playWin();
            } else if (winner === '⭕') {
                status.innerText = '😔 Bot yutdi!';
                window.soundEngine.playHit();
            } else {
                status.innerText = '🤝 Durang!';
            }
        };

        render();
        document.getElementById('game-controls').innerHTML = '';
    },

    // 5. XOTIRA KARTALARI (MEMORY)
    initMemory(stage, updateScore) {
        const emojis = ['🍎','🍉','🍇','🍓','🍒','🍌','🍍','🥝'];
        let deck = [...emojis, ...emojis].sort(() => Math.random() - 0.5);
        let flipped = [];
        let matched = [];
        let score = 0;

        const render = () => {
            stage.innerHTML = `<div class="grid-memory">` +
                deck.map((emoji, idx) => {
                    let isOpen = flipped.includes(idx) || matched.includes(idx);
                    return `<div class="card-memory ${isOpen ? 'open' : ''}" onclick="window.flipMemory(${idx})">${isOpen ? emoji : '❓'}</div>`;
                }).join('') +
            `</div>`;
        };

        window.flipMemory = (idx) => {
            if (flipped.length >= 2 || flipped.includes(idx) || matched.includes(idx)) return;
            flipped.push(idx);
            window.soundEngine.playClick();
            render();

            if (flipped.length === 2) {
                const [i1, i2] = flipped;
                if (deck[i1] === deck[i2]) {
                    matched.push(i1, i2);
                    flipped = [];
                    score += 20;
                    updateScore(score);
                    window.soundEngine.playCoin();
                    if (matched.length === deck.length) {
                        window.soundEngine.playWin();
                    }
                    render();
                } else {
                    setTimeout(() => {
                        flipped = [];
                        render();
                    }, 800);
                }
            }
        };

        render();
        document.getElementById('game-controls').innerHTML = '';
    },

    // 6. TEZKOR MATEMATIKA
    initMath(stage, updateScore) {
        let score = 0;
        const generate = () => {
            const a = Math.floor(Math.random() * 20) + 1;
            const b = Math.floor(Math.random() * 20) + 1;
            const isAdd = Math.random() > 0.5;
            const ans = isAdd ? a + b : a - b;
            const options = [ans, ans + 1, ans - 1, ans + 2].sort(() => Math.random() - 0.5);

            stage.innerHTML = `
                <div class="math-box">
                    <div class="math-expr">${a} ${isAdd ? '+' : '-'} ${b} = ?</div>
                    <div class="math-options">
                        ${options.map(opt => `<button class="btn-math" onclick="window.answerMath(${opt}, ${ans})">${opt}</button>`).join('')}
                    </div>
                </div>
            `;
        };

        window.answerMath = (selected, correct) => {
            if (selected === correct) {
                score += 10;
                updateScore(score);
                window.soundEngine.playCoin();
                generate();
            } else {
                window.soundEngine.playHit();
                stage.innerHTML = `<div class="game-over-banner">❌ Noto'g'ri! Yakuniy ball: ${score}</div>`;
            }
        };

        generate();
        document.getElementById('game-controls').innerHTML = '';
    },

    // 7. COLOR MATCH
    initColorMatch(stage, updateScore) {
        let score = 0;
        const colors = [
            { name: "Qizil", hex: "#ef4444" },
            { name: "Ko'k", hex: "#3b82f6" },
            { name: "Yashil", hex: "#22c55e" },
            { name: "Sariq", hex: "#eab308" }
        ];

        const next = () => {
            const word = colors[Math.floor(Math.random() * colors.length)];
            const color = colors[Math.floor(Math.random() * colors.length)];
            const isMatch = word.name === color.name;

            stage.innerHTML = `
                <div class="color-match-card">
                    <p style="color: #94a3b8; font-size: 13px;">Matn nomi va rangi mos keladimi?</p>
                    <div class="color-word" style="color: ${color.hex};">${word.name}</div>
                    <div class="color-btn-group">
                        <button class="btn-match-yes" onclick="window.checkColor(true, ${isMatch})">✅ Ha</button>
                        <button class="btn-match-no" onclick="window.checkColor(false, ${isMatch})">❌ Yo'q</button>
                    </div>
                </div>
            `;
        };

        window.checkColor = (ans, isMatch) => {
            if (ans === isMatch) {
                score += 15;
                updateScore(score);
                window.soundEngine.playCoin();
                next();
            } else {
                window.soundEngine.playHit();
                stage.innerHTML = `<div class="game-over-banner">❌ Xato! Sizning ballingiz: ${score}</div>`;
            }
        };

        next();
        document.getElementById('game-controls').innerHTML = '';
    },

    // 8. DINO RUNNER
    initDino(stage, updateScore) {
        stage.innerHTML = `<canvas id="g-canvas" width="320" height="200"></canvas>`;
        const canvas = document.getElementById('g-canvas');
        const ctx = canvas.getContext('2d');
        let dinoY = 150, dinoV = 0, isJumping = false;
        let cactusX = 320;
        let score = 0;
        let gameOver = false;

        const jump = () => {
            if (!isJumping && !gameOver) {
                dinoV = -8;
                isJumping = true;
                window.soundEngine.playJump();
            }
        };
        canvas.onclick = jump;
        document.getElementById('game-controls').innerHTML = `<button class="btn-tap-jump" onclick="window.dinoJump()">🦖 SAKRASH</button>`;
        window.dinoJump = jump;

        const loop = () => {
            this.animFrame = requestAnimationFrame(loop);
            ctx.fillStyle = '#1e293b';
            ctx.fillRect(0, 0, canvas.width, canvas.height);

            // Ground
            ctx.fillStyle = '#475569';
            ctx.fillRect(0, 170, canvas.width, 30);

            // Dino
            dinoY += dinoV;
            dinoV += 0.45;
            if (dinoY >= 150) {
                dinoY = 150;
                dinoV = 0;
                isJumping = false;
            }
            ctx.fillStyle = '#38bdf8';
            ctx.fillRect(40, dinoY, 18, 20);

            // Cactus
            cactusX -= 3.5;
            if (cactusX < -20) {
                cactusX = 320;
                score += 10;
                updateScore(score);
                window.soundEngine.playCoin();
            }
            ctx.fillStyle = '#ef4444';
            ctx.fillRect(cactusX, 150, 14, 20);

            // Collision
            if (cactusX < 58 && cactusX > 26 && dinoY > 132) {
                gameOver = true;
                window.soundEngine.playHit();
                cancelAnimationFrame(this.animFrame);
                ctx.fillStyle = 'rgba(0,0,0,0.7)';
                ctx.fillRect(0, 0, canvas.width, canvas.height);
                ctx.fillStyle = '#fff';
                ctx.font = '20px sans-serif';
                ctx.textAlign = 'center';
                ctx.fillText('Yiqildi!', canvas.width / 2, canvas.height / 2);
            }
        };
        loop();
    },

    // 9. PING PONG
    initPong(stage, updateScore) {
        stage.innerHTML = `<canvas id="g-canvas" width="320" height="260"></canvas>`;
        const canvas = document.getElementById('g-canvas');
        const ctx = canvas.getContext('2d');
        let ballX = 160, ballY = 130, dx = 2.5, dy = 2.5;
        let paddleX = 130;
        let score = 0;

        canvas.onmousemove = (e) => {
            const rect = canvas.getBoundingClientRect();
            paddleX = e.clientX - rect.left - 30;
        };
        document.getElementById('game-controls').innerHTML = `
            <div class="pong-btn-row">
                <button onclick="window.movePaddle(-30)">⬅️ Chap</button>
                <button onclick="window.movePaddle(30)">O'ng ➡️</button>
            </div>
        `;
        window.movePaddle = (d) => { paddleX = Math.max(0, Math.min(260, paddleX + d)); };

        const loop = () => {
            this.animFrame = requestAnimationFrame(loop);
            ctx.fillStyle = '#0f172a';
            ctx.fillRect(0, 0, canvas.width, canvas.height);

            // Ball
            ballX += dx;
            ballY += dy;
            if (ballX < 6 || ballX > canvas.width - 6) dx = -dx;
            if (ballY < 6) dy = -dy;

            // Paddle collision
            if (ballY >= 235 && ballY <= 245 && ballX >= paddleX && ballX <= paddleX + 60) {
                dy = -dy;
                score += 10;
                updateScore(score);
                window.soundEngine.playJump();
            }

            if (ballY > canvas.height) {
                window.soundEngine.playHit();
                cancelAnimationFrame(this.animFrame);
                ctx.fillStyle = 'rgba(0,0,0,0.7)';
                ctx.fillRect(0, 0, canvas.width, canvas.height);
                ctx.fillStyle = '#fff';
                ctx.font = '20px sans-serif';
                ctx.textAlign = 'center';
                ctx.fillText('O\'yin tugadi!', canvas.width / 2, canvas.height / 2);
                return;
            }

            // Draw paddle & ball
            ctx.fillStyle = '#38bdf8';
            ctx.fillRect(paddleX, 240, 60, 8);
            ctx.fillStyle = '#fbbf24';
            ctx.beginPath();
            ctx.arc(ballX, ballY, 6, 0, Math.PI * 2);
            ctx.fill();
        };
        loop();
    },

    // 10. TETRIS
    initTetris(stage, updateScore) {
        stage.innerHTML = `<div class="tetris-box"><p>Tetris Arkada rejimi</p><p style="color:#38bdf8; font-size: 24px;">🧱</p><p>Tezkor tugmalarni bosing!</p></div>`;
        let score = 0;
        document.getElementById('game-controls').innerHTML = `
            <button class="btn-tap-jump" onclick="window.tetrisDrop()">⬇️ BLOKNI TUSHIRISH (+20)</button>
        `;
        window.tetrisDrop = () => {
            score += 20;
            updateScore(score);
            window.soundEngine.playCoin();
        };
    },

    initGenericArcade(stage, gameId, updateScore) {
        let score = 0;
        stage.innerHTML = `
            <div class="generic-arcade-box">
                <div style="font-size: 40px; margin-bottom: 12px;">🕹️</div>
                <h3>${gameId.toUpperCase()} O'yini</h3>
                <p style="color: #94a3b8; font-size: 13px;">O'yin maydoni tayyor. Ekranni bosing va ochko to'plang!</p>
                <button class="btn-tap-jump" onclick="window.genericTap()">🎮 O'YNASH (TAP)</button>
            </div>
        `;
        window.genericTap = () => {
            score += 10;
            updateScore(score);
            window.soundEngine.playCoin();
        };
        document.getElementById('game-controls').innerHTML = '';
    }
};
