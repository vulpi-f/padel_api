// ====== Padel Scoreboard Logic (patched + undo globale + scelta servizio iniziale + cambio campo) ======

let ws;
let timerInterval = null;
let elapsedSeconds = 0;              // timer globale che NON torna indietro
let isMatchStarted = false;
let isMatchOver    = false;
let isServeDecisionPhase = true;     // nuova fase iniziale "Chi inizia?"

const INITIAL_MESSAGE = "Chi inizia?";

const ChangeoverMode = {
  NEVER:      'never',    // mai
  STANDARD:   'standard', // logica attuale
  END_OF_SET: 'end_of_set', // solo a fine set
  END_OF_SET_TB:'end_of_set_tb',  // fine set + tie-break ogni 6 punti
  ONLY_TB:      'only_tb'         // solo tie-break ogni 6 punti
};

const matchConfig = {
  maxSets: 5 // es. 3 per “best of 3”, 5 per “best of 5”, o 'unlimited'
};

// ——— Configurazione Ad ———
const adConfig = {
  // un solo tipo di ad per evento: 'fullScreen', 'banner' o null
  triggers: {
    onMatchStart: 'fullScreen',
    onGameEnd:    'banner',
    onSetEnd:     'fullScreen',
    onDeuce:      null
  },
  views: {
    fullScreen:  true,
    sideBanners: true
  }
};

const adManager = {
  showFullScreen() {
    if (!adConfig.views.fullScreen) return;
    this.hideBanner();
    document.body.classList.add('show-ad');
    document.body.classList.remove('show-scoreboard');
  },
  hideFullScreen() {
    document.body.classList.add('show-scoreboard');
    document.body.classList.remove('show-ad');
  },
  showBanner() {
    if (!adConfig.views.sideBanners) return;
    if (document.body.classList.contains('show-ad')) return;
    document.querySelector('.game-content').classList.add('show-ads');
  },
  hideBanner() {
    document.querySelector('.game-content').classList.remove('show-ads');
  },

  // un solo ramo possibile
  triggerAd(evt) {
    const mode = adConfig.triggers[evt];  // 'fullScreen' | 'banner' | null
    if (mode === 'fullScreen') {
      this.showFullScreen();
    } else if (mode === 'banner') {
      this.showBanner();
    }
    // null => nessuna ad
  }
};
// Scegli la modalità desiderata qui:
let changeoverMode = ChangeoverMode.ONLY_TB;

// ===== SERVE STATE =====
let servingTeam      = "team1";
let team1ServerIndex = 0; // 0 -> G1, 1 -> G2
let team2ServerIndex = 0;

// ===== Set & Tie-break =====
let firstServerTeamOfSet = "team1";
let isTieBreak    = false;
let p1TiePoints   = 0, p2TiePoints = 0;
let tbPointCount  = 0;
let tbServers     = [];
let tbFirstServer = null;
let tbNextSetFirst = null;

// ===== Punteggi =====
let p1Points    = 0, p2Points    = 0;
let team1Games  = 0, team2Games  = 0;
let team1Sets   = 0, team2Sets   = 0;
let currentSet  = 1;

// Timer relativo per il set corrente
let setStartElapsed = 0;

let pendingGameClose  = false, pendingWinner = null;

function resetPending() {
  pendingGameClose = false;
  pendingWinner = null;
}

const scoreNames      = ["0","15","30","40"];

// ===== Cambio campo =====
let isSidesFlipped      = false;
let isChangeoverPending = false;

// ===== DOM =====
const statusEl          = document.getElementById('conn-status');
const Team1ScoreEl      = document.getElementById('team1-score');
const Team2ScoreEl      = document.getElementById('team2-score');
const scoreMsgEl        = document.getElementById('score-msg');
const currentSetEl      = document.getElementById('current-set');
const Team1SetScoreEl   = document.getElementById('team1-sets');
const Team1GameScoreEl  = document.getElementById('team1-games');
const Team2SetScoreEl   = document.getElementById('team2-sets');
const Team2GameScoreEl  = document.getElementById('team2-games');
const serveBoxT1El      = document.getElementById('serve-box-team1');
const serveBoxT2El      = document.getElementById('serve-box-team2');
const setSummaryLeftEl  = document.getElementById('set-summary-left');
const setSummaryRightEl = document.getElementById('set-summary-right');
const timerEl           = document.getElementById('timer');
const wrapperEl         = document.querySelector('.scoreboard-wrapper');

// ===== Config eventi =====
const setCloseConfig = { event: "SHORT PRESS : CNT" };
const undoConfig     = { event: "LONG PRESS : RED" };
const scoreConfig = {
  "SHORT PRESS : BLU": { side: "team2", delta:  1 },
  "SHORT PRESS : RED": { side: "team1", delta:  1 }
};

// ===== Timer =====
function formatTime(sec){
  const m = Math.floor(sec/60).toString().padStart(2,'0');
  const s = (sec%60).toString().padStart(2,'0');
  return `${m}:${s}`;
}

function renderTimer(){ timerEl.textContent = formatTime(elapsedSeconds); }

function startTimer(){
  if (timerInterval) return;
  timerInterval = setInterval(()=>{ elapsedSeconds++; renderTimer(); },1000);
}
function stopTimer(){ if (timerInterval) { clearInterval(timerInterval); timerInterval=null; } }
renderTimer();

// ===== UNDO STACK =====
const stateStack = [];
function pushState(){
  stateStack.push(JSON.parse(JSON.stringify({
    p1Points, p2Points, p1TiePoints, p2TiePoints, isTieBreak,
    team1Games, team2Games, team1Sets, team2Sets,
    currentSet, pendingGameClose, pendingWinner,
    servingTeam, team1ServerIndex, team2ServerIndex,
    firstServerTeamOfSet, tbPointCount, tbServers, tbFirstServer, tbNextSetFirst,
    setStartElapsed, isMatchOver, isMatchStarted, isServeDecisionPhase,
    isSidesFlipped, isChangeoverPending,
    setSummaryLeftHTML:  setSummaryLeftEl.innerHTML,
    setSummaryRightHTML: setSummaryRightEl.innerHTML,
    scoreMsg:            scoreMsgEl.innerText
  })));
}

function undoLast() {
  while (stateStack.length) {
    const st = stateStack.pop();

    ({
      p1Points, p2Points, p1TiePoints, p2TiePoints, isTieBreak,
      team1Games, team2Games, team1Sets, team2Sets,
      currentSet, pendingGameClose, pendingWinner,
      servingTeam, team1ServerIndex, team2ServerIndex,
      firstServerTeamOfSet, tbPointCount, tbServers, tbFirstServer, tbNextSetFirst,
      setStartElapsed, isMatchOver, isMatchStarted, isServeDecisionPhase,
      isSidesFlipped, isChangeoverPending
    } = st);

    setSummaryLeftEl.innerHTML  = st.setSummaryLeftHTML;
    setSummaryRightEl.innerHTML = st.setSummaryRightHTML;

    if ((isTieBreak && hasWinCondition()) || pendingGameClose) continue;

    applySideClass();
    renderTimer();
    updateScoreUI();
    scoreMsgEl.innerText = st.scoreMsg || "";
    return;
  }
}

// ===== Cambio campo =====
function applySideClass(){
  if (!wrapperEl) return;
  wrapperEl.classList.toggle('flipped', isSidesFlipped);
}

function requestChangeover(){
  if (isChangeoverPending || !isMatchStarted || isMatchOver) return;
  pushState();
  isChangeoverPending = true;
  scoreMsgEl.innerText = "Cambio Campo";
}

function doChangeover(){
  adManager.hideBanner();
  pushState();
  isChangeoverPending = false;
  isSidesFlipped = !isSidesFlipped;
  applySideClass();
  if (isTieBreak) {
    scoreMsgEl.innerText = "TIE-BREAK";
  }
  else {scoreMsgEl.innerText = "";}
  updateScoreUI();
}

function maybeRequestChangeover(context, endedByTB = false) {
  if (isChangeoverPending || !isMatchStarted || isMatchOver) return;
  switch (context) {
    case 'game': {
      if (changeoverMode !== ChangeoverMode.STANDARD) return;
      const totGames = team1Games + team2Games;
      if (!isTieBreak && totGames % 2 === 1) {
        requestChangeover();
      }
      break;
    }
    case 'tb': {
      if ((changeoverMode === ChangeoverMode.STANDARD ||
           changeoverMode === ChangeoverMode.END_OF_SET_TB ||
           changeoverMode === ChangeoverMode.ONLY_TB)
          && isTieBreak) {
        const totPoints = p1TiePoints + p2TiePoints;
        if (totPoints !== 0 && totPoints % 6 === 0) {
          requestChangeover();
        }
      }
      break;
    }
    case 'set': {
      if ((changeoverMode === ChangeoverMode.END_OF_SET ||
           changeoverMode === ChangeoverMode.END_OF_SET_TB)
          && !endedByTB) {
        requestChangeover();
      }
      break;
    }
  }
}

// ===== Utility =====
function hasWinCondition(){
  if (isTieBreak){
    return (p1TiePoints>=7||p2TiePoints>=7) && Math.abs(p1TiePoints-p2TiePoints)>=2;
  } else {
    return (p1Points>=4||p2Points>=4) && Math.abs(p1Points-p2Points)>=2;
  }
}

function renderDeuceAdvMessage(){
  if (isServeDecisionPhase || isTieBreak || pendingGameClose || isChangeoverPending) return;

  if (p1Points >= 3 && p2Points >= 3){
    if (p1Points === p2Points){
      scoreMsgEl.innerText = "Parità";
    } else if (p1Points === p2Points + 1){
      scoreMsgEl.innerText = "Vantaggio Red";
    } else if (p2Points === p1Points + 1){
      scoreMsgEl.innerText = "Vantaggio Blue";
    }
  }
}

// ===== Tie-break =====
function buildTieBreakOrder(){
  let t1Idx = team1ServerIndex;
  let t2Idx = team2ServerIndex;

  const order = [];

  const pushBlock = (team, n)=>{
    const idx = (team === "team1") ? t1Idx : t2Idx;
    for (let k = 0; k < n; k++) order.push({ team, idx });
    if (team === "team1") t1Idx = (t1Idx + 1) % 2;
    else                  t2Idx = (t2Idx + 1) % 2;
  };

  pushBlock(servingTeam, 1);

  let nextTeam = (servingTeam === "team1") ? "team2" : "team1";
  while (order.length < 60) {
    pushBlock(nextTeam, 2);
    nextTeam = (nextTeam === "team1") ? "team2" : "team1";
  }

  return order;
}

function initTieBreak(){
  pushState();
  isTieBreak   = true;
  p1TiePoints  = 0;
  p2TiePoints  = 0;
  tbPointCount = 0;
  tbServers    = buildTieBreakOrder();
  tbFirstServer = tbServers[0];
  tbNextSetFirst = (tbFirstServer.team==="team1")?"team2":"team1";

  servingTeam = tbFirstServer.team;
  if (servingTeam==="team1") team1ServerIndex = tbFirstServer.idx;
  else                      team2ServerIndex = tbFirstServer.idx;

  scoreMsgEl.innerText = "TIE-BREAK";
  renderServeBoxes();
  updateScoreUI();
}

function advanceTieBreakServer(){
  tbPointCount++;
  const srv = tbServers[tbPointCount];
  if (!srv) return;
  servingTeam = srv.team;
  if (servingTeam==="team1") team1ServerIndex = srv.idx; else team2ServerIndex = srv.idx;
  renderServeBoxes();
}

function getDisplayPoints(pPoints, oPoints){
  if (pPoints >= 3 && oPoints >= 3){
    if (pPoints === oPoints) return "-";
    if (pPoints === oPoints + 1) return "AD";
    return "-";
  }
  return scoreNames[Math.min(pPoints,3)];
}

// ===== UI =====
function updateScoreUI(){
  if (isTieBreak){
    Team1ScoreEl.innerText = p1TiePoints;
    Team2ScoreEl.innerText = p2TiePoints;
  } else {
    Team1ScoreEl.innerText = getDisplayPoints(p1Points, p2Points);
    Team2ScoreEl.innerText = getDisplayPoints(p2Points, p1Points);
  }

  if (!isTieBreak && !pendingGameClose){
    renderDeuceAdvMessage();
  }

  Team1GameScoreEl.innerText = team1Games;
  Team2GameScoreEl.innerText = team2Games;
  Team1SetScoreEl.innerText  = team1Sets;
  Team2SetScoreEl.innerText  = team2Sets;
  currentSetEl.innerText     = `Set: ${currentSet}`;
  renderServeBoxes();
}

// ===== Check game/set =====
function checkGameWin(){
  if (pendingGameClose) return;

  let side;
  if (isTieBreak){
    if (!hasWinCondition()) return;
    side = p1TiePoints>p2TiePoints?"team1":"team2";
  } else {
    if (!hasWinCondition()) return;
    side = p1Points>p2Points?"team1":"team2";
  }
  const name = side==="team1"?"Team Red":"Team Blue";

  let willWinSet = false;
  if (isTieBreak){
    willWinSet = true;
  } else {
    const g1 = team1Games + (side==="team1"?1:0);
    const g2 = team2Games + (side==="team2"?1:0);
    if ((g1>=6||g2>=6) && Math.abs(g1-g2)>=2) willWinSet = true;
  }

  adManager.triggerAd('onGameEnd');

  pendingGameClose = true;
  pendingWinner    = side;

  scoreMsgEl.innerText = isTieBreak
    ? (willWinSet ? `Gioco e Set tie-break ${name}` : `Gioco tie-break ${name}`)
    : (willWinSet ? `Gioco e Set ${name}`           : `Gioco ${name}`);
}

// ===== Chiusura game/set =====
function closeGame() {
  if (!pendingGameClose) return;
  if (!isTieBreak) pushState();

  if (isTieBreak) {
    isTieBreak = false;
    const winner = pendingWinner;
    p1TiePoints = p2TiePoints = 0;
    endSet(winner, true);
    resetPending();
    maybeRequestChangeover('set', true);
    return;
  }

  // Game normale
  if (pendingWinner === 'team1') team1Games++;
  else team2Games++;
  p1Points = p2Points = 0;

  // Tie-break a 6-6
  if (team1Games === 6 && team2Games === 6) {
    initTieBreak();
    resetPending();
    return;
  }

  // Set vinto
  if ((team1Games >= 6 || team2Games >= 6) && Math.abs(team1Games - team2Games) >= 2) {
    endSet(pendingWinner, false);
    resetPending();
    return;
  }

  // Normale avanzamento server
  resetPending();
  advanceServerAfterGame();
  updateScoreUI();
  maybeRequestChangeover('game');
  adManager.hideBanner();
  scoreMsgEl.innerText = "";
}

function endSet(winner, endedByTB=false){
  pushState();

  const durSec = Math.max(0, elapsedSeconds - setStartElapsed);

  const finalG1 = team1Games;
  const finalG2 = team2Games;

  const entry = document.createElement('div');
  entry.textContent = `Set ${currentSet} (${formatTime(durSec)}) ${finalG1}-${finalG2}`;
  if (winner === "team1") {
    setSummaryLeftEl.appendChild(entry);
    setSummaryLeftEl.scrollTop = setSummaryLeftEl.scrollHeight;
  } else {
    setSummaryRightEl.appendChild(entry);
    setSummaryRightEl.scrollTop = setSummaryRightEl.scrollHeight;
  }

  if (winner==="team1") team1Sets++; else team2Sets++;

  const { maxSets } = matchConfig;
  const setsToWin = (typeof maxSets === 'number')
    ? Math.ceil(maxSets/2)
    : null; // null => unlimited, non chiude mai
  if (setsToWin !== null && (team1Sets === setsToWin || team2Sets === setsToWin)) {
    isMatchOver = true;
    stopTimer(); // se vuoi il timer continuo, commenta
    const champ = team1Sets === setsToWin ? "Team Red" : "Team Blue";
    scoreMsgEl.innerText = `Match vinto da ${champ}`;
    return;
  }

  currentSet++;
  team1Games = team2Games = 0;
  p1Points = p2Points = 0;
  isTieBreak = false;

  setStartElapsed = elapsedSeconds;

  if (endedByTB){
    servingTeam = tbNextSetFirst;
  } else {
    servingTeam = (firstServerTeamOfSet==="team1")?"team2":"team1";
  }
  firstServerTeamOfSet = servingTeam;

  renderServeBoxes();
  updateScoreUI();
  adManager.triggerAd('onSetEnd');
  maybeRequestChangeover('set', endedByTB);
  scoreMsgEl.innerText = "";
}

// ===== Punti =====
function applyPoint(side){
  pushState();
  if (isTieBreak){
    if (side==="team1") p1TiePoints++; else p2TiePoints++;
    checkGameWin();
    updateScoreUI();
    if (!pendingGameClose) {
      advanceTieBreakServer();
      // *** controllo cambio campo nel TB ***
      maybeRequestChangeover('tb');
    }
    return;
  }
  if (side==="team1") p1Points++; else p2Points++;
  checkGameWin();
  updateScoreUI();
}

// ===== Serve boxes =====
function renderServeBoxes(){
  serveBoxT1El.classList.remove('show');
  serveBoxT2El.classList.remove('show');

  if (!isMatchStarted || isMatchOver) return;

  serveBoxT1El.textContent = `Serve: G${team1ServerIndex+1}`;
  serveBoxT2El.textContent = `Serve: G${team2ServerIndex+1}`;

  if (servingTeam === "team1") serveBoxT1El.classList.add('show');
  else                         serveBoxT2El.classList.add('show');
}

function advanceServerAfterGame(){
  const prevTeam = servingTeam;
  servingTeam = (servingTeam==="team1")?"team2":"team1";
  if (prevTeam==="team1") team1ServerIndex = (team1ServerIndex+1)%2;
  else                    team2ServerIndex = (team2ServerIndex+1)%2;
  renderServeBoxes();
}

// ===== Match start helper =====
function startMatchWithServer(team) {
  adManager.triggerAd('onMatchStart');
  adManager.hideBanner();
  pushState();
  servingTeam = team;
  firstServerTeamOfSet = team;
  team1ServerIndex = team2ServerIndex = 0;
  isServeDecisionPhase = false;
  isMatchStarted = true;
  setStartElapsed = elapsedSeconds;
  startTimer();
  renderServeBoxes();
  updateScoreUI();
}


// ===== WebSocket =====
function connect(){
  ws = new WebSocket(`${location.protocol==='https:'?'wss':'ws'}://${location.host}/ws`);
  ws.onopen  = ()=>statusEl.innerText='connesso';
  ws.onclose = ()=>{
    statusEl.innerText='disconnesso, riconnessione in 3s...';
    setTimeout(connect,3000);
  };
  ws.onerror = e=>console.error(e);

  ws.onmessage = e=>{
    const text = e.data.trim();

    // STATUS
    if (text.startsWith("STATUS:")) {
      statusEl.innerText = text.slice(7);
      return;
    }

    // full‑screen ad mode
    if (document.body.classList.contains('show-ad')) {
      if (text === setCloseConfig.event) {
        adManager.hideFullScreen();
        closeGame();
      }
      return;
    }

    // **banner mode**
    if (document.querySelector('.game-content').classList.contains('show-ads')) {
      if (text === setCloseConfig.event) {
        adManager.hideBanner();
        closeGame();
      }
      return;
    }

    // undo sempre disponibile
    if (text === undoConfig.event) {
      undoLast();
      return;
    }

    // Conferma cambio campo in attesa
    if (isChangeoverPending){
      if (text === setCloseConfig.event){
        doChangeover();
      }
      return;
    }

    // ===== Fase scelta servizio iniziale =====
    if (isServeDecisionPhase){
      if (text === "SHORT PRESS : RED"){
        startMatchWithServer("team1");
        scoreMsgEl.innerText = "";
      } else if (text === "SHORT PRESS : BLU"){
        startMatchWithServer("team2");
        scoreMsgEl.innerText = "";
      }
      return;
    }

    // ===== Logica originale =====
    if (!isMatchStarted){
      if (!isMatchOver && text===setCloseConfig.event){
        startMatchWithServer("team1");
      }
      return;
    }
    if (isMatchOver) return;

    if (pendingGameClose){
      if (text===setCloseConfig.event){
        closeGame()
      }
      return;
    }

    const cfg = scoreConfig[text];
    if (!cfg) return;
    if (cfg.delta>0) applyPoint(cfg.side);
  };
}

// start
applySideClass();
updateScoreUI();
scoreMsgEl.innerText = INITIAL_MESSAGE;
connect();
