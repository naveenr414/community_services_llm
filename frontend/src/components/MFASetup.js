// MFASetup.js - MFA setup component
import React, { useState, useEffect } from 'react';
import { authenticatedFetch } from '../utils/api';
import '../styles/pages/mfa.css';

function MFASetup({ onClose, onSuccess }) {
  const [step, setStep] = useState('loading');
  const [qrCode, setQrCode] = useState('');
  const [secret, setSecret] = useState('');
  const [verificationCode, setVerificationCode] = useState('');
  const [error, setError] = useState('');
  const [isSubmitting, setIsSubmitting] = useState(false);

  useEffect(() => {
    fetchQRCode();
  }, []);

  const fetchQRCode = async () => {
    try {
      const response = await authenticatedFetch('/api/auth/mfa/setup', {
        method: 'POST',
      });
      const data = await response.json();
      setQrCode(data.qr_code);
      setSecret(data.secret);
      setStep('setup');
    } catch (error) {
      console.error('Error fetching QR code:', error);
      setError('Failed to generate QR code');
      setStep('setup');
    }
  };

  const handleVerify = async (e) => {
    e.preventDefault();
    setError('');
    setIsSubmitting(true);

    try {
      const response = await authenticatedFetch('/api/auth/mfa/enable', {
        method: 'POST',
        body: JSON.stringify({ code: verificationCode })
      });

      const data = await response.json();
      if (data.success) {
        setStep('success');
        setTimeout(() => {
          onSuccess();
          onClose();
        }, 2000);
      }
    } catch (error) {
      setError('Invalid code. Please try again.');
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div className="modal-overlay">
      <div className="modal-content mfa-modal">
        <h2>Set Up Two-Factor Authentication</h2>

        {step === 'loading' && (
          <div className="loading">Loading...</div>
        )}

        {step === 'setup' && (
          <>
            <p className="mfa-instructions">
              Scan this QR code with your authenticator app (Google Authenticator, Duo Mobile, Authy, etc.)
            </p>
            
            {qrCode && (
              <div className="qr-code-container">
                <img src={qrCode} alt="MFA QR Code" />
              </div>
            )}

            <div className="secret-backup">
              <p><strong>Manual entry code:</strong></p>
              <code className="secret-code">{secret}</code>
              <p className="help-text">Save this code in a safe place as a backup</p>
            </div>

            <form onSubmit={handleVerify}>
              <div className="form-group">
                <label>Enter the 6-digit code from your app:</label>
                <input
                  type="text"
                  value={verificationCode}
                  onChange={(e) => setVerificationCode(e.target.value.replace(/\D/g, '').slice(0, 6))}
                  placeholder="000000"
                  maxLength="6"
                  required
                  className="mfa-code-input"
                  autoFocus
                />
              </div>

              {error && <div className="error-message">{error}</div>}

              <div className="modal-buttons">
                <button type="button" onClick={onClose} className="btn-cancel">
                  Cancel
                </button>
                <button 
                  type="submit" 
                  className="btn-confirm" 
                  disabled={isSubmitting || verificationCode.length !== 6}
                >
                  {isSubmitting ? 'Verifying...' : 'Enable MFA'}
                </button>
              </div>
            </form>
          </>
        )}

        {step === 'success' && (
          <div className="success-message">
            <div className="success-icon">✓</div>
            <p>Two-Factor Authentication has been enabled successfully!</p>
          </div>
        )}
      </div>
    </div>
  );
}

export default MFASetup;