// useInactivityTimeout.js - Custom hook for handling user inactivity and auto-logout
import { useEffect, useRef, useCallback } from 'react';

/**
 * Hook that monitors user activity and triggers logout after specified inactivity period
 * @param {Function} onTimeout - Callback function to execute when timeout occurs
 * @param {number} timeoutMinutes - Minutes of inactivity before logout (default: 30)
 */
export const useInactivityTimeout = (onTimeout, timeoutMinutes = 30) => {
  const timeoutRef = useRef(null);
  const TIMEOUT_MS = timeoutMinutes * 60 * 1000;

  const resetTimer = useCallback(() => {
    // Clear existing timeout
    if (timeoutRef.current) {
      clearTimeout(timeoutRef.current);
    }

    // Set new timeout
    timeoutRef.current = setTimeout(() => {
      console.log('[Inactivity] Timeout reached, logging out...');
      onTimeout();
    }, TIMEOUT_MS);
  }, [onTimeout, TIMEOUT_MS]);

  useEffect(() => {
    // Events that indicate user activity
    const events = [
      'mousedown',
      'mousemove',
      'keypress',
      'scroll',
      'touchstart',
      'click',
    ];

    // Reset timer on any user activity
    const handleActivity = () => {
      resetTimer();
    };

    // Add event listeners
    events.forEach(event => {
      document.addEventListener(event, handleActivity);
    });

    // Start initial timer
    resetTimer();

    // Cleanup
    return () => {
      if (timeoutRef.current) {
        clearTimeout(timeoutRef.current);
      }
      events.forEach(event => {
        document.removeEventListener(event, handleActivity);
      });
    };
  }, [resetTimer]);

  return { resetTimer };
};