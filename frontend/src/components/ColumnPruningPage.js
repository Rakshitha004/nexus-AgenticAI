import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { getApiBase } from '../config';

const API_BASE = getApiBase();
const PRUNE_URL = `${API_BASE}/column-pruning/prune-columns`;

function ColumnPruningPage() {
  const navigate = useNavigate();
  const [query, setQuery] = useState('');
  const [useLLM, setUseLLM] = useState(false);
  const [loading, setLoading] = useState(false);
  const [status, setStatus] = useState(null);
  const [error, setError] = useState(null);
  const [result, setResult] = useState(null);

  const handlePrune = async () => {
    if (!query.trim()) return;
    
    setLoading(true);
    setError(null);
    setStatus(null);
    setResult(null);

    const formData = new FormData();
    formData.append('query', query.trim());
    formData.append('use_llm', useLLM);

    try {
      const res = await fetch(PRUNE_URL, {
        method: 'POST',
        body: formData,
      });
      const data = await res.json().catch(() => ({}));
      if (!res.ok) {
        setError(typeof data.detail === 'string' ? data.detail : JSON.stringify(data.detail || data) || res.statusText);
        return;
      }
      setResult(data);
      setStatus('Columns pruned successfully!');
    } catch (e) {
      setError(e.message || String(e));
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="glass-container" style={{ padding: '40px 24px' }}>
      <div style={{ maxWidth: 800, margin: '0 auto', display: 'flex', flexDirection: 'column', gap: '32px' }}>
        
        {/* Header Section */}
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <div>
            <h1 style={{ margin: 0, fontSize: '2rem', fontWeight: 700, letterSpacing: '-1px' }}>Column Pruning</h1>
            <p style={{ margin: '4px 0 0', color: 'var(--text-dim)', fontSize: '1rem' }}>Database-wide intelligent feature selection</p>
          </div>
          <button
            type="button"
            onClick={() => navigate('/chatbot')}
            className="glass-button secondary"
            style={{ padding: '10px 20px', borderRadius: '30px' }}
          >
            ← Back to Chat
          </button>
        </div>

        {/* Input Card */}
        <div className="glass-card" style={{ padding: '32px', display: 'flex', flexDirection: 'column', gap: '24px' }}>
          <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
            <label style={{ fontSize: '0.9rem', fontWeight: 600, color: 'var(--accent-primary)', textTransform: 'uppercase', letterSpacing: '1px' }}>
              Your Query
            </label>
            <input
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="e.g. show me the average grades for 3rd sem"
              className="glass-input"
              style={{ fontSize: '1.1rem', padding: '16px' }}
            />
          </div>

          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <label style={{ display: 'flex', alignItems: 'center', gap: '12px', cursor: 'pointer', userSelect: 'none' }}>
              <input
                type="checkbox"
                checked={useLLM}
                onChange={(e) => setUseLLM(e.target.checked)}
                style={{ width: '20px', height: '20px', accentColor: 'var(--accent-primary)' }}
              />
              <span style={{ fontSize: '0.95rem', color: 'var(--text-main)' }}>Enable LLM Reasoning</span>
            </label>

            <button
              type="button"
              onClick={handlePrune}
              disabled={loading || !query.trim()}
              className="glass-button"
              style={{ padding: '14px 32px', minWidth: '200px' }}
            >
              {loading ? 'Pruning...' : 'Run Pruning'}
            </button>
          </div>
        </div>

        {/* Messages */}
        {error && (
          <div className="glass-card" style={{ padding: '16px', background: 'rgba(239, 68, 68, 0.1)', borderColor: 'rgba(239, 68, 68, 0.2)', color: '#f87171' }}>
            <strong>Error:</strong> {error}
          </div>
        )}

        {/* Results Section */}
        {result && (
          <div className="glass-card" style={{ padding: '32px', animation: 'slideIn 0.4s ease-out' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: '24px' }}>
              <div>
                <h2 style={{ fontSize: '1.5rem', marginBottom: '8px' }}>Analysis Results</h2>
                <p style={{ color: 'var(--accent-secondary)', fontWeight: 600 }}>
                  🎯 {result.matched_table_alias}
                </p>
              </div>
              <div style={{ textAlign: 'right' }}>
                <span style={{ display: 'block', fontSize: '1.5rem', fontWeight: 700, color: 'var(--accent-secondary)' }}>{result.reduction_pct}%</span>
                <span style={{ fontSize: '0.8rem', color: 'var(--text-dim)', textTransform: 'uppercase' }}>Reduction</span>
              </div>
            </div>

            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '24px', marginBottom: '32px' }}>
              <div className="glass-card" style={{ padding: '16px', background: 'rgba(16, 185, 129, 0.05)' }}>
                <h4 style={{ marginBottom: '12px', fontSize: '0.9rem', color: 'var(--accent-secondary)' }}>COLUMNS KEPT</h4>
                <div style={{ display: 'flex', flexWrap: 'wrap', gap: '6px' }}>
                  {result.kept.map((col) => (
                    <span key={col} style={{ background: 'rgba(16, 185, 129, 0.2)', color: '#6ee7b7', padding: '4px 10px', borderRadius: '12px', fontSize: '0.8rem' }}>{col}</span>
                  ))}
                </div>
              </div>
              <div className="glass-card" style={{ padding: '16px', background: 'rgba(239, 68, 68, 0.05)' }}>
                <h4 style={{ marginBottom: '12px', fontSize: '0.9rem', color: '#f87171' }}>COLUMNS DROPPED</h4>
                <div style={{ display: 'flex', flexWrap: 'wrap', gap: '6px' }}>
                  {result.dropped.length > 0 ? result.dropped.map((col) => (
                    <span key={col} style={{ background: 'rgba(239, 68, 68, 0.2)', color: '#fca5a5', padding: '4px 10px', borderRadius: '12px', fontSize: '0.8rem' }}>{col}</span>
                  )) : <span style={{ color: 'var(--text-dim)', fontSize: '0.8rem' }}>None</span>}
                </div>
              </div>
            </div>

            <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
              <h4 style={{ fontSize: '0.9rem', color: 'var(--text-dim)', textTransform: 'uppercase', letterSpacing: '1px' }}>Reasoning Data</h4>
              <pre
                style={{
                  padding: '16px',
                  background: 'rgba(0, 0, 0, 0.3)',
                  borderRadius: '12px',
                  overflow: 'auto',
                  fontSize: '0.85rem',
                  lineHeight: '1.5',
                  color: '#e2e8f0',
                  border: '1px solid var(--glass-border)',
                }}
              >
                {JSON.stringify(result.reasons, null, 2)}
              </pre>
            </div>
          </div>
        )}

        {/* API Endpoint Helper */}
        {!result && !loading && (
          <div className="glass-card" style={{ padding: '20px', background: 'rgba(0,0,0,0.2)' }}>
            <span style={{ fontSize: '0.8rem', color: 'var(--text-dim)', display: 'block', marginBottom: '8px' }}>API ENDPOINT</span>
            <code style={{ color: 'var(--accent-secondary)', fontSize: '0.85rem' }}>{PRUNE_URL}</code>
          </div>
        )}
      </div>
    </div>
  );
}

export default ColumnPruningPage;
