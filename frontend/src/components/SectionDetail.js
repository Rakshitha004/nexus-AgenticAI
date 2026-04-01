import React from 'react';
import { useParams, useNavigate } from 'react-router-dom';

function SectionDetail() {
  const { section } = useParams();
  const navigate = useNavigate();

  const sectionData = {
    'attendance': {
      title: 'Attendance Records',
      content: 'Your attendance for AIML courses is 85%. You have attended 17 out of 20 classes this semester.'
    },
    'timetable': {
      title: 'Class Timetable',
      content: 'Monday: Machine Learning (9:00-10:30), Deep Learning (11:00-12:30)\nTuesday: Data Structures (9:00-10:30), AI Ethics (11:00-12:30)\nWednesday: Neural Networks (9:00-10:30), Computer Vision (11:00-12:30)\nThursday: Natural Language Processing (9:00-10:30), Big Data Analytics (11:00-12:30)\nFriday: Project Work (9:00-12:00)'
    },
    'results': {
      title: 'Academic Results',
      content: 'Semester 1: GPA 8.5\nSemester 2: GPA 8.7\nSemester 3: GPA 9.0\nOverall GPA: 8.7'
    },
    'academic-details': {
      title: 'Academic Details',
      content: 'Program: B.Tech in Artificial Intelligence and Machine Learning\nYear: 3rd Year\nSpecialization: Deep Learning and Computer Vision\nCredits Completed: 120/160\nExpected Graduation: 2025'
    },
    'fees-structure': {
      title: 'Fees Structure',
      content: 'Tuition Fee: ₹1,50,000 per year\nHostel Fee: ₹80,000 per year\nMess Fee: ₹40,000 per year\nTotal Annual Fee: ₹2,70,000\nScholarship Available: ₹50,000 (based on merit)\nNet Payable: ₹2,20,000'
    }
  };

  const data = sectionData[section];

  if (!data) {
    return <div>Section not found</div>;
  }

  return (
    <div className="glass-container" style={{ padding: '40px 24px' }}>
      <div style={{ maxWidth: '900px', margin: '0 auto', display: 'flex', flexDirection: 'column', gap: '32px' }}>
        
        <div style={{ display: 'flex', alignItems: 'center', gap: '20px' }}>
          <button
            onClick={() => navigate('/dashboard')}
            className="glass-button secondary"
            style={{ padding: '10px 20px', borderRadius: '30px' }}
          >
            ← Back to Dashboard
          </button>
        </div>

        <div className="glass-card" style={{ padding: '40px', animation: 'slideIn 0.3s ease-out' }}>
          <h1 style={{ 
            fontSize: '2.5rem', 
            marginBottom: '24px', 
            fontWeight: 800,
            background: 'linear-gradient(to right, var(--accent-primary), var(--accent-secondary))',
            WebkitBackgroundClip: 'text',
            WebkitTextFillColor: 'transparent'
          }}>
            {data.title}
          </h1>
          
          <div style={{ 
            fontSize: '1.1rem', 
            lineHeight: '1.8', 
            color: 'var(--text-main)',
            whiteSpace: 'pre-line',
            background: 'rgba(255, 255, 255, 0.03)',
            padding: '24px',
            borderRadius: '12px',
            border: '1px solid var(--glass-border)'
          }}>
            {data.content}
          </div>
        </div>
      </div>
    </div>
  );
}

export default SectionDetail;
