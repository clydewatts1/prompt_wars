import React, { useRef, useEffect, useState } from 'react';

const HexGrid = ({ frame, config, selectedBotId, onSelectBot }) => {
  const canvasRef = useRef(null);
  const [camera, setCamera] = useState({ x: 0, y: 0, zoom: 1 });
  const [isDragging, setIsDragging] = useState(false);
  const [dragStart, setDragStart] = useState({ x: 0, y: 0 });

  const HEX_SIZE = 30; // base size

  // Math for pointy top hex
  const hexToPixel = (q, r, size) => {
    const x = size * Math.sqrt(3) * (q + r / 2);
    const y = size * 3 / 2 * r;
    return { x, y };
  };

  const pixelToHex = (x, y, size) => {
    const q = (Math.sqrt(3) / 3 * x - 1 / 3 * y) / size;
    const r = (2 / 3 * y) / size;
    return axialRound(q, r);
  };

  const axialRound = (fq, fr) => {
    const fs = -fq - fr;
    let q = Math.round(fq);
    let r = Math.round(fr);
    let s = Math.round(fs);
    const q_diff = Math.abs(q - fq);
    const r_diff = Math.abs(r - fr);
    const s_diff = Math.abs(s - fs);
    if (q_diff > r_diff && q_diff > s_diff) {
      q = -r - s;
    } else if (r_diff > s_diff) {
      r = -q - s;
    }
    return { q, r };
  };

  const drawHex = (ctx, x, y, size, fillStyle, strokeStyle, lineWidth = 1) => {
    ctx.beginPath();
    for (let i = 0; i < 6; i++) {
      const angle_deg = 60 * i - 30;
      const angle_rad = Math.PI / 180 * angle_deg;
      const hx = x + size * Math.cos(angle_rad);
      const hy = y + size * Math.sin(angle_rad);
      if (i === 0) ctx.moveTo(hx, hy);
      else ctx.lineTo(hx, hy);
    }
    ctx.closePath();
    if (fillStyle) {
      ctx.fillStyle = fillStyle;
      ctx.fill();
    }
    if (strokeStyle) {
      ctx.lineWidth = lineWidth;
      ctx.strokeStyle = strokeStyle;
      ctx.stroke();
    }
  };

  // Rendering Loop
  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    const width = canvas.clientWidth;
    const height = canvas.clientHeight;
    
    // Support high DPI
    const dpr = window.devicePixelRatio || 1;
    canvas.width = width * dpr;
    canvas.height = height * dpr;
    ctx.scale(dpr, dpr);
    
    // Clear background
    const isDark = window.matchMedia('(prefers-color-scheme: dark)').matches;
    ctx.fillStyle = isDark ? '#0f172a' : '#fafafa';
    ctx.fillRect(0, 0, width, height);
    
    ctx.save();
    // Move to center + camera offset
    ctx.translate(width / 2 + camera.x, height / 2 + camera.y);
    ctx.scale(camera.zoom, camera.zoom);

    if (!frame || !frame.board_state) {
      ctx.restore();
      return;
    }

    const { cells } = frame.board_state;
    const size = HEX_SIZE;

    // Draw boundary circle based on current_radius
    const radiusSize = frame.board_state.current_radius;
    // max hex distance is roughly radiusSize * size * sqrt(3)
    const maxPixelDist = (radiusSize + 0.5) * size * Math.sqrt(3);
    ctx.beginPath();
    ctx.arc(0, 0, maxPixelDist, 0, Math.PI * 2);
    ctx.strokeStyle = isDark ? 'rgba(255,255,255,0.1)' : 'rgba(0,0,0,0.1)';
    ctx.setLineDash([5, 5]);
    ctx.lineWidth = 2;
    ctx.stroke();
    ctx.setLineDash([]);

    // Draw cells
    Object.values(cells).forEach(cell => {
      const { q, r } = cell.coordinate;
      const { x, y } = hexToPixel(q, r, size);
      
      let fillStyle = 'transparent';
      let strokeStyle = isDark ? '#334155' : '#e5e7eb';
      
      switch(cell.terrain) {
        case 'grass': fillStyle = isDark ? '#166534' : '#dcfce7'; break;
        case 'forest': fillStyle = isDark ? '#14532d' : '#86efac'; break;
        case 'asteroid': fillStyle = isDark ? '#1e293b' : '#a3a3a3'; break;
        case 'ground': fillStyle = 'transparent'; break;
      }
      
      if (cell.capture_progress >= 100) {
        fillStyle = '#60a5fa'; // control node owned
      }

      // Base Hex
      drawHex(ctx, x, y, size - 1, fillStyle, strokeStyle, 1);

      // Wreckage
      if (cell.wreckage) {
         drawHex(ctx, x, y, size / 2, '#fbbf24', null);
      }
      
      // Structure
      if (cell.structure) {
         drawHex(ctx, x, y, size * 0.7, null, isDark ? '#fff' : '#000', 2);
      }

      // Rock
      if (cell.rock) {
         drawHex(ctx, x, y, size * 0.8, isDark ? '#4b5563' : '#9ca3af', isDark ? '#1f2937' : '#4b5563', 2);
      }
      
      // Goal
      if (cell.goal) {
         drawHex(ctx, x, y, size * 0.8, 'rgba(250, 204, 21, 0.3)', '#facc15', 3);
         ctx.beginPath();
         ctx.arc(x, y, size * 0.15, 0, Math.PI * 2);
         ctx.fillStyle = cell.goal_owner === 'red' ? '#ef4444' : (cell.goal_owner === 'blue' ? '#3b82f6' : (q < 0 ? '#ef4444' : (q > 0 ? '#3b82f6' : '#facc15')));
         ctx.fill();
         ctx.strokeStyle = '#fff';
         ctx.lineWidth = 1.5;
         ctx.stroke();
      }
      
      // Ball
      if (cell.ball) {
         const ballRadius = size * 0.5;
         ctx.beginPath();
         ctx.arc(x, y, ballRadius, 0, Math.PI * 2);
         ctx.fillStyle = '#d1d5db'; // light grey
         ctx.fill();
         ctx.strokeStyle = '#000';
         ctx.lineWidth = 2;
         ctx.stroke();
         
         // simple pentagon in center to look like a soccer ball
         ctx.beginPath();
         for (let i = 0; i < 5; i++) {
           const angle = (Math.PI * 2 * i) / 5 - Math.PI / 2;
           const px = x + Math.cos(angle) * (ballRadius * 0.4);
           const py = y + Math.sin(angle) * (ballRadius * 0.4);
           if (i === 0) ctx.moveTo(px, py);
           else ctx.lineTo(px, py);
         }
         ctx.closePath();
         ctx.fillStyle = '#1f2937'; // black
         ctx.fill();

         // lines radiating from pentagon to edge
         ctx.beginPath();
         for (let i = 0; i < 5; i++) {
           const angle = (Math.PI * 2 * i) / 5 - Math.PI / 2;
           const px1 = x + Math.cos(angle) * (ballRadius * 0.4);
           const py1 = y + Math.sin(angle) * (ballRadius * 0.4);
           const px2 = x + Math.cos(angle) * ballRadius;
           const py2 = y + Math.sin(angle) * ballRadius;
           ctx.moveTo(px1, py1);
           ctx.lineTo(px2, py2);
         }
         ctx.strokeStyle = '#1f2937';
         ctx.lineWidth = 1.5;
         ctx.stroke();
      }
    });

    // Draw Bots
    frame.bot_states.forEach(bot => {
      if (!bot.is_alive) return;
      const { q, r } = bot.position;
      const { x, y } = hexToPixel(q, r, size);
      
      const isSelected = selectedBotId === bot.bot_id;
      const botColor = bot.team === 'red' ? '#ef4444' : '#3b82f6';

      // Bot Base
      drawHex(ctx, x, y, size * 0.8, botColor, isSelected ? '#fff' : 'rgba(0,0,0,0.5)', isSelected ? 3 : 1);
      
      // HP Text
      ctx.fillStyle = '#fff';
      ctx.font = `bold ${size * 0.4}px Inter`;
      ctx.textAlign = 'center';
      ctx.textBaseline = 'middle';
      ctx.fillText(`${bot.hp}`, x, y);

      // Label
      if (isSelected) {
        ctx.fillStyle = isDark ? '#fff' : '#000';
        ctx.font = `bold 12px Inter`;
        ctx.fillText(`${bot.name} HP:${bot.hp}`, x, y - size - 10);
      }
    });

    ctx.restore();

    // Scoreboard for football mode
    if (frame.board_state && frame.board_state.team_scores) {
      const scores = frame.board_state.team_scores;
      // Only show if the scores object exists and looks like a football match
      if (scores.red !== undefined && scores.blue !== undefined) {
        ctx.fillStyle = isDark ? 'rgba(15, 23, 42, 0.8)' : 'rgba(255, 255, 255, 0.8)';
        ctx.beginPath();
        if (ctx.roundRect) {
          ctx.roundRect(width / 2 - 100, 20, 200, 50, 10);
        } else {
          ctx.rect(width / 2 - 100, 20, 200, 50); // Fallback
        }
        ctx.fill();
        ctx.strokeStyle = isDark ? '#334155' : '#e5e7eb';
        ctx.stroke();

        ctx.font = 'bold 24px Inter';
        ctx.textAlign = 'center';
        ctx.textBaseline = 'middle';
        
        ctx.fillStyle = '#ef4444';
        ctx.fillText(`RED ${scores.red}`, width / 2 - 40, 45);
        
        ctx.fillStyle = '#3b82f6';
        ctx.fillText(`${scores.blue} BLU`, width / 2 + 40, 45);
        
        ctx.fillStyle = isDark ? '#fff' : '#000';
        ctx.font = 'bold 20px Inter';
        ctx.fillText(`-`, width / 2, 45);
      }
    }
  }, [frame, camera, selectedBotId]);

  // Event Handlers
  const handleWheel = (e) => {
    const zoomSensitivity = 0.001;
    setCamera(prev => ({
      ...prev,
      zoom: Math.max(0.2, Math.min(3, prev.zoom - e.deltaY * zoomSensitivity))
    }));
  };

  const handlePointerDown = (e) => {
    setIsDragging(true);
    setDragStart({ x: e.clientX - camera.x, y: e.clientY - camera.y });
  };

  const handlePointerMove = (e) => {
    if (!isDragging) return;
    setCamera(prev => ({
      ...prev,
      x: e.clientX - dragStart.x,
      y: e.clientY - dragStart.y
    }));
  };

  const handlePointerUp = (e) => {
    setIsDragging(false);
    // Simple click detection to select bots
    if (Math.abs(e.clientX - dragStart.x - camera.x) < 5 && Math.abs(e.clientY - dragStart.y - camera.y) < 5) {
      const rect = canvasRef.current.getBoundingClientRect();
      const clickX = e.clientX - rect.left - rect.width / 2 - camera.x;
      const clickY = e.clientY - rect.top - rect.height / 2 - camera.y;
      
      const hex = pixelToHex(clickX / camera.zoom, clickY / camera.zoom, HEX_SIZE);
      
      // Find bot at this hex
      if (frame && frame.bot_states) {
        const bot = frame.bot_states.find(b => b.position.q === hex.q && b.position.r === hex.r);
        if (bot) {
          onSelectBot(bot.bot_id);
        }
      }
    }
  };

  return (
    <canvas
      ref={canvasRef}
      onWheel={handleWheel}
      onPointerDown={handlePointerDown}
      onPointerMove={handlePointerMove}
      onPointerUp={handlePointerUp}
      onPointerLeave={handlePointerUp}
    />
  );
};

export default HexGrid;
