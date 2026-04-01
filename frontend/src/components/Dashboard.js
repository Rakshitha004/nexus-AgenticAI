import React from 'react';
import { useNavigate } from 'react-router-dom';

function Dashboard() {
  const navigate = useNavigate();

  const sections = [
    { name: 'Attendance', description: 'View your attendance records' },
    { name: 'Timetable', description: 'Check your class schedule' },
    { name: 'Results', description: 'View your academic results' },
    { name: 'Academic Details', description: 'Access your academic information' },
    { name: 'Fees Structure', description: 'Check fees and payment details' }
  ];

  const handleSectionClick = (section) => {
    navigate(`/dashboard/${section.toLowerCase().replace(' ', '-')}`);
  };

  return (
    <div className="glass-container" style={{ padding: '60px 40px' }}>
      <div style={{ maxWidth: '1200px', margin: '0 auto' }}>
        <h1 style={{
          textAlign: 'center',
          marginBottom: '60px',
          fontSize: '3.5rem',
          fontWeight: 800,
          background: 'linear-gradient(to right, #60a5fa, #34d399)',
          WebkitBackgroundClip: 'text',
          WebkitTextFillColor: 'transparent',
          letterSpacing: '-2px'
        }}>
          NEXUS DASHBOARD
        </h1>
        
        <div style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fit, minmax(320px, 1fr))',
          gap: '24px'
        }}>
          {sections.map((section, index) => (
            <div
              key={index}
              onClick={() => handleSectionClick(section.name)}
              className="glass-card"
              style={{
                padding: '40px',
                cursor: 'pointer',
                transition: 'all 0.4s cubic-bezier(0.4, 0, 0.2, 1)',
                display: 'flex',
                flexDirection: 'column',
                justifyContent: 'center',
                textAlign: 'center'
              }}
              onMouseOver={(e) => {
                e.currentTarget.style.transform = 'translateY(-8px) scale(1.02)';
                e.currentTarget.style.borderColor = 'var(--accent-primary)';
                e.currentTarget.style.background = 'rgba(255, 255, 255, 0.08)';
              }}
              onMouseOut={(e) => {
                e.currentTarget.style.transform = 'translateY(0) scale(1)';
                e.currentTarget.style.borderColor = 'var(--glass-border)';
                e.currentTarget.style.background = 'var(--glass-bg)';
              }}
            >
              <h3 style={{ 
                fontSize: '1.5rem', 
                marginBottom: '12px', 
                color: 'var(--accent-primary)',
                fontWeight: 700 
              }}>
                {section.name}
              </h3>
              <p style={{ 
                color: 'var(--text-dim)', 
                lineHeight: '1.6',
                fontSize: '0.95rem'
              }}>
                {section.description}
              </p>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

export default Dashboard;
