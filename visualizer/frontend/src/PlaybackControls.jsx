import React from 'react';
import { Play, Pause, SkipBack, SkipForward, Radio, FastForward } from 'lucide-react';

const PlaybackControls = ({ 
  replay, 
  currentCycle, 
  isPlaying, 
  setIsPlaying, 
  isLive, 
  setIsLive,
  speed,
  setSpeed,
  onSeek,
  hasFinale,
  onShowWinner
}) => {
  const minCycle = replay.length > 0 ? replay[0].cycle_id : 0;
  const maxCycle = replay.length > 0 ? replay[replay.length - 1].cycle_id : 0;

  const handleSliderChange = (e) => {
    onSeek(parseInt(e.target.value));
    setIsPlaying(false);
    setIsLive(false);
  };

  const step = (dir) => {
    setIsPlaying(false);
    setIsLive(false);
    const currentIndex = replay.findIndex(r => r.cycle_id === currentCycle);
    if (currentIndex !== -1) {
      const nextIndex = Math.max(0, Math.min(replay.length - 1, currentIndex + dir));
      onSeek(replay[nextIndex].cycle_id);
    }
  };

  return (
    <div className="playback-controls">
      <button className="playback-btn" onClick={() => step(-1)} title="Previous Turn">
        <SkipBack size={20} />
      </button>
      
      <button className="playback-btn" onClick={() => { setIsPlaying(!isPlaying); setIsLive(false); }} title={isPlaying ? "Pause" : "Play"}>
        {isPlaying ? <Pause size={24} /> : <Play size={24} />}
      </button>
      
      <button className="playback-btn" onClick={() => step(1)} title="Next Turn">
        <SkipForward size={20} />
      </button>

      <div style={{width: '1px', height: '24px', backgroundColor: 'var(--border-color)', margin: '0 8px'}}></div>

      <input 
        type="range" 
        min={minCycle} 
        max={maxCycle} 
        value={currentCycle} 
        onChange={handleSliderChange}
        className="timeline-slider"
      />

      <div className="cycle-display">
        Cycle {currentCycle} / {maxCycle}
      </div>

      <div style={{width: '1px', height: '24px', backgroundColor: 'var(--border-color)', margin: '0 8px'}}></div>

      <button 
        className="playback-btn" 
        onClick={() => setSpeed(speed === 500 ? 100 : 500)} 
        title="Toggle Fast Forward"
        style={{ color: speed === 100 ? '#3b82f6' : 'inherit' }}
      >
        <FastForward size={20} />
      </button>

      <button 
        className="playback-btn" 
        onClick={() => { setIsLive(!isLive); if(!isLive) setIsPlaying(true); }} 
        title="Live Sync"
        style={{ color: isLive ? '#ef4444' : 'inherit' }}
      >
        <Radio size={20} />
      </button>

      {hasFinale && (
        <>
          <div style={{width: '1px', height: '24px', backgroundColor: 'var(--border-color)', margin: '0 8px'}}></div>
          <button 
            className="results-btn" 
            onClick={onShowWinner} 
            title="Show Match Results"
          >
            🏆 Results
          </button>
        </>
      )}
    </div>
  );
};

export default PlaybackControls;
