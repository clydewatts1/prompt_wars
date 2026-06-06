import React, { useState, useEffect, useRef } from 'react';
import HexGrid from './HexGrid';
import Sidebar from './Sidebar';
import PlaybackControls from './PlaybackControls';

function App() {
  const [config, setConfig] = useState(null);
  const [replay, setReplay] = useState([]);
  const [currentCycle, setCurrentCycle] = useState(0);
  const [isPlaying, setIsPlaying] = useState(false);
  const [speed, setSpeed] = useState(500); // ms per frame
  const [isLive, setIsLive] = useState(false);
  const [selectedBotId, setSelectedBotId] = useState(null);
  
  const [finale, setFinale] = useState(null);
  const [showWinner, setShowWinner] = useState(false);
  const [hasAutoTriggered, setHasAutoTriggered] = useState(false);

  // Fetch initial data
  useEffect(() => {
    const fetchData = async () => {
      try {
        const confRes = await fetch('http://localhost:5000/api/config');
        const confData = await confRes.json();
        setConfig(confData);
        
        const repRes = await fetch('http://localhost:5000/api/replay');
        const repData = await repRes.json();
        setReplay(repData);

        const finRes = await fetch('http://localhost:5000/api/finale');
        const finData = await finRes.json();
        setFinale(finData);
        
        if (repData.length > 0) {
          setCurrentCycle(repData[0].cycle_id);
          // auto-select first bot
          if (repData[0].bot_states?.length > 0) {
            setSelectedBotId(repData[0].bot_states[0].bot_id);
          }
        }
      } catch (err) {
        console.error("Failed to load data", err);
      }
    };
    fetchData();
  }, []);

  // Live polling
  useEffect(() => {
    if (!isLive) return;
    const interval = setInterval(async () => {
      try {
        const repRes = await fetch('http://localhost:5000/api/replay');
        const repData = await repRes.json();
        setReplay(repData);

        const finRes = await fetch('http://localhost:5000/api/finale');
        const finData = await finRes.json();
        setFinale(finData);
        
        // Jump to latest cycle if playing or just to keep up
        if (repData.length > 0) {
           setCurrentCycle(repData[repData.length - 1].cycle_id);
        }
      } catch (err) {
        console.error("Live fetch failed", err);
      }
    }, 5000); // poll every 5s instead of 30s for responsiveness
    return () => clearInterval(interval);
  }, [isLive]);

  // Playback timer
  useEffect(() => {
    if (!isPlaying) return;
    const currentIndex = replay.findIndex(r => r.cycle_id === currentCycle);
    if (currentIndex === -1 || currentIndex >= replay.length - 1) {
      setIsPlaying(false);
      return;
    }
    const timer = setTimeout(() => {
      setCurrentCycle(replay[currentIndex + 1].cycle_id);
    }, speed);
    return () => clearTimeout(timer);
  }, [isPlaying, currentCycle, replay, speed]);

  // Automatically trigger winner banner at the end of playback
  useEffect(() => {
    if (replay.length > 0 && currentCycle === replay[replay.length - 1].cycle_id) {
      const isGameOver = finale && finale.cycle_terminated === currentCycle;
      if (isGameOver && !hasAutoTriggered) {
        setShowWinner(true);
        setHasAutoTriggered(true);
      }
    } else {
      setHasAutoTriggered(false);
    }
  }, [currentCycle, replay, finale, hasAutoTriggered]);

  const currentFrame = replay.find(r => r.cycle_id === currentCycle) || replay[0];

  if (!config || replay.length === 0) {
    return <div style={{padding: 40}}>Loading Prompt Wars Data...</div>;
  }

  const handleSeek = (cycleId) => {
    setCurrentCycle(cycleId);
  };

  return (
    <div className="app-container">
      <div className="canvas-container">
        <HexGrid 
          frame={currentFrame} 
          config={config} 
          selectedBotId={selectedBotId}
          onSelectBot={setSelectedBotId}
        />
        <div className="legend">
          <div className="legend-item"><div className="legend-color" style={{backgroundColor: 'var(--hex-grass)'}}></div> Grass</div>
          <div className="legend-item"><div className="legend-color" style={{backgroundColor: 'var(--hex-control)'}}></div> Control</div>
          <div className="legend-item"><div className="legend-color" style={{backgroundColor: 'var(--hex-forest)'}}></div> Forest</div>
          <div className="legend-item"><div className="legend-color" style={{backgroundColor: 'var(--hex-wreckage)'}}></div> Wreckage</div>
          <div className="legend-item"><div className="legend-color" style={{backgroundColor: 'var(--hex-ground)'}}></div> Ground</div>
          <div className="legend-item"><div className="legend-color" style={{backgroundColor: 'var(--hex-asteroid)'}}></div> Asteroid</div>
          <div className="legend-item"><div className="legend-color" style={{backgroundColor: '#fff', border: '1px solid #000', borderRadius: '50%'}}></div> Ball</div>
          <div className="legend-item"><div className="legend-color" style={{borderColor: '#facc15', borderWidth: '2px', borderStyle: 'solid', backgroundColor: 'transparent'}}></div> Goal</div>
          <div className="legend-item"><div className="legend-color" style={{backgroundColor: '#9ca3af', border: '1px solid #4b5563'}}></div> Rock</div>
        </div>
        <PlaybackControls 
          replay={replay}
          currentCycle={currentCycle}
          isPlaying={isPlaying}
          setIsPlaying={setIsPlaying}
          isLive={isLive}
          setIsLive={setIsLive}
          speed={speed}
          setSpeed={setSpeed}
          onSeek={handleSeek}
          hasFinale={!!(finale && finale.overlord_verdict)}
          onShowWinner={() => setShowWinner(true)}
        />
      </div>
      <Sidebar 
        frame={currentFrame} 
        replay={replay}
        selectedBotId={selectedBotId}
        config={config}
      />

      {showWinner && finale && finale.overlord_verdict && (
        <div className="winner-overlay" onClick={() => setShowWinner(false)}>
          <div className={`winner-card ${(finale.overlord_verdict.winner?.team || 'red').toLowerCase()}`} onClick={(e) => e.stopPropagation()}>
            <div className="confetti-container">
              {Array.from({ length: 40 }).map((_, i) => {
                const left = Math.random() * 100;
                const delay = Math.random() * 3;
                const duration = 2 + Math.random() * 2;
                const colors = ['#ef4444', '#3b82f6', '#22c55e', '#eab308', '#ec4899', '#a855f7'];
                const randomColor = colors[Math.floor(Math.random() * colors.length)];
                return (
                  <div 
                    key={i} 
                    className="confetti-piece" 
                    style={{
                      left: `${left}%`,
                      animationDelay: `${delay}s`,
                      animationDuration: `${duration}s`,
                      backgroundColor: randomColor
                    }}
                  />
                );
              })}
            </div>
            <div className="winner-badge">🏆</div>
            <h2 className={`winner-title ${(finale.overlord_verdict.winner?.team || 'red').toLowerCase()}`}>
              {finale.overlord_verdict.winner?.name || 'Unknown'} Wins!
            </h2>
            <p style={{ color: 'var(--text-muted)', fontSize: '14px', fontWeight: 600, marginTop: '4px' }}>
              TEAM {(finale.overlord_verdict.winner?.team || 'RED').toUpperCase()} • SCORE {finale.overlord_verdict.winner?.total_score}/100
            </p>

            <div className={`winner-verdict ${(finale.overlord_verdict.winner?.team || 'red').toLowerCase()}`}>
              <strong>Overlord Verdict:</strong>
              <p style={{ marginTop: '8px' }}>
                {finale.overlord_verdict.winner?.verdict || finale.termination_reason}
              </p>
            </div>

            <table className="scores-table">
              <thead>
                <tr>
                  <th>Bot</th>
                  <th>Team</th>
                  <th>Status</th>
                  <th>Final Score</th>
                </tr>
              </thead>
              <tbody>
                {finale.overlord_verdict.bot_evaluations
                  ?.sort((a, b) => b.total_score - a.total_score)
                  .map((bot) => {
                    const isWinner = bot.bot_id === finale.overlord_verdict.winner?.bot_id;
                    return (
                      <tr key={bot.bot_id} className={isWinner ? "winner-row" : ""}>
                        <td>{bot.name} {isWinner ? "👑" : ""}</td>
                        <td style={{ color: `var(--${bot.team.toLowerCase()}-team)`, fontWeight: 700 }}>
                          {bot.team.toUpperCase()}
                        </td>
                        <td>{bot.is_alive ? "🟢 Alive" : `💀 Starved (Cycle ${bot.destruction_order || '?'})`}</td>
                        <td style={{ fontWeight: 800 }}>{bot.total_score}</td>
                      </tr>
                    );
                  })}
              </tbody>
            </table>

            <button className="close-btn" onClick={() => setShowWinner(false)}>
              Inspect Battlefield
            </button>
          </div>
        </div>
      )}
    </div>
  );
}

export default App;
