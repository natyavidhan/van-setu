/**
 * CorridorProposalPanel — Main panel for corridor intervention proposals
 * 
 * Shows:
 * - Overview tab: Corridor type, exposure breakdown
 * - Interventions tab: Suggested interventions with icons
 * - Before/After tab: Conceptual visualization toggle
 * - Community tab: Votes and feedback
 * 
 * Uses careful language — "suggested", "conceptual", not "predicted"
 */
import { useState, useEffect, useCallback } from 'react';
import { corridorsApi } from '../api';
import './CorridorProposalPanel.css';

const TABS = [
  { id: 'overview', label: 'Overview', icon: '📊' },
  { id: 'interventions', label: 'Interventions', icon: '🌳' },
  { id: 'vision', label: 'Before / After', icon: '👁️' },
  { id: 'community', label: 'Community', icon: '💬' },
];

/**
 * Exposure bar visualization
 */
function ExposureBar({ label, value, color, icon }) {
  const percentage = Math.round(value * 100);
  return (
    <div className="exposure-bar">
      <div className="exposure-label">
        <span className="exposure-icon">{icon}</span>
        <span>{label}</span>
      </div>
      <div className="exposure-track">
        <div 
          className="exposure-fill" 
          style={{ width: `${percentage}%`, backgroundColor: color }}
        />
      </div>
      <div className="exposure-value">{percentage}%</div>
    </div>
  );
}

/**
 * Intervention card
 */
function InterventionCard({ intervention }) {
  return (
    <div className="intervention-card">
      <div className="intervention-icon">{intervention.icon}</div>
      <div className="intervention-content">
        <h4>{intervention.name}</h4>
        <p>{intervention.description}</p>
        <span className="intervention-benefit">
          Primary benefit: {intervention.primary_benefit.replace('_', ' ')}
        </span>
      </div>
    </div>
  );
}

/**
 * Community feedback section
 */
function CommunitySection({ corridorId, communityData, onRefresh }) {
  const [comment, setComment] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [voting, setVoting] = useState(false);

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!comment.trim()) return;
    
    setSubmitting(true);
    try {
      await corridorsApi.addFeedback(corridorId, comment.trim());
      setComment('');
      onRefresh();
    } catch (err) {
      console.error('Failed to submit feedback:', err);
    } finally {
      setSubmitting(false);
    }
  };

  const handleCorridorVote = async (upvote) => {
    setVoting(true);
    try {
      await corridorsApi.voteCorridor(corridorId, upvote);
      onRefresh();
    } catch (err) {
      console.error('Failed to vote:', err);
    } finally {
      setVoting(false);
    }
  };

  const handleFeedbackVote = async (feedbackId, upvote) => {
    try {
      await corridorsApi.voteFeedback(feedbackId, upvote);
      onRefresh();
    } catch (err) {
      console.error('Failed to vote on feedback:', err);
    }
  };

  if (!communityData) return <div className="loading">Loading community data...</div>;

  return (
    <div className="community-section">
      {/* Corridor voting */}
      <div className="corridor-votes">
        <h4>Community Support</h4>
        <div className="vote-buttons">
          <button 
            className="vote-btn upvote"
            onClick={() => handleCorridorVote(true)}
            disabled={voting}
          >
            👍 {communityData.votes?.upvotes || 0}
          </button>
          <button 
            className="vote-btn downvote"
            onClick={() => handleCorridorVote(false)}
            disabled={voting}
          >
            👎 {communityData.votes?.downvotes || 0}
          </button>
        </div>
        <div className="support-level">
          {communityData.votes?.support_level || 'No votes yet'}
        </div>
      </div>

      {/* Feedback form */}
      <form className="feedback-form" onSubmit={handleSubmit}>
        <h4>Share Your Thoughts</h4>
        <textarea
          placeholder="What would improve this corridor? (e.g., 'Add benches', 'Good cycling route')"
          value={comment}
          onChange={(e) => setComment(e.target.value)}
          maxLength={500}
        />
        <button type="submit" disabled={submitting || !comment.trim()}>
          {submitting ? 'Submitting...' : 'Submit Feedback'}
        </button>
      </form>

      {/* Feedback list */}
      <div className="feedback-list">
        <h4>Community Feedback ({communityData.feedback_count || 0})</h4>
        {communityData.feedback?.length > 0 ? (
          communityData.feedback.map((item) => (
            <div key={item.id} className="feedback-item">
              <p>{item.comment}</p>
              <div className="feedback-meta">
                <span className="feedback-time">
                  {new Date(item.timestamp).toLocaleDateString()}
                </span>
                <div className="feedback-votes">
                  <button 
                    className="mini-vote"
                    onClick={() => handleFeedbackVote(item.id, true)}
                  >
                    ▲
                  </button>
                  <span>{item.votes}</span>
                  <button 
                    className="mini-vote"
                    onClick={() => handleFeedbackVote(item.id, false)}
                  >
                    ▼
                  </button>
                </div>
              </div>
            </div>
          ))
        ) : (
          <p className="no-feedback">No feedback yet. Be the first to share!</p>
        )}
      </div>
    </div>
  );
}

/**
 * Main CorridorProposalPanel component
 */
export default function CorridorProposalPanel({ corridor, onClose, onShowAfter }) {
  const [activeTab, setActiveTab] = useState('overview');
  const [proposal, setProposal] = useState(null);
  const [communityData, setCommunityData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [showAfter, setShowAfter] = useState(false);

  const corridorId = corridor?.properties?.corridor_id;

  // Load proposal data
  useEffect(() => {
    if (!corridorId) return;
    
    setLoading(true);
    corridorsApi.proposal(corridorId)
      .then(res => setProposal(res.data))
      .catch(err => console.error('Failed to load proposal:', err))
      .finally(() => setLoading(false));
  }, [corridorId]);

  // Load community data
  const loadCommunityData = useCallback(() => {
    if (!corridorId) return;
    
    corridorsApi.getCommunity(corridorId, 5)
      .then(res => setCommunityData(res.data))
      .catch(err => console.error('Failed to load community data:', err));
  }, [corridorId]);

  useEffect(() => {
    loadCommunityData();
  }, [loadCommunityData]);

  // Handle before/after toggle
  useEffect(() => {
    if (onShowAfter) {
      onShowAfter(showAfter);
    }
  }, [showAfter, onShowAfter]);

  if (!corridor) return null;

  const props = corridor.properties;
  const lengthKm = (props.length_m / 1000).toFixed(2);
  
  // Risk level based on priority
  const getRiskLevel = (priority) => {
    if (priority > 0.80) return { label: 'Critical', color: '#d73027' };
    if (priority > 0.70) return { label: 'High', color: '#fc8d59' };
    return { label: 'Elevated', color: '#fee08b' };
  };
  const risk = getRiskLevel(props.mean_priority);

  return (
    <div className="proposal-panel">
      {/* Header */}
      <div className="proposal-header">
        <div className="proposal-title">
          <h3>Corridor Proposal</h3>
          <span className="risk-badge" style={{ backgroundColor: risk.color }}>
            {risk.label}
          </span>
        </div>
        <button className="close-btn" onClick={onClose}>×</button>
      </div>

      {/* Quick stats */}
      <div className="quick-stats">
        <div className="stat">
          <span className="stat-value">{lengthKm}</span>
          <span className="stat-label">km length</span>
        </div>
        <div className="stat">
          <span className="stat-value">{props.segment_count}</span>
          <span className="stat-label">segments</span>
        </div>
        <div className="stat">
          <span className="stat-value">{(props.mean_priority * 100).toFixed(0)}%</span>
          <span className="stat-label">priority</span>
        </div>
      </div>

      {/* Tabs */}
      <div className="proposal-tabs">
        {TABS.map(tab => (
          <button
            key={tab.id}
            className={`tab-btn ${activeTab === tab.id ? 'active' : ''}`}
            onClick={() => setActiveTab(tab.id)}
          >
            <span className="tab-icon">{tab.icon}</span>
            <span className="tab-label">{tab.label}</span>
          </button>
        ))}
      </div>

      {/* Tab content */}
      <div className="proposal-content">
        {loading && activeTab !== 'community' ? (
          <div className="loading">Loading proposal...</div>
        ) : (
          <>
            {/* Overview Tab */}
            {activeTab === 'overview' && proposal && (
              <div className="tab-overview">
                <div className="corridor-type">
                  <h4>Corridor Classification</h4>
                  <div className="type-badge">{proposal.corridor_type}</div>
                  <p className="type-desc">{proposal.corridor_type_description}</p>
                </div>

                <div className="exposure-breakdown">
                  <h4>Exposure Profile</h4>
                  <ExposureBar 
                    label="Heat Exposure" 
                    value={proposal.exposure_breakdown.heat_score}
                    color="#d73027"
                    icon="🌡️"
                  />
                  <ExposureBar 
                    label="Air Pollution" 
                    value={proposal.exposure_breakdown.pollution_score}
                    color="#7570b3"
                    icon="💨"
                  />
                  <ExposureBar 
                    label="Green Deficit" 
                    value={proposal.exposure_breakdown.green_deficit_score}
                    color="#1b9e77"
                    icon="🌿"
                  />
                </div>

                <p className="disclaimer">
                  ℹ️ Classification is based on rule-based analysis of environmental data.
                </p>
              </div>
            )}

            {/* Interventions Tab */}
            {activeTab === 'interventions' && proposal && (
              <div className="tab-interventions">
                <h4>Suggested Interventions</h4>
                <p className="interventions-intro">
                  Based on the corridor's exposure profile, these interventions may be appropriate:
                </p>
                
                <div className="interventions-list">
                  {proposal.suggested_interventions.map((intervention, idx) => (
                    <InterventionCard key={idx} intervention={intervention} />
                  ))}
                </div>

                <p className="disclaimer">
                  ⚠️ These are conceptual suggestions for planning discussion.
                  Actual implementation requires detailed site assessment.
                </p>
              </div>
            )}

            {/* Before/After Tab */}
            {activeTab === 'vision' && (
              <div className="tab-vision">
                <h4>Conceptual Vision</h4>
                <p className="vision-intro">
                  Toggle to see a conceptual illustration of how this corridor 
                  might look with green infrastructure.
                </p>

                <div className="vision-toggle">
                  <span className={!showAfter ? 'active' : ''}>Before</span>
                  <label className="switch">
                    <input 
                      type="checkbox" 
                      checked={showAfter}
                      onChange={(e) => setShowAfter(e.target.checked)}
                    />
                    <span className="slider"></span>
                  </label>
                  <span className={showAfter ? 'active' : ''}>After</span>
                </div>

                <div className={`vision-preview ${showAfter ? 'after' : 'before'}`}>
                  {showAfter ? (
                    <div className="vision-after">
                      <div className="tree-row">🌳🌳🌳🌳🌳🌳🌳</div>
                      <div className="path-illustration">
                        <span className="path-element">🚶</span>
                        <span className="path-line">━━━━━━━━━━</span>
                        <span className="path-element">🚴</span>
                      </div>
                      <div className="tree-row">🌳🌲🌳🌲🌳🌲🌳</div>
                    </div>
                  ) : (
                    <div className="vision-before">
                      <div className="road-illustration">
                        <span className="road-line">▬▬▬▬▬▬▬▬▬▬</span>
                      </div>
                      <p className="before-label">Current state: Urban road corridor</p>
                    </div>
                  )}
                </div>

                <p className="disclaimer">
                  ⚠️ This is a <strong>conceptual illustration</strong>, not a simulation 
                  or predicted outcome. Actual design will vary based on site conditions.
                </p>
              </div>
            )}

            {/* Community Tab */}
            {activeTab === 'community' && (
              <CommunitySection 
                corridorId={corridorId}
                communityData={communityData}
                onRefresh={loadCommunityData}
              />
            )}
          </>
        )}
      </div>
    </div>
  );
}
