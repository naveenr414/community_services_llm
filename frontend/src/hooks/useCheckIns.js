import { useState, useCallback } from 'react';
import { authenticatedFetch, apiGet } from '../utils/api';

const DEBUG = process.env.NODE_ENV === 'development';

export const useCheckIns = () => {
  const [checkIns, setCheckIns] = useState([]);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState(null);

  const fetchCheckIns = useCallback(async (serviceUserId) => {
    if (!serviceUserId) {
      setCheckIns([]);
      return;
    }

    const controller = new AbortController();
    setIsLoading(true);
    setError(null);

    try {
      if (DEBUG) console.log('[useCheckIns] Fetching for user:', serviceUserId);
      
      const data = await apiGet(
        `/service_user_check_ins/?service_user_id=${serviceUserId}`,
        { signal: controller.signal }
      );
      
      setCheckIns(data || []);
      if (DEBUG) console.log('[useCheckIns] Loaded', data?.length || 0, 'check-ins');
    } catch (err) {
      if (err.name === 'AbortError') {
        if (DEBUG) console.log('[useCheckIns] Fetch aborted');
        return;
      }
      console.error('[useCheckIns] Error fetching:', err);
      setError(err.message);
      setCheckIns([]);
    } finally {
      setIsLoading(false);
    }

    return () => controller.abort();
  }, []);

  const saveAllCheckIns = useCallback(async (allEdits, serviceUserId) => {
    if (!allEdits || Object.keys(allEdits).length === 0) {
      throw new Error('No changes to save');
    }

    setIsLoading(true);
    setError(null);

    try {
      if (DEBUG) console.log('[useCheckIns] Saving edits:', allEdits);

      for (const [id, data] of Object.entries(allEdits)) {
        await authenticatedFetch(`/service_user_outreach_edit/`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            check_in_id: id,
            check_in: data.check_in,
            follow_up_message: data.follow_up_message
          })
        });
      }

      // Refresh check-ins after save
      if (serviceUserId) {
        await fetchCheckIns(serviceUserId);
      }

      if (DEBUG) console.log('[useCheckIns] Successfully saved all edits');
    } catch (err) {
      console.error('[useCheckIns] Error saving:', err);
      setError(err.message);
      throw err;
    } finally {
      setIsLoading(false);
    }
  }, [fetchCheckIns]);

  const updatePatientLastSession = useCallback(async (serviceUserId, lastSession) => {
    if (!serviceUserId) {
      throw new Error('Service user ID is required');
    }

    setIsLoading(true);
    setError(null);

    try {
      if (DEBUG) console.log('[useCheckIns] Updating last session:', { serviceUserId, lastSession });

      const response = await authenticatedFetch(`/service_user/${serviceUserId}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ last_session: lastSession })
      });

      if (!response.ok) {
        throw new Error('Failed to update patient');
      }

      if (DEBUG) console.log('[useCheckIns] Successfully updated last session');
    } catch (err) {
      console.error('[useCheckIns] Error updating last session:', err);
      setError(err.message);
      throw err;
    } finally {
      setIsLoading(false);
    }
  }, []);

  const refresh = useCallback(async (serviceUserId) => {
    return fetchCheckIns(serviceUserId);
  }, [fetchCheckIns]);

  return {
    checkIns,
    isLoading,
    error,
    fetchCheckIns,
    saveAllCheckIns,
    updatePatientLastSession,
    refresh
  };
};