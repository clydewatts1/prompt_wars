import React from 'react';

const Sidebar = ({ frame, replay, selectedBotId, config }) => {
  if (!frame) return <div className="sidebar"></div>;

  const bot = frame.bot_states.find(b => b.bot_id === selectedBotId) || frame.bot_states[0];
  if (!bot) return <div className="sidebar"></div>;

  // Extract past logs for this bot up to current cycle
  const pastCycles = replay.filter(r => r.cycle_id <= frame.cycle_id).reverse();

  const botConfig = config?.bots?.find(b => b.bot_id === bot.bot_id) || 
                    config?.bots?.find(b => b.name?.toLowerCase() === bot.name?.toLowerCase());
  const systemPrompt = botConfig ? botConfig.system_prompt : '';

  return (
    <div className="sidebar">
      <div className="panel-section">
        <div className="bot-card">
          <div className="bot-header">
            <div className={`bot-avatar ${bot.team}`}>
              {bot.name.substring(0, 2).toUpperCase()}
            </div>
            <div>
              <div className="bot-name" style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                {bot.name}
                {systemPrompt && (
                  <div className="prompt-tooltip-container">
                    <span className="info-icon">ℹ️</span>
                    <div className="prompt-tooltip-content">
                      <strong style={{ fontSize: '12px', display: 'block', borderBottom: '1px solid var(--border-color)', paddingBottom: '6px', marginBottom: '8px' }}>
                        System Prompt
                      </strong>
                      <div style={{ maxHeight: '200px', overflowY: 'auto', whiteSpace: 'pre-wrap', fontSize: '11px', fontFamily: 'monospace', lineHeight: '1.4' }}>
                        {systemPrompt}
                      </div>
                    </div>
                  </div>
                )}
              </div>
              <div className="bot-subtitle">team {bot.team} • q:{bot.position.q} r:{bot.position.r}</div>
            </div>
          </div>

          <div className="progress-container">
            <div className="progress-header">
              <span>HP</span>
              <span>{bot.hp}/{bot.max_hp}</span>
            </div>
            <div className="progress-bar-bg">
              <div 
                className="progress-bar-fill hp" 
                style={{width: `${Math.max(0, (bot.hp / bot.max_hp) * 100)}%`}}
              ></div>
            </div>
          </div>

          <div className="progress-container">
            <div className="progress-header">
              <span>Compute</span>
              <span>{bot.compute_units} CU</span>
            </div>
            <div className="progress-bar-bg">
              <div 
                className="progress-bar-fill compute" 
                style={{width: `${Math.max(0, (bot.compute_units / bot.max_compute) * 100)}%`}}
              ></div>
            </div>
          </div>

          <div className="panel-title" style={{marginTop: '20px'}}>Memory</div>
          <div className="memory-box">
            {bot.memory_string || 'Memory core empty...'}
          </div>
        </div>
      </div>

      <div className="panel-section" style={{flex: 1, display: 'flex', flexDirection: 'column'}}>
        <div className="panel-title">ReAct Log (Up to Cycle {frame.cycle_id})</div>
        <div style={{overflowY: 'auto', flex: 1, paddingRight: '10px'}}>
          {pastCycles.map((cyc) => {
             const bState = cyc.bot_states.find(b => b.bot_id === bot.bot_id);
             // We want to show the turn result of this cycle if it exists, but the LLM reasoning isn't explicitly saved in replay unless it's in last_turn_result.
             // Usually, replay.jsonl has the raw LLM response or we just show the action.
             const action = bState?.last_turn_result?.action_attempted || 'None';
             const deduct = bState?.last_turn_result?.compute_deducted || 0;
             const status = bState?.last_turn_result?.status || '';

             return (
               <div key={cyc.cycle_id} className={`react-log-item ${bot.team}`}>
                 <div className="log-meta">Cycle {cyc.cycle_id} • {bot.name}</div>
                 <div className="log-action">
                    {action} • cost {deduct} CU • {status}
                 </div>
               </div>
             );
          })}
        </div>
      </div>

      {frame.overlord_evaluation && frame.overlord_evaluation.bot_evaluations && (
        <div className="panel-section" style={{backgroundColor: 'var(--bg-dark)'}}>
          <div className="panel-title">Overlord Standings</div>
          {frame.overlord_evaluation.bot_evaluations.map(ev => (
            <div key={ev.bot_id} style={{marginBottom: 16}}>
              <div style={{fontWeight: 600, fontSize: 14, marginBottom: 8}}>{ev.name}</div>
              <div className="score-row">
                <span>Survival</span>
                <span>{ev.scores.survival_efficiency}/20</span>
              </div>
              <div className="score-bar-bg">
                 <div className="score-bar-fill" style={{width: `${(ev.scores.survival_efficiency/20)*100}%`}}></div>
              </div>

              <div className="score-row">
                <span>Resource Mastery</span>
                <span>{ev.scores.resource_mastery}/20</span>
              </div>
              <div className="score-bar-bg">
                 <div className="score-bar-fill" style={{width: `${(ev.scores.resource_mastery/20)*100}%`}}></div>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
};

export default Sidebar;
